"""Zone 1: Legacy file access.

Sample COBOL files are simplified (50-100 LOC) for demo purposes.
Production legacy systems are typically 10,000-500,000+ LOC with
cross-module dependencies, copybooks, and JCL orchestration.
The pipeline architecture handles arbitrary scale — Zone 2 analysis
and Zone 3 extraction operate on AST-level chunks, not whole files.
"""

import pathlib

SAMPLES_DIR = pathlib.Path(__file__).parent.parent / "samples"

def list_files():
    """Return list of available legacy files with metadata."""
    files = []
    for f in SAMPLES_DIR.glob("*.cbl"):
        stat = f.stat()
        content = f.read_text()
        lines = content.strip().split('\n')
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
    # Ensure the resolved path stays within SAMPLES_DIR to prevent path traversal
    try:
        resolved = path.resolve()
        samples_resolved = SAMPLES_DIR.resolve()
        if not str(resolved).startswith(str(samples_resolved)):
            return None
    except (OSError, ValueError):
        return None
    if not resolved.exists() or not resolved.suffix == '.cbl':
        return None
    content = resolved.read_text()
    lines = content.strip().split('\n')
    return {
        "filename": filename,
        "language": "COBOL",
        "loc": len(lines),
        "content": content
    }
