mod common;

use std::process::Command;

use common::{DicomFixture, fresh_dir, write_synthetic};

#[test]
fn cli_info_prints_expected_fields() {
    let dir = fresh_dir();
    let path = write_synthetic(
        dir.path(),
        "case.dcm",
        DicomFixture {
            patient_name: Some("Smith^John"),
            modality: Some("CT"),
            instance_number: Some(3),
            window_center: Some(40.0),
            window_width: Some(400.0),
            ..Default::default()
        },
    );

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["info"])
        .arg(&path)
        .output()
        .expect("run rrs-cli");
    assert!(
        out.status.success(),
        "rrs-cli failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    let stdout = String::from_utf8(out.stdout).unwrap();
    // Labels are padded to 18 columns; expect at least one space between label and value.
    assert!(
        stdout.contains("PatientName:      Smith^John"),
        "stdout: {stdout}"
    );
    assert!(stdout.contains("Modality:         CT"), "stdout: {stdout}");
    assert!(stdout.contains("InstanceNumber:   3"), "stdout: {stdout}");
    assert!(
        stdout.contains("Rows x Cols:      4 x 4"),
        "stdout: {stdout}"
    );
    assert!(stdout.contains("WindowCenter:     40"), "stdout: {stdout}");
    assert!(stdout.contains("WindowWidth:      400"), "stdout: {stdout}");
    assert!(stdout.contains("RescaleSlope:     1"), "stdout: {stdout}");
    assert!(
        stdout.contains("RescaleIntercept: -1024"),
        "stdout: {stdout}"
    );
}
