#!/usr/bin/env python3
"""Apply the outcome control plane to the canonical Company OS execution path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_controller() -> None:
    path = ROOT / "skills/company-os/elastic-company-os/scripts/company_os_controller.py"

    replace_once(
        path,
        "_OPERATOR_BRIEF_MODULE: Any | None = None\n_ACTIVE_CONTROL_STORE_TRANSACTION",
        "_OPERATOR_BRIEF_MODULE: Any | None = None\n_OUTCOME_CONTROL_MODULE: Any | None = None\n_ACTIVE_CONTROL_STORE_TRANSACTION",
        "controller outcome module global",
    )

    replace_once(
        path,
        "\ndef utc_now() -> str:\n",
        """

def outcome_control_module() -> Any:
    \"\"\"Load portable outcome control validation without relying on PYTHONPATH.\"\"\"
    global _OUTCOME_CONTROL_MODULE
    if _OUTCOME_CONTROL_MODULE is not None:
        return _OUTCOME_CONTROL_MODULE
    module_path = Path(__file__).resolve().with_name(\"outcome_control.py\")
    spec = importlib.util.spec_from_file_location(\"company_os_outcome_control\", module_path)
    if spec is None or spec.loader is None:
        raise ValueError(\"outcome control module could not be loaded\")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _OUTCOME_CONTROL_MODULE = module
    return module


def utc_now() -> str:
""",
        "controller outcome module loader",
    )

    replace_once(
        path,
        '        "manifest_digest": None,\n        "configured_at": None,\n        "managers": {},',
        '        "manifest_digest": None,\n        "configured_at": None,\n        "outcome_control": None,\n        "managers": {},',
        "empty fabric outcome control",
    )

    replace_once(
        path,
        '        for field in ("work_id", "cycle_id", "manifest", "manifest_digest", "configured_at"):',
        '        for field in ("work_id", "cycle_id", "manifest", "manifest_digest", "configured_at", "outcome_control"):',
        "unconfigured fabric outcome control",
    )

    old_validation = '''    if not work:
        errors.append("execution_fabric.work_id must reference governed work")
    else:
        if work.get("execution_mode", "single") != "luna_fabric":
            errors.append("execution_fabric work must use execution_mode luna_fabric")
        if manifest.get("outcome") != work.get("user_visible_outcome"):
            errors.append("execution_fabric outcome must match the governed user-visible outcome")

    if not fabric.get("configured_at"):
'''
    new_validation = '''    if not work:
        errors.append("execution_fabric.work_id must reference governed work")
    else:
        if work.get("execution_mode", "single") != "luna_fabric":
            errors.append("execution_fabric work must use execution_mode luna_fabric")
        if manifest.get("outcome") != work.get("user_visible_outcome"):
            errors.append("execution_fabric outcome must match the governed user-visible outcome")

    outcome_control_state = None
    if work and manifest:
        if manifest.get("outcome_control") is None and manifest.get("topology_mode") is None:
            if fabric.get("outcome_control") is not None:
                errors.append("legacy execution_fabric may not retain outcome control state")
        else:
            try:
                outcome_control_state = outcome_control_module().validate_manifest_binding(
                    project_root=project_root,
                    manifest=manifest,
                    project_id=str(state.get("instance", {}).get("project_id", "")),
                    program_version=int(state.get("strategy", {}).get("program_version", 0)),
                    work_id=str(fabric.get("work_id", "")),
                    governed_outcome=str(work.get("user_visible_outcome", "")),
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"execution_fabric outcome control: {exc}")
            else:
                if fabric.get("outcome_control") != outcome_control_state:
                    errors.append("execution_fabric.outcome_control does not match current contracts")
                if work.get("status") == "completed" and work.get("execution_mode") == "luna_fabric":
                    completion = work.get("completion")
                    if not isinstance(completion, dict):
                        errors.append("completed luna_fabric work requires completion evidence")
                    else:
                        completion_ids = completion.get("evidence_ids")
                        if not isinstance(completion_ids, list):
                            errors.append("completed luna_fabric work requires evidence_ids")
                        else:
                            try:
                                reality = outcome_control_module().find_reality_receipt(
                                    project_root=project_root,
                                    evidence_by_id=evidence_by_id,
                                    evidence_ids=completion_ids,
                                    outcome_control=outcome_control_state,
                                )
                            except (OSError, ValueError, json.JSONDecodeError) as exc:
                                errors.append(f"completed luna_fabric reality acceptance: {exc}")
                            else:
                                if completion.get("reality_acceptance") != reality:
                                    errors.append("completed luna_fabric reality acceptance does not match evidence")

    if not fabric.get("configured_at"):
'''
    replace_once(path, old_validation, new_validation, "fabric state outcome validation")

    old_configure = '''            if manifest.get("program_contract", {}).get("north_star") != state["strategy"]["north_star"]:
                raise ValueError("manifest north_star must match Company OS strategy")
            configured_at = utc_now()
            state["execution_fabric"] = {
'''
    new_configure = '''            if manifest.get("program_contract", {}).get("north_star") != state["strategy"]["north_star"]:
                raise ValueError("manifest north_star must match Company OS strategy")
            if manifest.get("outcome_control") is None and manifest.get("topology_mode") is None:
                outcome_control_state = None
            else:
                outcome_control_state = outcome_control_module().validate_manifest_binding(
                    project_root=project,
                    manifest=manifest,
                    project_id=state["instance"]["project_id"],
                    program_version=state["strategy"]["program_version"],
                    work_id=args.work_id,
                    governed_outcome=work["user_visible_outcome"],
                )
            configured_at = utc_now()
            state["execution_fabric"] = {
'''
    replace_once(path, old_configure, new_configure, "configure fabric outcome validation")

    replace_once(
        path,
        '                "configured_at": configured_at,\n                "managers": {',
        '                "configured_at": configured_at,\n                "outcome_control": outcome_control_state,\n                "managers": {',
        "configured fabric outcome state",
    )

    replace_once(
        path,
        '''                "execution_fabric_configured",
                work_id=args.work_id,
                manifest_digest=state["execution_fabric"]["manifest_digest"],
            )''',
        '''                "execution_fabric_configured",
                work_id=args.work_id,
                manifest_digest=state["execution_fabric"]["manifest_digest"],
                execution_lane=(outcome_control_state or {}).get("execution_lane", "legacy_compatibility"),
                outcome_control_digest=(outcome_control_state or {}).get("state_sha256"),
            )''',
        "configure event outcome binding",
    )

    replace_once(
        path,
        '''            evidence_ids = set(args.evidence_ids)
            work = next(''',
        '''            evidence_ids = set(args.evidence_ids)
            reality_acceptance = None
            work = next(''',
        "finish cycle reality initialization",
    )

    replace_once(
        path,
        '''            validate_completion_evidence(state, project, cycle, work, evidence_ids)
            if args.work_disposition == "complete" and args.reviewer_decision != "accepted":''',
        '''            validate_completion_evidence(state, project, cycle, work, evidence_ids)
            if (
                work.get("execution_mode", "single") == "luna_fabric"
                and args.work_disposition == "complete"
                and isinstance(state.get("execution_fabric", {}).get("outcome_control"), dict)
            ):
                completion_evidence_by_id = {
                    item.get("id"): item
                    for bucket in state.get("evidence", {}).values()
                    for item in bucket
                    if isinstance(item, dict)
                    and isinstance(item.get("id"), str)
                    and evidence_is_active(item)
                }
                reality_acceptance = outcome_control_module().find_reality_receipt(
                    project_root=project,
                    evidence_by_id=completion_evidence_by_id,
                    evidence_ids=sorted(evidence_ids),
                    outcome_control=state["execution_fabric"]["outcome_control"],
                )
            if args.work_disposition == "complete" and args.reviewer_decision != "accepted":''',
        "finish cycle reality validation",
    )

    replace_once(
        path,
        '''            )
            if args.commit:
                cycle["commit"] = args.commit''',
        '''            )
            if reality_acceptance is not None:
                cycle["reality_acceptance"] = reality_acceptance
            if args.commit:
                cycle["commit"] = args.commit''',
        "cycle reality receipt retention",
    )

    replace_once(
        path,
        '''                        "reviewer": args.reviewer,
                        "reviewer_grant": reviewer_grant,
                    }
                    if args.commit:''',
        '''                        "reviewer": args.reviewer,
                        "reviewer_grant": reviewer_grant,
                    }
                    if reality_acceptance is not None:
                        completion["reality_acceptance"] = reality_acceptance
                    if args.commit:''',
        "completion reality receipt retention",
    )


def patch_template() -> None:
    path = ROOT / "skills/company-os/elastic-company-os/assets/instance-template.json"
    replace_once(
        path,
        '    "configured_at": null,\n    "managers": {},',
        '    "configured_at": null,\n    "outcome_control": null,\n    "managers": {},',
        "template outcome control",
    )


def patch_validator() -> None:
    path = ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py"
    old = '''    if topology_mode not in {None, "elastic_work_graph"}:
        errors.append("topology_mode must be 'elastic_work_graph' when provided")
    if topology_mode is None:
'''
    new = '''    if topology_mode not in {None, "elastic_work_graph"}:
        errors.append("topology_mode must be 'elastic_work_graph' when provided")
    if topology_mode == "elastic_work_graph":
        outcome_control = manifest.get("outcome_control")
        required_outcome_fields = {
            "$schema", "execution_lane", "project_id", "program_version", "work_id",
            "governed_outcome", "objective_id", "outcome_contract_path",
            "artifact_contract_path", "evaluator_contract_path", "benchmark_contract_path",
            "calibration_receipts_path", "scale_authorization_path",
        }
        if not isinstance(outcome_control, dict):
            errors.append("elastic_work_graph requires an outcome_control binding")
        else:
            if set(outcome_control) != required_outcome_fields:
                errors.append("outcome_control must define the exact portable binding fields")
            if outcome_control.get("$schema") != "company-os.outcome-control-binding.v1":
                errors.append("outcome_control uses an unsupported schema")
            lane = outcome_control.get("execution_lane")
            if lane not in {"pilot", "production_scale"}:
                errors.append("outcome_control.execution_lane must be pilot or production_scale")
            if outcome_control.get("project_id") != manifest.get("program_id"):
                errors.append("outcome_control.project_id must match program_id")
            if outcome_control.get("program_version") != manifest.get("program_version"):
                errors.append("outcome_control.program_version must match program_version")
            if outcome_control.get("governed_outcome") != manifest.get("outcome"):
                errors.append("outcome_control.governed_outcome must match outcome")
            for field in (
                "work_id", "objective_id", "outcome_contract_path", "artifact_contract_path",
                "evaluator_contract_path", "benchmark_contract_path", "calibration_receipts_path",
            ):
                if not _nonempty(outcome_control.get(field)):
                    errors.append(f"outcome_control.{field} must be non-empty")
            if lane == "production_scale" and not _nonempty(outcome_control.get("scale_authorization_path")):
                errors.append("production_scale requires outcome_control.scale_authorization_path")
            if lane == "pilot":
                if outcome_control.get("scale_authorization_path") not in {None, ""}:
                    errors.append("pilot may not present scale authorization as pilot authority")
                for field, cap in LEGACY_HARD_CAPS.items():
                    if limits[field] > cap:
                        errors.append(f"pilot {field} cannot exceed {cap}")
    if topology_mode is None:
'''
    replace_once(path, old, new, "fabric validator outcome control")


def patch_elastic_skill() -> None:
    path = ROOT / "skills/company-os/elastic-company-os/SKILL.md"
    replace_once(
        path,
        '''- **Execution fabric:** after direction and experience are accepted, the master
  may use `$luna-execution-fabric` to create isolated Sol manager threads and
  bounded Luna worker teams. Managers never edit `control.json` or approve
  Company OS state.
''',
        '''- **Outcome control plane:** compiles the original objective into observable artifacts, executable independent evaluators, benchmark tiers, evaluator calibration, and a content-bound scale decision before elastic execution.
- **Execution fabric:** after direction and experience are accepted, the master
  may use `$luna-execution-fabric` to create isolated Sol manager threads and
  bounded Luna worker teams. New elastic manifests must carry the exact outcome control binding. Managers never edit `control.json` or approve Company OS state.
''',
        "elastic skill architecture",
    )
    replace_once(
        path,
        '''5. **Delivery:** version a complete Program Contract, assign bounded roadmap
   outcomes to Sol manager threads, and use Luna workers for most labor.
''',
        '''5. **Delivery:** compile and close the outcome contract first. Define rich artifacts, executable independent evaluators, benchmark tiers, and evaluator calibration. A bounded pilot may use at most the legacy 2/3/6 capacity. Elastic production requires a current content-bound outcome scale authorization. Then version a complete Program Contract, assign bounded roadmap
   outcomes to Sol manager threads, and use Luna workers for most labor.
''',
        "elastic skill delivery sequence",
    )
    replace_once(
        path,
        '''- `configure-fabric` binds a validated project-local Sol-manager/Luna-worker
  manifest to primary work queued with `--execution-mode luna_fabric`.
''',
        '''- `configure-fabric` binds a validated project-local Sol-manager/Luna-worker
  manifest to primary work queued with `--execution-mode luna_fabric`. Every new `elastic_work_graph` manifest must bind the current project, program, work outcome, outcome contract, artifact observations, executable evaluators, benchmark contract, and calibration receipts. A `production_scale` lane must additionally bind an authorized scale receipt. Contract drift invalidates the fabric on the next audit.
''',
        "elastic skill configure fabric",
    )
    replace_once(
        path,
        '''- stage completion with missing evidence, any applicable critical quality score below 9, or any applicable noncritical score below 8;
''',
        '''- stage completion with missing evidence, any applicable critical quality score below 9, or any applicable noncritical score below 8;
- an elastic execution fabric without a current outcome control binding, a pilot that exceeds 2 managers, 3 workers per manager, or 6 total workers, or production scale without exact outcome authorization;
- completion of outcome-controlled fabric work without exactly one accepted reality receipt bound through completion evidence to the original objective;
''',
        "elastic skill controller rejection",
    )


def patch_luna_skill() -> None:
    path = ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md"
    replace_once(
        path,
        '''1. Create one versioned Program Contract with north star, customer value,
   complete outcome, rationale, architecture, roadmap, dependencies, non-goals,
   acceptance evidence, constraints, budget, and stop conditions.
''',
        '''1. Start from the original objective and compile its outcome control plane. Resolve blocking unknowns with cited evidence, define observable artifact classes, compile executable independent evaluators, bind benchmark tiers, and calibrate the evaluators. Create one versioned Program Contract only after those controls can measure the intended outcome.
''',
        "luna start outcome control",
    )
    replace_once(
        path,
        '''7. When an Elastic Company OS instance exists, queue the governed primary work
   with `--execution-mode luna_fabric`, then bind the validated manifest through
   `configure-fabric`. Record every visible phase; use `decide-fabric-phase`
''',
        '''7. When an Elastic Company OS instance exists, queue the governed primary work
   with `--execution-mode luna_fabric`, then bind the validated manifest through
   `configure-fabric`. A new `elastic_work_graph` manifest requires `outcome_control`. A pilot is capped at 2 managers, 3 workers per manager, and 6 total workers. Production scale requires a content-bound authorized scale receipt. Record every visible phase; use `decide-fabric-phase`
''',
        "luna configure outcome control",
    )
    replace_once(
        path,
        '''- New manifests declare `topology_mode: elastic_work_graph`. Manifests without
  it retain the frozen 2/3/6 Phase 1 limits solely for replay compatibility.
''',
        '''- New manifests declare `topology_mode: elastic_work_graph` and carry an exact portable outcome control binding. Manifests without it retain the frozen 2/3/6 Phase 1 limits solely for replay compatibility and cannot establish elastic scale evidence.
- The pilot lane may use no more than 2 managers, 3 workers per manager, and 6 total workers. Any larger organization is production scale and requires current outcome authorization before configuration.
''',
        "luna elastic authorization",
    )
    replace_once(
        path,
        '''Business acceptance does not imply that any execution-fabric gate passed.
''',
        '''Business acceptance does not imply that any execution-fabric gate passed. Completion of outcome-controlled fabric work additionally requires one independently accepted reality receipt that judges actual artifacts against the original objective. Production summaries are not acceptance evidence.
''',
        "luna final reality acceptance",
    )


def patch_architecture() -> None:
    path = ROOT / "docs/ARCHITECTURE.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Project execution\n"
    if marker not in text:
        raise RuntimeError("architecture project execution marker missing")
    insertion = '''## Outcome control plane

Company OS accepts broad objectives as input. Before a new elastic execution fabric can be configured, the system must compile the original objective into measurable claims, close blocking unknowns with cited evidence, define observable artifact classes, compile executable independent evaluators, bind benchmark tiers, and calibrate those evaluators. A bounded pilot is capped at the legacy 2/3/6 topology. Production scale requires a content-bound authorization over the exact outcome, artifact, evaluator, benchmark, and calibration contracts. Final completion requires an accepted reality receipt from actual artifact evidence, not a production team narrative.

'''
    path.write_text(text.replace(marker, insertion + marker, 1), encoding="utf-8")


def patch_version() -> None:
    (ROOT / "VERSION").write_text("0.6.0\n", encoding="utf-8")


def main() -> None:
    patch_controller()
    patch_template()
    patch_validator()
    patch_elastic_skill()
    patch_luna_skill()
    patch_architecture()
    patch_version()
    print("outcome control integration applied")


if __name__ == "__main__":
    main()
