//! Smoke test for the public `presets` module.

use rustradstack::presets::{PRESETS, WindowPreset};

#[test]
fn lung_preset_is_negative_600_over_1500() {
    let lung: &WindowPreset = PRESETS.iter().find(|p| p.name == "Lung")
        .expect("Lung preset should exist");
    assert_eq!(lung.center, -600.0);
    assert_eq!(lung.width, 1500.0);
}
