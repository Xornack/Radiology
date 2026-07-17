mod common;

use std::fs;

use common::{DicomFixture, fresh_dir, write_synthetic};
use rustradstack::loading::paths_for;

#[test]
fn paths_for_folder_with_direct_images_ignores_subfolders() {
    // A series folder must not swallow a sibling/nested series into one stack.
    let dir = fresh_dir();
    let direct1 = write_synthetic(
        dir.path(),
        "a.dcm",
        DicomFixture {
            instance_number: Some(1),
            ..Default::default()
        },
    );
    let direct2 = write_synthetic(
        dir.path(),
        "b.dcm",
        DicomFixture {
            instance_number: Some(2),
            ..Default::default()
        },
    );
    let sub = dir.path().join("other_series");
    fs::create_dir(&sub).unwrap();
    write_synthetic(
        &sub,
        "nested.dcm",
        DicomFixture {
            instance_number: Some(1),
            ..Default::default()
        },
    );

    let paths = paths_for(dir.path()).expect("load series folder");
    assert_eq!(paths, vec![direct1, direct2]);
}

#[test]
fn paths_for_folder_without_direct_images_recurses() {
    // A study root with one folder per series still opens (recursive fallback).
    let dir = fresh_dir();
    let sub = dir.path().join("series1");
    fs::create_dir(&sub).unwrap();
    let nested = write_synthetic(&sub, "nested.dcm", DicomFixture::default());

    let paths = paths_for(dir.path()).expect("load study root");
    assert_eq!(paths, vec![nested]);
}

#[test]
fn paths_for_single_supported_file() {
    let dir = fresh_dir();
    let p = write_synthetic(dir.path(), "one.dcm", DicomFixture::default());
    let paths = paths_for(&p).expect("load single file");
    assert_eq!(paths, vec![p]);
}

#[test]
fn paths_for_rejects_unsupported_file() {
    let dir = fresh_dir();
    let txt = dir.path().join("notes.txt");
    fs::write(&txt, "not an image").unwrap();
    assert!(paths_for(&txt).is_err());
}

#[test]
fn paths_for_rejects_missing_path() {
    let dir = fresh_dir();
    assert!(paths_for(&dir.path().join("does_not_exist")).is_err());
}
