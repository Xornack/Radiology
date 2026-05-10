//! Recursive directory scanning for DICOM files.

use std::io;
use std::path::{Path, PathBuf};

/// Recursively walk `dir` and return all `.dcm` files (case-insensitive extension match)
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
        } else if file_type.is_file() && is_dicom(&path) {
            out.push(path);
        }
    }
    Ok(())
}

fn is_dicom(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| ext.eq_ignore_ascii_case("dcm"))
        .unwrap_or(false)
}
