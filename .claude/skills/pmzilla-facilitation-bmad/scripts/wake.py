#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Waking — load the agent's sanctum in one pass, or route to First Breath.

Run on activation. Determines the mode from the filesystem (and the --pulse
flag) and, when the sanctum exists, prints the full identity in a single read
(INDEX, PERSONA, CREED, BOND, MEMORY, CAPABILITIES) so the agent becomes itself
in one shot instead of six. In --pulse mode it also appends PULSE.md. When no
sanctum exists, it prints a directive to run First Breath.

This loads runtime memory only. It never reads or writes config or customize.toml.

The project root is computed from the location of this script (it is the same
in .claude/skills/<skill>/scripts/ and in _bmad/memory/<skill>/scripts/). Every
mode prints "Project root:" and "Sanctum:" right after the MODE line.

Usage:
    uv run wake.py [<project-root>] [--pulse]

    project-root: Optional. Ignored (with a warning on stderr) when it differs
                  from the computed root.
"""

import importlib.util
import re
import sys
from pathlib import Path

SKILL_NAME = "pmzilla-facilitation-bmad"
POSTURE = "facilitation"
PROJECT_ROOT = Path(__file__).resolve().parents[4]

# Load order — the "become yourself" set.
IDENTITY_FILES = [
    "INDEX.md",
    "PERSONA.md",
    "CREED.md",
    "BOND.md",
    "MEMORY.md",
    "CAPABILITIES.md",
]

def emit(path: Path) -> None:
    print(f"\n===== {path.name} =====")
    try:
        print(path.read_text(encoding="utf-8").rstrip())
    except FileNotFoundError:
        print(f"(missing: {path.name})")

IMPORT_LINE = re.compile(r"^\s*@(\S+)\s*$")


def missing_imports(project_root: Path) -> list[str]:
    """Files that CLAUDE.md imports with `@path` and that do not exist (a typo loses the context silently)."""
    claude_md = project_root / "CLAUDE.md"
    try:
        lines = claude_md.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    found = [m.group(1) for m in map(IMPORT_LINE.match, lines) if m]
    return [name for name in found if not (project_root / name).is_file()]


def outside_library(project_root: Path) -> list[str]:
    """Lines of the list of works absent from the library, computed from the catalogue (tools/outside_library.py)."""
    script = project_root / "tools" / "outside_library.py"
    try:
        spec = importlib.util.spec_from_file_location("outside_library", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.rendre(POSTURE)
    except ModuleNotFoundError as error:
        return [f"(list not computed: the Python module \"{error.name}\" is missing. Run this script with `uv run scripts/wake.py`, "
                "which installs its dependencies, and not with `python3`. Assume nothing: whatever the search does not return is absent from the library: write the out-of-library formula of your response language (CLAUDE.md table).)"]
    except Exception as error:  # the list is help, never a reason to fail the wake
        return [f"(list not computed: {error})"]


def book_relations(project_root: Path) -> list[str]:
    """Links between works (comments on, not to be confused with), from tools/references_postures.yaml."""
    script = project_root / "tools" / "outside_library.py"
    try:
        spec = importlib.util.spec_from_file_location("outside_library", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.rendre_relations(POSTURE)
    except Exception:  # already reported by outside_library
        return []


def context_map(project_root: Path) -> list[str]:
    """Lines of the organisation context map (date, nature, review date, stale mark, capped body), from tools/context_lab.py.
    It reads the map file and nothing else of the context folder; read-only."""
    script = project_root / "tools" / "context_lab.py"
    try:
        spec = importlib.util.spec_from_file_location("context_lab", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.wake_map_lines(project_root)
    except Exception as error:  # the map is help, never a reason to fail the wake
        return [f"(context map not computed: {error})"]


def emit_context_and_library(project_root: Path) -> None:
    for name in missing_imports(project_root):
        print(f"\n!!! LOCAL FILE MISSING: {name} (imported by CLAUDE.md). The user's context is not loaded.")
        print("Tell the user in your first answer (typo, file not created?) and work without context instead of inventing one.")
    print("\n===== WORKS ABSENT FROM THE LIBRARY (computed from the user's catalogue) =====")
    print("These works that your rules cite are not in the user's library: when you draw on them, write the out-of-library formula of your response language (CLAUDE.md table).")
    print("\n".join(outside_library(project_root)))
    relations = book_relations(project_root)
    if relations:
        print("\n===== RELATIONS ENTRE OUVRAGES (relations between works, not to be confused) =====")
        print("\n".join(relations))
    print("\n===== CONTEXT MAP (starting context: a dated statement of the organisation, not a reference; it does not replace the clarification questions) =====")
    print("\n".join(context_map(project_root)))


def main() -> int:
    args = sys.argv[1:]
    pulse = "--pulse" in args
    positional = [a for a in args if not a.startswith("--")]
    if len(positional) > 1:
        print("Usage: wake.py [<project-root>] [--pulse]", file=sys.stderr)
        return 2

    project_root = PROJECT_ROOT
    if positional and Path(positional[0]).resolve() != project_root:
        print(f"argument ignored: using {project_root}", file=sys.stderr)
    sanctum = project_root / "_bmad" / "memory" / SKILL_NAME

    core_ok = (
        sanctum.is_dir()
        and (sanctum / "CREED.md").is_file()
        and (sanctum / "MEMORY.md").is_file()
    )
    if not core_ok:
        print("MODE: FIRST_BREATH")
        print(f"Project root: {project_root}")
        print(f"Sanctum: {sanctum}")
        print(f"NO SANCTUM at {sanctum}")
        print("This is your one birth. Load references/first-breath.md and follow it.")
        emit_context_and_library(project_root)
        return 0

    print("MODE: PULSE" if pulse else "MODE: WAKING")
    print(f"Project root: {project_root}")
    print(f"Sanctum: {sanctum}")
    for name in IDENTITY_FILES:
        emit(sanctum / name)
    if pulse:
        emit(sanctum / "PULSE.md")
    emit_context_and_library(project_root)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
