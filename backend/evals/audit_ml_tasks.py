"""Print the ML task type audit matrix: PASS, SKIP(slice) or FAIL per task type and stage.

    python -m evals.audit_ml_tasks

Runs tests/e2e/test_ml_task_types_audit.py offline (no network, no real model) and reads its JUnit XML.
Exit code 1 if any cell FAILS (or the run itself broke); skips never fail. See specs/ml-tasks/07-audit-and-test-plan.md.
"""
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = "tests/e2e/test_ml_task_types_audit.py"
TASKS = ("classification", "regression", "forecast", "grouping", "unusual")
STAGES = [f"A{i}" for i in range(1, 15)]
CELL = re.compile(r"test_cell\[(\w+)-(A\d+)\]")


def parse(xml_path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """(task, stage) -> (PASS | SKIP | FAIL, note)."""
    cells: dict[tuple[str, str], tuple[str, str]] = {}
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        m = CELL.search(case.get("name", ""))
        if not m:
            continue
        key = (m.group(1), m.group(2))
        bad = case.find("failure") if case.find("failure") is not None else case.find("error")
        skip = case.find("skipped")
        if bad is not None:
            cells[key] = ("FAIL", (bad.get("message") or "")[:120])
        elif skip is not None:
            note = re.sub(r"^slice ", "", skip.get("message") or "")
            cells[key] = ("SKIP", note.split(":")[0].replace(" not built", "").strip())
        else:
            cells[key] = ("PASS", "")
    return cells


def render(cells: dict) -> str:
    width = 10
    lines = ["task".ljust(15) + "".join(s.ljust(width) for s in STAGES)]
    for t in TASKS:
        row = t.ljust(15)
        for s in STAGES:
            st, note = cells.get((t, s), ("FAIL", "missing"))
            row += (st if st != "SKIP" else f"SKIP({note})").ljust(width)
        lines.append(row)
    counts = {k: sum(1 for v in cells.values() if v[0] == k) for k in ("PASS", "SKIP", "FAIL")}
    lines.append("")
    lines.append(f"PASS {counts['PASS']}  SKIP {counts['SKIP']}  FAIL {counts['FAIL']}  of {len(TASKS) * len(STAGES)} cells")
    for (t, s), (st, note) in sorted(cells.items()):
        if st == "FAIL":
            lines.append(f"FAIL {t} {s}: {note}")
    return "\n".join(lines)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "audit.xml"
        proc = subprocess.run([sys.executable, "-m", "pytest", TEST_FILE, "-q", "-p", "no:cacheprovider",
                               f"--junitxml={xml_path}"], cwd=ROOT, capture_output=True, text=True)
        if not xml_path.exists():
            print(proc.stdout[-2000:], proc.stderr[-2000:])
            print("the audit run did not produce a report")
            return 1
        cells = parse(xml_path)
    print(render(cells))
    expected = len(TASKS) * len(STAGES)
    return 1 if any(v[0] == "FAIL" for v in cells.values()) or len(cells) != expected else 0


if __name__ == "__main__":
    raise SystemExit(main())
