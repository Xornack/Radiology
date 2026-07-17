//! DICOM window/level math and pixel extraction.

use dicom_dictionary_std::tags;
use dicom_object::{DefaultDicomObject, Tag};
use dicom_pixeldata::{ConvertOptions, ModalityLutOption, PixelDecoder};
use image::{GrayImage, ImageBuffer, Luma};

use crate::errors::RrsError;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WindowSettings {
    pub center: f64,
    pub width: f64,
    pub slope: f64,
    pub intercept: f64,
}

impl Default for WindowSettings {
    /// Generic midpoint defaults — safe for any modality.
    /// Not CT-specific (CT abdomen would be center=40, width=400).
    fn default() -> Self {
        Self {
            center: 128.0,
            width: 256.0,
            slope: 1.0,
            intercept: 0.0,
        }
    }
}

/// Decoded frame: (stored pixel values as i32, (rows, cols), window settings).
/// Stored values are pre-rescale — call sites apply slope/intercept inside `apply_window`.
type ExtractResult = (Vec<i32>, (u32, u32), WindowSettings);

/// Largest accepted frame edge. Real modalities top out well below this;
/// anything bigger is malformed metadata and would only trigger a giant
/// allocation attempt in the decoder.
pub const MAX_DIMENSION: u32 = 16_384;

/// Read just the dims + W/L tags from an already-opened DICOM object.
///
/// Cheap — does not touch pixel data. Use this when you only need metadata
/// (sorting, listing) and want to avoid decode cost on hundreds of files.
///
/// # Errors
/// Returns `RrsError::MissingTag` if `Rows` or `Columns` tags are absent.
/// Returns `RrsError::UnsupportedPixels` if either dimension is 0 or
/// exceeds [`MAX_DIMENSION`].
pub fn read_metadata(obj: &DefaultDicomObject) -> Result<((u32, u32), WindowSettings), RrsError> {
    let rows = read_u32(obj, tags::ROWS, "Rows")?;
    let cols = read_u32(obj, tags::COLUMNS, "Columns")?;
    if rows == 0 || cols == 0 || rows > MAX_DIMENSION || cols > MAX_DIMENSION {
        return Err(RrsError::UnsupportedPixels(format!(
            "invalid dimensions {rows}x{cols} (accepted: 1..={MAX_DIMENSION})"
        )));
    }
    let center = read_f64_or_default(obj, tags::WINDOW_CENTER, 128.0);
    let width = read_f64_or_default(obj, tags::WINDOW_WIDTH, 256.0);
    let slope = read_f64_or_default(obj, tags::RESCALE_SLOPE, 1.0);
    let intercept = read_f64_or_default(obj, tags::RESCALE_INTERCEPT, 0.0);
    Ok((
        (rows, cols),
        WindowSettings {
            center,
            width,
            slope,
            intercept,
        },
    ))
}

/// Extract dims, pre-rescale stored pixel values, and W/L tags from an already-opened DICOM object.
///
/// Stored values are pre-rescale; `apply_window` does the slope/intercept transform.
///
/// # Errors
/// Returns `RrsError::Dicom` if pixel decoding fails.
/// Returns `RrsError::MissingTag` if `Rows` or `Columns` tags are absent.
/// Returns `RrsError::UnsupportedPixels` if the decoded frame length doesn't match dimensions.
pub fn extract_pixels(obj: &DefaultDicomObject) -> Result<ExtractResult, RrsError> {
    let (dims, ws) = read_metadata(obj)?;
    let (rows, cols) = dims;

    // Decode without applying the Modality LUT so we get raw stored pixel values.
    let decoded = obj
        .decode_pixel_data()
        .map_err(|e| RrsError::Dicom(e.to_string()))?;
    let options = ConvertOptions::new().with_modality_lut(ModalityLutOption::None);
    let frame: Vec<i32> = decoded
        .to_vec_with_options(&options)
        .map_err(|e| RrsError::Dicom(e.to_string()))?;

    // Cast to usize before multiplying so dimensions like 65535x65535 don't overflow u32.
    let expected = rows as usize * cols as usize;
    if frame.len() != expected {
        return Err(RrsError::UnsupportedPixels(format!(
            "decoded {} values, expected {}x{}={}",
            frame.len(),
            rows,
            cols,
            expected
        )));
    }

    Ok((frame, dims, ws))
}

// Any element() failure is reported as MissingTag; if the tag exists with an unexpected VR
// the user gets a misleading "missing" error. Refine when real-world files surface the case.
fn read_u32(obj: &DefaultDicomObject, tag: Tag, name: &'static str) -> Result<u32, RrsError> {
    let elt = obj.element(tag).map_err(|_| RrsError::MissingTag(name))?;
    elt.to_int::<u32>()
        .map_err(|e| RrsError::Dicom(format!("{name}: {e}")))
}

// Silently falls back on missing or unparseable tags — W/L is optional and a viewer
// should still open the image. Caller can't distinguish "missing" from "parse failed".
fn read_f64_or_default(obj: &DefaultDicomObject, tag: Tag, default: f64) -> f64 {
    obj.element(tag)
        .ok()
        .and_then(|e| e.to_float64().ok())
        .unwrap_or(default)
}

