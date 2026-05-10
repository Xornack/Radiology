//! egui-based image viewer.

use eframe::egui;
use image::GrayImage;

/// State for the GUI viewer. Holds at most one uploaded image.
pub struct ViewerApp {
    /// Pre-windowed grayscale image to display. `None` until `set_image` is called.
    pending: Option<GrayImage>,
    /// Cached GPU texture once uploaded.
    texture: Option<egui::TextureHandle>,
}

impl ViewerApp {
    #[must_use]
    pub const fn new() -> Self {
        Self { pending: None, texture: None }
    }

    /// Provide the image to display. Texture upload happens on the next frame.
    pub fn set_image(&mut self, img: GrayImage) {
        self.pending = Some(img);
        self.texture = None;
    }
}

impl Default for ViewerApp {
    fn default() -> Self {
        Self::new()
    }
}

impl eframe::App for ViewerApp {
    // eframe 0.34.x: the required method is `ui`, not `update`.
    // `update` is a provided method that wraps `ui` via CentralPanel::show_inside.
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        // Upload pending image to a texture on the first frame after set_image.
        if let Some(img) = self.pending.take() {
            let (w, h) = img.dimensions();
            let pixels = img.into_raw();
            // egui ColorImage expects RGBA. Expand grayscale → RGBA by replicating each luma byte.
            let rgba: Vec<u8> = pixels.iter().flat_map(|&v| [v, v, v, 255]).collect();
            let color_img = egui::ColorImage::from_rgba_unmultiplied(
                [w as usize, h as usize],
                &rgba,
            );
            self.texture = Some(ui.ctx().load_texture(
                "dicom-frame",
                color_img,
                egui::TextureOptions::default(),
            ));
        }

        ui.vertical_centered(|ui| {
            if let Some(tex) = &self.texture {
                let size = tex.size_vec2();
                // SizedTexture newtype satisfies Into<ImageSource> — works with egui 0.34.x
                ui.image(egui::load::SizedTexture::new(tex.id(), size));
            } else {
                ui.label("(no image loaded)");
            }
        });
    }
}
