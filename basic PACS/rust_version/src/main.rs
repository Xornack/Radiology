//! `rustradstack` GUI binary — slice 4 displays a single DICOM in an egui window.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use dicom_object::open_file;
use rustradstack::viewer::ViewerApp;
use rustradstack::windowing::{apply_window, extract_pixels};

const USAGE: &str = "Usage: rustradstack <FILE.dcm>";

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e:#}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<()> {
    let dcm: PathBuf = env::args()
        .nth(1)
        .ok_or_else(|| anyhow!(USAGE))?
        .into();

    let obj = open_file(&dcm).with_context(|| format!("opening {}", dcm.display()))?;
    let (pixels, dims, ws) = extract_pixels(&obj)
        .with_context(|| format!("extracting pixels from {}", dcm.display()))?;
    let img = apply_window(&pixels, dims, ws);

    let mut app = ViewerApp::new();
    app.set_image(img);

    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([800.0, 600.0])
            .with_title("RustRadStack"),
        ..Default::default()
    };
    // AppCreator closure returns Result<Box<dyn App>, Box<dyn Error + Send + Sync>>
    eframe::run_native(
        "RustRadStack",
        options,
        Box::new(|_cc| Ok(Box::new(app))),
    )
    .map_err(|e| anyhow!("eframe run_native failed: {e}"))
}
