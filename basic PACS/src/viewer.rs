//! egui-based image viewer.

use eframe::egui;

use crate::stack::{ImageStack, Measurement};

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

/// (slice index, override W/L) of whatever pixels are in the texture right now.
/// Re-upload when this differs from the stack's current state — which catches
/// both slice changes AND W/L drag (override mutates without index changing).
type TextureKey = (usize, Option<(f64, f64)>);

/// State for the GUI viewer. Holds a stack and the currently-uploaded texture.
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    /// Identifies which (slice, W/L) is currently in `texture`. None means "nothing uploaded yet".
    texture_key: Option<TextureKey>,
    /// Accumulated wheel delta; consumed in `WHEEL_SENSITIVITY` chunks per slice step.
    wheel_accum: f32,
    /// Accumulated left-click drag dy; consumed in `DRAG_SENSITIVITY` chunks per slice step.
    drag_accum: f32,
    /// Non-None when the last `load_path` call failed; cleared on the next successful load.
    load_error: Option<String>,
    /// Name of the active W/L preset, or None if user is on file defaults or has
    /// dragged W/L manually ("Custom" mode). Cleared on W/L drag and on `load_path`.
    active_preset_name: Option<&'static str>,
    /// Currently active tool.
    active_tool: Tool,
    /// Current drawing state, if any.
    drawing_measurement: Option<DrawingState>,
    /// Currently selected measurement indices on the current slice.
    selected_indices: std::collections::HashSet<usize>,
    /// Screen position where right-click marquee selection started.
    selection_start_pos: Option<egui::Pos2>,
    /// Bounding box of current right-click marquee selection.
    selection_box: Option<egui::Rect>,
    /// Bounding box of the label currently being dragged, if any: (measurement index, LabelId).
    dragged_label: Option<(usize, LabelId)>,
    /// Offset in screen coordinates from mouse pointer to top-left of the dragged label rect.
    dragged_label_offset: egui::Vec2,
    /// Track last slice index to clear selection on change.
    last_slice: Option<usize>,
    /// Pixel value readout ("HU: -56") under the cursor, shown in the status bar.
    hover_readout: Option<String>,
    /// Window title to push on the next frame (set when a stack loads —
    /// `load_path` has no `Context`, so the title is applied from `ui`).
    pending_title: Option<String>,
}

/// Window title for a loaded stack: "RustRadStack — <series folder>".
fn title_for(stack: &ImageStack) -> Option<String> {
    let path = stack.current_path()?;
    let folder = path.parent()?.file_name()?.to_string_lossy();
    Some(format!("RustRadStack — {folder}"))
}

impl ViewerApp {
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(stack: ImageStack) -> Self {
        let pending_title = title_for(&stack);
        Self {
            stack: Some(stack),
            texture: None,
            texture_key: None,
            wheel_accum: 0.0,
            drag_accum: 0.0,
            load_error: None,
            active_preset_name: None,
            active_tool: Tool::PanScroll,
            drawing_measurement: None,
            selected_indices: std::collections::HashSet::new(),
            selection_start_pos: None,
            selection_box: None,
            dragged_label: None,
            dragged_label_offset: egui::Vec2::ZERO,
            last_slice: None,
            hover_readout: None,
            pending_title,
        }
    }

    /// Construct an empty viewer (no stack). Used for error cases.
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn empty() -> Self {
        Self {
            stack: None,
            texture: None,
            texture_key: None,
            wheel_accum: 0.0,
            drag_accum: 0.0,
            load_error: None,
            active_preset_name: None,
            active_tool: Tool::PanScroll,
            drawing_measurement: None,
            selected_indices: std::collections::HashSet::new(),
            selection_start_pos: None,
            selection_box: None,
            dragged_label: None,
            dragged_label_offset: egui::Vec2::ZERO,
            last_slice: None,
            hover_readout: None,
            pending_title: None,
        }
    }

    /// Parent of the current series folder — i.e. the study folder containing
    /// sibling series. Used to seed the Open Folder picker so the user lands
    /// next to the related series instead of wherever the OS defaults.
    /// Returns None when no stack is loaded or the path has no grandparent.
    fn study_dir(&self) -> Option<&std::path::Path> {
        let series_dir = self.stack.as_ref()?.current_path()?.parent()?;
        series_dir.parent()
    }

