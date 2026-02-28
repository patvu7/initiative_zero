"""Zone 1: Legacy file access.

Sample COBOL files are simplified (50-100 LOC) for demo purposes.
Production legacy systems are typically 10,000-500,000+ LOC with
cross-module dependencies, copybooks, and JCL orchestration.
The pipeline architecture handles arbitrary scale — Zone 2 analysis
and Zone 3 extraction operate on AST-level chunks, not whole files.
"""

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
