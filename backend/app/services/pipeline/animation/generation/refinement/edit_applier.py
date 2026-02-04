from typing import Any, Dict, List, Tuple

from app.core import get_logger

logger = get_logger(__name__, component="animation_refinement")


def apply_edits_atomically(code: str, edits: List[Dict[str, str]]) -> Tuple[str, Dict[str, Any]]:
    """Sequentially applies code modifications."""
    buffer = code
    successful_edits = 0
    failed_edits = 0
    failure_reasons = {
        "empty_search_text": 0,
        "not_found": 0,
        "ambiguous": 0,
        "exception": 0,
    }

    logger.info(f"📝 Applying {len(edits)} surgical edit(s)...")

    for idx, edit in enumerate(edits, 1):
        try:
            search_text = edit.get("search_text", "")
            replacement_text = edit.get("replacement_text", "")

            if not search_text:
                logger.warning(f"  Edit {idx}: ❌ SKIPPED - empty search_text")
                failed_edits += 1
                failure_reasons["empty_search_text"] += 1
                continue

            occurrences = buffer.count(search_text)
            if occurrences == 0:
                logger.warning(f"  Edit {idx}: ❌ FAILED - search text not found")
                logger.debug(f"    Searched for: {search_text[:100]}...")
                failed_edits += 1
                failure_reasons["not_found"] += 1
                continue
            if occurrences > 1:
                logger.warning(f"  Edit {idx}: ❌ FAILED - ambiguous ({occurrences} matches)")
                logger.debug(f"    Ambiguous text: {search_text[:100]}...")
                failed_edits += 1
                failure_reasons["ambiguous"] += 1
                continue

            buffer = buffer.replace(search_text, replacement_text)
            logger.info(f"  Edit {idx}: ✅ SUCCESS - applied surgical fix")
            logger.debug(f"    Replaced {len(search_text)} chars with {len(replacement_text)} chars")
            successful_edits += 1

        except Exception as e:
            logger.error(f"  Edit {idx}: ❌ EXCEPTION - {e}")
            failed_edits += 1
            failure_reasons["exception"] += 1

    # Summary
    logger.info(
        f"📊 Edit summary: {successful_edits} successful, {failed_edits} failed (out of {len(edits)} total)",
        extra={
            "successful_edits": successful_edits,
            "failed_edits": failed_edits,
            "total_edits": len(edits)
        }
    )
    primary_reason = None
    if failed_edits > 0:
        primary_reason = max(failure_reasons, key=failure_reasons.get)

    return buffer, {
        "successful": successful_edits,
        "failed": failed_edits,
        "total": len(edits),
        "primary_failure_reason": primary_reason,
        "failure_reasons": failure_reasons,
    }
