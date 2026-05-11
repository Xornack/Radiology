mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::stack::ImageStack;

#[test]
fn image_stack_reports_length_and_starts_at_index_0() {
    let dir = fresh_dir();
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let stack = ImageStack::new(vec![p1, p2]);
    assert_eq!(stack.len(), 2);
    assert_eq!(stack.current(), 0);
    assert!(!stack.is_empty());
}

#[test]
fn image_stack_next_and_prev_clamp_at_bounds() {
    let dir = fresh_dir();
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });
    let p3 = write_synthetic(dir.path(), "c.dcm", DicomFixture { instance_number: Some(3), ..Default::default() });

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
        DicomFixture { rows: Some(8), cols: Some(8), ..Default::default() },
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
