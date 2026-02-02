"""
Manim Scaffolder - Handles the mapping between code snippets and full runnable files.

Following Google-quality standards:
- Clear separation of concerns: Scaffolding vs Validation vs Generation.
- Bi-directional mapping: Correctly offsets errors back to snippet lines.
- Progressive imports: Automatically handles common missing imports.
"""

import re
from typing import List, Optional, Tuple, Set

class ManimScaffolder:
    """Manages the relationship between an LLM-generated snippet and a full Manim file."""

    # Common libraries LLMs forget to import
    AUTO_IMPORTS = {
        "np": "import numpy as np",
        "numpy": "import numpy as np",
        "math": "import math",
        "random": "import random",
        "itertools": "import itertools",
    }

    def __init__(self, scene_name: str = "GeneratedScene"):
        self.scene_name = scene_name
        self.base_imports = ["from manim import *"]
        self.header_lines = 0

    def assemble(self, snippet: str, extra_imports: Optional[Set[str]] = None) -> str:
        """Assembles a full runnable file from a snippet.
        
        It also detects common symbols and adds missing imports automatically.
        """
        imports = set(self.base_imports)
        if extra_imports:
            imports.update(extra_imports)

        # Auto-detect common missing imports in the snippet
        for symbol, import_stmt in self.AUTO_IMPORTS.items():
            if re.search(rf"\b{symbol}\.", snippet):
                imports.add(import_stmt)

        # Sort imports: stdlib first, then manim
        sorted_imports = sorted(list(imports), key=lambda x: ("manim" in x, x))
        
        import_block = "\n".join(sorted_imports)
        class_header = f"class {self.scene_name}(Scene):\n    def construct(self):"
        
        # Calculate header lines for offset correction
        # +2 for empty lines after imports
        self.header_lines = len(sorted_imports) + 2 + 2 

        indented_body = "\n".join(["        " + line if line.strip() else line 
                                  for line in snippet.split("\n")])

        return f"{import_block}\n\n\n{class_header}\n{indented_body}\n"

    def translate_error(self, message: str, line_no: Optional[int]) -> Tuple[str, Optional[int]]:
        """Translates a full-file error message/line number back to snippet coordinates."""
        if line_no is None:
            return message, None
            
        snippet_line = line_no - self.header_lines
        
        # Replace line number in text message
        translated_message = re.sub(rf"line {line_no}\b", f"line {snippet_line}", message, flags=re.IGNORECASE)
        translated_message = re.sub(rf"Line {line_no}\b", f"Line {snippet_line}", translated_message)
        
        return translated_message, snippet_line
