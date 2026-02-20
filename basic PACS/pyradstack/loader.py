from pathlib import Path

SUPPORTED_EXTENSIONS = {".dcm", ".jpg", ".jpeg", ".png"}


def scan_directory(directory: Path) -> list[Path]:
    """Recursively scan a directory and return paths to supported image files."""
    directory = Path(directory)
    return sorted(
        p.resolve()
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
