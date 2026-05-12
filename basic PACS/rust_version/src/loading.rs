//! Convert a user-supplied path (file or folder) into a sorted Vec<PathBuf>
//! ready to feed into `ImageStack::new`.

use std::path::{Path, PathBuf};

use crate::loader::scan_directory;
use crate::sorting::sort_files;

/// Result of trying to build a stack from a path.
// #[non_exhaustive]: future slices will add InvalidContent and similar variants.
#[non_exhaustive]
#[derive(Debug)]
pub enum LoadError {
    /// Path doesn't exist or is neither a file nor a directory.
    NotFile(PathBuf),
    /// Recursive scan failed (permission denied, etc.).
    ScanFailed(std::io::Error),
    /// Folder scanned successfully but contained no DICOM files.
    Empty(PathBuf),
}

impl std::fmt::Display for LoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotFile(p) => write!(f, "not a file or directory: {}", p.display()),
            Self::ScanFailed(e) => write!(f, "scan failed: {e}"),
            Self::Empty(p) => write!(f, "no DICOM files found in {}", p.display()),
        }
    }
}

impl std::error::Error for LoadError {}

/// Build a sorted Vec<PathBuf> from a file or folder path. Returns `LoadError`
/// on missing path, scan failure, or empty folder.
///
/// # Errors
/// See `LoadError` variants.
pub fn paths_for(arg: &Path) -> Result<Vec<PathBuf>, LoadError> {
    if arg.is_dir() {
        let scanned = scan_directory(arg).map_err(LoadError::ScanFailed)?;
        let sorted = sort_files(scanned);
        if sorted.is_empty() {
            return Err(LoadError::Empty(arg.to_path_buf()));
        }
        Ok(sorted)
    } else if arg.is_file() {
        Ok(vec![arg.to_path_buf()])
    } else {
        Err(LoadError::NotFile(arg.to_path_buf()))
    }
}
