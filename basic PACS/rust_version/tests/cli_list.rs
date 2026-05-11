mod common;

use std::process::Command;

use common::{fresh_dir, write_synthetic, DicomFixture};

#[test]
fn cli_list_prints_files_in_instance_order() {
    let dir = fresh_dir();
    write_synthetic(dir.path(), "c.dcm", DicomFixture { instance_number: Some(3), ..Default::default() });
    write_synthetic(dir.path(), "a.dcm", DicomFixture { instance_number: Some(1), ..Default::default() });
    write_synthetic(dir.path(), "b.dcm", DicomFixture { instance_number: Some(2), ..Default::default() });

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["list"])
        .arg(dir.path())
        .output()
        .expect("run rrs-cli");

    assert!(out.status.success(), "rrs-cli list failed: {}", String::from_utf8_lossy(&out.stderr));

    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(stdout.contains("3 DICOM(s)"), "header missing in: {stdout}");

    // Verify ordering: a.dcm appears before b.dcm appears before c.dcm in stdout.
    let idx_a = stdout.find("a.dcm").expect("a.dcm in output");
    let idx_b = stdout.find("b.dcm").expect("b.dcm in output");
    let idx_c = stdout.find("c.dcm").expect("c.dcm in output");
    assert!(idx_a < idx_b && idx_b < idx_c, "expected a < b < c, got positions {idx_a}, {idx_b}, {idx_c}");
}

#[test]
fn cli_list_handles_empty_folder() {
    let dir = fresh_dir();
    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin).args(["list"]).arg(dir.path()).output().expect("run");
    assert!(out.status.success());
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(stdout.contains("0 DICOM(s)"), "expected empty count: {stdout}");
}
