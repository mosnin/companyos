#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_outcome_control() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/outcome_control.py")
    text = path.read_text(encoding="utf-8")
    marker = '''    _CALIBRATION_MODULE = module
    return module


class OutcomeControlError'''
    replacement = '''    _CALIBRATION_MODULE = module
    return module


_REALITY_MODULE: Any | None = None


def reality_module() -> Any:
    global _REALITY_MODULE
    if _REALITY_MODULE is not None:
        return _REALITY_MODULE
    module_path = (
        Path(__file__).resolve().parents[2]
        / "accept-outcome-reality"
        / "scripts"
        / "accept_reality.py"
    )
    spec = importlib.util.spec_from_file_location(
        "company_os_accept_outcome_reality", module_path
    )
    if spec is None or spec.loader is None:
        raise OutcomeControlError("E_RUNTIME", "reality acceptance runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _REALITY_MODULE = module
    return module


class OutcomeControlError'''
    if text.count(marker) != 1:
        raise SystemExit("reality loader insertion did not match exactly once")
    text = text.replace(marker, replacement, 1)
    start = text.index("def validate_reality_receipt(")
    end = text.index("\ndef find_reality_receipt(", start)
    new_function = '''def validate_reality_receipt(
    project_root: Path,
    receipt: Mapping[str, Any],
    outcome_control: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        verified = reality_module().verify_receipt(project_root, receipt)
    except Exception as exc:
        code = getattr(exc, "code", "E_REALITY")
        raise OutcomeControlError(
            code,
            f"reality receipt failed execution verification: {exc}",
        ) from exc
    if verified.get("accepted") is not True:
        raise OutcomeControlError("E_REALITY", "reality acceptance did not accept the outcome")
    if verified.get("execution_bound") is not True:
        raise OutcomeControlError("E_REALITY", "reality acceptance is not execution bound")
    if verified.get("objective_id") != outcome_control.get("objective_id"):
        raise OutcomeControlError("E_BINDING", "reality acceptance objective_id does not match")
    if receipt.get("original_objective") != outcome_control.get("original_objective"):
        raise OutcomeControlError("E_BINDING", "reality acceptance does not bind the original objective")
    sources = _object_value(receipt.get("source_bindings"), "reality source_bindings")
    expected_sources = {
        "outcome_contract": _object_value(outcome_control.get("outcome"), "outcome control outcome"),
        "artifact_contract": _object_value(outcome_control.get("artifacts"), "outcome control artifacts"),
        "evaluator_contract": _object_value(outcome_control.get("evaluators"), "outcome control evaluators"),
        "benchmark_contract": _object_value(outcome_control.get("benchmarks"), "outcome control benchmarks"),
        "calibration_receipts": _object_value(outcome_control.get("calibrations"), "outcome control calibrations"),
    }
    if set(sources) != set(expected_sources):
        raise OutcomeControlError("E_BINDING", "reality acceptance source bindings are incomplete")
    for source_name, expected in expected_sources.items():
        observed = _object_value(sources.get(source_name), f"reality {source_name}")
        if observed.get("file_sha256") != expected.get("file_sha256"):
            raise OutcomeControlError(
                "E_BINDING", f"reality acceptance does not bind current {source_name}"
            )
    claim_count = verified.get("claim_count")
    if not isinstance(claim_count, int) or isinstance(claim_count, bool) or claim_count < 1:
        raise OutcomeControlError("E_REALITY", "reality acceptance claim count is invalid")
    return {
        "objective_id": verified["objective_id"],
        "receipt_sha256": _sha256(verified.get("receipt_sha256"), "reality receipt_sha256"),
        "claim_count": claim_count,
        "execution_bound": True,
        "candidate_id": verified.get("candidate_id"),
    }
'''
    text = text[:start] + new_function + text[end:]
    old_call = "        validated = validate_reality_receipt(raw, outcome_control)"
    new_call = "        validated = validate_reality_receipt(project_root, raw, outcome_control)"
    if text.count(old_call) != 1:
        raise SystemExit("reality verification call did not match exactly once")
    text = text.replace(old_call, new_call, 1)
    path.write_text(text, encoding="utf-8")


