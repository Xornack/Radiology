//! Recursive directory scanning for DICOM files.

use std::io;
use std::path::{Path, PathBuf};

/// Recursively walk `dir` and return all supported image files (DICOM, JPG, JPEG, PNG …)
/// in alphabetical-by-path order.
///
/// # Errors
/// Returns `io::Error` if the directory can't be read.
pub fn scan_directory(dir: &Path) -> io::Result<Vec<PathBuf>> {
    let mut out = Vec::new();
    walk(dir, &mut out)?;
    out.sort();
    Ok(out)
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) -> io::Result<()> {
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            walk(&path, out)?;
        } else if file_type.is_file() && is_supported(&path) {
            out.push(path);
        }
    }
    Ok(())
}

// Shared with the study loader for single-file extension checks.
pub(crate) fn is_supported(path: &Path) -> bool {
    let Some(ext) = path.extension().and_then(|e| e.to_str()) else {
        return false;
    };
    matches!(
        ext.to_ascii_lowercase().as_str(),
        "dcm" | "jpg" | "jpeg" | "png"
    )
}
