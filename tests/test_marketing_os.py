from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "marketing-os"
SCRIPT = SKILL / "scripts" / "validate_marketing_os.py"
COMPILER_PATH = ROOT / "skills/company-os/company-blueprint/scripts/compile_company_blueprint.py"
EXAMPLE = ROOT / "skills/company-os/company-blueprint/assets/company-blueprint.example.json"
SPEC = importlib.util.spec_from_file_location("validate_marketing_os", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMPILER_SPEC = importlib.util.spec_from_file_location(
    "company_blueprint_compiler_marketing_os", COMPILER_PATH
)
assert COMPILER_SPEC and COMPILER_SPEC.loader
COMPILER = importlib.util.module_from_spec(COMPILER_SPEC)
COMPILER_SPEC.loader.exec_module(COMPILER)


class MarketingOsTests(unittest.TestCase):
    def test_pack_and_spawn_template_validate(self) -> None:
        self.assertEqual([], MODULE.validate_pack(SKILL))

    def test_cli_accepts_canonical_pack(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(SKILL)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual([], payload["errors"])

    def test_source_pack_refuses_orchestrator_and_copies(self) -> None:
        index = (SKILL / "references/source/00-index.txt").read_text(encoding="utf-8")
        self.assertIn("not a copy of that repository", index.casefold())
        self.assertIn("research → brief → copy", index)
        pipeline = " ".join(
            (SKILL / "references/source/01-pipeline.txt").read_text(encoding="utf-8").split()
        )
        self.assertIn("Do not spawn a router agent", pipeline)
        self.assertIn("Routing is the playbook", pipeline)
        scale = " ".join(
            (SKILL / "references/source/03-scale.txt").read_text(encoding="utf-8").split()
        )
        self.assertIn("work-graph width", scale)
        self.assertIn("Do not stand up a second operating system", scale)
        quality = (SKILL / "references/source/05-quality-and-authority.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("qualified demand", quality.casefold())
        self.assertNotIn("MOS-Orchestrator", index)
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("always-on", skill.casefold())

    def test_example_artifacts_are_digest_bound(self) -> None:
        audience = json.loads((SKILL / "assets/examples/audience-profile.json").read_text())
        brief = json.loads((SKILL / "assets/examples/campaign-brief.json").read_text())
        copy = json.loads((SKILL / "assets/examples/copy-packet.json").read_text())
        self.assertEqual([], MODULE.validate_audience_profile(audience))
        self.assertEqual([], MODULE.validate_campaign_brief(brief))
        self.assertEqual([], MODULE.validate_copy_packet(copy))
        self.assertEqual(
            MODULE.digest_bytes(MODULE.canonical_bytes(audience)),
            brief["audience_profile_digest"],
        )
        self.assertEqual(
            MODULE.digest_bytes(MODULE.canonical_bytes(brief)),
            copy["brief_digest"],
        )
        drifted = dict(copy)
        drifted["brief_digest"] = "0" * 64
        self.assertEqual([], MODULE.validate_copy_packet(drifted))
        self.assertNotEqual(
            drifted["brief_digest"],
            MODULE.digest_bytes(MODULE.canonical_bytes(brief)),
        )
        awareness = dict(brief)
        awareness["goal"] = "Build awareness in the category"
        self.assertIn(
            "campaign-brief.goal must not use awareness as the object",
            MODULE.validate_campaign_brief(awareness),
        )

    def test_spawn_template_rejects_worker_or_master_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        for role in ("master", "worker"):
            with self.subTest(role=role):
                mutated = dict(template)
                mutated["role"] = role
                self.assertIn("spawn role must be manager", MODULE.validate_spawn_template(mutated))

    def test_marketing_lanes_point_at_marketing_os(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/company-blueprint/SKILL.md",
            ROOT / "skills/company-os/department-charters/SKILL.md",
            ROOT / "skills/company-os/corporate-departments/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("$marketing-os", path.read_text(encoding="utf-8"))

    def test_company_os_does_not_send_marketing_os_to_workers(self) -> None:
        text = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "When compiling Marketing, also send `$marketing-os` to that department manager.",
            text,
        )
        self.assertIn("Do not send `$marketing-os` to workers", text)

    def test_general_manager_and_worker_skills_do_not_require_marketing_os(self) -> None:
        manager = (ROOT / "skills/company-os/manage-company-program/SKILL.md").read_text()
        worker = (ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md").read_text()
        fabric = (
            ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md"
        ).read_text()
        self.assertNotIn("$marketing-os", manager)
        self.assertNotIn("$marketing-os", worker)
        self.assertNotIn("$marketing-os", fabric)

    def test_host_bindings_stay_explicit_and_lane_bound(self) -> None:
        for name in ("openai.yaml", "grok.yaml", "claude.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$marketing-os", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn("allow_implicit_invocation: false", text)
            short = [
                line.split(":", 1)[1].strip().strip('"')
                for line in text.splitlines()
                if line.strip().startswith("short_description:")
            ][0]
            self.assertTrue(25 <= len(short) <= 64, short)

    def test_software_company_compiles_scaled_marketing_slots(self) -> None:
        blueprint = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "blueprint.json"
            path.write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
            COMPILER.compile_blueprint(path, root / "compiled")
            organization = json.loads((root / "compiled/organization.json").read_text())
            marketing = next(item for item in organization["departments"] if item["id"] == "marketing")
            slot_ids = [slot["id"] for slot in marketing["agent_slots"]]
            self.assertEqual(
                [
                    "marketing-manager",
                    "marketing-campaign-manager",
                    "marketing-research-worker",
                    "marketing-brief-worker",
                    "marketing-copy-worker",
                ],
                slot_ids,
            )
            self.assertEqual("low_level", marketing["agent_slots"][1]["management_tier"])
            self.assertIn("marketing-os", marketing["skills"])
            self.assertIn("campaign-brief", marketing["playbooks"])
            registry = json.loads((root / "compiled/agent-registry.json").read_text())
            self.assertEqual(27, len(registry["slots"]))
            self.assertEqual("templates-not-running-agents", registry["activation_policy"])


if __name__ == "__main__":
    unittest.main()
