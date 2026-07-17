//! Manual performance smoke tests — excluded from normal runs.
//!
//! Run with:
//!   cargo test --release --test perf -- --ignored --nocapture

mod common;

use std::time::Instant;

use common::{DicomFixture, fresh_dir, write_synthetic};
use rustradstack::sorting::sort_files;

#[test]
#[ignore = "manual perf check; run with --ignored --nocapture"]
fn series_load_sort_timing() {
    let dir = fresh_dir();
    let n: usize = 200;
    let mut paths = Vec::new();
    for i in 0..n {
        // Descending InstanceNumber so the sort genuinely reorders.
        let instance = i32::try_from(n - i).expect("small n");
        paths.push(write_synthetic(
            dir.path(),
            &format!("slice_{i:03}.dcm"),
            DicomFixture {
                rows: Some(256),
                cols: Some(256),
                instance_number: Some(instance),
                ..Default::default()
            },
        ));
    }

    // Baseline: full-file parse (what sort_files did before read_until).
    let t0 = Instant::now();
    for p in &paths {
        let _ = dicom_object::open_file(p);
    }
    let full_parse = t0.elapsed();

    let t1 = Instant::now();
    let sorted = sort_files(paths.clone());
    let header_only = t1.elapsed();

    assert_eq!(sorted.len(), n);
    // Written first = highest InstanceNumber = must sort last.
    assert_eq!(sorted.last(), paths.first());
    println!(
        "{n} slices of 256x256 — full-parse baseline: {full_parse:?}; \
         sort_files with read_until: {header_only:?}"
    );
}
