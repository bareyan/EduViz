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


def unwrap_script(script: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unwrap a script from its wrapper format if necessary.
    
    The script generator returns scripts in a wrapped format:
    {"script": {...actual script...}, "mode": "...", "output_language": "..."}
    
    This function extracts the inner script for consistent access.
    
    Args:
        script: Either a wrapped script {"script": {...}} or an unwrapped script
        
    Returns:
        The unwrapped script with title, sections, etc. at top level
    """
    # Check if script is wrapped (has "script" key with sections inside)
    if "script" in script and isinstance(script.get("script"), dict):
        inner = script["script"]
        # Verify it looks like a valid inner script (has sections or title)
        if "sections" in inner or "title" in inner:
            return inner
    return script


def load_script(job_id: str) -> Dict[str, Any]:
    """
    Load and parse a job's script.json file.
    
    Returns the unwrapped script with title, sections, etc. at top level.
    """
    path = _script_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Script not found for job {job_id}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_script = json.load(f)
        return unwrap_script(raw_script)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid script JSON: {exc}") from exc


def load_script_raw(job_id: str) -> Dict[str, Any]:
    """
    Load a job's script.json file without unwrapping.
    
    Use this when you need access to metadata like mode, output_language, etc.
    """
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
    """
    Extract common metadata fields from a script structure.
    
    Handles both wrapped and unwrapped script formats.
    """
    # Unwrap if necessary
    inner_script = unwrap_script(script)
    return {
        "title": inner_script.get("title", "Untitled"),
        "total_duration": inner_script.get("total_duration_seconds", 0),
        "sections_count": len(inner_script.get("sections", [])),
    }


def load_section_script(job_id: str, section_id: str) -> Dict[str, Any]:
    """Load a specific section's data from a job's script.json."""
    script = load_script(job_id)  # Already unwrapped
    for section in script.get("sections", []):
        if section.get("id") == section_id:
            return section
    raise HTTPException(status_code=404, detail=f"Section {section_id} not found for job {job_id}")


__all__ = [
    "load_script",
    "load_script_raw",
    "save_script",
    "get_script_metadata",
    "load_section_script",
    "unwrap_script",
]
