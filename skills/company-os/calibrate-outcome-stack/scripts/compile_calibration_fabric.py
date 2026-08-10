#!/usr/bin/env python3
"""Compile bounded calibration laboratories for required Company OS evaluators."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

EVALUATOR_SCHEMA = "company-os.evaluator-runtime-contract.v1"
ARTIFACT_SCHEMA = "company-os.artifact-observation-contract.v1"
BENCHMARK_SCHEMA = "company-os.benchmark-contract.v1"
REGISTRY_SCHEMA = "company-os.evaluator-adapter-registry.v1"
PHASES = ["charter", "discovery", "design", "execution", "verification", "integration"]
MAX_EVALUATORS_PER_BATCH = 2


class CalibrationFabricError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise CalibrationFabricError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CalibrationFabricError("E_SCHEMA", f"{label} must be an object")
    return value


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalibrationFabricError("E_JSON", f"cannot read {label}: {path}") from exc
    return dict(obj(raw, label))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CalibrationFabricError("E_RUNTIME", f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def company_root() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def control_store_module():
    return load_module(
        company_root() / "elastic-company-os/scripts/control_store.py",
        "company_os_calibration_store",
    )


def fabric_module():
    return load_module(
        repo_root() / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py",
        "company_os_calibration_fabric",
    )


def verify_ready(raw: Mapping[str, Any], schema: str, label: str) -> dict[str, Any]:
    value = dict(raw)
    if value.get("$schema") != schema:
        raise CalibrationFabricError("E_SCHEMA", f"{label} must use {schema}")
    if value.get("ready") is not True:
        raise CalibrationFabricError("E_NOT_READY", f"{label} is not ready")
    return value


def verify_registry(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(raw)
    if value.get("$schema") != REGISTRY_SCHEMA:
        raise CalibrationFabricError("E_SCHEMA", f"adapter registry must use {REGISTRY_SCHEMA}")
    adapters = value.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise CalibrationFabricError("E_SCHEMA", "adapter registry has no adapters")
    return value


def required_artifact_map(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records = contract.get("artifact_classes")
    if not isinstance(records, list):
        raise CalibrationFabricError("E_SCHEMA", "artifact_classes must be an array")
    result = {}
    for raw in records:
        if not isinstance(raw, Mapping):
            raise CalibrationFabricError("E_SCHEMA", "artifact class must be an object")
        artifact_id = text(raw.get("artifact_class_id"), "artifact_class_id")
        result[artifact_id] = dict(raw)
    return result


def positive_negative_anchors(contract: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    dimensions = contract.get("dimensions")
    if not isinstance(dimensions, list):
        raise CalibrationFabricError("E_SCHEMA", "benchmark dimensions must be an array")
    negative: list[dict[str, Any]] = []
    positive: list[dict[str, Any]] = []
    for dimension in dimensions:
        if not isinstance(dimension, Mapping) or dimension.get("required") is not True:
            continue
        for reference in dimension.get("references", []):
            if not isinstance(reference, Mapping):
                continue
            record = dict(reference)
            record["dimension_id"] = dimension.get("dimension_id")
            tier = reference.get("quality_tier")
            if tier in {"negative", "baseline"}:
                negative.append(record)
            if tier in {"strong", "exemplar"}:
                positive.append(record)
    if not negative or not positive:
        raise CalibrationFabricError(
            "E_BENCHMARK",
            "calibration requires at least one negative or baseline anchor and one strong or exemplar anchor",
        )
    return {
        "negative": sorted(negative, key=lambda item: (str(item.get("dimension_id")), str(item.get("reference_id")))),
        "positive": sorted(positive, key=lambda item: (str(item.get("dimension_id")), str(item.get("reference_id")))),
    }


def adapter_for(registry: Mapping[str, Any], locator: str) -> Mapping[str, Any]:
    matches = [
        item
        for item in registry.get("adapters", [])
        if isinstance(item, Mapping) and item.get("adapter_locator") == locator
    ]
    if len(matches) != 1:
        raise CalibrationFabricError(
            "E_ADAPTER",
            f"evaluator adapter registry does not contain exactly one adapter for {locator}",
        )
    return matches[0]


def candidate_task(
    evaluator: Mapping[str, Any],
    artifact_definitions: list[dict[str, Any]],
    anchors: dict[str, list[dict[str, Any]]],
    rank: int,
    output_root: str,
) -> str:
    if rank == 1:
        tier_instruction = (
            "Materialize a deliberately weak but valid candidate. Use the negative or baseline anchors as evidence for the expected low quality state. "
            "The candidate must still be observable by the evaluator; do not make it invalid merely to force a low score."
        )
    elif rank == 2:
        tier_instruction = (
            "Materialize a materially intermediate candidate between the negative and positive anchors. Deliberately preserve some strengths and some clear deficiencies so it should rank strictly between the other two candidates."
        )
    else:
        tier_instruction = (
            "Materialize a strong candidate aligned with the strong or exemplar anchors. It must exhibit the relevant high quality properties in actual behavior, not just source structure."
        )
    return (
        f"Build calibration candidate rank {rank} for evaluator {evaluator['evaluator_id']!r}. {tier_instruction} "
        f"Required artifact definitions: {json.dumps(artifact_definitions, sort_keys=True)}. "
        f"Negative anchors: {json.dumps(anchors['negative'], sort_keys=True)}. Positive anchors: {json.dumps(anchors['positive'], sort_keys=True)}. "
        f"Write all candidate artifacts under {output_root!r}. Produce a candidate-manifest.json in that directory with schema company-os.calibration-candidate.v1, expected_rank {rank}, every artifact_id, artifact_class_id, path, and sha256. "
        "Use real artifacts that the registered evaluator can exercise. If an external runtime or referenced asset cannot be obtained, return the exact blocker instead of fabricating a candidate."
    )


def manager_integration_instruction(
    evaluator: Mapping[str, Any],
    *,
    evaluator_contract_path: str,
    benchmark_contract_path: str,
    adapter_registry_path: str,
    manager_root: str,
) -> str:
    evaluator_id = evaluator["evaluator_id"]
    return (
        f"After all three ranked candidate manifests are verified, run the registered evaluator {evaluator_id!r} independently against each candidate using the exact same evaluator contract {evaluator_contract_path!r}, benchmark contract {benchmark_contract_path!r}, and adapter registry {adapter_registry_path!r}. "
        f"Write three execution receipts under {manager_root!r}. Then write a company-os.evaluator-calibration.v2 request with evaluator_id {evaluator_id!r}, required_dimensions {sorted(evaluator.get('score_dimensions', []))}, candidate IDs rank-1, rank-2, rank-3, expected ranks 1, 2, 3, and the three execution receipt paths. "
        "Run skills/company-os/calibrate-outcome-evaluator/scripts/calibrate_evaluator.py against that request. The manager is accepted only if the resulting execution bound calibration receipt has passed true. If any score dimension ties or inverts, reject the evaluator capability and report the precise dimension. Do not change expected ranks after seeing scores."
    )


def compile_manifest(
    project_root: Path,
    evaluator_contract_path: str,
    artifact_contract_path: str,
    benchmark_contract_path: str,
    adapter_registry_path: str,
    already_calibrated: set[str] | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    evaluator_contract = verify_ready(
        read_json(project_root / evaluator_contract_path, "evaluator contract"),
        EVALUATOR_SCHEMA,
        "evaluator contract",
    )
    artifact_contract = verify_ready(
        read_json(project_root / artifact_contract_path, "artifact contract"),
        ARTIFACT_SCHEMA,
        "artifact contract",
    )
    benchmark_contract = verify_ready(
        read_json(project_root / benchmark_contract_path, "benchmark contract"),
        BENCHMARK_SCHEMA,
        "benchmark contract",
    )
    registry = verify_registry(read_json(project_root / adapter_registry_path, "adapter registry"))
    objective_id = text(evaluator_contract.get("objective_id"), "objective_id")
    if artifact_contract.get("objective_id") != objective_id or benchmark_contract.get("objective_id") != objective_id:
        raise CalibrationFabricError("E_BINDING", "outcome runtime contracts do not share one objective")
    artifact_map = required_artifact_map(artifact_contract)
    anchors = positive_negative_anchors(benchmark_contract)
    calibrated = already_calibrated or set()
    evaluators = [
        dict(raw)
        for raw in evaluator_contract.get("evaluators", [])
        if isinstance(raw, Mapping)
        and raw.get("required") is True
        and raw.get("evaluator_id") not in calibrated
    ]
    evaluators.sort(key=lambda item: str(item.get("evaluator_id", "")))
    batch = evaluators[:MAX_EVALUATORS_PER_BATCH]
    remaining = [item["evaluator_id"] for item in evaluators[MAX_EVALUATORS_PER_BATCH:]]
    if not batch:
        return {
            "complete": True,
            "objective_id": objective_id,
            "calibration_evaluator_ids": [],
            "remaining_evaluator_ids": [],
            "fabric": None,
        }
    try:
        _, state = control_store_module().load(project_root)
    except Exception as exc:
        raise CalibrationFabricError(
            "E_STATE",
            f"Company OS transactional control store is required: {exc}",
        ) from exc
    strategy = obj(state.get("strategy"), "strategy")
    instance = obj(state.get("instance"), "instance")
    project_id = text(instance.get("project_id"), "project_id")
    program_version = strategy.get("program_version")
    if not isinstance(program_version, int) or isinstance(program_version, bool) or program_version < 1:
        raise CalibrationFabricError("E_STATE", "strategy.program_version is invalid")

    program_outcome = f"Calibrate required independent evaluators for objective {objective_id}"
    managers = []
    for manager_index, evaluator in enumerate(batch, 1):
        evaluator_id = text(evaluator.get("evaluator_id"), "evaluator_id")
        locator = text(evaluator.get("adapter_locator"), f"{evaluator_id}.adapter_locator")
        adapter_for(registry, locator)
        covered = evaluator.get("artifact_classes")
        if not isinstance(covered, list) or not covered:
            raise CalibrationFabricError("E_SCHEMA", f"{evaluator_id} covers no artifact classes")
        definitions = []
        for artifact_id in covered:
            if artifact_id not in artifact_map:
                raise CalibrationFabricError(
                    "E_BINDING",
                    f"{evaluator_id} references unknown artifact class {artifact_id}",
                )
            definitions.append(artifact_map[artifact_id])
        manager_id = f"calibration-manager-{manager_index:02d}-{evaluator_id}"
        manager_root = f".company-os/calibration/{evaluator_id}"
        manager_outcome = f"Prove evaluator {evaluator_id} strictly discriminates three known quality ranks"
        workers = []
        for rank in (1, 2, 3):
            output_root = f"{manager_root}/rank-{rank}"
            workers.append(
                {
                    "id": f"{manager_id}-candidate-{rank}",
                    "model": "gpt-5.6-luna",
                    "task": candidate_task(
                        evaluator,
                        definitions,
                        anchors,
                        rank,
                        output_root,
                    ),
                    "acceptance": [
                        f"Candidate manifest exists at {output_root}/candidate-manifest.json",
                        "Candidate contains real artifacts for every evaluator artifact class",
                        "Candidate artifacts are distinct from the other calibration ranks",
                        "Candidate quality intent is fixed before evaluator scores are observed",
                    ],
                    "write_scope": [output_root],
                    "risk": "low",
                    "budget": {
                        "time_minutes": 30.0,
                        "token_limit": 8000,
                        "cost_usd": 8.0,
                        "max_concurrency": 1,
                        "max_retries": 1,
                    },
                    "outcome_context": {
                        "program_version": program_version,
                        "north_star": strategy.get("north_star") or "Produce independently verified outcomes",
                        "user_value": f"A trustworthy independent evaluator for {objective_id}",
                        "program_outcome": program_outcome,
                        "manager_outcome": manager_outcome,
                        "roadmap_position": "verification",
                        "dependencies": [
                            evaluator_contract_path,
                            artifact_contract_path,
                            benchmark_contract_path,
                            adapter_registry_path,
                        ],
                        "non_goals": ["Production candidate modification", "Changing evaluator expectations after scoring"],
                        "constraints": [
                            "Candidate rank is fixed before scoring",
                            "Calibration candidates must use distinct artifact sets",
                            "Unavailable external evidence cannot be fabricated",
                        ],
                    },
                    "stop_condition": "A real ranked candidate is materialized, or a concrete prerequisite blocker is proven.",
                }
            )
        integration_instruction = manager_integration_instruction(
            evaluator,
            evaluator_contract_path=evaluator_contract_path,
            benchmark_contract_path=benchmark_contract_path,
            adapter_registry_path=adapter_registry_path,
            manager_root=manager_root,
        )
        managers.append(
            {
                "id": manager_id,
                "model": "gpt-5.6-sol",
                "outcome": manager_outcome,
                "acceptance": [
                    "Three distinct ranked candidate artifact sets are materialized",
                    "The same evaluator contract, benchmark contract, registry, and adapter bytes are used for all three executions",
                    "Three verified evaluator execution receipts exist",
                    "Execution bound calibration receipt exists and passed is true",
                    integration_instruction,
                ],
                "phase_ids": PHASES,
                "budget": {
                    "time_minutes": 120.0,
                    "token_limit": 30000,
                    "cost_usd": 30.0,
                    "max_concurrency": 1,
                    "max_retries": 1,
                },
                "write_scope": [manager_root],
                "workers": workers,
            }
        )
    worker_count = sum(len(manager["workers"]) for manager in managers)
    fabric = {
        "program_id": project_id,
        "program_version": program_version,
        "outcome": program_outcome,
        "acceptance": [
            "Every evaluator in this batch has an execution bound calibration receipt",
            "Every calibration receipt passed strict pairwise ordering across every required score dimension",
            "No expected rank changed after evaluator output was observed",
        ],
        "program_contract": {
            "north_star": strategy.get("north_star") or "Produce independently verified outcomes",
            "user_value": f"A trustworthy independent evaluator set for {objective_id}",
            "rationale": "Production must not scale before the evaluator system proves it can distinguish poor from excellent artifacts.",
            "architecture": "Three real calibration candidate workers feed one independent evaluator manager per evaluator capability.",
            "roadmap": PHASES,
            "dependencies": [
                evaluator_contract_path,
                artifact_contract_path,
                benchmark_contract_path,
                adapter_registry_path,
            ],
            "non_goals": ["Production artifact delivery", "Changing quality expectations after scoring"],
            "constraints": ["Strict score ordering required", "Exact evaluator bytes are fixed during calibration"],
        },
        "max_managers": len(managers),
        "max_manager_concurrency": len(managers),
        "max_workers_per_manager": 3,
        "max_total_workers": worker_count,
        "max_depth": 2,
        "max_worker_retries": 1,
        "max_manager_rework_rounds": 2,
        "budget": {
            "time_minutes": 360.0,
            "token_limit": 90000,
            "cost_usd": 90.0,
            "max_concurrency": len(managers),
            "max_retries": 1,
        },
        "luna_token_share_target": 0.75,
        "external_effects_allowed": False,
        "managers": managers,
    }
    validation = fabric_module().validate(fabric)
    if not validation.get("valid"):
        raise CalibrationFabricError("E_FABRIC", "; ".join(validation.get("errors", [])))
    return {
        "complete": False,
        "objective_id": objective_id,
        "calibration_evaluator_ids": [item["evaluator_id"] for item in batch],
        "remaining_evaluator_ids": remaining,
        "fabric": fabric,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evaluator-contract", required=True)
    parser.add_argument("--artifact-contract", required=True)
    parser.add_argument("--benchmark-contract", required=True)
    parser.add_argument("--adapter-registry", required=True)
    parser.add_argument("--already-calibrated", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compile_manifest(
            args.project_root,
            args.evaluator_contract,
            args.artifact_contract,
            args.benchmark_contract,
            args.adapter_registry,
            set(args.already_calibrated),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "complete": result["complete"],
                    "calibration_evaluator_ids": result["calibration_evaluator_ids"],
                    "remaining_evaluator_ids": result["remaining_evaluator_ids"],
                },
                sort_keys=True,
            )
        )
        return 0
    except CalibrationFabricError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
