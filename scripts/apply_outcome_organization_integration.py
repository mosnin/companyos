#!/usr/bin/env python3
import json
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_validator() -> None:
    path = Path("skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py")
    replace_once(
        path,
        '''    if topology_mode not in {None, "elastic_work_graph"}:
        errors.append("topology_mode must be 'elastic_work_graph' when provided")
    if topology_mode == "elastic_work_graph":
''',
        '''    if topology_mode not in {None, "elastic_work_graph", "outcome_closed_loop"}:
        errors.append("topology_mode must be elastic_work_graph or outcome_closed_loop when provided")
    if topology_mode in {"elastic_work_graph", "outcome_closed_loop"}:
''',
        "topology modes",
    )
    marker = '''    if topology_mode is None:
        for key, cap in LEGACY_HARD_CAPS.items():
'''
    insertion = '''    if topology_mode == "outcome_closed_loop":
        loop_binding = manifest.get("outcome_loop")
        required_loop_fields = {
            "$schema", "state_path", "state_file_sha256", "state_sha256", "phase",
            "iteration", "next_action", "organization_sha256", "lane_sha256s",
        }
        if not isinstance(loop_binding, dict):
            errors.append("outcome_closed_loop requires an outcome_loop binding")
        else:
            if set(loop_binding) != required_loop_fields:
                errors.append("outcome_loop must define the exact portable binding fields")
            if loop_binding.get("$schema") != "company-os.outcome-loop-fabric-binding.v1":
                errors.append("outcome_loop uses an unsupported schema")
            if not _nonempty(loop_binding.get("state_path")):
                errors.append("outcome_loop.state_path must be non-empty")
            for field in ("state_file_sha256", "state_sha256", "organization_sha256"):
                value = loop_binding.get(field)
                if not isinstance(value, str) or len(value) != 64 or any(
                    character not in "0123456789abcdef" for character in value
                ):
                    errors.append(f"outcome_loop.{field} must be lowercase sha256")
            if loop_binding.get("phase") not in {"build_candidate", "rework"}:
                errors.append("outcome_loop.phase must be build_candidate or rework")
            iteration = loop_binding.get("iteration")
            if not isinstance(iteration, int) or isinstance(iteration, bool) or iteration < 0:
                errors.append("outcome_loop.iteration must be a non-negative integer")
            if loop_binding.get("next_action") not in {"materialize_candidate", "execute_intervention"}:
                errors.append("outcome_loop.next_action does not authorize production execution")
            lane_sha256s = loop_binding.get("lane_sha256s")
            if not isinstance(lane_sha256s, dict) or not lane_sha256s:
                errors.append("outcome_loop.lane_sha256s must bind at least one lane")
            elif any(
                not _nonempty(lane_id)
                or not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for lane_id, value in lane_sha256s.items()
            ):
                errors.append("outcome_loop.lane_sha256s contains an invalid lane binding")

    if topology_mode is None:
        for key, cap in LEGACY_HARD_CAPS.items():
'''
    replace_once(path, marker, insertion, "outcome loop validator")


