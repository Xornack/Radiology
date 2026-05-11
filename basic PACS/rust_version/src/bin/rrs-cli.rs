//! `rrs-cli` — command-line interface for `RustRadStack`.
//!
//! Subcommands:
//!   info <FILE>              Print key DICOM tags from a single file.
//!   render <FILE> <OUT.png>  Window/level a DICOM and write it as a PNG.
//!   list <FOLDER>            List DICOM files in a folder, sorted by `InstanceNumber`.

use std::env;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use anyhow::{anyhow, Context, Result};

use dicom_dictionary_std::tags;
use dicom_object::open_file;
use rustradstack::loader::scan_directory;
use rustradstack::sorting::sort_files;
use rustradstack::windowing::{apply_window, extract_pixels, read_metadata};

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
        "render" => {
            let input: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("render requires <FILE> <OUT.png>\n\n{USAGE}"))?
                .into();
            let output: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("render requires <FILE> <OUT.png>\n\n{USAGE}"))?
                .into();
            cmd_render(&input, &output)
        }
        "list" => {
            let folder: PathBuf = args
                .next()
                .ok_or_else(|| anyhow!("list requires a <FOLDER> argument\n\n{USAGE}"))?
                .into();
            cmd_list(&folder)
        }
        other => Err(anyhow!("unknown subcommand: {other}\n\n{USAGE}")),
    }
}

const USAGE: &str = "Usage:\n  rrs-cli info <FILE>\n  rrs-cli render <FILE> <OUT.png>\n  rrs-cli list <FOLDER>";

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

    let ((rows, cols), ws) = read_metadata(&obj)
        .with_context(|| format!("reading metadata from {}", path.display()))?;

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

fn cmd_render(input: &Path, output: &Path) -> Result<()> {
    let obj = open_file(input).with_context(|| format!("opening {}", input.display()))?;
    let (pixels, dims, ws) = extract_pixels(&obj)
        .with_context(|| format!("extracting pixels from {}", input.display()))?;
    let img = apply_window(&pixels, dims, ws);
    img.save(output)
        .with_context(|| format!("writing {}", output.display()))?;
    println!("wrote {}", output.display());
    Ok(())
}

fn cmd_list(folder: &Path) -> Result<()> {
    let paths = scan_directory(folder)
        .with_context(|| format!("scanning {}", folder.display()))?;
    let sorted = sort_files(paths);
    println!("{} DICOM(s) in {}:", sorted.len(), folder.display());
    for (idx, path) in sorted.iter().enumerate() {
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("(?)");
        println!("  {:>4}  {}", idx + 1, name);
    }
    Ok(())
}
