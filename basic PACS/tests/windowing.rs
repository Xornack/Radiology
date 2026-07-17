mod common;

use common::{DicomFixture, fresh_dir, write_synthetic};
use dicom_object::open_file;
use rustradstack::windowing::{WindowSettings, extract_pixels, read_metadata};

#[test]
fn read_metadata_returns_dims_and_window_settings_without_decoding_pixels() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "ct.dcm",
        DicomFixture {
            rows: Some(4),
            cols: Some(4),
            window_center: Some(40.0),
            window_width: Some(400.0),
            rescale_slope: Some(1.0),
            rescale_intercept: Some(-1024.0),
            ..Default::default()
        },
    );

    let obj = open_file(&path).expect("open");
    let (dims, ws) = read_metadata(&obj).expect("read metadata");
    assert_eq!(dims, (4, 4));
    assert_eq!(
        ws,
        WindowSettings {
            center: 40.0,
            width: 400.0,
            slope: 1.0,
            intercept: -1024.0
        }
    );
}

#[test]
// Ported from the removed rrs-cli render test: the full open → decode →
// window → save pipeline must produce a single-channel 8-bit PNG.
fn windowed_image_saves_as_grayscale_png() {
    use image::GenericImageView;
    use rustradstack::windowing::apply_window;

    let dir = fresh_dir();
    let dcm = write_synthetic(
        dir.path(),
        "case.dcm",
        DicomFixture {
            rows: Some(8),
            cols: Some(8),
            window_center: Some(40.0),
            window_width: Some(400.0),
            ..Default::default()
        },
    );

    let obj = open_file(&dcm).expect("open");
    let (pixels, dims, ws) = extract_pixels(&obj).expect("extract");
    let png = dir.path().join("out.png");
    apply_window(&pixels, dims, ws).save(&png).expect("save");

    let img = image::open(&png).expect("decode written PNG");
    assert_eq!(img.dimensions(), (8, 8));
    assert_eq!(
        img.color(),
        image::ColorType::L8,
        "PNG should be 8-bit grayscale, not RGB(A)"
    );
}

#[test]
fn read_metadata_rejects_zero_dimensions() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "degenerate.dcm",
        DicomFixture {
            rows: Some(0),
            cols: Some(0),
            pixels: Some(vec![]),
            ..Default::default()
        },
    );

    let obj = open_file(&path).expect("open");
    assert!(
        read_metadata(&obj).is_err(),
        "0x0 dimensions must be rejected, not passed to the decoder"
    );
}

#[test]
fn extract_pixels_returns_dims_and_window_settings() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "ct.dcm",
        DicomFixture {
            rows: Some(4),
            cols: Some(4),
            window_center: Some(40.0),
            window_width: Some(400.0),
            rescale_slope: Some(1.0),
            rescale_intercept: Some(-1024.0),
            ..Default::default()
        },
    );

    let obj = open_file(&path).expect("open");
    let (pixels, dims, ws) = extract_pixels(&obj).expect("extract");

    assert_eq!(dims, (4, 4));
    assert_eq!(pixels.len(), 16);
    assert_eq!(pixels[0], 0);
    assert_eq!(pixels[15], 15);
    assert_eq!(
        ws,
        WindowSettings {
            center: 40.0,
            width: 400.0,
            slope: 1.0,
            intercept: -1024.0,
        }
    );
}
