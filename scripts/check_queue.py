#!/usr/bin/env python3
"""Script to check spool queue status."""
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import settings


def list_files(dir_path: Path, suffix: str):
    if not dir_path.exists():
        return []
    files = [p for p in dir_path.iterdir() if p.is_file() and p.suffix == suffix]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def main():
    print("Spool Queue Status")
    print("=" * 50)
    tw = settings.SPOOL_TEAMWORK_DIR
    ms = settings.SPOOL_MISSIVE_DIR
    print(f"Teamwork spool dir: {tw}")
    print(f"Missive spool dir:  {ms}")
    print(f"Retry cadence (s):  {settings.SPOOL_RETRY_SECONDS}")
    print()

    for name, dir_path in (("Teamwork", tw), ("Missive", ms)):
        evt = list_files(dir_path, ".evt")
        rty = list_files(dir_path, ".retry")
        print(f"[{name}] pending: {len(evt)}  retry: {len(rty)}")
        # Show up to 5 oldest of each
        for label, files in (("evt", evt[:5]), ("retry", rty[:5])):
            for p in files:
                age = int(time.time() - p.stat().st_mtime)
                wait = max(0, settings.SPOOL_RETRY_SECONDS - age) if label == "retry" else 0
                print(f"  {label}: {p.name}  age={age}s  wait={wait}s")
        print()


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()

