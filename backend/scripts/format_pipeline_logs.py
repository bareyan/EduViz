"""
Format pipeline logs from JSON to human-readable format
Usage: python format_pipeline_logs.py [log_file]
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def format_timestamp(ts_str: str) -> str:
    """Convert ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime('%H:%M:%S.%f')[:-3]
    except:
        return ts_str

def format_log_entry(entry: dict) -> str:
    """Format a single log entry"""
    lines = []
    
    # Header line with timestamp and level
    time = format_timestamp(entry.get('timestamp', ''))
    level = entry.get('level', 'INFO')
    job_id = entry.get('job_id', 'N/A')
    message = entry.get('message', '')
    
    # Color codes
    colors = {
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'DEBUG': '\033[36m',    # Cyan
        'RESET': '\033[0m'
    }
    color = colors.get(level, colors['RESET'])
    reset = colors['RESET']
    
    lines.append(f"{color}[{time}] {level:7s}{reset} | Job: {job_id[:12]}")
    lines.append(f"  📝 {message}")
    
    # Extract extra data
    extra = entry.get('extra', {})
    
    # Pipeline stage
    if 'pipeline_stage' in extra:
        stage = extra['pipeline_stage']
        stage_icons = {
            'code_generated': '🔨',
            'visual_qc_input': '👁️',
            'visual_qc_confirmed': '✅',
            'visual_qc_false_positive': '❌'
        }
        icon = stage_icons.get(stage, '⚙️')
        lines.append(f"  {icon} Stage: {stage}")
    
    # Refinement stage
    if 'refinement_stage' in extra:
        stage = extra['refinement_stage']
        stage_icons = {
            'triage_summary': '📊',
            'triage_routing': '🔀',
            'deterministic_fix': '🔧',
            'llm_fix': '🤖',
            'pattern_fix': '🔍'
        }
        icon = stage_icons.get(stage, '⚙️')
        lines.append(f"  {icon} Refinement: {stage}")
    
    # Section info
    if 'section_title' in extra:
        lines.append(f"  📄 Section: {extra['section_title']}")
    if 'turn' in extra:
        lines.append(f"  🔄 Turn: {extra['turn']}")
    
    # Issue counts
    if 'total_issues' in extra:
        lines.append(f"  🐛 Total Issues: {extra['total_issues']}")
    if 'certain_issues' in extra:
        lines.append(f"     ├─ Certain: {extra['certain_issues']}")
    if 'uncertain_issues' in extra:
        lines.append(f"     └─ Uncertain: {extra['uncertain_issues']}")
    
    # Individual issue details
    if 'issues' in extra and isinstance(extra['issues'], list):
        if len(extra['issues']) > 0:
            lines.append(f"  📋 Issues:")
            for i, issue in enumerate(extra['issues'][:5], 1):  # Show first 5
                severity = issue.get('severity', 'N/A')
                category = issue.get('category', 'N/A')
                is_certain = issue.get('is_certain', False)
                certainty = '✓ Certain' if is_certain else '? Uncertain'
                msg = issue.get('message', '')[:60]
                lines.append(f"     {i}. [{severity}] {category} - {certainty}")
                if msg:
                    lines.append(f"        {msg}")
            if len(extra['issues']) > 5:
                lines.append(f"     ... and {len(extra['issues']) - 5} more")
    
    # Fix details
    if 'issue_category' in extra:
        lines.append(f"  🔧 Fixed: {extra['issue_category']}")
    if 'fix_type' in extra:
        lines.append(f"     Type: {extra['fix_type']}")
    if 'success' in extra:
        status = '✅' if extra['success'] else '❌'
        lines.append(f"     {status} Success: {extra['success']}")
    
    # Visual QC details
    if 'uncertain_issues_count' in extra:
        lines.append(f"  👁️  Sent to QC: {extra['uncertain_issues_count']} issues")
    if 'confirmed_false_positives' in extra:
        lines.append(f"  ❌ False Positives: {extra['confirmed_false_positives']}")
    if 'whitelisted_keys' in extra and extra['whitelisted_keys']:
        keys = extra['whitelisted_keys'][:3]
        lines.append(f"  🗒️  Whitelisted: {', '.join(k[:8] + '...' for k in keys)}")
    
    # Code length
    if 'code_length' in extra:
        lines.append(f"  📏 Code Length: {extra['code_length']} chars")
    
    return '\n'.join(lines)

def main():
    # Get log file path
    if len(sys.argv) > 1:
        log_file = Path(sys.argv[1])
    else:
        log_file = Path("logs/animation_pipeline.jsonl")
    
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        return
    
    print(f"{'='*80}")
    print(f"Pipeline Logs: {log_file.name}")
    print(f"{'='*80}\n")
    
    # Read and format each line
    with open(log_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
                formatted = format_log_entry(entry)
                print(formatted)
                print()  # Blank line between entries
            except json.JSONDecodeError as e:
                print(f"⚠️  Line {line_num}: Invalid JSON - {e}")
                continue
    
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
