//! egui-based image viewer: a study of series hung into 1 / 1×2 / 2×2 viewports.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use eframe::egui;

use crate::stack::{ImageStack, Measurement};
use crate::study::{Series, Study};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tool {
    PanScroll,
    Line,
    Orthogonal,
    Circle,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LabelId {
    Line,
    Ortho1,
    Ortho2,
    Circle,
}

#[derive(Debug, Clone, PartialEq)]
pub enum DrawingState {
    Line {
        start: (f64, f64),
        current: (f64, f64),
    },
    OrthogonalStep1 {
        start: (f64, f64),
        current: (f64, f64),
    },
    OrthogonalStep2 {
        start: (f64, f64),
        end: (f64, f64),
        current: (f64, f64),
    },
    Circle {
        center: (f64, f64),
        current: (f64, f64),
    },
}

/// Wheel delta units per slice advance. Higher = slower scroll.
/// Matches `PyRadStack`'s `_DRAG_SCROLL_SENSITIVITY = 10`.
const WHEEL_SENSITIVITY: f32 = 10.0;

/// Pixels of left-click drag per slice advance.
const DRAG_SENSITIVITY: f32 = 10.0;

/// W/L drag sensitivity — units of W/L per pixel of mouse motion.
/// Matches `PyRadStack`'s `_WL_SENSITIVITY = 3.0`.
const WL_SENSITIVITY: f64 = 3.0;

/// Gap between viewports in multi-viewport layouts.
const VIEWPORT_GAP: f32 = 4.0;

/// Viewport grid layouts (PACS convention: 1×1, 1×2, 2×2).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Layout {
    One,
    TwoAcross,
    TwoByTwo,
}

impl Layout {
    const fn viewport_count(self) -> usize {
        match self {
            Self::One => 1,
            Self::TwoAcross => 2,
            Self::TwoByTwo => 4,
        }
    }

    /// Split the central area into per-viewport rects, in reading order.
    fn rects(self, area: egui::Rect) -> Vec<egui::Rect> {
        let g = VIEWPORT_GAP / 2.0;
        match self {
            Self::One => vec![area],
            Self::TwoAcross => {
                let mid_x = area.center().x;
                vec![
                    egui::Rect::from_min_max(area.min, egui::pos2(mid_x - g, area.max.y)),
                    egui::Rect::from_min_max(egui::pos2(mid_x + g, area.min.y), area.max),
                ]
            }
            Self::TwoByTwo => {
                let c = area.center();
                vec![
                    egui::Rect::from_min_max(area.min, egui::pos2(c.x - g, c.y - g)),
                    egui::Rect::from_min_max(
                        egui::pos2(c.x + g, area.min.y),
                        egui::pos2(area.max.x, c.y - g),
                    ),
                    egui::Rect::from_min_max(
                        egui::pos2(area.min.x, c.y + g),
                        egui::pos2(c.x - g, area.max.y),
                    ),
                    egui::Rect::from_min_max(egui::pos2(c.x + g, c.y + g), area.max),
                ]
            }
        }
    }
}

/// (slice index, override W/L) of whatever pixels are in the texture right now.
/// Re-upload when this differs from the stack's current state — which catches
/// both slice changes AND W/L drag (override mutates without index changing).
type TextureKey = (usize, Option<(f64, f64)>);

/// This frame's pointer/keyboard snapshot, read once and shared by all viewports.
struct PointerState {
    pos: Option<egui::Pos2>,
    /// Where the current press started; used to lock drags to one viewport.
    press_origin: Option<egui::Pos2>,
    primary_down: bool,
    primary_pressed: bool,
    primary_released: bool,
    secondary_down: bool,
    secondary_pressed: bool,
    secondary_released: bool,
    both_down: bool,
    /// Primary held alone — drag-scroll (not W/L, which is both buttons).
    primary_only_down: bool,
    delta: egui::Vec2,
    wheel_y: f32,
    shift: bool,
}

fn read_pointer_state(ctx: &egui::Context) -> PointerState {
    ctx.input(|i| {
        let primary_down = i.pointer.button_down(egui::PointerButton::Primary);
        let secondary_down = i.pointer.button_down(egui::PointerButton::Secondary);
        PointerState {
            pos: i.pointer.hover_pos(),
            press_origin: i.pointer.press_origin(),
            primary_down,
            primary_pressed: i.pointer.button_pressed(egui::PointerButton::Primary),
            primary_released: i.pointer.button_released(egui::PointerButton::Primary),
            secondary_down,
            secondary_pressed: i.pointer.button_pressed(egui::PointerButton::Secondary),
            secondary_released: i.pointer.button_released(egui::PointerButton::Secondary),
            both_down: primary_down && secondary_down,
            primary_only_down: primary_down && !secondary_down,
            delta: i.pointer.delta(),
            // In egui 0.27+, smooth_scroll_delta replaces scroll_delta.
            wheel_y: i.smooth_scroll_delta.y,
            shift: i.modifiers.shift,
        }
    })
}

/// One viewport: a hung series (stack) plus its texture and interaction state.
struct Viewport {
    stack: Option<ImageStack>,
    /// Index into the study's series list this viewport is showing.
    series_idx: Option<usize>,
    texture: Option<egui::TextureHandle>,
    /// Identifies which (slice, W/L) is currently in `texture`. None means "nothing uploaded yet".
    texture_key: Option<TextureKey>,
    /// Accumulated wheel delta; consumed in `WHEEL_SENSITIVITY` chunks per slice step.
    wheel_accum: f32,
    /// Accumulated left-click drag dy; consumed in `DRAG_SENSITIVITY` chunks per slice step.
    drag_accum: f32,
    /// Non-None when the hung series failed to decode.
    load_error: Option<String>,
    /// Name of the active W/L preset; cleared on manual W/L drag.
    active_preset_name: Option<&'static str>,
    /// Current drawing state, if any.
    drawing_measurement: Option<DrawingState>,
    /// Currently selected measurement indices on the current slice.
    selected_indices: HashSet<usize>,
    /// Screen position where right-click marquee selection started.
    selection_start_pos: Option<egui::Pos2>,
    /// Bounding box of current right-click marquee selection.
    selection_box: Option<egui::Rect>,
    /// (measurement index, label) currently being dragged, if any.
    dragged_label: Option<(usize, LabelId)>,
    /// Offset in screen coordinates from mouse pointer to top-left of the dragged label rect.
    dragged_label_offset: egui::Vec2,
    /// Track last slice index to clear selection on change.
    last_slice: Option<usize>,
}

impl Viewport {
    fn empty() -> Self {
        Self {
            stack: None,
            series_idx: None,
            texture: None,
            texture_key: None,
            wheel_accum: 0.0,
            drag_accum: 0.0,
            load_error: None,
            active_preset_name: None,
            drawing_measurement: None,
            selected_indices: HashSet::new(),
            selection_start_pos: None,
            selection_box: None,
            dragged_label: None,
            dragged_label_offset: egui::Vec2::ZERO,
            last_slice: None,
        }
    }

    /// Hang a series into this viewport, resetting all interaction state.
    fn set_series(&mut self, idx: usize, series: &Series) {
        *self = Self {
            stack: Some(ImageStack::new(series.paths.clone())),
            series_idx: Some(idx),
            ..Self::empty()
        };
    }

    fn has_measurements(&self) -> bool {
        self.stack.as_ref().is_some_and(ImageStack::has_measurements)
    }

    /// True while an interaction that needs continuous repaints is running.
    fn busy(&self) -> bool {
        self.drawing_measurement.is_some()
            || self.dragged_label.is_some()
            || self.selection_start_pos.is_some()
    }
}

/// Series thumbnail for the strip: built progressively, one per frame.
enum ThumbState {
    Pending,
    Ready(egui::TextureHandle),
    Failed,
}

/// Drag-and-drop payload: index of the dragged series in the study.
#[derive(Clone, Copy)]
struct SeriesDrag(usize);

/// Longest edge of a series thumbnail, in pixels.
const THUMB_EDGE: u32 = 96;
/// Full tile size in the strip (thumbnail + caption).
const THUMB_TILE: egui::Vec2 = egui::vec2(108.0, 124.0);

