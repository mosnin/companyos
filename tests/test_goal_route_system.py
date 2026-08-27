from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/goal-route-system/scripts/goal_route.py"
spec = importlib.util.spec_from_file_location("company_os_goal_route", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class GoalRouteSystemTests(unittest.TestCase):
    def compile(self, objective: str, objective_id: str = "test"):
        return MODULE.compile_goal_route(
            objective_id,
            objective,
            mission_class="company_mission",
            autonomy_mode="autonomous_research",
        )

    def test_software_route_has_goal_at_every_organizational_level(self):
        route = self.compile("Build a complete multi company AI support SaaS with widget, inbox, billing, security, and reliability.")
        levels = {goal["owner"]["goal_level"] for goal in route["goals"]}
        self.assertEqual(levels, {"company", "manager", "submanager", "worker"})
        self.assertEqual(len(route["route_segments"]), 6)
        self.assertEqual(len(route["sprints"]), 6)
        self.assertTrue(route["active_goal_ids"])
        for goal in route["goals"]:
            self.assertTrue(goal["goal_sha256"])
            self.assertTrue(goal["tasks"])
            self.assertTrue(goal["tasks"][0]["subtasks"])
            self.assertEqual(goal["cohesion_sha256"], route["cohesion_contract"]["cohesion_sha256"])
            if goal["parent_goal_id"] is not None:
                self.assertTrue(goal["contributes_to"])
                self.assertTrue(goal["parent_goal_sha256"])

    def test_consumer_company_route_preserves_cross_functional_cohesion(self):
        route = self.compile("Autonomously build an entire differentiated yoga leggings company with brand, product, supply chain, commerce, growth, operations, and launch readiness.", "leggings")
        manager_types = {goal["goal_type"] for goal in route["goals"] if goal["owner"]["goal_level"] == "manager"}
        self.assertTrue({"market_position", "brand_system", "product_system", "supply_chain", "commerce_experience", "growth_distribution", "company_operations", "launch_acceptance"}.issubset(manager_types))
        self.assertEqual(route["kickoff_profile"]["autonomy_mode"], "autonomous_research")
        self.assertTrue(route["kickoff_profile"]["assumptions"])

    def test_marketing_route_reverse_engineers_revenue_target(self):
        route = self.compile("Create a marketing system that reaches $100,000 a month in sales by reverse engineering the offer, funnel, channels, creative, conversion, and retention.", "revenue")
        root = MODULE.goal_by_id(route, route["root_goal_id"])
        revenue = next(item for item in root["success_metrics"] if item["metric_id"] == "monthly_revenue")
        self.assertEqual(revenue["target"], 100000.0)
        commercial = next(goal for goal in route["goals"] if goal["goal_type"] == "commercial_model")
        self.assertIn("revenue equation", commercial["target_state"]["conditions"])

    def test_child_goals_cover_parent_conditions_and_fit_budget(self):
        route = self.compile("Build a software application with a working user journey.")
        goals = {goal["goal_id"]: goal for goal in route["goals"]}
        for parent in route["goals"]:
            children = [goal for goal in route["goals"] if goal["parent_goal_id"] == parent["goal_id"]]
            if not children:
                continue
            required = {item["state_change_id"] for item in parent["required_state_changes"]}
            covered = {condition for child in children for condition in child["contributes_to"]}
            self.assertTrue(required.issubset(covered))
            for field in ("time_minutes", "token_limit", "cost_usd"):
                self.assertLessEqual(sum(child["budget"][field] for child in children), parent["budget"][field] + 1e-6)
            for child in children:
                self.assertEqual(child["parent_goal_sha256"], goals[parent["goal_id"]]["goal_sha256"])

    def test_lane_assignment_binds_manager_worker_sprint_template_and_cohesion(self):
        route = self.compile("Build a complete software platform with a real browser journey.")
        assignment = MODULE.assignment_for_lane(
            route,
            artifact_classes=["first-real-product"],
            phase="build_candidate",
            lane_id="artifact:first-real-product",
            manager_id="manager-1",
            worker_id="worker-1",
        )
        self.assertEqual(assignment["manager_id"], "manager-1")
        self.assertEqual(assignment["worker_id"], "worker-1")
        self.assertEqual(assignment["worker_goal"]["owner"]["goal_level"], "worker")
        self.assertEqual(assignment["manager_goal"]["owner"]["goal_level"], "manager")
        self.assertEqual(assignment["cohesion_contract"]["cohesion_sha256"], route["cohesion_contract"]["cohesion_sha256"])
        self.assertEqual(len(assignment["assignment_sha256"]), 64)

    def test_worker_evidence_rolls_up_to_submanager(self):
        route = self.compile("Build a software application with a real user journey.")
        worker = next(goal for goal in route["goals"] if goal["owner"]["goal_level"] == "worker")
        updated = MODULE.record_evidence(
            route,
            goal_id=worker["goal_id"],
            evidence_type="artifact_manifest",
            path="evidence/worker.json",
            sha256="a" * 64,
            progress_state="accepted",
        )
        accepted_worker = MODULE.goal_by_id(updated, worker["goal_id"])
        accepted_parent = MODULE.goal_by_id(updated, worker["parent_goal_id"])
        self.assertEqual(accepted_worker["status"], "accepted")
        self.assertEqual(accepted_parent["status"], "accepted")

    def test_reroute_preserves_root_goal_and_issues_takeover_packet(self):
        route = self.compile("Build a software application with a real user journey.")
        worker = next(goal for goal in route["goals"] if goal["owner"]["goal_level"] == "worker")
        original_root = route["root_goal_sha256"]
        updated = MODULE.reroute(
            route,
            blocked_goal_id=worker["goal_id"],
            replacement_owner_id="replacement-worker",
            reason="The first method stalled without runtime movement.",
            failed_strategy="Repeat the same implementation.",
            new_strategy="Use the alternate existing integration.",
        )
        self.assertEqual(updated["root_goal_sha256"], original_root)
        self.assertEqual(updated["route_version"], 2)
        self.assertEqual(MODULE.goal_by_id(updated, worker["goal_id"])["owner"]["owner_id"], "replacement-worker")
        self.assertEqual(updated["takeover_packets"][-1]["failed_strategy"], "Repeat the same implementation.")

    def test_authority_widening_is_rejected(self):
        route = self.compile("Build a software application with a real user journey.")
        child = next(goal for goal in route["goals"] if goal["parent_goal_id"] is not None)
        for goal in route["goals"]:
            if goal["goal_id"] == child["goal_id"]:
                goal["authority"]["effects"].append("production")
                goal["goal_sha256"] = None
                goal.update(MODULE.seal(goal, "goal_sha256"))
                break
        route["state_sha256"] = None
        route = MODULE.seal(route, "state_sha256")
        with self.assertRaises(MODULE.GoalRouteError) as caught:
            MODULE.verify_state(route)
        self.assertEqual(caught.exception.code, "E_AUTHORITY")

    def test_cohesion_drift_is_rejected(self):
        route = self.compile("Build a software application with a real user journey.")
        child = next(goal for goal in route["goals"] if goal["parent_goal_id"] is not None)
        for goal in route["goals"]:
            if goal["goal_id"] == child["goal_id"]:
                goal["cohesion_sha256"] = "b" * 64
                goal["goal_sha256"] = None
                goal.update(MODULE.seal(goal, "goal_sha256"))
                break
        route["state_sha256"] = None
        route = MODULE.seal(route, "state_sha256")
        with self.assertRaises(MODULE.GoalRouteError) as caught:
            MODULE.verify_state(route)
        self.assertEqual(caught.exception.code, "E_COHESION")


if __name__ == "__main__":
    unittest.main()
