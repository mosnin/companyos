from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
spec = importlib.util.spec_from_file_location("reality_spike_ingestion", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class RealitySpikeIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        product = self.root / "src/app.html"
        runtime = self.root / ".company-os/spike/runtime.json"
        journey = self.root / ".company-os/spike/journey.json"
        product.parent.mkdir(parents=True)
        runtime.parent.mkdir(parents=True)
        product.write_text("<button>Working</button>\n", encoding="utf-8")
        runtime.write_text('{"rendered":true}\n', encoding="utf-8")
        journey.write_text('{"clicked":true}\n', encoding="utf-8")
        receipt = {
            "$schema": MODULE.REALITY_SPIKE_SCHEMA,
            "objective_id": "website",
            "completed_at": "2026-08-11T12:10:00Z",
            "artifacts": [
                {
                    "capability_id": "first_real_artifact",
                    "path": "src/app.html",
                    "sha256": MODULE.file_digest(product),
                }
            ],
            "commands": [
                {"command": "run browser preview", "exit_code": 0}
            ],
            "observations": [
                {
                    "capability_id": "first_real_artifact",
                    "kind": "runtime_observed",
                    "observation_kind": "browser",
                    "path": ".company-os/spike/runtime.json",
                    "sha256": MODULE.file_digest(runtime),
                },
                {
                    "capability_id": "first_real_artifact",
                    "kind": "journey_connected",
                    "observation_kind": "browser_interaction",
                    "path": ".company-os/spike/journey.json",
                    "sha256": MODULE.file_digest(journey),
                },
            ],
            "blockers": [],
            "receipt_sha256": None,
        }
        receipt["receipt_sha256"] = MODULE.digest(receipt)
        self.receipt = receipt

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_spike_requires_real_bound_bytes(self) -> None:
        tampered = json.loads(json.dumps(self.receipt))
        tampered["artifacts"][0]["sha256"] = "0" * 64
        tampered["receipt_sha256"] = None
        tampered["receipt_sha256"] = MODULE.digest(tampered)
        with self.assertRaises(MODULE.MissionControlError) as caught:
            MODULE.verify_reality_spike(self.root, tampered, objective_id="website")
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_spike_advances_provisional_capability_from_artifact_to_connected(self) -> None:
        state = MODULE.initialize_state(
            "website",
            "Build a website",
            started_at="2026-08-11T12:00:00Z",
            mission_class="quick_build",
            duration_minutes=90,
        )
        updated = MODULE.ingest_reality_spike(state, self.root, self.receipt)
        by_id = {item["capability_id"]: item for item in updated["capabilities"]}
        self.assertEqual(by_id["first_real_artifact"]["state"], "connected")
        self.assertTrue(updated["events"])

    def test_scope_compilation_preserves_spike_progress(self) -> None:
        state = MODULE.initialize_state(
            "website",
            "Build a website",
            started_at="2026-08-11T12:00:00Z",
            mission_class="quick_build",
            duration_minutes=90,
        )
        updated = MODULE.ingest_reality_spike(state, self.root, self.receipt)
        scoped = MODULE.update_scope(
            updated,
            {
                "$schema": "company-os.artifact-observation-contract.v1",
                "artifact_classes": [
                    {
                        "artifact_class_id": "browser_interface",
                        "label": "Browser interface",
                        "required": True,
                        "modalities": ["interactive", "ui"],
                        "observation_methods": ["browser"],
                    },
                    {
                        "artifact_class_id": "billing",
                        "label": "Billing",
                        "required": True,
                        "modalities": ["service"],
                        "observation_methods": ["api"],
                    },
                ],
            },
        )
        by_id = {item["capability_id"]: item for item in scoped["capabilities"]}
        first_id = scoped["first_reality"]["required_capability_ids"][0]
        self.assertEqual(by_id[first_id]["state"], "connected")
        self.assertTrue(by_id[first_id]["evidence"])


if __name__ == "__main__":
    unittest.main()
