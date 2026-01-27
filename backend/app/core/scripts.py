"""Compatibility wrapper for script I/O utilities.

The actual implementation now lives in app.adapters.scripts_io to keep
infrastructure concerns out of core/.
"""

from app.adapters.scripts_io import (  # type: ignore F401
    load_script,
    save_script,
    get_script_metadata,
    load_section_script,
)

__all__ = [
    "load_script",
    "save_script",
    "get_script_metadata",
    "load_section_script",
]
