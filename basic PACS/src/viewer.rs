//! egui-based image viewer.

use eframe::egui;

use crate::stack::ImageStack;

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
}

impl ViewerApp {
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(stack: ImageStack) -> Self {
        Self {
            stack: Some(stack),
            texture: None,
            texture_key: None,
            wheel_accum: 0.0,
            drag_accum: 0.0,
            load_error: None,
            active_preset_name: None,
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
        match crate::loading::paths_for(path) {
            Ok(paths) => {
                self.stack = Some(ImageStack::new(paths));
                self.texture = None;
                self.texture_key = None;
                self.wheel_accum = 0.0;
                self.drag_accum = 0.0;
                self.load_error = None;
                self.active_preset_name = None;
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

        if let Some(stack) = self.stack.as_mut() {
            handle_wheel(stack, &mut self.wheel_accum, wheel_y);
            handle_drag(stack, &mut self.drag_accum, drag_button_down, drag_dy);
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
            // Read current W/L: override if set, otherwise read from current file's tags
            // (so the drag starts at where the file's W/L is). Falls back to 128/256 if
            // the file can't be read — same defaults extract_pixels uses.
            let (current_center, current_width) = stack
                .override_window()
                .or_else(|| current_file_window(stack))
                .unwrap_or((128.0, 256.0));
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
                        let pixels = img.into_raw();
                        let rgba: Vec<u8> = pixels.iter().flat_map(|&v| [v, v, v, 255]).collect();
                        let color_img = egui::ColorImage::from_rgba_unmultiplied(
                            [w as usize, h as usize],
                            &rgba,
                        );
                        self.texture = Some(ctx.load_texture(
                            "dicom-frame",
                            color_img,
                            egui::TextureOptions::default(),
                        ));
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

        // Image (centered)
        ui.vertical_centered(|ui| {
            if let Some(err) = &self.load_error {
                ui.colored_label(egui::Color32::LIGHT_RED, format!("Error: {err}"));
            }
            if let Some(tex) = &self.texture {
                let size = tex.size_vec2();
                ui.image(egui::load::SizedTexture::new(tex.id(), size));
            } else {
                ui.label("(no image loaded)");
            }
        });

        // Status bar: "Slice X / N" (plus active preset name when applicable) at the bottom.
        if let Some(stack) = &self.stack {
            let current = stack.current() + 1;
            let total = stack.len();
            // map_or_else reads worse than the if-let here — two format! arms in one line is dense.
            #[allow(clippy::option_if_let_else)]
            let label = if let Some(name) = self.active_preset_name {
                format!("Slice {current} / {total} — {name}")
            } else {
                format!("Slice {current} / {total}")
            };
            ui.with_layout(egui::Layout::bottom_up(egui::Align::Center), |ui| {
                ui.label(label);
            });
        }

        // Request continuous repaint while wheel scrolling or dragging — without this,
        // drags only register at events egui happens to repaint for.
        if wheel_y != 0.0 || drag_button_down || both_buttons_down {
            ctx.request_repaint();
        }
    }
}

/// Read the current slice's W/L from its DICOM tags. Returns None if the file
/// can't be opened or metadata can't be read.
fn current_file_window(stack: &crate::stack::ImageStack) -> Option<(f64, f64)> {
    use crate::windowing::read_metadata;
    use dicom_object::open_file;

    let path = stack.current_path()?;
    let obj = open_file(path).ok()?;
    let (_dims, ws) = read_metadata(&obj).ok()?;
    Some((ws.center, ws.width))
}
