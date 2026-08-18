from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "company-context-ledger"
SCRIPT = SKILL / "scripts" / "validate_company_context_ledger.py"


class CompanyContextLedgerTests(unittest.TestCase):
    def test_pack_and_spawn_template_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(SKILL)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"], payload["errors"])
        self.assertEqual([], payload["errors"])

    def test_source_pack_names_the_boundary(self) -> None:
        boundary = (SKILL / "references/source/01-what-it-is.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("not a control plane", boundary.casefold())
        self.assertIn("coming_soon", boundary)
        self.assertIn("one mcp", boundary.casefold())
        connect = (SKILL / "references/source/02-connect-harnesses.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("claude-code", connect)
        self.assertIn("chatgpt-work", connect)
        self.assertIn("config.pull", connect)
        writes = (SKILL / "references/source/03-write-contract.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("expectedRevision", writes)
        self.assertIn("run.append", writes)
        self.assertIn("accept_outcome", writes)

    def test_company_os_points_at_the_ledger_and_not_workers(self) -> None:
        text = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md")
            .read_text(encoding="utf-8")
            .split()
        )
        self.assertIn("$company-context-ledger", text)
        self.assertIn("Do not send `$company-context-ledger` to workers", text)
        self.assertIn("The ledger is not a control plane", text)

    def test_general_manager_and_worker_skills_do_not_require_the_ledger(self) -> None:
        manager = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        worker = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        fabric = (
            ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$company-context-ledger", manager)
        self.assertNotIn("$company-context-ledger", worker)
        self.assertNotIn("$company-context-ledger", fabric)

    def test_host_bindings_stay_explicit(self) -> None:
        for name in ("openai.yaml", "grok.yaml", "claude.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$company-context-ledger", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn("allow_implicit_invocation: false", text)
            short = [
                line.split(":", 1)[1].strip().strip('"')
                for line in text.splitlines()
                if line.strip().startswith("short_description:")
            ][0]
            self.assertTrue(25 <= len(short) <= 64, short)

    def test_spawn_template_rejects_control_roles(self) -> None:
        spec = __import__("importlib.util").util.spec_from_file_location(
            "validate_company_context_ledger", SCRIPT
        )
        module = __import__("importlib.util").util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        template = json.loads(
            (SKILL / "assets/spawn-template.json").read_text(encoding="utf-8")
        )
        for role in ("master", "worker"):
            mutated = dict(template)
            mutated["role"] = role
            self.assertIn(
                "spawn role must be manager", module.validate_spawn_template(mutated)
            )

    def test_companyosweb_stays_out_of_this_repo(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/companyosweb/", ignore)


if __name__ == "__main__":
    unittest.main()
