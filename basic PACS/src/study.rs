//! Study ("jacket") model — group scanned image files into series.
//!
//! DICOM files group by `SeriesInstanceUID` (fallback: parent folder); JPG/PNG
//! group by parent folder. Within a series, DICOMs order by `InstanceNumber`,
//! falling back to `ImagePositionPatient[2]`; non-DICOM files alphabetically.
//! Series order follows `SeriesNumber`, then description.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use dicom_dictionary_std::tags;
use dicom_object::OpenFileOptions;

use crate::loader::{is_supported, scan_directory};

/// Result of trying to load a study from a path.
// #[non_exhaustive]: future slices may add InvalidContent and similar variants.
#[non_exhaustive]
#[derive(Debug)]
pub enum LoadError {
    /// Path doesn't exist or is neither a file nor a directory.
    NotFound(PathBuf),
    /// Recursive scan failed (permission denied, etc.).
    ScanFailed(std::io::Error),
    /// Folder scanned successfully but contained no image files.
    Empty(PathBuf),
    /// Path is a file but has no recognised image extension.
    UnsupportedFile(PathBuf),
}

impl std::fmt::Display for LoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotFound(p) => write!(f, "not found: {}", p.display()),
            Self::ScanFailed(e) => write!(f, "scan failed: {e}"),
            Self::Empty(p) => write!(f, "no image files found in {}", p.display()),
            Self::UnsupportedFile(p) => write!(f, "unsupported file type: {}", p.display()),
        }
    }
}

impl std::error::Error for LoadError {}

/// One scrollable series within a study.
#[derive(Debug, Clone, PartialEq)]
pub struct Series {
    /// Grouping key — `SeriesInstanceUID` or parent folder path. Stable, not shown.
    pub key: String,
    /// Label for the thumbnail strip: SeriesDescription → "Series N" → folder name.
    pub description: String,
    /// `SeriesNumber` when present; primary ordering of the series strip.
    pub number: Option<i32>,
    /// Slice paths in scroll order.
    pub paths: Vec<PathBuf>,
}

impl Series {
    /// Middle slice — the representative image for the series thumbnail.
    #[must_use]
    pub fn center_path(&self) -> Option<&Path> {
        self.paths.get(self.paths.len() / 2).map(PathBuf::as_path)
    }
}

/// A loaded study: one or more series ready to hang into viewports.
#[derive(Debug, Clone, PartialEq)]
pub struct Study {
    pub series: Vec<Series>,
}

/// Header fields needed for grouping + in-series ordering, read in one pass
/// per file (stops before PixelData — see `read_until`).
struct DicomMeta {
    series_uid: Option<String>,
    series_desc: Option<String>,
    series_num: Option<i32>,
    /// InstanceNumber → ImagePositionPatient\[2\] → +∞ (unsortable last).
    sort_key: f64,
}

fn read_dicom_meta(path: &Path) -> DicomMeta {
    let unknown = DicomMeta {
        series_uid: None,
        series_desc: None,
        series_num: None,
        sort_key: f64::INFINITY,
    };
    let Ok(obj) = OpenFileOptions::new()
        .read_until(tags::PIXEL_DATA)
        .open_file(path)
    else {
        return unknown;
    };

    let read_string = |tag| {
        obj.element(tag)
            .ok()
            .and_then(|e| e.to_str().ok())
            .map(|s| s.trim_matches(['\0', ' ']).to_owned())
            .filter(|s| !s.is_empty())
    };
    let series_uid = read_string(tags::SERIES_INSTANCE_UID);
    let series_desc = read_string(tags::SERIES_DESCRIPTION);
    let series_num = obj
        .element(tags::SERIES_NUMBER)
        .ok()
        .and_then(|e| e.to_int::<i32>().ok());

    let mut sort_key = f64::INFINITY;
    if let Ok(elt) = obj.element(tags::INSTANCE_NUMBER)
        && let Ok(n) = elt.to_int::<i32>()
    {
        sort_key = f64::from(n);
    } else if let Ok(elt) = obj.element(tags::IMAGE_POSITION_PATIENT)
        && let Ok(values) = elt.to_multi_float64()
        && let Some(z) = values.get(2)
    {
        sort_key = *z;
    }

    DicomMeta {
        series_uid,
        series_desc,
        series_num,
        sort_key,
    }
}

