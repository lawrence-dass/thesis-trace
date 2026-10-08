"""Which tool calls did Lawrence have to approve by hand, and what shape were they?

    make permissions-audit                    # newest session transcript for this project
    make permissions-audit ARGS="<path.jsonl>" # a specific one
    make permissions-audit ARGS="--list"      # also print every manually approved call

Reads Claude Code's own session transcript (~/.claude/projects/<project-slug>/*.jsonl).
Each tool result carries a `permissionDecision`; `source: user_temporary` means a
human clicked approve. Transcripts from CLI versions before ~2.1.294 carry no
decisions at all, so an old session reports 0/0 — that is "not recorded", not
"no prompts".

Written 2026-10-08, when one session needed 63 manual approvals in auto mode and
the cause turned out to be command SHAPE (a `cd` prefix, paths outside the repo,
shell file edits, inline code) rather than risk or settings. CLAUDE.md "Command
shapes that defeat auto mode" holds the table this script produces; re-run it to
check the fix held rather than trusting it.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(PROJECT_ROOT))

SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cd-prefix", re.compile(r"^\s*cd ")),
    # `../`, a sibling checkout such as /…/ThesisTrace-bmad-upgrade, temp dirs, and
    # Claude's own transcript store.
    ("path-outside-project", re.compile(r"\.\./|/ThesisTrace-|/private/tmp|/\.claude/projects/")),
    ("shell-file-edit", re.compile(r"sed -i|>>|cat >|<<|\bcp |\bmv |\bln -s")),
    ("inline-code", re.compile(r"python3? (-c|-\s)|<<")),
    ("3+-segments", re.compile(r"(?:(?:&&|;|\|\|).*){2,}")),
)


def _tool_calls_and_decisions(path: Path) -> tuple[dict[str, tuple[str, str]], list[tuple[str, dict]]]:
    calls: dict[str, tuple[str, str]] = {}
    decisions: list[tuple[str, dict]] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "tool_use" and "id" in obj:
                inp = obj.get("input") or {}
                text = inp.get("command") or inp.get("file_path") or inp.get("skill") or json.dumps(inp)
                calls[obj["id"]] = (str(obj.get("name")), str(text))
            if "permissionDecision" in obj:
                content = (obj.get("message") or {}).get("content") or []
                tid = next(
                    (c["tool_use_id"] for c in content if isinstance(c, dict) and c.get("tool_use_id")),
                    None,
                )
                if tid:
                    decisions.append((tid, obj["permissionDecision"]))
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    for line in path.read_text().splitlines():
        try:
            walk(json.loads(line))
        except json.JSONDecodeError:
            continue
    return calls, decisions


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        candidates = sorted(TRANSCRIPTS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            print(f"no transcripts under {TRANSCRIPTS}")
            return 1
        paths = [candidates[-1]]
    path = paths[0]
    calls, decisions = _tool_calls_and_decisions(path)

    # One tool call can be logged more than once; count each (call, verdict) once.
    unique: dict[tuple[str, str], dict] = {}
    for tid, decision in decisions:
        group = "manual" if decision.get("source") == "user_temporary" else "auto"
        unique.setdefault((tid, group), decision)

    print(f"transcript: {path.name}")
    if not unique:
        print("no permission decisions recorded (older CLI versions did not log them)")
        return 0

    shape_counts = {"manual": Counter(), "auto": Counter()}
    totals = Counter()
    manual_calls: list[tuple[str, str]] = []
    for (tid, group), _decision in unique.items():
        name, text = calls.get(tid, ("?", ""))
        if group == "manual":
            manual_calls.append((name, text))
        if name != "Bash":
            continue
        totals[group] += 1
        for label, pattern in SHAPES:
            if pattern.search(text):
                shape_counts[group][label] += 1

    print(f"manual approvals: {len(manual_calls)} "
          f"({sum(1 for n, _ in manual_calls if n == 'AskUserQuestion')} were questions, not permissions)")
    print(f"bash calls: {totals['manual']} manual, {totals['auto']} auto-approved\n")
    print(f"{'shape':24} {'manual':>8} {'auto':>8}")
    for label, _ in SHAPES:
        m = shape_counts["manual"][label]
        a = shape_counts["auto"][label]
        print(f"{label:24} {100 * m // max(totals['manual'], 1):7}% {100 * a // max(totals['auto'], 1):7}%")

    if "--list" in argv:
        print("\nmanually approved:")
        for name, text in manual_calls:
            print(f"  [{name}] {text.replace(chr(10), ' ')[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
