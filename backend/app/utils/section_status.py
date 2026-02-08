"""
Minimal section status tracking for live progress updates.
Uses simple JSON files for scalability and crash-resilience.
"""

import json
from pathlib import Path
from typing import Optional, Literal, Union, TypedDict

SectionState = Literal[
    "waiting",
    "generating_audio",
    "generating_manim",
    "fixing_manim",
    "generating_video",
    "fixing_error",
    "completed",
]


class SectionStatusDetails(TypedDict, total=False):
    status: SectionState
    error: str


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


def read_status_details(section_dir: Path) -> Optional[SectionStatusDetails]:
    """Read section status + error from file. Returns None if no status file."""
    status_file = section_dir / "status.json"
    try:
        if status_file.exists():
            data = json.loads(status_file.read_text())
            return {
                "status": data.get("status"),
                "error": data.get("error"),
            }
    except Exception:
        pass
    return None


def read_status(section_dir: Path) -> Optional[SectionState]:
    """Read section status from file. Returns None if no status file."""
    details = read_status_details(section_dir)
    if details:
        return details.get("status")
    return None