fn is_dicom_ext(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("dcm"))
}

fn folder_name(path: &Path) -> String {
    path.parent()
        .and_then(Path::file_name)
        .map_or_else(|| "(unnamed)".to_owned(), |n| n.to_string_lossy().into_owned())
}

/// Accumulates one series while grouping scanned files.
struct GroupBuilder {
    key: String,
    description: Option<String>,
    number: Option<i32>,
    dicom: bool,
    /// (sort key, path); non-DICOM entries sort alphabetically instead.
    entries: Vec<(f64, PathBuf)>,
}

impl GroupBuilder {
    fn into_series(mut self) -> Series {
        if self.dicom {
            self.entries.sort_by(|(a, _), (b, _)| a.total_cmp(b));
        } else {
            self.entries.sort_by_key(|(_, p)| {
                p.file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("")
                    .to_ascii_lowercase()
            });
        }
        let first = self.entries.first().map(|(_, p)| p.clone());
        let description = self
            .description
            .or_else(|| self.number.map(|n| format!("Series {n}")))
            .or_else(|| first.as_deref().map(folder_name))
            .unwrap_or_else(|| "(unnamed)".to_owned());
        Series {
            key: self.key,
            description,
            number: self.number,
            paths: self.entries.into_iter().map(|(_, p)| p).collect(),
        }
    }
}

/// Group already-scanned image paths into series.
fn group_into_series(paths: Vec<PathBuf>) -> Vec<Series> {
    let mut groups: Vec<GroupBuilder> = Vec::new();
    let mut index: HashMap<String, usize> = HashMap::new();

    for path in paths {
        let dicom = is_dicom_ext(&path);
        let (key, meta) = if dicom {
            let meta = read_dicom_meta(&path);
            // Distinct prefixes so a folder holding both DICOMs and screenshots
            // can never collide into one series.
            let key = meta.series_uid.clone().map_or_else(
                || format!("folder-dcm:{}", path.parent().unwrap_or(Path::new("")).display()),
                |uid| format!("uid:{uid}"),
            );
            (key, Some(meta))
        } else {
            (
                format!("folder-img:{}", path.parent().unwrap_or(Path::new("")).display()),
                None,
            )
        };

        let slot = *index.entry(key.clone()).or_insert_with(|| {
            groups.push(GroupBuilder {
                key,
                description: None,
                number: None,
                dicom,
                entries: Vec::new(),
            });
            groups.len() - 1
        });
        let group = &mut groups[slot];
        if let Some(meta) = meta {
            if group.description.is_none() {
                group.description = meta.series_desc;
            }
            if group.number.is_none() {
                group.number = meta.series_num;
            }
            group.entries.push((meta.sort_key, path));
        } else {
            group.entries.push((0.0, path));
        }
    }

    let mut series: Vec<Series> = groups.into_iter().map(GroupBuilder::into_series).collect();
    // Strip order: SeriesNumber first (missing numbers last), then label.
    series.sort_by(|a, b| {
        let na = a.number.unwrap_or(i32::MAX);
        let nb = b.number.unwrap_or(i32::MAX);
        na.cmp(&nb)
            .then_with(|| a.description.to_lowercase().cmp(&b.description.to_lowercase()))
            .then_with(|| a.key.cmp(&b.key))
    });
    series
}

/// Load a study ("jacket") from a file or folder path.
///
/// A folder is scanned recursively and grouped into series; a single file
/// becomes a one-slice study. The result always has at least one series.
///
/// # Errors
/// See [`LoadError`] variants.
pub fn load_study(arg: &Path) -> Result<Study, LoadError> {
    if arg.is_dir() {
        let scanned = scan_directory(arg).map_err(LoadError::ScanFailed)?;
        let series = group_into_series(scanned);
        if series.is_empty() {
            return Err(LoadError::Empty(arg.to_path_buf()));
        }
        Ok(Study { series })
    } else if arg.is_file() {
        // Reject .txt, .exe, DICOMDIR, etc. early — otherwise the viewer would
        // accept the path, then silently fail on first decode.
        if !is_supported(arg) {
            return Err(LoadError::UnsupportedFile(arg.to_path_buf()));
        }
        let series = group_into_series(vec![arg.to_path_buf()]);
        Ok(Study { series })
    } else {
        Err(LoadError::NotFound(arg.to_path_buf()))
    }
}
