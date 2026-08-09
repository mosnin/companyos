#!/usr/bin/env python3
from pathlib import Path

path = Path("skills/company-os/elastic-company-os/scripts/outcome_control.py")
text = path.read_text(encoding="utf-8")

old_imports = "import hashlib\nimport json\n"
new_imports = "import hashlib\nimport importlib.util\nimport json\n"
if text.count(old_imports) != 1:
    raise SystemExit("outcome control import patch did not match exactly once")
text = text.replace(old_imports, new_imports, 1)

marker = "}\n\n\nclass OutcomeControlError"
loader = '''}

_CALIBRATION_MODULE: Any | None = None


def calibration_module() -> Any:
    global _CALIBRATION_MODULE
    if _CALIBRATION_MODULE is not None:
        return _CALIBRATION_MODULE
    module_path = (
        Path(__file__).resolve().parents[2]
        / "calibrate-outcome-evaluator"
        / "scripts"
        / "calibrate_evaluator.py"
    )
    spec = importlib.util.spec_from_file_location(
        "company_os_calibrate_outcome_evaluator",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise OutcomeControlError(
            "E_RUNTIME",
            "calibration runtime cannot be loaded",
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CALIBRATION_MODULE = module
    return module


class OutcomeControlError'''
if text.count(marker) != 1:
    raise SystemExit("calibration loader insertion did not match exactly once")
text = text.replace(marker, loader, 1)

start = text.index("def _validate_calibrations(")
end = text.index("\ndef validate_manifest_binding(", start)
replacement = '''def _validate_calibrations(
    project_root: Path,
    value: Any,
    objective_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    runtime = calibration_module()
    for index, raw in enumerate(_array(value, "calibration receipts")):
        receipt = dict(_object_value(raw, f"calibration[{index}]"))
        _require_schema(receipt, CALIBRATION_SCHEMA, f"calibration[{index}]")
        try:
            verified = runtime.verify_receipt(project_root, receipt)
        except Exception as exc:
            code = getattr(exc, "code", "E_CALIBRATION")
            raise OutcomeControlError(
                code,
                f"calibration[{index}] failed execution verification: {exc}",
            ) from exc
        evaluator_id = _text(
            verified.get("evaluator_id"),
            f"calibration[{index}].evaluator_id",
        )
        if evaluator_id in seen:
            raise OutcomeControlError(
                "E_DUPLICATE",
                f"duplicate calibration for {evaluator_id}",
            )
        seen.add(evaluator_id)
        if verified.get("objective_id") != objective_id:
            raise OutcomeControlError(
                "E_BINDING",
                f"calibration objective does not match outcome control: {evaluator_id}",
            )
        if verified.get("execution_bound") is not True:
            raise OutcomeControlError(
                "E_CALIBRATION",
                f"calibration is not execution bound: {evaluator_id}",
            )
        if verified.get("passed") is not True:
            raise OutcomeControlError(
                "E_CALIBRATION",
                f"calibration failed for {evaluator_id}",
            )
        receipt_digest = _sha256(
            verified.get("receipt_sha256"),
            f"calibration[{index}].receipt_sha256",
        )
        candidate_count = verified.get("candidate_count")
        if (
            not isinstance(candidate_count, int)
            or isinstance(candidate_count, bool)
            or candidate_count < 3
        ):
            raise OutcomeControlError(
                "E_CALIBRATION",
                f"calibration candidate count is invalid: {evaluator_id}",
            )
        receipts.append(receipt)
        bindings.append(
            {
                "evaluator_id": evaluator_id,
                "receipt_sha256": receipt_digest,
                "execution_bound": True,
                "candidate_count": candidate_count,
            }
        )
    receipts.sort(key=lambda item: str(item.get("evaluator_id", "")))
    bindings.sort(key=lambda item: str(item["evaluator_id"]))
    return receipts, bindings
'''
text = text[:start] + replacement + text[end:]

old_call = '''    calibrations, calibration_bindings = _validate_calibrations(
        read_json(calibration_path),
        objective_id,
    )'''
new_call = '''    calibrations, calibration_bindings = _validate_calibrations(
        project_root,
        read_json(calibration_path),
        objective_id,
    )'''
if text.count(old_call) != 1:
    raise SystemExit("calibration call patch did not match exactly once")
text = text.replace(old_call, new_call, 1)
path.write_text(text, encoding="utf-8")
