//! DICOM-aware sorting: `InstanceNumber` → `ImagePositionPatient`\[2\] → end.

use std::path::PathBuf;

use dicom_dictionary_std::tags;
use dicom_object::OpenFileOptions;

/// Sort a mixed list of DICOM and non-DICOM paths.
///
/// DICOMs (`.dcm`) come first, ordered by `InstanceNumber` ascending, falling back to
/// `ImagePositionPatient[2]`. Non-DICOM files follow, sorted alphabetically by filename.
#[must_use]
pub fn sort_files(paths: Vec<PathBuf>) -> Vec<PathBuf> {
    let (dicoms, mut others): (Vec<_>, Vec<_>) =
        paths.into_iter().partition(|p| is_dicom_extension(p));
    // Pre-compute keys so each DICOM is opened exactly once (not O(log n) times per sort_by).
    let mut keyed: Vec<(f64, PathBuf)> = dicoms.into_iter().map(|p| (sort_key(&p), p)).collect();
    keyed.sort_by(|(a, _), (b, _)| a.total_cmp(b));
    others.sort_by(|a, b| {
        let na = a
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let nb = b
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        na.cmp(&nb)
    });
    keyed.into_iter().map(|(_, p)| p).chain(others).collect()
}

fn is_dicom_extension(path: &std::path::Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("dcm"))
}

fn sort_key(path: &std::path::Path) -> f64 {
    // Stop parsing before PixelData — the sort only needs header tags, and
    // reading whole files makes opening a large series many times slower.
    let Ok(obj) = OpenFileOptions::new()
        .read_until(tags::PIXEL_DATA)
        .open_file(path)
    else {
        return f64::INFINITY;
    };

    if let Ok(elt) = obj.element(tags::INSTANCE_NUMBER)
        && let Ok(n) = elt.to_int::<i32>()
    {
        return f64::from(n);
    }

    if let Ok(elt) = obj.element(tags::IMAGE_POSITION_PATIENT) {
        // ImagePositionPatient is DS with 3 values; we want index [2] (Z).
        if let Ok(values) = elt.to_multi_float64()
            && let Some(z) = values.get(2)
        {
            return *z;
        }
    }

    f64::INFINITY
}
