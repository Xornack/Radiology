//! `rrs-cli` — command-line interface for RustRadStack.
//!
//! Subcommands:
//!   info <FILE>   Print key DICOM tags from a single file.

use std::env;
use std::path::PathBuf;
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

fn cmd_info(path: &std::path::Path) -> Result<()> {
    // Read tags directly via dicom-object for the metadata-only fields
    // (PatientName, Modality), then call extract_pixels for dims + W/L.
    let obj = open_file(path).with_context(|| format!("opening {}", path.display()))?;

    let patient_name = obj
        .element(tags::PATIENT_NAME)
        .ok()
        .and_then(|e| e.to_str().ok().map(|s| s.into_owned()))
        .unwrap_or_else(|| "(missing)".into());
    let modality = obj
        .element(tags::MODALITY)
        .ok()
        .and_then(|e| e.to_str().ok().map(|s| s.into_owned()))
        .unwrap_or_else(|| "(missing)".into());
    let instance_number: Option<i32> = obj
        .element(tags::INSTANCE_NUMBER)
        .ok()
        .and_then(|e| e.to_int::<i32>().ok());

    let (_pixels, (rows, cols), ws) =
        extract_pixels(path).with_context(|| format!("extracting pixels from {}", path.display()))?;

    println!("File:            {}", path.display());
    println!("PatientName:     {patient_name}");
    println!("Modality:        {modality}");
    println!(
        "InstanceNumber:  {}",
        instance_number
            .map(|n| n.to_string())
            .unwrap_or_else(|| "(missing)".into())
    );
    println!("Rows x Cols:     {rows} x {cols}");
    println!("WindowCenter:    {}", ws.center);
    println!("WindowWidth:     {}", ws.width);
    println!("RescaleSlope:    {}", ws.slope);
    println!("RescaleIntercept:{}", ws.intercept);

    Ok(())
}
