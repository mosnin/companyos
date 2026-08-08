#!/usr/bin/env python3
"""Compile native Company OS production dispatch only with current outcome authorization."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "prepare_native_codex_dispatch.py"
AUTH_SCHEMA = "company-os.outcome-scale-authorization.v1"
OUTCOME_SCHEMA = "company-os.outcome-contract.v1"


class AuthorizedDispatchError(ValueError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("company_os_native_dispatch_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise AuthorizedDispatchError("cannot load native dispatch bridge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def outcome_canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def outcome_digest(value: Any) -> str:
    return hashlib.sha256(outcome_canonical_bytes(value)).hexdigest()


def validate_outcome_authorization(
    kernel: Mapping[str, Any],
    authorization: Mapping[str, Any],
    outcome: Mapping[str, Any],
) -> str:
    if authorization.get("$schema") != AUTH_SCHEMA:
        raise AuthorizedDispatchError("outcome scale authorization schema is unsupported")
    if authorization.get("authorized") is not True:
        raise AuthorizedDispatchError("outcome scale authorization does not authorize production")
    if authorization.get("blockers") != []:
        raise AuthorizedDispatchError("authorized outcome receipt contains blockers")
    if outcome.get("$schema") != OUTCOME_SCHEMA:
        raise AuthorizedDispatchError("outcome contract schema is unsupported")
    objective_id = outcome.get("objective_id")
    if not isinstance(objective_id, str) or not objective_id:
        raise AuthorizedDispatchError("outcome objective_id is invalid")
    if authorization.get("objective_id") != objective_id:
        raise AuthorizedDispatchError("authorization and outcome objective IDs differ")
    original_objective = outcome.get("original_objective")
    if not isinstance(original_objective, str) or not original_objective:
        raise AuthorizedDispatchError("outcome original objective is invalid")
    if kernel.get("objective") != original_objective:
        raise AuthorizedDispatchError("kernel objective differs from authorized original objective")
    bindings = authorization.get("input_bindings")
    if not isinstance(bindings, Mapping):
        raise AuthorizedDispatchError("authorization input bindings are missing")
    if bindings.get("outcome_sha256") != outcome_digest(outcome):
        raise AuthorizedDispatchError("authorization is stale for the supplied outcome contract")
    supplied = authorization.get("authorization_sha256")
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise AuthorizedDispatchError("authorization digest is invalid")
    unsigned = dict(authorization)
    unsigned["authorization_sha256"] = None
    if outcome_digest(unsigned) != supplied:
        raise AuthorizedDispatchError("authorization digest does not verify")
    return supplied


def read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AuthorizedDispatchError(f"{label} must be a regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorizedDispatchError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AuthorizedDispatchError(f"{label} must be an object")
    return value


def command_compile(args: argparse.Namespace) -> int:
    try:
        kernel = BASE.RECONCILE.verify_kernel_document(Path(args.kernel))
        claim = BASE.read_canonical(Path(args.claim), "command claim")
        binding = BASE.read_canonical(Path(args.binding), "host binding")
        authorization = read_object(Path(args.outcome_authorization), "outcome authorization")
        outcome = read_object(Path(args.outcome_contract), "outcome contract")
        authorization_digest = validate_outcome_authorization(kernel, authorization, outcome)
        dispatch = BASE.build_dispatch(kernel, claim, binding)
        dispatch["outcome_authorization_sha256"] = authorization_digest
        dispatch.pop("dispatch_digest")
        dispatch["dispatch_digest"] = BASE.digest_text(BASE.canonical_json(dispatch))
        print(BASE.canonical_json(dispatch))
        return 0
    except (
        AuthorizedDispatchError,
        BASE.NativeBridgeError,
        BASE.RECONCILE.ReconciliationError,
        BASE.RECONCILE.KERNEL.KernelError,
        OSError,
    ) as exc:
        print(BASE.canonical_json({"ok": False, "errors": [str(exc)]}))
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    compile_parser = root.add_subparsers(dest="command", required=True).add_parser("compile")
    compile_parser.add_argument("--kernel", required=True)
    compile_parser.add_argument("--claim", required=True)
    compile_parser.add_argument("--binding", required=True)
    compile_parser.add_argument("--outcome-authorization", required=True)
    compile_parser.add_argument("--outcome-contract", required=True)
    compile_parser.set_defaults(handler=command_compile)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
