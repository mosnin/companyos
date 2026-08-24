from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "company-os"
SCRIPT = SKILL / "scripts" / "validate_riocl_tc_packet.py"
EXAMPLE = SKILL / "assets" / "riocl-tc-packet.example.json"
PLAYBOOK = SKILL / "references" / "riocl-tc.md"
SOURCE = SKILL / "references" / "source" / "riocl-tc-master-algorithm.txt"
SPEC = importlib.util.spec_from_file_location("validate_riocl_tc_packet", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def example_packet() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class RioclTcPacketTests(unittest.TestCase):
    def test_example_packet_validates(self) -> None:
        self.assertEqual([], MODULE.validate_packet(example_packet()))

    def test_cli_accepts_example(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(EXAMPLE)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual([], payload["errors"])

    def test_source_algorithm_and_playbook_are_present(self) -> None:
        self.assertGreater(SOURCE.stat().st_size, 0)
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertIn("does not own", text.casefold())
        self.assertIn("seventh primary loop", text)
        self.assertIn("company-os.riocl-tc-packet.v1", text)
        self.assertIn("observe", text)

    def test_unknown_keys_fail_closed(self) -> None:
        packet = example_packet()
        packet["orchestrator"] = True
        self.assertIn("unknown keys: orchestrator", MODULE.validate_packet(packet))

    def test_loop_field_is_rejected(self) -> None:
        packet = example_packet()
        packet["loop"] = {"primary": "riocl-tc-loop", "activation_state": "active"}
        self.assertIn("unknown keys: loop", MODULE.validate_packet(packet))

    def test_authority_cannot_become_orchestrator(self) -> None:
        packet = example_packet()
        packet["authority"] = "orchestrator"
        self.assertIn("authority must be overlay", MODULE.validate_packet(packet))

    def test_more_than_two_constraints_fail(self) -> None:
        packet = example_packet()
        packet["constraints"] = ["budget", "requirements", "taste"]
        self.assertIn("constraints must contain 1 to 2 items", MODULE.validate_packet(packet))

    def test_missing_bottleneck_fails(self) -> None:
        packet = example_packet()
        packet["bottleneck"] = " "
        self.assertIn("bottleneck must be a non-empty string", MODULE.validate_packet(packet))

    def test_forbidden_next_action_fails(self) -> None:
        packet = example_packet()
        for action in (
            "launch_runtime",
            "enable_scheduler",
            "complete_from_narrative",
            "run_riocl_tc",
        ):
            with self.subTest(action=action):
                mutated = copy.deepcopy(packet)
                mutated["next_action"] = action
                errors = MODULE.validate_packet(mutated)
                self.assertTrue(any("next_action" in item for item in errors))

    def test_next_action_must_match_decision_mode(self) -> None:
        packet = example_packet()
        packet["next_action"] = "observe"
        self.assertIn("next_action does not match decision_mode", MODULE.validate_packet(packet))

    def test_exploration_forbids_leverage(self) -> None:
        packet = example_packet()
        packet["regime"] = "exploration"
        self.assertIn(
            "exploration regime forbids leverage and redesign",
            MODULE.validate_packet(packet),
        )

    def test_non_survivable_downside_forbids_leverage(self) -> None:
        packet = example_packet()
        packet["survivable"] = False
        self.assertIn(
            "non-survivable downside forbids leverage and redesign",
            MODULE.validate_packet(packet),
        )

    def test_irreversible_context_stays_a_test(self) -> None:
        packet = example_packet()
        packet["reversibility"] = "irreversible"
        packet["decision_mode"] = "test"
        packet["next_action"] = "close_outcome_discovery"
        packet["leverage_candidates"] = []
        self.assertEqual([], MODULE.validate_packet(packet))
        packet["decision_mode"] = "execute_leverage"
        packet["next_action"] = "force_first_execution"
        packet["leverage_candidates"] = ["ship the irreversible cutover"]
        errors = MODULE.validate_packet(packet)
        self.assertTrue(any("irreversible" in item for item in errors))

    def test_do_nothing_maps_to_observe(self) -> None:
        packet = example_packet()
        packet["decision_mode"] = "do_nothing"
        packet["next_action"] = "observe"
        packet["leverage_candidates"] = []
        self.assertEqual([], MODULE.validate_packet(packet))

    def test_company_os_points_at_riocl_as_default_optimizer(self) -> None:
        text = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
        self.assertIn("company-os.riocl-tc-packet.v1", text)
        self.assertIn("references/riocl-tc.md", text)
        self.assertIn("default bottleneck-optimization overlay", text)

    def test_governor_and_navigation_load_the_overlay(self) -> None:
        paths = (
            ROOT / "skills/company-os/govern-outcome-execution/SKILL.md",
            ROOT / "skills/company-os/navigation-control/SKILL.md",
            ROOT / "skills/company-os/operational-control/SKILL.md",
            ROOT / "skills/company-os/select-execution-loop/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertIn("riocl-tc", text)
                self.assertIn("overlay", text.casefold())

    def test_role_skills_do_not_own_the_algorithm(self) -> None:
        manager = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        worker = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("riocl-tc", manager)
        self.assertNotIn("riocl-tc", worker)


if __name__ == "__main__":
    unittest.main()
