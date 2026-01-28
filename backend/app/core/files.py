"""
File utilities - File operations and discovery
"""

from typing import Optional, List
from pathlib import Path


def find_file_by_id(file_id: str, upload_dir: Path, extensions: List[str]) -> Optional[Path]:
    """Find an uploaded file by its ID, trying different extensions
    
    Args:
        file_id: File identifier
        upload_dir: Directory to search in
        extensions: List of extensions to try (e.g., ['.pdf', '.png', '.txt'])
        
    Returns:
        Path to file if found, None otherwise
    """
    for ext in extensions:
        potential_path = upload_dir / f"{file_id}{ext}"
        if potential_path.exists():
            return potential_path
    return None


def ensure_directory(dir_path: Path) -> Path:
    """Ensure directory exists, creating if necessary
    
    Args:
        dir_path: Directory path
        
    Returns:
        The directory path
    """
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_extension(file_path: Path) -> str:
    """Get file extension
    
    Args:
        file_path: File path
        
    Returns:
        Extension including dot (e.g., '.pdf')
    """
    return file_path.suffix.lower()