/// State for the GUI viewer: a study, up to four viewports, and global tool state.
pub struct ViewerApp {
    study: Option<Study>,
    /// Path the study was loaded from (window title + picker seeding).
    study_path: Option<PathBuf>,
    /// One entry per series in the study; built lazily, one per frame.
    thumbnails: Vec<ThumbState>,
    /// Fixed pool of four; `layout` controls how many are visible.
    viewports: Vec<Viewport>,
    layout: Layout,
    /// Index of the active viewport (keyboard target, highlighted border).
    active: usize,
    /// Currently active tool (global — applies in whichever viewport you draw).
    active_tool: Tool,
    /// Non-None when the last `load_study_path` failed; shown in the status bar.
    load_error: Option<String>,
    /// Pixel value readout ("HU: -56") under the cursor, shown in the status bar.
    hover_readout: Option<String>,
    /// Window title to push on the next frame (set on load —
    /// `load_study_path` has no `Context`, so the title is applied from `ui`).
    pending_title: Option<String>,
}

/// Render the series' center slice at its own W/L, downscaled for the strip.
fn build_thumbnail(series: &Series, ctx: &egui::Context) -> Option<egui::TextureHandle> {
    let path = series.center_path()?;
    // A one-slice stack reuses the whole decode pipeline (DICOM W/L or plain image).
    let stack = ImageStack::new(vec![path.to_path_buf()]);
    let img = stack.get_current_image().ok()?;
    let (w, h) = img.dimensions();
    if w == 0 || h == 0 {
        return None;
    }
    let scale = f64::from(THUMB_EDGE) / f64::from(w.max(h));
    // Truncation fine: dims are ≤ THUMB_EDGE after the scale.
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let (tw, th) = (
        ((f64::from(w) * scale).round() as u32).max(1),
        ((f64::from(h) * scale).round() as u32).max(1),
    );
    let thumb = image::imageops::thumbnail(&img, tw, th);
    Some(ctx.load_texture(
        format!("thumb-{}", series.key),
        egui::ColorImage::from_gray([tw as usize, th as usize], thumb.as_raw()),
        egui::TextureOptions::default(),
    ))
}

/// Truncate a label to fit a thumbnail tile.
fn elide(s: &str, max_chars: usize) -> String {
    if s.chars().count() <= max_chars {
        s.to_owned()
    } else {
        let cut: String = s.chars().take(max_chars.saturating_sub(1)).collect();
        format!("{cut}…")
    }
}

/// Window title: "RustRadStack — <study folder or file>".
fn title_for_path(path: &Path) -> String {
    let name = path
        .file_name()
        .map_or_else(|| path.display().to_string(), |n| n.to_string_lossy().into_owned());
    format!("RustRadStack — {name}")
}

impl ViewerApp {
    #[must_use]
    pub fn new(study: Study, origin: &Path) -> Self {
        let mut app = Self::empty();
        app.hang_study(study, origin);
        app
    }

    /// Construct an empty viewer (no study). Used at no-args startup.
    #[must_use]
    pub fn empty() -> Self {
        Self {
            study: None,
            study_path: None,
            thumbnails: Vec::new(),
            viewports: (0..4).map(|_| Viewport::empty()).collect(),
            layout: Layout::One,
            active: 0,
            active_tool: Tool::PanScroll,
            load_error: None,
            hover_readout: None,
            pending_title: None,
        }
    }

    /// Replace the current study: hang the first series into viewport 1, the
    /// next ones into the remaining viewports (PACS-style initial hanging).
    fn hang_study(&mut self, study: Study, origin: &Path) {
        for (i, vp) in self.viewports.iter_mut().enumerate() {
            *vp = Viewport::empty();
            if let Some(series) = study.series.get(i) {
                vp.set_series(i, series);
            }
        }
        self.active = 0;
        self.thumbnails = study.series.iter().map(|_| ThumbState::Pending).collect();
        self.study = Some(study);
        self.study_path = Some(origin.to_path_buf());
        self.load_error = None;
        self.hover_readout = None;
        self.pending_title = Some(title_for_path(origin));
    }

    /// Hang the given series into a viewport (thumbnail double-click / drop).
    fn assign_series(&mut self, viewport_idx: usize, series_idx: usize) {
        let Some(study) = &self.study else { return };
        let Some(series) = study.series.get(series_idx) else {
            return;
        };
        if self.viewports[viewport_idx].has_measurements() && !confirm_discard_measurements() {
            return;
        }
        let series = series.clone();
        self.viewports[viewport_idx].set_series(series_idx, &series);
    }

    /// Default folder for the open dialogs: the loaded study's parent (so
    /// sibling studies/series are immediately visible), else the study itself.
    fn picker_dir(&self) -> Option<&Path> {
        let p = self.study_path.as_deref()?;
        p.parent().or(Some(p))
    }

    /// Load a new study from a file or folder, replacing all viewports.
    /// On failure, the previous study stays visible and an error is shown.
    pub fn load_study_path(&mut self, path: &Path) {
        // Replacing the study silently drops all measurements — confirm first.
        if self.viewports.iter().any(Viewport::has_measurements) && !confirm_discard_measurements()
        {
            return;
        }
        match crate::study::load_study(path) {
            Ok(study) => self.hang_study(study, path),
            Err(e) => {
                self.load_error = Some(e.to_string());
            }
        }
    }
}

/// Modal yes/no: OK to throw away existing measurements?
fn confirm_discard_measurements() -> bool {
    rfd::MessageDialog::new()
        .set_level(rfd::MessageLevel::Warning)
        .set_title("Discard measurements?")
        .set_description("Loading a new series here discards its measurements.")
        .set_buttons(rfd::MessageButtons::YesNo)
        .show()
        == rfd::MessageDialogResult::Yes
}

/// Advance `stack` by accumulated `wheel_y` in `WHEEL_SENSITIVITY` chunks.
/// `wheel_y` > 0 = scroll up = previous slice (matches `PyRadStack` convention).
// Float while-loop is intentional: we consume accum in fixed-size chunks until
// it falls below the threshold, which is clearer than a single trunc() step.
#[allow(clippy::while_float)]
fn handle_wheel(stack: &mut ImageStack, accum: &mut f32, wheel_y: f32) {
    *accum += wheel_y;
    while *accum >= WHEEL_SENSITIVITY {
        stack.prev();
        *accum -= WHEEL_SENSITIVITY;
    }
    while *accum <= -WHEEL_SENSITIVITY {
        stack.next();
        *accum += WHEEL_SENSITIVITY;
    }
}

/// Advance `stack` by accumulated drag `dy` in `DRAG_SENSITIVITY` chunks.
/// `button_down` false → reset accum so next drag starts fresh.
/// Drag down (positive dy in egui coords) = next slice.
// Float while-loop is intentional — same rationale as handle_wheel.
#[allow(clippy::while_float)]
fn handle_drag(stack: &mut ImageStack, accum: &mut f32, button_down: bool, dy: f32) {
    if button_down {
        *accum += dy;
        while *accum >= DRAG_SENSITIVITY {
            stack.next();
            *accum -= DRAG_SENSITIVITY;
        }
        while *accum <= -DRAG_SENSITIVITY {
            stack.prev();
            *accum += DRAG_SENSITIVITY;
        }
    } else {
        *accum = 0.0;
    }
}

/// Read this frame's preset-key input. Returns `(Some(N), _)` if 1..=6 was
/// pressed, and `(_, true)` if 0 was pressed. Both can be set if the user
/// somehow pressed two number keys in the same frame; preset wins.
fn read_preset_keys(ctx: &egui::Context) -> (Option<usize>, bool) {
    let preset_index = ctx.input(|i| {
        for (n, key) in [
            (1usize, egui::Key::Num1),
            (2, egui::Key::Num2),
            (3, egui::Key::Num3),
            (4, egui::Key::Num4),
            (5, egui::Key::Num5),
            (6, egui::Key::Num6),
        ] {
            if i.key_pressed(key) {
                return Some(n);
            }
        }
        None
    });
    let clear_pressed = ctx.input(|i| i.key_pressed(egui::Key::Num0));
    (preset_index, clear_pressed)
}

