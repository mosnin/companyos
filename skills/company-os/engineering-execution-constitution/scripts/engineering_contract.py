#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "company-os.engineering-execution-contract.v1"
LEVELS = {"master": 0, "mid": 1, "lower": 2, "worker": 3}
BOOLEAN_GATES = (
    "loom_delivery_loop",
    "durable_state",
    "exclusive_write_ownership",
    "skill_resolution_required",
    "runtime_observation_required",
    "independent_review_required",
    "original_objective_acceptance_required",
)
SECURITY = {"not_applicable": 0, "static": 1, "authorized_pentest": 2}

class ContractError(ValueError):
    pass

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be nonempty")
    return value

def seal(value: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(value)
    out["contract_sha256"] = None
    out["contract_sha256"] = digest(out)
    return out

def verify(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(raw)
    if value.get("$schema") != SCHEMA:
        raise ContractError("engineering contract schema is invalid")
    level = value.get("manager_level")
    if level not in LEVELS:
        raise ContractError("manager_level is invalid")
    text(value.get("contract_id"), "contract_id")
    text(value.get("objective_id"), "objective_id")
    rigor = value.get("engineering_rigor")
    if not isinstance(rigor, int) or isinstance(rigor, bool) or not 1 <= rigor <= 10:
        raise ContractError("engineering_rigor must be 1..10")
    for gate in BOOLEAN_GATES:
        if value.get(gate) is not True:
            raise ContractError(f"mandatory gate {gate} must be true")
    if value.get("security_verification") not in SECURITY:
        raise ContractError("security_verification is invalid")
    skills = value.get("required_skills")
    if not isinstance(skills, list) or not all(isinstance(x, str) and x.strip() for x in skills):
        raise ContractError("required_skills must be strings")
    scopes = value.get("write_scopes")
    if not isinstance(scopes, list) or not all(isinstance(x, str) and x.strip() for x in scopes):
        raise ContractError("write_scopes must be strings")
    observed = value.get("contract_sha256")
    if not isinstance(observed, str) or len(observed) != 64:
        raise ContractError("contract_sha256 is invalid")
    if digest({**value, "contract_sha256": None}) != observed:
        raise ContractError("engineering contract digest changed")
    return value

def derive(parent_raw: Mapping[str, Any], child: Mapping[str, Any]) -> dict[str, Any]:
    parent = verify(parent_raw)
    level = child.get("manager_level")
    if level not in LEVELS or LEVELS[level] <= LEVELS[parent["manager_level"]]:
        raise ContractError("child level must be below parent level")
    if child.get("objective_id") != parent["objective_id"]:
        raise ContractError("child objective cannot drift")
    rigor = child.get("engineering_rigor", parent["engineering_rigor"])
    if rigor < parent["engineering_rigor"]:
        raise ContractError("child cannot weaken engineering rigor")
    security = child.get("security_verification", parent["security_verification"])
    if SECURITY.get(security, -1) < SECURITY[parent["security_verification"]]:
        raise ContractError("child cannot weaken security verification")
    required_skills = sorted(set(parent["required_skills"]) | set(child.get("required_skills", [])))
    out = {
        "$schema": SCHEMA,
        "contract_id": text(child.get("contract_id"), "contract_id"),
        "objective_id": parent["objective_id"],
        "manager_level": level,
        "parent_contract_sha256": parent["contract_sha256"],
        "engineering_rigor": rigor,
        "security_verification": security,
        "required_skills": required_skills,
        "write_scopes": list(child.get("write_scopes", [])),
    }
    for gate in BOOLEAN_GATES:
        requested = child.get(gate, parent[gate])
        if parent[gate] is True and requested is not True:
            raise ContractError(f"child cannot weaken {gate}")
        out[gate] = requested
    return seal(out)

def root(request: Mapping[str, Any]) -> dict[str, Any]:
    value = {
        "$schema": SCHEMA,
        "contract_id": text(request.get("contract_id"), "contract_id"),
        "objective_id": text(request.get("objective_id"), "objective_id"),
        "manager_level": "master",
        "parent_contract_sha256": None,
        "engineering_rigor": int(request.get("engineering_rigor", 8)),
        "security_verification": request.get("security_verification", "static"),
        "required_skills": sorted(set(request.get("required_skills", []))),
        "write_scopes": list(request.get("write_scopes", [])),
    }
    for gate in BOOLEAN_GATES:
        value[gate] = True
    return seal(value)

def assert_nonoverlap(contracts: list[Mapping[str, Any]]) -> None:
    owners: dict[str, str] = {}
    for raw in contracts:
        contract = verify(raw)
        for scope in contract["write_scopes"]:
            if scope in owners:
                raise ContractError(f"write scope {scope} has multiple writers: {owners[scope]} and {contract['contract_id']}")
            owners[scope] = contract["contract_id"]

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    make = sub.add_parser("root"); make.add_argument("--request", type=Path, required=True); make.add_argument("--output", type=Path, required=True)
    child = sub.add_parser("derive"); child.add_argument("--parent", type=Path, required=True); child.add_argument("--request", type=Path, required=True); child.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify"); check.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    try:
        read = lambda p: json.loads(p.read_text())
        if args.cmd == "root": result = root(read(args.request)); args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        elif args.cmd == "derive": result = derive(read(args.parent), read(args.request)); args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        else: result = verify(read(args.contract))
        print(json.dumps({"ok": True, "contract_sha256": result["contract_sha256"]}, sort_keys=True)); return 0
    except (ContractError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)); return 2

if __name__ == "__main__":
    raise SystemExit(main())
