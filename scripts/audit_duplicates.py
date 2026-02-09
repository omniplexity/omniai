#!/usr/bin/env python3
"""Detect duplicate files by SHA256 hash."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from collections import defaultdict

EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
EXCLUDE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".mp4", ".mov", ".avi", ".mkv"}

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    root = Path(".").resolve()
    groups: dict[str, list[Path]] = defaultdict(list)

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = dp / fn
            if p.suffix.lower() in EXCLUDE_EXTS:
                continue
            try:
                if p.is_symlink() or not p.is_file():
                    continue
                digest = sha256_file(p)
                groups[digest].append(p.relative_to(root))
            except (OSError, PermissionError):
                continue

    dups = {k: v for k, v in groups.items() if len(v) > 1}
    if not dups:
        print("No duplicates found.")
        return 0

    print("Duplicate file groups (sha256):")
    for digest, files in sorted(dups.items(), key=lambda kv: len(kv[1]), reverse=True):
        print(f"\n{digest} ({len(files)} files)")
        for f in files:
            print(f"  - {f}")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
