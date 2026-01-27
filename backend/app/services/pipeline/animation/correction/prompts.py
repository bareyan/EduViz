"""
Diff Correction Prompts - Compatibility Layer

Re-exports from centralized animation/prompts.py for backward compatibility.
New code should import directly from app.services.pipeline.animation.prompts
"""


# Import from centralized animation prompts

# Import schema from tools
from app.services.pipeline.animation.generation.tools import SEARCH_REPLACE_SCHEMA

# Re-export schema for backward compatibility
DIFF_CORRECTION_SCHEMA = SEARCH_REPLACE_SCHEMA
