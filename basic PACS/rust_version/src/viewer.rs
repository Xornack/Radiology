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
}

impl ViewerApp {
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(stack: ImageStack) -> Self {
        Self { stack: Some(stack), texture: None, texture_key: None, wheel_accum: 0.0, drag_accum: 0.0, load_error: None }
    }

    /// Construct an empty viewer (no stack). Used for error cases.
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn empty() -> Self {
        Self { stack: None, texture: None, texture_key: None, wheel_accum: 0.0, drag_accum: 0.0, load_error: None }
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

impl eframe::App for ViewerApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();

        // Top menubar — file open dialogs.
        egui::Panel::top("menubar").show_inside(ui, |ui| {
            egui::MenuBar::new().ui(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("Open Folder…").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        // When a series is open, default the picker to the study folder
                        // (parent of the series dir) so sibling series are visible without
                        // navigation. With nothing open, let the OS choose the start dir.
                        let mut dialog = rfd::FileDialog::new().set_title("Open DICOM folder");
                        if let Some(study_dir) = self.study_dir() {
                            dialog = dialog.set_directory(study_dir);
                        }
                        if let Some(folder) = dialog.pick_folder() {
                            self.load_path(&folder);
                        }
                    }
                    if ui.button("Open File…").clicked() {
                        ui.close_kind(egui::UiKind::Menu);
                        if let Some(file) = rfd::FileDialog::new()
                            .set_title("Open DICOM file")
                            .add_filter("DICOM", &["dcm"])
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

        // Both-button drag = W/L adjustment. dx → width, dy → center.
        // While both held, mutate stack.override_window each frame.
        let (both_buttons_down, wl_drag_delta) = ctx.input(|i| {
            let primary = i.pointer.button_down(egui::PointerButton::Primary);
            let secondary = i.pointer.button_down(egui::PointerButton::Secondary);
            let both = primary && secondary;
            let delta = if both { i.pointer.delta() } else { egui::Vec2::ZERO };
            (both, delta)
        });
        if both_buttons_down
            && let Some(stack) = self.stack.as_mut() {
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
        }

        // Re-upload texture when either the slice index OR the override W/L changed.
        // The composite key catches W/L drag (override mutates without index change).
        if let Some(stack) = &self.stack {
            let current_key: TextureKey = (stack.current(), stack.override_window());
            if self.texture_key != Some(current_key)
                && let Ok(img) = stack.get_current_image()
            {
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
            }
        }

        // Image (centered)
        ui.vertical_centered(|ui| {
            if let Some(err) = &self.load_error {
                ui.colored_label(egui::Color32::LIGHT_RED, format!("Load error: {err}"));
            }
            if let Some(tex) = &self.texture {
                let size = tex.size_vec2();
                ui.image(egui::load::SizedTexture::new(tex.id(), size));
            } else {
                ui.label("(no image loaded)");
            }
        });

        // Status bar: "Slice X / N" at the bottom
        if let Some(stack) = &self.stack {
            let current = stack.current() + 1;
            let total = stack.len();
            ui.with_layout(
                egui::Layout::bottom_up(egui::Align::Center),
                |ui| { ui.label(format!("Slice {current} / {total}")); },
            );
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
    use dicom_object::open_file;
    use crate::windowing::read_metadata;

    let path = stack.current_path()?;
    let obj = open_file(path).ok()?;
    let (_dims, ws) = read_metadata(&obj).ok()?;
    Some((ws.center, ws.width))
}
