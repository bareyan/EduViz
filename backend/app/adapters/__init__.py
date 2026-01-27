"""Adapters layer for infrastructure concerns (storage, I/O, external systems)."""

from .scripts_io import (
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
