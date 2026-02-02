"""
Formatting utilities for spatial validation reports.
"""

from .models import SpatialValidationResult


def format_spatial_issues(result: SpatialValidationResult) -> str:
    """Format issues for a single human-readable summary."""
    if result.raw_report and result.has_issues:
        return result.raw_report

    if not result.has_issues:
        return "No spatial layout issues found"

    output = []

    if result.errors:
        output.append("ERRORS:")
        for error in result.errors:
            output.append(f"  Line {error.line_number}: {error.message}")
            if error.code_snippet:
                output.append(f"    Code: {error.code_snippet}")

    if result.warnings:
        minor_warnings = [w for w in result.warnings if w.severity == "info"]
        regular_warnings = [w for w in result.warnings if w.severity != "info"]
        
        if regular_warnings:
            output.append("\nWARNINGS:")
            for warning in regular_warnings:
                output.append(f"  Line {warning.line_number}: {warning.message}")
                if warning.code_snippet:
                    output.append(f"    Code: {warning.code_snippet}")
        
        if minor_warnings:
            output.append("\nNOTES (minor issues):")
            for warning in minor_warnings:
                output.append(f"  Line {warning.line_number}: {warning.message}")
                if warning.code_snippet:
                    output.append(f"    Code: {warning.code_snippet}")

    return "\n".join(output)
