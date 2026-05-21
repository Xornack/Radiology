//! Scrollable stack of DICOM slices with one-slot decoded-pixel cache.

use std::path::PathBuf;

use dicom_object::open_file;
use image::GrayImage;

use crate::errors::RrsError;
use crate::windowing::{WindowSettings, apply_window, extract_pixels};

/// One-slot cache of the most recently loaded slice's decoded payload.
/// DICOM holds raw stored pixels so W/L drags re-window without re-decoding the file;
/// non-DICOM holds the final 8-bit image (no W/L applies).
enum Cached {
    Dicom {
        pixels: Vec<i32>,
        dims: (u32, u32),
        ws: WindowSettings,
    },
    NonDicom(GrayImage),
}

/// Sorted DICOM series with a current-slice cursor and one-slot pixel cache.
///
/// Slices are loaded on demand via `get_current_image`. The cache holds the most
/// recently loaded slice's raw (pre-window) pixels so repeated calls — including
/// W/L drags — don't re-decode the same file.
pub struct ImageStack {
    paths: Vec<PathBuf>,
    current: usize,
    cache: std::cell::RefCell<Option<(usize, Cached)>>,
    /// User-set W/L (center, width) overriding per-file DICOM tags.
    /// `None` means "use the file's tags" (default).
    override_window: Option<(f64, f64)>,
}

impl ImageStack {
    #[must_use]
    // Vec heap-allocation makes this non-const; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(paths: Vec<PathBuf>) -> Self {
        Self {
            paths,
            current: 0,
            cache: std::cell::RefCell::new(None),
            override_window: None,
        }
    }

    #[must_use]
    // Vec::len is not const-stable; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn len(&self) -> usize {
        self.paths.len()
    }

    #[must_use]
    // Vec::is_empty is not const-stable; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn is_empty(&self) -> bool {
        self.paths.is_empty()
    }

    #[must_use]
    pub const fn current(&self) -> usize {
        self.current
    }

    /// Path of the current slice, or `None` if the stack is empty.
    #[must_use]
    pub fn current_path(&self) -> Option<&std::path::Path> {
        self.paths.get(self.current).map(PathBuf::as_path)
    }

    /// Advance one slice (saturating at last index). Returns the new index.
    // `next` mirrors egui's scroll direction naming; not an Iterator impl.
    #[allow(clippy::should_implement_trait)]
    // Vec::len call prevents `const fn` here.
    #[allow(clippy::missing_const_for_fn)]
    pub fn next(&mut self) -> usize {
        if self.current + 1 < self.paths.len() {
            self.current += 1;
        }
        self.current
    }

    /// Go back one slice (saturating at 0). Returns the new index.
    pub const fn prev(&mut self) -> usize {
        self.current = self.current.saturating_sub(1);
        self.current
    }

    #[must_use]
    pub const fn override_window(&self) -> Option<(f64, f64)> {
        self.override_window
    }

    /// Set the user override W/L (or `None` to revert to per-file tags).
    /// Does NOT invalidate the cache — cache holds pre-window pixels, so the next
    /// `get_current_image` re-applies windowing without re-decoding the file.
    pub const fn set_override_window(&mut self, ws: Option<(f64, f64)>) {
        self.override_window = ws;
    }

    /// Load the current slice (using the cache when possible).
    ///
    /// # Errors
    /// Returns `RrsError` if the underlying DICOM can't be opened or decoded.
    /// Returns an `RrsError::UnsupportedPixels` with the message "empty stack"
    /// if the stack contains no paths.
    pub fn get_current_image(&self) -> Result<GrayImage, RrsError> {
        if self.paths.is_empty() {
            return Err(RrsError::UnsupportedPixels("empty stack".into()));
        }

        // Reload cache only when the slice index changed.
        let needs_load = self
            .cache
            .borrow()
            .as_ref()
            .is_none_or(|(idx, _)| *idx != self.current);
        if needs_load {
            let cached = self.load_slice(self.current)?;
            *self.cache.borrow_mut() = Some((self.current, cached));
        }

        let cache = self.cache.borrow();
        let (_, cached) = cache.as_ref().expect("just filled");
        Ok(match cached {
            Cached::NonDicom(img) => {
                if let Some((center, width)) = self.override_window {
                    let pixels: Vec<i32> = img.as_raw().iter().map(|&v| i32::from(v)).collect();
                    let dims = (img.height(), img.width());
                    let ws = WindowSettings {
                        center,
                        width,
                        slope: 1.0,
                        intercept: 0.0,
                    };
                    apply_window(&pixels, dims, ws)
                } else {
                    img.clone()
                }
            }
            Cached::Dicom { pixels, dims, ws } => {
                let mut ws = *ws;
                if let Some((center, width)) = self.override_window {
                    ws.center = center;
                    ws.width = width;
                }
                apply_window(pixels, *dims, ws)
            }
        })
    }

    fn load_slice(&self, idx: usize) -> Result<Cached, RrsError> {
        let path = &self.paths[idx];
        if is_dicom_path(path) {
            let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
            let (pixels, dims, ws) = extract_pixels(&obj)?;
            Ok(Cached::Dicom { pixels, dims, ws })
        } else {
            // JPG/PNG: image crate decode; override W/L is intentionally ignored — no HU values to map.
            let img = image::open(path)
                .map_err(|e| RrsError::Dicom(format!("decode {}: {}", path.display(), e)))?
                .into_luma8();
            Ok(Cached::NonDicom(img))
        }
    }
}

// `.dcm` extension → use DICOM pipeline; anything else → image crate.
fn is_dicom_path(path: &std::path::Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("dcm"))
}
