//! `rustradstack` GUI binary — slice 5 loads a folder of DICOMs and scrolls them.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{anyhow, Result};

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

    let paths = rustradstack::loading::paths_for(&arg)
        .map_err(|e| anyhow!("{e}"))?;

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
