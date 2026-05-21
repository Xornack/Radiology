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
