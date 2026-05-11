mod common;

use std::fs;

use common::{fresh_dir, write_synthetic, DicomFixture};
use rustradstack::loader::scan_directory;

#[test]
fn scan_directory_returns_dcm_files_in_alphabetical_order() {
    let dir = fresh_dir();
    let p2 = write_synthetic(dir.path(), "b.dcm", DicomFixture::default());
    let p1 = write_synthetic(dir.path(), "a.dcm", DicomFixture::default());
    let p3 = write_synthetic(dir.path(), "c.dcm", DicomFixture::default());

    let found = scan_directory(dir.path()).expect("scan");
    assert_eq!(found, vec![p1, p2, p3]);
}

#[test]
fn scan_directory_filters_non_dcm_files() {
    let dir = fresh_dir();
    let dcm = write_synthetic(dir.path(), "image.dcm", DicomFixture::default());
    fs::write(dir.path().join("notes.txt"), "ignore me").unwrap();
    fs::write(dir.path().join("README"), "no extension").unwrap();

    let found = scan_directory(dir.path()).expect("scan");
    assert_eq!(found, vec![dcm]);
}

#[test]
fn scan_directory_recurses_into_subdirectories() {
    let dir = fresh_dir();
    let sub = dir.path().join("sub");
    fs::create_dir(&sub).unwrap();
    let nested = write_synthetic(&sub, "nested.dcm", DicomFixture::default());
    let top = write_synthetic(dir.path(), "top.dcm", DicomFixture::default());

    let found = scan_directory(dir.path()).expect("scan");
    assert!(found.contains(&nested));
    assert!(found.contains(&top));
    assert_eq!(found.len(), 2);
}

#[test]
fn scan_directory_returns_empty_for_empty_dir() {
    let dir = fresh_dir();
    let found = scan_directory(dir.path()).expect("scan");
    assert!(found.is_empty());
}
