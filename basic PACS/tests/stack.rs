mod common;

use common::{DicomFixture, fresh_dir, write_synthetic};
use rustradstack::stack::ImageStack;

#[test]
fn image_stack_reports_length_and_starts_at_index_0() {
    let dir = fresh_dir();
    let p1 = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            instance_number: Some(1),
            ..Default::default()
        },
    );
    let p2 = write_synthetic(
        dir.path(),
        "b.dcm",
        DicomFixture {
            instance_number: Some(2),
            ..Default::default()
        },
    );

    let stack = ImageStack::new(vec![p1, p2]);
    assert_eq!(stack.len(), 2);
    assert_eq!(stack.current(), 0);
    assert!(!stack.is_empty());
}

#[test]
fn image_stack_next_and_prev_clamp_at_bounds() {
    let dir = fresh_dir();
    let p1 = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            instance_number: Some(1),
            ..Default::default()
        },
    );
    let p2 = write_synthetic(
        dir.path(),
        "b.dcm",
        DicomFixture {
            instance_number: Some(2),
            ..Default::default()
        },
    );
    let p3 = write_synthetic(
        dir.path(),
        "c.dcm",
        DicomFixture {
            instance_number: Some(3),
            ..Default::default()
        },
    );

    let mut stack = ImageStack::new(vec![p1, p2, p3]);
    assert_eq!(stack.next(), 1);
    assert_eq!(stack.next(), 2);
    assert_eq!(stack.next(), 2, "should clamp at last index");
    assert_eq!(stack.prev(), 1);
    assert_eq!(stack.prev(), 0);
    assert_eq!(stack.prev(), 0, "should clamp at first index");
}

#[test]
fn image_stack_get_current_image_returns_correct_dimensions() {
    let dir = fresh_dir();
    let p1 = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            rows: Some(8),
            cols: Some(8),
            ..Default::default()
        },
    );
    let stack = ImageStack::new(vec![p1]);

    let img = stack.get_current_image().expect("get image");
    assert_eq!(img.dimensions(), (8, 8));
}

#[test]
fn image_stack_empty_reports_correctly() {
    let stack = ImageStack::new(vec![]);
    assert_eq!(stack.len(), 0);
    assert!(stack.is_empty());
}

#[test]
fn image_stack_override_window_round_trips() {
    let dir = fresh_dir();
    let p = write_synthetic(dir.path(), "a.dcm", DicomFixture::default());
    let mut stack = ImageStack::new(vec![p]);

    assert_eq!(stack.override_window(), None);

    stack.set_override_window(Some((100.0, 500.0)));
    assert_eq!(stack.override_window(), Some((100.0, 500.0)));

    stack.set_override_window(None);
    assert_eq!(stack.override_window(), None);
}

#[test]
fn image_stack_get_current_image_uses_override_when_set() {
    let dir = fresh_dir();
    // File W/L: center=128, width=256, slope=1, intercept=0 (defaults from DicomFixture)
    let p = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            window_center: Some(128.0),
            window_width: Some(256.0),
            rescale_slope: Some(1.0),
            rescale_intercept: Some(0.0),
            ..Default::default()
        },
    );
    let mut stack = ImageStack::new(vec![p]);

    let img_default = stack.get_current_image().expect("default render");

    // Tighten window to [60, 70] (center=65, width=10) — most ramp values clamp.
    stack.set_override_window(Some((65.0, 10.0)));
    let img_overridden = stack.get_current_image().expect("override render");

    let sum_default: u32 = img_default.as_raw().iter().map(|&b| u32::from(b)).sum();
    let sum_overridden: u32 = img_overridden.as_raw().iter().map(|&b| u32::from(b)).sum();
    assert_ne!(
        sum_default, sum_overridden,
        "override should produce visibly different pixels (default sum={sum_default}, overridden sum={sum_overridden})"
    );
}

#[test]
fn image_stack_renders_png_via_image_crate() {
    use image::{ImageBuffer, Luma};
    let dir = fresh_dir();
    // Values are 0-15, so cast to u8 is safe; allow rather than use try_from for readability.
    #[allow(clippy::cast_possible_truncation)]
    let buf: ImageBuffer<Luma<u8>, Vec<u8>> =
        ImageBuffer::from_fn(4, 4, |x, y| Luma([(y * 4 + x) as u8 * 16]));
    let png_path = dir.path().join("ramp.png");
    buf.save(&png_path).expect("save png");

    let stack = ImageStack::new(vec![png_path]);
    let img = stack.get_current_image().expect("decode png");
    assert_eq!(img.dimensions(), (4, 4));
    // Ramp pixel (2, 1) should be (1*4+2)*16 = 96
    assert_eq!(img.get_pixel(2, 1).0[0], 96);
}

