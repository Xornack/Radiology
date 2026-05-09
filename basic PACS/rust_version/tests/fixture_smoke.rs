mod common;

use common::{fresh_dir, write_synthetic, DicomFixture};
use dicom_dictionary_std::tags;
use dicom_object::open_file;

#[test]
fn synthetic_fixture_roundtrips_through_dicom_rs() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "smoke.dcm",
        DicomFixture {
            patient_name: Some("Smoke^Test"),
            modality: Some("MR"),
            instance_number: Some(7),
            ..Default::default()
        },
    );

    let obj = open_file(&path).expect("read synthetic DICOM");
    let name = obj
        .element(tags::PATIENT_NAME)
        .unwrap()
        .to_str()
        .unwrap()
        .into_owned();
    assert_eq!(name, "Smoke^Test");

    let modality = obj
        .element(tags::MODALITY)
        .unwrap()
        .to_str()
        .unwrap()
        .into_owned();
    assert_eq!(modality, "MR");

    let instance: i32 = obj
        .element(tags::INSTANCE_NUMBER)
        .unwrap()
        .to_int()
        .unwrap();
    assert_eq!(instance, 7);
}