/// Apply a preset key event to the stack and the viewport's active-preset state.
/// Preset key sets both override + name; clear key drops both.
fn apply_preset_keys(
    stack: &mut ImageStack,
    active_preset_name: &mut Option<&'static str>,
    preset_index: Option<usize>,
    clear_pressed: bool,
) {
    if let Some(n) = preset_index
        && let Some(preset) = crate::presets::PRESETS.get(n - 1)
    {
        stack.set_override_window(Some((preset.center, preset.width)));
        *active_preset_name = Some(preset.name);
    } else if clear_pressed {
        stack.set_override_window(None);
        *active_preset_name = None;
    }
}

impl eframe::App for ViewerApp {
    // egui immediate-mode style: ui() bundles input read, state updates, and
    // render in one pass; the per-viewport body lives in viewport_ui.
    #[allow(clippy::too_many_lines)]
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();

        if let Some(title) = self.pending_title.take() {
            ctx.send_viewport_cmd(egui::ViewportCommand::Title(title));
        }

        // Hotkeys: tools are global; Esc/Delete act on the active viewport.
        ctx.input(|i| {
            let mut tool_change = None;
            if i.key_pressed(egui::Key::P) {
                tool_change = Some(Tool::PanScroll);
            } else if i.key_pressed(egui::Key::L) {
                tool_change = Some(Tool::Line);
            } else if i.key_pressed(egui::Key::O) {
                tool_change = Some(Tool::Orthogonal);
            } else if i.key_pressed(egui::Key::C) {
                tool_change = Some(Tool::Circle);
            }
            if let Some(tool) = tool_change {
                self.active_tool = tool;
                for vp in &mut self.viewports {
                    vp.drawing_measurement = None;
                }
            } else if i.key_pressed(egui::Key::Escape) {
                self.viewports[self.active].drawing_measurement = None;
            } else if i.key_pressed(egui::Key::Delete) || i.key_pressed(egui::Key::Backspace) {
                // Only removes the selection — with nothing selected this is a
                // no-op, not a clear-the-slice surprise (that's the Clear button).
                let vp = &mut self.viewports[self.active];
                if let Some(stack) = vp.stack.as_mut()
                    && !vp.selected_indices.is_empty()
                {
                    stack.remove_measurements(&vp.selected_indices);
                    vp.selected_indices.clear();
                }
                vp.drawing_measurement = None;
            }
        });

        // Preset keys: 1..=6 apply PRESETS[N-1] to the ACTIVE viewport; 0 reverts to file tags.
        let (preset_index, clear_pressed) = read_preset_keys(&ctx);
        {
            let vp = &mut self.viewports[self.active];
            if let Some(stack) = vp.stack.as_mut() {
                apply_preset_keys(
                    stack,
                    &mut vp.active_preset_name,
                    preset_index,
                    clear_pressed,
                );
            }
        }

