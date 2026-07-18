//! Manual performance smoke tests — excluded from normal runs.
//!
//! Run with:
//!   cargo test --release --test perf -- --ignored --nocapture

mod common;

use std::time::Instant;

use common::{DicomFixture, fresh_dir, write_synthetic};
use rustradstack::study::load_study;

#[test]
#[ignore = "manual perf check; run with --ignored --nocapture"]
fn study_load_timing() {
    let dir = fresh_dir();
    let n: usize = 200;
    let series_count = 4;
    let mut paths = Vec::new();
    for i in 0..n {
        // Descending InstanceNumber so the sort genuinely reorders; spread
        // across several series so grouping is exercised too.
        let instance = i32::try_from(n - i).expect("small n");
        let uid: &'static str = ["1.2.3.1", "1.2.3.2", "1.2.3.3", "1.2.3.4"][i % series_count];
        paths.push(write_synthetic(
            dir.path(),
            &format!("slice_{i:03}.dcm"),
            DicomFixture {
                rows: Some(256),
                cols: Some(256),
                instance_number: Some(instance),
                series_instance_uid: Some(uid),
                ..Default::default()
            },
        ));
    }

    // Baseline: full-file parse (what loading did before read_until).
    let t0 = Instant::now();
    for p in &paths {
        let _ = dicom_object::open_file(p);
    }
    let full_parse = t0.elapsed();

    let t1 = Instant::now();
    let study = load_study(dir.path()).expect("load study");
    let header_only = t1.elapsed();

    assert_eq!(study.series.len(), series_count);
    assert_eq!(study.series.iter().map(|s| s.paths.len()).sum::<usize>(), n);
    println!(
        "{n} slices of 256x256 across {series_count} series — full-parse baseline: \
         {full_parse:?}; load_study (scan + group + sort, header-only): {header_only:?}"
    );
}
