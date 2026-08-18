from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "corporate-departments"
SCRIPT = SKILL / "scripts" / "validate_corporate_departments.py"
COMPILER_PATH = ROOT / "skills/company-os/company-blueprint/scripts/compile_company_blueprint.py"
EXAMPLE = ROOT / "skills/company-os/company-blueprint/assets/company-blueprint.example.json"
SPEC = importlib.util.spec_from_file_location("validate_corporate_departments", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMPILER_SPEC = importlib.util.spec_from_file_location(
    "company_blueprint_compiler_departments", COMPILER_PATH
)
assert COMPILER_SPEC and COMPILER_SPEC.loader
COMPILER = importlib.util.module_from_spec(COMPILER_SPEC)
COMPILER_SPEC.loader.exec_module(COMPILER)


class CorporateDepartmentsTests(unittest.TestCase):
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

    def test_source_pack_has_department_doctrine(self) -> None:
        names = sorted(
            path.name
            for path in (SKILL / "references/source").iterdir()
            if path.is_file()
        )
        self.assertEqual(len(names), 9)
        self.assertIn("01-issue-trees.txt", names)
        self.assertIn("08-preset-departments.txt", names)
        issue_trees = " ".join(
            (SKILL / "references/source/01-issue-trees.txt")
            .read_text(encoding="utf-8")
            .split()
        )
        self.assertIn("mutually exclusive and collectively exhaustive", issue_trees)
        self.assertIn("kill rule", issue_trees)
        mapping = " ".join(
            (SKILL / "references/source/08-preset-departments.txt")
            .read_text(encoding="utf-8")
            .split()
        )
        self.assertIn("marketing: demand generation", mapping)
        self.assertIn("sales: qualification", mapping)
        self.assertIn("human-resources:", mapping)
        self.assertIn("Do not restore a combined commercial-growth", mapping)
        identity = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("not a claim of personal identity", identity)
        self.assertIn("McKinsey", identity)
        self.assertIn("original compiled operating template", identity)

    def test_spawn_template_is_department_lane_specific(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["use_when"], list(MODULE.USE_WHEN))
        mutated = dict(template)
        mutated["use_when"] = ["general_management"]
        self.assertIn(
            "use_when must be the corporate-departments lanes",
            MODULE.validate_spawn_template(mutated),
        )

    def test_spawn_template_rejects_worker_or_master_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        for role in ("master", "worker"):
            with self.subTest(role=role):
                mutated = dict(template)
                mutated["role"] = role
                self.assertIn("spawn role must be manager", MODULE.validate_spawn_template(mutated))

    def test_organization_lanes_point_at_corporate_departments(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/company-blueprint/SKILL.md",
            ROOT / "skills/company-os/department-charters/SKILL.md",
            ROOT / "skills/company-os/corporate-management/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("$corporate-departments", path.read_text(encoding="utf-8"))

    def test_company_os_does_not_send_corporate_departments_to_workers(self) -> None:
        text = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "When compiling named departments, also send `$corporate-departments` to the department manager.",
            text,
        )
        self.assertIn("Do not send `$corporate-departments` to workers", text)

    def test_general_manager_and_worker_skills_do_not_require_corporate_departments(self) -> None:
        manager = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        worker = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        fabric = (
            ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$corporate-departments", manager)
        self.assertNotIn("$corporate-departments", worker)
        self.assertNotIn("$corporate-departments", fabric)

    def test_host_bindings_stay_explicit_and_lane_bound(self) -> None:
        for name in ("openai.yaml", "grok.yaml", "claude.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$corporate-departments", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn("named department", text)
            self.assertIn("allow_implicit_invocation: false", text)
            short = [
                line.split(":", 1)[1].strip().strip('"')
                for line in text.splitlines()
                if line.strip().startswith("short_description:")
            ][0]
            self.assertTrue(25 <= len(short) <= 64, short)

    def test_preset_catalog_is_a_corporate_company(self) -> None:
        catalog = json.loads(
            (
                ROOT / "skills/company-os/company-blueprint/assets/department-packs.json"
            ).read_text(encoding="utf-8")
        )
        departments = COMPILER.validate_department_catalog(catalog)
        self.assertEqual(
            [
                "brand-creative",
                "customer-success",
                "engineering-quality",
                "executive-strategy",
                "finance",
                "human-resources",
                "marketing",
                "operations",
                "product",
                "program-management",
                "sales",
                "security-compliance",
            ],
            sorted(departments),
        )
        self.assertNotIn("commercial-growth", departments)
        self.assertIn("demand-generation", departments["marketing"]["capabilities"])
        self.assertIn("revenue-growth", departments["sales"]["capabilities"])
        self.assertNotIn("revenue-growth", departments["marketing"]["capabilities"])
        self.assertIn("hiring", departments["human-resources"]["capabilities"])
        for department in departments.values():
            self.assertIn("corporate-departments", department["skills"])
            manager = next(slot for slot in department["agent_slots"] if slot["role"] == "manager")
            self.assertIn("corporate-departments", manager["skills"])

    def test_software_company_compiles_the_full_corporate_set(self) -> None:
        blueprint = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "blueprint.json"
            path.write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
            COMPILER.compile_blueprint(path, root / "compiled")
            organization = json.loads((root / "compiled/organization.json").read_text())
            department_ids = {item["id"] for item in organization["departments"]}
            self.assertEqual(12, organization["department_count"])
            self.assertEqual(
                {
                    "brand-creative",
                    "customer-success",
                    "engineering-quality",
                    "executive-strategy",
                    "finance",
                    "human-resources",
                    "marketing",
                    "operations",
                    "product",
                    "program-management",
                    "sales",
                    "security-compliance",
                },
                department_ids,
            )
            registry = json.loads((root / "compiled/agent-registry.json").read_text())
            self.assertEqual(24, len(registry["slots"]))

    def test_revenue_growth_selects_sales_not_a_combined_commercial_pack(self) -> None:
        blueprint = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        blueprint["company_id"] = "harbor-services"
        blueprint["operating_model"] = {
            "archetypes": ["professional-services"],
            "department_overrides": [],
            "requested_capabilities": ["revenue-growth"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "blueprint.json"
            path.write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
            COMPILER.compile_blueprint(path, root / "compiled")
            organization = json.loads((root / "compiled/organization.json").read_text())
            department_ids = {item["id"] for item in organization["departments"]}
            self.assertIn("sales", department_ids)
            self.assertNotIn("marketing", department_ids)
            self.assertNotIn("commercial-growth", department_ids)


if __name__ == "__main__":
    unittest.main()
