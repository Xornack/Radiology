//! Scrollable stack of DICOM slices with one-slot image cache.

use std::path::PathBuf;

use dicom_object::open_file;
use image::GrayImage;

use crate::errors::RrsError;
use crate::windowing::{apply_window, extract_pixels};

/// Sorted DICOM series with a current-slice cursor and one-slot image cache.
///
/// Slices are loaded on demand via `get_current_image`. The cache holds the most
/// recently loaded slice so repeated calls (e.g. across egui repaints) don't
/// re-decode the same file.
pub struct ImageStack {
    paths: Vec<PathBuf>,
    current: usize,
    cache: std::cell::RefCell<Option<(usize, GrayImage)>>,
    /// User-set W/L (center, width) overriding per-file DICOM tags.
    /// `None` means "use the file's tags" (default).
    override_window: Option<(f64, f64)>,
}

impl ImageStack {
    #[must_use]
    // Vec heap-allocation makes this non-const; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(paths: Vec<PathBuf>) -> Self {
        Self { paths, current: 0, cache: std::cell::RefCell::new(None), override_window: None }
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
    pub fn override_window(&self) -> Option<(f64, f64)> {
        self.override_window
    }

    /// Set the user override W/L (or `None` to revert to per-file tags).
    /// Invalidates the cached image so the next `get_current_image` re-renders.
    pub fn set_override_window(&mut self, ws: Option<(f64, f64)>) {
        self.override_window = ws;
        self.cache.borrow_mut().take();
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

        // Cached? Use let-chain to collapse the nested if.
        {
            let cache = self.cache.borrow();
            if let Some((idx, img)) = cache.as_ref()
                && *idx == self.current
            {
                return Ok(img.clone());
            }
        }

        let path = &self.paths[self.current];
        let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
        let (pixels, dims, ws) = extract_pixels(&obj)?;
        let img = apply_window(&pixels, dims, ws);

        *self.cache.borrow_mut() = Some((self.current, img.clone()));
        Ok(img)
    }
}
