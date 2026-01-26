"""
DEPRECATED: Import compatibility shim

Script generation has moved to the script_generation package.
Existing imports continue to work via this shim.

New code should import directly:
    from app.services.script_generation import ScriptGenerator
"""

from app.services.script_generation import ScriptGenerator

__all__ = ["ScriptGenerator"]
