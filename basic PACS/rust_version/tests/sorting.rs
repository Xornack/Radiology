mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::sorting::sort_files;

#[test]
fn sort_files_orders_by_instance_number_ascending() {
    let dir = fresh_dir();
    let p3 = write_synthetic(dir.path(), "c.dcm", DicomFixture { instance_number: Some(3), ..Default::default() });
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let sorted = sort_files(vec![p3.clone(), p1.clone(), p2.clone()]);
    assert_eq!(sorted, vec![p1, p2, p3]);
}

#[test]
fn sort_files_falls_back_to_image_position_patient_z() {
    let dir = fresh_dir();
    let p_top = write_synthetic(
        dir.path(),
        "top.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 100.0]),
            ..Default::default()
        },
    );
    let p_mid = write_synthetic(
        dir.path(),
        "mid.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 50.0]),
            ..Default::default()
        },
    );
    let p_bot = write_synthetic(
        dir.path(),
        "bot.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 0.0]),
            ..Default::default()
        },
    );

    let sorted = sort_files(vec![p_top.clone(), p_mid.clone(), p_bot.clone()]);
    assert_eq!(sorted, vec![p_bot, p_mid, p_top]);
}

#[test]
fn sort_files_puts_files_with_no_sort_key_at_the_end() {
    let dir = fresh_dir();
    let no_keys = write_synthetic(
        dir.path(),
        "noinfo.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: None,
            ..Default::default()
        },
    );
    let n1 = write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let n2 = write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let sorted = sort_files(vec![no_keys.clone(), n2.clone(), n1.clone()]);
    assert_eq!(sorted, vec![n1, n2, no_keys]);
}

#[test]
fn sort_files_handles_empty_input() {
    assert!(sort_files(vec![]).is_empty());
}

use std::fs;

#[test]
fn sort_files_puts_non_dicom_files_after_dicoms_in_alphabetical_order() {
    let dir = fresh_dir();
    let d1 = write_synthetic(dir.path(), "ct1.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    let d2 = write_synthetic(dir.path(), "ct2.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });
    let png = dir.path().join("zebra.png");
    fs::write(&png, b"placeholder").unwrap();
    let jpg = dir.path().join("apple.jpg");
    fs::write(&jpg, b"placeholder").unwrap();

    let sorted = sort_files(vec![png.clone(), d2.clone(), jpg.clone(), d1.clone()]);
    assert_eq!(sorted, vec![d1, d2, jpg, png]);
}
