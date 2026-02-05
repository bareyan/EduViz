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


def format_visual_context_for_fix(result: SpatialValidationResult) -> str:
    """Format a compact visual context block for surgical fixes."""
    if not result or not result.frame_captures:
        return ""

    issues = (result.errors or []) + (result.warnings or []) + (result.info or [])
    issues_by_frame = {}
    for issue in issues:
        if not issue.frame_id:
            continue
        issues_by_frame.setdefault(issue.frame_id, []).append(issue)

    if not issues_by_frame:
        return ""

    lines = [
        "## VISUAL CONTEXT",
        "Screenshots are attached for the issues below:",
    ]

    for fc in result.frame_captures:
        frame_issues = issues_by_frame.get(fc.screenshot_path, [])
        if not frame_issues:
            continue
        msg = "; ".join(i.message for i in frame_issues[:3])
        lines.append(f"- t={fc.timestamp:.2f}s: {msg}")

    return "\n".join(lines)
