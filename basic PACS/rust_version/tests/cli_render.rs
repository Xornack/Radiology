mod common;

use std::process::Command;

use common::{fresh_dir, write_synthetic, DicomFixture};
use image::GenericImageView;

#[test]
fn cli_render_writes_a_png_with_correct_dimensions() {
    let dir = fresh_dir();
    let dcm = write_synthetic(
        dir.path(),
        "case.dcm",
        DicomFixture {
            rows: Some(8),
            cols: Some(8),
            window_center: Some(40.0),
            window_width: Some(400.0),
            ..Default::default()
        },
    );
    let png = dir.path().join("out.png");

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["render"])
        .arg(&dcm)
        .arg(&png)
        .output()
        .expect("run rrs-cli");
    assert!(
        out.status.success(),
        "rrs-cli render failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    assert!(png.exists(), "PNG was not written");

    let img = image::open(&png).expect("decode written PNG");
    assert_eq!(img.dimensions(), (8, 8), "PNG dimensions don't match input");
}

#[test]
fn cli_render_errors_when_output_dir_missing() {
    let dir = fresh_dir();
    let dcm = write_synthetic(dir.path(), "case.dcm", DicomFixture::default());
    let bad_output = dir.path().join("does/not/exist/out.png");

    let bin = env!("CARGO_BIN_EXE_rrs-cli");
    let out = Command::new(bin)
        .args(["render"])
        .arg(&dcm)
        .arg(&bad_output)
        .output()
        .expect("run rrs-cli");

    assert!(!out.status.success(), "expected non-zero exit on bad output path");
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("writing") || stderr.contains("does") || stderr.contains("not"),
        "stderr should mention the failed write; got: {stderr}"
    );
}
