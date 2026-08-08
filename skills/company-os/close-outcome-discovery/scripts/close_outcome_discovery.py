#!/usr/bin/env python3
"""Apply cited domain discovery evidence to an outcome request."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REPORT_SCHEMA = "company-os.outcome-discovery-report.v1"
REQUEST_SCHEMA = "company-os.outcome-request.v1"


class DiscoveryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiscoveryError("E_SCHEMA", f"{path} must contain an object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError("E_SCHEMA", f"{label} must be non-empty")
    return value


def unique_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise DiscoveryError("E_SCHEMA", f"{label} must be an array")
    result = [text(item, f"{label}[]") for item in value]
    if len(result) != len(set(result)):
        raise DiscoveryError("E_DUPLICATE", f"{label} contains duplicates")
    return sorted(result)


def validate_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if report.get("$schema") != REPORT_SCHEMA:
        raise DiscoveryError("E_SCHEMA", f"$schema must be {REPORT_SCHEMA}")
    allowed = {"$schema", "objective_id", "request_sha256", "resolutions", "domain_hypotheses"}
    extra = sorted(set(report) - allowed)
    if extra:
        raise DiscoveryError("E_SCHEMA", f"unknown report keys: {', '.join(extra)}")
    objective_id = text(report.get("objective_id"), "objective_id")
    request_sha256 = text(report.get("request_sha256"), "request_sha256")
    if len(request_sha256) != 64:
        raise DiscoveryError("E_SCHEMA", "request_sha256 must be sha256")

    resolutions = report.get("resolutions")
    if not isinstance(resolutions, list):
        raise DiscoveryError("E_SCHEMA", "resolutions must be an array")
    seen: set[str] = set()
    normalized_resolutions = []
    for item in resolutions:
        if not isinstance(item, dict):
            raise DiscoveryError("E_SCHEMA", "resolution must be an object")
        unknown_id = text(item.get("unknown_id"), "resolution.unknown_id")
        if unknown_id in seen:
            raise DiscoveryError("E_DUPLICATE", f"duplicate resolution {unknown_id}")
        seen.add(unknown_id)
        conclusion = text(item.get("conclusion"), f"{unknown_id}.conclusion")
        citations = unique_strings(item.get("citations"), f"{unknown_id}.citations")
        if not citations:
            raise DiscoveryError("E_EVIDENCE", f"{unknown_id} cannot resolve without citations")
        counterevidence = unique_strings(item.get("counterevidence", []), f"{unknown_id}.counterevidence")
        reconciliation = item.get("reconciliation")
        if counterevidence:
            reconciliation = text(reconciliation, f"{unknown_id}.reconciliation")
        elif reconciliation is not None:
            reconciliation = text(reconciliation, f"{unknown_id}.reconciliation")
        closure_evidence = unique_strings(item.get("closure_evidence"), f"{unknown_id}.closure_evidence")
        if not closure_evidence:
            raise DiscoveryError("E_EVIDENCE", f"{unknown_id} requires closure evidence")
        normalized_resolutions.append({
            "unknown_id": unknown_id,
            "conclusion": conclusion,
            "citations": citations,
            "counterevidence": counterevidence,
            "reconciliation": reconciliation,
            "closure_evidence": closure_evidence,
        })

    hypotheses = report.get("domain_hypotheses", [])
    if not isinstance(hypotheses, list):
        raise DiscoveryError("E_SCHEMA", "domain_hypotheses must be an array")
    normalized_hypotheses = []
    hseen: set[str] = set()
    for item in hypotheses:
        if not isinstance(item, dict):
            raise DiscoveryError("E_SCHEMA", "domain hypothesis must be an object")
        domain_id = text(item.get("domain_id"), "domain_id")
        if domain_id in hseen:
            raise DiscoveryError("E_DUPLICATE", f"duplicate domain hypothesis {domain_id}")
        hseen.add(domain_id)
        hypothesis = text(item.get("hypothesis"), f"{domain_id}.hypothesis")
        status = item.get("status")
        if status not in {"hypothesis", "supported", "refuted"}:
            raise DiscoveryError("E_SCHEMA", f"{domain_id}.status invalid")
        sources = unique_strings(item.get("source_bindings"), f"{domain_id}.source_bindings")
        if not sources:
            raise DiscoveryError("E_EVIDENCE", f"{domain_id} requires source bindings")
        normalized_hypotheses.append({
            "domain_id": domain_id,
            "hypothesis": hypothesis,
            "status": status,
            "source_bindings": sources,
        })

    return {
        "$schema": REPORT_SCHEMA,
        "objective_id": objective_id,
        "request_sha256": request_sha256,
        "resolutions": sorted(normalized_resolutions, key=lambda item: item["unknown_id"]),
        "domain_hypotheses": sorted(normalized_hypotheses, key=lambda item: item["domain_id"]),
    }


def apply_report(request: Mapping[str, Any], raw_report: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("$schema") != REQUEST_SCHEMA:
        raise DiscoveryError("E_SCHEMA", f"request $schema must be {REQUEST_SCHEMA}")
    original = copy.deepcopy(dict(request))
    report = validate_report(raw_report)
    if report["objective_id"] != request.get("objective_id"):
        raise DiscoveryError("E_BINDING", "objective_id mismatch")
    if report["request_sha256"] != digest(request):
        raise DiscoveryError("E_BINDING", "report is not bound to the exact request")

    unknowns = request.get("unknowns")
    if not isinstance(unknowns, list):
        raise DiscoveryError("E_SCHEMA", "request unknowns must be an array")
    unknown_map = {
        text(item.get("unknown_id"), "unknown.unknown_id"): copy.deepcopy(item)
        for item in unknowns
        if isinstance(item, dict)
    }

    for resolution in report["resolutions"]:
        unknown_id = resolution["unknown_id"]
        if unknown_id not in unknown_map:
            raise DiscoveryError("E_UNKNOWN", f"report resolves unknown id not in request: {unknown_id}")
        required = set(unknown_map[unknown_id].get("closure_evidence", []))
        supplied = set(resolution["closure_evidence"])
        if required and not required.issubset(supplied):
            missing = ", ".join(sorted(required - supplied))
            raise DiscoveryError("E_EVIDENCE", f"{unknown_id} missing required closure evidence: {missing}")
        unknown_map[unknown_id]["resolved"] = True
        unknown_map[unknown_id]["resolution"] = resolution["conclusion"]
        unknown_map[unknown_id]["resolution_citations"] = resolution["citations"]
        unknown_map[unknown_id]["resolution_counterevidence"] = resolution["counterevidence"]
        if resolution["reconciliation"] is not None:
            unknown_map[unknown_id]["resolution_reconciliation"] = resolution["reconciliation"]

    updated = copy.deepcopy(dict(request))
    updated["unknowns"] = sorted(unknown_map.values(), key=lambda item: item["unknown_id"])

    existing_domains = {
        item["domain_id"]: copy.deepcopy(item)
        for item in request.get("domain_hypotheses", [])
        if isinstance(item, dict) and isinstance(item.get("domain_id"), str)
    }
    for hypothesis in report["domain_hypotheses"]:
        existing_domains[hypothesis["domain_id"]] = hypothesis
    updated["domain_hypotheses"] = sorted(existing_domains.values(), key=lambda item: item["domain_id"])

    if updated.get("objective") != original.get("objective"):
        raise DiscoveryError("E_OBJECTIVE_DRIFT", "discovery may not alter original objective")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--request", required=True, type=Path)
    apply_parser.add_argument("--report", required=True, type=Path)
    apply_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    request = read_json(args.request)
    report = read_json(args.report)
    updated = apply_report(request, report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"applied discovery objective={updated['objective_id']} request={digest(updated)}")


if __name__ == "__main__":
    main()
