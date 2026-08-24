from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/select-execution-loop/scripts/select_execution_loop.py"
SPEC = importlib.util.spec_from_file_location("select_execution_loop", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def request(**overrides):
    value = {
        "schema": "company-os.loop-selection-request.v1",
        "outcome_id": "deliver-customer-portal",
        "task_family": "general",
        "evidence": {
            "acceptance_oracle": True,
            "objective_metric": True,
            "production_traces": False,
            "durable_event_source": False,
        },
        "shape": {
            "parallel_lanes": 1,
            "uncertainty": "medium",
            "recurrence": "one_off",
            "failure_cost": "medium",
            "novelty_need": "medium",
            "code_mutation": False,
        },
        "limits": {
            "max_passes": 6,
            "no_progress_limit": 2,
            "max_concurrency": 1,
            "max_depth": 0,
            "max_cost_usd": None,
        },
        "requirements": {
            "independent_review": True,
            "worktree_isolation": False,
            "post_run_learning": False,
            "approval_boundaries": ["production-write"],
        },
    }
    for key, nested in overrides.items():
        if isinstance(nested, dict):
            value[key].update(nested)
        else:
            value[key] = nested
    return value


class ExecutionLoopSelectorTests(unittest.TestCase):
    def select(self, raw):
        validated = MODULE.validate_request(raw)
        return MODULE.select_plan(validated, MODULE.load_catalog())

    def test_general_work_uses_bounded_evidence_loop(self):
        plan = self.select(request())
        self.assertEqual(plan["primary"]["id"], "bounded-evidence-loop")
        self.assertEqual(plan["activation_state"], "planned")
        self.assertIn("stagnated", plan["terminal_states"])

    def test_recurring_parallel_software_keeps_scheduler_controls(self):
        plan = self.select(request(
            task_family="software_delivery",
            shape={"parallel_lanes": 16, "code_mutation": True, "recurrence": "recurring"},
            limits={"max_concurrency": 4, "max_depth": 2},
            requirements={"worktree_isolation": True},
        ))
        self.assertEqual(plan["primary"]["id"], "recurring-operations-loop")
        for control in (
            "scheduler admission",
            "frequency guard",
            "lease and heartbeat",
            "missed-run reconciliation",
        ):
            self.assertIn(control, plan["required_controls"])

    def test_parallel_code_uses_recursive_worktrees(self):
        plan = self.select(request(
            task_family="software_delivery",
            shape={"parallel_lanes": 12, "code_mutation": True},
            limits={"max_concurrency": 4, "max_depth": 2},
            requirements={"worktree_isolation": True},
        ))
        self.assertEqual(plan["primary"]["id"], "recursive-worktree-loop")
        self.assertIn("path ownership", plan["required_controls"])
        self.assertEqual(plan["limits"]["max_concurrency"], 4)

    def test_event_driven_work_uses_fenced_reaction_loop(self):
        plan = self.select(request(
            task_family="operations",
            evidence={"durable_event_source": True},
            shape={"recurrence": "event_driven"},
        ))
        self.assertEqual(plan["primary"]["id"], "event-reaction-loop")
        self.assertNotIn("durable-event-transport-adapter", [item["id"] for item in plan["adapters"]])
        self.assertIn("generation fencing", plan["required_controls"])

    def test_creative_work_uses_finite_divergent_exploration(self):
        plan = self.select(request(
            task_family="creative_exploration",
            shape={"parallel_lanes": 8, "novelty_need": "high"},
            limits={"max_concurrency": 4},
        ))
        self.assertEqual(plan["primary"]["id"], "bounded-divergent-exploration-loop")
        self.assertIn("held-out acceptance", plan["required_controls"])

    def test_trace_and_learning_are_adapters_not_competing_primaries(self):
        plan = self.select(request(
            task_family="optimization",
            evidence={"production_traces": True, "durable_event_source": True},
            requirements={"post_run_learning": True},
        ))
        self.assertEqual(plan["primary"]["id"], "bounded-evidence-loop")
        self.assertEqual(
            [item["id"] for item in plan["adapters"]],
            ["trace-optimization-adapter", "apprenticeship-learning-adapter", "durable-event-transport-adapter"],
        )

    def test_unsafe_or_unmeasurable_requests_fail_closed(self):
        cases = [
            request(evidence={"acceptance_oracle": False}),
            request(shape={"failure_cost": "high"}, requirements={"independent_review": False}),
            request(
                task_family="software_delivery",
                shape={"parallel_lanes": 2, "code_mutation": True},
                limits={"max_concurrency": 2},
            ),
            request(
                task_family="software_delivery",
                shape={"parallel_lanes": 2, "code_mutation": True},
                limits={"max_concurrency": 2, "max_depth": 0},
                requirements={"worktree_isolation": True},
            ),
            request(shape={"recurrence": "event_driven"}),
            request(limits={"max_passes": 2, "no_progress_limit": 3}),
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(MODULE.SelectionError):
                    MODULE.validate_request(case)

    def test_cli_output_is_canonical_and_verifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            output_path = root / "plan.json"
            request_path.write_text(json.dumps(request()), encoding="utf-8")
            first = subprocess.run(
                [sys.executable, str(SCRIPT), str(request_path), "--output", str(output_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            verification = subprocess.run(
                [sys.executable, str(SCRIPT), str(request_path), "--verify-output", str(output_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(verification.returncode, 0, verification.stderr)
            parsed = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(output_path.read_bytes(), MODULE.canonical_bytes(parsed))
            output_path.write_text("{}\n", encoding="utf-8")
            drift = subprocess.run(
                [sys.executable, str(SCRIPT), str(request_path), "--verify-output", str(output_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(drift.returncode, 2)

    def test_catalog_preserves_pinned_source_provenance(self):
        source = (SCRIPT.parent.parent / "references/source-essence.md").read_text(encoding="utf-8")
        for commit in (
            "75966cbd572a4185064971c9fe5e9c52e8f8456d",
            "0b68141633c14f488461aaecdf91a739a411f05d",
            "73ce05adcd73d52c69afb394447d7ab95880d321",
            "463b642a5c6e314d4abccf66e3950aa5b3e70c8d",
            "32f80926ac11ae514342401c6eeaae1fb860656a",
            "6e9a012f81ef2291faf174d67176f7e69832cc0a",
            "4beafff2ff41da7d97a4faee9b516ccde466fb4b",
            "a172acc389351cb3db6deb5cd60e3dec11e7ff39",
        ):
            self.assertIn(commit, source)


if __name__ == "__main__":
    unittest.main()
