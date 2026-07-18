//! Generates a synthetic multi-series demo study for manual GUI testing.
//!
//! Run with:
//!   cargo test --test gen_demo -- --ignored --nocapture
//!
//! Writes to %TEMP%\rrs_demo_study and prints the path.

mod common;

use common::{DicomFixture, write_synthetic};

#[test]
#[ignore = "writes a demo study to %TEMP% for manual GUI testing"]
fn generate_demo_study() {
    let dir = std::env::temp_dir().join("rrs_demo_study");
    if dir.exists() {
        std::fs::remove_dir_all(&dir).expect("clear old demo");
    }
    std::fs::create_dir_all(&dir).expect("create demo dir");

    let size: u16 = 64;
    let n_slices = 12;
    /// (x, y, image size) → stored pixel value.
    type PixelFn = fn(u16, u16, u16) -> u16;
    // Four visually distinct series: different gradients + W/L.
    let series: [(&str, &str, i32, PixelFn); 4] = [
        ("1.9.1", "Axial Ramp H", 1, |x, _y, _s| x * 16),
        ("1.9.2", "Axial Ramp V", 2, |_x, y, _s| y * 16),
        ("1.9.3", "Diagonal", 3, |x, y, _s| (x + y) * 8),
        ("1.9.4", "Rings", 4, |x, y, s| {
            let cx = f64::from(x) - f64::from(s) / 2.0;
            let cy = f64::from(y) - f64::from(s) / 2.0;
            // Wrap is fine — it's what makes the rings.
            #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
            let v = ((cx * cx + cy * cy).sqrt() * 24.0) as u16;
            v
        }),
    ];

    for (uid, desc, num, pixel_fn) in series {
        for slice in 1..=n_slices {
            let pixels: Vec<u16> = (0..size)
                .flat_map(|y| (0..size).map(move |x| (x, y)))
                .map(|(x, y)| pixel_fn(x, y, size).wrapping_add(u16::from(slice as u8) * 8))
                .collect();
            write_synthetic(
                &dir,
                &format!("{uid}.{slice:02}.dcm"),
                DicomFixture {
                    rows: Some(size),
                    cols: Some(size),
                    pixels: Some(pixels),
                    instance_number: Some(slice),
                    series_instance_uid: Some(uid),
                    series_description: Some(desc),
                    series_number: Some(num),
                    window_center: Some(512.0),
                    window_width: Some(1024.0),
                    rescale_slope: Some(1.0),
                    rescale_intercept: Some(0.0),
                    pixel_spacing: Some((0.7, 0.7)),
                    ..Default::default()
                },
            );
        }
    }
    println!("demo study at {}", dir.display());
}