/// Apply rescale + Window/Level to stored pixel values to produce a displayable 8-bit image.
///
/// Steps per DICOM PS3.3 C.11.1:
/// 1. HU/VOI input = stored * slope + intercept
/// 2. Clamp to [center - width/2, center + width/2]
/// 3. Linearly rescale clamped values to 0..=255
///
/// `dims` is `(rows, cols)`; the returned `GrayImage` has `dimensions() == (cols, rows)`
/// because the `image` crate uses `(width, height)`.
///
/// # Panics
/// Panics if `pixels.len() != dims.0 * dims.1`. Use `extract_pixels` to get a `(pixels, dims)`
/// tuple where this invariant holds.
#[must_use]
pub fn apply_window(pixels: &[i32], dims: (u32, u32), w: WindowSettings) -> GrayImage {
    let (rows, cols) = dims;
    assert_eq!(
        pixels.len(),
        rows as usize * cols as usize,
        "pixels.len() ({}) doesn't match dims ({rows}x{cols})",
        pixels.len()
    );

    // Negative WindowWidth would invert lower/upper and panic in f64::clamp.
    // Treat negative width as zero (degenerate but non-panicking) — malformed metadata happens.
    let effective_width = w.width.max(0.0);
    let lower = w.center - effective_width / 2.0;
    let upper = w.center + effective_width / 2.0;
    // .max(EPSILON) avoids divide-by-zero when effective_width is 0.
    let span = (upper - lower).max(f64::EPSILON);

    // Values are clamped to [0, 255] before the cast; truncation and sign loss are intentional.
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let bytes: Vec<u8> = pixels
        .iter()
        .map(|&v| {
            let hu = f64::from(v).mul_add(w.slope, w.intercept);
            let clamped = hu.clamp(lower, upper);
            let scaled = (clamped - lower) / span * 255.0;
            scaled.round() as u8
        })
        .collect();

    ImageBuffer::<Luma<u8>, _>::from_raw(cols, rows, bytes)
        .expect("dims/pixel-count invariant verified by assert above")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ws(center: f64, width: f64, slope: f64, intercept: f64) -> WindowSettings {
        WindowSettings {
            center,
            width,
            slope,
            intercept,
        }
    }

    #[test]
    fn maps_window_midpoint_to_128() {
        // center=128, width=256, slope=1, intercept=0 → window [0, 256], midpoint 128
        // (128-0)/256*255 = 127.5 → rounds to 128 (Rust's f64::round is half-away-from-zero, deterministic).
        let img = apply_window(&[128], (1, 1), ws(128.0, 256.0, 1.0, 0.0));
        assert_eq!(img.as_raw()[0], 128);
    }

    #[test]
    fn clamps_values_below_window_to_0() {
        let img = apply_window(&[-1000], (1, 1), ws(128.0, 256.0, 1.0, 0.0));
        assert_eq!(img.as_raw()[0], 0);
    }

    #[test]
    fn clamps_values_above_window_to_255() {
        let img = apply_window(&[10_000], (1, 1), ws(128.0, 256.0, 1.0, 0.0));
        assert_eq!(img.as_raw()[0], 255);
    }

    #[test]
    fn applies_rescale_slope_and_intercept_before_windowing() {
        // CT-style: stored=1024, slope=1, intercept=-1024 → HU=0
        // window center=40, width=400 → [-160, 240], 0 at (160/400)*255 = 102.0 (exact, rounds to 102).
        let img = apply_window(&[1024], (1, 1), ws(40.0, 400.0, 1.0, -1024.0));
        assert_eq!(img.as_raw()[0], 102);
    }

    #[test]
    fn produces_image_with_correct_dimensions() {
        // 2 rows × 3 cols = 6 pixels. image's dimensions() returns (width, height) = (cols, rows).
        let img = apply_window(
            &[0, 64, 128, 192, 255, 255],
            (2, 3),
            ws(128.0, 256.0, 1.0, 0.0),
        );
        assert_eq!(img.dimensions(), (3, 2));
        assert_eq!(img.as_raw().len(), 6);
    }

    #[test]
    fn handles_zero_width_without_dividing_by_zero() {
        // Degenerate: width=0 means lower==upper==center. (clamped - lower)/EPSILON*255 = 0.
        // All pixels map to 0; the function must not panic or produce NaN.
        let img = apply_window(&[100, 200, 300], (1, 3), ws(128.0, 0.0, 1.0, 0.0));
        assert_eq!(img.as_raw(), &[0, 0, 0]);
    }

    #[test]
    fn handles_negative_width_without_panic() {
        // Malformed metadata (DICOM PS3.3 requires width >= 1). Negative width
        // would invert clamp bounds and panic. Treat as zero-width (output = 0s).
        let img = apply_window(&[100, 200], (1, 2), ws(128.0, -10.0, 1.0, 0.0));
        assert_eq!(img.as_raw(), &[0, 0]);
    }
}