def patch_controller() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/company_os_controller.py")
    replace_once(
        path,
        '''_OUTCOME_CONTROL_MODULE: Any | None = None
_ACTIVE_CONTROL_STORE_TRANSACTION''',
        '''_OUTCOME_CONTROL_MODULE: Any | None = None
_OUTCOME_ORGANIZATION_MODULE: Any | None = None
_ACTIVE_CONTROL_STORE_TRANSACTION''',
        "organization module global",
    )
    marker = '''def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
'''
    loader = '''def outcome_organization_module() -> Any:
    """Load the outcome organization compiler without relying on PYTHONPATH."""
    global _OUTCOME_ORGANIZATION_MODULE
    if _OUTCOME_ORGANIZATION_MODULE is not None:
        return _OUTCOME_ORGANIZATION_MODULE
    module_path = (
        Path(__file__).resolve().parents[2]
        / "compile-outcome-organization"
        / "scripts"
        / "compile_outcome_organization.py"
    )
    spec = importlib.util.spec_from_file_location("company_os_outcome_organization", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("outcome organization module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _OUTCOME_ORGANIZATION_MODULE = module
    return module


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
'''
    replace_once(path, marker, loader, "organization module loader")
    replace_once(
        path,
        '''        "outcome_control": None,
        "managers": {},
''',
        '''        "outcome_control": None,
        "outcome_loop": None,
        "managers": {},
''',
        "empty fabric outcome loop",
    )
    replace_once(
        path,
        '''        for field in ("work_id", "cycle_id", "manifest", "manifest_digest", "configured_at", "outcome_control"):
''',
        '''        for field in ("work_id", "cycle_id", "manifest", "manifest_digest", "configured_at", "outcome_control", "outcome_loop"):
''',
        "unconfigured fabric outcome loop",
    )
    old_config = '''            if manifest.get("outcome_control") is None and manifest.get("topology_mode") is None:
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
'''
    new_config = '''            if manifest.get("outcome_control") is None and manifest.get("topology_mode") is None:
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
            if manifest.get("topology_mode") == "outcome_closed_loop":
                outcome_loop_state = outcome_organization_module().validate_manifest_binding(
                    project,
                    manifest,
                )
                if outcome_loop_state.get("state_sha256") != manifest.get("outcome_loop", {}).get("state_sha256"):
                    raise ValueError("outcome loop state binding is invalid")
            else:
                outcome_loop_state = None
            configured_at = utc_now()
'''
    replace_once(path, old_config, new_config, "configure outcome loop")
    replace_once(
        path,
        '''                "outcome_control": outcome_control_state,
                "managers": {
''',
        '''                "outcome_control": outcome_control_state,
                "outcome_loop": outcome_loop_state,
                "managers": {
''',
        "store configured outcome loop",
    )
    replace_once(
        path,
        '''                outcome_control_digest=(outcome_control_state or {}).get("state_sha256"),
            )
''',
        '''                outcome_control_digest=(outcome_control_state or {}).get("state_sha256"),
                outcome_loop_digest=(outcome_loop_state or {}).get("state_sha256"),
            )
''',
        "event outcome loop digest",
    )
    marker = '''    if not fabric.get("configured_at"):
        errors.append("configured execution_fabric.configured_at is required")
'''
    insertion = '''    if manifest.get("topology_mode") == "outcome_closed_loop":
        try:
            current_outcome_loop = outcome_organization_module().validate_manifest_binding(
                project_root,
                manifest,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"execution_fabric outcome loop: {exc}")
        else:
            if fabric.get("outcome_loop") != current_outcome_loop:
                errors.append("execution_fabric.outcome_loop does not match current outcome loop state")
    elif fabric.get("outcome_loop") is not None:
        errors.append("non closed loop execution_fabric may not retain outcome loop state")

    if not fabric.get("configured_at"):
        errors.append("configured execution_fabric.configured_at is required")
'''
    replace_once(path, marker, insertion, "audit outcome loop binding")


def patch_template() -> None:
    path = Path("skills/company-os/elastic-company-os/assets/instance-template.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    fabric = value["execution_fabric"]
    rebuilt = {}
    for key, item in fabric.items():
        rebuilt[key] = item
        if key == "outcome_control":
            rebuilt["outcome_loop"] = None
    value["execution_fabric"] = rebuilt
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def patch_skill() -> None:
    path = Path("skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md")
    text = path.read_text(encoding="utf-8")
    marker = '''- New manifests declare `topology_mode: elastic_work_graph` and carry an exact portable outcome control binding. Manifests without it retain the frozen 2/3/6 Phase 1 limits solely for replay compatibility and cannot establish elastic scale evidence.
'''
    replacement = '''- Outcome-owned manifests compile from the current `$run-outcome-loop` state and declare `topology_mode: outcome_closed_loop`. They carry both the portable outcome control binding and the exact current outcome loop state, organization, next action, and lane digests. If the bottleneck or loop state changes, the old fabric becomes stale and must be recompiled.
- `topology_mode: elastic_work_graph` remains compatible for non-loop orchestration. Manifests without an outcome control binding retain the frozen 2/3/6 Phase 1 limits solely for replay compatibility and cannot establish elastic scale evidence.
'''
    if marker not in text:
        raise SystemExit("elastic topology documentation marker missing")
    path.write_text(text.replace(marker, replacement, 1), encoding="utf-8")


patch_validator()
patch_controller()
patch_template()
patch_skill()
print("outcome organization integration applied")
