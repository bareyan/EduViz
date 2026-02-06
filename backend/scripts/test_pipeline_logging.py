"""
Test script to verify pipeline logging is working correctly.
Run this to generate sample pipeline log entries.
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.logging import setup_logging, get_logger, set_job_id

# Setup logging
log_file = Path("logs/animation_pipeline.jsonl")
setup_logging(
    level="INFO",
    use_json=True,
    pipeline_log_file=log_file
)

# Get logger
logger = get_logger(__name__, service="pipeline_test")

# Set a test job ID
set_job_id("test-job-12345")

# Generate test log entries
logger.info(
    "Test: Code generated",
    extra={
        "pipeline_stage": "code_generated",
        "section_title": "Test Section",
        "code_length": 1500,
        "turn": 1
    }
)

logger.info(
    "Test: Validation found issues",
    extra={
        "refinement_stage": "triage_summary",
        "total_issues": 3,
        "certain_issues": 2,
        "uncertain_issues": 1,
        "issues": [
            {
                "category": "spatial_overlap",
                "severity": "critical",
                "confidence": "high",
                "is_certain": True,
                "message": "Text overlap detected: 25%"
            },
            {
                "category": "spatial_edge",
                "severity": "warning",
                "confidence": "low",
                "is_certain": False,
                "message": "Element near edge"
            }
        ]
    }
)

logger.info(
    "Test: Deterministic fix applied",
    extra={
        "refinement_stage": "deterministic_fix",
        "issue_category": "spatial_overlap",
        "fix_type": "increase_buffer",
        "success": True
    }
)

logger.info(
    "Test: Visual QC input",
    extra={
        "pipeline_stage": "visual_qc_input",
        "uncertain_issues_count": 1,
        "issues": [
            {
                "category": "spatial_edge",
                "message": "Element near edge",
                "whitelist_key": "abc123def456"
            }
        ]
    }
)

logger.info(
    "Test: Visual QC confirmed false positive",
    extra={
        "pipeline_stage": "visual_qc_false_positive",
        "confirmed_false_positives": 1,
        "whitelisted_keys": ["abc123def456"]
    }
)

print(f"\n✅ Test logging complete!")
print(f"📄 Check the log file at: {log_file.absolute()}")
print(f"\nTo view the logs, run:")
print(f"  cat {log_file}")
print(f"\nOr on Windows:")
print(f"  type {log_file}")
