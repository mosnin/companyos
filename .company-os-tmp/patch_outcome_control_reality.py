#!/usr/bin/env python3
from pathlib import Path

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
        "company_os_accept_outcome_reality",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise OutcomeControlError(
            "E_RUNTIME",
            "reality acceptance runtime cannot be loaded",
        )
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
                "E_BINDING",
                f"reality acceptance does not bind current {source_name}",
            )
    claim_count = verified.get("claim_count")
    if not isinstance(claim_count, int) or isinstance(claim_count, bool) or claim_count < 1:
        raise OutcomeControlError("E_REALITY", "reality acceptance claim count is invalid")
    return {
        "objective_id": verified["objective_id"],
        "receipt_sha256": _sha256(verified.get("receipt_sha256"), "reality receipt_sha256"),
        "claim_count": claim_count,
        "execution_bound": True,
    }
'''
text = text[:start] + new_function + text[end:]

old_call = "        validated = validate_reality_receipt(raw, outcome_control)"
new_call = "        validated = validate_reality_receipt(project_root, raw, outcome_control)"
if text.count(old_call) != 1:
    raise SystemExit("reality verification call did not match exactly once")
text = text.replace(old_call, new_call, 1)
path.write_text(text, encoding="utf-8")
