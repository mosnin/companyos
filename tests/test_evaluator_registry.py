from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/register-outcome-evaluators/scripts/register_outcome_evaluators.py"
spec = importlib.util.spec_from_file_location("register_outcome_evaluators_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


class EvaluatorRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.adapter = self.project / ".company-os/evaluators/gameplay/adapter.py"
        self.adapter.parent.mkdir(parents=True, exist_ok=True)
        self.adapter.write_text("#!/usr/bin/env python3\nprint('{}')\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def contract(self, locator: str = "workspace://.company-os/evaluators/gameplay/adapter.py") -> dict:
        contract = {
            "$schema": MODULE.CONTRACT_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "evaluators": [
                {
                    "evaluator_id": "gameplay",
                    "label": "Gameplay evaluator",
                    "required": True,
                    "independent_role": True,
                    "research_only": False,
                    "adapter_locator": locator,
                    "artifact_classes": ["playable_game"],
                    "produces_evidence": ["interaction_trace", "screenshot"],
                    "score_dimensions": ["gameplay", "visual_quality"],
                }
            ],
            "blockers": [],
            "ready": True,
            "contract_sha256": None,
        }
        contract["contract_sha256"] = MODULE.digest({**contract, "contract_sha256": None})
        return contract

    def test_required_adapter_bytes_register_and_resolve(self) -> None:
        registry = MODULE.build_registry(self.project, self.contract())
        self.assertEqual(registry["$schema"], MODULE.REGISTRY_SCHEMA)
        self.assertEqual(len(registry["adapters"]), 1)
        adapter = registry["adapters"][0]
        self.assertEqual(adapter["entrypoint"], ".company-os/evaluators/gameplay/adapter.py")
        self.assertEqual(adapter["entrypoint_sha256"], MODULE.file_digest(self.adapter))
        self.assertEqual(adapter["produces_evidence"], ["interaction_trace", "screenshot"])
        self.assertEqual(
            registry["registry_sha256"],
            MODULE.digest({**registry, "registry_sha256": None}),
        )

    def test_missing_adapter_is_capability_failure(self) -> None:
        self.adapter.unlink()
        with self.assertRaises(MODULE.RegistryError) as caught:
            MODULE.build_registry(self.project, self.contract())
        self.assertEqual(caught.exception.code, "E_ADAPTER_MISSING")

    def test_non_workspace_locator_is_not_silently_accepted(self) -> None:
        with self.assertRaises(MODULE.RegistryError) as caught:
            MODULE.build_registry(self.project, self.contract("tool://browser-judge"))
        self.assertEqual(caught.exception.code, "E_LOCATOR")

    def test_adapter_digest_changes_when_bytes_change(self) -> None:
        first = MODULE.build_registry(self.project, self.contract())
        self.adapter.write_text("#!/usr/bin/env python3\nprint('{\"changed\":true}')\n", encoding="utf-8")
        second = MODULE.build_registry(self.project, self.contract())
        self.assertNotEqual(
            first["adapters"][0]["entrypoint_sha256"],
            second["adapters"][0]["entrypoint_sha256"],
        )
        self.assertNotEqual(first["registry_sha256"], second["registry_sha256"])


if __name__ == "__main__":
    unittest.main()
