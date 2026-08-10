#!/usr/bin/env python3
"""Compile bounded work for missing required outcome evaluator adapters."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

CONTRACT_SCHEMA = "company-os.evaluator-runtime-contract.v1"
ARTIFACT_SCHEMA = "company-os.artifact-observation-contract.v1"
BENCHMARK_SCHEMA = "company-os.benchmark-contract.v1"
WORKSPACE_PREFIX = "workspace://"
PHASES = ["charter", "discovery", "design", "execution", "verification", "integration"]
MAX_BATCH = 6


class BuildFabricError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise BuildFabricError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BuildFabricError("E_SCHEMA", f"{label} must be an object")
    return value


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BuildFabricError("E_RUNTIME", f"cannot load {name}")
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
        "company_os_build_evaluator_store",
    )


def fabric_module():
    return load_module(
        repo_root() / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py",
        "company_os_build_evaluator_fabric",
    )


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildFabricError("E_JSON", f"cannot read {label}: {path}") from exc
    return dict(obj(raw, label))


def verify_contract(raw: Mapping[str, Any], schema: str, label: str) -> dict[str, Any]:
    value = dict(raw)
    if value.get("$schema") != schema:
        raise BuildFabricError("E_SCHEMA", f"{label} must use {schema}")
    if value.get("ready") is not True:
        raise BuildFabricError("E_NOT_READY", f"{label} is not ready")
    return value


def workspace_relative(locator: Any, label: str) -> str:
    locator = text(locator, label)
    if not locator.startswith(WORKSPACE_PREFIX):
        raise BuildFabricError(
            "E_UNBUILDABLE_LOCATOR",
            f"{label} is not a project local workspace adapter",
        )
    raw = locator[len(WORKSPACE_PREFIX) :]
    pure = PurePosixPath(raw)
    if (
        not raw
        or "\\" in raw
        or pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise BuildFabricError("E_PATH", f"{label} workspace path is unsafe")
    return pure.as_posix()


def missing_required(
    project_root: Path,
    evaluator_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records = evaluator_contract.get("evaluators")
    if not isinstance(records, list):
        raise BuildFabricError("E_SCHEMA", "evaluator contract evaluators must be an array")
    missing = []
    root = project_root.resolve()
    for raw in records:
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            continue
        evaluator = dict(raw)
        evaluator_id = text(evaluator.get("evaluator_id"), "evaluator_id")
        relative = workspace_relative(
            evaluator.get("adapter_locator"),
            f"{evaluator_id}.adapter_locator",
        )
        candidate = root / Path(*PurePosixPath(relative).parts)
        if candidate.exists():
            if candidate.is_symlink() or not candidate.is_file():
                raise BuildFabricError(
                    "E_PATH", f"existing evaluator adapter is not a regular file: {relative}"
                )
            continue
        evaluator["entrypoint"] = relative
        missing.append(evaluator)
    return sorted(missing, key=lambda item: str(item.get("evaluator_id", "")))


def worker_task(
    evaluator: Mapping[str, Any],
    *,
    evaluator_contract_path: str,
    artifact_contract_path: str,
    benchmark_contract_path: str,
) -> str:
    evaluator_id = evaluator["evaluator_id"]
    return (
        f"Build the missing required Company OS evaluator adapter {evaluator_id!r} at the exact path "
        f"{evaluator['entrypoint']!r}. Inspect the local execute outcome evaluator runtime and implement its "
        "company-os.evaluator-adapter-input.v1 to company-os.evaluator-adapter-output.v1 protocol. "
        f"The exact evaluator definition is {json.dumps(dict(evaluator), sort_keys=True)}. "
        f"Read the bound evaluator contract {evaluator_contract_path!r}, artifact contract {artifact_contract_path!r}, "
        f"and benchmark contract {benchmark_contract_path!r}. The adapter must evaluate actual artifacts in classes "
        f"{sorted(evaluator.get('artifact_classes', []))}, produce every required evidence type "
        f"{sorted(evaluator.get('produces_evidence', []))}, and return every score dimension "
        f"{sorted(evaluator.get('score_dimensions', []))}. Evidence files must be real project files produced by the "
        "evaluation. Do not grade source code when the artifact contract requires interactive, visual, audio, runtime, "
        "or other experiential observation. Do not modify the product candidate. If the required external runtime or "
        "tooling is unavailable, return that exact prerequisite as a blocker instead of fabricating evidence."
    )


def compile_manifest(
    project_root: Path,
    evaluator_contract_path: str,
    artifact_contract_path: str,
    benchmark_contract_path: str,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    evaluator_contract = verify_contract(
        read_json(project_root / evaluator_contract_path, "evaluator contract"),
        CONTRACT_SCHEMA,
        "evaluator contract",
    )
    artifact_contract = verify_contract(
        read_json(project_root / artifact_contract_path, "artifact contract"),
        ARTIFACT_SCHEMA,
        "artifact contract",
    )
    benchmark_contract = verify_contract(
        read_json(project_root / benchmark_contract_path, "benchmark contract"),
        BENCHMARK_SCHEMA,
        "benchmark contract",
    )
    objective_id = text(evaluator_contract.get("objective_id"), "objective_id")
    if artifact_contract.get("objective_id") != objective_id or benchmark_contract.get("objective_id") != objective_id:
        raise BuildFabricError("E_BINDING", "outcome runtime contracts do not share one objective")
    missing = missing_required(project_root, evaluator_contract)
    batch = missing[:MAX_BATCH]
    remaining = [item["evaluator_id"] for item in missing[MAX_BATCH:]]
    if not batch:
        return {
            "complete": True,
            "objective_id": objective_id,
            "missing_evaluator_ids": [],
            "remaining_evaluator_ids": [],
            "fabric": None,
        }
    try:
        _, state = control_store_module().load(project_root)
    except Exception as exc:
        raise BuildFabricError(
            "E_STATE", f"Company OS transactional control store is required: {exc}"
        ) from exc
    strategy = obj(state.get("strategy"), "strategy")
    project_id = text(obj(state.get("instance"), "instance").get("project_id"), "project_id")
    program_version = strategy.get("program_version")
    if not isinstance(program_version, int) or isinstance(program_version, bool) or program_version < 1:
        raise BuildFabricError("E_STATE", "strategy.program_version is invalid")
    manager_groups = [batch[index : index + 3] for index in range(0, len(batch), 3)]
    managers = []
    for manager_index, group in enumerate(manager_groups, 1):
        manager_id = f"evaluator-builder-manager-{manager_index:02d}"
        manager_scope = f".company-os/evaluator-build/batch/{manager_index:02d}"
        workers = []
        for worker_index, evaluator in enumerate(group, 1):
            entrypoint = evaluator["entrypoint"]
            parent = str(PurePosixPath(entrypoint).parent)
            task = worker_task(
                evaluator,
                evaluator_contract_path=evaluator_contract_path,
                artifact_contract_path=artifact_contract_path,
                benchmark_contract_path=benchmark_contract_path,
            )
            workers.append(
                {
                    "id": f"{manager_id}-worker-{worker_index:02d}",
                    "model": "gpt-5.6-luna",
                    "task": task,
                    "acceptance": [
                        f"Adapter exists at {entrypoint}",
                        "Adapter is valid Python and imports without syntax errors",
                        "Adapter implements the exact evaluator adapter input and output schemas",
                        "Adapter returns every required score dimension",
                        "Adapter produces every required evidence type as actual files",
                        "Adapter does not mutate production candidate artifacts",
                    ],
                    "write_scope": [parent],
                    "risk": "medium",
                    "budget": {
                        "time_minutes": 45.0,
                        "token_limit": 14000,
                        "cost_usd": 14.0,
                        "max_concurrency": 1,
                        "max_retries": 1,
                    },
                    "outcome_context": {
                        "program_version": program_version,
                        "north_star": strategy.get("north_star") or "Produce independently verified outcomes",
                        "user_value": f"Executable evaluator capability for {objective_id}",
                        "program_outcome": f"Build the independent evaluator capabilities required by {objective_id}",
                        "manager_outcome": f"Materialize evaluator adapters for {[item['evaluator_id'] for item in group]}",
                        "roadmap_position": "evaluator capability construction",
                        "dependencies": [
                            evaluator_contract_path,
                            artifact_contract_path,
                            benchmark_contract_path,
                            "skills/company-os/execute-outcome-evaluator/scripts/execute_evaluator.py",
                        ],
                        "non_goals": ["Modify product candidate artifacts", "Lower evaluator requirements"],
                        "constraints": [
                            "Independent evaluator capability cannot trust production narrative",
                            "Required experiential evidence cannot be replaced by source inspection",
                            "Fabrication of unavailable evidence is forbidden",
                        ],
                    },
                    "stop_condition": "The adapter is real and executable, or a concrete unavailable prerequisite is proven.",
                }
            )
        managers.append(
            {
                "id": manager_id,
                "model": "gpt-5.6-sol",
                "outcome": f"Build and verify evaluator adapters for {[item['evaluator_id'] for item in group]}",
                "acceptance": [
                    "Every assigned adapter path exists or has an explicit prerequisite blocker",
                    "No evaluator requirement was weakened",
                    "Worker changes remain inside disjoint evaluator adapter scopes",
                ],
                "phase_ids": PHASES,
                "budget": {
                    "time_minutes": 55.0,
                    "token_limit": 18000,
                    "cost_usd": 18.0,
                    "max_concurrency": min(3, len(workers)),
                    "max_retries": 1,
                },
                "write_scope": [manager_scope, *sorted({worker["write_scope"][0] for worker in workers})],
                "workers": workers,
            }
        )
    worker_count = sum(len(manager["workers"]) for manager in managers)
    fabric = {
        "program_id": project_id,
        "program_version": program_version,
        "outcome": f"Materialize missing independent evaluator adapters for objective {objective_id}",
        "acceptance": [
            "All adapters in this batch are materialized or expose exact external prerequisites",
            "Required evaluator contract semantics are preserved",
            "Adapters are ready for content addressed registration and calibration",
        ],
        "program_contract": {
            "north_star": strategy.get("north_star") or "Produce independently verified outcomes",
            "user_value": f"Independent quality judgment for {objective_id}",
            "rationale": "The outcome loop cannot judge reality until required evaluator capabilities exist.",
            "architecture": "Bounded adapter construction workers implement exact evaluator runtime contracts in disjoint workspace scopes.",
            "roadmap": PHASES,
            "dependencies": [evaluator_contract_path, artifact_contract_path, benchmark_contract_path],
            "non_goals": ["Production candidate modification", "Quality gate removal"],
            "constraints": ["No fabricated evidence", "No evaluator self grading by production workers"],
        },
        "max_managers": len(managers),
        "max_manager_concurrency": len(managers),
        "max_workers_per_manager": 3,
        "max_total_workers": worker_count,
        "max_depth": 2,
        "max_worker_retries": 1,
        "max_manager_rework_rounds": 2,
        "budget": {
            "time_minutes": 110.0,
            "token_limit": 36000,
            "cost_usd": 36.0,
            "max_concurrency": len(managers),
            "max_retries": 1,
        },
        "luna_token_share_target": 0.75,
        "external_effects_allowed": False,
        "managers": managers,
    }
    validation = fabric_module().validate(fabric)
    if not validation.get("valid"):
        raise BuildFabricError("E_FABRIC", "; ".join(validation.get("errors", [])))
    return {
        "complete": False,
        "objective_id": objective_id,
        "missing_evaluator_ids": [item["evaluator_id"] for item in batch],
        "remaining_evaluator_ids": remaining,
        "fabric": fabric,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evaluator-contract", required=True)
    parser.add_argument("--artifact-contract", required=True)
    parser.add_argument("--benchmark-contract", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compile_manifest(
            args.project_root,
            args.evaluator_contract,
            args.artifact_contract,
            args.benchmark_contract,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "complete": result["complete"],
                    "missing_evaluator_ids": result["missing_evaluator_ids"],
                    "remaining_evaluator_ids": result["remaining_evaluator_ids"],
                },
                sort_keys=True,
            )
        )
        return 0
    except BuildFabricError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
