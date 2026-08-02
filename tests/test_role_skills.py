from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_role_skills", ROOT / "scripts/validate_role_skills.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def dispatched_payload(role_name: str) -> dict:
    spec = MODULE.ROLE_SPECS[role_name]
    path = MODULE.SKILLS[role_name] / "assets" / spec["asset"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ids"] = {
        "project_id": "project-1",
        "program_id": "program-1",
        "cycle_id": "cycle-1",
        "task_id": "task-1",
        "parent_task_id": "parent-1",
    }
    payload["outcome"] = "Deliver one accepted bounded artifact."
    payload["outcome_digest"] = sha(payload["outcome"])
    for reference in payload["artifact_references"]:
        reference["path"] = f"artifacts/{reference['kind']}.v1.md"
        reference["sha256"] = sha(reference["path"])
    payload["authorization"].update({
        "decision_id": "decision-1",
        "decider_id": "master-1",
        "evidence_digest": sha("phase-evidence-1"),
        "authentication_digest": sha("authenticated-grant-1"),
    })
    payload["task_local_context"]["artifact_paths"] = ["artifacts/input.json"]
    payload["scope"]["owned_paths"] = ["program/artifact"]
    payload["permissions"] = {
        "allowed_actions": ["read", "write-owned-artifact"],
        "allowed_tools": ["repository", "local-tests"],
        "prohibited_actions": ["deploy", "external-message"],
    }
    payload["deliverables"] = ["artifacts/result.json"]
    payload["acceptance"]["oracle"] = "result.status == accepted"
    payload["acceptance"]["checks"] = ["validate-result"]
    payload["acceptance"]["independent_review"]["evidence_requirements"] = ["review-receipt"]
    payload["budget"].update({
        "max_tokens": 10000,
        "max_cost_usd": 5.0,
        "max_time_minutes": 30,
        "max_tasks": 1 if role_name == "execute-bounded-task" else 3,
        "max_concurrency": 1 if role_name == "execute-bounded-task" else 3,
        "max_retries": 1,
    })
    payload["stop_escalation"] = {
        "stop_conditions": ["oracle-passed", "budget-exhausted"],
        "escalate_on": ["authority-change", "failed-barrier"],
    }
    payload["reporting_destination"] = "task:manager-1"
    payload["authorization"]["definition_digest"] = MODULE.contract_definition_digest(payload)
    return payload


class RoleSkillTests(unittest.TestCase):
    def test_role_skills_are_compact_versioned_and_consistent(self) -> None:
        self.assertEqual([], MODULE.validate())

    def test_dispatched_v2_contracts_validate_strictly(self) -> None:
        for role_name in MODULE.SKILLS:
            with self.subTest(role=role_name):
                self.assertEqual(
                    [],
                    MODULE.validate_contract_payload(
                        dispatched_payload(role_name), role_name, template=False
                    ),
                )

    def test_worker_inherits_design_authorization_without_waiting_on_master(self) -> None:
        payload = dispatched_payload("execute-bounded-task")
        self.assertEqual("design", payload["authorization"]["phase"])
        self.assertTrue(payload["decision_barriers"]["inherited_design_authorization_required"])
        self.assertTrue(payload["decision_barriers"]["manager_verification_required"])
        self.assertFalse(payload["decision_barriers"]["worker_waits_for_master"])

    def test_missing_attributable_authorization_fails_closed(self) -> None:
        payload = dispatched_payload("execute-bounded-task")
        payload["authorization"]["decider_id"] = ""
        errors = MODULE.validate_contract_payload(
            payload, "execute-bounded-task", template=False
        )
        self.assertIn("authorization must be attributable and digest-bound", errors)

    def test_authorization_definition_digest_detects_post_decision_mutation(self) -> None:
        payload = dispatched_payload("manage-company-program")
        payload["deliverables"].append("artifacts/unapproved.json")
        errors = MODULE.validate_contract_payload(
            payload, "manage-company-program", template=False
        )
        self.assertIn(
            "authorization definition digest does not bind this exact contract", errors
        )

    def test_dispatched_scope_rejects_aliases_and_ancestor_overlap(self) -> None:
        for scopes in (
            ["Program/Artifact"],
            ["program/artifáct"],
            ["program//artifact"],
            ["program", "program/artifact"],
        ):
            with self.subTest(scopes=scopes):
                payload = dispatched_payload("execute-bounded-task")
                payload["scope"]["owned_paths"] = scopes
                errors = MODULE.validate_contract_payload(
                    payload, "execute-bounded-task", template=False
                )
                self.assertTrue(any("scope paths" in item for item in errors))

    def test_malformed_payload_types_never_raise(self) -> None:
        mutations = (
            ("task_local_context", None),
            ("scope", False),
            ("permissions", "all"),
            ("acceptance", {"oracle": [], "checks": None, "independent_review": None}),
            ("decision_barriers", {"authenticated_master_decision_required": [], "routine_auto_continue_phase": "execution", "routine_conditions": None}),
            ("budget", {key: None for key in MODULE.BUDGET_KEYS}),
            ("authorization", {"phase": [], "decision": None}),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                payload = dispatched_payload("manage-company-program")
                payload[key] = copy.deepcopy(value)
                errors = MODULE.validate_contract_payload(
                    payload, "manage-company-program", template=False
                )
                self.assertTrue(errors)

    def test_agent_metadata_boolean_string_field_fails_without_crash(self) -> None:
        text = (MODULE.SKILLS["manage-company-program"] / "agents/openai.yaml").read_text(encoding="utf-8")
        malformed = text.replace(
            '  short_description: "Manage governed Company OS delivery"',
            "  short_description: false",
        )
        errors = MODULE.validate_agent_metadata(malformed, "manage-company-program")
        self.assertIn("interface metadata values must be strings", errors)

    def test_agent_policy_must_be_explicit_false(self) -> None:
        text = (MODULE.SKILLS["execute-bounded-task"] / "agents/openai.yaml").read_text(encoding="utf-8")
        for malformed in (
            text.replace("allow_implicit_invocation: false", "allow_implicit_invocation: true"),
            text.replace("policy:\n  allow_implicit_invocation: false\n", ""),
        ):
            with self.subTest(metadata=malformed):
                errors = MODULE.validate_agent_metadata(
                    malformed, "execute-bounded-task"
                )
                self.assertIn(
                    "implicit invocation must be structurally disabled", errors
                )


if __name__ == "__main__":
    unittest.main()
