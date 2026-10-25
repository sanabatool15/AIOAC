"""Re-check the hand-checked dataset list against the live services. Network. Run by hand, never in tests.

    cd backend && python scripts/check_curated.py [--no-download]

For each item it prints OK or CHANGED with the differences: row count (within 2%), answer column present in the real
header, license, and that the dataset is still a plain table. Downloads each dataset once (the same limits as the app)
unless --no-download is given, in which case it only checks what the source reports. Nothing is executed or saved.
"""
import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.config import settings  # noqa: E402
from app.providers.datasets import build_registry  # noqa: E402
from app.providers.datasets.curated import load_curated  # noqa: E402


def check(item, registry, download: bool) -> list[str]:
    r = registry.resolve(item.id)
    if r is None:
        return [f"id {item.id} does not resolve through the registry"]
    problems = []
    info = r.entry.source.info(r.local_id)
    if not info.tabular:
        problems.append("no longer a plain table")
    if info.gated:
        problems.append("now gated")
    if info.rows and abs(info.rows - item.rows) > 0.02 * item.rows:
        problems.append(f"rows changed: list says {item.rows}, source says {info.rows}")
    lic = (info.license or "not stated").lower()
    if lic != item.license.lower():
        problems.append(f"license changed: list says {item.license}, source says {lic}")
    if info.target and info.target != item.target:
        problems.append(f"answer column changed: list says {item.target}, source says {info.target}")
    if download:
        f = r.entry.source.fetch_csv(r.local_id, settings.max_fetch_rows, settings.max_fetch_bytes)
        cols = list(pd.read_csv(io.BytesIO(f.csv_bytes), nrows=1).columns)
        if item.target not in cols:
            problems.append(f"answer column '{item.target}' is not in the downloaded table (columns start: {cols[:5]})")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()
    registry, bad = build_registry(), 0
    for item in load_curated():
        try:
            problems = check(item, registry, not args.no_download)
        except Exception as exc:  # a source being down is a result too
            problems = [f"could not check: {type(exc).__name__}: {exc}"]
        print(f"{'OK     ' if not problems else 'CHANGED'}  {item.id:<42} {item.name}")
        for p in problems:
            print(f"          - {p}")
        bad += bool(problems)
    print(f"\n{len(load_curated()) - bad} ok, {bad} need attention")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
