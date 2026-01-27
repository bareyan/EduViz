"""
Code correction/fixing prompts.

Used by: diff_correction/corrector.py, integration.py, visual_qc_diff.py
"""

from .base import PromptTemplate


CODE_FIX_SIMPLE = PromptTemplate(
    template="""FIX THIS MANIM ERROR:

Error: {error_message}

Code:
```python
{code}
```

Provide fix as SEARCH/REPLACE block:
<<<<<<< SEARCH
exact text to find
=======
replacement text
>>>>>>> REPLACE""",
    description="Simple code fix with search/replace"
)


CODE_FIX_ANALYSIS = PromptTemplate(
    template="""Analyze this Manim error and provide fixes.

Error: {error_message}
Error type: {error_type}

Code context:
```python
{code}
```

Section context: {section_context}

Analyze the error and provide SEARCH/REPLACE blocks to fix it.
Focus on the root cause, not symptoms.""",
    description="Analyze error and provide fix"
)


CODE_FIX_MULTIPLE = PromptTemplate(
    template="""Fix ALL these Manim errors using SEARCH/REPLACE blocks:

Errors:
{error_messages}

Code:
```python
{code}
```

Provide one SEARCH/REPLACE block per fix:
<<<<<<< SEARCH
exact text to find
=======
replacement text
>>>>>>> REPLACE""",
    description="Fix multiple errors at once"
)


VISUAL_FIX = PromptTemplate(
    template="""FIX THESE VISUAL LAYOUT ERRORS in Manim code:

Error Report:
{error_report}

Current Code:
```python
{code}
```

Section: {section_title}

Common visual fixes:
- Move text: .to_edge(UP), .shift(DOWN*0.5)
- Scale: .scale(0.8) for smaller
- Clear screen: self.clear() or FadeOut(group)
- Spacing: arrange with buff=0.5

Provide SEARCH/REPLACE blocks for each fix.""",
    description="Fix visual layout issues"
)
