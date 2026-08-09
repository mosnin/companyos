#!/usr/bin/env python3
"""Execute a content addressed outcome evaluator through a local adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

REQUEST_SCHEMA = "company-os.evaluator-execution-request.v1"
CONTRACT_SCHEMA = "company-os.evaluator-runtime-contract.v1"
REGISTRY_SCHEMA = "company-os.evaluator-adapter-registry.v1"
BENCHMARK_SCHEMA = "company-os.benchmark-contract.v1"
ADAPTER_INPUT_SCHEMA = "company-os.evaluator-adapter-input.v1"
ADAPTER_OUTPUT_SCHEMA = "company-os.evaluator-adapter-output.v1"
RECEIPT_SCHEMA = "company-os.evaluator-execution-receipt.v1"

MAX_TIMEOUT_SECONDS = 3600
MAX_OUTPUT_BYTES = 10 * 1024 * 1024
DEFAULT_OUTPUT_BYTES = 1024 * 1024
SAFE_ENVIRONMENT_KEYS = (
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TMP",
    "TEMP",
    "TMPDIR",
    "HOME",
)
FINDING_SEVERITIES = {"info", "warning", "error", "critical"}


class EvaluatorExecutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvaluatorExecutionError(
            "E_CANONICAL", f"value is not canonical JSON: {exc}"
        ) from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _reject_constant(value: str) -> None:
    raise EvaluatorExecutionError(
        "E_JSON", f"non finite JSON value is forbidden: {value}"
    )


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvaluatorExecutionError(
                "E_JSON", f"duplicate JSON key is forbidden: {key}"
            )
        result[key] = value
    return result


def parse_json_bytes(value: bytes, label: str) -> Any:
    try:
        return json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except EvaluatorExecutionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluatorExecutionError("E_JSON", f"invalid JSON in {label}") from exc


def read_json(path: Path, label: str) -> Any:
    try:
        return parse_json_bytes(path.read_bytes(), label)
    except OSError as exc:
        raise EvaluatorExecutionError(
            "E_READ", f"cannot read {label}: {path}"
        ) from exc


def require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluatorExecutionError("E_SCHEMA", f"{label} must be an object")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluatorExecutionError(
            "E_SCHEMA", f"{label} must be a nonempty string"
        )
    if "\x00" in value:
        raise EvaluatorExecutionError("E_SCHEMA", f"{label} contains a null byte")
    return value


def require_sha256(value: Any, label: str) -> str:
    text = require_text(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise EvaluatorExecutionError(
            "E_SCHEMA", f"{label} must be a lowercase sha256"
        )
    return text


def require_strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise EvaluatorExecutionError("E_SCHEMA", f"{label} must be an array")
    result = [require_text(item, f"{label}[]") for item in value]
    if nonempty and not result:
        raise EvaluatorExecutionError("E_SCHEMA", f"{label} must not be empty")
    if len(result) != len(set(result)):
        raise EvaluatorExecutionError("E_DUPLICATE", f"{label} contains duplicates")
    return sorted(result)


def require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise EvaluatorExecutionError("E_SCHEMA", f"{label} must be an array")
    return [require_text(item, f"{label}[]") for item in value]


def require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise EvaluatorExecutionError(
            "E_SCHEMA",
            f"{label} keys are invalid; missing={missing} extra={extra}",
        )


def verify_self_digest(value: Mapping[str, Any], field: str, label: str) -> str:
    observed = require_sha256(value.get(field), f"{label}.{field}")
    candidate = dict(value)
    candidate[field] = None
    if digest(candidate) != observed:
        raise EvaluatorExecutionError(
            "E_DIGEST", f"{label}.{field} does not match exact content"
        )
    return observed


def safe_file(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    raw = require_text(value, label)
    if "\\" in raw:
        raise EvaluatorExecutionError(
            "E_PATH", f"{label} must use slash separated project paths"
        )
    pure = PurePosixPath(raw)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise EvaluatorExecutionError(
            "E_PATH", f"{label} must be a safe project relative path"
        )
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise EvaluatorExecutionError(
                "E_PATH", f"{label} may not traverse a symlink"
            )
    try:
        resolved = (root / Path(*pure.parts)).resolve(strict=True)
    except OSError as exc:
        raise EvaluatorExecutionError(
            "E_PATH", f"{label} does not resolve to an existing file"
        ) from exc
    if resolved != root and root not in resolved.parents:
        raise EvaluatorExecutionError("E_PATH", f"{label} escapes the project root")
    if not resolved.is_file() or resolved.is_symlink():
        raise EvaluatorExecutionError(
            "E_PATH", f"{label} must reference a regular file"
        )
    return resolved, pure.as_posix()


def load_bound_json(
    project_root: Path,
    path_value: Any,
    label: str,
    schema: str,
    digest_field: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path, relative = safe_file(project_root, path_value, f"{label}_path")
    value = dict(require_object(read_json(path, label), label))
    if value.get("$schema") != schema:
        raise EvaluatorExecutionError(
            "E_SCHEMA", f"{label} must use schema {schema}"
        )
    content_digest = verify_self_digest(value, digest_field, label)
    return value, {
        "path": relative,
        "file_sha256": file_digest(path),
        digest_field: content_digest,
    }


def find_evaluator(contract: Mapping[str, Any], evaluator_id: str) -> dict[str, Any]:
    records = contract.get("evaluators")
    if not isinstance(records, list):
        raise EvaluatorExecutionError(
            "E_SCHEMA", "evaluator contract evaluators must be an array"
        )
    matches = [item for item in records if isinstance(item, Mapping) and item.get("evaluator_id") == evaluator_id]
    if len(matches) != 1:
        raise EvaluatorExecutionError(
            "E_EVALUATOR", f"evaluator contract must contain exactly one {evaluator_id}"
        )
    evaluator = dict(matches[0])
    if evaluator.get("research_only") is not False:
        raise EvaluatorExecutionError(
            "E_EVALUATOR", f"evaluator {evaluator_id} is research only"
        )
    if evaluator.get("independent_role") is not True:
        raise EvaluatorExecutionError(
            "E_AUTHORITY", f"evaluator {evaluator_id} is not independent"
        )
    require_text(evaluator.get("adapter_locator"), "evaluator.adapter_locator")
    require_strings(
        evaluator.get("artifact_classes"),
        "evaluator.artifact_classes",
        nonempty=True,
    )
    require_strings(
        evaluator.get("produces_evidence"),
        "evaluator.produces_evidence",
        nonempty=True,
    )
    require_strings(
        evaluator.get("score_dimensions", []),
        "evaluator.score_dimensions",
    )
    return evaluator


def validate_registry(registry: Mapping[str, Any]) -> str:
    if registry.get("$schema") != REGISTRY_SCHEMA:
        raise EvaluatorExecutionError(
            "E_SCHEMA", f"adapter registry must use schema {REGISTRY_SCHEMA}"
        )
    registry_digest = verify_self_digest(registry, "registry_sha256", "adapter registry")
    records = registry.get("adapters")
    if not isinstance(records, list) or not records:
        raise EvaluatorExecutionError(
            "E_SCHEMA", "adapter registry adapters must be a nonempty array"
        )
    locators: list[str] = []
    for index, item in enumerate(records):
        record = require_object(item, f"adapter registry adapters[{index}]")
        locators.append(
            require_text(record.get("adapter_locator"), f"adapter[{index}].adapter_locator")
        )
    if len(locators) != len(set(locators)):
        raise EvaluatorExecutionError(
            "E_DUPLICATE", "adapter registry contains duplicate locators"
        )
    return registry_digest


def resolve_adapter(
    project_root: Path,
    registry: Mapping[str, Any],
    evaluator: Mapping[str, Any],
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    locator = evaluator["adapter_locator"]
    records = registry["adapters"]
    matches = [item for item in records if isinstance(item, Mapping) and item.get("adapter_locator") == locator]
    if len(matches) != 1:
        raise EvaluatorExecutionError(
            "E_ADAPTER", f"adapter registry must contain exactly one {locator}"
        )
    adapter = dict(matches[0])
    required_keys = {
        "adapter_locator",
        "runtime",
        "entrypoint",
        "entrypoint_sha256",
        "timeout_seconds",
        "max_output_bytes",
        "arguments",
        "artifact_classes",
        "produces_evidence",
        "score_dimensions",
    }
    require_exact_keys(adapter, required_keys, f"adapter {locator}")
    runtime = adapter.get("runtime")
    if runtime not in {"python", "executable"}:
        raise EvaluatorExecutionError(
            "E_ADAPTER", f"adapter {locator} runtime is unsupported"
        )
    entrypoint, relative = safe_file(
        project_root, adapter.get("entrypoint"), f"adapter {locator}.entrypoint"
    )
    expected_entrypoint_digest = require_sha256(
        adapter.get("entrypoint_sha256"),
        f"adapter {locator}.entrypoint_sha256",
    )
    if file_digest(entrypoint) != expected_entrypoint_digest:
        raise EvaluatorExecutionError(
            "E_DIGEST", f"adapter {locator} entrypoint digest does not match"
        )
    timeout = adapter.get("timeout_seconds")
    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or timeout < 1
        or timeout > MAX_TIMEOUT_SECONDS
    ):
        raise EvaluatorExecutionError(
            "E_ADAPTER", f"adapter {locator} timeout_seconds is invalid"
        )
    max_output = adapter.get("max_output_bytes")
    if (
        not isinstance(max_output, int)
        or isinstance(max_output, bool)
        or max_output < 1024
        or max_output > MAX_OUTPUT_BYTES
    ):
        raise EvaluatorExecutionError(
            "E_ADAPTER", f"adapter {locator} max_output_bytes is invalid"
        )
    arguments = require_string_list(adapter.get("arguments"), f"adapter {locator}.arguments")
    for field in ("artifact_classes", "produces_evidence", "score_dimensions"):
        adapter_values = require_strings(adapter.get(field), f"adapter {locator}.{field}")
        evaluator_values = require_strings(evaluator.get(field), f"evaluator.{field}")
        if adapter_values != evaluator_values:
            raise EvaluatorExecutionError(
                "E_BINDING", f"adapter {locator}.{field} does not match evaluator contract"
            )
    if runtime == "executable" and not os.access(entrypoint, os.X_OK):
        raise EvaluatorExecutionError(
            "E_ADAPTER", f"adapter {locator} entrypoint is not executable"
        )
    descriptor = {
        "adapter_locator": locator,
        "runtime": runtime,
        "entrypoint": relative,
        "entrypoint_sha256": expected_entrypoint_digest,
        "arguments": arguments,
        "timeout_seconds": timeout,
        "max_output_bytes": max_output,
    }
    return adapter, entrypoint, descriptor


def validate_artifacts(
    project_root: Path,
    artifacts: Any,
    evaluator: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(artifacts, list) or not artifacts:
        raise EvaluatorExecutionError(
            "E_ARTIFACT", "execution request artifacts must be a nonempty array"
        )
    allowed_classes = set(
        require_strings(
            evaluator.get("artifact_classes"),
            "evaluator.artifact_classes",
            nonempty=True,
        )
    )
    seen: set[str] = set()
    covered: set[str] = set()
    portable: list[dict[str, Any]] = []
    runtime_values: list[dict[str, Any]] = []
    expected_keys = {"artifact_id", "artifact_class_id", "path", "sha256"}
    for index, raw in enumerate(artifacts):
        item = require_object(raw, f"artifacts[{index}]")
        require_exact_keys(item, expected_keys, f"artifacts[{index}]")
        artifact_id = require_text(item.get("artifact_id"), f"artifacts[{index}].artifact_id")
        if artifact_id in seen:
            raise EvaluatorExecutionError("E_DUPLICATE", f"duplicate artifact_id {artifact_id}")
        seen.add(artifact_id)
        artifact_class = require_text(
            item.get("artifact_class_id"),
            f"artifacts[{index}].artifact_class_id",
        )
        if artifact_class not in allowed_classes:
            raise EvaluatorExecutionError(
                "E_ARTIFACT", f"artifact {artifact_id} has an unhandled class"
            )
        path, relative = safe_file(
            project_root, item.get("path"), f"artifacts[{index}].path"
        )
        expected_digest = require_sha256(
            item.get("sha256"), f"artifacts[{index}].sha256"
        )
        observed_digest = file_digest(path)
        if observed_digest != expected_digest:
            raise EvaluatorExecutionError(
                "E_DIGEST", f"artifact {artifact_id} digest does not match"
            )
        record = {
            "artifact_id": artifact_id,
            "artifact_class_id": artifact_class,
            "path": relative,
            "sha256": observed_digest,
            "size": path.stat().st_size,
        }
        portable.append(record)
        runtime_values.append({**record, "resolved_path": str(path)})
        covered.add(artifact_class)
    missing = sorted(allowed_classes - covered)
    if missing:
        raise EvaluatorExecutionError(
            "E_ARTIFACT", f"required artifact classes are missing: {missing}"
        )
    portable.sort(key=lambda item: item["artifact_id"])
    runtime_values.sort(key=lambda item: item["artifact_id"])
    return portable, runtime_values


def safe_environment() -> dict[str, str]:
    environment = {
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    for key in SAFE_ENVIRONMENT_KEYS:
        value = os.environ.get(key)
        if value:
            environment[key] = value
    return environment


def validate_scores(value: Any, dimensions: Sequence[str]) -> dict[str, float]:
    scores = require_object(value, "adapter output scores")
    expected = set(dimensions)
    if set(scores) != expected:
        raise EvaluatorExecutionError(
            "E_OUTPUT",
            f"adapter output score dimensions are invalid; expected={sorted(expected)} observed={sorted(scores)}",
        )
    result: dict[str, float] = {}
    for dimension in sorted(expected):
        score = scores.get(dimension)
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(float(score))
            or float(score) < 0.0
            or float(score) > 10.0
        ):
            raise EvaluatorExecutionError(
                "E_OUTPUT", f"adapter output score is invalid: {dimension}"
            )
        result[dimension] = float(score)
    return result


def validate_findings(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise EvaluatorExecutionError("E_OUTPUT", "adapter output findings must be an array")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    expected = {"code", "severity", "statement"}
    for index, raw in enumerate(value):
        item = require_object(raw, f"findings[{index}]")
        require_exact_keys(item, expected, f"findings[{index}]")
        code = require_text(item.get("code"), f"findings[{index}].code")
        if code in seen:
            raise EvaluatorExecutionError("E_DUPLICATE", f"duplicate finding code {code}")
        seen.add(code)
        severity = item.get("severity")
        if severity not in FINDING_SEVERITIES:
            raise EvaluatorExecutionError(
                "E_OUTPUT", f"finding {code} has invalid severity"
            )
        statement = require_text(
            item.get("statement"), f"findings[{index}].statement"
        )
        result.append({"code": code, "severity": severity, "statement": statement})
    return sorted(result, key=lambda item: item["code"])


def validate_evidence(
    project_root: Path,
    value: Any,
    required_types: Sequence[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise EvaluatorExecutionError("E_OUTPUT", "adapter output evidence must be an array")
    required = set(required_types)
    seen_ids: set[str] = set()
    observed_types: set[str] = set()
    result: list[dict[str, Any]] = []
    expected = {"evidence_id", "evidence_type", "path"}
    for index, raw in enumerate(value):
        item = require_object(raw, f"evidence[{index}]")
        require_exact_keys(item, expected, f"evidence[{index}]")
        evidence_id = require_text(item.get("evidence_id"), f"evidence[{index}].evidence_id")
        if evidence_id in seen_ids:
            raise EvaluatorExecutionError(
                "E_DUPLICATE", f"duplicate evidence_id {evidence_id}"
            )
        seen_ids.add(evidence_id)
        evidence_type = require_text(
            item.get("evidence_type"), f"evidence[{index}].evidence_type"
        )
        if evidence_type not in required:
            raise EvaluatorExecutionError(
                "E_OUTPUT", f"evidence {evidence_id} has an undeclared type"
            )
        path, relative = safe_file(
            project_root, item.get("path"), f"evidence[{index}].path"
        )
        result.append(
            {
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "path": relative,
                "sha256": file_digest(path),
                "size": path.stat().st_size,
            }
        )
        observed_types.add(evidence_type)
    missing = sorted(required - observed_types)
    if missing:
        raise EvaluatorExecutionError(
            "E_OUTPUT", f"required evidence types are missing: {missing}"
        )
    return sorted(result, key=lambda item: item["evidence_id"])


def execute(project_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    project_root = project_root.resolve()
    if not project_root.is_dir() or project_root.is_symlink():
        raise EvaluatorExecutionError("E_PATH", "project_root must be a real directory")
    expected_request_keys = {
        "$schema",
        "run_id",
        "objective_id",
        "evaluator_id",
        "evaluator_contract_path",
        "adapter_registry_path",
        "benchmark_contract_path",
        "executor_actor_id",
        "production_actor_ids",
        "artifacts",
        "arguments",
    }
    require_exact_keys(request, expected_request_keys, "execution request")
    if request.get("$schema") != REQUEST_SCHEMA:
        raise EvaluatorExecutionError(
            "E_SCHEMA", f"execution request must use {REQUEST_SCHEMA}"
        )
    run_id = require_text(request.get("run_id"), "run_id")
    objective_id = require_text(request.get("objective_id"), "objective_id")
    evaluator_id = require_text(request.get("evaluator_id"), "evaluator_id")
    executor_actor_id = require_text(
        request.get("executor_actor_id"), "executor_actor_id"
    )
    production_actor_ids = require_strings(
        request.get("production_actor_ids"), "production_actor_ids"
    )
    if executor_actor_id in set(production_actor_ids):
        raise EvaluatorExecutionError(
            "E_AUTHORITY", "evaluator executor is a production actor"
        )
    arguments = dict(require_object(request.get("arguments"), "arguments"))
    canonical_bytes(arguments)

    evaluator_contract, evaluator_binding = load_bound_json(
        project_root,
        request.get("evaluator_contract_path"),
        "evaluator contract",
        CONTRACT_SCHEMA,
        "contract_sha256",
    )
    if evaluator_contract.get("objective_id") != objective_id:
        raise EvaluatorExecutionError(
            "E_BINDING", "evaluator contract objective_id does not match request"
        )
    if evaluator_contract.get("ready") is not True:
        raise EvaluatorExecutionError("E_EVALUATOR", "evaluator contract is not ready")
    evaluator = find_evaluator(evaluator_contract, evaluator_id)

    benchmark_contract, benchmark_binding = load_bound_json(
        project_root,
        request.get("benchmark_contract_path"),
        "benchmark contract",
        BENCHMARK_SCHEMA,
        "contract_sha256",
    )
    if benchmark_contract.get("objective_id") != objective_id:
        raise EvaluatorExecutionError(
            "E_BINDING", "benchmark contract objective_id does not match request"
        )
    if benchmark_contract.get("ready") is not True:
        raise EvaluatorExecutionError("E_BENCHMARK", "benchmark contract is not ready")

    registry, registry_binding = load_bound_json(
        project_root,
        request.get("adapter_registry_path"),
        "adapter registry",
        REGISTRY_SCHEMA,
        "registry_sha256",
    )
    validate_registry(registry)
    adapter, entrypoint, adapter_descriptor = resolve_adapter(
        project_root, registry, evaluator
    )

    artifact_bindings, runtime_artifacts = validate_artifacts(
        project_root, request.get("artifacts"), evaluator
    )
    portable_input = {
        "$schema": ADAPTER_INPUT_SCHEMA,
        "schema_version": 1,
        "run_id": run_id,
        "objective_id": objective_id,
        "evaluator_id": evaluator_id,
        "evaluator": evaluator,
        "artifacts": artifact_bindings,
        "benchmarks": benchmark_contract,
        "arguments": arguments,
    }
    runtime_input = {**portable_input, "artifacts": runtime_artifacts}
    input_payload = canonical_bytes(runtime_input)

    runtime = adapter_descriptor["runtime"]
    arguments_list = adapter_descriptor["arguments"]
    if runtime == "python":
        command = [sys.executable, str(entrypoint), *arguments_list]
    else:
        command = [str(entrypoint), *arguments_list]
    command_descriptor = {
        "runtime": runtime,
        "entrypoint": adapter_descriptor["entrypoint"],
        "arguments": arguments_list,
    }
    timeout = adapter_descriptor["timeout_seconds"]
    try:
        process = subprocess.run(
            command,
            cwd=project_root,
            env=safe_environment(),
            input=input_payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvaluatorExecutionError(
            "E_TIMEOUT", f"evaluator adapter exceeded {timeout} seconds"
        ) from exc
    max_output = adapter_descriptor["max_output_bytes"]
    if len(process.stdout) > max_output or len(process.stderr) > max_output:
        raise EvaluatorExecutionError(
            "E_OUTPUT", "evaluator adapter output exceeded its byte limit"
        )
    stdout_sha256 = bytes_digest(process.stdout)
    stderr_sha256 = bytes_digest(process.stderr)
    if process.returncode != 0:
        raise EvaluatorExecutionError(
            "E_ADAPTER",
            f"evaluator adapter exited nonzero; code={process.returncode} stderr_sha256={stderr_sha256}",
        )

    output = dict(
        require_object(parse_json_bytes(process.stdout, "adapter stdout"), "adapter output")
    )
    expected_output_keys = {
        "$schema",
        "run_id",
        "objective_id",
        "evaluator_id",
        "accepted",
        "scores",
        "findings",
        "evidence",
    }
    require_exact_keys(output, expected_output_keys, "adapter output")
    if output.get("$schema") != ADAPTER_OUTPUT_SCHEMA:
        raise EvaluatorExecutionError(
            "E_OUTPUT", f"adapter output must use {ADAPTER_OUTPUT_SCHEMA}"
        )
    for field, expected in (
        ("run_id", run_id),
        ("objective_id", objective_id),
        ("evaluator_id", evaluator_id),
    ):
        if output.get(field) != expected:
            raise EvaluatorExecutionError(
                "E_BINDING", f"adapter output {field} does not match execution request"
            )
    accepted = output.get("accepted")
    if not isinstance(accepted, bool):
        raise EvaluatorExecutionError(
            "E_OUTPUT", "adapter output accepted must be boolean"
        )
    score_dimensions = require_strings(
        evaluator.get("score_dimensions", []), "evaluator.score_dimensions"
    )
    scores = validate_scores(output.get("scores"), score_dimensions)
    findings = validate_findings(output.get("findings"))
    required_evidence = require_strings(
        evaluator.get("produces_evidence"),
        "evaluator.produces_evidence",
        nonempty=True,
    )
    evidence_bindings = validate_evidence(
        project_root, output.get("evidence"), required_evidence
    )

    receipt: dict[str, Any] = {
        "$schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "run_id": run_id,
        "objective_id": objective_id,
        "evaluator_id": evaluator_id,
        "executor_actor_id": executor_actor_id,
        "production_actor_ids": production_actor_ids,
        "independent_role": True,
        "accepted": accepted,
        "scores": scores,
        "findings": findings,
        "artifact_bindings": artifact_bindings,
        "evidence_bindings": evidence_bindings,
        "source_bindings": {
            "evaluator_contract": evaluator_binding,
            "benchmark_contract": benchmark_binding,
            "adapter_registry": registry_binding,
            "adapter_entrypoint": {
                "path": adapter_descriptor["entrypoint"],
                "file_sha256": adapter_descriptor["entrypoint_sha256"],
            },
        },
        "execution": {
            "adapter_locator": evaluator["adapter_locator"],
            "runtime": runtime,
            "command_sha256": digest(command_descriptor),
            "timeout_seconds": timeout,
            "exit_code": process.returncode,
            "stdout_sha256": stdout_sha256,
            "stderr_sha256": stderr_sha256,
            "adapter_input_sha256": digest(portable_input),
            "adapter_output_sha256": digest(output),
        },
    }
    receipt["receipt_sha256"] = digest({**receipt, "receipt_sha256": None})
    return receipt


def verify_file_binding(project_root: Path, binding: Mapping[str, Any], label: str) -> None:
    path, _ = safe_file(project_root, binding.get("path"), f"{label}.path")
    expected = require_sha256(binding.get("file_sha256"), f"{label}.file_sha256")
    if file_digest(path) != expected:
        raise EvaluatorExecutionError(
            "E_DIGEST", f"{label} file digest does not match"
        )


def verify_receipt(project_root: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("$schema") != RECEIPT_SCHEMA:
        raise EvaluatorExecutionError(
            "E_SCHEMA", f"execution receipt must use {RECEIPT_SCHEMA}"
        )
    receipt_sha256 = verify_self_digest(
        receipt, "receipt_sha256", "execution receipt"
    )
    executor = require_text(receipt.get("executor_actor_id"), "executor_actor_id")
    production = require_strings(
        receipt.get("production_actor_ids"), "production_actor_ids"
    )
    if receipt.get("independent_role") is not True or executor in set(production):
        raise EvaluatorExecutionError(
            "E_AUTHORITY", "execution receipt is not independent from production"
        )
    sources = require_object(receipt.get("source_bindings"), "source_bindings")
    for label in (
        "evaluator_contract",
        "benchmark_contract",
        "adapter_registry",
        "adapter_entrypoint",
    ):
        verify_file_binding(
            project_root,
            require_object(sources.get(label), f"source_bindings.{label}"),
            f"source_bindings.{label}",
        )
    for collection_name in ("artifact_bindings", "evidence_bindings"):
        values = receipt.get(collection_name)
        if not isinstance(values, list) or not values:
            raise EvaluatorExecutionError(
                "E_SCHEMA", f"{collection_name} must be a nonempty array"
            )
        for index, raw in enumerate(values):
            binding = require_object(raw, f"{collection_name}[{index}]")
            path, _ = safe_file(
                project_root, binding.get("path"), f"{collection_name}[{index}].path"
            )
            expected = require_sha256(
                binding.get("sha256"), f"{collection_name}[{index}].sha256"
            )
            if file_digest(path) != expected:
                raise EvaluatorExecutionError(
                    "E_DIGEST", f"{collection_name}[{index}] file digest does not match"
                )
    return {
        "receipt_sha256": receipt_sha256,
        "objective_id": require_text(receipt.get("objective_id"), "objective_id"),
        "evaluator_id": require_text(receipt.get("evaluator_id"), "evaluator_id"),
        "accepted": receipt.get("accepted") is True,
        "independent_role": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--project-root", required=True, type=Path)
    execute_parser.add_argument("--request", required=True, type=Path)
    execute_parser.add_argument("--output", required=True, type=Path)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project-root", required=True, type=Path)
    verify_parser.add_argument("--receipt", required=True, type=Path)

    args = parser.parse_args()
    if args.command == "execute":
        request = require_object(read_json(args.request, "execution request"), "execution request")
        receipt = execute(args.project_root, request)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"evaluator executed id={receipt['evaluator_id']} accepted={receipt['accepted']}"
        )
        return
    receipt = require_object(read_json(args.receipt, "execution receipt"), "execution receipt")
    result = verify_receipt(args.project_root, receipt)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
