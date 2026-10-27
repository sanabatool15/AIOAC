"""View a past run: python -m evals.show <log_id or folder> [--tools] [--md] [--raw] [--level WARN]

Reads events.jsonl written by the eval runner or the notebook (backend/logs/...). A log id is the folder path under the
log directory, for example eval-20261101-101500/churn-subscription/r1. Give an eval batch folder to list its runs.
"""
import argparse
import json
import sys
from pathlib import Path

from app.services.agent.runlog import LEVELS, format_line, render_markdown

LOG_ROOT = Path(__file__).resolve().parents[1] / "logs"
TOOL_TYPES = {"tool_call", "tool_result", "tool_refused", "gate", "approval_card"}


def resolve(target: str, log_dir: Path | None = None) -> Path:
    p = Path(target)
    if p.exists():
        return p
    q = (log_dir or LOG_ROOT) / target
    if q.exists():
        return q
    raise FileNotFoundError(f"no log at {target} or {q}")


def event_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("events.jsonl"))


def load_events(folder: Path) -> list[dict]:
    out = []
    for f in event_files(folder):
        out += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def render(events: list[dict], tools: bool = False, md: bool = False, raw: bool = False, level: str = "INFO") -> str:
    if raw:
        return "\n".join(json.dumps(e) for e in events)
    if md:
        return render_markdown(events)
    floor = LEVELS[level]
    lines = []
    for e in events:
        if tools:
            if e["type"] not in TOOL_TYPES:
                continue
            if e["type"] == "tool_result":
                lines.append(format_line(e) + "\n      result: " + json.dumps(e.get("result"), default=str)[:600])
            else:
                lines.append(format_line(e))
        elif LEVELS.get(e["level"], 20) >= floor and not (e["type"] == "tool_call" and floor > LEVELS["DEBUG"]):
            lines.append(format_line(e))
    return "\n".join(lines)


def show_run(target: str, tools: bool = False, md: bool = False, raw: bool = False, level: str = "INFO",
             log_dir: Path | None = None, display: bool = False) -> str:
    """Return (and in a notebook, with display=True, render) the log of one run."""
    folder = resolve(target, log_dir)
    if (folder / "index.json").exists():
        rows = json.loads((folder / "index.json").read_text(encoding="utf-8"))
        text = "\n".join(f"{'PASS' if r['passed'] else 'FAIL'}  {r['case']} #{r['repeat']}  {r['folder']}"
                         + ("" if r["passed"] else "  failed: " + ", ".join(r["failed_checks"])) for r in rows)
    elif md and (folder / "transcript.md").exists() and not tools:
        text = (folder / "transcript.md").read_text(encoding="utf-8")
    else:
        text = render(load_events(folder), tools, md, raw, level)
    if display:
        try:
            from IPython.display import Markdown, display as ipy_display
            ipy_display(Markdown(text) if md else Markdown("```\n" + text + "\n```"))
        except ImportError:
            print(text)
    return text


def tail(n: int = 20, root: Path | None = None) -> str:
    """The newest n console lines of the newest log under the log directory (handy in a notebook)."""
    files = sorted((root or LOG_ROOT).rglob("events.jsonl"), key=lambda f: f.stat().st_mtime)
    if not files:
        return "(no logs yet)"
    return "\n".join(format_line(json.loads(l)) for l in files[-1].read_text(encoding="utf-8").splitlines()[-n:])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.show", description=__doc__.split("\n\n")[0])
    ap.add_argument("target", help="log id or folder (an eval batch folder lists its runs)")
    ap.add_argument("--tools", action="store_true", help="only tool calls, gate decisions and results")
    ap.add_argument("--md", action="store_true", help="print the Markdown transcript")
    ap.add_argument("--raw", action="store_true", help="print the raw JSON lines")
    ap.add_argument("--level", default="INFO", choices=list(LEVELS), help="lowest level to show (default INFO; DEBUG adds context)")
    ap.add_argument("--log-dir", default=str(LOG_ROOT))
    a = ap.parse_args(argv)
    try:
        print(show_run(a.target, a.tools, a.md, a.raw, a.level, Path(a.log_dir)))
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
