"""
Script file I/O utilities.

Centralizes reading and writing of job script data to avoid duplication across
routes and services. All operations handle errors gracefully with appropriate
HTTP exceptions for route layer integration.

Functions:
    load_script: Load and parse a job's script.json file
    save_script: Write script data to script.json file
    get_script_metadata: Extract common metadata from script
    load_section_script: Load individual section from job script
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from app.config import OUTPUT_DIR


def _script_path(job_id: str) -> Path:
    """
    Construct the path to a job's script.json file.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Path object pointing to script.json for the job
    """
    return OUTPUT_DIR / job_id / "script.json"


def load_script(job_id: str) -> Dict[str, Any]:
    """
    Load and parse a job's script.json file.
    
    Reads the complete script definition for a job, including all sections,
    metadata, and processing information. Handles file not found and JSON
    parsing errors with appropriate HTTP exceptions.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Dictionary containing the full script structure with sections,
        metadata, narration, and visual descriptions
        
    Raises:
        HTTPException: 404 if script file doesn't exist, 500 if JSON is invalid
        
    Example:
        >>> script = load_script("job-123")
        >>> sections = script.get("sections", [])
        >>> print(f"Job has {len(sections)} sections")
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
    """
    Write script data to script.json file.
    
    Persists the complete script structure to disk. Creates parent directories
    if needed. Uses 2-space indentation for readable JSON output.
    
    Args:
        job_id: Unique job identifier
        script: Dictionary containing complete script data
        
    Raises:
        IOError: If file cannot be written
        
    Example:
        >>> script = {"title": "My Video", "sections": [...]}
        >>> save_script("job-123", script)
    """
    path = _script_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)


def get_script_metadata(script: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract common metadata fields from a script structure.
    
    Pulls frequently-needed metadata that's used for listing jobs,
    displaying job info, and progress tracking. Provides sensible defaults
    if fields are missing.
    
    Args:
        script: Dictionary containing script data
        
    Returns:
        Dictionary with keys:
            - title: Video title (default: "Untitled")
            - total_duration: Duration in seconds (default: 0)
            - sections_count: Number of sections (default: 0)
            
    Example:
        >>> metadata = get_script_metadata(script)
        >>> print(f"Video: {metadata['title']} ({metadata['sections_count']} sections)")
    """
    return {
        "title": script.get("title", "Untitled"),
        "total_duration": script.get("total_duration_seconds", 0),
        "sections_count": len(script.get("sections", [])),
    }


def load_section_script(job_id: str, section_id: str) -> Dict[str, Any]:
    """
    Load a specific section's data from a job's script.json.
    
    Retrieves the complete metadata and content for a single section,
    including narration, visual description, and animation code.
    
    Args:
        job_id: Unique job identifier
        section_id: Section identifier within the script
        
    Returns:
        Dictionary containing the section's complete data
        
    Raises:
        HTTPException: 404 if script or section not found
        
    Example:
        >>> section = load_section_script("job-123", "section-456")
        >>> print(f"Section: {section['title']}")
        >>> print(f"Narration: {section['narration'][:100]}...")
    """
    script = load_script(job_id)
    for section in script.get("sections", []):
        if section.get("id") == section_id:
            return section
    raise HTTPException(status_code=404, detail=f"Section {section_id} not found for job {job_id}")
