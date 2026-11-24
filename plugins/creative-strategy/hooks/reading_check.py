#!/usr/bin/env python3
"""Tell the agent which required references it has not yet read in full.

A PostToolUse hook for Claude Code and Codex. It stays silent until the
creative-performance-analysis skill is loaded in the session. From then on,
after each read or shell call, it credits every line of a required reference
that the call's output actually contained, whatever path, variable, glob or
saved-output file delivered it, and lists the references still incomplete.
Once every one is complete it says so once, then goes quiet.

It never blocks anything. On any error it prints nothing and exits 0. The
session ledger, in the system temp folder, keeps the skill's reference paths and
hashes of their delivered lines, never file, prompt or client text. Loading the
skill again starts a new check against the same ledger, so reading already done
in the session still counts. It is a best-effort notice, not proof that the
agent understood or applied what it read.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

SKILL_NAME = "creative-performance-analysis"
SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / SKILL_NAME
READ_TOOLS = {"Read", "read", "read_file", "view"}
SHELL_TOOLS = {"Bash", "bash", "shell", "exec_command", "local_shell"}
READERS = {"cat", "nl", "sed", "head", "tail", "bat", "less", "more", "awk", "type", "Get-Content", "gc"}
LINE_NUMBER = re.compile(r"^\s*\d+[\t\u2192:|]\s?")
MAX_INPUT = 8_000_000


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def required_units(skill_dir: Path = SKILL_DIR) -> list[dict]:
    """Each required unit: its label, file and the hashes of its non-blank lines."""
    spec = json.loads((skill_dir / "required-reading.json").read_text(encoding="utf-8"))
    units = []
    for entry in spec["required"]:
        path = (skill_dir / entry["path"]).resolve()
        lines = path.read_text(encoding="utf-8").splitlines()
        label = entry["path"]
        if "from" in entry:
            start = next(i for i, line in enumerate(lines) if line.strip() == entry["from"])
            end = next(i for i, line in enumerate(lines) if i > start and line.strip() == entry["to"])
            lines = lines[start:end]
            label = f'{entry["path"]} ("{entry["from"].lstrip("# ")}" up to "{entry["to"].lstrip("# ")}")'
        units.append({"label": label, "file": str(path),
                      "lines": sorted({digest(line.strip()) for line in lines if line.strip()})})
    return units


def ledger_path(session: str) -> Path:
    """One folder per session. Each hook call adds its own small file, so parallel tool calls never overwrite each other."""
    folder = Path(tempfile.gettempdir()) / "cpa-reading-check" / digest(session)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder


def load(folder: Path) -> dict:
    delivered = {}
    for part in folder.glob("delivered-*.json"):
        try:
            for key, lines in json.loads(part.read_text(encoding="utf-8")).items():
                delivered.setdefault(key, set()).update(lines)
        except (OSError, ValueError, AttributeError):
            continue
    return {"active": (folder / "active").exists(), "delivered": delivered}


def write_part(folder: Path, name: str, data) -> None:
    temporary = folder / f".{name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temporary, folder / name)


def announce_once(folder: Path) -> bool:
    """True for exactly one caller after each skill load, even when calls run in parallel."""
    try:
        os.close(os.open(folder / "announced", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except FileExistsError:
        return False


def text_of(response) -> str:
    """The text a tool returned, from the response shapes Claude Code and Codex use."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if isinstance(response.get("file"), dict):
            return str(response["file"].get("content", ""))
        for key in ("stdout", "output", "aggregated_output", "content", "text"):
            if key in response:
                return text_of(response[key])
        return ""
    if isinstance(response, list):
        return "\n".join(text_of(item) for item in response)
    return ""


def failed(response) -> bool:
    return isinstance(response, dict) and bool(response.get("is_error") or response.get("isError")
                                               or response.get("exit_code", 0) not in (0, None))


def read_paths(command: str, cwd: Path) -> list[Path]:
    """Files a shell command reads: arguments of a reading command, following `cd` in the same command."""
    found, here = [], cwd
    for segment in re.split(r"&&|\|\||[;|\n]", command):
        try:
            args = shlex.split(segment, comments=True)
        except ValueError:
            continue
        if not args:
            continue
        if args[0] == "cd" and len(args) > 1:
            here = (here / os.path.expanduser(args[1])).resolve()
            continue
        if args[0] == "rtk" and len(args) > 1:
            args = args[1:]
        if Path(args[0]).name not in READERS:
            continue
        for arg in args[1:]:
            if not arg.startswith("-") and arg.endswith(".md"):
                found.append((here / os.path.expanduser(arg)).resolve())
    return found


def is_skill_load(tool: str, given: dict, paths: list[Path], output: str) -> bool:
    if tool == "Skill" and str(given.get("skill", "")).split(":")[-1] == SKILL_NAME:
        return True
    skill_file = (SKILL_DIR / "SKILL.md").resolve()
    if any(path == skill_file or (path.name == "SKILL.md" and path.parent.name == SKILL_NAME) for path in paths):
        return True
    return f"name: {SKILL_NAME}" in output and "## Required reading" in output


def respond(payload: dict, skill_dir: Path = SKILL_DIR) -> str:
    session = str(payload.get("session_id") or "")
    if not session:
        return ""
    tool = str(payload.get("tool_name") or "")
    given = payload.get("tool_input") or {}
    if isinstance(given, str):
        try:
            given = json.loads(given)
        except ValueError:
            given = {"command": given}
    response = payload.get("tool_response")
    if failed(response) or not isinstance(given, dict):
        return ""
    output = text_of(response)
    cwd = Path(str(payload.get("cwd") or given.get("workdir") or given.get("cwd") or os.getcwd()))
    if tool in READ_TOOLS:
        paths = [(cwd / str(given.get("file_path") or given.get("path") or "")).resolve()]
    elif tool in SHELL_TOOLS:
        command = given.get("command") or given.get("cmd")
        command = " ".join(command) if isinstance(command, list) else str(command or "")
        paths = read_paths(command, cwd)
    else:
        paths = []

    folder = ledger_path(session)
    state = load(folder)
    loading = is_skill_load(tool, given, paths, output)
    if not state["active"] and not loading:
        return ""
    if loading:
        (folder / "active").touch()
        (folder / "announced").unlink(missing_ok=True)

    units = required_units(skill_dir)
    if tool in READ_TOOLS or tool in SHELL_TOOLS or tool == "Grep":
        got = {digest(LINE_NUMBER.sub("", line, count=1).strip()) for line in output.splitlines()}
        new = {}
        for unit in units:
            seen = got.intersection(unit["lines"]) - state["delivered"].get(unit["file"], set())
            if seen:
                new.setdefault(unit["file"], set()).update(seen)
        if new:
            write_part(folder, f"delivered-{os.getpid()}-{os.urandom(4).hex()}.json",
                       {key: sorted(lines) for key, lines in new.items()})
            for key, lines in new.items():
                state["delivered"].setdefault(key, set()).update(lines)

    missing = [unit["label"] for unit in units
               if not set(unit["lines"]) <= state["delivered"].get(unit["file"], set())]
    message = ""
    if missing:
        message = ("creative-performance-analysis: these required references are not yet read in full. "
                   "Read each one completely before the step that uses it, and before writing the analysis: "
                   + "; ".join(missing) + ".")
    elif announce_once(folder):
        message = "creative-performance-analysis: every required reference has been read in full."
    return message


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read(MAX_INPUT).decode("utf-8"))
        text = respond(payload)
    except Exception:  # a broken check must never stop the agent's work
        return 0
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
