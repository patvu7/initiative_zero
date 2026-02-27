import os
import pathlib

SAMPLES_DIR = pathlib.Path(__file__).parent.parent / "samples"

def list_files():
    """Return list of available legacy files with metadata."""
    files = []
    for f in SAMPLES_DIR.glob("*.cbl"):
        stat = f.stat()
        content = f.read_text()
        lines = content.strip().split('\n')
        # Extract metadata from header comments
        files.append({
            "filename": f.name,
            "language": "COBOL",
            "loc": len(lines),
            "size_bytes": stat.st_size,
            "content": content
        })
    return files

def get_file(filename: str):
    """Return contents and metadata of a specific file."""
    path = SAMPLES_DIR / filename
    if not path.exists() or not path.suffix == '.cbl':
        return None
    content = path.read_text()
    lines = content.strip().split('\n')
    return {
        "filename": filename,
        "language": "COBOL",
        "loc": len(lines),
        "content": content
    }
