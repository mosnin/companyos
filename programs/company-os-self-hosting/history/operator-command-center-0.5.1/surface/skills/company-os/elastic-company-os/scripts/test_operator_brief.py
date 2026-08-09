#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import test_company_os_controller as controller_test

controller = controller_test.controller
MODULE_PATH = Path(__file__).with_name("operator_brief.py")
SPEC = importlib.util.spec_from_file_location("company_os_operator_brief_test", MODULE_PATH)
assert SPEC and SPEC.loader
presenter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(presenter)


class OperatorBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = controller_test.ControllerTests(methodName="runTest")
        self.fixture.setUp()
        self.project = self.fixture.project

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def brief(self, state: dict, prior: dict | None = None, prior_revision: int | None = None) -> dict:
        report = controller.validate_state(state, expected_project=self.project)
        return presenter.build_operator_brief(
            state,
            report,
            {"ok": True, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES,
            critical_dimensions=controller.BASE_DIMENSIONS,
            prior_state=prior,
            prior_revision=prior_revision,
        )

    def test_missing_experience_quality_becomes_the_one_next_action(self) -> None:
        state = self.fixture.valid_state()
        state["phase"] = "experience"
        for item in state["quality"]["dimensions"].values():
            item["score"] = None
            item["evidence"] = []
        brief = self.brief(state)
        self.assertEqual(brief["gate"]["status"], "needs_quality")
        self.assertEqual(brief["gate"]["next_action"]["kind"], "audit_quality")
        self.assertEqual(brief["quality"]["required"], 13)
        self.assertEqual(brief["quality"]["passed"], 0)

    def test_invalid_evidence_precedes_quality_and_authority_work(self) -> None:
        state = self.fixture.valid_state()
        artifact = self.project / state["evidence"]["reality"][0]["artifact_path"]
        artifact.write_text("drift\n", encoding="utf-8")
        brief = self.brief(state)
        self.assertEqual(brief["gate"]["status"], "needs_evidence")
        self.assertEqual(brief["gate"]["next_action"]["kind"], "repair_evidence")

    def test_operator_projection_never_exposes_signed_grants(self) -> None:
        state = self.fixture.valid_state()
        secret_token = state["quality"]["dimensions"]["user_value"]["scorer_grant"]["token"]
        brief = self.brief(state)
        encoded = json.dumps(brief, sort_keys=True)
        self.assertNotIn(secret_token, encoded)
        self.assertNotIn("reviewer_grant", encoded)
        self.assertNotIn("scorer_grant", encoded)
        self.assertNotIn("consumed_grant_nonces", encoded)

    def test_markdown_renders_untrusted_project_text_as_inert_content(self) -> None:
        state = self.fixture.valid_state()
        state["instance"]["name"] = "<script>[click](javascript:alert(1))</script>"
        brief = self.brief(state)
        rendered = presenter.render_markdown(brief)
        html_view = presenter.render_html(brief)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("[click](javascript", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("One move now", rendered)
        self.assertNotIn("<script>[click]", html_view)
        self.assertIn("&lt;script&gt;", html_view)
        brief["gate"]["impact"] = '<script>window.bad = true</script> "decision"'
        html_view = presenter.render_html(brief)
        self.assertIn('<p class="change-impact"><span>Why now</span>&lt;script&gt;window.bad = true&lt;/script&gt; &quot;decision&quot;</p>', html_view)
        self.assertNotIn("<script>window.bad", html_view)
        self.assertIn("prefers-reduced-motion", html_view)
        self.assertIn("<main>", html_view)
        self.assertIn('class="skip-link"', html_view)
        self.assertIn('href="#decision-heading"', html_view)
        self.assertIn("@media(max-width:560px)", html_view)

    def test_cli_reads_sqlite_authority_and_marks_export_drift(self) -> None:
        state = self.fixture.valid_state()
        self.fixture.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    controller_test.namespace(project=str(self.project))
                ),
                0,
            )
        export = controller.load_json(self.project / ".company-os" / "control.json")
        export["instance"]["name"] = "TAMPERED EXPORT"
        controller.atomic_write_json(self.project / ".company-os" / "control.json", export)
        args = controller_test.namespace(project=str(self.project), format="json", strict=False)
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 0)
        brief = json.loads(output.getvalue())
        self.assertEqual(brief["project"]["name"], "Test")
        self.assertFalse(brief["authority"]["exports_match"])

    def test_strict_mode_signals_a_blocked_gate_without_hiding_the_brief(self) -> None:
        state = self.fixture.valid_state()
        state["quality"]["dimensions"]["user_value"]["score"] = None
        self.fixture.write_state(state)
        args = controller_test.namespace(project=str(self.project), format="markdown", strict=True)
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 1)
        self.assertIn("# Company OS", output.getvalue())
        self.assertIn("One move now", output.getvalue())

    def test_render_is_deterministic_and_does_not_mutate_authority(self) -> None:
        state = self.fixture.valid_state()
        self.fixture.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    controller_test.namespace(project=str(self.project))
                ),
                0,
            )
        store = controller.control_store_module()
        before_revision, before_state = store.load(self.project)
        args = controller_test.namespace(project=str(self.project), format="json", strict=False)
        with redirect_stdout(first := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 0)
        with redirect_stdout(second := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 0)
        after_revision, after_state = store.load(self.project)
        self.assertEqual(first.getvalue(), second.getvalue())
        self.assertEqual(before_revision, after_revision)
        self.assertEqual(controller.canonical_json(before_state), controller.canonical_json(after_state))

    def test_control_failure_outranks_evidence_and_quality(self) -> None:
        state = self.fixture.valid_state()
        report = controller.validate_state(state, expected_project=self.project)
        report["errors"] = [
            "phase experience requires complete applicable quality evidence",
            "evidence.reality[0].snapshot is corrupt",
            "control store: revision chain is broken",
        ]
        report["ok"] = False
        brief = presenter.build_operator_brief(
            state, report,
            {"ok": False, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES,
            critical_dimensions=controller.BASE_DIMENSIONS,
        )
        self.assertEqual(brief["gate"]["status"], "control_failure")
        self.assertEqual(brief["gate"]["next_action"]["kind"], "repair_control")

    def test_supervision_and_feedback_are_safe_aggregates(self) -> None:
        state = self.fixture.valid_state()
        state["execution_fabric"]["managers"] = {
            "manager-a": {"status": "awaiting_decision", "next_phase": "discovery", "model": "gpt-5.6-sol", "reports": [{"phase": "charter"}, {"phase": "discovery"}]},
            "manager-b": {"status": "pending", "next_phase": "charter", "model": "gpt-5.6-sol", "reports": []},
        }
        state["runtime_adapter"]["attempts"] = [
            {
                "attempt_id": "attempt-1", "manifest_identity_id": "manager-a", "role": "manager", "status": "running",
                "requested_model": "gpt-5.6-sol", "observed_model": None,
                "provider": "test", "parent_runtime_id": "master-1",
                "secret": "must-not-leak",
            }
        ]
        state["feedback"]["cycles"] = [
            {"cost_usd": float("nan"), "latency_minutes": -2, "token_usage": -1},
            {"cost_usd": 1.25, "latency_minutes": 4, "token_usage": 90, "reviewer_decision": "accepted", "user_visible_movement": True},
        ]
        brief = self.brief(state)
        self.assertEqual(brief["execution"]["manager_count"], 2)
        self.assertEqual(brief["execution"]["manager_reports"], 2)
        self.assertEqual(len(brief["execution"]["runtime_attempts"]), 1)
        self.assertEqual(brief["execution"]["managers"][0]["requested_model"], "gpt-5.6-sol")
        self.assertEqual(brief["execution"]["managers"][0]["decision_required"], "discovery")
        self.assertNotIn("must-not-leak", json.dumps(brief))
        self.assertEqual(brief["feedback"]["metrics"]["cost"]["value"], 1.25)
        self.assertEqual(brief["feedback"]["metrics"]["lead_time"]["value"], 4.0)
        self.assertEqual(brief["feedback"]["metrics"]["tokens"]["value"], 90)
        self.assertEqual(brief["feedback"]["metrics"]["cost"]["invalid_sources"], 1)
        rendered = presenter.render_markdown(brief)
        self.assertIn("1 invalid", rendered)
        self.assertIn("Requested", rendered)
        self.assertIn("Observed", rendered)

    def test_provider_observed_model_comes_only_from_gateway_verified_observation(self) -> None:
        state = self.fixture.valid_state()
        state["runtime_adapter"]["attempts"] = [{
            "attempt_id": "attempt-observed", "manifest_identity_id": "manager-a",
            "role": "manager", "status": "admitted", "requested_model": "gpt-5.6-sol",
            "observed_model": "untrusted-admission-field", "provider": "provider",
            "parent_runtime_id": "master", "budget": {"max_tokens": 100},
        }]
        state["runtime_adapter"]["observation_inboxes"] = {
            "attempt-observed": {"trusted_observations": [{
                "trust": "gateway_verified", "claims": {"observed_model": "provider/model-v2"},
            }]}
        }
        brief = self.brief(state)
        attempt = brief["execution"]["runtime_attempts"][0]
        self.assertEqual(attempt["observed_model"], "provider/model-v2")
        self.assertEqual(attempt["model_evidence"], "gateway_verified")
        self.assertNotIn("untrusted-admission-field", json.dumps(brief))

    def test_generic_budget_error_marks_every_relevant_row_as_exception(self) -> None:
        state = self.fixture.valid_state()
        state["execution_fabric"]["managers"] = {
            "manager-a": {"status": "pending", "next_phase": "charter", "reports": [], "decisions": []},
        }
        state["runtime_adapter"]["attempts"] = [{
            "attempt_id": "attempt-budget", "manifest_identity_id": "manager-a",
            "role": "manager", "status": "admitted", "requested_model": "gpt-5.6-sol",
            "provider": "provider", "parent_runtime_id": "master", "budget": {"max_tokens": 100},
        }]
        report = controller.validate_state(state, expected_project=self.project)
        report["errors"] = ["runtime attempt budget does not match its manifest identity"]
        report["ok"] = False
        brief = presenter.build_operator_brief(
            state, report,
            {"ok": True, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES, critical_dimensions=controller.BASE_DIMENSIONS,
        )
        self.assertEqual(brief["execution"]["managers"][0]["budget_evidence"], "exception")
        self.assertEqual(brief["execution"]["runtime_attempts"][0]["budget_evidence"], "exception")

    def test_every_manager_operating_state_is_rendered_in_both_surfaces(self) -> None:
        cases = {
            "pending": {"status": "pending", "reports": [], "decisions": []},
            "reporting": {"status": "ready", "reports": [{"phase": "design"}], "decisions": []},
            "awaiting_decision": {"status": "awaiting_decision", "reports": [{"phase": "design"}], "decisions": []},
            "in_rework": {"status": "ready", "reports": [{"phase": "design"}], "decisions": [{"decision": "rework"}]},
            "accepted": {"status": "accepted", "reports": [], "decisions": []},
            "paused": {"status": "paused", "reports": [], "decisions": []},
            "terminated": {"status": "terminated", "reports": [], "decisions": []},
        }
        for expected, manager in cases.items():
            with self.subTest(expected=expected):
                state = self.fixture.valid_state()
                state["execution_fabric"]["managers"] = {
                    "manager-a": {
                        "id": "manager-a", "model": "gpt-5.6-sol", "next_phase": "design",
                        "rework_rounds": 1 if expected == "in_rework" else 0,
                        **manager,
                    },
                }
                brief = self.brief(state)
                row = brief["execution"]["managers"][0]
                self.assertEqual(row["status"], expected)
                label = presenter._label(expected)
                self.assertIn(label, presenter.render_markdown(brief))
                self.assertIn(f"<td>{label}</td>", presenter.render_html(brief))

    def test_runtime_identity_and_budget_evidence_matrix_is_rendered(self) -> None:
        state = self.fixture.valid_state()
        state["runtime_adapter"]["attempts"] = [
            {
                "attempt_id": "attempt-unobserved", "manifest_identity_id": "manager-a", "role": "manager",
                "status": "admitted", "requested_model": "gpt-5.6-sol", "provider": "provider",
                "parent_runtime_id": "master",
            },
            {
                "attempt_id": "attempt-provider-unknown", "manifest_identity_id": "manager-b", "role": "manager",
                "status": "admitted", "requested_model": "gpt-5.6-sol", "provider": "provider",
                "parent_runtime_id": "master", "budget": {"max_tokens": 100},
            },
            {
                "attempt_id": "attempt-observed", "manifest_identity_id": "manager-c", "role": "manager",
                "status": "admitted", "requested_model": "gpt-5.6-sol", "provider": "provider",
                "parent_runtime_id": "master", "budget": {"max_tokens": 100},
            },
        ]
        state["runtime_adapter"]["observation_inboxes"] = {
            "attempt-provider-unknown": {"trusted_observations": [
                {"trust": "gateway_verified", "claims": {}},
            ]},
            "attempt-observed": {"trusted_observations": [
                {"trust": "gateway_verified", "claims": {"observed_model": "provider/model-v3"}},
            ]},
        }
        report = controller.validate_state(state, expected_project=self.project)
        report["errors"] = ["budget limit exceeded for attempt-observed"]
        report["ok"] = False
        brief = presenter.build_operator_brief(
            state, report,
            {"ok": True, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES, critical_dimensions=controller.BASE_DIMENSIONS,
        )
        rows = {item["attempt_id"]: item for item in brief["execution"]["runtime_attempts"]}
        self.assertEqual((rows["attempt-unobserved"]["model_evidence"], rows["attempt-unobserved"]["budget_evidence"]), ("unverified", "unknown"))
        self.assertEqual((rows["attempt-provider-unknown"]["model_evidence"], rows["attempt-provider-unknown"]["budget_evidence"]), ("provider_unknown", "declared_only"))
        self.assertEqual((rows["attempt-observed"]["model_evidence"], rows["attempt-observed"]["budget_evidence"]), ("gateway_verified", "exception"))
        rendered = presenter.render_markdown(brief) + presenter.render_html(brief)
        for expected in ("Unverified", "Provider Unknown", "Gateway Verified", "Declared Only", "Exception", "provider/model-v3"):
            self.assertIn(expected, rendered)

    def test_html_state_colors_and_safe_schedule_are_semantic(self) -> None:
        base = self.brief(self.fixture.valid_state())

        ready = json.loads(json.dumps(base))
        ready["gate"]["status"] = "ready"
        ready["authority"]["validation_valid"] = True
        ready["execution"]["schedule_enabled"] = False
        ready["execution"]["protected_launcher_ready"] = False
        rendered = presenter.render_html(ready)
        self.assertIn('class="status status--ready"', rendered)
        self.assertIn('class="fact fact--good"><span>Certification</span><strong>Current</strong>', rendered)
        self.assertIn('class="fact fact--safe"><span>Schedule</span><strong>Off — safe default</strong><small>Launcher proof required</small>', rendered)

        proven_off = json.loads(json.dumps(ready))
        proven_off["execution"]["protected_launcher_ready"] = True
        self.assertIn('class="fact fact--safe"><span>Schedule</span><strong>Off — safe default</strong><small>Launcher protected</small>', presenter.render_html(proven_off))

        blocked = json.loads(json.dumps(base))
        blocked["gate"]["status"] = "needs_quality"
        blocked["authority"]["validation_valid"] = False
        rendered = presenter.render_html(blocked)
        self.assertIn('class="status status--blocked"', rendered)
        self.assertIn('class="fact fact--bad"><span>Certification</span><strong>Not current</strong>', rendered)

        cancelled = json.loads(json.dumps(base))
        cancelled["gate"]["status"] = "cancelled"
        self.assertIn('class="status status--cancelled"', presenter.render_html(cancelled))

        unsafe_on = json.loads(json.dumps(base))
        unsafe_on["execution"]["schedule_enabled"] = True
        unsafe_on["execution"]["scheduler_ready"] = False
        self.assertIn('class="fact fact--bad"><span>Schedule</span><strong>On</strong>', presenter.render_html(unsafe_on))

        accepted_on = json.loads(json.dumps(base))
        accepted_on["execution"]["schedule_enabled"] = True
        accepted_on["execution"]["scheduler_ready"] = True
        self.assertIn('class="fact fact--good"><span>Schedule</span><strong>On</strong>', presenter.render_html(accepted_on))

    def test_decision_badge_is_not_a_false_button_and_handoff_is_direct(self) -> None:
        state = self.fixture.valid_state()
        state["phase"] = "experience"
        state["evidence"]["experience"][0]["source_artifact_path"] = "programs/example/ACCEPTANCE_MATRIX.md"
        brief = self.brief(state)
        rendered = presenter.render_html(brief)
        self.assertRegex(rendered, r'class="decision-mark" aria-hidden="true">\d{2}</span>')
        self.assertNotIn('<svg viewBox="0 0 24 24"', rendered)
        self.assertIn('class="decision-link" href="#decision-handoff"', rendered)
        self.assertIn('id="decision-handoff" open', rendered)
        self.assertIn("programs/example/ACCEPTANCE_MATRIX.md", rendered)
        self.assertIn('href="/programs/example/ACCEPTANCE_MATRIX.md"', rendered)
        self.assertIn('<p class="decision-context"><strong>Outcome</strong>', rendered)
        self.assertIn("programs/example/ACCEPTANCE\\_MATRIX.md", presenter.render_markdown(brief))

    def test_project_references_reject_absolute_and_parent_paths(self) -> None:
        self.assertEqual(presenter._safe_project_reference("programs/example/matrix.md"), "programs/example/matrix.md")
        self.assertIsNone(presenter._safe_project_reference("/private/tmp/secret.md"))
        self.assertIsNone(presenter._safe_project_reference("../secret.md"))
        self.assertIsNone(presenter._safe_project_reference("programs\\secret.md"))

    def test_legacy_instance_names_migration_as_the_next_move(self) -> None:
        state = self.fixture.valid_state()
        self.fixture.write_state(state)
        args = controller_test.namespace(project=str(self.project), format="json", strict=False)
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 0)
        brief = json.loads(output.getvalue())
        self.assertEqual(brief["gate"]["status"], "control_failure")
        self.assertEqual(brief["gate"]["next_action"]["kind"], "repair_control")

    def test_numeric_quality_score_is_invalid_when_its_audit_contract_fails(self) -> None:
        state = self.fixture.valid_state()
        state["quality"]["dimensions"]["user_value"]["binding"]["rubric_version"] = "wrong"
        brief = self.brief(state)
        row = next(item for item in brief["quality"]["dimensions"] if item["dimension"] == "user_value")
        self.assertEqual(row["score"], 9)
        self.assertEqual(row["status"], "invalid")
        self.assertFalse(row["audit_valid"])

    def test_global_quality_policy_error_invalidates_high_numeric_rows(self) -> None:
        state = self.fixture.valid_state()
        state["quality"]["threshold"] = 8
        brief = self.brief(state)
        self.assertTrue(brief["quality"]["invalid"])
        self.assertFalse(any(item["status"] == "pass" for item in brief["quality"]["dimensions"]))

    def test_program_execution_and_authority_blockers_have_explicit_routes(self) -> None:
        state = self.fixture.valid_state()
        cases = {
            "current outcome is inconsistent with primary work": "repair_program",
            "execution fabric manager report is missing": "resolve_execution",
            "actor issuer public key is not configured": "configure_issuer",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                report = controller.validate_state(state, expected_project=self.project)
                report["errors"] = [message]
                report["ok"] = False
                report["actor_issuer_ready"] = expected != "configure_issuer"
                brief = presenter.build_operator_brief(
                    state, report,
                    {"ok": True, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
                    phases=controller.PHASES, critical_dimensions=controller.BASE_DIMENSIONS,
                )
                self.assertEqual(brief["gate"]["next_action"]["kind"], expected)

    def test_direction_delta_and_named_stage_track_lead_the_human_view(self) -> None:
        prior = self.fixture.valid_state()
        current = json.loads(json.dumps(prior))
        current["strategy"]["program_version"] = 2
        current["strategy"]["current_outcome"] = "Ship an exceptional operator command center"
        current["phase"] = "reality_audit"
        current["evidence"] = {key: [] for key in controller.EVIDENCE_BUCKETS}
        current["portfolio"]["active_work"] = []
        brief = self.brief(current, prior=prior, prior_revision=6)
        kinds = {item["kind"] for item in brief["gate"]["changes"]}
        self.assertTrue({"program", "direction", "phase"}.issubset(kinds))
        rendered = presenter.render_markdown(brief)
        self.assertLess(rendered.index("## Latest governed change"), rendered.index("## Direction"))
        self.assertIn(r"Reality Audit \[Current\]", rendered)
        self.assertIn(r"Intelligence \[Future\]", rendered)
        self.assertNotIn("●", rendered)
        self.assertNotIn("◉", rendered)

    def test_no_feedback_observations_are_never_rendered_as_zero(self) -> None:
        state = self.fixture.valid_state()
        state["feedback"]["cycles"] = []
        rendered = presenter.render_markdown(self.brief(state))
        self.assertEqual(rendered.count("No observations"), 3)
        self.assertNotIn("Tokens: **0", rendered)

    def test_missing_stage_evidence_requests_new_proof_not_supersession(self) -> None:
        state = self.fixture.valid_state()
        state["phase"] = "reality_audit"
        state["evidence"]["reality"] = []
        state["portfolio"]["active_work"] = []
        brief = self.brief(state)
        self.assertEqual(brief["gate"]["next_action"]["kind"], "record_evidence")

    def test_cli_compares_an_explicit_authoritative_revision(self) -> None:
        state = self.fixture.valid_state()
        self.fixture.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.migrate_control_store(controller_test.namespace(project=str(self.project))), 0)
            self.assertEqual(controller.replace_program(controller_test.namespace(
                project=str(self.project), north_star="New mandate", current_outcome="New outcome",
                success_metric="One result", reason="comparison test",
            )), 0)
            self.assertEqual(controller.replace_program(controller_test.namespace(
                project=str(self.project), north_star="Newest mandate", current_outcome="Newest outcome",
                success_metric="Newest result", reason="second comparison test",
            )), 0)
        default_args = controller_test.namespace(project=str(self.project), format="json", strict=False)
        with redirect_stdout(default_output := io.StringIO()):
            self.assertEqual(controller.brief_instance(default_args), 0)
        default_brief = json.loads(default_output.getvalue())
        self.assertEqual(default_brief["gate"]["comparison_window"], {"from_revision": 2, "to_revision": 3, "event_count": 1})
        args = controller_test.namespace(project=str(self.project), format="json", strict=False, since_revision=1)
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 0)
        brief = json.loads(output.getvalue())
        self.assertEqual(brief["gate"]["comparison_window"], {"from_revision": 1, "to_revision": 3, "event_count": 2})
        self.assertTrue(any(item.get("comparison") == "revision 1 → 3" for item in brief["gate"]["changes"]))
        self.assertEqual(brief["gate"]["change_events"][-1]["event_type"], "program_replaced")
        self.assertEqual(brief["gate"]["change_events"][-1]["revision"], 3)

    def test_cli_rejects_a_nonhistorical_comparison_without_mutation(self) -> None:
        state = self.fixture.valid_state()
        self.fixture.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.migrate_control_store(controller_test.namespace(project=str(self.project))), 0)
        store = controller.control_store_module()
        before = store.load(self.project)
        args = controller_test.namespace(project=str(self.project), format="json", strict=False, since_revision=1)
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.brief_instance(args), 2)
        self.assertIn("must be earlier", output.getvalue())
        self.assertEqual(store.load(self.project), before)

    def test_legacy_issuer_rotation_warning_is_visible(self) -> None:
        state = self.fixture.valid_state()
        report = controller.validate_state(state, expected_project=self.project)
        report["warnings"].append("legacy evidence review is transactionally retained but lacks its historical public verification key")
        brief = presenter.build_operator_brief(
            state, report,
            {"ok": True, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES, critical_dimensions=controller.BASE_DIMENSIONS,
        )
        self.assertIn("legacy evidence review", presenter.render_markdown(brief))
        self.assertIn("legacy evidence review", presenter.render_html(brief))

    def test_html_projection_is_deterministic_and_redacted(self) -> None:
        state = self.fixture.valid_state()
        brief = self.brief(state)
        first = presenter.render_html(brief)
        second = presenter.render_html(brief)
        self.assertEqual(first, second)
        self.assertNotIn("scorer_grant", first)
        self.assertNotIn(state["quality"]["dimensions"]["user_value"]["scorer_grant"]["token"], first)
        self.assertIn("Company OS seven-stage journey", first)
        self.assertIn("aria-label", first)
        self.assertIn("Governed decision handoff", first)
        self.assertIn("<h2>", first)
        self.assertNotIn("<h3>", first)

    def test_html_quality_action_is_concise_without_losing_full_contract(self) -> None:
        state = self.fixture.valid_state()
        state["phase"] = "experience"
        for item in state["quality"]["dimensions"].values():
            item["score"] = None
            item["evidence"] = []
        brief = self.brief(state)
        rendered = presenter.render_html(brief)
        self.assertIn("13 / 13 dimensions independently accepted at their gates.", rendered)
        self.assertIn("Record the report, then pass brief --strict.", rendered)
        self.assertIn(brief["gate"]["next_action"]["instruction"], rendered)
        self.assertIn(brief["gate"]["next_action"]["success_signal"], rendered)
        self.assertIn(brief["gate"]["next_action"]["verification"], rendered)

    def test_html_recent_trail_is_bounded_and_comparison_scope_is_explicit(self) -> None:
        state = self.fixture.valid_state()
        report = controller.validate_state(state, expected_project=self.project)
        change_events = [
            {
                "revision": index,
                "event_type": "work_queued",
                "command": "queue-work",
                "command_key": f"command-{index}",
                "references": {"work_id": f"work-{index}"},
            }
            for index in range(1, 6)
        ]
        brief = presenter.build_operator_brief(
            state,
            report,
            {"ok": True, "backend": "sqlite", "revision": 7, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES,
            critical_dimensions=controller.BASE_DIMENSIONS,
            prior_revision=2,
            change_events=change_events,
        )
        rendered = presenter.render_html(brief)
        self.assertIn("Latest governed change · Update 2 → 7", rendered)
        self.assertIn("Governed command trail · Update 2 → 7", rendered)
        self.assertIn("View 5 updates in this comparison", rendered)
        self.assertNotIn("View all", rendered)
        recent = rendered.split('<details class="trail-all">', 1)[0]
        self.assertNotIn("work-1", recent)
        for index in range(2, 6):
            self.assertIn(f"work-{index}", recent)
        self.assertIn("work-1", rendered)
        self.assertIn("work-5", rendered)
        self.assertIn(".trail-panel>.trail li:nth-child(n+3)", rendered)

    def test_single_update_window_never_claims_total_history(self) -> None:
        state = self.fixture.valid_state()
        report = controller.validate_state(state, expected_project=self.project)
        brief = presenter.build_operator_brief(
            state,
            report,
            {"ok": True, "backend": "sqlite", "revision": 15, "state_export_match": True, "events_export_match": True},
            phases=controller.PHASES,
            critical_dimensions=controller.BASE_DIMENSIONS,
            prior_revision=14,
            change_events=[{"revision": 15, "event_type": "work_queued", "references": {"work_id": "work-15"}}],
        )
        html_view = presenter.render_html(brief)
        markdown_view = presenter.render_markdown(brief)
        self.assertIn("Update 14 → 15", html_view)
        self.assertIn("View 1 update in this comparison", html_view)
        self.assertIn("Governed command trail · Update 14 → 15", markdown_view)
        self.assertNotIn("View all", html_view)


if __name__ == "__main__":
    unittest.main()
