"""
Script file I/O utilities (adapter layer).

Centralizes reading and writing of job script data. Kept outside core/ so
infrastructure concerns stay separate from cross-cutting helpers.
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from app.config import OUTPUT_DIR


def _script_path(job_id: str) -> Path:
    """Construct the path to a job's script.json file."""
    return OUTPUT_DIR / job_id / "script.json"


def load_script(job_id: str) -> Dict[str, Any]:
    """Load and parse a job's script.json file."""
    path = _script_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Script not found for job {job_id}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid script JSON: {exc}") from exc


def save_script(job_id: str, script: Dict[str, Any]) -> None:
    """Write script data to script.json file."""
    path = _script_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)


def get_script_metadata(script: Dict[str, Any]) -> Dict[str, Any]:
    """Extract common metadata fields from a script structure."""
    return {
        "title": script.get("title", "Untitled"),
        "total_duration": script.get("total_duration_seconds", 0),
        "sections_count": len(script.get("sections", [])),
    }


def load_section_script(job_id: str, section_id: str) -> Dict[str, Any]:
    """Load a specific section's data from a job's script.json."""
    script = load_script(job_id)
    for section in script.get("sections", []):
        if section.get("id") == section_id:
            return section
    raise HTTPException(status_code=404, detail=f"Section {section_id} not found for job {job_id}")


__all__ = [
    "load_script",
    "save_script",
    "get_script_metadata",
    "load_section_script",
]