    /// Load a new file or folder into the viewer, replacing the current stack.
    /// Resets W/L override (via fresh `ImageStack`) and texture cache so the new
    /// series starts clean. On failure, the previous stack stays visible and an
    /// error label is shown.
    pub fn load_path(&mut self, path: &std::path::Path) {
        // Replacing the stack silently drops its measurements — confirm first.
        if self
            .stack
            .as_ref()
            .is_some_and(ImageStack::has_measurements)
        {
            let choice = rfd::MessageDialog::new()
                .set_level(rfd::MessageLevel::Warning)
                .set_title("Discard measurements?")
                .set_description(
                    "Loading a new series discards all measurements on the current one.",
                )
                .set_buttons(rfd::MessageButtons::YesNo)
                .show();
            if choice != rfd::MessageDialogResult::Yes {
                return;
            }
        }
        match crate::loading::paths_for(path) {
            Ok(paths) => {
                self.stack = Some(ImageStack::new(paths));
                self.texture = None;
                self.texture_key = None;
                self.wheel_accum = 0.0;
                self.drag_accum = 0.0;
                self.load_error = None;
                self.active_preset_name = None;
                self.active_tool = Tool::PanScroll;
                self.drawing_measurement = None;
                self.selected_indices.clear();
                self.selection_start_pos = None;
                self.selection_box = None;
                self.dragged_label = None;
                self.dragged_label_offset = egui::Vec2::ZERO;
                self.last_slice = None;
                self.hover_readout = None;
                self.pending_title = self.stack.as_ref().and_then(title_for);
            }
            Err(e) => {
                self.load_error = Some(e.to_string());
            }
        }
    }
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

/// Apply a preset key event to the stack and the viewer's active-preset state.
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
    // render in one pass. Further splitting hurts readability more than it
    // helps; targeted helpers are extracted for the heavier sub-blocks.
    #[allow(clippy::too_many_lines)]
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();

        if let Some(title) = self.pending_title.take() {
            ctx.send_viewport_cmd(egui::ViewportCommand::Title(title));
        }

        let current_slice = self.stack.as_ref().map(|s| s.current());
        if current_slice != self.last_slice {
            self.selected_indices.clear();
            self.dragged_label = None;
            self.selection_box = None;
            // Abandon any in-progress drawing — finishing it after a scroll
            // would silently drop the measurement onto the wrong slice.
            self.drawing_measurement = None;
            self.last_slice = current_slice;
        }

        // Hotkeys for tool selection
        ctx.input(|i| {
            if i.key_pressed(egui::Key::P) {
                self.active_tool = Tool::PanScroll;
                self.drawing_measurement = None;
            } else if i.key_pressed(egui::Key::L) {
                self.active_tool = Tool::Line;
                self.drawing_measurement = None;
            } else if i.key_pressed(egui::Key::O) {
                self.active_tool = Tool::Orthogonal;
                self.drawing_measurement = None;
            } else if i.key_pressed(egui::Key::C) {
                self.active_tool = Tool::Circle;
                self.drawing_measurement = None;
            } else if i.key_pressed(egui::Key::Escape) {
                self.drawing_measurement = None;
            } else if i.key_pressed(egui::Key::Delete) || i.key_pressed(egui::Key::Backspace) {
                // Only removes the selection — with nothing selected this is a
                // no-op, not a clear-the-slice surprise (that's the Clear button).
                if let Some(stack) = self.stack.as_mut()
                    && !self.selected_indices.is_empty()
                {
                    stack.remove_measurements(&self.selected_indices);
                    self.selected_indices.clear();
                }
                self.drawing_measurement = None;
            }
        });

