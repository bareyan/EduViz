"""
Analysis repository - persistence for material analysis results.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import JOB_DATA_DIR


class AnalysisRepository(ABC):
    """Abstract repository for analysis result persistence."""

    @abstractmethod
    def save(self, analysis: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        pass


class FileBasedAnalysisRepository(AnalysisRepository):
    """File-based repository for analysis results."""
    _SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = ((base_dir or JOB_DATA_DIR) / "analysis").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _build_target(self, analysis_id: str) -> Optional[Path]:
        safe_id = str(analysis_id or "").strip()
        if not safe_id or not self._SAFE_ID_PATTERN.fullmatch(safe_id):
            return None

        target = (self.base_dir / f"{safe_id}.json").resolve()
        if target.parent != self.base_dir:
            return None
        return target

    def save(self, analysis: Dict[str, Any]) -> None:
        target = self._build_target(str(analysis.get("analysis_id", "")))
        if not target:
            raise ValueError("analysis must contain analysis_id")

        with open(target, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

    def get(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        target = self._build_target(analysis_id)
        if not target:
            return None
        if not target.exists() or not target.is_file():
            return None

        try:
            with open(target, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
