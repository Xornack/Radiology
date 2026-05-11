//! DICOM-aware sorting: `InstanceNumber` → `ImagePositionPatient`\[2\] → end.

use std::path::PathBuf;

use dicom_dictionary_std::tags;
use dicom_object::open_file;

/// Sort DICOM file paths by `InstanceNumber` ascending.
///
/// Files missing `InstanceNumber` fall back to `ImagePositionPatient[2]` (Z-coordinate).
/// Files missing both keys (or that fail to parse) sort to the end.
#[must_use]
pub fn sort_files(mut paths: Vec<PathBuf>) -> Vec<PathBuf> {
    paths.sort_by(|a, b| {
        let ka = sort_key(a);
        let kb = sort_key(b);
        ka.partial_cmp(&kb).unwrap_or(std::cmp::Ordering::Equal)
    });
    paths
}

fn sort_key(path: &std::path::Path) -> f64 {
    let Ok(obj) = open_file(path) else { return f64::INFINITY; };

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