#[test]
fn image_stack_applies_override_window_for_png() {
    use image::{ImageBuffer, Luma};
    let dir = fresh_dir();
    let buf: ImageBuffer<Luma<u8>, Vec<u8>> = ImageBuffer::from_fn(2, 2, |_, _| Luma([100]));
    let png_path = dir.path().join("flat.png");
    buf.save(&png_path).expect("save png");

    let mut stack = ImageStack::new(vec![png_path]);
    let img_no_override = stack.get_current_image().expect("decode");
    assert_eq!(img_no_override.as_raw()[0], 100);

    stack.set_override_window(Some((10.0, 5.0))); // clamps 100 to 12.5 -> 255
    let img_with_override = stack.get_current_image().expect("decode");
    assert_eq!(img_with_override.as_raw()[0], 255);
}

#[test]
fn image_stack_measurements_management() {
    let stack = ImageStack::new(vec![]);
    assert_eq!(stack.current_measurements().len(), 0);

    let dir = fresh_dir();
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture::default());
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture::default());
    let mut stack = ImageStack::new(vec![p1, p2]);

    assert_eq!(stack.current_measurements().len(), 0);

    let m1 = rustradstack::stack::Measurement::Line {
        start: (10.0, 10.0),
        end: (20.0, 20.0),
        label_pos: None,
    };
    let m2 = rustradstack::stack::Measurement::Circle {
        center: (15.0, 15.0),
        radius: 5.0,
        label_pos: None,
    };

    stack.add_measurement(m1.clone());
    stack.add_measurement(m2.clone());
    assert_eq!(stack.current_measurements(), &[m1.clone(), m2.clone()]);

    stack.next();
    assert_eq!(stack.current_measurements().len(), 0);

    stack.prev();
    assert_eq!(stack.current_measurements().len(), 2);

    stack.clear_current_measurements();
    assert_eq!(stack.current_measurements().len(), 0);

    stack.add_measurement(m1);
    stack.next();
    stack.add_measurement(m2);
    stack.clear_all_measurements();
    assert_eq!(stack.current_measurements().len(), 0);
    stack.prev();
    assert_eq!(stack.current_measurements().len(), 0);
}

#[test]
fn image_stack_remove_measurements() {
    let dir = fresh_dir();
    let p = write_synthetic(dir.path(), "a.dcm", DicomFixture::default());
    let mut stack = ImageStack::new(vec![p]);

    let m1 = rustradstack::stack::Measurement::Line {
        start: (10.0, 10.0),
        end: (20.0, 20.0),
        label_pos: None,
    };
    let m2 = rustradstack::stack::Measurement::Circle {
        center: (15.0, 15.0),
        radius: 5.0,
        label_pos: None,
    };
    let m3 = rustradstack::stack::Measurement::Orthogonal {
        start: (0.0, 0.0),
        end: (10.0, 0.0),
        ortho_start: (5.0, -5.0),
        ortho_end: (5.0, 5.0),
        label1_pos: None,
        label2_pos: None,
    };

    stack.add_measurement(m1.clone());
    stack.add_measurement(m2.clone());
    stack.add_measurement(m3.clone());

    assert_eq!(stack.current_measurements().len(), 3);

    let mut to_remove = std::collections::HashSet::new();
    to_remove.insert(1); // remove m2 (Circle)

    stack.remove_measurements(&to_remove);
    let cur = stack.current_measurements();
    assert_eq!(cur.len(), 2);
    assert_eq!(cur[0], m1);
    assert_eq!(cur[1], m3);

    // Try removing nothing
    stack.remove_measurements(&std::collections::HashSet::new());
    assert_eq!(stack.current_measurements().len(), 2);

    // Remove remaining
    let mut to_remove_all = std::collections::HashSet::new();
    to_remove_all.insert(0);
    to_remove_all.insert(1);
    stack.remove_measurements(&to_remove_all);
    assert_eq!(stack.current_measurements().len(), 0);
}

#[test]
fn image_stack_spacing_parsing() {
    let dir = fresh_dir();

    // 1. Pixel spacing tag present
    let p_sp = write_synthetic(
        dir.path(),
        "spacing.dcm",
        DicomFixture {
            pixel_spacing: Some((1.5, 0.8)),
            ..Default::default()
        },
    );
    let stack_sp = ImageStack::new(vec![p_sp]);
    assert_eq!(stack_sp.current_spacing(), Some((1.5, 0.8)));

    // 2. Imager pixel spacing fallback tag present
    let p_isp = write_synthetic(
        dir.path(),
        "imager_spacing.dcm",
        DicomFixture {
            imager_pixel_spacing: Some((2.0, 2.5)),
            ..Default::default()
        },
    );
    let stack_isp = ImageStack::new(vec![p_isp]);
    assert_eq!(stack_isp.current_spacing(), Some((2.0, 2.5)));

    // 3. No spacing tags present
    let p_none = write_synthetic(dir.path(), "no_spacing.dcm", DicomFixture::default());
    let stack_none = ImageStack::new(vec![p_none]);
    assert_eq!(stack_none.current_spacing(), None);

    // 4. Non-DICOM (PNG)
    use image::{ImageBuffer, Luma};
    let buf: ImageBuffer<Luma<u8>, Vec<u8>> = ImageBuffer::from_fn(2, 2, |_, _| Luma([100]));
    let png_path = dir.path().join("flat.png");
    buf.save(&png_path).expect("save png");
    let stack_png = ImageStack::new(vec![png_path]);
    assert_eq!(stack_png.current_spacing(), None);
}

