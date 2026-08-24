#!/usr/bin/env python3
"""Fail if the Chippi north star drifted under 10000 paying Team/Team Plus accounts.

Chippi's accepted outcome is tens of thousands of paying Team or Team Plus
brokerage accounts (numeric floor 10000). A 1000-account substitute is not
accepted. This does not rewrite Company OS. It only guards the Chippi instance.

Usage:
  python3 assert_chippi_north_star.py
  python3 assert_chippi_north_star.py --instance /workspace/studio/chippi
  python3 assert_chippi_north_star.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

MIN_PAYING = 10000
STANDALONE_1000 = re.compile(r"(^|[^0-9])1000([^0-9]|$)")
YEAR = re.compile(r"^(19|20)\d{2}$")
NUM = re.compile(r"\d+")
TENS = re.compile(r"tens of thousands", re.IGNORECASE)
PAYING_HINT = re.compile(r"paying|team plus|brokerage account", re.IGNORECASE)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"missing {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must be a JSON object")
    return value


def paying_numbers(text: str) -> list[int]:
    found: list[int] = []
    for match in NUM.finditer(text or ""):
        token = match.group()
        if YEAR.fullmatch(token):
            continue
        number = int(token)
        if number <= 31:
            continue
        found.append(number)
    return found


def check_text(label: str, text: str, *, require_floor: bool = True) -> list[str]:
    errors: list[str] = []
    blob = text or ""
    if STANDALONE_1000.search(blob):
        errors.append(f"{label} contains standalone 1000: {blob!r}")
    numbers = paying_numbers(blob)
    under = [n for n in numbers if n < MIN_PAYING]
    if under:
        errors.append(f"{label} has paying-account target {under} under {MIN_PAYING}: {blob!r}")
    if require_floor and PAYING_HINT.search(blob) and not TENS.search(blob) and not any(n >= MIN_PAYING for n in numbers):
        errors.append(f"{label} is a paying-account north star without tens of thousands / {MIN_PAYING}+: {blob!r}")
    return errors


def check_instance(root: Path) -> list[str]:
    errors: list[str] = []
    blueprint_path = root / "blueprint.v1.json"
    blueprint = load_json(blueprint_path)
    for objective in blueprint.get("objectives") or []:
        if not isinstance(objective, dict):
            continue
        oid = str(objective.get("id") or "")
        fields = {
            "outcome": str(objective.get("outcome") or ""),
            "target": str(objective.get("target") or ""),
            "metric": str(objective.get("metric") or ""),
        }
        paying = oid == "objective-paying-teams" or any(PAYING_HINT.search(v) for v in fields.values())
        if not paying:
            continue
        for name, value in fields.items():
            require_floor = name in {"outcome", "target"}
            errors.extend(check_text(f"{blueprint_path} objectives.{oid}.{name}", value, require_floor=require_floor))
    kg_path = root / "compiled" / "knowledge-graph.json"
    kg = load_json(kg_path)
    for node in kg.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        if node.get("kind") != "objective" and "objective-paying" not in str(node.get("id") or ""):
            continue
        errors.extend(check_text(f"{kg_path} node {node.get('id')}", str(node.get("label") or "")))
    control_path = root / ".company-os" / "control.json"
    control = load_json(control_path)
    north = ((control.get("strategy") or {}) if isinstance(control.get("strategy"), dict) else {}).get("north_star")
    errors.extend(check_text(f"{control_path} strategy.north_star", str(north or "")))
    return errors


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "compiled").mkdir()
        (root / ".company-os").mkdir()
        good_bp = {
            "objectives": [
                {
                    "id": "objective-paying-teams",
                    "outcome": "Tens of thousands of paying Team or Team Plus brokerage accounts",
                    "target": "At least 10000 paying Team or Team Plus brokerage accounts",
                    "metric": "Paying Team or Team Plus brokerage accounts",
                    "baseline": "0 paying Team or Team Plus brokerage accounts as of 2026-08-15",
                    "horizon": "2026-12-31",
                }
            ]
        }
        (root / "blueprint.v1.json").write_text(json.dumps(good_bp))
        (root / "compiled" / "knowledge-graph.json").write_text(
            json.dumps({"nodes": [{"id": "objective:objective-paying-teams", "kind": "objective", "label": "Tens of thousands of paying Team or Team Plus brokerage accounts"}]})
        )
        (root / ".company-os" / "control.json").write_text(
            json.dumps({"strategy": {"north_star": "Tens of thousands of paying Team or Team Plus brokerage accounts by 2026-12-31 (at least 10000). Baseline 0."}})
        )
        good = check_instance(root)
        if good:
            print("self-test failed: good instance rejected", good, file=sys.stderr)
            return 1
        bad_bp = json.loads(json.dumps(good_bp))
        bad_bp["objectives"][0]["target"] = "1000 paying Team or Team Plus brokerage accounts"
        (root / "blueprint.v1.json").write_text(json.dumps(bad_bp))
        bad = check_instance(root)
        if not bad:
            print("self-test failed: 1000 target was accepted", file=sys.stderr)
            return 1
        print("self-test ok")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path, default=Path("/workspace/studio/chippi"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    errors = check_instance(args.instance)
    if errors:
        print("FAIL Chippi north star guard:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1
    print(f"ok {args.instance} north star is tens of thousands / {MIN_PAYING}+")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