        // Top menubar — file open dialogs + W/L presets.
        egui::Panel::top("menubar").show_inside(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui
                        .button("Open Study…")
                        .on_hover_text("Pick a study folder — every series inside is loaded")
                        .clicked()
                    {
                        ui.close_kind(egui::UiKind::Menu);
                        let mut dialog = rfd::FileDialog::new().set_title("Open study folder");
                        if let Some(dir) = self.picker_dir() {
                            dialog = dialog.set_directory(dir);
                        }
                        if let Some(folder) = dialog.pick_folder() {
                            self.load_study_path(&folder);
                        }
                    }
                    if ui.button("Open Folder…").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        // The OS folder picker hides files (FOS_PICKFOLDERS), so the user
                        // can't preview a folder's contents before picking it. Workaround:
                        // use the file picker and load the picked file's parent dir.
                        let mut dialog = rfd::FileDialog::new()
                            .set_title("Open folder (pick any image inside)")
                            .add_filter("Images (DICOM, JPG, PNG)", &["dcm", "jpg", "jpeg", "png"]);
                        if let Some(dir) = self.picker_dir() {
                            dialog = dialog.set_directory(dir);
                        }
                        if let Some(file) = dialog.pick_file()
                            && let Some(folder) = file.parent()
                        {
                            self.load_study_path(folder);
                        }
                    }
                    if ui.button("Open File…").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        // Single combined filter so all supported types are visible.
                        if let Some(file) = rfd::FileDialog::new()
                            .set_title("Open image file")
                            .add_filter("Images (DICOM, JPG, PNG)", &["dcm", "jpg", "jpeg", "png"])
                            .pick_file()
                        {
                            self.load_study_path(&file);
                        }
                    }
                });
                // Same presets the number keys apply — the menu makes them
                // discoverable and doubles as the shortcut reference.
                ui.menu_button("W/L", |ui| {
                    let vp = &mut self.viewports[self.active];
                    for (n, preset) in crate::presets::PRESETS.iter().enumerate() {
                        let text = format!(
                            "{}  {} (C {:.0} / W {:.0})",
                            n + 1,
                            preset.name,
                            preset.center,
                            preset.width
                        );
                        if ui.button(text).clicked() {
                            ui.close_kind(egui::UiKind::Menu);
                            if let Some(stack) = vp.stack.as_mut() {
                                apply_preset_keys(
                                    stack,
                                    &mut vp.active_preset_name,
                                    Some(n + 1),
                                    false,
                                );
                            }
                        }
                    }
                    ui.separator();
                    if ui.button("0  File default").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        if let Some(stack) = vp.stack.as_mut() {
                            apply_preset_keys(stack, &mut vp.active_preset_name, None, true);
                        }
                    }
                });
            });
        });

        // Toolbar: measurement tools (global), clear buttons (active viewport), layout.
        egui::Panel::top("toolbar").show_inside(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label("Tool:");

                let mut tool_changed = false;
                if ui
                    .selectable_label(self.active_tool == Tool::PanScroll, "🖐 Pan/Scroll")
                    .on_hover_text("Shortcut: P. Wheel or left-drag scrolls slices.")
                    .clicked()
                {
                    self.active_tool = Tool::PanScroll;
                    tool_changed = true;
                }
                if ui
                    .selectable_label(self.active_tool == Tool::Line, "📏 1D Line")
                    .on_hover_text("Shortcut: L. Esc cancels; Del removes selected.")
                    .clicked()
                {
                    self.active_tool = Tool::Line;
                    tool_changed = true;
                }
                if ui
                    .selectable_label(self.active_tool == Tool::Orthogonal, "➕ 2D Ortho")
                    .on_hover_text("Shortcut: O. Esc cancels; Del removes selected.")
                    .clicked()
                {
                    self.active_tool = Tool::Orthogonal;
                    tool_changed = true;
                }
                if ui
                    .selectable_label(self.active_tool == Tool::Circle, "⭕ Circle ROI")
                    .on_hover_text("Shortcut: C. Esc cancels; Del removes selected.")
                    .clicked()
                {
                    self.active_tool = Tool::Circle;
                    tool_changed = true;
                }

                if tool_changed {
                    for vp in &mut self.viewports {
                        vp.drawing_measurement = None;
                    }
                }

                ui.separator();

                {
                    let vp = &mut self.viewports[self.active];
                    if ui
                        .button("Clear Slice")
                        .on_hover_text("Remove all measurements on this slice (active viewport)")
                        .clicked()
                    {
                        if let Some(stack) = vp.stack.as_mut() {
                            stack.clear_current_measurements();
                        }
                        vp.drawing_measurement = None;
                        vp.selected_indices.clear();
                    }
                    if ui
                        .button("Clear All")
                        .on_hover_text("Remove measurements on every slice (active viewport)")
                        .clicked()
                    {
                        if let Some(stack) = vp.stack.as_mut() {
                            stack.clear_all_measurements();
                        }
                        vp.drawing_measurement = None;
                        vp.selected_indices.clear();
                    }
                }

                ui.separator();
                ui.label("Layout:");
                for (layout, label) in [
                    (Layout::One, "1"),
                    (Layout::TwoAcross, "1×2"),
                    (Layout::TwoByTwo, "2×2"),
                ] {
                    if ui
                        .selectable_label(self.layout == layout, label)
                        .clicked()
                    {
                        self.layout = layout;
                        self.active = self.active.min(layout.viewport_count() - 1);
                    }
                }
            });
        });

        // Progressive thumbnail building: one per frame keeps the UI responsive
        // while a big study's previews fill in.
        if let Some(study) = &self.study
            && let Some(i) = self
                .thumbnails
                .iter()
                .position(|t| matches!(t, ThumbState::Pending))
        {
            self.thumbnails[i] = build_thumbnail(&study.series[i], &ctx)
                .map_or(ThumbState::Failed, ThumbState::Ready);
            ctx.request_repaint();
        }

        // Series strip: one thumbnail per series (center slice). Double-click
        // hangs the series in the active viewport; drag-and-drop in any viewport.
        let mut pending_assign: Option<(usize, usize)> = None; // (viewport, series)
        if self.study.is_some() {
            egui::Panel::top("series-strip").show_inside(ui, |ui| {
                let study = self.study.as_ref().expect("checked above");
                egui::ScrollArea::horizontal().show(ui, |ui| {
                    ui.horizontal(|ui| {
                        for (i, series) in study.series.iter().enumerate() {
                            let (rect, resp) =
                                ui.allocate_exact_size(THUMB_TILE, egui::Sense::click_and_drag());
                            if resp.double_clicked() {
                                pending_assign = Some((self.active, i));
                            }
                            resp.dnd_set_drag_payload(SeriesDrag(i));

                            let visuals = ui.visuals();
                            // Outline the tiles that are hung in a visible viewport.
                            let hung = self.viewports[..self.layout.viewport_count()]
                                .iter()
                                .any(|vp| vp.series_idx == Some(i));
                            let bg = if resp.hovered() {
                                visuals.widgets.hovered.bg_fill
                            } else {
                                visuals.extreme_bg_color
                            };
                            let painter = ui.painter_at(rect);
                            painter.rect_filled(rect, 4.0, bg);
                            if hung {
                                painter.rect_stroke(
                                    rect,
                                    4.0,
                                    egui::Stroke::new(1.5, visuals.selection.stroke.color),
                                    egui::StrokeKind::Inside,
                                );
                            }

                            // Thumbnail image, aspect-fit into the upper square.
                            let img_area = egui::Rect::from_min_size(
                                rect.min + egui::vec2(6.0, 6.0),
                                egui::vec2(THUMB_EDGE as f32, THUMB_EDGE as f32),
                            );
                            match &self.thumbnails[i] {
                                ThumbState::Ready(tex) => {
                                    let size = tex.size_vec2();
                                    let s = (img_area.width() / size.x)
                                        .min(img_area.height() / size.y);
                                    let draw_rect = egui::Rect::from_center_size(
                                        img_area.center(),
                                        size * s,
                                    );
                                    painter.image(
                                        tex.id(),
                                        draw_rect,
                                        egui::Rect::from_min_max(
                                            egui::pos2(0.0, 0.0),
                                            egui::pos2(1.0, 1.0),
                                        ),
                                        egui::Color32::WHITE,
                                    );
                                }
                                ThumbState::Pending => {
                                    painter.text(
                                        img_area.center(),
                                        egui::Align2::CENTER_CENTER,
                                        "…",
                                        egui::FontId::proportional(18.0),
                                        visuals.weak_text_color(),
                                    );
                                }
                                ThumbState::Failed => {
                                    painter.text(
                                        img_area.center(),
                                        egui::Align2::CENTER_CENTER,
                                        "⚠",
                                        egui::FontId::proportional(18.0),
                                        visuals.warn_fg_color,
                                    );
                                }
                            }

                            // Caption: elided description + slice count.
                            let caption = format!(
                                "{} ({})",
                                elide(&series.description, 14),
                                series.paths.len()
                            );
                            painter.text(
                                egui::pos2(rect.center().x, rect.max.y - 4.0),
                                egui::Align2::CENTER_BOTTOM,
                                caption,
                                egui::FontId::proportional(12.0),
                                visuals.text_color(),
                            );

                            resp.on_hover_text(format!(
                                "{} — {} slice(s)\nDouble-click: hang in active viewport.\nDrag into any viewport.",
                                series.description,
                                series.paths.len()
                            ));
                        }
                    });
                });
            });
        }

        let ps = read_pointer_state(&ctx);

        // Status bar (bottom panel so a full-height image can't push it off screen):
        // active viewport's series, slice position, live W/L, preset, cursor value.
        egui::Panel::bottom("statusbar").show_inside(ui, |ui| {
            use std::fmt::Write;
            let mut label = String::new();
            if let Some(err) = &self.load_error {
                let _ = write!(label, "Error: {err}  —  ");
            }
            let vp = &self.viewports[self.active];
            if let Some(stack) = &vp.stack {
                if let Some(desc) = vp
                    .series_idx
                    .and_then(|i| self.study.as_ref()?.series.get(i))
                    .map(|s| s.description.clone())
                {
                    let _ = write!(label, "{desc}  —  ");
                }
                let _ = write!(label, "Slice {} / {}", stack.current() + 1, stack.len());
                if let Some((center, width)) = stack.effective_window() {
                    let _ = write!(label, "  —  W: {width:.0} L: {center:.0}");
                }
                if let Some(name) = vp.active_preset_name {
                    let _ = write!(label, " ({name})");
                }
                if let Some(readout) = &self.hover_readout {
                    let _ = write!(label, "  —  {readout}");
                }
            } else if label.is_empty() {
                label = "No study loaded — File → Open Study…".to_owned();
            }
            ui.vertical_centered(|ui| {
                ui.label(label);
            });
        });

        // Central area: split into viewports per the current layout.
        let area = ui.available_rect_before_wrap();
        let rects = self.layout.rects(area);

        // Click (either button) inside a viewport makes it the active one.
        if (ps.primary_pressed || ps.secondary_pressed)
            && let Some(pos) = ps.pos
            && let Some(idx) = rects.iter().position(|r| r.contains(pos))
        {
            self.active = idx;
        }

        self.hover_readout = None;
        let mut any_busy = false;
        let multi = rects.len() > 1;
        for (idx, rect) in rects.iter().enumerate() {
            // Border: accent for the active viewport (only worth showing with
            // more than one viewport on screen).
            if multi {
                let stroke = if idx == self.active {
                    egui::Stroke::new(1.5, ui.visuals().selection.stroke.color)
                } else {
                    egui::Stroke::new(1.0, ui.visuals().weak_text_color())
                };
                ui.painter()
                    .rect_stroke(*rect, 0.0, stroke, egui::StrokeKind::Inside);
            }

            // Drop target: hovering with a dragged series highlights the
            // viewport; releasing hangs the series here.
            let drop_resp = ui.interact(
                *rect,
                ui.id().with(("viewport-drop", idx)),
                egui::Sense::hover(),
            );
            if drop_resp.dnd_hover_payload::<SeriesDrag>().is_some() {
                ui.painter().rect_stroke(
                    *rect,
                    0.0,
                    egui::Stroke::new(2.5, ui.visuals().selection.stroke.color),
                    egui::StrokeKind::Inside,
                );
            }
            if let Some(payload) = drop_resp.dnd_release_payload::<SeriesDrag>() {
                pending_assign = Some((idx, payload.0));
            }

            let inner = rect.shrink(if multi { 3.0 } else { 0.0 });
            let mut child = ui.new_child(
                egui::UiBuilder::new()
                    .max_rect(inner)
                    .layout(egui::Layout::top_down(egui::Align::Center)),
            );

            let hovered = ps.pos.is_some_and(|p| rect.contains(p));
            let press_in = ps.press_origin.is_some_and(|o| rect.contains(o));
            let vp = &mut self.viewports[idx];
            let readout = viewport_ui(
                vp,
                &mut child,
                &ctx,
                &ps,
                self.active_tool,
                hovered,
                press_in,
            );
            if hovered {
                self.hover_readout = readout;
            }
            any_busy |= vp.busy();
        }

        // Floating label following the pointer while dragging a series.
        if let Some(payload) = egui::DragAndDrop::payload::<SeriesDrag>(&ctx)
            && let Some(pos) = ps.pos
            && let Some(series) = self.study.as_ref().and_then(|s| s.series.get(payload.0))
        {
            let painter = ctx.layer_painter(egui::LayerId::new(
                egui::Order::Tooltip,
                egui::Id::new("series-drag-float"),
            ));
            let font = egui::FontId::proportional(13.0);
            let galley = ctx.fonts_mut(|f| {
                f.layout_no_wrap(series.description.clone(), font, egui::Color32::WHITE)
            });
            let text_pos = pos + egui::vec2(14.0, 14.0);
            let bg = egui::Rect::from_min_size(text_pos, galley.size()).expand(4.0);
            painter.rect_filled(bg, 4.0, egui::Color32::from_black_alpha(200));
            painter.galley(text_pos, galley, egui::Color32::WHITE);
            ctx.request_repaint();
        }

        // Apply thumbnail double-click / drop actions.
        if let Some((vp_idx, series_idx)) = pending_assign {
            self.assign_series(vp_idx, series_idx);
            self.active = vp_idx;
        }

        // Request continuous repaint while wheel scrolling or dragging — without this,
        // drags only register at events egui happens to repaint for.
        if ps.wheel_y != 0.0 || ps.primary_down || any_busy {
            ctx.request_repaint();
        }
    }
}

