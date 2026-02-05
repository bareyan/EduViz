"""
Minimal section status tracking for live progress updates.
Uses simple JSON files for scalability and crash-resilience.
"""

import json
from pathlib import Path
from typing import Optional, Literal, Union, Tuple

SectionState = Literal[
    "waiting",
    "generating_audio",
    "generating_manim",
    "fixing_manim",
    "generating_video",
    "fixing_error",
    "completed",
    "failed",
]


def write_status(section_dir: Union[Path, str], status: SectionState, error: Optional[str] = None) -> None:
    """Write current section status to a file. Fast and atomic."""
    section_dir = Path(section_dir)
    section_dir.mkdir(parents=True, exist_ok=True)
    status_file = section_dir / "status.json"
    data = {"status": status}
    if error:
        data["error"] = error
    try:
        status_file.write_text(json.dumps(data))
    except Exception:
        pass  # Non-critical - don't break pipeline


def read_status_info(section_dir: Path) -> Tuple[Optional[SectionState], Optional[str]]:
    """Read section status and error from file. Returns (None, None) if missing."""
    status_file = section_dir / "status.json"
    try:
        if status_file.exists():
            data = json.loads(status_file.read_text())
            return data.get("status"), data.get("error")
    except Exception:
        pass
    return None, None


def read_status(section_dir: Path) -> Optional[SectionState]:
    """Read section status from file. Returns None if no status file."""
    status, _ = read_status_info(section_dir)
    return status
