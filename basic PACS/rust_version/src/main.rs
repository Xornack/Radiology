//! `rustradstack` GUI binary — slice 5 loads a folder of DICOMs and scrolls them.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use rustradstack::loader::scan_directory;
use rustradstack::sorting::sort_files;
use rustradstack::stack::ImageStack;
use rustradstack::viewer::ViewerApp;

const USAGE: &str = "Usage:\n  rustradstack <FILE.dcm>\n  rustradstack <FOLDER>";

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
    let arg: PathBuf = env::args()
        .nth(1)
        .ok_or_else(|| anyhow!(USAGE))?
        .into();

    let paths: Vec<PathBuf> = if arg.is_dir() {
        let scanned = scan_directory(&arg)
            .with_context(|| format!("scanning {}", arg.display()))?;
        sort_files(scanned)
    } else if arg.is_file() {
        vec![arg.clone()]
    } else {
        return Err(anyhow!("{} is neither a file nor a directory", arg.display()));
    };

    if paths.is_empty() {
        return Err(anyhow!("no DICOM files found in {}", arg.display()));
    }

    let stack = ImageStack::new(paths);
    let app = ViewerApp::new(stack);

    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([800.0, 600.0])
            .with_title("RustRadStack"),
        ..Default::default()
    };
    eframe::run_native(
        "RustRadStack",
        options,
        Box::new(|_cc| Ok(Box::new(app))),
    )
    .map_err(|e| anyhow!("eframe run_native failed: {e}"))
}
