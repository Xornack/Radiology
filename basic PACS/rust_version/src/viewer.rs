//! egui-based image viewer.

use eframe::egui;

use crate::stack::ImageStack;

/// State for the GUI viewer. Holds a stack and the currently-uploaded texture.
pub struct ViewerApp {
    stack: Option<ImageStack>,
    texture: Option<egui::TextureHandle>,
    /// Index whose pixels are currently in `texture`. Re-upload when this != stack.current().
    texture_idx: Option<usize>,
}

impl ViewerApp {
    #[must_use]
    pub fn new(stack: ImageStack) -> Self {
        Self { stack: Some(stack), texture: None, texture_idx: None }
    }

    /// Construct an empty viewer (no stack). Used for error cases.
    #[must_use]
    pub fn empty() -> Self {
        Self { stack: None, texture: None, texture_idx: None }
    }
}

impl eframe::App for ViewerApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();

        // Handle mouse-wheel scroll. egui exposes scroll as part of input state.
        // In egui 0.27+, smooth_scroll_delta replaces scroll_delta.
        let wheel_y = ctx.input(|i| i.smooth_scroll_delta.y);
        if let Some(stack) = self.stack.as_mut() {
            if wheel_y > 0.0 {
                stack.prev();
            } else if wheel_y < 0.0 {
                stack.next();
            }
        }

        // Re-upload texture if the current slice changed.
        if let Some(stack) = &self.stack {
            let need_upload = self.texture_idx != Some(stack.current());
            if need_upload {
                if let Ok(img) = stack.get_current_image() {
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

        // Request a repaint when the wheel was scrolled (otherwise egui idles).
        if wheel_y != 0.0 {
            ctx.request_repaint();
        }
    }
}