#[test]
fn image_stack_roi_stats_dicom() {
    let dir = fresh_dir();

    // We create a 4x4 image with raw pixel values (pre-rescale):
    // [ 0,  1,  2,  3]
    // [ 4,  5,  6,  7]
    // [ 8,  9, 10, 11]
    // [12, 13, 14, 15]
    //
    // Rescale slope: 2.0, intercept: -1000.0
    // Scaled HU values:
    // [ -1000,  -998,  -996,  -994 ]
    // [  -992,  -990,  -988,  -986 ]
    // ...
    //
    // Let's place a Circle ROI centered at (1.5, 1.5) with radius 1.0.
    // Point distances from (1.5, 1.5):
    // (x - 1.5)^2 + (y - 1.5)^2 <= 1.0
    // Test points:
    // (1, 1): (1-1.5)^2 + (1-1.5)^2 = 0.25 + 0.25 = 0.5 <= 1.0 (Included, raw 5 -> HU: -990.0)
    // (2, 1): (2-1.5)^2 + (1-1.5)^2 = 0.25 + 0.25 = 0.5 <= 1.0 (Included, raw 6 -> HU: -988.0)
    // (1, 2): (1-1.5)^2 + (2-1.5)^2 = 0.25 + 0.25 = 0.5 <= 1.0 (Included, raw 9 -> HU: -982.0)
    // (2, 2): (2-1.5)^2 + (2-1.5)^2 = 0.25 + 0.25 = 0.5 <= 1.0 (Included, raw 10 -> HU: -980.0)
    //
    // 4 pixels are inside.
    // Area with spacing (1.2, 0.5):
    // count * row_sp * col_sp = 4 * 1.2 * 0.5 = 2.4 mm^2.
    // Min = -990.0
    // Max = -980.0
    // Mean = (-990 - 988 - 982 - 980) / 4 = -985.0
    // Count = 4

    let p = write_synthetic(
        dir.path(),
        "stats.dcm",
        DicomFixture {
            rows: Some(4),
            cols: Some(4),
            rescale_slope: Some(2.0),
            rescale_intercept: Some(-1000.0),
            pixel_spacing: Some((1.2, 0.5)),
            ..Default::default()
        },
    );
    let stack = ImageStack::new(vec![p]);

    let stats = stack.get_roi_stats((1.5, 1.5), 1.0).expect("get_roi_stats");
    assert_eq!(stats.count, 4);
    assert_eq!(stats.min, -990.0);
    assert_eq!(stats.max, -980.0);
    assert_eq!(stats.mean, -985.0);
    assert_eq!(stats.area, 2.4);

    assert!(stack.get_roi_stats((-10.0, -10.0), 1.0).is_none());
}

#[test]
fn image_stack_roi_stats_nondicom() {
    use image::{ImageBuffer, Luma};
    let dir = fresh_dir();

    // 4x4 PNG image:
    // Values:
    // [ 10,  20,  30,  40]
    // [ 50,  60,  70,  80]
    // [ 90, 100, 110, 120]
    // [130, 140, 150, 160]
    let buf: ImageBuffer<Luma<u8>, Vec<u8>> =
        ImageBuffer::from_fn(4, 4, |x, y| Luma([(y * 4 + x) as u8 * 10 + 10]));
    let png_path = dir.path().join("ramp.png");
    buf.save(&png_path).expect("save png");

    let stack = ImageStack::new(vec![png_path]);

    // Circle centered at (1.5, 1.5) with radius 1.0
    // Pixels: (1,1) -> 60, (2,1) -> 70, (1,2) -> 100, (2,2) -> 110
    // Min = 60.0
    // Max = 110.0
    // Mean = 85.0
    // Count = 4
    // Area = 4.0

    let stats = stack.get_roi_stats((1.5, 1.5), 1.0).expect("get_roi_stats");
    assert_eq!(stats.count, 4);
    assert_eq!(stats.min, 60.0);
    assert_eq!(stats.max, 110.0);
    assert_eq!(stats.mean, 85.0);
    assert_eq!(stats.area, 4.0);

    assert!(stack.get_roi_stats((10.0, 10.0), 1.0).is_none());
}