def patch_outcome_control_tests() -> None:
    path = Path("tests/test_outcome_control.py")
    text = path.read_text(encoding="utf-8")
    marker = '''CALIBRATION = load(
    "calibrate_evaluator",
    ROOT / "skills/company-os/calibrate-outcome-evaluator/scripts/calibrate_evaluator.py",
)


def seal'''
    replacement = '''CALIBRATION = load(
    "calibrate_evaluator",
    ROOT / "skills/company-os/calibrate-outcome-evaluator/scripts/calibrate_evaluator.py",
)


class FakeReality:
    @staticmethod
    def verify_receipt(project_root, receipt):
        return {
            "objective_id": receipt.get("objective_id"),
            "candidate_id": receipt.get("candidate_id"),
            "accepted": receipt.get("accepted") is True,
            "execution_bound": receipt.get("execution_bound") is True,
            "claim_count": len(receipt.get("claim_decisions", [])),
            "receipt_sha256": receipt.get("receipt_sha256"),
        }


def seal'''
    if text.count(marker) != 1:
        raise SystemExit("test fake reality insertion did not match")
    text = text.replace(marker, replacement, 1)
    set_marker = '''        self.objective_id = "viral-game"
        self.prepare_contracts_and_calibration()
'''
    set_replacement = '''        self.objective_id = "viral-game"
        CONTROL._REALITY_MODULE = FakeReality
        self.prepare_contracts_and_calibration()
'''
    if text.count(set_marker) != 1:
        raise SystemExit("test setup marker did not match")
    text = text.replace(set_marker, set_replacement, 1)
    tear_marker = '''    def tearDown(self) -> None:
        self.temporary.cleanup()
'''
    tear_replacement = '''    def tearDown(self) -> None:
        CONTROL._REALITY_MODULE = None
        self.temporary.cleanup()
'''
    if text.count(tear_marker) != 1:
        raise SystemExit("test teardown marker did not match")
    text = text.replace(tear_marker, tear_replacement, 1)
    start = text.index("    def reality_receipt(self) -> dict:")
    end = text.index("\n    def test_completion_requires_matching_reality_receipt", start)
    helper = '''    def reality_receipt(self, control: dict) -> dict:
        return seal({
            "$schema": CONTROL.REALITY_SCHEMA,
            "schema_version": 2,
            "execution_bound": True,
            "objective_id": self.objective_id,
            "original_objective": "Make a viral game.",
            "original_objective_sha256": hashlib.sha256(b"Make a viral game.").hexdigest(),
            "candidate_id": "candidate-1",
            "production_actor_ids": ["builder"],
            "production_narrative_admissible": False,
            "source_bindings": {
                "outcome_contract": control["outcome"],
                "artifact_contract": control["artifacts"],
                "evaluator_contract": control["evaluators"],
                "benchmark_contract": control["benchmarks"],
                "calibration_receipts": control["calibrations"],
            },
            "claim_decisions": [{
                "claim_id": "playable",
                "statement": self.governed_outcome,
                "required": True,
                "passed": True,
                "artifact_evidence_count": 2,
                "evaluator_receipt_count": 1,
            }],
            "blockers": [],
            "accepted": True,
            "receipt_sha256": None,
        }, "receipt_sha256")
'''
    text = text[:start] + helper + text[end:]
    old = '        receipt_path = self.write("reality.json", self.reality_receipt())'
    new = '        receipt_path = self.write("reality.json", self.reality_receipt(control))'
    if text.count(old) != 1:
        raise SystemExit("reality helper call did not match")
    text = text.replace(old, new, 1)
    insertion = '''        self.assertEqual(result["evidence_id"], "reality-evidence")
'''
    extra = '''        self.assertEqual(result["evidence_id"], "reality-evidence")
        self.assertTrue(result["execution_bound"])

    def test_legacy_self_asserted_reality_receipt_is_rejected(self) -> None:
        control = self.validate(self.manifest("pilot"))
        legacy = self.reality_receipt(control)
        legacy.pop("execution_bound")
        legacy["receipt_sha256"] = CONTROL.digest({**legacy, "receipt_sha256": None})
        receipt_path = self.write("legacy-reality.json", legacy)
        with self.assertRaises(CONTROL.OutcomeControlError) as caught:
            CONTROL.find_reality_receipt(
                project_root=self.root,
                evidence_by_id={"legacy": {"id": "legacy", "artifact_path": receipt_path}},
                evidence_ids=["legacy"],
                outcome_control=control,
            )
        self.assertEqual(caught.exception.code, "E_REALITY")
'''
    if text.count(insertion) != 1:
        raise SystemExit("reality assertion insertion did not match")
    text = text.replace(insertion, extra, 1)
    path.write_text(text, encoding="utf-8")


def patch_skill() -> None:
    path = Path("skills/company-os/elastic-company-os/SKILL.md")
    text = path.read_text(encoding="utf-8")
    marker = "## Controller rules\n"
    if text.count(marker) != 1:
        raise SystemExit("controller rules marker did not match")
    section = '''## Outcome feedback loop

For outcome owned work, route the master through `$run-outcome-loop`. The original objective remains the authority throughout discovery and delivery. Materialize a real candidate before expanding production scale. Every required evaluator must execute against the current candidate, not its source tree or the production team's report. Use the resulting independent scores and findings to identify the dominant bottleneck. Preserve dimensions that already pass and rework only the dominant constraint plus directly coupled artifacts. When repeated iterations fail to move the bottleneck, change the organization, capability mix, benchmarks, or artifact approach instead of adding identical workers. Completion requires the loop's `accepted` state and an execution bound reality receipt for the current candidate.

'''
    text = text.replace(marker, section + marker, 1)
    path.write_text(text, encoding="utf-8")


patch_outcome_control()
patch_outcome_control_tests()
patch_skill()
print("outcome loop controller integration applied")