/// One viewport's per-frame work: scroll/W-L input, texture upload, image
/// display, and measurement interactions. Returns the hover pixel readout.
// Immediate-mode bundle, same rationale as ui().
#[allow(clippy::too_many_lines)]
fn viewport_ui(
    vp: &mut Viewport,
    ui: &mut egui::Ui,
    ctx: &egui::Context,
    ps: &PointerState,
    active_tool: Tool,
    hovered: bool,
    press_in: bool,
) -> Option<String> {
    let mut hover_readout = None;

    // Slice changed (scroll) → stale selection/drawing state must go: finishing
    // a drawing after a scroll would drop the measurement onto the wrong slice.
    let current_slice = vp.stack.as_ref().map(|s| s.current());
    if current_slice != vp.last_slice {
        vp.selected_indices.clear();
        vp.dragged_label = None;
        vp.selection_box = None;
        vp.drawing_measurement = None;
        vp.last_slice = current_slice;
    }

    let is_measuring = active_tool != Tool::PanScroll;
    if let Some(stack) = vp.stack.as_mut() {
        // Wheel routes to the hovered viewport only.
        handle_wheel(stack, &mut vp.wheel_accum, if hovered { ps.wheel_y } else { 0.0 });
        // Drag-scroll locks to the viewport where the press started; off while
        // measuring or label-dragging so those gestures don't also scrub.
        let drag_active =
            ps.primary_only_down && press_in && !is_measuring && vp.dragged_label.is_none();
        let dy = if drag_active { ps.delta.y } else { 0.0 };
        handle_drag(stack, &mut vp.drag_accum, drag_active, dy);
    }

    // Both-button drag = W/L adjustment. dx → width, dy → center.
    if ps.both_down && press_in && let Some(stack) = vp.stack.as_mut() {
        // W/L drag takes over both buttons — cancel any marquee selection the
        // right button may have started, or releasing it would mangle the
        // user's measurement selection mid-drag.
        vp.selection_start_pos = None;
        vp.selection_box = None;
        // Read current W/L: override if set, otherwise the current file's tags
        // (so the drag starts at where the file's W/L is). Falls back to 128/256
        // for non-DICOM slices — same defaults extract_pixels uses.
        let (current_center, current_width) = stack.effective_window().unwrap_or((128.0, 256.0));
        let new_center = f64::from(ps.delta.y).mul_add(WL_SENSITIVITY, current_center);
        // Width: clamp to [1, 100_000] to prevent degenerate windows and runaway drags.
        let new_width = f64::from(ps.delta.x)
            .mul_add(WL_SENSITIVITY, current_width)
            .clamp(1.0, 100_000.0);
        stack.set_override_window(Some((new_center, new_width)));
        // Manual W/L drag → no longer on a named preset.
        vp.active_preset_name = None;
    }

    // Re-upload texture when either the slice index OR the override W/L changed.
    // The composite key catches W/L drag (override mutates without index change).
    if let Some(stack) = vp.stack.as_ref() {
        let current_key: TextureKey = (stack.current(), stack.override_window());
        if vp.texture_key != Some(current_key) {
            match stack.get_current_image() {
                Ok(img) => {
                    let (w, h) = img.dimensions();
                    let color_img =
                        egui::ColorImage::from_gray([w as usize, h as usize], img.as_raw());
                    match &mut vp.texture {
                        // Update in place — no new GPU texture per W/L step.
                        Some(tex) => tex.set(color_img, egui::TextureOptions::default()),
                        None => {
                            vp.texture = Some(ctx.load_texture(
                                "viewport-frame",
                                color_img,
                                egui::TextureOptions::default(),
                            ));
                        }
                    }
                    vp.texture_key = Some(current_key);
                    vp.load_error = None;
                }
                // Surface decode errors — silent failure would just freeze on the prior slice.
                Err(e) => {
                    vp.load_error = Some(format!("decode: {e}"));
                }
            }
        }
    }

    if let Some(err) = &vp.load_error {
        ui.colored_label(egui::Color32::LIGHT_RED, format!("Error: {err}"));
    }
    let Some(tex) = &vp.texture else {
        ui.centered_and_justified(|ui| {
            ui.label("(empty — drop a series here)");
        });
        return None;
    };

    let size = tex.size_vec2();
    // Fit the image to the viewport, preserving aspect ratio (scales both up
    // and down). Measurement mapping goes through the displayed rect, so
    // image coordinates are unaffected.
    let avail = ui.available_size();
    let scale = (avail.x / size.x).min(avail.y / size.y).max(0.001);
    let display = size * scale;
    ui.add_space(((avail.y - display.y) / 2.0).max(0.0));
    let response = ui.image(egui::load::SizedTexture::new(tex.id(), display));

    if let Some(stack) = vp.stack.as_mut() {
        let rect = response.rect;

        let pointer_pos = ps.pos;
        let shift_held = ps.shift;

        let map_pt = |pt: (f64, f64)| -> egui::Pos2 {
            let px = pt.0 / (size.x as f64);
            let py = pt.1 / (size.y as f64);
            egui::pos2(
                rect.min.x + (px as f32) * rect.width(),
                rect.min.y + (py as f32) * rect.height(),
            )
        };
        let unmap_pt = |pos: egui::Pos2| -> (f64, f64) {
            let px = f64::from((pos.x - rect.min.x) / rect.width()) * (size.x as f64);
            let py = f64::from((pos.y - rect.min.y) / rect.height()) * (size.y as f64);
            (px.clamp(0.0, size.x as f64), py.clamp(0.0, size.y as f64))
        };

        // 1. Update active label dragging
        if let Some((drag_idx, label_id)) = vp.dragged_label {
            if ps.primary_down {
                if let Some(pos) = pointer_pos {
                    let new_rect_min = pos - vp.dragged_label_offset;
                    let img_pos = unmap_pt(new_rect_min);
                    let measurements = stack.current_measurements_mut();
                    if let Some(m) = measurements.get_mut(drag_idx) {
                        match (m, label_id) {
                            (Measurement::Line { label_pos, .. }, LabelId::Line) => {
                                *label_pos = Some(img_pos);
                            }
                            (Measurement::Orthogonal { label1_pos, .. }, LabelId::Ortho1) => {
                                *label1_pos = Some(img_pos);
                            }
                            (Measurement::Orthogonal { label2_pos, .. }, LabelId::Ortho2) => {
                                *label2_pos = Some(img_pos);
                            }
                            (Measurement::Circle { label_pos, .. }, LabelId::Circle) => {
                                *label_pos = Some(img_pos);
                            }
                            _ => {}
                        }
                    }
                }
            } else {
                vp.dragged_label = None;
            }
        }

        // 2. Check label hover
        let mut hovered_label_info = None;
        let font_id = egui::FontId::proportional(14.0);
        let spacing = stack.current_spacing();

        // Pixel value under the cursor for the status bar. Labelled HU
        // when spacing exists (same convention as ROI stats).
        hover_readout = pointer_pos.filter(|p| rect.contains(*p)).and_then(|p| {
            let (ix, iy) = unmap_pt(p);
            stack.value_at(ix.floor(), iy.floor()).map(|v| {
                if spacing.is_some() {
                    format!("HU: {v:.0}")
                } else {
                    format!("Val: {v:.0}")
                }
            })
        });

        if vp.dragged_label.is_none()
            && let Some(pos) = pointer_pos
            && rect.contains(pos)
        {
            for (idx, m) in stack.current_measurements().iter().enumerate() {
                let labels = get_measurement_labels(m, map_pt, spacing, stack, ctx, &font_id);
                for (label_id, _, _, label_rect) in labels {
                    if label_rect.contains(pos) {
                        hovered_label_info = Some((idx, label_id, label_rect));
                        break;
                    }
                }
                if hovered_label_info.is_some() {
                    break;
                }
            }
        }

        if let Some((idx, label_id, label_rect)) = hovered_label_info {
            ctx.set_cursor_icon(egui::CursorIcon::Grab);
            if ps.primary_pressed && let Some(pos) = pointer_pos {
                vp.dragged_label = Some((idx, label_id));
                vp.dragged_label_offset = pos - label_rect.min;
                vp.drawing_measurement = None;
            }
        }

        // 3. Right-click selection and marquee selection box.
        // Only when the right button is pressed alone — with the left
        // button already down this is a W/L drag, not a selection.
        if let Some(pos) = pointer_pos
            && ps.secondary_pressed
            && !ps.primary_down
            && rect.contains(pos)
        {
            vp.selection_start_pos = Some(pos);
            vp.selection_box = None;
        }

        if let Some(start) = vp.selection_start_pos {
            if ps.secondary_down && let Some(curr) = pointer_pos {
                let dist = start.distance(curr);
                if dist >= 4.0 {
                    vp.selection_box = Some(egui::Rect::from_two_pos(start, curr));
                } else {
                    vp.selection_box = None;
                }
            }

            if ps.secondary_released {
                let curr = pointer_pos.unwrap_or(start);
                let dist = start.distance(curr);
                if dist < 4.0 {
                    // Single Right-Click Selection
                    let mut closest_idx = None;
                    let mut min_dist = f32::INFINITY;
                    for (idx, m) in stack.current_measurements().iter().enumerate() {
                        let d = distance_to_measurement(curr, m, map_pt);
                        if d < min_dist {
                            min_dist = d;
                            closest_idx = Some(idx);
                        }
                    }

                    if min_dist < 15.0 {
                        if let Some(idx) = closest_idx {
                            if shift_held {
                                if vp.selected_indices.contains(&idx) {
                                    vp.selected_indices.remove(&idx);
                                } else {
                                    vp.selected_indices.insert(idx);
                                }
                            } else {
                                vp.selected_indices.clear();
                                vp.selected_indices.insert(idx);
                            }
                        }
                    } else if !shift_held {
                        vp.selected_indices.clear();
                    }
                } else if let Some(sel_box) = vp.selection_box {
                    // Marquee Selection
                    if !shift_held {
                        vp.selected_indices.clear();
                    }
                    for (idx, m) in stack.current_measurements().iter().enumerate() {
                        if measurement_in_marquee(sel_box, m, map_pt) {
                            vp.selected_indices.insert(idx);
                        }
                    }
                }
                vp.selection_start_pos = None;
                vp.selection_box = None;
            }
        }

        // 4. Drawing logic
        if vp.dragged_label.is_none()
            && (vp.drawing_measurement.is_some()
                || (is_measuring && hovered_label_info.is_none()))
            && let Some(pos) = pointer_pos
        {
            let current_pt = unmap_pt(pos);
            match &mut vp.drawing_measurement {
                None => {
                    if ps.primary_pressed && rect.contains(pos) {
                        match active_tool {
                            Tool::Line => {
                                vp.drawing_measurement = Some(DrawingState::Line {
                                    start: current_pt,
                                    current: current_pt,
                                });
                            }
                            Tool::Circle => {
                                vp.drawing_measurement = Some(DrawingState::Circle {
                                    center: current_pt,
                                    current: current_pt,
                                });
                            }
                            Tool::Orthogonal => {
                                vp.drawing_measurement = Some(DrawingState::OrthogonalStep1 {
                                    start: current_pt,
                                    current: current_pt,
                                });
                            }
                            Tool::PanScroll => {}
                        }
                    }
                }
                Some(state) => {
                    if ps.primary_down {
                        match state {
                            DrawingState::Line { current, .. }
                            | DrawingState::Circle { current, .. }
                            | DrawingState::OrthogonalStep1 { current, .. }
                            | DrawingState::OrthogonalStep2 { current, .. } => {
                                *current = current_pt;
                            }
                        }
                    }

                    if ps.primary_released {
                        match state.clone() {
                            DrawingState::Line { start, current } => {
                                let dx = current.0 - start.0;
                                let dy = current.1 - start.1;
                                if (dx * dx + dy * dy).sqrt() > 0.1 {
                                    stack.add_measurement(Measurement::Line {
                                        start,
                                        end: current,
                                        label_pos: None,
                                    });
                                }
                                vp.drawing_measurement = None;
                            }
                            DrawingState::Circle { center, current } => {
                                let dx = current.0 - center.0;
                                let dy = current.1 - center.1;
                                let r = (dx * dx + dy * dy).sqrt();
                                if r > 0.1 {
                                    stack.add_measurement(Measurement::Circle {
                                        center,
                                        radius: r,
                                        label_pos: None,
                                    });
                                }
                                vp.drawing_measurement = None;
                            }
                            DrawingState::OrthogonalStep1 { start, current } => {
                                let dx = current.0 - start.0;
                                let dy = current.1 - start.1;
                                if (dx * dx + dy * dy).sqrt() > 0.1 {
                                    vp.drawing_measurement = Some(DrawingState::OrthogonalStep2 {
                                        start,
                                        end: current,
                                        current,
                                    });
                                } else {
                                    vp.drawing_measurement = None;
                                }
                            }
                            DrawingState::OrthogonalStep2 {
                                start,
                                end,
                                current,
                            } => {
                                let mx = (start.0 + end.0) / 2.0;
                                let my = (start.1 + end.1) / 2.0;
                                let vx = end.0 - start.0;
                                let vy = end.1 - start.1;
                                let len = (vx * vx + vy * vy).sqrt();
                                if len > 0.1 {
                                    let nx = -vy / len;
                                    let ny = vx / len;
                                    let dx = current.0 - mx;
                                    let dy = current.1 - my;
                                    let d = dx * nx + dy * ny;
                                    let ortho_start = (mx - d * nx, my - d * ny);
                                    let ortho_end = (mx + d * nx, my + d * ny);
                                    stack.add_measurement(Measurement::Orthogonal {
                                        start,
                                        end,
                                        ortho_start,
                                        ortho_end,
                                        label1_pos: None,
                                        label2_pos: None,
                                    });
                                }
                                vp.drawing_measurement = None;
                            }
                        }
                    }
                }
            }
        }

        // 5. Render
        let painter = ui.painter_at(rect);

        for (idx, m) in stack.current_measurements().iter().enumerate() {
            let selected = vp.selected_indices.contains(&idx);
            draw_measurement(&painter, m, map_pt, spacing, stack, selected, ctx);
        }

        if let Some(state) = &vp.drawing_measurement {
            draw_drawing_state(&painter, state, map_pt, spacing, stack, ctx);
        }

        // Draw selection marquee box
        if let Some(sel_box) = vp.selection_box {
            painter.rect_filled(
                sel_box,
                0.0,
                egui::Color32::from_rgba_unmultiplied(33, 150, 243, 30),
            );
            draw_dashed_rect(
                &painter,
                sel_box,
                egui::Stroke::new(1.0, egui::Color32::from_rgb(33, 150, 243)),
                4.0,
                3.0,
            );
        }
    }

    hover_readout
}

