//! Scrollable stack of DICOM slices with an LRU decoded-pixel cache.

use std::path::PathBuf;

use dicom_object::open_file;
use image::GrayImage;

use crate::errors::RrsError;
use crate::windowing::{WindowSettings, apply_window, extract_pixels};

#[derive(Debug, Clone, PartialEq)]
pub enum Measurement {
    Line {
        start: (f64, f64),
        end: (f64, f64),
        label_pos: Option<(f64, f64)>,
    },
    Orthogonal {
        start: (f64, f64),
        end: (f64, f64),
        ortho_start: (f64, f64),
        ortho_end: (f64, f64),
        label1_pos: Option<(f64, f64)>,
        label2_pos: Option<(f64, f64)>,
    },
    Circle {
        center: (f64, f64),
        radius: f64,
        label_pos: Option<(f64, f64)>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RoiStats {
    pub area: f64,
    pub mean: f64,
    pub min: f64,
    pub max: f64,
    pub count: usize,
}

/// A cached slice's decoded payload.
/// DICOM holds raw stored pixels so W/L drags re-window without re-decoding the file;
/// non-DICOM holds the decoded 8-bit image (W/L override is applied at render time).
enum Cached {
    Dicom {
        pixels: Vec<i32>,
        dims: (u32, u32),
        ws: WindowSettings,
        spacing: Option<(f64, f64)>,
    },
    NonDicom(GrayImage),
}

/// Total elements cached across all slots before eviction kicks in.
/// DICOM entries are i32 (4 bytes/element), so this is ~256 MB worst case —
/// roughly 240 slices of 512×512 CT, or ~5 mammo-sized frames.
const CACHE_ELEMENT_BUDGET: usize = 64_000_000;

impl Cached {
    /// Number of stored elements — the dominant memory cost of a cache entry.
    fn element_count(&self) -> usize {
        match self {
            Self::Dicom { pixels, .. } => pixels.len(),
            Self::NonDicom(img) => img.as_raw().len(),
        }
    }
}

/// Sorted DICOM series with a current-slice cursor and an LRU pixel cache.
///
/// Slices are loaded on demand via `get_current_image`. The cache holds raw
/// (pre-window) pixels of recently viewed slices — most recent first — so
/// W/L drags and back-and-forth scrubbing don't re-decode files.
pub struct ImageStack {
    paths: Vec<PathBuf>,
    current: usize,
    cache: std::cell::RefCell<Vec<(usize, Cached)>>,
    /// User-set W/L (center, width) overriding per-file DICOM tags.
    /// `None` means "use the file's tags" (default).
    override_window: Option<(f64, f64)>,
    /// Measurements stored per slice.
    measurements: Vec<Vec<Measurement>>,
}

impl ImageStack {
    #[must_use]
    // Vec heap-allocation makes this non-const; suppress nursery lint.
    #[allow(clippy::missing_const_for_fn)]
    pub fn new(paths: Vec<PathBuf>) -> Self {
        let n = paths.len();
        Self {
            paths,
            current: 0,
            cache: std::cell::RefCell::new(Vec::new()),
            override_window: None,
            measurements: vec![vec![]; n],
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

    /// The W/L in effect for the current slice: the user override if set,
    /// otherwise the file's own tags (read from the cache, not from disk).
    /// `None` for non-DICOM slices with no override, or if the slice can't load.
    #[must_use]
    pub fn effective_window(&self) -> Option<(f64, f64)> {
        if self.override_window.is_some() {
            return self.override_window;
        }
        self.ensure_cache().ok()?;
        let cache = self.cache.borrow();
        match cache.first() {
            Some((_, Cached::Dicom { ws, .. })) => Some((ws.center, ws.width)),
            _ => None,
        }
    }

    /// Make sure the current slice's decoded payload is cached, without
    /// rendering it. Cheap when already cached — callers that only need
    /// metadata (spacing, ROI stats) use this to avoid a full W/L pass.
    fn ensure_cache(&self) -> Result<(), RrsError> {
        if self.paths.is_empty() {
            return Err(RrsError::UnsupportedPixels("empty stack".into()));
        }
        {
            let mut cache = self.cache.borrow_mut();
            if let Some(pos) = cache.iter().position(|(idx, _)| *idx == self.current) {
                // Move to front so eviction drops the least recently viewed slice.
                if pos != 0 {
                    let entry = cache.remove(pos);
                    cache.insert(0, entry);
                }
                return Ok(());
            }
        }
        let loaded = self.load_slice(self.current)?;
        let mut cache = self.cache.borrow_mut();
        cache.insert(0, (self.current, loaded));
        // Evict least-recently-viewed entries once over budget (always keep one).
        let mut total: usize = cache.iter().map(|(_, c)| c.element_count()).sum();
        while cache.len() > 1 && total > CACHE_ELEMENT_BUDGET {
            if let Some((_, evicted)) = cache.pop() {
                total -= evicted.element_count();
            }
        }
        Ok(())
    }

    /// Load the current slice (using the cache when possible).
    ///
    /// # Errors
    /// Returns `RrsError` if the underlying DICOM can't be opened or decoded.
    /// Returns an `RrsError::UnsupportedPixels` with the message "empty stack"
    /// if the stack contains no paths.
    pub fn get_current_image(&self) -> Result<GrayImage, RrsError> {
        self.ensure_cache()?;
        let cache = self.cache.borrow();
        let (_, cached) = cache.first().expect("ensure_cache put current at front");
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
            Cached::Dicom {
                pixels, dims, ws, ..
            } => {
                let mut ws = *ws;
                if let Some((center, width)) = self.override_window {
                    ws.center = center;
                    ws.width = width;
                }
                apply_window(pixels, *dims, ws)
            }
        })
    }

    #[must_use]
    pub fn current_measurements(&self) -> &[Measurement] {
        if self.measurements.is_empty() {
            &[]
        } else {
            &self.measurements[self.current]
        }
    }

    pub fn add_measurement(&mut self, m: Measurement) {
        if !self.measurements.is_empty() {
            self.measurements[self.current].push(m);
        }
    }

    pub fn clear_current_measurements(&mut self) {
        if !self.measurements.is_empty() {
            self.measurements[self.current].clear();
        }
    }

    pub fn current_measurements_mut(&mut self) -> &mut [Measurement] {
        if self.measurements.is_empty() {
            &mut []
        } else {
            &mut self.measurements[self.current]
        }
    }

    pub fn remove_measurements(&mut self, indices: &std::collections::HashSet<usize>) {
        if !self.measurements.is_empty() {
            let mut idx = 0;
            self.measurements[self.current].retain(|_| {
                let keep = !indices.contains(&idx);
                idx += 1;
                keep
            });
        }
    }

    pub fn clear_all_measurements(&mut self) {
        for list in &mut self.measurements {
            list.clear();
        }
    }

    /// True when any slice has at least one measurement.
    #[must_use]
    pub fn has_measurements(&self) -> bool {
        self.measurements.iter().any(|m| !m.is_empty())
    }

    #[must_use]
    pub fn current_spacing(&self) -> Option<(f64, f64)> {
        self.ensure_cache().ok()?;
        let cache = self.cache.borrow();
        match cache.first() {
            Some((_, Cached::Dicom { spacing, .. })) => *spacing,
            _ => None,
        }
    }

    /// Rescaled value (HU for CT) of the pixel at image coordinates, from the
    /// cache. `None` when out of bounds or the slice can't load.
    #[must_use]
    // Casts are guarded: x/y are checked non-negative, then bounds-checked after truncation.
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    pub fn value_at(&self, x: f64, y: f64) -> Option<f64> {
        if x < 0.0 || y < 0.0 {
            return None;
        }
        self.ensure_cache().ok()?;
        let cache = self.cache.borrow();
        let (_, cached) = cache.first()?;
        match cached {
            Cached::Dicom {
                pixels, dims, ws, ..
            } => {
                let (rows, cols) = *dims;
                let (xi, yi) = (x as u32, y as u32);
                if xi >= cols || yi >= rows {
                    return None;
                }
                let stored = pixels[yi as usize * cols as usize + xi as usize];
                Some(f64::from(stored).mul_add(ws.slope, ws.intercept))
            }
            Cached::NonDicom(img) => {
                let (w, h) = img.dimensions();
                let (xi, yi) = (x as u32, y as u32);
                if xi >= w || yi >= h {
                    return None;
                }
                Some(f64::from(img.get_pixel(xi, yi)[0]))
            }
        }
    }

    #[must_use]
    pub fn get_roi_stats(&self, center: (f64, f64), radius: f64) -> Option<RoiStats> {
        self.ensure_cache().ok()?;
        let cache = self.cache.borrow();
        let (_, cached) = cache.first()?;

        let (cx, cy) = center;
        let r2 = radius * radius;

        let mut sum = 0.0;
        let mut min = f64::INFINITY;
        let mut max = f64::NEG_INFINITY;
        let mut count = 0;

        match cached {
            Cached::Dicom {
                pixels,
                dims,
                ws,
                spacing,
            } => {
                let (rows, cols) = *dims;
                // Guards the `cols - 1` below from underflowing on a degenerate frame.
                if rows == 0 || cols == 0 {
                    return None;
                }

                // Determine bounding box
                let min_x = (cx - radius).floor().max(0.0) as u32;
                let max_x = (cx + radius).ceil().min((cols - 1) as f64) as u32;
                let min_y = (cy - radius).floor().max(0.0) as u32;
                let max_y = (cy + radius).ceil().min((rows - 1) as f64) as u32;

                for y in min_y..=max_y {
                    for x in min_x..=max_x {
                        let dx = x as f64 - cx;
                        let dy = y as f64 - cy;
                        if dx * dx + dy * dy <= r2 {
                            let stored = pixels[(y * cols + x) as usize];
                            let val = f64::from(stored).mul_add(ws.slope, ws.intercept);
                            sum += val;
                            if val < min {
                                min = val;
                            }
                            if val > max {
                                max = val;
                            }
                            count += 1;
                        }
                    }
                }

                if count == 0 {
                    return None;
                }

                let area = if let Some((row_sp, col_sp)) = spacing {
                    count as f64 * row_sp * col_sp
                } else {
                    count as f64
                };

                Some(RoiStats {
                    area,
                    mean: sum / count as f64,
                    min,
                    max,
                    count,
                })
            }
            Cached::NonDicom(img) => {
                let (cols, rows) = img.dimensions(); // GrayImage uses (width, height) i.e. (cols, rows)
                // Guards the `cols - 1` below from underflowing on a degenerate frame.
                if rows == 0 || cols == 0 {
                    return None;
                }

                // Determine bounding box
                let min_x = (cx - radius).floor().max(0.0) as u32;
                let max_x = (cx + radius).ceil().min((cols - 1) as f64) as u32;
                let min_y = (cy - radius).floor().max(0.0) as u32;
                let max_y = (cy + radius).ceil().min((rows - 1) as f64) as u32;

                for y in min_y..=max_y {
                    for x in min_x..=max_x {
                        let dx = x as f64 - cx;
                        let dy = y as f64 - cy;
                        if dx * dx + dy * dy <= r2 {
                            let val = img.get_pixel(x, y)[0] as f64;
                            sum += val;
                            if val < min {
                                min = val;
                            }
                            if val > max {
                                max = val;
                            }
                            count += 1;
                        }
                    }
                }

                if count == 0 {
                    return None;
                }

                let area = count as f64;

                Some(RoiStats {
                    area,
                    mean: sum / count as f64,
                    min,
                    max,
                    count,
                })
            }
        }
    }

    fn load_slice(&self, idx: usize) -> Result<Cached, RrsError> {
        let path = &self.paths[idx];
        if is_dicom_path(path) {
            let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;
            let (pixels, dims, ws) = extract_pixels(&obj)?;

            // Try PixelSpacing (0028,0030)
            let mut spacing = obj
                .element(dicom_dictionary_std::tags::PIXEL_SPACING)
                .ok()
                .and_then(|e| e.to_multi_float64().ok())
                .and_then(|v| {
                    if v.len() >= 2 {
                        Some((v[0], v[1]))
                    } else {
                        None
                    }
                });

            // If absent, try ImagerPixelSpacing (0018,1164)
            if spacing.is_none() {
                spacing = obj
                    .element(dicom_dictionary_std::tags::IMAGER_PIXEL_SPACING)
                    .ok()
                    .and_then(|e| e.to_multi_float64().ok())
                    .and_then(|v| {
                        if v.len() >= 2 {
                            Some((v[0], v[1]))
                        } else {
                            None
                        }
                    });
            }

            Ok(Cached::Dicom {
                pixels,
                dims,
                ws,
                spacing,
            })
        } else {
            // JPG/PNG via the image crate. Explicit dimension limits so a malformed
            // header can't trigger a giant allocation (the crate's defaults cap
            // total allocation but not width/height). The W/L override is applied
            // at render time in get_current_image, like a brightness/contrast knob.
            let mut reader = image::ImageReader::open(path)
                .map_err(|e| RrsError::Dicom(format!("open {}: {}", path.display(), e)))?;
            let mut limits = image::Limits::default();
            limits.max_image_width = Some(crate::windowing::MAX_DIMENSION);
            limits.max_image_height = Some(crate::windowing::MAX_DIMENSION);
            reader.limits(limits);
            let img = reader
                .decode()
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
