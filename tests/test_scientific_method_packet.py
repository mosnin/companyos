from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "company-os"
SCRIPT = SKILL / "scripts" / "validate_scientific_method_packet.py"
EXAMPLE = SKILL / "assets" / "scientific-method-packet.example.json"
PLAYBOOK = SKILL / "references" / "scientific-method.md"
REQUEST_EXAMPLE = (
    ROOT / "skills" / "company-os" / "compile-outcome-contract" / "references" / "outcome-request.example.json"
)
SPEC = importlib.util.spec_from_file_location("validate_scientific_method_packet", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def example_packet() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def outcome_request() -> dict:
    return json.loads(REQUEST_EXAMPLE.read_text(encoding="utf-8"))


class ScientificMethodPacketTests(unittest.TestCase):
    def test_example_packet_validates(self) -> None:
        self.assertEqual([], MODULE.validate_packet(example_packet()))

    def test_example_packet_binds_published_outcome_request(self) -> None:
        self.assertEqual(
            [],
            MODULE.validate_against_request(example_packet(), outcome_request()),
        )

    def test_cli_accepts_example_and_request(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(EXAMPLE), "--request", str(REQUEST_EXAMPLE)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual([], payload["errors"])

    def test_unknown_keys_fail_closed(self) -> None:
        packet = example_packet()
        packet["orchestrator"] = True
        self.assertIn("unknown keys: orchestrator", MODULE.validate_packet(packet))

    def test_missing_disconfirm_condition_fails(self) -> None:
        packet = example_packet()
        packet["disconfirm_condition"] = " "
        self.assertTrue(
            any("disconfirm_condition" in item for item in MODULE.validate_packet(packet))
        )

    def test_authority_cannot_become_orchestrator(self) -> None:
        packet = example_packet()
        packet["authority"] = "orchestrator"
        self.assertIn("authority must be overlay", MODULE.validate_packet(packet))

    def test_forbidden_next_action_fails(self) -> None:
        packet = example_packet()
        for action in (
            "launch_runtime",
            "enable_scheduler",
            "complete_from_narrative",
            "run_scientific_method",
        ):
            with self.subTest(action=action):
                mutated = copy.deepcopy(packet)
                mutated["next_action"] = action
                errors = MODULE.validate_packet(mutated)
                self.assertTrue(any("next_action" in item for item in errors))

    def test_new_primary_loop_is_rejected(self) -> None:
        packet = example_packet()
        packet["loop"]["primary"] = "scientific-method-loop"
        self.assertIn(
            "loop.primary is not an existing Company OS primary loop",
            MODULE.validate_packet(packet),
        )

    def test_parallel_variants_require_divergent_exploration_loop(self) -> None:
        packet = example_packet()
        packet["loop"]["primary"] = "bounded-evidence-loop"
        self.assertIn(
            "parallel variants require bounded-divergent-exploration-loop",
            MODULE.validate_packet(packet),
        )

    def test_loop_activation_must_stay_planned(self) -> None:
        packet = example_packet()
        packet["loop"]["activation_state"] = "active"
        self.assertIn("loop.activation_state must be planned", MODULE.validate_packet(packet))

    def test_supported_outcome_requires_independent_receipt(self) -> None:
        packet = example_packet()
        packet["status"] = "supported"
        packet["evidence"] = [{"kind": "citation", "ref": "source://note"}]
        errors = MODULE.validate_packet(packet)
        self.assertTrue(any("evaluator or reality receipt" in item for item in errors))

    def test_supported_outcome_accepts_evaluator_receipt(self) -> None:
        packet = example_packet()
        packet["status"] = "supported"
        packet["next_action"] = "run_outcome_loop"
        packet["evidence"] = [
            {
                "kind": "evaluator_receipt",
                "ref": "artifacts/viral-game/evaluator-execution.v1.json",
            }
        ]
        self.assertEqual([], MODULE.validate_packet(packet))

    def test_hypothesis_cannot_carry_acceptance_evidence(self) -> None:
        packet = example_packet()
        packet["evidence"] = [{"kind": "citation", "ref": "source://too-soon"}]
        self.assertIn(
            "hypothesis status cannot carry acceptance evidence",
            MODULE.validate_packet(packet),
        )

    def test_refuted_requires_preserved_evidence(self) -> None:
        packet = example_packet()
        packet["status"] = "refuted"
        packet["next_action"] = "rework"
        self.assertIn("refuted requires preserved evidence", MODULE.validate_packet(packet))

    def test_binding_kind_must_match_class(self) -> None:
        packet = example_packet()
        packet["experiment_class"] = "innovation_bet"
        errors = MODULE.validate_packet(packet)
        self.assertTrue(any("binding.kind" in item for item in errors))
        self.assertTrue(any("test.kind" in item for item in errors))

    def test_innovation_bet_packet_validates(self) -> None:
        packet = example_packet()
        packet.update(
            {
                "packet_id": "smp-thin-evidence-bet",
                "experiment_class": "innovation_bet",
                "hypothesis_id": "voice-first-onboarding",
                "hypothesis": "A voice-first onboarding path will convert first-session users.",
                "disconfirm_condition": "A capped prototype fails the learning metric inside the time box.",
                "next_action": "hold_bet",
            }
        )
        packet["binding"] = {
            "kind": "innovation_bet",
            "record_id": "voice-first-onboarding",
            "record_sha256": None,
            "field_id": "voice-first-onboarding",
        }
        packet["cap"]["max_variants"] = 1
        packet["loop"]["primary"] = "bounded-evidence-loop"
        packet["test"] = {
            "kind": "kill_rule",
            "rule": "Kill if the learning metric is unmet at the time/cost cap.",
        }
        self.assertEqual([], MODULE.validate_packet(packet))

    def test_supported_adaptation_requires_independent_review(self) -> None:
        packet = {
            "schema": MODULE.SCHEMA,
            "packet_id": "smp-wip-limit",
            "experiment_class": "process_adaptation",
            "hypothesis_id": "tighter-wip",
            "hypothesis": "A tighter WIP limit reduces collision rework.",
            "status": "supported",
            "disconfirm_condition": "Collision rate does not fall inside the capped trial.",
            "binding": {
                "kind": "adaptation",
                "record_id": "tighter-wip",
                "record_sha256": None,
                "field_id": "tighter-wip",
            },
            "cap": {"max_time_minutes": 60, "max_cost_usd": 0, "max_variants": 1},
            "test": {
                "kind": "adaptation_review",
                "rule": "A different reviewer must accept the reversible WIP change.",
            },
            "loop": {
                "primary": "bounded-evidence-loop",
                "activation_state": "planned",
            },
            "next_action": "review_adaptation",
            "authority": "overlay",
            "evidence": [{"kind": "citation", "ref": "cycle://drift-3"}],
        }
        errors = MODULE.validate_packet(packet)
        self.assertTrue(any("independent review decision" in item for item in errors))

    def test_request_binding_rejects_unknown_domain(self) -> None:
        packet = example_packet()
        packet["hypothesis_id"] = "missing-domain"
        packet["binding"]["field_id"] = "missing-domain"
        errors = MODULE.validate_against_request(packet, outcome_request())
        self.assertIn("binding.field_id is not a request domain_id", errors)

    def test_refuted_request_cannot_be_marked_supported(self) -> None:
        request = outcome_request()
        request["domain_hypotheses"][0]["status"] = "refuted"
        packet = example_packet()
        packet["status"] = "supported"
        packet["evidence"] = [
            {
                "kind": "evaluator_receipt",
                "ref": "artifacts/viral-game/evaluator-execution.v1.json",
            }
        ]
        errors = MODULE.validate_against_request(packet, request)
        self.assertIn("a refuted request hypothesis cannot be marked supported", errors)

    def test_malformed_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.json"
            path.write_text("{", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertTrue(any("unreadable JSON" in item for item in payload["errors"]))


class ScientificMethodPlaybookTests(unittest.TestCase):
    def test_playbook_is_overlay_not_orchestrator(self) -> None:
        text = PLAYBOOK.read_text(encoding="utf-8").casefold()
        required = (
            "does not own",
            "domain_hypotheses",
            "bounded-divergent-exploration-loop",
            "sensor",
            "reality",
            "2 managers",
            "company-os.scientific-method-packet.v1",
        )
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term, text)
        self.assertNotIn("owns iteration", text)
        self.assertNotIn("enable runtime", text)

    def test_existing_skills_point_at_the_packet(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/select-execution-loop/SKILL.md",
            ROOT / "skills/company-os/intelligence/research-intelligence/SKILL.md",
            ROOT / "skills/company-os/intelligence/innovation-bets/SKILL.md",
            ROOT / "skills/company-os/close-outcome-discovery/SKILL.md",
            ROOT / "skills/company-os/intelligence/evidence-research-campaign/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(
                    "scientific-method" in text or "scientific-method-packet" in text
                )


if __name__ == "__main__":
    unittest.main()
