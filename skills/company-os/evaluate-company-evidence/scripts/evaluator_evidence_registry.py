#!/usr/bin/env python3
"""Build, verify, and resolve the feature-off evaluator evidence registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


DECISIONS_SCHEMA = "company-os.evaluation-method-decisions.v1"
REGISTRY_SCHEMA = "company-os.evaluator-evidence-registry.v1"
SOURCE_SCHEMA = "company-os.source-intelligence-registry.v1"
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
STAGES = {
    "discovery", "adaptive_validation", "deterministic_floor",
    "semantic_review", "sealed_challenge", "transfer",
}
DECISION_KEYS = {
    "method_id", "stage", "artifact_classes", "source_intelligence_ids",
    "required_evidence", "failure_semantics", "status", "mechanism_claim",
    "mechanism_evidence_locator", "mechanism_evidence_sha256", "counterevidence",
}
RECORD_KEYS = DECISION_KEYS | {"source_bindings", "method_sha256"}
REQUIRED_SOURCES = {
    "archishman-autovoiceevals", "chchenhui-mlrbench", "masworks-ml-agent",
    "orchestra-research-ai-research-skills", "skyllwt-autosci",
    "snap-stanford-mlagentbench", "thudm-agentbench", "wecoai-aideml",
}
MECHANISM_EVIDENCE_LOCATOR = "research://company-os/2026-08-05/recursive/lane-c/project-extractions.md"
MECHANISM_EVIDENCE_SHA256 = "428ef1aea811d2c1061c0ad6dc758f98f1080ef0fd48fd17319c82edcdc99239"


class EvaluatorRegistryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise EvaluatorRegistryError("E_SCHEMA", f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise EvaluatorRegistryError("E_SCHEMA", f"{label} keys differ")


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise EvaluatorRegistryError("E_SCHEMA", f"{label} is not a canonical identifier")
    return value


def _ids(value: Any, label: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise EvaluatorRegistryError("E_SCHEMA", f"{label} must be an array")
    if any(not isinstance(item, str) or not ID_RE.fullmatch(item) for item in value):
        raise EvaluatorRegistryError("E_SCHEMA", f"{label} contains a noncanonical identifier")
    if value != sorted(set(value)):
        raise EvaluatorRegistryError("E_SCHEMA", f"{label} must be sorted and unique")
    return value


def _read(path: Path, label: str) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EvaluatorRegistryError("E_PATH", f"{label} is not a regular non-symlink file")
    raw = path.read_bytes()
    try:
        value = _object(json.loads(raw), label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluatorRegistryError("E_JSON", f"{label} is invalid JSON") from exc
    if raw != canonical_bytes(value):
        raise EvaluatorRegistryError("E_CANONICAL", f"{label} is not canonical JSON")
    return value


def _validate_decision(value: Mapping[str, Any], *, exact: bool = True) -> None:
    if exact:
        _exact(value, DECISION_KEYS, "decision")
    _id(value["method_id"], "decision.method_id")
    if value["stage"] not in STAGES:
        raise EvaluatorRegistryError("E_STAGE", "decision stage is unsupported")
    _ids(value["artifact_classes"], "decision.artifact_classes")
    _ids(value["source_intelligence_ids"], "decision.source_intelligence_ids")
    _ids(value["required_evidence"], "decision.required_evidence")
    _ids(value["counterevidence"], "decision.counterevidence")
    if not isinstance(value["mechanism_claim"], str) or len(value["mechanism_claim"].strip()) < 20:
        raise EvaluatorRegistryError("E_EVIDENCE", "mechanism claim must be concrete")
    if value["mechanism_evidence_locator"] != MECHANISM_EVIDENCE_LOCATOR:
        raise EvaluatorRegistryError("E_EVIDENCE", "mechanism evidence locator is not accepted")
    if value["mechanism_evidence_sha256"] != MECHANISM_EVIDENCE_SHA256:
        raise EvaluatorRegistryError("E_EVIDENCE", "mechanism evidence digest is not accepted")
    if value["failure_semantics"] != "invalid_evidence":
        raise EvaluatorRegistryError("E_EVIDENCE", "evaluator failure must be invalid evidence")
    if value["status"] != "research_method_only":
        raise EvaluatorRegistryError("E_AUTHORITY", "research methods cannot become evaluator authority")


def build_registry(decisions: Mapping[str, Any], sources: Mapping[str, Any]) -> dict[str, Any]:
    if decisions.get("$schema") != DECISIONS_SCHEMA or decisions.get("schema_version") != 1:
        raise EvaluatorRegistryError("E_SCHEMA", "decision schema/version is unsupported")
    if sources.get("$schema") != SOURCE_SCHEMA:
        raise EvaluatorRegistryError("E_SCHEMA", "source registry schema is unsupported")
    raw_decisions = decisions.get("decisions")
    if not isinstance(raw_decisions, list):
        raise EvaluatorRegistryError("E_SCHEMA", "decisions must be an array")
    source_index = {item["source_id"]: item for item in sources["records"]}
    records = []
    covered: set[str] = set()
    for decision in raw_decisions:
        decision = dict(_object(decision, "decision"))
        _validate_decision(decision)
        bindings = []
        for source_id in decision["source_intelligence_ids"]:
            source = source_index.get(source_id)
            if source is None or source["evidence_class"] in {"invalid_unresolved", "duplicate_provenance_resolution"}:
                raise EvaluatorRegistryError("E_SOURCE", f"source {source_id!r} is missing, invalid, or duplicate-only")
            covered.add(source_id)
            bindings.append({
                "source_intelligence_id": source_id,
                "pin": source["pin"],
                "review_evidence_sha256": source["review_evidence_sha256"],
            })
        unsigned = dict(decision)
        unsigned["source_bindings"] = bindings
        record = dict(unsigned)
        record["method_sha256"] = canonical_digest(unsigned)
        records.append(record)
    records.sort(key=lambda item: item["method_id"])
    if len({item["method_id"] for item in records}) != len(records):
        raise EvaluatorRegistryError("E_COVERAGE", "method IDs must be unique")
    if covered != REQUIRED_SOURCES:
        raise EvaluatorRegistryError("E_COVERAGE", "evaluation source family coverage differs")
    if {record["stage"] for record in records} != STAGES:
        raise EvaluatorRegistryError("E_COVERAGE", "evaluation stage coverage differs")
    registry = {
        "$schema": REGISTRY_SCHEMA,
        "schema_version": 1,
        "registry_id": "company-os-evaluator-evidence-methods-2026-08-05",
        "source_intelligence_registry_sha256": canonical_digest(sources),
        "policy": {
            "research_methods_execute": False,
            "research_methods_score": False,
            "judge_failure_is_invalid_evidence": True,
            "sealed_challenge_burns_on_exposure": True,
            "benchmark_implies_business_outcome": False,
        },
        "method_count": len(records),
        "source_family_count": len(covered),
        "records": records,
    }
    validate_registry(registry, sources)
    return registry


def validate_registry(registry: Mapping[str, Any], sources: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "$schema", "schema_version", "registry_id", "source_intelligence_registry_sha256",
        "policy", "method_count", "source_family_count", "records",
    }
    _exact(registry, expected, "registry")
    if registry["$schema"] != REGISTRY_SCHEMA or registry["schema_version"] != 1:
        raise EvaluatorRegistryError("E_SCHEMA", "registry schema/version is unsupported")
    _id(registry["registry_id"], "registry.registry_id")
    if registry["source_intelligence_registry_sha256"] != canonical_digest(sources):
        raise EvaluatorRegistryError("E_BINDING", "source-intelligence binding is stale")
    expected_policy = {
        "research_methods_execute": False,
        "research_methods_score": False,
        "judge_failure_is_invalid_evidence": True,
        "sealed_challenge_burns_on_exposure": True,
        "benchmark_implies_business_outcome": False,
    }
    if registry["policy"] != expected_policy:
        raise EvaluatorRegistryError("E_POLICY", "registry policy differs")
    records = registry["records"]
    if not isinstance(records, list) or registry["method_count"] != len(records):
        raise EvaluatorRegistryError("E_COUNT", "method count differs")
    source_index = {item["source_id"]: item for item in sources["records"]}
    method_ids = []
    covered: set[str] = set()
    for raw in records:
        record = dict(_object(raw, "record"))
        _exact(record, RECORD_KEYS, "record")
        _validate_decision(record, exact=False)
        method_ids.append(record["method_id"])
        bindings = record["source_bindings"]
        if not isinstance(bindings, list) or not bindings:
            raise EvaluatorRegistryError("E_SOURCE", "method source bindings must be nonempty")
        if [item.get("source_intelligence_id") for item in bindings] != record["source_intelligence_ids"]:
            raise EvaluatorRegistryError("E_BINDING", "method source binding order differs")
        for binding in bindings:
            _exact(binding, {"source_intelligence_id", "pin", "review_evidence_sha256"}, "source binding")
            source_id = binding["source_intelligence_id"]
            source = source_index.get(source_id)
            if source is None or source["evidence_class"] in {"invalid_unresolved", "duplicate_provenance_resolution"}:
                raise EvaluatorRegistryError("E_SOURCE", f"source {source_id!r} is missing, invalid, or duplicate-only")
            expected_binding = {
                "source_intelligence_id": source_id,
                "pin": source["pin"],
                "review_evidence_sha256": source["review_evidence_sha256"],
            }
            if binding != expected_binding:
                raise EvaluatorRegistryError("E_BINDING", f"source binding for {source_id!r} differs")
            covered.add(source_id)
        unsigned = {key: record[key] for key in RECORD_KEYS - {"method_sha256"}}
        if record["method_sha256"] != canonical_digest(unsigned):
            raise EvaluatorRegistryError("E_BINDING", "method digest does not verify")
    if method_ids != sorted(method_ids) or len(method_ids) != len(set(method_ids)):
        raise EvaluatorRegistryError("E_COVERAGE", "method records must be sorted and unique")
    if covered != REQUIRED_SOURCES:
        raise EvaluatorRegistryError("E_COVERAGE", "evaluation source family coverage differs")
    if {record["stage"] for record in records} != STAGES:
        raise EvaluatorRegistryError("E_COVERAGE", "evaluation stage coverage differs")
    if registry["source_family_count"] != len(covered):
        raise EvaluatorRegistryError("E_COUNT", "source family count differs")
    return {
        "$schema": REGISTRY_SCHEMA,
        "registry_id": registry["registry_id"],
        "registry_sha256": canonical_digest(registry),
        "method_count": len(records),
        "source_family_count": len(covered),
        "execution_authorized": False,
    }


def resolve(registry: Mapping[str, Any], sources: Mapping[str, Any], artifacts: list[str], stages: list[str]) -> dict[str, Any]:
    evidence = validate_registry(registry, sources)
    artifacts = sorted(set(_id(item, "artifact class") for item in artifacts))
    stages = sorted(set(stages))
    if not artifacts or not stages or any(stage not in STAGES for stage in stages):
        raise EvaluatorRegistryError("E_REQUEST", "artifact classes and supported stages are required")
    selected = []
    for record in registry["records"]:
        if record["stage"] not in stages:
            continue
        compatible = "artifact" in record["artifact_classes"] or bool(set(artifacts) & set(record["artifact_classes"]))
        if compatible:
            selected.append({
                "method_id": record["method_id"],
                "method_sha256": record["method_sha256"],
                "stage": record["stage"],
                "required_evidence": record["required_evidence"],
                "status": record["status"],
            })
    research_covered = sorted({item["stage"] for item in selected})
    return {
        "$schema": "company-os.evaluation-method-resolution.v1",
        "registry_sha256": evidence["registry_sha256"],
        "artifact_classes": artifacts,
        "stages": stages,
        "research_methods": selected,
        "research_covered_stages": research_covered,
        "ready_evaluator_stages": [],
        "missing_ready_stages": stages,
        "execution_authorized": False,
        "next_gate": "materialize_and_independently_accept_exact_evaluator_adapters",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--decisions", type=Path, required=True)
    build.add_argument("--source-intelligence", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    for name in ("verify", "resolve"):
        command = sub.add_parser(name)
        command.add_argument("--registry", type=Path, required=True)
        command.add_argument("--source-intelligence", type=Path, required=True)
        if name == "resolve":
            command.add_argument("--artifact-class", action="append", default=[])
            command.add_argument("--stage", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        sources = _read(args.source_intelligence, "source intelligence")
        if args.command == "build":
            registry = build_registry(_read(args.decisions, "decisions"), sources)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical_bytes(registry))
            result = validate_registry(registry, sources)
        elif args.command == "verify":
            result = validate_registry(_read(args.registry, "registry"), sources)
        else:
            result = resolve(
                _read(args.registry, "registry"), sources,
                args.artifact_class, args.stage,
            )
        print(canonical_bytes(result).decode(), end="")
        return 0
    except EvaluatorRegistryError as exc:
        print(canonical_bytes({"code": exc.code, "error": str(exc), "ok": False}).decode(), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
