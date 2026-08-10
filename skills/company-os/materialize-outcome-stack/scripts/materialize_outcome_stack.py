#!/usr/bin/env python3
"""Materialize synthesized outcome knowledge into executable Company OS contracts."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping

OUTCOME_REQUEST_SCHEMA = "company-os.outcome-request.v1"
RECEIPT_SCHEMA = "company-os.outcome-stack-receipt.v1"
ALLOWED_BENCHMARK_TIERS = {"negative", "baseline", "strong", "exemplar"}


class StackError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise StackError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise StackError("E_SCHEMA", f"{label} must be an array")
    return value


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StackError("E_SCHEMA", f"{label} must be an object")
    return value


def load_module(relative: str, name: str):
    path = Path(__file__).resolve().parents[2] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise StackError("E_RUNTIME", f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artifact_module():
    return load_module(
        "define-outcome-artifacts/scripts/compile_artifact_observations.py",
        "company_os_materialize_artifacts",
    )


def evaluator_module():
    return load_module(
        "compile-outcome-evaluators/scripts/compile_evaluator_runtime.py",
        "company_os_materialize_evaluators",
    )


def benchmark_module():
    return load_module(
        "compile-outcome-benchmarks/scripts/compile_benchmarks.py",
        "company_os_materialize_benchmarks",
    )


def artifact_request(outcome: Mapping[str, Any]) -> dict[str, Any]:
    objective_id = text(outcome.get("objective_id"), "objective_id")
    records = []
    seen: set[str] = set()
    for index, raw in enumerate(array(outcome.get("artifact_classes"), "artifact_classes")):
        item = obj(raw, f"artifact_classes[{index}]")
        artifact_id = text(item.get("artifact_class_id"), f"artifact_classes[{index}].artifact_class_id")
        if artifact_id in seen:
            raise StackError("E_DUPLICATE", f"duplicate artifact class {artifact_id}")
        seen.add(artifact_id)
        records.append(
            {
                "artifact_class_id": artifact_id,
                "label": text(item.get("label"), f"{artifact_id}.label"),
                "required": item.get("required", True),
                "modalities": list(array(item.get("modalities"), f"{artifact_id}.modalities")),
                "observation_methods": list(
                    array(item.get("observation_methods"), f"{artifact_id}.observation_methods")
                ),
                "required_evidence": list(
                    array(item.get("required_evidence"), f"{artifact_id}.required_evidence")
                ),
            }
        )
    if not records:
        raise StackError("E_INCOMPLETE", "outcome has no artifact classes")
    return {
        "$schema": "company-os.artifact-observation-request.v1",
        "objective_id": objective_id,
        "artifact_classes": sorted(records, key=lambda item: item["artifact_class_id"]),
    }


def evaluator_request(outcome: Mapping[str, Any]) -> dict[str, Any]:
    objective_id = text(outcome.get("objective_id"), "objective_id")
    records = []
    seen: set[str] = set()
    for index, raw in enumerate(array(outcome.get("evaluators"), "evaluators")):
        item = obj(raw, f"evaluators[{index}]")
        evaluator_id = text(item.get("evaluator_id"), f"evaluators[{index}].evaluator_id")
        if evaluator_id in seen:
            raise StackError("E_DUPLICATE", f"duplicate evaluator {evaluator_id}")
        seen.add(evaluator_id)
        records.append(
            {
                "evaluator_id": evaluator_id,
                "label": text(item.get("label"), f"{evaluator_id}.label"),
                "required": item.get("required", True),
                "independent_role": item.get("independent_role") is True,
                "research_only": item.get("research_only") is True,
                "adapter_locator": text(item.get("adapter_locator"), f"{evaluator_id}.adapter_locator"),
                "artifact_classes": list(
                    array(item.get("artifact_classes"), f"{evaluator_id}.artifact_classes")
                ),
                "produces_evidence": list(
                    array(item.get("produces_evidence"), f"{evaluator_id}.produces_evidence")
                ),
                "score_dimensions": list(
                    array(item.get("score_dimensions"), f"{evaluator_id}.score_dimensions")
                ),
            }
        )
    if not records:
        raise StackError("E_INCOMPLETE", "outcome has no evaluator definitions")
    return {
        "$schema": "company-os.evaluator-runtime-request.v1",
        "objective_id": objective_id,
        "evaluators": sorted(records, key=lambda item: item["evaluator_id"]),
    }


def benchmark_request(outcome: Mapping[str, Any]) -> dict[str, Any]:
    objective_id = text(outcome.get("objective_id"), "objective_id")
    dimensions = []
    seen: set[str] = set()
    for index, raw in enumerate(array(outcome.get("benchmarks"), "benchmarks")):
        item = obj(raw, f"benchmarks[{index}]")
        benchmark_id = text(item.get("benchmark_id"), f"benchmarks[{index}].benchmark_id")
        if benchmark_id in seen:
            raise StackError("E_DUPLICATE", f"duplicate benchmark {benchmark_id}")
        seen.add(benchmark_id)
        references_raw = item.get("reference_records")
        if references_raw is None:
            raise StackError(
                "E_INCOMPLETE",
                f"benchmark {benchmark_id} lacks structured reference_records from discovery synthesis",
            )
        references = []
        ref_ids: set[str] = set()
        for ref_index, raw_ref in enumerate(array(references_raw, f"{benchmark_id}.reference_records")):
            ref = obj(raw_ref, f"{benchmark_id}.reference_records[{ref_index}]")
            reference_id = text(ref.get("reference_id"), f"{benchmark_id}.reference_id")
            if reference_id in ref_ids:
                raise StackError("E_DUPLICATE", f"duplicate benchmark reference {reference_id}")
            ref_ids.add(reference_id)
            tier = text(ref.get("quality_tier"), f"{reference_id}.quality_tier")
            if tier not in ALLOWED_BENCHMARK_TIERS:
                raise StackError(
                    "E_BENCHMARK_TIER",
                    f"benchmark reference {reference_id} uses unsupported quality tier {tier}",
                )
            references.append(
                {
                    "reference_id": reference_id,
                    "locator": text(ref.get("locator"), f"{reference_id}.locator"),
                    "provenance": text(ref.get("provenance"), f"{reference_id}.provenance"),
                    "quality_tier": tier,
                }
            )
        dimensions.append(
            {
                "dimension_id": benchmark_id,
                "label": text(item.get("dimension"), f"{benchmark_id}.dimension"),
                "required": item.get("required", True),
                "references": sorted(references, key=lambda ref: ref["reference_id"]),
            }
        )
    if not dimensions:
        raise StackError("E_INCOMPLETE", "outcome has no benchmark definitions")
    return {
        "$schema": "company-os.benchmark-request.v1",
        "objective_id": objective_id,
        "dimensions": sorted(dimensions, key=lambda item: item["dimension_id"]),
    }


def compile_stack(outcome: Mapping[str, Any]) -> dict[str, Any]:
    if outcome.get("$schema") != OUTCOME_REQUEST_SCHEMA:
        raise StackError("E_SCHEMA", f"outcome request must use {OUTCOME_REQUEST_SCHEMA}")
    objective_id = text(outcome.get("objective_id"), "objective_id")
    artifacts_request = artifact_request(outcome)
    evaluators_request = evaluator_request(outcome)
    benchmarks_request = benchmark_request(outcome)
    try:
        artifacts_contract = artifact_module().compile_contract(artifacts_request)
        evaluators_contract = evaluator_module().compile_contract(evaluators_request)
        benchmarks_contract = benchmark_module().compile_contract(benchmarks_request)
    except Exception as exc:
        raise StackError(getattr(exc, "code", "E_CONTRACT"), f"runtime contract compilation failed: {exc}") from exc
    contracts = {
        "artifact": artifacts_contract,
        "evaluator": evaluators_contract,
        "benchmark": benchmarks_contract,
    }
    not_ready = [name for name, contract in contracts.items() if contract.get("ready") is not True]
    if not_ready:
        detail = []
        for name in not_ready:
            detail.extend(
                f"{name}:{item.get('code')}:{item.get('artifact_class_id') or item.get('evaluator_id') or item.get('dimension_id') or ''}"
                for item in contracts[name].get("blockers", [])
            )
        raise StackError(
            "E_NOT_READY",
            "runtime contracts are not ready: " + "; ".join(detail or not_ready),
        )
    return {
        "objective_id": objective_id,
        "outcome_request_sha256": digest(outcome),
        "requests": {
            "artifact": artifacts_request,
            "evaluator": evaluators_request,
            "benchmark": benchmarks_request,
        },
        "contracts": contracts,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def materialize(outcome_path: Path, output_dir: Path) -> dict[str, Any]:
    try:
        raw = json.loads(outcome_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StackError("E_JSON", f"cannot read outcome request: {exc}") from exc
    outcome = obj(raw, "outcome request")
    stack = compile_stack(outcome)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "artifact_request": output_dir / "artifact-request.json",
        "artifact_contract": output_dir / "artifact-contract.json",
        "evaluator_request": output_dir / "evaluator-request.json",
        "evaluator_contract": output_dir / "evaluator-contract.json",
        "benchmark_request": output_dir / "benchmark-request.json",
        "benchmark_contract": output_dir / "benchmark-contract.json",
    }
    write_json(paths["artifact_request"], stack["requests"]["artifact"])
    write_json(paths["artifact_contract"], stack["contracts"]["artifact"])
    write_json(paths["evaluator_request"], stack["requests"]["evaluator"])
    write_json(paths["evaluator_contract"], stack["contracts"]["evaluator"])
    write_json(paths["benchmark_request"], stack["requests"]["benchmark"])
    write_json(paths["benchmark_contract"], stack["contracts"]["benchmark"])
    receipt = {
        "$schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "objective_id": stack["objective_id"],
        "outcome_request_path": str(outcome_path),
        "outcome_request_sha256": stack["outcome_request_sha256"],
        "artifacts": {
            name: {"path": str(path), "file_sha256": file_digest(path)}
            for name, path in sorted(paths.items())
        },
        "contract_sha256s": {
            "artifact": stack["contracts"]["artifact"]["contract_sha256"],
            "evaluator": stack["contracts"]["evaluator"]["contract_sha256"],
            "benchmark": stack["contracts"]["benchmark"]["contract_sha256"],
        },
        "next_action": "register_or_build_required_evaluator_adapters",
        "receipt_sha256": None,
    }
    receipt["receipt_sha256"] = digest(receipt)
    write_json(output_dir / "stack-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outcome-request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = materialize(args.outcome_request, args.output_dir)
        print(json.dumps({"ok": True, **receipt}, sort_keys=True))
        return 0
    except StackError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
