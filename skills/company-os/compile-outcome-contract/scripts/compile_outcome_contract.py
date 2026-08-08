#!/usr/bin/env python3
"""Compile broad objectives into deterministic Company OS outcome contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "company-os.outcome-contract.v1"
REQUEST_SCHEMA = "company-os.outcome-request.v1"


class OutcomeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OutcomeError("E_CANONICAL", f"not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OutcomeError("E_READ", f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise OutcomeError("E_JSON", f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OutcomeError("E_SCHEMA", "request must be an object")
    return value


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OutcomeError("E_SCHEMA", f"{label} must be a non-empty string")
    return value


def records(value: Any, label: str, id_key: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise OutcomeError("E_SCHEMA", f"{label} must be an array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise OutcomeError("E_SCHEMA", f"{label}[{index}] must be an object")
        identifier = nonempty(item.get(id_key), f"{label}[{index}].{id_key}")
        if identifier in seen:
            raise OutcomeError("E_DUPLICATE", f"duplicate {label} id: {identifier}")
        seen.add(identifier)
        result.append(dict(item))
    return sorted(result, key=lambda item: str(item[id_key]))


def string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise OutcomeError("E_SCHEMA", f"{label} must be an array")
    result = []
    for index, item in enumerate(value):
        result.append(nonempty(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        raise OutcomeError("E_DUPLICATE", f"{label} contains duplicates")
    return sorted(result)


def validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "$schema",
        "objective_id",
        "objective",
        "outcome_claims",
        "domain_hypotheses",
        "artifact_classes",
        "evaluators",
        "benchmarks",
        "unknowns",
        "reality_acceptance",
    }
    unknown_keys = sorted(set(request) - allowed)
    if unknown_keys:
        raise OutcomeError("E_SCHEMA", f"unknown request keys: {', '.join(unknown_keys)}")
    if request.get("$schema") != REQUEST_SCHEMA:
        raise OutcomeError("E_SCHEMA", f"$schema must equal {REQUEST_SCHEMA!r}")

    objective_id = nonempty(request.get("objective_id"), "objective_id")
    objective = nonempty(request.get("objective"), "objective")
    claims = records(request.get("outcome_claims"), "outcome_claims", "claim_id")
    domains = records(request.get("domain_hypotheses"), "domain_hypotheses", "domain_id")
    artifacts = records(request.get("artifact_classes"), "artifact_classes", "artifact_class_id")
    evaluators = records(request.get("evaluators"), "evaluators", "evaluator_id")
    benchmarks = records(request.get("benchmarks"), "benchmarks", "benchmark_id")
    unknowns = records(request.get("unknowns"), "unknowns", "unknown_id")

    for claim in claims:
        nonempty(claim.get("statement"), f"outcome claim {claim['claim_id']}.statement")
        claim["evidence_bindings"] = string_list(
            claim.get("evidence_bindings"), f"outcome claim {claim['claim_id']}.evidence_bindings"
        )

    for domain in domains:
        nonempty(domain.get("hypothesis"), f"domain {domain['domain_id']}.hypothesis")
        status = domain.get("status")
        if status not in {"hypothesis", "supported", "refuted"}:
            raise OutcomeError("E_SCHEMA", f"domain {domain['domain_id']}.status is invalid")

    for artifact in artifacts:
        nonempty(artifact.get("label"), f"artifact {artifact['artifact_class_id']}.label")
        artifact["required"] = artifact.get("required", True)
        if not isinstance(artifact["required"], bool):
            raise OutcomeError("E_SCHEMA", f"artifact {artifact['artifact_class_id']}.required must be boolean")
        artifact["observation_methods"] = string_list(
            artifact.get("observation_methods"),
            f"artifact {artifact['artifact_class_id']}.observation_methods",
        )

    for evaluator in evaluators:
        nonempty(evaluator.get("label"), f"evaluator {evaluator['evaluator_id']}.label")
        evaluator["required"] = evaluator.get("required", True)
        if not isinstance(evaluator["required"], bool):
            raise OutcomeError("E_SCHEMA", f"evaluator {evaluator['evaluator_id']}.required must be boolean")
        evaluator["executable_methods"] = string_list(
            evaluator.get("executable_methods"),
            f"evaluator {evaluator['evaluator_id']}.executable_methods",
        )
        evaluator["independent_role"] = bool(evaluator.get("independent_role", False))

    for benchmark in benchmarks:
        nonempty(benchmark.get("dimension"), f"benchmark {benchmark['benchmark_id']}.dimension")
        benchmark["required"] = benchmark.get("required", True)
        if not isinstance(benchmark["required"], bool):
            raise OutcomeError("E_SCHEMA", f"benchmark {benchmark['benchmark_id']}.required must be boolean")
        benchmark["references"] = string_list(
            benchmark.get("references"), f"benchmark {benchmark['benchmark_id']}.references"
        )

    for unknown in unknowns:
        nonempty(unknown.get("question"), f"unknown {unknown['unknown_id']}.question")
        unknown["blocking"] = unknown.get("blocking", True)
        if not isinstance(unknown["blocking"], bool):
            raise OutcomeError("E_SCHEMA", f"unknown {unknown['unknown_id']}.blocking must be boolean")
        unknown["closure_evidence"] = string_list(
            unknown.get("closure_evidence"), f"unknown {unknown['unknown_id']}.closure_evidence"
        )
        unknown["resolved"] = unknown.get("resolved", False)
        if not isinstance(unknown["resolved"], bool):
            raise OutcomeError("E_SCHEMA", f"unknown {unknown['unknown_id']}.resolved must be boolean")

    reality = request.get("reality_acceptance")
    if reality is not None:
        if not isinstance(reality, dict):
            raise OutcomeError("E_SCHEMA", "reality_acceptance must be an object")
        nonempty(reality.get("policy"), "reality_acceptance.policy")
        reality = {
            "policy": reality["policy"],
            "independent_from_production": bool(reality.get("independent_from_production", False)),
            "binds_original_objective": bool(reality.get("binds_original_objective", False)),
        }

    return {
        "$schema": REQUEST_SCHEMA,
        "objective_id": objective_id,
        "objective": objective,
        "outcome_claims": claims,
        "domain_hypotheses": domains,
        "artifact_classes": artifacts,
        "evaluators": evaluators,
        "benchmarks": benchmarks,
        "unknowns": unknowns,
        "reality_acceptance": reality,
    }


def compile_contract(raw: Mapping[str, Any]) -> dict[str, Any]:
    request = validate_request(raw)
    blockers: list[dict[str, str]] = []
    agenda: list[dict[str, Any]] = []

    if not request["outcome_claims"]:
        blockers.append({"code": "OUTCOME_UNDEFINED", "detail": "no explicit outcome claims exist"})
        agenda.append({
            "discovery_id": "discover-outcome-claims",
            "question": "What observable state of reality would make the original objective successful?",
            "closure_evidence": ["one_or_more_outcome_claims_with_evidence_bindings"],
        })

    for unknown in request["unknowns"]:
        if unknown["blocking"] and not unknown["resolved"]:
            blockers.append({"code": "UNRESOLVED_UNKNOWN", "detail": unknown["unknown_id"]})
            agenda.append({
                "discovery_id": f"resolve-{unknown['unknown_id']}",
                "question": unknown["question"],
                "closure_evidence": unknown["closure_evidence"] or ["cited_domain_evidence"],
            })

    for artifact in request["artifact_classes"]:
        if artifact["required"] and not artifact["observation_methods"]:
            blockers.append({"code": "UNOBSERVABLE_ARTIFACT", "detail": artifact["artifact_class_id"]})
            agenda.append({
                "discovery_id": f"observe-{artifact['artifact_class_id']}",
                "question": f"How can {artifact['label']} be independently observed or exercised?",
                "closure_evidence": ["one_or_more_observation_methods"],
            })

    for evaluator in request["evaluators"]:
        if evaluator["required"] and (
            not evaluator["executable_methods"] or not evaluator["independent_role"]
        ):
            blockers.append({"code": "EVALUATOR_NOT_EXECUTABLE", "detail": evaluator["evaluator_id"]})
            agenda.append({
                "discovery_id": f"calibrate-{evaluator['evaluator_id']}",
                "question": f"How will {evaluator['label']} execute independently of production?",
                "closure_evidence": ["executable_method", "independent_evaluator_role"],
            })

    for benchmark in request["benchmarks"]:
        if benchmark["required"] and not benchmark["references"]:
            blockers.append({"code": "BENCHMARK_UNBOUND", "detail": benchmark["benchmark_id"]})
            agenda.append({
                "discovery_id": f"bind-{benchmark['benchmark_id']}",
                "question": f"What reference set anchors the {benchmark['dimension']} quality bar?",
                "closure_evidence": ["one_or_more_reference_artifacts"],
            })

    reality = request["reality_acceptance"]
    if (
        reality is None
        or not reality["independent_from_production"]
        or not reality["binds_original_objective"]
    ):
        blockers.append({"code": "REALITY_ACCEPTANCE_MISSING", "detail": "original objective lacks independent final acceptance"})
        agenda.append({
            "discovery_id": "define-reality-acceptance",
            "question": "How will a fresh independent evaluator judge the actual artifact against the original objective?",
            "closure_evidence": ["independent_acceptance_policy", "original_objective_binding"],
        })

    all_bindings = {
        item["artifact_class_id"] for item in request["artifact_classes"]
    } | {
        item["evaluator_id"] for item in request["evaluators"]
    } | {
        item["benchmark_id"] for item in request["benchmarks"]
    }
    for claim in request["outcome_claims"]:
        if not claim["evidence_bindings"]:
            blockers.append({"code": "CLAIM_UNBOUND", "detail": claim["claim_id"]})
        elif not set(claim["evidence_bindings"]).issubset(all_bindings):
            blockers.append({"code": "CLAIM_UNKNOWN_BINDING", "detail": claim["claim_id"]})

    blockers = sorted(blockers, key=lambda item: (item["code"], item["detail"]))
    agenda = sorted(agenda, key=lambda item: item["discovery_id"])
    blocking_unknowns = [
        item for item in request["unknowns"] if item["blocking"] and not item["resolved"]
    ]

    has_candidate_measurement = bool(request["artifact_classes"]) and bool(request["evaluators"])
    pilot_allowed = has_candidate_measurement
    scale_allowed = not blockers and bool(request["outcome_claims"])

    contract = {
        "$schema": SCHEMA,
        "schema_version": 1,
        "objective_id": request["objective_id"],
        "original_objective": request["objective"],
        "request_sha256": digest(request),
        "state": (
            "scale_allowed"
            if scale_allowed
            else "pilot_allowed"
            if pilot_allowed
            else "discovery_required"
        ),
        "pilot_allowed": pilot_allowed,
        "scale_allowed": scale_allowed,
        "blocking_unknown_count": len(blocking_unknowns),
        "blockers": blockers,
        "discovery_agenda": agenda,
        "outcome_claims": request["outcome_claims"],
        "domain_hypotheses": request["domain_hypotheses"],
        "artifact_classes": request["artifact_classes"],
        "evaluators": request["evaluators"],
        "benchmarks": request["benchmarks"],
        "reality_acceptance": reality,
    }
    contract["contract_sha256"] = digest({**contract, "contract_sha256": None})
    return contract


def verify_contract(raw_request: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    expected = compile_contract(raw_request)
    if canonical_bytes(expected) != canonical_bytes(candidate):
        raise OutcomeError("E_MISMATCH", "contract does not match deterministic compilation")
    return expected


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--request", required=True, type=Path)
    compile_parser.add_argument("--output", required=True, type=Path)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--request", required=True, type=Path)
    verify_parser.add_argument("--contract", required=True, type=Path)

    args = parser.parse_args()
    request = read_json(args.request)

    if args.command == "compile":
        contract = compile_contract(request)
        write_json(args.output, contract)
        print(
            f"compiled {contract['objective_id']} state={contract['state']} "
            f"blockers={len(contract['blockers'])}"
        )
        return

    candidate = read_json(args.contract)
    contract = verify_contract(request, candidate)
    print(f"verified {contract['objective_id']} {contract['contract_sha256']}")


if __name__ == "__main__":
    main()
