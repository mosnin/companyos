#!/usr/bin/env python3
"""Synthesize cited discovery proposals into a measurable Company OS outcome request."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Mapping

PROPOSAL_SCHEMA = "company-os.outcome-model-proposal.v1"
REQUEST_SCHEMA = "company-os.outcome-request.v1"
LOCATOR = re.compile(r"^(?:https?://|tool://|runtime://|module://|workspace://|reference://)[^\s]+$")
RICH_MODALITIES = {"interactive", "visual", "audio", "executable", "service", "database", "model", "physical", "composite"}

class SynthesisError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise SynthesisError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()

def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SynthesisError("E_SCHEMA", f"{label} must be an object")
    return value

def strings(value: Any, label: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise SynthesisError("E_SCHEMA", f"{label} must be an array")
    result = [text(item, f"{label}[]") for item in value]
    if len(result) != len(set(result)):
        raise SynthesisError("E_DUPLICATE", f"{label} contains duplicates")
    if nonempty and not result:
        raise SynthesisError("E_EVIDENCE", f"{label} cannot be empty")
    return sorted(result)

def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SynthesisError("E_JSON", f"invalid {label}: {path}") from exc

def outcome_module():
    path = Path(__file__).resolve().parents[2] / "compile-outcome-contract/scripts/compile_outcome_contract.py"
    spec = importlib.util.spec_from_file_location("company_os_synthesis_outcome", path)
    if spec is None or spec.loader is None:
        raise SynthesisError("E_RUNTIME", "outcome compiler cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def citations(item: Mapping[str, Any], label: str) -> list[str]:
    return strings(item.get("citations"), f"{label}.citations")

def normalize_resolution(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    unknown_id = text(item.get("unknown_id"), f"{label}.unknown_id")
    counter = strings(item.get("counterevidence", []), f"{label}.counterevidence", nonempty=False)
    reconciliation = item.get("reconciliation")
    if counter:
        reconciliation = text(reconciliation, f"{label}.reconciliation")
    elif reconciliation is not None:
        reconciliation = text(reconciliation, f"{label}.reconciliation")
    return {
        "unknown_id": unknown_id,
        "conclusion": text(item.get("conclusion"), f"{label}.conclusion"),
        "citations": citations(item, label),
        "counterevidence": counter,
        "reconciliation": reconciliation,
        "closure_evidence": strings(item.get("closure_evidence"), f"{label}.closure_evidence"),
    }
def normalize_domain(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    status = item.get("status")
    if status not in {"supported", "refuted"}:
        raise SynthesisError("E_SCHEMA", f"{label}.status must be supported or refuted")
    source_bindings = strings(item.get("source_bindings"), f"{label}.source_bindings")
    return {
        "domain_id": text(item.get("domain_id"), f"{label}.domain_id"),
        "hypothesis": text(item.get("hypothesis"), f"{label}.hypothesis"),
        "status": status,
        "source_bindings": source_bindings,
    }
def normalize_claim(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    return {
        "claim_id": text(item.get("claim_id"), f"{label}.claim_id"),
        "statement": text(item.get("statement"), f"{label}.statement"),
        "evidence_bindings": strings(item.get("evidence_bindings"), f"{label}.evidence_bindings"),
        "source_bindings": citations(item, label),
    }
def normalize_artifact(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    artifact_id = text(item.get("artifact_class_id"), f"{label}.artifact_class_id")
    required = item.get("required", True)
    if not isinstance(required, bool):
        raise SynthesisError("E_SCHEMA", f"{label}.required must be boolean")
    modalities = strings(item.get("modalities"), f"{label}.modalities")
    methods = strings(item.get("observation_methods"), f"{label}.observation_methods")
    required_evidence = strings(item.get("required_evidence"), f"{label}.required_evidence")
    if required and set(modalities) & RICH_MODALITIES and not required_evidence:
        raise SynthesisError("E_EVIDENCE", f"{artifact_id} is rich and requires experiential evidence")
    return {
        "artifact_class_id": artifact_id,
        "label": text(item.get("label"), f"{label}.label"),
        "required": required,
        "modalities": modalities,
        "observation_methods": methods,
        "required_evidence": required_evidence,
        "source_bindings": citations(item, label),
    }
def normalize_evaluator(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    evaluator_id = text(item.get("evaluator_id"), f"{label}.evaluator_id")
    required = item.get("required", True)
    if not isinstance(required, bool):
        raise SynthesisError("E_SCHEMA", f"{label}.required must be boolean")
    independent = item.get("independent_role")
    if independent is not True:
        raise SynthesisError("E_AUTHORITY", f"{evaluator_id} must be independent from production")
    adapter_locator = item.get("adapter_locator")
    if adapter_locator is None:
        adapter_locator = f"workspace://.company-os/evaluators/{evaluator_id}/adapter.py"
    adapter_locator = text(adapter_locator, f"{label}.adapter_locator")
    if LOCATOR.fullmatch(adapter_locator) is None:
        raise SynthesisError("E_SCHEMA", f"{label}.adapter_locator is invalid")
    return {
        "evaluator_id": evaluator_id,
        "label": text(item.get("label"), f"{label}.label"),
        "required": required,
        "independent_role": True,
        "research_only": False,
        "executable_methods": strings(item.get("executable_methods"), f"{label}.executable_methods"),
        "adapter_locator": adapter_locator,
        "artifact_classes": strings(item.get("artifact_classes"), f"{label}.artifact_classes"),
        "produces_evidence": strings(item.get("produces_evidence"), f"{label}.produces_evidence"),
        "score_dimensions": strings(item.get("score_dimensions"), f"{label}.score_dimensions"),
        "source_bindings": citations(item, label),
    }
def normalize_benchmark(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    benchmark_id = text(item.get("benchmark_id"), f"{label}.benchmark_id")
    required = item.get("required", True)
    if not isinstance(required, bool):
        raise SynthesisError("E_SCHEMA", f"{label}.required must be boolean")
    references = item.get("references")
    if not isinstance(references, list) or len(references) < 2:
        raise SynthesisError("E_BENCHMARK", f"{benchmark_id} requires at least two reference tiers")
    normalized_refs = []
    ids = set()
    tiers = set()
    for index, raw in enumerate(references):
        ref = obj(raw, f"{label}.references[{index}]")
        ref_id = text(ref.get("reference_id"), f"{label}.reference_id")
        if ref_id in ids:
            raise SynthesisError("E_DUPLICATE", f"duplicate benchmark reference {ref_id}")
        ids.add(ref_id)
        locator = text(ref.get("locator"), f"{label}.locator")
        if LOCATOR.fullmatch(locator) is None:
            raise SynthesisError("E_SCHEMA", f"benchmark locator invalid: {locator}")
        tier = text(ref.get("quality_tier"), f"{label}.quality_tier")
        tiers.add(tier)
        normalized_refs.append(
            {
                "reference_id": ref_id,
                "locator": locator,
                "quality_tier": tier,
                "provenance": text(ref.get("provenance"), f"{label}.provenance"),
                "citations": citations(ref, f"{label}.references[{index}]"),
            }
        )
    if len(tiers) < 2 or not ({"strong", "exemplar"} & tiers):
        raise SynthesisError("E_BENCHMARK", f"{benchmark_id} must include multiple tiers and a positive anchor")
    return {
        "benchmark_id": benchmark_id,
        "dimension": text(item.get("dimension"), f"{label}.dimension"),
        "required": required,
        "references": sorted(ref["locator"] for ref in normalized_refs),
        "reference_records": sorted(normalized_refs, key=lambda ref: ref["reference_id"]),
        "source_bindings": citations(item, label),
    }
def normalize_reality(item: Mapping[str, Any], label: str) -> dict[str, Any]:
    if item.get("independent_from_production") is not True or item.get("binds_original_objective") is not True:
        raise SynthesisError("E_AUTHORITY", "reality acceptance must be independent and bind the original objective")
    return {
        "policy": text(item.get("policy"), f"{label}.policy"),
        "independent_from_production": True,
        "binds_original_objective": True,
        "source_bindings": citations(item, label),
    }
def validate_proposal(raw: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "$schema", "proposal_id", "objective_id", "request_sha256", "sources",
        "unknown_resolutions", "domain_hypotheses", "outcome_claims", "artifact_classes",
        "evaluators", "benchmarks", "reality_acceptance",
    }
    if set(raw) != expected:
        raise SynthesisError("E_SCHEMA", f"proposal keys are invalid: {sorted(set(raw) ^ expected)}")
    if raw.get("$schema") != PROPOSAL_SCHEMA:
        raise SynthesisError("E_SCHEMA", f"proposal must use {PROPOSAL_SCHEMA}")
    proposal_id = text(raw.get("proposal_id"), "proposal_id")
    if raw.get("objective_id") != base.get("objective_id"):
        raise SynthesisError("E_BINDING", f"proposal {proposal_id} objective mismatch")
    if raw.get("request_sha256") != digest(base):
        raise SynthesisError("E_BINDING", f"proposal {proposal_id} is not bound to the exact base request")
    sources = strings(raw.get("sources"), f"{proposal_id}.sources")
    def normalize_array(key: str, fn):
        value = raw.get(key)
        if not isinstance(value, list):
            raise SynthesisError("E_SCHEMA", f"{proposal_id}.{key} must be an array")
        return [fn(obj(item, f"{proposal_id}.{key}[{index}]"), f"{proposal_id}.{key}[{index}]") for index, item in enumerate(value)]
    reality_raw = raw.get("reality_acceptance")
    reality = None if reality_raw is None else normalize_reality(obj(reality_raw, "reality_acceptance"), f"{proposal_id}.reality_acceptance")
    return {
        "proposal_id": proposal_id,
        "sources": sources,
        "unknown_resolutions": normalize_array("unknown_resolutions", normalize_resolution),
        "domain_hypotheses": normalize_array("domain_hypotheses", normalize_domain),
        "outcome_claims": normalize_array("outcome_claims", normalize_claim),
        "artifact_classes": normalize_array("artifact_classes", normalize_artifact),
        "evaluators": normalize_array("evaluators", normalize_evaluator),
        "benchmarks": normalize_array("benchmarks", normalize_benchmark),
        "reality_acceptance": reality,
    }
def merge_records(proposals: list[dict[str, Any]], key: str, id_key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    source: dict[str, str] = {}
    for proposal in proposals:
        for record in proposal[key]:
            identifier = record[id_key]
            if identifier in merged and canonical(merged[identifier]) != canonical(record):
                raise SynthesisError(
                    "E_CONFLICT",
                    f"{key} {identifier} conflicts between proposals {source[identifier]} and {proposal['proposal_id']}",
                )
            merged[identifier] = copy.deepcopy(record)
            source[identifier] = proposal["proposal_id"]
    return [merged[key] for key in sorted(merged)]
def synthesize(base_raw: Mapping[str, Any], proposal_raws: list[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    if base_raw.get("$schema") != REQUEST_SCHEMA:
        raise SynthesisError("E_SCHEMA", f"base request must use {REQUEST_SCHEMA}")
    base = copy.deepcopy(dict(base_raw))
    if not proposal_raws:
        raise SynthesisError("E_SCHEMA", "at least one discovery proposal is required")
    proposals = [validate_proposal(raw, base) for raw in proposal_raws]
    ids = [proposal["proposal_id"] for proposal in proposals]
    if len(ids) != len(set(ids)):
        raise SynthesisError("E_DUPLICATE", "proposal IDs must be unique")
    resolution_records = merge_records(proposals, "unknown_resolutions", "unknown_id")
    resolution_by_id = {record["unknown_id"]: record for record in resolution_records}
    unknowns = []
    for raw in base.get("unknowns", []):
        item = copy.deepcopy(dict(obj(raw, "base unknown")))
        unknown_id = text(item.get("unknown_id"), "unknown_id")
        resolution = resolution_by_id.get(unknown_id)
        if resolution is not None:
            required = set(item.get("closure_evidence", []))
            supplied = set(resolution["closure_evidence"])
            if not required.issubset(supplied):
                raise SynthesisError("E_EVIDENCE", f"{unknown_id} does not satisfy its closure evidence")
            item["resolved"] = True
            item["resolution"] = resolution["conclusion"]
            item["resolution_citations"] = resolution["citations"]
            item["resolution_counterevidence"] = resolution["counterevidence"]
            if resolution["reconciliation"] is not None:
                item["resolution_reconciliation"] = resolution["reconciliation"]
        unknowns.append(item)
    unresolved = sorted(
        item["unknown_id"]
        for item in unknowns
        if item.get("blocking", True) is True and item.get("resolved") is not True
    )
    if unresolved:
        raise SynthesisError("E_INCOMPLETE", f"blocking unknowns remain unresolved: {', '.join(unresolved)}")
    domains = {
        item["domain_id"]: copy.deepcopy(item)
        for item in base.get("domain_hypotheses", [])
        if isinstance(item, Mapping) and isinstance(item.get("domain_id"), str)
    }
    for item in merge_records(proposals, "domain_hypotheses", "domain_id"):
        domains[item["domain_id"]] = item
    reality_values = [proposal["reality_acceptance"] for proposal in proposals if proposal["reality_acceptance"] is not None]
    if not reality_values:
        raise SynthesisError("E_INCOMPLETE", "discovery did not define final reality acceptance")
    reality = reality_values[0]
    for candidate in reality_values[1:]:
        if canonical(candidate) != canonical(reality):
            raise SynthesisError("E_CONFLICT", "reality acceptance proposals conflict")
    request = {
        "$schema": REQUEST_SCHEMA,
        "objective_id": base["objective_id"],
        "objective": base["objective"],
        "outcome_claims": merge_records(proposals, "outcome_claims", "claim_id"),
        "domain_hypotheses": [domains[key] for key in sorted(domains)],
        "artifact_classes": merge_records(proposals, "artifact_classes", "artifact_class_id"),
        "evaluators": merge_records(proposals, "evaluators", "evaluator_id"),
        "benchmarks": merge_records(proposals, "benchmarks", "benchmark_id"),
        "unknowns": sorted(unknowns, key=lambda item: item["unknown_id"]),
        "reality_acceptance": reality,
    }
    try:
        contract = outcome_module().compile_contract(request)
    except Exception as exc:
        raise SynthesisError(getattr(exc, "code", "E_OUTCOME"), f"synthesized outcome is invalid: {exc}") from exc
    if contract.get("blockers"):
        detail = "; ".join(f"{item['code']}:{item['detail']}" for item in contract["blockers"])
        raise SynthesisError("E_INCOMPLETE", f"synthesized outcome still has blockers: {detail}")
    if contract.get("scale_allowed") is not True:
        raise SynthesisError("E_INCOMPLETE", "synthesized outcome did not become measurable")
    return request, contract

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-request", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, action="append", required=True)
    parser.add_argument("--request-output", type=Path, required=True)
    parser.add_argument("--contract-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        base = obj(read_json(args.base_request, "base request"), "base request")
        proposals = [obj(read_json(path, "proposal"), "proposal") for path in args.proposal]
        request, contract = synthesize(base, proposals)
        write_json(args.request_output, request)
        write_json(args.contract_output, contract)
        print(json.dumps({"ok": True, "objective_id": request["objective_id"], "request_sha256": digest(request), "contract_sha256": contract["contract_sha256"], "state": contract["state"]}, sort_keys=True))
        return 0
    except SynthesisError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
