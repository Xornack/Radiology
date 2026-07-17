//! `rustradstack` GUI binary — slice 5 loads a folder of DICOMs and scrolls them.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use anyhow::{Result, anyhow};

use rustradstack::stack::ImageStack;
use rustradstack::viewer::ViewerApp;

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
    let app = if let Some(arg_str) = env::args().nth(1) {
        let arg: PathBuf = arg_str.into();
        let paths = rustradstack::loading::paths_for(&arg).map_err(|e| anyhow!("{e}"))?;
        let stack = ImageStack::new(paths);
        ViewerApp::new(stack)
    } else {
        ViewerApp::empty()
    };

    let options = eframe::NativeOptions {
        // Maximized — radiology images want all the screen they can get.
        // The inner size is the fallback if the OS ignores maximize.
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([800.0, 600.0])
            .with_maximized(true)
            .with_title("RustRadStack"),
        ..Default::default()
    };
    eframe::run_native("RustRadStack", options, Box::new(|_cc| Ok(Box::new(app))))
        .map_err(|e| anyhow!("eframe run_native failed: {e}"))
}
