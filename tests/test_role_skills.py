from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_role_skills", ROOT / "scripts/validate_role_skills.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def write_bytes(root: Path, relative: str, content: bytes) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def write_json(root: Path, relative: str, value: dict) -> bytes:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_bytes(root, relative, encoded)
    return encoded


def authorization_record(payload: dict, parent_definition_digest: str | None) -> dict:
    ids = payload["ids"]
    expectation = payload["authorization_expectation"]
    definition_digest = MODULE.contract_definition_digest(payload)
    assert definition_digest is not None
    evidence_path = (
        f"artifacts/{ids['project_id']}/phase-evidence/{ids['task_id']}."
        f"{expectation['phase']}.v1.json"
    )
    evidence_content = (
        json.dumps(
            {
                "decision_id": expectation["decision_id"],
                "phase": expectation["phase"],
                "task_id": ids["task_id"],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    record = {
        "schema": MODULE.AUTHORIZATION_SCHEMA,
        "record_version": 1,
        "decision_id": expectation["decision_id"],
        "decision_version": expectation["decision_version"],
        "status": "accepted",
        "decision": "continue",
        "bindings": {
            "project_id": ids["project_id"],
            "program_id": ids["program_id"],
            "program_version": payload["program_version"],
            "cycle_id": ids["cycle_id"],
            "task_id": ids["task_id"],
            "parent_task_id": ids["parent_task_id"],
            "definition_version": payload["definition_version"],
            "outcome_digest": payload["outcome_digest"],
            "requested_model": payload["requested_model"],
            "definition_digest": definition_digest,
            "parent_definition_digest": parent_definition_digest,
            "parent_manager_native_task_id": payload.get("parent_manager_task_id"),
            "phase": expectation["phase"],
            "decider_id": expectation["decider_id"],
        },
        "evidence_reference": {
            "project_id": ids["project_id"],
            "path": evidence_path,
            "version": 1,
            "sha256": sha_bytes(evidence_content),
        },
        "evidence_kind": MODULE.AUTHORIZATION_EVIDENCE_KIND,
        "authentication": {
            "scheme": MODULE.AUTHORIZATION_SIGNATURE_SCHEME,
            "key_id": "company-os-repository-test-v1",
            "signature": "",
        },
    }
    signature = MODULE.authorization_fixture_signature(record)
    assert signature is not None
    record["authentication"]["signature"] = signature
    return record


def persist_authorization(
    payload: dict, root: Path, parent_definition_digest: str | None
) -> None:
    record = authorization_record(payload, parent_definition_digest)
    evidence = record["evidence_reference"]
    evidence_content = (
        json.dumps(
            {
                "decision_id": record["decision_id"],
                "phase": record["bindings"]["phase"],
                "task_id": record["bindings"]["task_id"],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    write_bytes(root, evidence["path"], evidence_content)
    path = payload["authorization"]["record_path"]
    write_json(root, path, record)
    digest = MODULE.canonical_digest(record)
    assert digest is not None
    payload["authorization"]["record_sha256"] = digest


def populate_payload(
    role_name: str,
    root: Path,
    *,
    task_id: str,
    parent_task_id: str,
    scope: list[str],
    decider_id: str,
) -> dict:
    spec = MODULE.ROLE_SPECS[role_name]
    path = MODULE.SKILLS[role_name] / "assets" / spec["asset"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ids"] = {
        "project_id": "project-1",
        "program_id": "program-1",
        "cycle_id": "cycle-1",
        "task_id": task_id,
        "parent_task_id": parent_task_id,
    }
    payload["outcome"] = f"Deliver accepted bounded artifact for {task_id}."
    payload["outcome_digest"] = sha(payload["outcome"])
    payload["authorization_expectation"].update({
        "decision_id": f"decision-{task_id}",
        "decider_id": decider_id,
    })
    authorization_path = (
        f"artifacts/project-1/authorizations/{task_id}."
        f"{payload['authorization_expectation']['phase']}.v1.json"
    )
    payload["authorization"]["record_path"] = authorization_path
    for reference in payload["artifact_references"]:
        reference["project_id"] = payload["ids"]["project_id"]
        reference["path"] = f"artifacts/project-1/references/{reference['kind']}.v1.md"
        content = f"{reference['kind']} evidence for project-1\n".encode("utf-8")
        write_bytes(root, reference["path"], content)
        reference["sha256"] = sha_bytes(content)
    payload["task_local_context"]["artifact_paths"] = [
        authorization_path,
        "artifacts/project-1/input.v1.json",
    ]
    write_bytes(root, "artifacts/project-1/input.v1.json", b"{}\n")
    payload["scope"]["owned_paths"] = scope
    payload["permissions"] = {
        "allowed_actions": ["read", "write-owned-artifact"],
        "allowed_tools": ["repository", "local-tests"],
        "prohibited_actions": ["deploy", "external-message"],
    }
    payload["deliverables"] = ["artifacts/project-1/result.v1.json"]
    payload["acceptance"]["oracle"] = "result.status == accepted"
    payload["acceptance"]["checks"] = ["validate-result"]
    payload["acceptance"]["independent_review"]["evidence_requirements"] = [
        "review-receipt"
    ]
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
    payload["reporting_destination"] = f"task:{parent_task_id}"
    return payload


def manager_payload(root: Path, task_id: str = "manager-1") -> dict:
    payload = populate_payload(
        "manage-company-program",
        root,
        task_id=task_id,
        parent_task_id="master-1",
        scope=["program"],
        decider_id="master-1",
    )
    persist_authorization(payload, root, None)
    return payload


def dispatched_payload(role_name: str, root: Path) -> dict:
    if role_name == "manage-company-program":
        return manager_payload(root)
    parent = manager_payload(root)
    parent_path = "artifacts/project-1/charters/manager-1.v1.json"
    parent_bytes = write_json(root, parent_path, parent)
    payload = populate_payload(
        "execute-bounded-task",
        root,
        task_id="worker-1",
        parent_task_id="manager-1",
        scope=["program/artifact"],
        decider_id="master-1",
    )
    payload["parent_manager_task_id"] = "native-manager-1"
    payload["reporting_destination"] = "task:native-manager-1"
    payload["parent_manager_charter"] = {
        "path": parent_path,
        "sha256": sha_bytes(parent_bytes),
    }
    payload["parent_budget_available"] = {
        "max_tokens": 10000,
        "max_cost_usd": 5.0,
        "max_time_minutes": 30,
        "max_tasks": 1,
        "max_concurrency": 1,
        "max_retries": 1,
    }
    payload["task_local_context"]["artifact_paths"].append(parent_path)
    parent_digest = MODULE.contract_definition_digest(parent)
    assert parent_digest is not None
    persist_authorization(payload, root, parent_digest)
    return payload


def dispatched_worker_with_parent_versions(
    root: Path,
    *,
    program_version: int,
    charter_version: int,
    parent_path_version: int,
) -> dict:
    parent = populate_payload(
        "manage-company-program",
        root,
        task_id="manager-versioned",
        parent_task_id="master-1",
        scope=["program"],
        decider_id="master-1",
    )
    parent["program_version"] = program_version
    parent["charter_version"] = charter_version
    parent["definition_version"] = charter_version
    persist_authorization(parent, root, None)
    parent_path = (
        "artifacts/project-1/charters/manager-versioned."
        f"v{parent_path_version}.json"
    )
    parent_bytes = write_json(root, parent_path, parent)

    payload = populate_payload(
        "execute-bounded-task",
        root,
        task_id="worker-versioned",
        parent_task_id="manager-versioned",
        scope=["program/artifact"],
        decider_id="master-1",
    )
    payload["program_version"] = program_version
    payload["parent_manager_task_id"] = "native-manager-versioned"
    payload["reporting_destination"] = "task:native-manager-versioned"
    payload["parent_manager_charter"] = {
        "path": parent_path,
        "sha256": sha_bytes(parent_bytes),
    }
    payload["parent_budget_available"] = {
        "max_tokens": 10000,
        "max_cost_usd": 5.0,
        "max_time_minutes": 30,
        "max_tasks": 1,
        "max_concurrency": 1,
        "max_retries": 1,
    }
    payload["task_local_context"]["artifact_paths"].append(parent_path)
    parent_digest = MODULE.contract_definition_digest(parent)
    assert parent_digest is not None
    persist_authorization(payload, root, parent_digest)
    return payload


def resign_record(payload: dict, root: Path, mutate) -> None:
    path = root / payload["authorization"]["record_path"]
    record = json.loads(path.read_text(encoding="utf-8"))
    mutate(record)
    record["authentication"]["signature"] = ""
    signature = MODULE.authorization_fixture_signature(record)
    assert signature is not None
    record["authentication"]["signature"] = signature
    write_json(root, payload["authorization"]["record_path"], record)
    digest = MODULE.canonical_digest(record)
    assert digest is not None
    payload["authorization"]["record_sha256"] = digest


def rewrite_parent_charter(payload: dict, root: Path, mutate) -> None:
    reference = payload["parent_manager_charter"]
    path = root / reference["path"]
    parent = json.loads(path.read_text(encoding="utf-8"))
    mutate(parent)
    encoded = write_json(root, reference["path"], parent)
    reference["sha256"] = sha_bytes(encoded)


def assign_nested(target: dict, path: tuple[str, ...], value: object) -> None:
    cursor = target
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = copy.deepcopy(value)


class RoleSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository_root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def validate_payload(self, payload: dict, role: str) -> list[str]:
        return MODULE.validate_contract_payload(
            payload,
            role,
            template=False,
            artifact_root=self.repository_root,
        )

    def test_role_skills_are_compact_versioned_and_consistent(self) -> None:
        self.assertEqual([], MODULE.validate())

    def test_dispatched_v2_contracts_validate_strictly(self) -> None:
        for role_name in MODULE.SKILLS:
            with self.subTest(role=role_name):
                self.assertEqual(
                    [], self.validate_payload(dispatched_payload(role_name, self.repository_root), role_name)
                )

    def test_worker_parent_filename_uses_charter_version_not_program_version(self) -> None:
        payload = dispatched_worker_with_parent_versions(
            self.repository_root,
            program_version=6,
            charter_version=2,
            parent_path_version=2,
        )
        self.assertEqual([], self.validate_payload(payload, "execute-bounded-task"))

    def test_worker_rejects_parent_filename_spoofed_with_program_version(self) -> None:
        payload = dispatched_worker_with_parent_versions(
            self.repository_root,
            program_version=6,
            charter_version=2,
            parent_path_version=6,
        )
        self.assertIn(
            "parent manager charter path version does not match charter_version",
            self.validate_payload(payload, "execute-bounded-task"),
        )

    def test_worker_inherits_design_authorization_without_waiting_on_master(self) -> None:
        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        self.assertEqual("design", payload["authorization_expectation"]["phase"])
        self.assertTrue(payload["decision_barriers"]["inherited_design_authorization_required"])
        self.assertTrue(payload["decision_barriers"]["manager_verification_required"])
        self.assertFalse(payload["decision_barriers"]["worker_waits_for_master"])

    def test_arbitrary_authorization_hash_and_signature_fail_closed(self) -> None:
        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        payload["authorization"]["record_sha256"] = sha("arbitrary-hash")
        self.assertIn(
            "authorization record canonical digest mismatch",
            self.validate_payload(payload, "execute-bounded-task"),
        )

        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        path = self.repository_root / payload["authorization"]["record_path"]
        record = json.loads(path.read_text(encoding="utf-8"))
        record["authentication"]["signature"] = sha("arbitrary-signature")
        write_json(self.repository_root, payload["authorization"]["record_path"], record)
        payload["authorization"]["record_sha256"] = MODULE.canonical_digest(record)
        self.assertIn(
            "authorization fixture signature is invalid",
            self.validate_payload(payload, "execute-bounded-task"),
        )

    def test_malformed_authorization_authentication_never_raises(self) -> None:
        payload = dispatched_payload("manage-company-program", self.repository_root)
        path = self.repository_root / payload["authorization"]["record_path"]
        record = json.loads(path.read_text(encoding="utf-8"))
        record["authentication"]["key_id"] = ["not-hashable"]
        write_json(self.repository_root, payload["authorization"]["record_path"], record)
        payload["authorization"]["record_sha256"] = MODULE.canonical_digest(record)
        self.assertIn(
            "authorization fixture signature is invalid",
            self.validate_payload(payload, "manage-company-program"),
        )

    def test_authorization_substitution_attacks_fail_closed(self) -> None:
        attacks = {
            "program": lambda record: record["bindings"].__setitem__("program_id", "program-2"),
            "phase": lambda record: record["bindings"].__setitem__("phase", "verification"),
            "definition": lambda record: record["bindings"].__setitem__("definition_digest", sha("foreign-definition")),
            "outcome": lambda record: record["bindings"].__setitem__("outcome_digest", sha("foreign-outcome")),
            "decider": lambda record: record["bindings"].__setitem__("decider_id", "master-2"),
            "task": lambda record: record["bindings"].__setitem__("task_id", "worker-2"),
            "parent-task": lambda record: record["bindings"].__setitem__("parent_task_id", "manager-2"),
            "mission-parent": lambda record: record["bindings"].__setitem__(
                "parent_manager_native_task_id", "native-manager-2"
            ),
            "replay": lambda record: record.__setitem__("decision_id", "decision-replayed"),
        }
        for name, mutate in attacks.items():
            with self.subTest(attack=name):
                payload = dispatched_payload("execute-bounded-task", self.repository_root)
                resign_record(payload, self.repository_root, mutate)
                errors = self.validate_payload(payload, "execute-bounded-task")
                self.assertTrue(any("authorization" in item for item in errors), errors)

    def test_whole_signed_authorization_record_substitution_fails_closed(self) -> None:
        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        manager_record_path = (
            self.repository_root
            / "artifacts/project-1/authorizations/manager-1.charter.v1.json"
        )
        substituted = json.loads(manager_record_path.read_text(encoding="utf-8"))
        self.assertEqual(
            substituted["authentication"]["signature"],
            MODULE.authorization_fixture_signature(substituted),
        )
        write_json(
            self.repository_root,
            payload["authorization"]["record_path"],
            substituted,
        )
        digest = MODULE.canonical_digest(substituted)
        self.assertIsNotNone(digest)
        payload["authorization"]["record_sha256"] = digest
        errors = self.validate_payload(payload, "execute-bounded-task")
        self.assertIn(
            "authorization record does not bind the exact contract and lineage",
            errors,
        )
        self.assertIn(
            "authorization decision identity/version does not match expectation",
            errors,
        )
        self.assertNotIn("authorization fixture signature is invalid", errors)

    def test_unaccepted_authorization_decision_fails(self) -> None:
        payload = dispatched_payload("manage-company-program", self.repository_root)
        resign_record(payload, self.repository_root, lambda record: record.__setitem__("status", "rejected"))
        self.assertIn(
            "authorization decision is not accepted for dispatch",
            self.validate_payload(payload, "manage-company-program"),
        )

    def test_authorization_evidence_is_real_project_local_bytes(self) -> None:
        attacks = {
            "path-hash": lambda record: record["evidence_reference"].__setitem__(
                "sha256", sha(record["evidence_reference"]["path"])
            ),
            "cross-project": lambda record: record["evidence_reference"].__setitem__(
                "project_id", "project-2"
            ),
            "cross-project-path": lambda record: record["evidence_reference"].__setitem__(
                "path", "artifacts/project-2/phase-evidence/foreign.charter.v1.json"
            ),
        }
        for name, mutate in attacks.items():
            with self.subTest(attack=name):
                payload = dispatched_payload("manage-company-program", self.repository_root)
                resign_record(payload, self.repository_root, mutate)
                errors = self.validate_payload(payload, "manage-company-program")
                self.assertTrue(any("authorization evidence" in item for item in errors), errors)

    def test_authorization_definition_digest_detects_post_decision_mutation(self) -> None:
        payload = dispatched_payload("manage-company-program", self.repository_root)
        payload["deliverables"].append("artifacts/unapproved.v1.json")
        errors = self.validate_payload(payload, "manage-company-program")
        self.assertIn("authorization record does not bind the exact contract and lineage", errors)

    def test_worker_destination_must_be_exact_parent_manager(self) -> None:
        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        payload["reporting_destination"] = "task:master-1"
        self.assertIn(
            "reporting_destination must canonically target the exact parent task",
            self.validate_payload(payload, "execute-bounded-task"),
        )

    def test_cross_manager_replay_and_stale_parent_digest_fail(self) -> None:
        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        payload["parent_manager_task_id"] = "native-manager-2"
        payload["reporting_destination"] = "task:native-manager-2"
        errors = self.validate_payload(payload, "execute-bounded-task")
        self.assertTrue(any("parent manager" in item or "authorization" in item for item in errors), errors)

        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        payload["parent_manager_charter"]["sha256"] = sha("stale-parent")
        self.assertIn(
            "parent manager charter byte digest mismatch",
            self.validate_payload(payload, "execute-bounded-task"),
        )

    def test_child_scope_permission_tool_and_budget_must_narrow_parent(self) -> None:
        attacks = (
            ("scope", lambda p: p["scope"].__setitem__("owned_paths", ["outside/program"]), "scope escapes"),
            ("action", lambda p: p["permissions"]["allowed_actions"].append("deploy"), "allowed_actions widens"),
            ("tool", lambda p: p["permissions"]["allowed_tools"].append("network"), "allowed_tools widens"),
            ("prohibition", lambda p: p["permissions"].__setitem__("prohibited_actions", ["deploy"]), "prohibited_actions weakens"),
            ("budget", lambda p: p["budget"].__setitem__("max_tokens", 10001), "budget.max_tokens widens"),
        )
        for name, mutate, expected in attacks:
            with self.subTest(attack=name):
                payload = dispatched_payload("execute-bounded-task", self.repository_root)
                mutate(payload)
                errors = self.validate_payload(payload, "execute-bounded-task")
                self.assertTrue(any(expected in item for item in errors), errors)

    def test_every_worker_budget_dimension_must_fit_parent_available_budget(self) -> None:
        for field in MODULE.BUDGET_KEYS:
            with self.subTest(field=field):
                payload = dispatched_payload("execute-bounded-task", self.repository_root)
                if field == "max_cost_usd":
                    payload["parent_budget_available"][field] = 4.0
                elif field == "max_retries":
                    payload["parent_budget_available"][field] = 0
                else:
                    payload["parent_budget_available"][field] = payload["budget"][field] - 1
                errors = self.validate_payload(payload, "execute-bounded-task")
                self.assertTrue(
                    any(f"budget.{field} widens parent residual/allocation" in item for item in errors),
                    errors,
                )

    def test_parent_available_budget_fields_reject_invalid_numeric_values(self) -> None:
        for field in MODULE.BUDGET_KEYS:
            for value in (True, "1", -1, float("nan"), float("inf"), float("-inf")):
                with self.subTest(field=field, value=value):
                    payload = dispatched_payload("execute-bounded-task", self.repository_root)
                    payload["parent_budget_available"][field] = value
                    errors = self.validate_payload(payload, "execute-bounded-task")
                    self.assertTrue(
                        any(f"budget.{field} cannot be compared" in item for item in errors),
                        errors,
                    )

    def test_parent_scope_malformed_values_fail_closed(self) -> None:
        for value in ([1], None, {}, False, ["program", 1]):
            with self.subTest(value=value):
                payload = dispatched_payload(
                    "execute-bounded-task", self.repository_root
                )
                rewrite_parent_charter(
                    payload,
                    self.repository_root,
                    lambda parent, malformed=copy.deepcopy(value): parent["scope"].__setitem__(
                        "owned_paths", malformed
                    ),
                )
                first = self.validate_payload(payload, "execute-bounded-task")
                second = self.validate_payload(payload, "execute-bounded-task")
                self.assertEqual(first, second)
                self.assertTrue(first)
                self.assertNotEqual(
                    ["malformed JSON-shaped contract failed closed"], first
                )

    def test_malformed_parent_nested_fields_fail_closed(self) -> None:
        cases = (
            (("ids",), None),
            (("ids", "project_id"), False),
            (("scope",), []),
            (("permissions",), None),
            (("permissions", "allowed_actions"), {}),
            (("permissions", "allowed_tools"), True),
            (("permissions", "prohibited_actions"), ["deploy", 1]),
            (("budget",), False),
            (("budget", "max_tokens"), {}),
            (("artifact_references",), None),
            (("artifact_references",), [1]),
            (("authorization",), True),
            (("authorization_expectation",), []),
            (("task_local_context",), False),
            (("stop_escalation", "stop_conditions"), {}),
            (("reporting_destination",), ["task:master-1"]),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                payload = dispatched_payload(
                    "execute-bounded-task", self.repository_root
                )
                rewrite_parent_charter(
                    payload,
                    self.repository_root,
                    lambda parent, keys=path, malformed=value: assign_nested(
                        parent, keys, malformed
                    ),
                )
                errors = self.validate_payload(payload, "execute-bounded-task")
                self.assertTrue(errors)

    def test_bounded_json_schema_fuzz_is_deterministic_and_never_raises(self) -> None:
        paths = (
            ("ids",),
            ("ids", "parent_task_id"),
            ("authorization_expectation",),
            ("authorization",),
            ("artifact_references",),
            ("task_local_context",),
            ("scope",),
            ("scope", "owned_paths"),
            ("permissions",),
            ("permissions", "allowed_actions"),
            ("permissions", "allowed_tools"),
            ("permissions", "prohibited_actions"),
            ("dependencies",),
            ("deliverables",),
            ("acceptance",),
            ("acceptance", "checks"),
            ("acceptance", "independent_review"),
            ("decision_barriers",),
            ("budget",),
            ("budget", "max_cost_usd"),
            ("stop_escalation",),
            ("stop_escalation", "escalate_on"),
            ("reporting_destination",),
        )
        malformed_values = (None, False, {}, [1], ["mixed", 1])
        for location in ("worker", "parent"):
            for path in paths:
                for value in malformed_values:
                    with self.subTest(location=location, path=path, value=value):
                        payload = dispatched_payload(
                            "execute-bounded-task", self.repository_root
                        )
                        if location == "worker":
                            assign_nested(payload, path, value)
                        else:
                            rewrite_parent_charter(
                                payload,
                                self.repository_root,
                                lambda parent, keys=path, malformed=value: assign_nested(
                                    parent, keys, malformed
                                ),
                            )
                        first = self.validate_payload(
                            payload, "execute-bounded-task"
                        )
                        second = self.validate_payload(
                            payload, "execute-bounded-task"
                        )
                        self.assertEqual(first, second)
                        self.assertTrue(first)

    def test_cross_project_child_fails_parent_binding(self) -> None:
        payload = dispatched_payload("execute-bounded-task", self.repository_root)
        payload["ids"]["project_id"] = "project-2"
        errors = self.validate_payload(payload, "execute-bounded-task")
        self.assertTrue(any("crosses the contract project" in item for item in errors), errors)

    def test_artifact_references_are_real_safe_versioned_local_bytes(self) -> None:
        attacks = (
            ("path-hash", lambda p, r: r.__setitem__("sha256", sha(r["path"])), "byte digest mismatch"),
            ("missing", lambda p, r: r.__setitem__("path", "artifacts/project-1/references/missing.v1.md"), "unavailable"),
            ("digest", lambda p, r: r.__setitem__("sha256", sha("wrong")), "byte digest mismatch"),
            ("project", lambda p, r: r.__setitem__("project_id", "project-2"), "crosses the contract project"),
            ("project-path", lambda p, r: r.__setitem__("path", "artifacts/project-2/references/architecture.v1.md"), "project-local and versioned"),
            ("root", lambda p, r: r.__setitem__("path", "work/project-1/architecture.v1.md"), "project-local and versioned"),
            ("mutable", lambda p, r: r.__setitem__("path", "artifacts/project-1/references/architecture.md"), "project-local and versioned"),
            ("absolute", lambda p, r: r.__setitem__("path", "/etc/passwd"), "project-local and versioned"),
            ("backslash", lambda p, r: r.__setitem__("path", "artifacts\\project-1\\architecture.v1.md"), "project-local and versioned"),
            ("dot", lambda p, r: r.__setitem__("path", "artifacts/project-1/./architecture.v1.md"), "project-local and versioned"),
            ("escape", lambda p, r: r.__setitem__("path", "artifacts/project-1/../architecture.v1.md"), "project-local and versioned"),
        )
        for name, mutate, expected in attacks:
            with self.subTest(attack=name):
                payload = dispatched_payload("manage-company-program", self.repository_root)
                mutate(payload, payload["artifact_references"][0])
                errors = self.validate_payload(payload, "manage-company-program")
                self.assertTrue(any(expected in item for item in errors), errors)

    def test_artifact_reference_symlink_is_rejected(self) -> None:
        payload = dispatched_payload("manage-company-program", self.repository_root)
        reference = payload["artifact_references"][0]
        path = self.repository_root / reference["path"]
        target = self.repository_root / "artifacts/project-1/references/actual.v1.md"
        target.write_bytes(path.read_bytes())
        path.unlink()
        os.symlink(target, path)
        self.assertIn(
            "artifact reference local evidence path may not traverse a symlink",
            self.validate_payload(payload, "manage-company-program"),
        )

    def test_every_numeric_budget_field_rejects_bad_types_and_nonfinite_values(self) -> None:
        invalid_by_field = {
            "max_tokens": [0, -1, True, "1", 1.0, float("nan"), float("inf"), float("-inf")],
            "max_cost_usd": [-1, True, "1", float("nan"), float("inf"), float("-inf")],
            "max_time_minutes": [0, -1, True, "1", 1.0, float("nan"), float("inf"), float("-inf")],
            "max_tasks": [0, -1, True, "1", 1.0, float("nan"), float("inf"), float("-inf")],
            "max_concurrency": [0, -1, True, "1", 1.0, float("nan"), float("inf"), float("-inf")],
            "max_retries": [-1, True, "0", 0.0, float("nan"), float("inf"), float("-inf")],
        }
        for field, values in invalid_by_field.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    payload = dispatched_payload("manage-company-program", self.repository_root)
                    payload["budget"][field] = value
                    errors = self.validate_payload(payload, "manage-company-program")
                    self.assertTrue(any(f"budget.{field}" in item for item in errors), errors)

    def test_numeric_budget_boundaries_accept(self) -> None:
        payload = dispatched_payload("manage-company-program", self.repository_root)
        payload["budget"].update({
            "max_tokens": 1,
            "max_cost_usd": 0,
            "max_time_minutes": 1,
            "max_tasks": 1,
            "max_concurrency": 1,
            "max_retries": 0,
        })
        persist_authorization(payload, self.repository_root, None)
        self.assertEqual([], self.validate_payload(payload, "manage-company-program"))

    def test_dispatched_scope_rejects_aliases_and_ancestor_overlap(self) -> None:
        for scopes in (
            ["Program/Artifact"],
            ["program/artifáct"],
            ["program//artifact"],
            ["program", "program/artifact"],
        ):
            with self.subTest(scopes=scopes):
                payload = dispatched_payload("manage-company-program", self.repository_root)
                payload["scope"]["owned_paths"] = scopes
                errors = self.validate_payload(payload, "manage-company-program")
                self.assertTrue(any("scope paths" in item for item in errors))

    def test_malformed_payload_types_never_raise(self) -> None:
        mutations = (
            ("task_local_context", None),
            ("scope", False),
            ("permissions", "all"),
            ("acceptance", {"oracle": [], "checks": None, "independent_review": None}),
            ("decision_barriers", {"authenticated_master_decision_required": [], "routine_auto_continue_phase": "execution", "routine_conditions": None}),
            ("budget", {key: None for key in MODULE.BUDGET_KEYS}),
            ("authorization", {"record_path": [], "record_sha256": None}),
            ("authorization_expectation", {"phase": [], "decision_id": None}),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                payload = dispatched_payload("manage-company-program", self.repository_root)
                payload[key] = copy.deepcopy(value)
                self.assertTrue(self.validate_payload(payload, "manage-company-program"))

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
                errors = MODULE.validate_agent_metadata(malformed, "execute-bounded-task")
                self.assertIn("implicit invocation must be structurally disabled", errors)

    def test_role_skills_keep_openai_and_grok_host_bindings(self) -> None:
        for name, root in MODULE.SKILLS.items():
            with self.subTest(role=name):
                openai_text = (root / "agents/openai.yaml").read_text(encoding="utf-8")
                grok_text = (root / "agents/grok.yaml").read_text(encoding="utf-8")
                self.assertEqual([], MODULE.validate_agent_metadata(openai_text, name))
                self.assertEqual([], MODULE.validate_agent_metadata(grok_text, name))
                self.assertEqual(
                    MODULE.parse_agent_yaml(openai_text)[0]["interface"],
                    MODULE.parse_agent_yaml(grok_text)[0]["interface"],
                )

    def test_every_openai_host_binding_has_grok_sibling(self) -> None:
        openai_files = sorted((ROOT / "skills").glob("**/agents/openai.yaml"))
        self.assertGreater(len(openai_files), 0)
        for openai_path in openai_files:
            grok_path = openai_path.with_name("grok.yaml")
            with self.subTest(path=str(openai_path.relative_to(ROOT))):
                self.assertTrue(grok_path.is_file(), f"missing {grok_path}")
                self.assertGreater(grok_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
