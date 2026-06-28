"""Skill loader (T031, US3, research R3).

A skill is a directory with a manifest (skill.json: name, description,
input_schema) and an entry point — either a Python callable (module:function)
or a subprocess script. Skills register behind the same tool contract as MCP.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
from pathlib import Path

from src.config import get_settings
from src.models.entities import RiskLevel
from src.tools.registry import ToolDescriptor, register

logger = logging.getLogger(__name__)


def _run_subprocess(skill_dir: Path, entry: list[str]):
    # entry[0] is the interpreter/program (kept as-is); remaining args that are
    # relative filenames present in the skill dir are resolved there.
    resolved = [entry[0]]
    for arg in entry[1:]:
        if os.path.isabs(arg):
            resolved.append(arg)
        elif (skill_dir / arg).exists():
            resolved.append(str(skill_dir / arg))
        else:
            resolved.append(arg)
    cmd = resolved

    async def _exec(arguments: dict) -> dict:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdin = json.dumps(arguments).encode()
        out, err = await asyncio.wait_for(proc.communicate(stdin), timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"skill exited {proc.returncode}: {err.decode()[:500]}")
        return json.loads(out.decode() or "{}")

    return _exec


def _make_callable(entry: str):
    module_name, _, func_name = entry.partition(":")
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name)

    async def _exec(arguments: dict) -> dict:
        result = fn(arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return result if isinstance(result, dict) else {"result": str(result)}

    return _exec


def load_skills(skills_dir: str | None = None) -> list[ToolDescriptor]:
    """Scan a skills directory and register each skill as a tool (research R3)."""
    base = Path(skills_dir or get_settings().skills_dir)
    if not base.is_dir():
        return []
    descriptors: list[ToolDescriptor] = []
    for skill_dir in base.iterdir():
        if not skill_dir.is_dir():
            continue
        manifest = skill_dir / "skill.json"
        if not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            logger.warning("invalid manifest: %s", manifest)
            continue
        entry = m.get("entry")  # "module:function" or ["python", "run.py"]
        if entry is None:
            continue
        if isinstance(entry, list):
            executor = _run_subprocess(skill_dir, entry)
        else:
            executor = _make_callable(entry)
        desc = ToolDescriptor(
            name=m["name"],
            description=m.get("description", f"skill {m['name']}"),
            source_type="skill",
            input_schema=m.get("input_schema", {"type": "object"}),
            risk_level=RiskLevel(m.get("risk_level", "none")),
            timeout_seconds=m.get("timeout_seconds", 60),
        )
        register(desc, executor)
        descriptors.append(desc)
    logger.info("loaded %d skills from %s", len(descriptors), base)
    return descriptors
