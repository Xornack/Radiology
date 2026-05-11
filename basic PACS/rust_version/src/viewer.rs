//! egui-based image viewer.

use eframe::egui;

use crate::stack::ImageStack;

/// Wheel delta units per slice advance. Higher = slower scroll.
/// Matches `PyRadStack`'s `_DRAG_SCROLL_SENSITIVITY = 10`.
const WHEEL_SENSITIVITY: f32 = 10.0;

/// Pixels of left-click drag per slice advance.
const DRAG_SENSITIVITY: f32 = 10.0;

/// State for the GUI viewer. Holds a stack and the currently-uploaded texture.
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    /// Index whose pixels are currently in `texture`. Re-upload when this != `stack.current()`.
    texture_idx: Option<usize>,
    /// Accumulated wheel delta; consumed in `WHEEL_SENSITIVITY` chunks per slice step.
    wheel_accum: f32,
    /// Accumulated left-click drag dy; consumed in `DRAG_SENSITIVITY` chunks per slice step.
    drag_accum: f32,
}

impl ViewerApp {
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(stack: ImageStack) -> Self {
        Self { stack: Some(stack), texture: None, texture_idx: None, wheel_accum: 0.0, drag_accum: 0.0 }
    }

    /// Construct an empty viewer (no stack). Used for error cases.
    #[must_use]
    // egui::TextureHandle is not const-constructible; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn empty() -> Self {
        Self { stack: None, texture: None, texture_idx: None, wheel_accum: 0.0, drag_accum: 0.0 }
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

        // Read all pointer/scroll input in one pass.
        // In egui 0.27+, smooth_scroll_delta replaces scroll_delta.
        let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
        let (drag_button_down, drag_dy) = ctx.input(|i| {
            let down = i.pointer.button_down(egui::PointerButton::Primary);
            let dy = if down { i.pointer.delta().y } else { 0.0 };
            (down, dy)
        });

        if let Some(stack) = self.stack.as_mut() {
            handle_wheel(stack, &mut self.wheel_accum, wheel_y);
            handle_drag(stack, &mut self.drag_accum, drag_button_down, drag_dy);
        }

        // Re-upload texture if the current slice changed.
        if let Some(stack) = &self.stack {
            let need_upload = self.texture_idx != Some(stack.current());
            if need_upload
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
                self.texture_idx = Some(stack.current());
            }
        }

        // Image (centered)
        ui.vertical_centered(|ui| {
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
        if wheel_y != 0.0 || drag_button_down {
            ctx.request_repaint();
        }
    }
}
