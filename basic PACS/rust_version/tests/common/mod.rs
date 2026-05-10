//! Synthetic DICOM builders used by integration tests.

use std::path::{Path, PathBuf};
use tempfile::TempDir;

use dicom_core::dicom_value;
use dicom_core::value::PrimitiveValue;
use dicom_core::{DataElement, VR};
use dicom_dictionary_std::tags;
use dicom_object::{FileMetaTableBuilder, InMemDicomObject};

/// Parameters for a synthetic DICOM file. All fields are optional;
/// sensible defaults are used when omitted.
#[derive(Default)]
pub struct DicomFixture {
    pub patient_name: Option<&'static str>,
    pub modality: Option<&'static str>,
    pub rows: Option<u16>,
    pub cols: Option<u16>,
    pub instance_number: Option<i32>,
    pub window_center: Option<f64>,
    pub window_width: Option<f64>,
    pub rescale_slope: Option<f64>,
    pub rescale_intercept: Option<f64>,
    /// Stored pixel values (raw, pre-rescale). Length must be rows*cols.
    /// If None, a flat ramp from 0..(rows*cols) is generated.
    pub pixels: Option<Vec<u16>>,
}

/// Write a synthetic DICOM into the given temp dir; returns the resulting path.
pub fn write_synthetic(dir: &Path, name: &str, fx: DicomFixture) -> PathBuf {
    let rows = fx.rows.unwrap_or(4);
    let cols = fx.cols.unwrap_or(4);
    // Default ramp wraps modulo 2^16. Only meaningful for rows*cols <= 65535;
    // pass an explicit `pixels` Vec for larger images where pixel values matter.
    #[allow(clippy::cast_possible_truncation)] // intentional wrap: ramp is test-only, docs above
    let pixels = fx
        .pixels
        .unwrap_or_else(|| (0..(u32::from(rows) * u32::from(cols))).map(|v| v as u16).collect());
    assert_eq!(pixels.len(), rows as usize * cols as usize);

    let mut obj = InMemDicomObject::new_empty();

    // Required identifying / display tags
    obj.put(DataElement::new(
        tags::PATIENT_NAME,
        VR::PN,
        PrimitiveValue::from(fx.patient_name.unwrap_or("Test^Patient")),
    ));
    obj.put(DataElement::new(
        tags::MODALITY,
        VR::CS,
        PrimitiveValue::from(fx.modality.unwrap_or("CT")),
    ));
    obj.put(DataElement::new(
        tags::INSTANCE_NUMBER,
        VR::IS,
        PrimitiveValue::from(fx.instance_number.unwrap_or(1).to_string()),
    ));

    // Image-pixel-module tags
    obj.put(DataElement::new(tags::ROWS, VR::US, dicom_value!(U16, rows)));
    obj.put(DataElement::new(tags::COLUMNS, VR::US, dicom_value!(U16, cols)));
    obj.put(DataElement::new(tags::BITS_ALLOCATED, VR::US, dicom_value!(U16, 16)));
    obj.put(DataElement::new(tags::BITS_STORED, VR::US, dicom_value!(U16, 16)));
    obj.put(DataElement::new(tags::HIGH_BIT, VR::US, dicom_value!(U16, 15)));
    obj.put(DataElement::new(tags::PIXEL_REPRESENTATION, VR::US, dicom_value!(U16, 0)));
    obj.put(DataElement::new(tags::SAMPLES_PER_PIXEL, VR::US, dicom_value!(U16, 1)));
    obj.put(DataElement::new(
        tags::PHOTOMETRIC_INTERPRETATION,
        VR::CS,
        PrimitiveValue::from("MONOCHROME2"),
    ));

    // W/L + rescale
    obj.put(DataElement::new(
        tags::WINDOW_CENTER,
        VR::DS,
        PrimitiveValue::from(fx.window_center.unwrap_or(40.0).to_string()),
    ));
    obj.put(DataElement::new(
        tags::WINDOW_WIDTH,
        VR::DS,
        PrimitiveValue::from(fx.window_width.unwrap_or(400.0).to_string()),
    ));
    obj.put(DataElement::new(
        tags::RESCALE_SLOPE,
        VR::DS,
        PrimitiveValue::from(fx.rescale_slope.unwrap_or(1.0).to_string()),
    ));
    obj.put(DataElement::new(
        tags::RESCALE_INTERCEPT,
        VR::DS,
        PrimitiveValue::from(fx.rescale_intercept.unwrap_or(-1024.0).to_string()),
    ));

    // Pixel data (Explicit VR Little Endian, uncompressed, 16-bit unsigned)
    let pixel_bytes: Vec<u8> = pixels.iter().flat_map(|p| p.to_le_bytes()).collect();
    obj.put(DataElement::new(
        tags::PIXEL_DATA,
        VR::OW,
        PrimitiveValue::from(pixel_bytes),
    ));

    // Build file meta with Explicit VR Little Endian transfer syntax.
    // dicom-object 0.9.1: with_meta takes the builder, not a pre-built meta object.
    let path = dir.join(name);
    let file_obj = obj
        .with_meta(
            FileMetaTableBuilder::new()
                .transfer_syntax("1.2.840.10008.1.2.1") // Explicit VR Little Endian
                .media_storage_sop_class_uid("1.2.840.10008.5.1.4.1.1.2") // CT Image Storage
                .media_storage_sop_instance_uid("1.2.3.4.5.6.7.8.9.0"),
        )
        .expect("build file meta");

    file_obj.write_to_file(&path).expect("write synthetic DICOM");
    path
}

/// Convenience: a fresh `TempDir` so individual tests don't have to manage it.
pub fn fresh_dir() -> TempDir {
    tempfile::tempdir().expect("create tempdir")
}
