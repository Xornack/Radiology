//! Hardcoded W/L presets for common radiology display modes.
//!
//! Six canonical CT settings — daily-use across PACS workstations. Pure data;
//! no GUI deps so callers can use the values without pulling in egui.

/// A named (center, width) pair.
pub struct WindowPreset {
    pub name: &'static str,
    pub center: f64,
    pub width: f64,
}

/// Canonical CT W/L presets, in order. Indexing is 0-based; the viewer maps
/// number keys 1..=N to `PRESETS[N-1]`.
pub const PRESETS: &[WindowPreset] = &[
    WindowPreset {
        name: "Soft Tissue",
        center: 40.0,
        width: 400.0,
    },
    WindowPreset {
        name: "Lung",
        center: -600.0,
        width: 1500.0,
    },
    WindowPreset {
        name: "Bone",
        center: 400.0,
        width: 1800.0,
    },
    WindowPreset {
        name: "Brain",
        center: 40.0,
        width: 80.0,
    },
    WindowPreset {
        name: "Mediastinum",
        center: 40.0,
        width: 350.0,
    },
    WindowPreset {
        name: "Liver",
        center: 60.0,
        width: 160.0,
    },
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn presets_list_non_empty() {
        assert!(!PRESETS.is_empty());
    }

    #[test]
    fn preset_widths_positive_and_finite() {
        for p in PRESETS {
            assert!(
                p.width > 0.0,
                "preset {} has non-positive width: {}",
                p.name,
                p.width
            );
            assert!(p.center.is_finite(), "preset {} center not finite", p.name);
            assert!(p.width.is_finite(), "preset {} width not finite", p.name);
        }
    }

    #[test]
    fn preset_names_unique() {
        let mut names: Vec<&str> = PRESETS.iter().map(|p| p.name).collect();
        names.sort_unstable();
        let original_len = names.len();
        names.dedup();
        assert_eq!(names.len(), original_len, "duplicate preset name(s)");
    }
}
