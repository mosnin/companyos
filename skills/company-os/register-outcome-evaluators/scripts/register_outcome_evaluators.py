#!/usr/bin/env python3
"""Register required outcome evaluators against real project local adapter bytes."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

CONTRACT_SCHEMA = "company-os.evaluator-runtime-contract.v1"
REGISTRY_SCHEMA = "company-os.evaluator-adapter-registry.v1"
WORKSPACE_PREFIX = "workspace://"


class RegistryError(ValueError):
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
        raise RegistryError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RegistryError("E_SCHEMA", f"{label} must be an object")
    return value


def sha256(value: Any, label: str) -> str:
    value = text(value, label)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise RegistryError("E_SCHEMA", f"{label} must be lowercase sha256")
    return value


def execute_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "execute-outcome-evaluator/scripts/execute_evaluator.py"
    )
    spec = importlib.util.spec_from_file_location("company_os_register_evaluator_runtime", path)
    if spec is None or spec.loader is None:
        raise RegistryError("E_RUNTIME", "execute outcome evaluator runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError("E_JSON", f"cannot read {label}: {path}") from exc


def verify_contract(raw: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(raw)
    if contract.get("$schema") != CONTRACT_SCHEMA:
        raise RegistryError("E_SCHEMA", f"evaluator contract must use {CONTRACT_SCHEMA}")
    observed = sha256(contract.get("contract_sha256"), "contract_sha256")
    if digest({**contract, "contract_sha256": None}) != observed:
        raise RegistryError("E_DIGEST", "evaluator contract content digest does not match")
    if contract.get("ready") is not True:
        raise RegistryError("E_NOT_READY", "evaluator contract is not ready")
    return contract


def workspace_path(project_root: Path, locator: str, label: str) -> tuple[Path, str]:
    locator = text(locator, label)
    if not locator.startswith(WORKSPACE_PREFIX):
        raise RegistryError(
            "E_LOCATOR",
            f"{label} must use workspace:// for locally constructed evaluator adapters",
        )
    raw = locator[len(WORKSPACE_PREFIX) :]
    if not raw or "\\" in raw:
        raise RegistryError("E_LOCATOR", f"{label} workspace path is invalid")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise RegistryError("E_LOCATOR", f"{label} workspace path is unsafe")
    root = project_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise RegistryError("E_PATH", "project_root must be a real directory")
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise RegistryError("E_PATH", f"{label} may not traverse a symlink")
    candidate = root / Path(*pure.parts)
    if not candidate.exists():
        raise RegistryError(
            "E_ADAPTER_MISSING",
            f"required evaluator adapter does not exist: {pure.as_posix()}",
        )
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise RegistryError("E_ADAPTER_MISSING", f"cannot resolve adapter {raw}") from exc
    if (resolved != root and root not in resolved.parents) or not resolved.is_file() or resolved.is_symlink():
        raise RegistryError("E_PATH", f"required adapter is not a regular project file: {raw}")
    return resolved, pure.as_posix()


def adapter_record(
    project_root: Path,
    evaluator: Mapping[str, Any],
    *,
    timeout_seconds: int,
    max_output_bytes: int,
) -> dict[str, Any]:
    evaluator_id = text(evaluator.get("evaluator_id"), "evaluator_id")
    locator = text(evaluator.get("adapter_locator"), f"{evaluator_id}.adapter_locator")
    entrypoint, relative = workspace_path(project_root, locator, f"{evaluator_id}.adapter_locator")
    artifact_classes = evaluator.get("artifact_classes")
    evidence = evaluator.get("produces_evidence")
    dimensions = evaluator.get("score_dimensions", [])
    for value, label in (
        (artifact_classes, f"{evaluator_id}.artifact_classes"),
        (evidence, f"{evaluator_id}.produces_evidence"),
        (dimensions, f"{evaluator_id}.score_dimensions"),
    ):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise RegistryError("E_SCHEMA", f"{label} is invalid")
    return {
        "adapter_locator": locator,
        "runtime": "python",
        "entrypoint": relative,
        "entrypoint_sha256": file_digest(entrypoint),
        "timeout_seconds": timeout_seconds,
        "max_output_bytes": max_output_bytes,
        "arguments": [],
        "artifact_classes": sorted(artifact_classes),
        "produces_evidence": sorted(evidence),
        "score_dimensions": sorted(dimensions),
    }


def build_registry(
    project_root: Path,
    contract_raw: Mapping[str, Any],
    *,
    timeout_seconds: int = 300,
    max_output_bytes: int = 1024 * 1024,
) -> dict[str, Any]:
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 3600:
        raise RegistryError("E_SCHEMA", "timeout_seconds must be between 1 and 3600")
    if not isinstance(max_output_bytes, int) or isinstance(max_output_bytes, bool) or not 1024 <= max_output_bytes <= 10 * 1024 * 1024:
        raise RegistryError("E_SCHEMA", "max_output_bytes is outside the evaluator runtime bounds")
    contract = verify_contract(contract_raw)
    records = contract.get("evaluators")
    if not isinstance(records, list) or not records:
        raise RegistryError("E_SCHEMA", "evaluator contract contains no evaluators")
    required = [
        dict(record)
        for record in records
        if isinstance(record, Mapping) and record.get("required") is True
    ]
    if not required:
        raise RegistryError("E_SCHEMA", "evaluator contract contains no required evaluators")
    adapters = [
        adapter_record(
            project_root,
            evaluator,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
        for evaluator in sorted(required, key=lambda item: str(item.get("evaluator_id", "")))
    ]
    locators = [adapter["adapter_locator"] for adapter in adapters]
    if len(locators) != len(set(locators)):
        raise RegistryError("E_DUPLICATE", "multiple required evaluators resolve to the same adapter locator")
    registry = {
        "$schema": REGISTRY_SCHEMA,
        "schema_version": 1,
        "adapters": adapters,
        "registry_sha256": None,
    }
    registry["registry_sha256"] = digest(registry)
    runtime = execute_module()
    try:
        runtime.validate_registry(registry)
        for evaluator in required:
            runtime.resolve_adapter(project_root, registry, evaluator)
    except Exception as exc:
        raise RegistryError(
            getattr(exc, "code", "E_ADAPTER"),
            f"adapter registry does not satisfy evaluator runtime: {exc}",
        ) from exc
    return registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evaluator-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--max-output-bytes", type=int, default=1024 * 1024)
    args = parser.parse_args()
    try:
        contract = obj(read_json(args.evaluator_contract, "evaluator contract"), "evaluator contract")
        registry = build_registry(
            args.project_root,
            contract,
            timeout_seconds=args.timeout_seconds,
            max_output_bytes=args.max_output_bytes,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "registry_sha256": registry["registry_sha256"],
                    "adapter_count": len(registry["adapters"]),
                },
                sort_keys=True,
            )
        )
        return 0
    except RegistryError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
