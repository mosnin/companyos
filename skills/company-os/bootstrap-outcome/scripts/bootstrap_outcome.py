#!/usr/bin/env python3
"""Bootstrap a vague objective into bounded Company OS discovery work."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Mapping

REQUEST_SCHEMA = "company-os.outcome-request.v1"
PHASES = ["charter", "discovery", "design", "execution", "verification", "integration"]

class BootstrapError(ValueError):
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
        raise BootstrapError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()

def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result:
        raise BootstrapError("E_SCHEMA", "objective_id cannot normalize to an empty path")
    return result[:64]

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BootstrapError("E_RUNTIME", f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]

def company_os_root() -> Path:
    return Path(__file__).resolve().parents[2]

def outcome_module():
    return load_module(company_os_root() / "compile-outcome-contract/scripts/compile_outcome_contract.py", "company_os_bootstrap_outcome_contract")

def loop_module():
    return load_module(company_os_root() / "elastic-company-os/scripts/outcome_loop.py", "company_os_bootstrap_outcome_loop")

def control_store_module():
    return load_module(company_os_root() / "elastic-company-os/scripts/control_store.py", "company_os_bootstrap_control_store")

def fabric_module():
    return load_module(repo_root() / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py", "company_os_bootstrap_fabric")

def seed_request(objective_id: str, objective: str) -> dict[str, Any]:
    objective_id = text(objective_id, "objective_id")
    objective = text(objective, "objective")
    unknowns = [
        {
            "unknown_id": "success-state",
            "question": "What observable real world state would prove the original objective succeeded?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["cited_success_definition", "measurable_outcome_claims"],
        },
        {
            "unknown_id": "domain-constraints",
            "question": "What domain, platform, operational, legal, technical, or distribution constraints define a valid solution?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["primary_domain_sources", "constraint_summary", "counterevidence_review"],
        },
        {
            "unknown_id": "artifact-reality",
            "question": "What actual artifacts must exist, and how can each artifact be exercised or independently observed?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["artifact_classes", "observation_methods", "required_evidence_types"],
        },
        {
            "unknown_id": "quality-bar",
            "question": "What observable properties distinguish weak, baseline, strong, and exemplar outcomes in this domain?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["benchmark_set", "quality_dimensions", "failure_signatures"],
        },
        {
            "unknown_id": "evaluator-runtime",
            "question": "How can independent evaluators execute against the actual artifacts and produce the evidence required to judge quality?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["evaluator_methods", "independent_roles", "evidence_outputs"],
        },
        {
            "unknown_id": "reality-acceptance",
            "question": "How can a fresh independent evaluator judge the final candidate against the original objective without trusting the production team's narrative?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["independent_acceptance_policy", "original_objective_binding"],
        },
    ]
    return {
        "$schema": REQUEST_SCHEMA,
        "objective_id": objective_id,
        "objective": objective,
        "outcome_claims": [],
        "domain_hypotheses": [
            {
                "domain_id": "initial-domain-uncertainty",
                "hypothesis": "Domain specific constraints, artifact reality, and quality criteria must be established from evidence before production.",
                "status": "hypothesis",
            }
        ],
        "artifact_classes": [],
        "evaluators": [],
        "benchmarks": [],
        "unknowns": unknowns,
        "reality_acceptance": None,
    }

def agenda_groups(contract: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    agenda = contract.get("discovery_agenda")
    if not isinstance(agenda, list) or not agenda:
        raise BootstrapError("E_DISCOVERY", "compiled outcome has no discovery agenda")
    truth_ids = {
        "discover-outcome-claims",
        "resolve-success-state",
        "resolve-domain-constraints",
    }
    truth: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    for item in agenda:
        if not isinstance(item, Mapping):
            raise BootstrapError("E_DISCOVERY", "discovery agenda entry is invalid")
        record = dict(item)
        if record.get("discovery_id") in truth_ids:
            truth.append(record)
        else:
            quality.append(record)
    if not truth or not quality:
        raise BootstrapError("E_DISCOVERY", "discovery agenda did not partition into both required research lanes")
    return truth, quality

def manager_budget() -> dict[str, Any]:
    return {"time_minutes": 10.0, "token_limit": 3000, "cost_usd": 3.0, "max_concurrency": 1, "max_retries": 1}

def worker_context(state: Mapping[str, Any], objective: str, manager_outcome: str, constraints: list[str], non_goals: list[str]) -> dict[str, Any]:
    strategy = state.get("strategy", {})
    return {
        "program_version": strategy.get("program_version"),
        "north_star": strategy.get("north_star") or objective,
        "user_value": objective,
        "program_outcome": objective,
        "manager_outcome": manager_outcome,
        "roadmap_position": "discovery",
        "dependencies": ["Authoritative or primary domain sources", "Current project repository"],
        "non_goals": non_goals or ["Production deployment during discovery"],
        "constraints": constraints or ["No consequential external effects during discovery"],
    }
def proposal_task(objective_id: str, objective: str, proposal_id: str, agenda: list[dict[str, Any]], section: str, output_path: str) -> str:
    agenda_json = json.dumps(agenda, sort_keys=True)
    return (
        f"Research the original objective exactly: {objective!r}. "
        f"You own the {section} research lane. Resolve the assigned discovery agenda with citations to authoritative or primary sources where available, actively search for counterevidence, and reconcile contradictions. "
        f"Assigned agenda: {agenda_json}. "
        f"Write one JSON proposal at {output_path} using schema company-os.outcome-model-proposal.v1, objective_id {objective_id!r}, proposal_id {proposal_id!r}, and the exact request_sha256 supplied in the manager packet. "
        "Every conclusion and every proposed outcome claim, artifact, evaluator, benchmark, or final acceptance policy must carry citations. Research only until the first real vertical slice is executable; defer nonblocking corpus expansion. Unknown means research until measurable enough to act. Do not ask the operator to provide domain vocabulary."
    )
def discovery_manifest(state: Mapping[str, Any], request: Mapping[str, Any], contract: Mapping[str, Any], base: str) -> dict[str, Any]:
    truth_agenda, quality_agenda = agenda_groups(contract)
    objective = text(request.get("objective"), "objective")
    objective_id = text(request.get("objective_id"), "objective_id")
    project_id = text(state.get("instance", {}).get("project_id"), "instance.project_id")
    program_version = state.get("strategy", {}).get("program_version")
    if not isinstance(program_version, int) or isinstance(program_version, bool) or program_version < 1:
        raise BootstrapError("E_STATE", "strategy.program_version is invalid")
    strategy = state.get("strategy", {})
    constraints = [item for item in strategy.get("constraints", []) if isinstance(item, str) and item.strip()]
    non_goals = [item for item in strategy.get("non_goals", []) if isinstance(item, str) and item.strip()]
    lanes = [
        (
            "domain-truth",
            "Discover observable success and domain constraints for the original objective.",
            truth_agenda,
            "success and domain truth",
        ),
        (
            "artifact-quality",
            "Discover artifact reality, observation evidence, quality benchmarks, executable evaluator requirements, and independent final acceptance.",
            quality_agenda,
            "artifact and quality system",
        ),
    ]
    managers = []
    for index, (lane_id, manager_outcome, agenda, section) in enumerate(lanes, 1):
        manager_id = f"outcome-discovery-manager-{index:02d}"
        scope = f"{base}/discovery/{lane_id}"
        proposal_path = f"{scope}/proposal.json"
        budget = manager_budget()
        worker = {
            "id": f"{manager_id}-worker-01",
            "model": "gpt-5.6-luna",
            "task": proposal_task(objective_id, objective, lane_id, agenda, section, proposal_path),
            "acceptance": [
                "Proposal is valid JSON using company-os.outcome-model-proposal.v1",
                "Every material conclusion has citations",
                "Counterevidence is searched and reconciled",
                f"Proposal is written to {proposal_path}",
            ],
            "write_scope": [scope],
            "risk": "low",
            "budget": dict(budget),
            "outcome_context": worker_context(state, objective, manager_outcome, constraints, non_goals),
            "stop_condition": "The assigned discovery agenda is closed with cited evidence, or an explicit unresolved blocker is returned.",
        }
        managers.append(
            {
                "id": manager_id,
                "model": "gpt-5.6-sol",
                "outcome": manager_outcome,
                "acceptance": [
                    "Worker proposal is independently checked against the assigned agenda",
                    "Unsupported certainty is rejected",
                    "Research output is integrated only as a proposal, not product acceptance",
                    "Stop discovery when enough evidence exists to execute the first reversible real-artifact slice",
                ],
                "phase_ids": PHASES,
                "budget": dict(budget),
                "write_scope": [scope],
                "workers": [worker],
            }
        )
    spike_scope = f"{base}/reality-spike"
    spike_worker = {
        "id": "outcome-reality-spike-manager-worker-01",
        "model": "gpt-5.6-luna",
        "task": (
            f"Start a reversible reality spike for the exact objective {objective!r} immediately while discovery runs. "
            "Inspect the repository, identify the task archetype, make the smallest real product mutation, run or render it, and observe actual behavior. "
            "Prefer supplied repositories, SDKs, frameworks, and existing project structure. Do not replace a supplied implementation without a failed integration attempt. "
            f"Write a receipt at {spike_scope}/reality-spike-receipt.json with schema company-os.reality-spike-receipt.v1, exact product artifact paths and sha256 values, commands executed, runtime result, observation evidence paths and sha256 values, and unresolved blockers. "
            "Research only a live implementation blocker. A plan or report without product mutation and runtime evidence fails this lane."
        ),
        "acceptance": [
            "At least one real product file is created or changed",
            "At least one build, runtime, browser, simulator, workflow, or equivalent execution command is run",
            "The exact artifact and observation evidence is content addressed",
            f"The receipt exists at {spike_scope}/reality-spike-receipt.json",
        ],
        "write_scope": ["app", "src", "public", "tests", "scripts", "prisma", "package.json", spike_scope],
        "risk": "low",
        "budget": {"time_minutes": 20.0, "token_limit": 6000, "cost_usd": 6.0, "max_concurrency": 1, "max_retries": 1},
        "work_class": "implementation",
        "outcome_context": worker_context(state, objective, "Create the first running artifact while focused discovery proceeds", constraints, non_goals),
        "stop_condition": "A real artifact runs or renders with exact evidence, or a concrete environment blocker is proven.",
    }
    first_manager = managers[0]
    first_manager["outcome"] = "Discover domain truth while creating the first reversible running artifact."
    first_manager["budget"] = {"time_minutes": 30.0, "token_limit": 9000, "cost_usd": 9.0, "max_concurrency": 2, "max_retries": 1}
    first_manager["write_scope"] = list(dict.fromkeys([*first_manager["write_scope"], *spike_worker["write_scope"]]))
    first_manager["acceptance"].extend(spike_worker["acceptance"])
    first_manager["workers"][0]["outcome_context"]["manager_outcome"] = first_manager["outcome"]
    spike_worker["outcome_context"]["manager_outcome"] = first_manager["outcome"]
    first_manager["workers"].append(spike_worker)
    manifest = {
        "program_id": project_id,
        "program_version": program_version,
        "outcome": objective,
        "acceptance": [
            "Success and domain truth proposal exists with citations",
            "Artifact and quality system proposal exists with citations",
            "Both proposals remain bound to the exact original outcome request",
        ],
        "program_contract": {
            "north_star": strategy.get("north_star") or objective,
            "user_value": objective,
            "rationale": "Resolve only the uncertainty blocking the first real vertical slice, then execute and learn from the artifact.",
            "architecture": "Two independent research managers produce structured outcome model proposals for deterministic synthesis.",
            "roadmap": PHASES,
            "dependencies": ["Authoritative or primary domain sources", "Current project repository"],
            "non_goals": non_goals or ["Production deployment during discovery"],
            "constraints": constraints or ["No consequential external effects during discovery"],
        },
        "max_managers": 2,
        "max_manager_concurrency": 2,
        "max_workers_per_manager": 2,
        "max_total_workers": 3,
        "max_depth": 2,
        "max_worker_retries": 1,
        "max_manager_rework_rounds": 2,
        "budget": {"time_minutes": 40.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 2, "max_retries": 1},
        "luna_token_share_target": 0.75,
        "external_effects_allowed": False,
        "managers": managers,
    }
    validation = fabric_module().validate(manifest)
    if not validation.get("valid"):
        raise BootstrapError("E_FABRIC", "; ".join(validation.get("errors", [])))
    return manifest

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
def bootstrap(project_root: Path, objective_id: str, objective: str) -> dict[str, Any]:
    project_root = project_root.resolve()
    if not project_root.is_dir() or project_root.is_symlink():
        raise BootstrapError("E_PATH", "project_root must be a real directory")
    try:
        revision, state = control_store_module().load(project_root)
    except Exception as exc:
        raise BootstrapError("E_STATE", f"Company OS transactional control store is required: {exc}") from exc
    request = seed_request(objective_id, objective)
    contract = outcome_module().compile_contract(request)
    loop = loop_module().start({"$schema": loop_module().REQUEST_SCHEMA, "objective_id": objective_id, "original_objective": objective})
    base = f".company-os/outcomes/{slug(objective_id)}"
    manifest = discovery_manifest(state, request, contract, base)
    paths = {
        "request": f"{base}/outcome-request.json",
        "contract": f"{base}/outcome-contract.json",
        "loop_state": f"{base}/outcome-loop.json",
        "discovery_fabric": f"{base}/discovery-fabric.json",
        "receipt": f"{base}/bootstrap-receipt.json",
    }
    write_json(project_root / paths["request"], request)
    write_json(project_root / paths["contract"], contract)
    write_json(project_root / paths["loop_state"], loop)
    write_json(project_root / paths["discovery_fabric"], manifest)
    receipt = {
        "$schema": "company-os.outcome-bootstrap-receipt.v1",
        "objective_id": objective_id,
        "original_objective": objective,
        "project_id": state["instance"]["project_id"],
        "program_version": state["strategy"]["program_version"],
        "control_revision": revision,
        "work_id": f"outcome-discovery-{slug(objective_id)}",
        "request_sha256": digest(request),
        "contract_sha256": contract["contract_sha256"],
        "loop_state_sha256": loop["state_sha256"],
        "paths": paths,
    }
    receipt["receipt_sha256"] = digest(receipt)
    write_json(project_root / paths["receipt"], receipt)
    return receipt

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--objective-id", required=True)
    parser.add_argument("--objective", required=True)
    args = parser.parse_args()
    try:
        result = bootstrap(args.project_root, args.objective_id, args.objective)
        print(json.dumps({"ok": True, **result}, sort_keys=True))
        return 0
    except BootstrapError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
