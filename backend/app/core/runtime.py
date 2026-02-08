"""
Runtime environment guards and dependency checks.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, List

from fastapi import HTTPException


REQUIRED_RENDER_TOOLS = ("ffmpeg", "ffprobe", "manim")


def parse_bool_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def missing_runtime_tools(tools: Iterable[str]) -> List[str]:
    return [tool for tool in tools if shutil.which(tool) is None]


def assert_runtime_tools_available(tools: Iterable[str], *, context: str) -> None:
    missing = missing_runtime_tools(tools)
    if missing:
        missing_list = ", ".join(sorted(set(missing)))
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: missing required runtime tools for {context}: {missing_list}",
        )


def assert_directory_writable(path: Path, *, create: bool = True) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.is_dir():
        raise RuntimeError(f"Required directory is missing: {path}")

    probe = path / f".write_probe_{os.getpid()}.tmp"
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Directory is not writable: {path}") from exc


def run_startup_runtime_checks(
    *,
    output_dir: Path,
    upload_dir: Path,
    strict_tools: bool,
    strict_dirs: bool = True,
) -> Dict[str, object]:
    report: Dict[str, object] = {
        "directories": {},
        "tools": {},
        "ok": True,
    }

    for dir_name, dir_path in (("output", output_dir), ("upload", upload_dir)):
        try:
            assert_directory_writable(dir_path)
            report["directories"][dir_name] = {"path": str(dir_path), "writable": True}
        except Exception as exc:
            report["directories"][dir_name] = {
                "path": str(dir_path),
                "writable": False,
                "error": str(exc),
            }
            report["ok"] = False
            if strict_dirs:
                raise

    missing = missing_runtime_tools(REQUIRED_RENDER_TOOLS)
    report["tools"] = {
        "required": list(REQUIRED_RENDER_TOOLS),
        "missing": missing,
    }
    if missing and strict_tools:
        report["ok"] = False
        raise RuntimeError(
            "Missing required runtime tools: " + ", ".join(missing)
        )

    return report
