mod common;

use std::fs;

use common::{DicomFixture, fresh_dir, write_synthetic};
use rustradstack::study::load_study;

#[test]
fn load_study_groups_by_series_instance_uid() {
    // Two interleaved series in ONE folder must split into two series,
    // each internally ordered by InstanceNumber.
    let dir = fresh_dir();
    let a2 = write_synthetic(
        dir.path(),
        "a2.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.1"),
            instance_number: Some(2),
            ..Default::default()
        },
    );
    let b1 = write_synthetic(
        dir.path(),
        "b1.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.2"),
            instance_number: Some(1),
            ..Default::default()
        },
    );
    let a1 = write_synthetic(
        dir.path(),
        "a1.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.1"),
            instance_number: Some(1),
            ..Default::default()
        },
    );
    let b2 = write_synthetic(
        dir.path(),
        "b2.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.2"),
            instance_number: Some(2),
            ..Default::default()
        },
    );

    let study = load_study(dir.path()).expect("load study");
    assert_eq!(study.series.len(), 2);
    let paths: Vec<_> = study.series.iter().map(|s| s.paths.clone()).collect();
    assert!(paths.contains(&vec![a1, a2]));
    assert!(paths.contains(&vec![b1, b2]));
}

#[test]
fn load_study_orders_series_by_series_number() {
    let dir = fresh_dir();
    write_synthetic(
        dir.path(),
        "z.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.9"),
            series_number: Some(2),
            series_description: Some("Sagittal"),
            ..Default::default()
        },
    );
    write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.5"),
            series_number: Some(1),
            series_description: Some("Axial"),
            ..Default::default()
        },
    );

    let study = load_study(dir.path()).expect("load study");
    let labels: Vec<_> = study.series.iter().map(|s| s.description.clone()).collect();
    assert_eq!(labels, vec!["Axial", "Sagittal"]);
    assert_eq!(study.series[0].number, Some(1));
}

#[test]
fn load_study_description_falls_back_to_series_number_then_folder() {
    let dir = fresh_dir();
    // No description, has number → "Series 3".
    write_synthetic(
        dir.path(),
        "n.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.7"),
            series_number: Some(3),
            ..Default::default()
        },
    );
    // No description, no number, no UID → folder-name fallback.
    let sub = dir.path().join("localizer");
    fs::create_dir(&sub).unwrap();
    write_synthetic(
        &sub,
        "u.dcm",
        DicomFixture {
            skip_instance_number: true,
            ..Default::default()
        },
    );

    let study = load_study(dir.path()).expect("load study");
    let labels: Vec<_> = study.series.iter().map(|s| s.description.clone()).collect();
    assert!(labels.contains(&"Series 3".to_owned()), "{labels:?}");
    assert!(labels.contains(&"localizer".to_owned()), "{labels:?}");
}

#[test]
fn load_study_sorts_within_series_by_instance_number_with_ipp_fallback() {
    // Ported from the removed sorting.rs tests: InstanceNumber ascending;
    // files without it fall back to ImagePositionPatient[2].
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
    let p_bot = write_synthetic(
        dir.path(),
        "bot.dcm",
        DicomFixture {
            skip_instance_number: true,
            image_position_patient: Some([0.0, 0.0, 0.0]),
            ..Default::default()
        },
    );

    let study = load_study(dir.path()).expect("load study");
    assert_eq!(study.series.len(), 1, "same folder, no UID → one series");
    assert_eq!(study.series[0].paths, vec![p_bot, p_top]);
}

#[test]
fn load_study_puts_files_with_no_sort_key_last_within_series() {
    let dir = fresh_dir();
    let no_keys = write_synthetic(
        dir.path(),
        "noinfo.dcm",
        DicomFixture {
            skip_instance_number: true,
            ..Default::default()
        },
    );
    let n1 = write_synthetic(
        dir.path(),
        "later.dcm",
        DicomFixture {
            instance_number: Some(1),
            ..Default::default()
        },
    );

    let study = load_study(dir.path()).expect("load study");
    assert_eq!(study.series.len(), 1);
    assert_eq!(study.series[0].paths, vec![n1, no_keys]);
}

#[test]
fn load_study_separates_non_dicom_by_folder_sorted_alphabetically() {
    let dir = fresh_dir();
    write_synthetic(
        dir.path(),
        "ct.dcm",
        DicomFixture {
            series_instance_uid: Some("1.2.3.4"),
            ..Default::default()
        },
    );
    let png_z = dir.path().join("zebra.png");
    fs::write(&png_z, b"placeholder").unwrap();
    let jpg_a = dir.path().join("apple.jpg");
    fs::write(&jpg_a, b"placeholder").unwrap();

    let study = load_study(dir.path()).expect("load study");
    assert_eq!(
        study.series.len(),
        2,
        "DICOMs and images in one folder are separate series"
    );
    let img_series = study
        .series
        .iter()
        .find(|s| s.paths.iter().any(|p| p.extension().unwrap() != "dcm"))
        .expect("image series present");
    assert_eq!(img_series.paths, vec![jpg_a, png_z]);
}

#[test]
fn load_study_single_file_becomes_one_series() {
    let dir = fresh_dir();
    let p = write_synthetic(dir.path(), "one.dcm", DicomFixture::default());
    let study = load_study(&p).expect("load single file");
    assert_eq!(study.series.len(), 1);
    assert_eq!(study.series[0].paths, vec![p]);
}

#[test]
fn series_center_path_is_middle_slice() {
    let dir = fresh_dir();
    let mut expected_center = None;
    for i in 1..=5 {
        let p = write_synthetic(
            dir.path(),
            &format!("s{i}.dcm"),
            DicomFixture {
                instance_number: Some(i),
                ..Default::default()
            },
        );
        if i == 3 {
            expected_center = Some(p);
        }
    }
    let study = load_study(dir.path()).expect("load study");
    assert_eq!(
        study.series[0].center_path(),
        expected_center.as_deref(),
        "center of 5 slices is index 2 (the 3rd)"
    );
}

#[test]
fn load_study_rejects_unsupported_file_and_missing_path() {
    let dir = fresh_dir();
    let txt = dir.path().join("notes.txt");
    fs::write(&txt, "not an image").unwrap();
    assert!(load_study(&txt).is_err());
    assert!(load_study(&dir.path().join("nope")).is_err());
}

#[test]
fn load_study_rejects_empty_folder() {
    let dir = fresh_dir();
    assert!(load_study(dir.path()).is_err());
}
