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
