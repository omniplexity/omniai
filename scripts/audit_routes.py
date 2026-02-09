#!/usr/bin/env python3
"""Detect duplicate FastAPI routes."""
from __future__ import annotations
from collections import defaultdict

def main() -> int:
    from backend.main import app

    route_map = defaultdict(list)

    for r in app.router.routes:
        methods = tuple(sorted(getattr(r, "methods", []) or []))
        path = getattr(r, "path", None)
        name = getattr(r, "name", None)
        endpoint = getattr(r, "endpoint", None)
        qual = getattr(endpoint, "__qualname__", "") if endpoint else ""
        mod = getattr(endpoint, "__module__", "") if endpoint else ""
        if not path or not methods:
            continue
        key = (methods, path)
        route_map[key].append((name, f"{mod}:{qual}"))

    dupes = {k: v for k, v in route_map.items() if len(v) > 1}
    if not dupes:
        print("No duplicate method+path routes found.")
        return 0

    print("Duplicate method+path routes:")
    for (methods, path), entries in sorted(dupes.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"\n{methods} {path}")
        for name, target in entries:
            print(f"  - {name} -> {target}")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
