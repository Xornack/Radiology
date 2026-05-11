//! egui-based image viewer.

use eframe::egui;

use crate::stack::ImageStack;

/// Wheel delta units per slice advance. Higher = slower scroll.
/// Matches PyRadStack's `_DRAG_SCROLL_SENSITIVITY = 10`.
const WHEEL_SENSITIVITY: f32 = 10.0;

/// Pixels of left-click drag per slice advance.
const DRAG_SENSITIVITY: f32 = 10.0;

/// State for the GUI viewer. Holds a stack and the currently-uploaded texture.
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    /// Index whose pixels are currently in `texture`. Re-upload when this != `stack.current()`.
    texture_idx: Option<usize>,
    /// Accumulated wheel delta; consumed in WHEEL_SENSITIVITY chunks per slice step.
    wheel_accum: f32,
    /// Accumulated left-click drag dy; consumed in DRAG_SENSITIVITY chunks per slice step.
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

impl eframe::App for ViewerApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();

        // Handle mouse-wheel scroll. egui exposes scroll as part of input state.
        // In egui 0.27+, smooth_scroll_delta replaces scroll_delta.
        // Accumulate wheel delta and consume in WHEEL_SENSITIVITY chunks so high-res
        // wheels don't blow past slices. wheel_y > 0 = scroll up = previous slice.
        let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
        if let Some(stack) = self.stack.as_mut() {
            self.wheel_accum += wheel_y;
            while self.wheel_accum >= WHEEL_SENSITIVITY {
                stack.prev();
                self.wheel_accum -= WHEEL_SENSITIVITY;
            }
            while self.wheel_accum <= -WHEEL_SENSITIVITY {
                stack.next();
                self.wheel_accum += WHEEL_SENSITIVITY;
            }
        }

        // Left-click drag = scroll. Accumulate dy while button held; consume in
        // DRAG_SENSITIVITY chunks. Drag down = next slice (positive dy in egui coords).
        let (drag_button_down, drag_dy) = ctx.input(|i| {
            let down = i.pointer.button_down(egui::PointerButton::Primary);
            let dy = if down { i.pointer.delta().y } else { 0.0 };
            (down, dy)
        });
        if let Some(stack) = self.stack.as_mut() {
            if drag_button_down {
                self.drag_accum += drag_dy;
                while self.drag_accum >= DRAG_SENSITIVITY {
                    stack.next();
                    self.drag_accum -= DRAG_SENSITIVITY;
                }
                while self.drag_accum <= -DRAG_SENSITIVITY {
                    stack.prev();
                    self.drag_accum += DRAG_SENSITIVITY;
                }
            } else {
                // Reset on release so the next drag starts fresh.
                self.drag_accum = 0.0;
            }
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
