mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::windowing::{extract_pixels, WindowSettings};

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

    let (pixels, dims, ws) = extract_pixels(&path).expect("extract");

    assert_eq!(dims, (4, 4));
    assert_eq!(pixels.len(), 16);
    // Default ramp is 0..16 stored values.
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
