#!/usr/bin/env python3
"""Verify every `path/to/file:LINE` reference in docs/ points at a real,
non-blank line. Run after editing code that the notes cite:

    python scripts/check_refs.py            # prints each ref and the line it hits
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = re.compile(r"(?<![\w/.:-])([\w.-]+(?:/[\w.-]+)*):(\d+)\b")
bad = 0
for doc in sorted((ROOT / "docs").rglob("*.md")):
    for path, line in sorted(set(REF.findall(doc.read_text(encoding="utf-8")))):
        target = ROOT / path
        n = int(line)
        if not target.is_file():
            if "/" not in path:
                continue  # "civicpulse.localhost:8081", "postgres:16" — not a file reference
            print(f"FAIL {doc.name}: {path}:{n} — no such file")
            bad += 1
            continue
        lines = target.read_text(encoding="utf-8").splitlines()
        if n > len(lines) or not lines[n - 1].strip():
            print(f"FAIL {doc.name}: {path}:{n} — line missing or blank")
            bad += 1
        else:
            print(f"ok   {path}:{n}  {lines[n - 1].strip()[:90]}")
sys.exit(1 if bad else 0)
