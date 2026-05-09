//! DICOM window/level math and pixel extraction.

use std::path::Path;

use dicom_dictionary_std::tags;
use dicom_object::{open_file, DefaultDicomObject, Tag};
use dicom_pixeldata::{ConvertOptions, ModalityLutOption, PixelDecoder};

use crate::errors::RrsError;

/// Window/Level + rescale parameters needed to convert stored pixel values
/// to a displayable 8-bit image.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WindowSettings {
    pub center: f64,
    pub width: f64,
    pub slope: f64,
    pub intercept: f64,
}

impl Default for WindowSettings {
    fn default() -> Self {
        Self {
            center: 128.0,
            width: 256.0,
            slope: 1.0,
            intercept: 0.0,
        }
    }
}

/// Read a DICOM file and return (stored pixel values as i32, (rows, cols), window settings).
///
/// Stored values are pre-rescale — call sites apply slope/intercept inside `apply_window`.
/// Returns an error if the file can't be parsed or pixel decoding fails.
pub fn extract_pixels(
    path: &Path,
) -> Result<(Vec<i32>, (u32, u32), WindowSettings), RrsError> {
    let obj = open_file(path).map_err(|e| RrsError::Dicom(e.to_string()))?;

    let rows = read_u32(&obj, tags::ROWS, "Rows")?;
    let cols = read_u32(&obj, tags::COLUMNS, "Columns")?;

    let center = read_f64_or_default(&obj, tags::WINDOW_CENTER, 128.0);
    let width = read_f64_or_default(&obj, tags::WINDOW_WIDTH, 256.0);
    let slope = read_f64_or_default(&obj, tags::RESCALE_SLOPE, 1.0);
    let intercept = read_f64_or_default(&obj, tags::RESCALE_INTERCEPT, 0.0);

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

    Ok((
        frame,
        (rows, cols),
        WindowSettings { center, width, slope, intercept },
    ))
}

/// Extract a u32 value from a DICOM element by tag, returning an error if absent.
fn read_u32(obj: &DefaultDicomObject, tag: Tag, name: &'static str) -> Result<u32, RrsError> {
    let elt = obj.element(tag).map_err(|_| RrsError::MissingTag(name))?;
    elt.to_int::<u32>()
        .map_err(|e| RrsError::Dicom(format!("{name}: {e}")))
}

/// Read an f64 DICOM attribute, returning `default` if the tag is absent or unparseable.
fn read_f64_or_default(obj: &DefaultDicomObject, tag: Tag, default: f64) -> f64 {
    obj.element(tag)
        .ok()
        .and_then(|e| e.to_float64().ok())
        .unwrap_or(default)
}