fn draw_measurement(
    painter: &egui::Painter,
    m: &Measurement,
    map_pt: impl Fn((f64, f64)) -> egui::Pos2,
    spacing: Option<(f64, f64)>,
    stack: &ImageStack,
    selected: bool,
    ctx: &egui::Context,
) {
    let stroke_color = if selected {
        egui::Color32::from_rgb(255, 140, 0)
    } else {
        egui::Color32::YELLOW
    };
    let stroke_width = if selected { 3.0 } else { 1.5 };
    let stroke = egui::Stroke::new(stroke_width, stroke_color);

    let handle_color = stroke_color;
    let handle_radius = if selected { 5.0 } else { 3.0 };

    let text_color = egui::Color32::YELLOW;
    let font_id = egui::FontId::proportional(14.0);

    match m {
        Measurement::Line {
            start,
            end,
            label_pos,
        } => {
            let p1 = map_pt(*start);
            let p2 = map_pt(*end);
            painter.line_segment([p1, p2], stroke);
            painter.circle_filled(p1, handle_radius, handle_color);
            painter.circle_filled(p2, handle_radius, handle_color);

            let labels = get_measurement_labels(m, &map_pt, spacing, stack, ctx, &font_id);
            for (_, text, screen_pos, rect) in labels {
                draw_text_with_shadow(painter, screen_pos, text, font_id.clone(), text_color);
                if label_pos.is_some() {
                    let t = if rect.center().distance(p1) < rect.center().distance(p2) {
                        p1
                    } else {
                        p2
                    };
                    let start_point = rect.clamp(t);
                    draw_dashed_line(
                        painter,
                        start_point,
                        t,
                        egui::Stroke::new(1.0, stroke_color),
                        4.0,
                        3.0,
                    );
                }
            }
        }
        Measurement::Orthogonal {
            start,
            end,
            ortho_start,
            ortho_end,
            label1_pos,
            label2_pos,
        } => {
            let p1 = map_pt(*start);
            let p2 = map_pt(*end);
            let q1 = map_pt(*ortho_start);
            let q2 = map_pt(*ortho_end);

            painter.line_segment([p1, p2], stroke);
            painter.line_segment([q1, q2], stroke);
            painter.circle_filled(p1, handle_radius, handle_color);
            painter.circle_filled(p2, handle_radius, handle_color);
            painter.circle_filled(q1, handle_radius, handle_color);
            painter.circle_filled(q2, handle_radius, handle_color);

            let labels = get_measurement_labels(m, &map_pt, spacing, stack, ctx, &font_id);
            for (label_id, text, screen_pos, rect) in labels {
                draw_text_with_shadow(painter, screen_pos, text, font_id.clone(), text_color);
                match label_id {
                    LabelId::Ortho1 => {
                        if label1_pos.is_some() {
                            let t = if rect.center().distance(p1) < rect.center().distance(p2) {
                                p1
                            } else {
                                p2
                            };
                            let start_point = rect.clamp(t);
                            draw_dashed_line(
                                painter,
                                start_point,
                                t,
                                egui::Stroke::new(1.0, stroke_color),
                                4.0,
                                3.0,
                            );
                        }
                    }
                    LabelId::Ortho2 => {
                        if label2_pos.is_some() {
                            let t = if rect.center().distance(q1) < rect.center().distance(q2) {
                                q1
                            } else {
                                q2
                            };
                            let start_point = rect.clamp(t);
                            draw_dashed_line(
                                painter,
                                start_point,
                                t,
                                egui::Stroke::new(1.0, stroke_color),
                                4.0,
                                3.0,
                            );
                        }
                    }
                    _ => {}
                }
            }
        }
        Measurement::Circle {
            center,
            radius,
            label_pos,
        } => {
            let cp = map_pt(*center);
            let edge = map_pt((center.0 + radius, center.1));
            let r_screen = (edge.x - cp.x).abs();

            painter.circle_stroke(cp, r_screen, stroke);
            painter.circle_filled(cp, handle_radius - 1.0, handle_color);

            let labels = get_measurement_labels(m, &map_pt, spacing, stack, ctx, &font_id);
            for (_, text, screen_pos, rect) in labels {
                draw_text_with_shadow(painter, screen_pos, text, font_id.clone(), text_color);
                if label_pos.is_some() {
                    let dir = rect.center() - cp;
                    let len = dir.length();
                    let t = if len > 1e-3 {
                        cp + dir * (r_screen / len)
                    } else {
                        cp + egui::vec2(r_screen, 0.0)
                    };
                    let start_point = rect.clamp(t);
                    draw_dashed_line(
                        painter,
                        start_point,
                        t,
                        egui::Stroke::new(1.0, stroke_color),
                        4.0,
                        3.0,
                    );
                }
            }
        }
    }
}

