#!/usr/bin/env python3
"""Deterministic regression lab for Company OS execution economics."""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class RegressionError(ValueError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RegressionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def modules():
    root = Path(__file__).resolve().parent
    mission = load_module(root / "mission_control.py", "company_os_regression_mission")
    governor = load_module(
        root.parents[1] / "govern-outcome-execution/scripts/executive_governor.py",
        "company_os_regression_governor",
    )
    return mission, governor


def website_case(mission, governor) -> dict[str, Any]:
    started = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    state = mission.initialize_state(
        "website",
        "Build a polished marketing website with a working contact flow.",
        started_at=mission.format_time(started),
        mission_class="quick_build",
        duration_minutes=90,
    )
    state = mission.refresh_governor(state, now=started + timedelta(minutes=30))
    request = {
        "$schema": mission.ADMISSION_SCHEMA,
        "request_id": "website-more-docs",
        "task_id": "documentation-worker",
        "manager_id": "website-manager",
        "work_class": "documentation",
        "bootstrap": False,
        "justification": {
            "consumer_task_id": "ui-worker",
            "blocker_id": "rendered-user-path",
            "decision_dependency": "document additional visual theory",
            "deadline_minutes": 10,
        },
    }
    receipt = mission.admit_work(state, request)
    passed = (
        state["governor_decision"]["mode"] == "compression"
        and state["governor_decision"]["first_reality_incident"] is True
        and receipt["admitted"] is False
    )
    return {
        "case_id": "website",
        "passed": passed,
        "reality_level": state["governor_decision"]["reality_level"],
        "mode": state["governor_decision"]["mode"],
        "documentation_admitted": receipt["admitted"],
    }


def n8n_case(mission, governor) -> dict[str, Any]:
    decision = governor.evaluate(
        {
            "$schema": governor.INPUT_SCHEMA,
            "objective_id": "n8n",
            "objective": "Generate, import, execute, repair, and package professional n8n workflows.",
            "budget_fraction_consumed": 0.44,
            "reality": {
                "internal_primitives": True,
                "runnable_capability": True,
                "connected_vertical_slice": False,
                "user_usable": False,
                "independent_acceptance": False,
            },
            "required_capabilities": [
                {
                    "capability_id": "objective_to_workflow_compiler",
                    "state": "missing",
                    "critical": True,
                    "priority": 100,
                },
                {
                    "capability_id": "protected_benchmark_suite",
                    "state": "missing",
                    "critical": False,
                    "priority": 20,
                },
            ],
            "allocation": {
                "research": 0.25,
                "governance": 0.25,
                "architecture": 0.20,
                "implementation": 0.20,
                "runtime": 0.10,
            },
        }
    )
    passed = (
        decision["mode"] == "compression"
        and decision["dominant_bottleneck"]["capability_id"] == "objective_to_workflow_compiler"
        and decision["allocation_incident"] is True
    )
    return {
        "case_id": "n8n",
        "passed": passed,
        "reality_level": decision["reality_level"],
        "mode": decision["mode"],
        "bottleneck": decision["dominant_bottleneck"]["capability_id"],
    }


def firecrawl_case(mission, governor) -> dict[str, Any]:
    state = mission.initialize_state(
        "firecrawl",
        "Build a Firecrawl expert using https://github.com/firecrawl/firecrawl.git and its supplied CLI and MCP repositories.",
        mission_class="bounded_feature",
        duration_minutes=180,
    )
    decision = state["governor_decision"]
    replacement = mission.admit_work(
        state,
        {
            "$schema": mission.ADMISSION_SCHEMA,
            "request_id": "replace-firecrawl",
            "task_id": "custom-crawler-worker",
            "manager_id": "acquisition-manager",
            "work_class": "implementation",
            "bootstrap": False,
            "replaces_existing_implementation": True,
        },
    )
    bottleneck = decision["dominant_bottleneck"] or {}
    passed = (
        decision["existing_capability_preference"] is True
        and bottleneck.get("existing_implementation") is not None
        and replacement["admitted"] is False
    )
    return {
        "case_id": "firecrawl",
        "passed": passed,
        "bottleneck": bottleneck.get("capability_id"),
        "existing_implementation": bottleneck.get("existing_implementation"),
        "replacement_admitted": replacement["admitted"],
    }


def support_case(mission, governor) -> dict[str, Any]:
    contract = {
        "$schema": "company-os.artifact-observation-contract.v1",
        "artifact_classes": [
            {
                "artifact_class_id": "support_runtime",
                "label": "Grounded support runtime",
                "required": True,
                "modalities": ["service", "executable"],
                "observation_methods": ["runtime"],
            },
            {
                "artifact_class_id": "support_interface",
                "label": "Widget and inbox interface",
                "required": True,
                "modalities": ["interactive", "ui"],
                "observation_methods": ["browser"],
            },
            {
                "artifact_class_id": "billing",
                "label": "Billing",
                "required": True,
                "modalities": ["service"],
                "observation_methods": ["api"],
            },
            {
                "artifact_class_id": "analytics",
                "label": "Analytics",
                "required": True,
                "modalities": ["service"],
                "observation_methods": ["api"],
            },
        ],
    }
    state = mission.initialize_state(
        "support",
        "Build a complete AI support SaaS with company switching, knowledge, widget, inbox, human reply, billing, security, and analytics.",
        mission_class="company_mission",
        duration_minutes=420,
        artifact_contract=contract,
    )
    first = state["first_reality"]
    passed = (
        1 <= len(first["required_artifact_class_ids"]) <= 2
        and bool(first["deferred_capability_ids"])
        and set(first["required_artifact_class_ids"]).isdisjoint(first["deferred_capability_ids"])
    )
    return {
        "case_id": "support",
        "passed": passed,
        "first_reality_artifacts": first["required_artifact_class_ids"],
        "deferred_artifacts": first["deferred_capability_ids"],
    }


def run_lab() -> dict[str, Any]:
    mission, governor = modules()
    results = [
        website_case(mission, governor),
        n8n_case(mission, governor),
        firecrawl_case(mission, governor),
        support_case(mission, governor),
    ]
    return {
        "schema": "company-os.execution-regression-lab.v1",
        "passed": all(item["passed"] for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_lab()
        print(json.dumps(result, sort_keys=True, indent=2 if args.json else None))
        return 0 if result["passed"] else 1
    except (RegressionError, ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
