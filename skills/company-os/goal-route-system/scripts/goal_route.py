#!/usr/bin/env python3
"""Content-addressed goal and route contracts for Company OS missions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


STATE_SCHEMA = "company-os.goal-route-state.v1"
GOAL_SCHEMA = "company-os.goal-contract.v1"
ASSIGNMENT_SCHEMA = "company-os.goal-assignment.v1"
PROGRESS_ORDER = {
    "planned": 0,
    "artifact_materialized": 1,
    "runnable": 2,
    "connected": 3,
    "accepted": 4,
}
LEVEL_ORDER = {"company": 0, "manager": 1, "submanager": 2, "worker": 3}


class GoalRouteError(ValueError):
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


def seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result[field] = None
    result[field] = digest(result)
    return result


def verify_seal(value: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    observed = result.get(field)
    if not isinstance(observed, str) or len(observed) != 64:
        raise GoalRouteError("E_DIGEST", f"{label} {field} is invalid")
    result[field] = None
    if digest(result) != observed:
        raise GoalRouteError("E_DIGEST", f"{label} {field} does not verify")
    result[field] = observed
    return result


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:56] or "goal"


def _archetype(objective: str) -> str:
    text = objective.lower()
    if any(term in text for term in ("leggings", "apparel", "consumer brand", "ecommerce")):
        return "consumer_company"
    if any(term in text for term in ("marketing", "sales", "revenue", "campaign", "funnel")):
        return "marketing"
    if any(term in text for term in ("software", "saas", "application", "platform", "browser")):
        return "software"
    if any(term in text for term in ("operations", "process", "workflow", "supply chain")):
        return "operations"
    return "general"


MANAGER_BLUEPRINTS: dict[str, list[tuple[str, str, list[str]]]] = {
    "software": [
        ("product_definition", "Define the user outcome and complete journey", ["requirements", "journey"]),
        ("experience_system", "Create a cohesive product experience", ["design", "content"]),
        ("technical_foundation", "Build the secure technical foundation", ["architecture", "security"]),
        ("connected_product", "Materialize the first connected product slice", ["first-real-product", "runtime"]),
        ("capability_completion", "Complete the required product capabilities", ["implementation", "integration"]),
        ("quality_system", "Prove reliability, accessibility, and performance", ["quality", "reliability"]),
        ("release_acceptance", "Integrate and independently accept the release", ["release", "acceptance"]),
    ],
    "consumer_company": [
        ("market_position", "Define the customer, category, and economic thesis", ["market", "economics"]),
        ("brand_system", "Create the differentiated brand system", ["brand", "creative"]),
        ("product_system", "Specify the hero product and quality bar", ["product", "quality"]),
        ("supply_chain", "Establish the supply and fulfillment system", ["supply", "fulfillment"]),
        ("commerce_experience", "Build the complete commerce journey", ["commerce", "checkout"]),
        ("growth_distribution", "Build the launch and growth engine", ["growth", "campaign"]),
        ("company_operations", "Create repeatable company operations", ["operations", "scorecard"]),
        ("launch_acceptance", "Run integrated launch acceptance", ["launch", "acceptance"]),
    ],
    "marketing": [
        ("commercial_model", "Reverse engineer the revenue equation", ["revenue-model", "economics"]),
        ("customer_intelligence", "Resolve customer, competitor, and cultural signal", ["research", "customer"]),
        ("offer_strategy", "Define positioning, offer, and channel strategy", ["offer", "positioning"]),
        ("creative_system", "Create the campaign creative system", ["creative", "copy"]),
        ("activation_system", "Activate channels with instrumentation", ["activation", "analytics"]),
        ("optimization_system", "Operate experiments and scale-or-stop decisions", ["optimization", "decision"]),
    ],
    "operations": [
        ("constraint_map", "Map the process and current constraint", ["process", "bottleneck"]),
        ("operating_design", "Design the improved operating system", ["design", "controls"]),
        ("implementation", "Implement the bounded process change", ["implementation", "training"]),
        ("operational_acceptance", "Verify the measured operating result", ["measurement", "acceptance"]),
    ],
    "general": [
        ("context", "Resolve the objective and current state", ["context", "requirements"]),
        ("delivery", "Materialize the required outcome", ["delivery", "integration"]),
        ("acceptance", "Verify the complete outcome", ["verification", "acceptance"]),
    ],
}


ROUTE_SEGMENTS = [
    ("context", "Resolve context and constraints"),
    ("route_strategy", "Design the causal route and dependencies"),
    ("first_reality", "Create the smallest connected real outcome"),
    ("capability_expansion", "Build the remaining required capabilities"),
    ("integration_cohesion", "Integrate the complete system and preserve cohesion"),
    ("verification_acceptance", "Verify reality and obtain independent acceptance"),
]


def _budget(minutes: float, tokens: float, cost: float) -> dict[str, float]:
    return {"time_minutes": minutes, "token_limit": tokens, "cost_usd": cost}


def _task(goal_id: str, purpose: str) -> list[dict[str, Any]]:
    return [
        {
            "task_id": f"task:{goal_id}",
            "description": purpose,
            "subtasks": [
                {"subtask_id": f"subtask:{goal_id}:materialize", "description": "Materialize the target state"},
                {"subtask_id": f"subtask:{goal_id}:verify", "description": "Verify the target state with evidence"},
            ],
        }
    ]


def _goal(
    *,
    goal_id: str,
    root_goal_id: str,
    parent_goal_id: str | None,
    goal_type: str,
    level: str,
    purpose: str,
    budget: Mapping[str, float],
    authority_effects: Sequence[str],
    cohesion_sha256: str,
    artifact_classes: Sequence[str],
    contributes_to: Sequence[str],
    conditions: Sequence[str] | None = None,
    success_metrics: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    state_change_id = f"change:{goal_id}"
    return {
        "$schema": GOAL_SCHEMA,
        "goal_id": goal_id,
        "root_goal_id": root_goal_id,
        "parent_goal_id": parent_goal_id,
        "parent_goal_sha256": None,
        "goal_type": goal_type,
        "purpose": purpose,
        "owner": {
            "owner_id": f"{level}:{_slug(goal_type)}",
            "role": "master" if level == "company" else level,
            "goal_level": level,
        },
        "target_state": {"conditions": list(conditions or [purpose])},
        "required_state_changes": [
            {"state_change_id": state_change_id, "description": f"Complete and verify: {purpose}"}
        ],
        "contributes_to": list(contributes_to),
        "success_metrics": [dict(item) for item in (success_metrics or [])],
        "tasks": _task(goal_id, purpose),
        "budget": dict(budget),
        "authority": {"effects": list(authority_effects)},
        "artifact_classes": list(artifact_classes),
        "cohesion_sha256": cohesion_sha256,
        "progress": {"state": "planned", "evidence_count": 0},
        "status": "active",
        "evidence": [],
        "goal_sha256": None,
    }


def _reseal_goals(state: dict[str, Any]) -> dict[str, Any]:
    ordered = sorted(state["goals"], key=lambda item: LEVEL_ORDER[item["owner"]["goal_level"]])
    sealed: dict[str, dict[str, Any]] = {}
    for raw in ordered:
        goal = copy.deepcopy(raw)
        parent_id = goal.get("parent_goal_id")
        goal["parent_goal_sha256"] = sealed[parent_id]["goal_sha256"] if parent_id else None
        goal["goal_sha256"] = None
        sealed[goal["goal_id"]] = seal(goal, "goal_sha256")
    state["goals"] = [sealed[item["goal_id"]] for item in state["goals"]]
    state["root_goal_sha256"] = sealed[state["root_goal_id"]]["goal_sha256"]
    state["active_goal_ids"] = [
        item["goal_id"] for item in state["goals"] if item.get("status") not in {"accepted", "replaced", "cancelled"}
    ]
    state["status"] = "accepted" if not state["active_goal_ids"] else "active"
    state["state_sha256"] = None
    return seal(state, "state_sha256")


def _monthly_revenue_metric(objective: str) -> dict[str, Any] | None:
    if not any(term in objective.lower() for term in ("revenue", "sales", "mrr", "month")):
        return None
    matches = list(re.finditer(r"\$?([0-9][0-9,]*(?:\.[0-9]+)?)\s*([kmb])?", objective, re.I))
    if not matches:
        return None
    match = matches[-1]
    target = float(match.group(1).replace(",", ""))
    target *= {None: 1.0, "k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}[
        match.group(2).lower() if match.group(2) else None
    ]
    return {"metric_id": "monthly_revenue", "target": target, "unit": "usd_per_month"}


def compile_goal_route(
    objective_id: str,
    objective: str,
    *,
    mission_class: str = "company_mission",
    kickoff_profile: Mapping[str, Any] | None = None,
    autonomy_mode: str = "guided",
) -> dict[str, Any]:
    if not isinstance(objective_id, str) or not objective_id.strip():
        raise GoalRouteError("E_SCHEMA", "objective_id must be nonempty text")
    if not isinstance(objective, str) or not objective.strip():
        raise GoalRouteError("E_SCHEMA", "objective must be nonempty text")
    autonomy_mode = autonomy_mode or "guided"

    archetype = _archetype(objective)
    root_goal_id = f"goal:{_slug(objective_id)}"
    cohesion = seal(
        {
            "$schema": "company-os.cohesion-contract.v1",
            "objective_id": objective_id,
            "customer_promise": objective.strip(),
            "principles": [
                "preserve the root objective",
                "prefer direct environment evidence",
                "do not widen authority",
                "integrate before declaring completion",
            ],
            "cohesion_sha256": None,
        },
        "cohesion_sha256",
    )
    root_budget = _budget(480.0, 240_000.0, 180.0)
    root_metric = _monthly_revenue_metric(objective)
    root = _goal(
        goal_id=root_goal_id,
        root_goal_id=root_goal_id,
        parent_goal_id=None,
        goal_type="root_outcome",
        level="company",
        purpose=objective.strip(),
        budget=root_budget,
        authority_effects=["local_source_changes", "local_runtime", "network_research"],
        cohesion_sha256=cohesion["cohesion_sha256"],
        artifact_classes=["integrated-outcome"],
        contributes_to=[],
        conditions=[objective.strip()],
        success_metrics=[root_metric] if root_metric else [],
    )
    root_change = root["required_state_changes"][0]["state_change_id"]
    blueprints = MANAGER_BLUEPRINTS[archetype]
    manager_budget = _budget(
        root_budget["time_minutes"] / len(blueprints),
        root_budget["token_limit"] / len(blueprints),
        root_budget["cost_usd"] / len(blueprints),
    )
    goals = [root]
    for index, (goal_type, purpose, artifacts) in enumerate(blueprints):
        manager_id = f"goal:{_slug(objective_id)}:manager:{index + 1}"
        manager_conditions = ["revenue equation"] if goal_type == "commercial_model" else [purpose]
        manager = _goal(
            goal_id=manager_id,
            root_goal_id=root_goal_id,
            parent_goal_id=root_goal_id,
            goal_type=goal_type,
            level="manager",
            purpose=purpose,
            budget=manager_budget,
            authority_effects=root["authority"]["effects"],
            cohesion_sha256=cohesion["cohesion_sha256"],
            artifact_classes=artifacts,
            contributes_to=[root_change],
            conditions=manager_conditions,
        )
        manager_change = manager["required_state_changes"][0]["state_change_id"]
        submanager_id = f"{manager_id}:delivery"
        submanager = _goal(
            goal_id=submanager_id,
            root_goal_id=root_goal_id,
            parent_goal_id=manager_id,
            goal_type=f"{goal_type}_delivery",
            level="submanager",
            purpose=f"Coordinate delivery for {purpose.lower()}",
            budget=manager_budget,
            authority_effects=root["authority"]["effects"],
            cohesion_sha256=cohesion["cohesion_sha256"],
            artifact_classes=artifacts,
            contributes_to=[manager_change],
        )
        submanager_change = submanager["required_state_changes"][0]["state_change_id"]
        worker_id = f"{submanager_id}:worker"
        worker = _goal(
            goal_id=worker_id,
            root_goal_id=root_goal_id,
            parent_goal_id=submanager_id,
            goal_type=f"{goal_type}_implementation",
            level="worker",
            purpose=f"Materialize and verify {purpose.lower()}",
            budget=manager_budget,
            authority_effects=["local_source_changes", "local_runtime"],
            cohesion_sha256=cohesion["cohesion_sha256"],
            artifact_classes=artifacts,
            contributes_to=[submanager_change],
        )
        goals.extend([manager, submanager, worker])

    route_segments = [
        {
            "route_segment_id": segment_id,
            "position": index + 1,
            "purpose": purpose,
            "entry_conditions": ["prior segment accepted"] if index else ["objective admitted"],
            "exit_conditions": [f"{segment_id} evidence accepted"],
        }
        for index, (segment_id, purpose) in enumerate(ROUTE_SEGMENTS)
    ]
    sprints = [
        {
            "sprint_id": f"sprint:{index + 1}",
            "route_segment_id": segment["route_segment_id"],
            "goal": segment["purpose"],
            "exit_conditions": segment["exit_conditions"],
        }
        for index, segment in enumerate(route_segments)
    ]
    profile = {
        "autonomy_mode": autonomy_mode,
        "assumptions": [
            "Missing non-authority context may be researched and must remain explicitly marked."
        ] if autonomy_mode != "guided" else [],
        "unknowns": [],
    }
    profile.update(copy.deepcopy(dict(kickoff_profile or {})))
    state = {
        "$schema": STATE_SCHEMA,
        "schema_version": 1,
        "objective_id": objective_id,
        "objective": objective.strip(),
        "mission_class": mission_class,
        "archetype": archetype,
        "autonomy_mode": autonomy_mode,
        "route_version": 1,
        "root_goal_id": root_goal_id,
        "root_goal_sha256": None,
        "kickoff_profile": profile,
        "cohesion_contract": cohesion,
        "route_segments": route_segments,
        "sprints": sprints,
        "goals": goals,
        "active_goal_ids": [],
        "takeover_packets": [],
        "status": "active",
        "state_sha256": None,
    }
    return verify_state(_reseal_goals(state))


def goal_by_id(state: Mapping[str, Any], goal_id: str) -> dict[str, Any]:
    for goal in state.get("goals", []):
        if goal.get("goal_id") == goal_id:
            return goal
    raise GoalRouteError("E_GOAL", f"unknown goal {goal_id}")


def verify_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    state = verify_seal(raw, "state_sha256", "goal route state")
    if state.get("$schema") != STATE_SCHEMA or state.get("schema_version") != 1:
        raise GoalRouteError("E_SCHEMA", "goal route state schema is invalid")
    if not isinstance(state.get("route_version"), int) or state["route_version"] < 1:
        raise GoalRouteError("E_SCHEMA", "route_version must be a positive integer")
    cohesion = verify_seal(state.get("cohesion_contract", {}), "cohesion_sha256", "cohesion contract")
    goals = [verify_seal(item, "goal_sha256", "goal") for item in state.get("goals", [])]
    if not goals:
        raise GoalRouteError("E_GOAL", "goal route requires goals")
    by_id = {goal["goal_id"]: goal for goal in goals}
    if len(by_id) != len(goals) or state.get("root_goal_id") not in by_id:
        raise GoalRouteError("E_GOAL", "goal identifiers are invalid")
    if state.get("root_goal_sha256") != by_id[state["root_goal_id"]]["goal_sha256"]:
        raise GoalRouteError("E_BINDING", "root goal digest changed")
    for goal in goals:
        if goal.get("cohesion_sha256") != cohesion["cohesion_sha256"]:
            raise GoalRouteError("E_COHESION", f"goal {goal['goal_id']} lost cohesion binding")
        parent_id = goal.get("parent_goal_id")
        if parent_id is None:
            if goal["goal_id"] != state["root_goal_id"]:
                raise GoalRouteError("E_GOAL", "only the root goal may omit a parent")
            continue
        parent = by_id.get(parent_id)
        if parent is None or goal.get("parent_goal_sha256") != parent.get("goal_sha256"):
            raise GoalRouteError("E_BINDING", f"goal {goal['goal_id']} has a stale parent binding")
        child_effects = set(goal.get("authority", {}).get("effects", []))
        parent_effects = set(parent.get("authority", {}).get("effects", []))
        if not child_effects.issubset(parent_effects):
            raise GoalRouteError("E_AUTHORITY", f"goal {goal['goal_id']} widens authority")
    for parent in goals:
        children = [goal for goal in goals if goal.get("parent_goal_id") == parent["goal_id"]]
        if not children:
            continue
        required = {item["state_change_id"] for item in parent.get("required_state_changes", [])}
        covered = {item for child in children for item in child.get("contributes_to", [])}
        if not required.issubset(covered):
            raise GoalRouteError("E_COVERAGE", f"children do not cover goal {parent['goal_id']}")
        for field in ("time_minutes", "token_limit", "cost_usd"):
            if sum(float(child["budget"][field]) for child in children) > float(parent["budget"][field]) + 1e-6:
                raise GoalRouteError("E_BUDGET", f"children exceed {field} for {parent['goal_id']}")
    expected_active = [
        item["goal_id"] for item in goals if item.get("status") not in {"accepted", "replaced", "cancelled"}
    ]
    if state.get("active_goal_ids") != expected_active:
        raise GoalRouteError("E_STATE", "active goal index is stale")
    if len(state.get("route_segments", [])) != 6 or len(state.get("sprints", [])) != 6:
        raise GoalRouteError("E_ROUTE", "goal route requires six segments and six sprints")
    state["goals"] = goals
    state["cohesion_contract"] = cohesion
    return state


def _descendants(state: Mapping[str, Any], root_id: str, level: str) -> list[dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for goal in state["goals"]:
        if goal.get("parent_goal_id"):
            by_parent.setdefault(goal["parent_goal_id"], []).append(goal)
    pending = list(by_parent.get(root_id, []))
    matches: list[dict[str, Any]] = []
    while pending:
        goal = pending.pop(0)
        if goal["owner"]["goal_level"] == level:
            matches.append(goal)
        pending.extend(by_parent.get(goal["goal_id"], []))
    return matches


def assignment_for_lane(
    route_raw: Mapping[str, Any],
    *,
    artifact_classes: Sequence[str],
    phase: str,
    lane_id: str,
    manager_id: str,
    worker_id: str,
) -> dict[str, Any]:
    route = verify_state(route_raw)
    requested = set(artifact_classes)
    managers = [goal for goal in route["goals"] if goal["owner"]["goal_level"] == "manager"]
    manager = max(
        managers,
        key=lambda goal: (len(requested.intersection(goal.get("artifact_classes", []))), -managers.index(goal)),
    )
    workers = _descendants(route, manager["goal_id"], "worker")
    worker = workers[0]
    segment = route["route_segments"][2 if phase in {"build_candidate", "rework"} else 5 if phase == "evaluate" else 0]
    sprint = next(item for item in route["sprints"] if item["route_segment_id"] == segment["route_segment_id"])
    assignment = {
        "$schema": ASSIGNMENT_SCHEMA,
        "route_state_sha256": route["state_sha256"],
        "route_version": route["route_version"],
        "lane_id": lane_id,
        "manager_id": manager_id,
        "worker_id": worker_id,
        "manager_goal": manager,
        "worker_goal": worker,
        "manager_template": {"template_id": f"template:{manager['goal_type']}", "role": "manager"},
        "worker_template": {"template_id": f"template:{worker['goal_type']}", "role": "worker"},
        "cohesion_contract": route["cohesion_contract"],
        "route_node": segment,
        "sprint": sprint,
        "assignment_sha256": None,
    }
    return seal(assignment, "assignment_sha256")


def verify_assignment(raw: Mapping[str, Any], route_raw: Mapping[str, Any]) -> dict[str, Any]:
    assignment = verify_seal(raw, "assignment_sha256", "goal assignment")
    route = verify_state(route_raw)
    if assignment.get("$schema") != ASSIGNMENT_SCHEMA:
        raise GoalRouteError("E_SCHEMA", "goal assignment schema is invalid")
    if assignment.get("route_state_sha256") != route["state_sha256"]:
        raise GoalRouteError("E_BINDING", "goal assignment binds a stale route")
    goals = {goal["goal_id"]: goal for goal in route["goals"]}
    for label in ("manager_goal", "worker_goal"):
        goal = assignment.get(label, {})
        if goal.get("goal_id") not in goals or goal.get("goal_sha256") != goals[goal["goal_id"]]["goal_sha256"]:
            raise GoalRouteError("E_BINDING", f"{label} changed")
    if assignment.get("cohesion_contract", {}).get("cohesion_sha256") != route["cohesion_contract"]["cohesion_sha256"]:
        raise GoalRouteError("E_COHESION", "assignment cohesion changed")
    return assignment


def delegation_plan(route_raw: Mapping[str, Any], manager_goal_id: str) -> dict[str, Any]:
    route = verify_state(route_raw)
    manager = goal_by_id(route, manager_goal_id)
    submanagers = _descendants(route, manager_goal_id, "submanager")
    workers = _descendants(route, manager_goal_id, "worker")
    return {
        "$schema": "company-os.goal-delegation-plan.v1",
        "route_state_sha256": route["state_sha256"],
        "manager_goal_id": manager_goal_id,
        "manager_goal_sha256": manager["goal_sha256"],
        "submanager_goals": submanagers,
        "worker_goals": workers,
        "coverage": sorted({item for goal in submanagers for item in goal.get("contributes_to", [])}),
        "delegation_sha256": None,
    }


def sealed_delegation_plan(route_raw: Mapping[str, Any], manager_goal_id: str) -> dict[str, Any]:
    return seal(delegation_plan(route_raw, manager_goal_id), "delegation_sha256")


def record_evidence(
    route_raw: Mapping[str, Any],
    *,
    goal_id: str,
    evidence_type: str,
    path: str,
    sha256: str,
    progress_state: str,
) -> dict[str, Any]:
    route = verify_state(route_raw)
    if progress_state not in PROGRESS_ORDER:
        raise GoalRouteError("E_PROGRESS", f"unknown progress state {progress_state}")
    target = goal_by_id(route, goal_id)
    if PROGRESS_ORDER[progress_state] < PROGRESS_ORDER[target["progress"]["state"]]:
        raise GoalRouteError("E_PROGRESS", "goal progress cannot move backward")
    target["evidence"].append(
        {"evidence_type": evidence_type, "path": path, "sha256": sha256, "progress_state": progress_state}
    )
    target["progress"] = {"state": progress_state, "evidence_count": len(target["evidence"])}
    if progress_state == "accepted":
        target["status"] = "accepted"
    changed = True
    while changed:
        changed = False
        for parent in route["goals"]:
            children = [goal for goal in route["goals"] if goal.get("parent_goal_id") == parent["goal_id"]]
            if children and all(child.get("status") == "accepted" for child in children) and parent.get("status") != "accepted":
                parent["status"] = "accepted"
                parent["progress"] = {"state": "accepted", "evidence_count": len(parent.get("evidence", []))}
                changed = True
    return verify_state(_reseal_goals(route))


def record_candidate(route_raw: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    route = verify_state(route_raw)
    for artifact in candidate.get("artifacts", []):
        goal_id = artifact.get("goal_id") if isinstance(artifact, Mapping) else None
        if goal_id:
            route = record_evidence(
                route,
                goal_id=goal_id,
                evidence_type="artifact_manifest",
                path=str(artifact.get("path", "candidate")),
                sha256=str(artifact.get("sha256", "")),
                progress_state="artifact_materialized",
            )
    return route


def accept_route(route_raw: Mapping[str, Any], *, receipt_path: str, receipt_sha256: str) -> dict[str, Any]:
    route = verify_state(route_raw)
    for worker in [goal for goal in route["goals"] if goal["owner"]["goal_level"] == "worker" and goal["status"] != "accepted"]:
        route = record_evidence(
            route,
            goal_id=worker["goal_id"],
            evidence_type="independent_acceptance",
            path=receipt_path,
            sha256=receipt_sha256,
            progress_state="accepted",
        )
    if route["status"] != "accepted":
        raise GoalRouteError("E_ACCEPTANCE", "independent receipt did not close the goal graph")
    return route


def reroute(
    route_raw: Mapping[str, Any],
    *,
    blocked_goal_id: str,
    replacement_owner_id: str,
    reason: str,
    failed_strategy: str,
    new_strategy: str,
) -> dict[str, Any]:
    route = verify_state(route_raw)
    goal = goal_by_id(route, blocked_goal_id)
    packet = {
        "$schema": "company-os.goal-takeover-packet.v1",
        "goal_id": goal["goal_id"],
        "goal_sha256": goal["goal_sha256"],
        "root_goal_id": route["root_goal_id"],
        "prior_owner_id": goal["owner"]["owner_id"],
        "replacement_owner_id": replacement_owner_id,
        "reason": reason,
        "failed_strategy": failed_strategy,
        "new_strategy": new_strategy,
    }
    goal["owner"]["owner_id"] = replacement_owner_id
    goal["status"] = "active"
    route["route_version"] += 1
    route["takeover_packets"].append(packet)
    return verify_state(_reseal_goals(route))


def summary(route_raw: Mapping[str, Any]) -> dict[str, Any]:
    route = verify_state(route_raw)
    return {
        "objective_id": route["objective_id"],
        "route_version": route["route_version"],
        "status": route["status"],
        "root_goal_id": route["root_goal_id"],
        "goal_count": len(route["goals"]),
        "active_goal_count": len(route["active_goal_ids"]),
        "state_sha256": route["state_sha256"],
    }


def simulate() -> dict[str, Any]:
    scenarios = [
        ("software", "Build a complete software platform with a real browser journey."),
        ("consumer_company", "Build a differentiated yoga leggings company with commerce and operations."),
        ("marketing", "Build a marketing system that reaches $100,000 a month in sales."),
        ("operations", "Improve an operations workflow and verify the bottleneck moved."),
    ]
    results = []
    for scenario_id, objective in scenarios:
        route = compile_goal_route(
            scenario_id,
            objective,
            mission_class="simulation",
            autonomy_mode="autonomous_research",
        )
        root = goal_by_id(route, route["root_goal_id"])
        revenue = next((item["target"] for item in root["success_metrics"] if item["metric_id"] == "monthly_revenue"), None)
        results.append(
            {
                "scenario_id": scenario_id,
                "manager_goals": sum(goal["owner"]["goal_level"] == "manager" for goal in route["goals"]),
                "worker_goals": sum(goal["owner"]["goal_level"] == "worker" for goal in route["goals"]),
                "revenue_target": revenue,
                "state_sha256": route["state_sha256"],
            }
        )
    return {"passed": True, "scenario_count": len(results), "results": results}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("simulate")
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("objective_id")
    compile_parser.add_argument("objective")
    compile_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "simulate":
        result = simulate()
    else:
        result = compile_goal_route(args.objective_id, args.objective)
    if getattr(args, "output", None):
        _write_json(args.output, result)
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
