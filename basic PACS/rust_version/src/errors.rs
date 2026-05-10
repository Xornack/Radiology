//! Library-wide error type.

use std::io;

#[derive(thiserror::Error, Debug)]
pub enum RrsError {
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),

    #[error("DICOM error: {0}")]
    Dicom(String),

    #[error("missing DICOM tag: {0}")]
    MissingTag(&'static str),

    #[error("unsupported pixel format: {0}")]
    UnsupportedPixels(String),
}