fn draw_drawing_state(
    painter: &egui::Painter,
    state: &DrawingState,
    map_pt: impl Fn((f64, f64)) -> egui::Pos2,
    spacing: Option<(f64, f64)>,
    stack: &ImageStack,
    ctx: &egui::Context,
) {
    match state {
        DrawingState::Line { start, current } => {
            let m = Measurement::Line {
                start: *start,
                end: *current,
                label_pos: None,
            };
            draw_measurement(painter, &m, map_pt, spacing, stack, false, ctx);
        }
        DrawingState::Circle { center, current } => {
            let dx = current.0 - center.0;
            let dy = current.1 - center.1;
            let r = (dx * dx + dy * dy).sqrt();
            let m = Measurement::Circle {
                center: *center,
                radius: r,
                label_pos: None,
            };
            draw_measurement(painter, &m, map_pt, spacing, stack, false, ctx);
        }
        DrawingState::OrthogonalStep1 { start, current } => {
            let m = Measurement::Line {
                start: *start,
                end: *current,
                label_pos: None,
            };
            draw_measurement(painter, &m, map_pt, spacing, stack, false, ctx);
        }
        DrawingState::OrthogonalStep2 {
            start,
            end,
            current,
        } => {
            let mx = (start.0 + end.0) / 2.0;
            let my = (start.1 + end.1) / 2.0;
            let vx = end.0 - start.0;
            let vy = end.1 - start.1;
            let len = (vx * vx + vy * vy).sqrt();
            if len > 0.1 {
                let nx = -vy / len;
                let ny = vx / len;
                let dx = current.0 - mx;
                let dy = current.1 - my;
                let d = dx * nx + dy * ny;
                let ortho_start = (mx - d * nx, my - d * ny);
                let ortho_end = (mx + d * nx, my + d * ny);
                let m = Measurement::Orthogonal {
                    start: *start,
                    end: *end,
                    ortho_start,
                    ortho_end,
                    label1_pos: None,
                    label2_pos: None,
                };
                draw_measurement(painter, &m, map_pt, spacing, stack, false, ctx);
            } else {
                let m = Measurement::Line {
                    start: *start,
                    end: *end,
                    label_pos: None,
                };
                draw_measurement(painter, &m, map_pt, spacing, stack, false, ctx);
            }
        }
    }
}

fn distance_point_to_segment(p: egui::Pos2, a: egui::Pos2, b: egui::Pos2) -> f32 {
    let ab_x = b.x - a.x;
    let ab_y = b.y - a.y;
    let ap_x = p.x - a.x;
    let ap_y = p.y - a.y;

    let ab_len_sq = ab_x * ab_x + ab_y * ab_y;
    if ab_len_sq < 1e-6 {
        return (ap_x * ap_x + ap_y * ap_y).sqrt();
    }

    let dot = ap_x * ab_x + ap_y * ab_y;
    let t = (dot / ab_len_sq).clamp(0.0, 1.0);

    let proj_x = a.x + ab_x * t;
    let proj_y = a.y + ab_y * t;

    let dx = p.x - proj_x;
    let dy = p.y - proj_y;
    (dx * dx + dy * dy).sqrt()
}

fn distance_to_measurement(
    p: egui::Pos2,
    m: &Measurement,
    map_pt: impl Fn((f64, f64)) -> egui::Pos2,
) -> f32 {
    match m {
        Measurement::Line { start, end, .. } => {
            let a = map_pt(*start);
            let b = map_pt(*end);
            distance_point_to_segment(p, a, b)
        }
        Measurement::Orthogonal {
            start,
            end,
            ortho_start,
            ortho_end,
            ..
        } => {
            let p1 = map_pt(*start);
            let p2 = map_pt(*end);
            let q1 = map_pt(*ortho_start);
            let q2 = map_pt(*ortho_end);
            let d1 = distance_point_to_segment(p, p1, p2);
            let d2 = distance_point_to_segment(p, q1, q2);
            d1.min(d2)
        }
        Measurement::Circle { center, radius, .. } => {
            let cp = map_pt(*center);
            let edge = map_pt((center.0 + radius, center.1));
            let r_screen = (edge.x - cp.x).abs();
            let dist_to_center = p.distance(cp);
            (dist_to_center - r_screen).abs()
        }
    }
}

