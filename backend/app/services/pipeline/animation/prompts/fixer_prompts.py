"""
Fixer Prompts

Constants and templates for the Adaptive Fixer Agent.
"""

from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate

# Guidance for the first attempt or when no specific failure reason exists using PromptTemplate
INITIAL_RETRY_NOTE = PromptTemplate(
    template="""CRITICAL: Keep response SHORT and FOCUSED:
- analysis: max 2 sentences
- edits: 1-10 edits
- search_text: 5-10 lines context
- replacement_text: only changed lines
This prevents JSON truncation issues.""",
    description="Guidance for keeping fixer response concise"
)

# Template for subsequent retry attempts
RETRY_FAILURE_NOTE = PromptTemplate(
    template="""Previous attempt failed: {failure_reason}. Attempt {attempt}/{max_retries}. Return ONLY valid JSON. Keep edits MINIMAL (1 edit preferred). Short search_text (5-10 lines), brief analysis (1-2 sentences). Ensure complete JSON to avoid truncation.""",
    description="Guidance after a failed fix attempt"
)

# Note for code context windowing
CODE_CONTEXT_NOTE = "Code below shows only snippets around error lines. Keep search_text within shown lines."

# Note for code truncation
CODE_TRUNCATION_NOTE = "Code is truncated (head/tail only). Keep search_text within shown lines."