        // Top menubar — file open dialogs.
        egui::Panel::top("menubar").show_inside(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("Open Folder…").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        // The OS folder picker hides files (FOS_PICKFOLDERS), so the user
                        // can't preview a folder's contents before picking it. Workaround:
                        // use the file picker and load the picked file's parent dir.
                        // Default to the study dir so sibling series are immediately visible.
                        let mut dialog = rfd::FileDialog::new()
                            .set_title("Open folder (pick any image inside)")
                            .add_filter("Images (DICOM, JPG, PNG)", &["dcm", "jpg", "jpeg", "png"]);
                        if let Some(study_dir) = self.study_dir() {
                            dialog = dialog.set_directory(study_dir);
                        }
                        if let Some(file) = dialog.pick_file()
                            && let Some(folder) = file.parent()
                        {
                            self.load_path(folder);
                        }
                    }
                    if ui.button("Open File…").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        // Single combined filter so all supported types are visible
                        // (slice 9 added JPG/PNG; the old .dcm-only filter hid them).
                        if let Some(file) = rfd::FileDialog::new()
                            .set_title("Open image file")
                            .add_filter("Images (DICOM, JPG, PNG)", &["dcm", "jpg", "jpeg", "png"])
                            .pick_file()
                        {
                            self.load_path(&file);
                        }
                    }
                });
                // Same presets the number keys apply — the menu makes them
                // discoverable and doubles as the shortcut reference.
                ui.menu_button("W/L", |ui| {
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
                            if let Some(stack) = self.stack.as_mut() {
                                apply_preset_keys(
                                    stack,
                                    &mut self.active_preset_name,
                                    Some(n + 1),
                                    false,
                                );
                            }
                        }
                    }
                    ui.separator();
                    if ui.button("0  File default").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        if let Some(stack) = self.stack.as_mut() {
                            apply_preset_keys(stack, &mut self.active_preset_name, None, true);
                        }
                    }
                });
            });
        });

        // Toolbar panel for measurement tools
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
                    self.drawing_measurement = None;
                }

                ui.separator();

                if ui
                    .button("Clear Slice")
                    .on_hover_text("Remove all measurements on this slice")
                    .clicked()
                {
                    if let Some(stack) = self.stack.as_mut() {
                        stack.clear_current_measurements();
                    }
                    self.drawing_measurement = None;
                    self.selected_indices.clear();
                }
                if ui
                    .button("Clear All")
                    .on_hover_text("Remove measurements on every slice")
                    .clicked()
                {
                    if let Some(stack) = self.stack.as_mut() {
                        stack.clear_all_measurements();
                    }
                    self.drawing_measurement = None;
                    self.selected_indices.clear();
                }
            });
        });

        // Read all pointer/scroll input in one pass.
        // In egui 0.27+, smooth_scroll_delta replaces scroll_delta.
        let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
        let (drag_button_down, drag_dy) = ctx.input(|i| {
            let primary = i.pointer.button_down(egui::PointerButton::Primary);
            let secondary = i.pointer.button_down(egui::PointerButton::Secondary);
            // drag-scroll fires only when Primary is held alone (not with Secondary, which means W/L).
            let down = primary && !secondary;
            let dy = if down { i.pointer.delta().y } else { 0.0 };
            (down, dy)
        });

        let is_measuring = self.active_tool != Tool::PanScroll;
        if let Some(stack) = self.stack.as_mut() {
            handle_wheel(stack, &mut self.wheel_accum, wheel_y);
            // Drag-scroll is off while measuring or while dragging a label —
            // otherwise moving a label would also scrub through the stack.
            if !is_measuring && self.dragged_label.is_none() {
                handle_drag(stack, &mut self.drag_accum, drag_button_down, drag_dy);
            }
        }

        // Preset keys: 1..=6 apply PRESETS[N-1]; 0 clears the override back to file tags.
        let (preset_index, clear_pressed) = read_preset_keys(&ctx);
        if let Some(stack) = self.stack.as_mut() {
            apply_preset_keys(
                stack,
                &mut self.active_preset_name,
                preset_index,
                clear_pressed,
            );
        }

        // Both-button drag = W/L adjustment. dx → width, dy → center.
        // While both held, mutate stack.override_window each frame.
        let (both_buttons_down, wl_drag_delta) = ctx.input(|i| {
            let primary = i.pointer.button_down(egui::PointerButton::Primary);
            let secondary = i.pointer.button_down(egui::PointerButton::Secondary);
            let both = primary && secondary;
            let delta = if both {
                i.pointer.delta()
            } else {
                egui::Vec2::ZERO
            };
            (both, delta)
        });
        if both_buttons_down && let Some(stack) = self.stack.as_mut() {
            // W/L drag takes over both buttons — cancel any marquee selection the
            // right button may have started, or releasing it would mangle the
            // user's measurement selection mid-drag.
            self.selection_start_pos = None;
            self.selection_box = None;
            // Read current W/L: override if set, otherwise the current file's tags
            // (so the drag starts at where the file's W/L is). Falls back to 128/256
            // for non-DICOM slices — same defaults extract_pixels uses.
            let (current_center, current_width) =
                stack.effective_window().unwrap_or((128.0, 256.0));
            let new_center = f64::from(wl_drag_delta.y).mul_add(WL_SENSITIVITY, current_center);
            // Width: clamp to [1, 100_000] to prevent degenerate windows and runaway drags.
            let new_width = f64::from(wl_drag_delta.x)
                .mul_add(WL_SENSITIVITY, current_width)
                .clamp(1.0, 100_000.0);
            stack.set_override_window(Some((new_center, new_width)));
            // Manual W/L drag → no longer on a named preset.
            self.active_preset_name = None;
        }

        // Re-upload texture when either the slice index OR the override W/L changed.
        // The composite key catches W/L drag (override mutates without index change).
        if let Some(stack) = self.stack.as_ref() {
            let current_key: TextureKey = (stack.current(), stack.override_window());
            if self.texture_key != Some(current_key) {
                match stack.get_current_image() {
                    Ok(img) => {
                        let (w, h) = img.dimensions();
                        let color_img =
                            egui::ColorImage::from_gray([w as usize, h as usize], img.as_raw());
                        match &mut self.texture {
                            // Update in place — no new GPU texture per W/L step.
                            Some(tex) => tex.set(color_img, egui::TextureOptions::default()),
                            None => {
                                self.texture = Some(ctx.load_texture(
                                    "dicom-frame",
                                    color_img,
                                    egui::TextureOptions::default(),
                                ));
                            }
                        }
                        self.texture_key = Some(current_key);
                        self.load_error = None;
                    }
                    // Surface decode errors — silent failure would just freeze on the prior slice.
                    Err(e) => {
                        self.load_error = Some(format!("decode: {e}"));
                    }
                }
            }
        }

        // Status bar (bottom panel so a full-height image can't push it off screen):
        // slice position, live W/L values, active preset, and cursor pixel value.
        egui::Panel::bottom("statusbar").show_inside(ui, |ui| {
            if let Some(stack) = &self.stack {
                use std::fmt::Write;
                let mut label = format!("Slice {} / {}", stack.current() + 1, stack.len());
                if let Some((center, width)) = stack.effective_window() {
                    let _ = write!(label, "  —  W: {width:.0} L: {center:.0}");
                }
                if let Some(name) = self.active_preset_name {
                    let _ = write!(label, " ({name})");
                }
                if let Some(readout) = &self.hover_readout {
                    let _ = write!(label, "  —  {readout}");
                }
                ui.vertical_centered(|ui| {
                    ui.label(label);
                });
            }
        });

        // Image (centered)
        ui.vertical_centered(|ui| {
            if let Some(err) = &self.load_error {
                ui.colored_label(egui::Color32::LIGHT_RED, format!("Error: {err}"));
            }
            if let Some(tex) = &self.texture {
                let size = tex.size_vec2();
                // Fit the image to the remaining panel space, preserving aspect
                // ratio (scales both up and down). Measurement mapping goes
                // through the displayed rect, so image coordinates are unaffected.
                let avail = ui.available_size();
                let scale = (avail.x / size.x).min(avail.y / size.y).max(0.001);
                let display = size * scale;
                ui.add_space(((avail.y - display.y) / 2.0).max(0.0));
                let response = ui.image(egui::load::SizedTexture::new(tex.id(), display));

                if let Some(stack) = self.stack.as_mut() {
                    let rect = response.rect;

                    let pointer_pos = ctx.input(|i| i.pointer.hover_pos());
                    let primary_pressed =
                        ctx.input(|i| i.pointer.button_pressed(egui::PointerButton::Primary));
                    let primary_released =
                        ctx.input(|i| i.pointer.button_released(egui::PointerButton::Primary));
                    let primary_down =
                        ctx.input(|i| i.pointer.button_down(egui::PointerButton::Primary));

                    let secondary_pressed =
                        ctx.input(|i| i.pointer.button_pressed(egui::PointerButton::Secondary));
                    let secondary_released =
                        ctx.input(|i| i.pointer.button_released(egui::PointerButton::Secondary));
                    let secondary_down =
                        ctx.input(|i| i.pointer.button_down(egui::PointerButton::Secondary));

                    let shift_held = ctx.input(|i| i.modifiers.shift);

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
                    if let Some((drag_idx, label_id)) = self.dragged_label {
                        if primary_down {
                            if let Some(pos) = pointer_pos {
                                let new_rect_min = pos - self.dragged_label_offset;
                                let img_pos = unmap_pt(new_rect_min);
                                let measurements = stack.current_measurements_mut();
                                if let Some(m) = measurements.get_mut(drag_idx) {
                                    match (m, label_id) {
                                        (Measurement::Line { label_pos, .. }, LabelId::Line) => {
                                            *label_pos = Some(img_pos);
                                        }
                                        (
                                            Measurement::Orthogonal { label1_pos, .. },
                                            LabelId::Ortho1,
                                        ) => {
                                            *label1_pos = Some(img_pos);
                                        }
                                        (
                                            Measurement::Orthogonal { label2_pos, .. },
                                            LabelId::Ortho2,
                                        ) => {
                                            *label2_pos = Some(img_pos);
                                        }
                                        (
                                            Measurement::Circle { label_pos, .. },
                                            LabelId::Circle,
                                        ) => {
                                            *label_pos = Some(img_pos);
                                        }
                                        _ => {}
                                    }
                                }
                            }
                        } else {
                            self.dragged_label = None;
                        }
                    }

                    // 2. Check label hover
                    let mut hovered_label_info = None;
                    let font_id = egui::FontId::proportional(14.0);
                    let spacing = stack.current_spacing();

                    // Pixel value under the cursor for the status bar. Labelled HU
                    // when spacing exists (same convention as ROI stats).
                    self.hover_readout = pointer_pos
                        .filter(|p| rect.contains(*p))
                        .and_then(|p| {
                            let (ix, iy) = unmap_pt(p);
                            stack.value_at(ix.floor(), iy.floor()).map(|v| {
                                if spacing.is_some() {
                                    format!("HU: {v:.0}")
                                } else {
                                    format!("Val: {v:.0}")
                                }
                            })
                        });

                    if self.dragged_label.is_none()
                        && let Some(pos) = pointer_pos
                        && rect.contains(pos)
                    {
                        for (idx, m) in stack.current_measurements().iter().enumerate() {
                            let labels =
                                get_measurement_labels(m, map_pt, spacing, stack, &ctx, &font_id);
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
                        if primary_pressed && let Some(pos) = pointer_pos {
                            self.dragged_label = Some((idx, label_id));
                            self.dragged_label_offset = pos - label_rect.min;
                            self.drawing_measurement = None;
                        }
                    }

                    // 3. Right-click selection and marquee selection box.
                    // Only when the right button is pressed alone — with the left
                    // button already down this is a W/L drag, not a selection.
                    if let Some(pos) = pointer_pos
                        && secondary_pressed
                        && !primary_down
                        && rect.contains(pos)
                    {
                        self.selection_start_pos = Some(pos);
                        self.selection_box = None;
                    }

                    if let Some(start) = self.selection_start_pos {
                        if secondary_down && let Some(curr) = pointer_pos {
                            let dist = start.distance(curr);
                            if dist >= 4.0 {
                                self.selection_box =
                                    Some(egui::Rect::from_two_pos(start, curr));
                            } else {
                                self.selection_box = None;
                            }
                        }

                        if secondary_released {
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
                                            if self.selected_indices.contains(&idx) {
                                                self.selected_indices.remove(&idx);
                                            } else {
                                                self.selected_indices.insert(idx);
                                            }
                                        } else {
                                            self.selected_indices.clear();
                                            self.selected_indices.insert(idx);
                                        }
                                    }
                                } else if !shift_held {
                                    self.selected_indices.clear();
                                }
                            } else if let Some(sel_box) = self.selection_box {
                                // Marquee Selection
                                if !shift_held {
                                    self.selected_indices.clear();
                                }
                                for (idx, m) in stack.current_measurements().iter().enumerate() {
                                    if measurement_in_marquee(sel_box, m, map_pt) {
                                        self.selected_indices.insert(idx);
                                    }
                                }
                            }
                            self.selection_start_pos = None;
                            self.selection_box = None;
                        }
                    }

                    // 4. Drawing logic
                    if self.dragged_label.is_none()
                        && (self.drawing_measurement.is_some()
                            || (is_measuring && hovered_label_info.is_none()))
                        && let Some(pos) = pointer_pos
                    {
                        let current_pt = unmap_pt(pos);
                            match &mut self.drawing_measurement {
                                None => {
                                    if primary_pressed && rect.contains(pos) {
                                        match self.active_tool {
                                            Tool::Line => {
                                                self.drawing_measurement =
                                                    Some(DrawingState::Line {
                                                        start: current_pt,
                                                        current: current_pt,
                                                    });
                                            }
                                            Tool::Circle => {
                                                self.drawing_measurement =
                                                    Some(DrawingState::Circle {
                                                        center: current_pt,
                                                        current: current_pt,
                                                    });
                                            }
                                            Tool::Orthogonal => {
                                                self.drawing_measurement =
                                                    Some(DrawingState::OrthogonalStep1 {
                                                        start: current_pt,
                                                        current: current_pt,
                                                    });
                                            }
                                            Tool::PanScroll => {}
                                        }
                                    }
                                }
                                Some(state) => {
                                    if primary_down {
                                        match state {
                                            DrawingState::Line { current, .. } => {
                                                *current = current_pt;
                                            }
                                            DrawingState::Circle { current, .. } => {
                                                *current = current_pt;
                                            }
                                            DrawingState::OrthogonalStep1 { current, .. } => {
                                                *current = current_pt;
                                            }
                                            DrawingState::OrthogonalStep2 { current, .. } => {
                                                *current = current_pt;
                                            }
                                        }
                                    }

                                    if primary_released {
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
                                                self.drawing_measurement = None;
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
                                                self.drawing_measurement = None;
                                            }
                                            DrawingState::OrthogonalStep1 { start, current } => {
                                                let dx = current.0 - start.0;
                                                let dy = current.1 - start.1;
                                                if (dx * dx + dy * dy).sqrt() > 0.1 {
                                                    self.drawing_measurement =
                                                        Some(DrawingState::OrthogonalStep2 {
                                                            start,
                                                            end: current,
                                                            current,
                                                        });
                                                } else {
                                                    self.drawing_measurement = None;
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
                                                    stack.add_measurement(
                                                        Measurement::Orthogonal {
                                                            start,
                                                            end,
                                                            ortho_start,
                                                            ortho_end,
                                                            label1_pos: None,
                                                            label2_pos: None,
                                                        },
                                                    );
                                                }
                                                self.drawing_measurement = None;
                                            }
                                        }
                                    }
                                }
                            }
                        }

                    // 5. Render
                    let painter = ui.painter_at(rect);

                    for (idx, m) in stack.current_measurements().iter().enumerate() {
                        let selected = self.selected_indices.contains(&idx);
                        draw_measurement(&painter, m, map_pt, spacing, stack, selected, &ctx);
                    }

                    if let Some(state) = &self.drawing_measurement {
                        draw_drawing_state(&painter, state, map_pt, spacing, stack, &ctx);
                    }

                    // Draw selection marquee box
                    if let Some(sel_box) = self.selection_box {
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
            } else {
                ui.label("(no image loaded)");
            }
        });

        // Request continuous repaint while wheel scrolling or dragging — without this,
        // drags only register at events egui happens to repaint for.
        if wheel_y != 0.0
            || drag_button_down
            || both_buttons_down
            || self.drawing_measurement.is_some()
            || self.dragged_label.is_some()
            || self.selection_start_pos.is_some()
        {
            ctx.request_repaint();
        }
    }
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
                format!("{:.1} mm", dist)
            } else {
                format!("{:.1} px", dist)
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
            let (u1, u2) = if spacing.is_some() {
                ("mm", "mm")
            } else {
                ("px", "px")
            };
            let text1 = format!("L1: {:.1} {}", dist1, u1);
            let text2 = format!("L2: {:.1} {}", dist2, u2);

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

            let mut text = format!("Area: {:.1} {}", area, area_unit);

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