fn measurement_in_marquee(
    rect: egui::Rect,
    m: &Measurement,
    map_pt: impl Fn((f64, f64)) -> egui::Pos2,
) -> bool {
    match m {
        Measurement::Line { start, end, .. } => {
            rect.contains(map_pt(*start)) || rect.contains(map_pt(*end))
        }
        Measurement::Orthogonal {
            start,
            end,
            ortho_start,
            ortho_end,
            ..
        } => {
            rect.contains(map_pt(*start))
                || rect.contains(map_pt(*end))
                || rect.contains(map_pt(*ortho_start))
                || rect.contains(map_pt(*ortho_end))
        }
        Measurement::Circle { center, .. } => rect.contains(map_pt(*center)),
    }
}

fn get_measurement_labels(
    m: &Measurement,
    map_pt: impl Fn((f64, f64)) -> egui::Pos2,
    spacing: Option<(f64, f64)>,
    stack: &ImageStack,
    ctx: &egui::Context,
    font_id: &egui::FontId,
) -> Vec<(LabelId, String, egui::Pos2, egui::Rect)> {
    let mut labels = Vec::new();
    match m {
        Measurement::Line {
            start,
            end,
            label_pos,
        } => {
            let p1 = map_pt(*start);
            let p2 = map_pt(*end);
            let dist = get_line_distance(*start, *end, spacing);
            let text = if spacing.is_some() {
                format!("{dist:.1} mm")
            } else {
                format!("{dist:.1} px")
            };
            let default_pos =
                egui::pos2((p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0) + egui::vec2(5.0, 5.0);
            let screen_pos = label_pos.map_or(default_pos, &map_pt);
            let galley = ctx.fonts_mut(|f| {
                f.layout_no_wrap(text.clone(), font_id.clone(), egui::Color32::WHITE)
            });
            let size = galley.size();
            let rect = egui::Rect::from_min_size(screen_pos, size);
            labels.push((LabelId::Line, text, screen_pos, rect));
        }
        Measurement::Orthogonal {
            start,
            end,
            ortho_start,
            ortho_end,
            label1_pos,
            label2_pos,
        } => {
            let p1 = map_pt(*start);
            let p2 = map_pt(*end);
            let q2 = map_pt(*ortho_end);

            let dist1 = get_line_distance(*start, *end, spacing);
            let dist2 = get_line_distance(*ortho_start, *ortho_end, spacing);
            let unit = if spacing.is_some() { "mm" } else { "px" };
            let text1 = format!("L1: {dist1:.1} {unit}");
            let text2 = format!("L2: {dist2:.1} {unit}");

            // Label 1 (midpoint of long axis)
            let default_pos1 =
                egui::pos2((p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0) + egui::vec2(5.0, 5.0);
            let screen_pos1 = label1_pos.map_or(default_pos1, &map_pt);
            let galley1 = ctx.fonts_mut(|f| {
                f.layout_no_wrap(text1.clone(), font_id.clone(), egui::Color32::WHITE)
            });
            let rect1 = egui::Rect::from_min_size(screen_pos1, galley1.size());
            labels.push((LabelId::Ortho1, text1, screen_pos1, rect1));

            // Label 2 (ortho_end point)
            let default_pos2 = q2 + egui::vec2(5.0, 5.0);
            let screen_pos2 = label2_pos.map_or(default_pos2, &map_pt);
            let galley2 = ctx.fonts_mut(|f| {
                f.layout_no_wrap(text2.clone(), font_id.clone(), egui::Color32::WHITE)
            });
            let rect2 = egui::Rect::from_min_size(screen_pos2, galley2.size());
            labels.push((LabelId::Ortho2, text2, screen_pos2, rect2));
        }
        Measurement::Circle {
            center,
            radius,
            label_pos,
        } => {
            let cp = map_pt(*center);
            let edge = map_pt((center.0 + radius, center.1));
            let r_screen = (edge.x - cp.x).abs();

            let area = if let Some((row_sp, col_sp)) = spacing {
                std::f64::consts::PI * (radius * col_sp) * (radius * row_sp)
            } else {
                std::f64::consts::PI * radius * radius
            };

            let (area_unit, val_unit) = if spacing.is_some() {
                ("mm²", "HU")
            } else {
                ("px²", "")
            };

            let mut text = format!("Area: {area:.1} {area_unit}");

            if let Some(stats) = stack.get_roi_stats(*center, *radius) {
                if spacing.is_some() {
                    text = format!(
                        "Area: {:.1} {}\nMean: {:.1} {}\nMin: {:.1} {}\nMax: {:.1} {}",
                        stats.area,
                        area_unit,
                        stats.mean,
                        val_unit,
                        stats.min,
                        val_unit,
                        stats.max,
                        val_unit
                    );
                } else {
                    text = format!(
                        "Area: {:.1} {}\nMean: {:.1}\nMin: {:.1}\nMax: {:.1}",
                        stats.area, area_unit, stats.mean, stats.min, stats.max
                    );
                }
            }

            let default_pos = cp + egui::vec2(r_screen + 8.0, -r_screen);
            let screen_pos = label_pos.map_or(default_pos, &map_pt);
            let galley = ctx.fonts_mut(|f| {
                f.layout_no_wrap(text.clone(), font_id.clone(), egui::Color32::WHITE)
            });
            let rect = egui::Rect::from_min_size(screen_pos, galley.size());
            labels.push((LabelId::Circle, text, screen_pos, rect));
        }
    }
    labels
}

fn draw_dashed_line(
    painter: &egui::Painter,
    p1: egui::Pos2,
    p2: egui::Pos2,
    stroke: egui::Stroke,
    dash_len: f32,
    gap_len: f32,
) {
    let dir = p2 - p1;
    let len = dir.length();
    if len < 0.1 {
        return;
    }
    let dir = dir / len;
    let mut current_dist = 0.0;
    while current_dist < len {
        let next_dist = (current_dist + dash_len).min(len);
        let start = p1 + dir * current_dist;
        let end = p1 + dir * next_dist;
        painter.line_segment([start, end], stroke);
        current_dist += dash_len + gap_len;
    }
}

fn draw_dashed_rect(
    painter: &egui::Painter,
    rect: egui::Rect,
    stroke: egui::Stroke,
    dash_len: f32,
    gap_len: f32,
) {
    draw_dashed_line(
        painter,
        rect.left_top(),
        rect.right_top(),
        stroke,
        dash_len,
        gap_len,
    );
    draw_dashed_line(
        painter,
        rect.right_top(),
        rect.right_bottom(),
        stroke,
        dash_len,
        gap_len,
    );
    draw_dashed_line(
        painter,
        rect.right_bottom(),
        rect.left_bottom(),
        stroke,
        dash_len,
        gap_len,
    );
    draw_dashed_line(
        painter,
        rect.left_bottom(),
        rect.left_top(),
        stroke,
        dash_len,
        gap_len,
    );
}

fn get_line_distance(p1: (f64, f64), p2: (f64, f64), spacing: Option<(f64, f64)>) -> f64 {
    if let Some((row_sp, col_sp)) = spacing {
        let dx = (p2.0 - p1.0) * col_sp;
        let dy = (p2.1 - p1.1) * row_sp;
        (dx * dx + dy * dy).sqrt()
    } else {
        let dx = p2.0 - p1.0;
        let dy = p2.1 - p1.1;
        (dx * dx + dy * dy).sqrt()
    }
}

fn draw_text_with_shadow(
    painter: &egui::Painter,
    pos: egui::Pos2,
    text: String,
    font_id: egui::FontId,
    text_color: egui::Color32,
) {
    let shadow_color = egui::Color32::BLACK;
    let offsets = [
        egui::vec2(-1.0, -1.0),
        egui::vec2(1.0, -1.0),
        egui::vec2(-1.0, 1.0),
        egui::vec2(1.0, 1.0),
    ];
    for offset in offsets {
        painter.text(
            pos + offset,
            egui::Align2::LEFT_TOP,
            &text,
            font_id.clone(),
            shadow_color,
        );
    }
    painter.text(pos, egui::Align2::LEFT_TOP, text, font_id, text_color);
}
