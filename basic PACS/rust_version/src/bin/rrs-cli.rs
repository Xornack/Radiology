//! `rrs-cli` — command-line interface for `RustRadStack`.
//!
//! Subcommands:
//!   info <FILE>   Print key DICOM tags from a single file.

use std::env;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use dicom_dictionary_std::tags;
use dicom_object::open_file;
use rustradstack::windowing::extract_pixels;

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
    let mut args = env::args().skip(1);
    let cmd = args.next().ok_or_else(|| anyhow!(USAGE))?;
    match cmd.as_str() {
        "info" => {
            let path: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("info requires a path argument\n\n{USAGE}"))?
                .into();
            cmd_info(&path)
        }
        other => Err(anyhow!("unknown subcommand: {other}\n\n{USAGE}")),
    }
}

const USAGE: &str = "Usage:\n  rrs-cli info <FILE>";

fn cmd_info(path: &Path) -> Result<()> {
    let obj = open_file(path).with_context(|| format!("opening {}", path.display()))?;

    let patient_name = obj
        .element(tags::PATIENT_NAME)
        .ok()
        .and_then(|e| e.to_str().ok().map(std::borrow::Cow::into_owned))
        .unwrap_or_else(|| "(missing)".into());
    let modality = obj
        .element(tags::MODALITY)
        .ok()
        .and_then(|e| e.to_str().ok().map(std::borrow::Cow::into_owned))
        .unwrap_or_else(|| "(missing)".into());
    let instance_number: Option<i32> = obj
        .element(tags::INSTANCE_NUMBER)
        .ok()
        .and_then(|e| e.to_int::<i32>().ok());

    let (_pixels, (rows, cols), ws) =
        extract_pixels(&obj).with_context(|| format!("extracting pixels from {}", path.display()))?;

    // Labels left-padded to 18 cols so RescaleIntercept (17 chars) still gets a separator space.
    println!("{:<18}{}", "File:", path.display());
    println!("{:<18}{patient_name}", "PatientName:");
    println!("{:<18}{modality}", "Modality:");
    println!(
        "{:<18}{}",
        "InstanceNumber:",
        instance_number.map_or_else(|| "(missing)".into(), |n| n.to_string())
    );
    println!("{:<18}{rows} x {cols}", "Rows x Cols:");
    println!("{:<18}{}", "WindowCenter:", ws.center);
    println!("{:<18}{}", "WindowWidth:", ws.width);
    println!("{:<18}{}", "RescaleSlope:", ws.slope);
    println!("{:<18}{}", "RescaleIntercept:", ws.intercept);

    Ok(())
}
