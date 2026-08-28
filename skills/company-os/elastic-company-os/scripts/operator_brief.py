#!/usr/bin/env python3
"""Safe, deterministic operator view for one Company OS project."""

from __future__ import annotations

import html
import math
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import quote

BRIEF_SCHEMA = "company-os.operator-brief.v1"
SPECIAL_LABELS = {"sqlite": "SQLite", "json": "JSON", "api": "API", "p0": "P0"}


def _objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _integer(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _metric(cycles: list[dict[str, Any]], field: str, *, integer: bool, unit: str) -> dict[str, Any]:
    known: list[int | float] = []
    unknown = 0
    invalid = 0
    for cycle in cycles:
        if field not in cycle or cycle.get(field) is None:
            unknown += 1
            continue
        value = cycle.get(field)
        valid = (
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            if integer
            else isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
        if valid:
            known.append(int(value) if integer else float(value))
        else:
            invalid += 1
    total = len(cycles)
    return {
        "value": (sum(known) if known else None),
        "unit": unit,
        "known_sources": len(known),
        "unknown_sources": unknown,
        "invalid_sources": invalid,
        "total_sources": total,
        "complete": total > 0 and len(known) == total,
    }


def _label(value: Any) -> str:
    words = str(value or "unknown").replace("_", " ").strip().split()
    return " ".join(SPECIAL_LABELS.get(word.lower(), word.title()) for word in words)


def _markdown(value: Any) -> str:
    """Render project text as inert one-line Markdown, not active markup/HTML."""
    text = html.escape(str(value or ""), quote=True).replace("\r", " ").replace("\n", " ")
    for character in ("\\", "`", "*", "_", "{", "}", "[", "]", "#", "|"):
        text = text.replace(character, f"\\{character}")
    return " ".join(text.split()) or "—"


def _safe_project_reference(value: Any) -> str | None:
    """Return a display-safe project-relative reference, never an authority path."""
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        return None
    candidate = PurePosixPath(value.strip())
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate.as_posix()


def _blocker_kind(message: str) -> str:
    lowered = message.lower()
    if "control store" in lowered or "revision" in lowered or "projection" in lowered:
        return "control"
    if "quality" in lowered:
        return "quality"
    if any(term in lowered for term in ("scheduler", "launcher", "issuer", "certif", "grant", "validation")):
        return "authority"
    if "fabric" in lowered or "runtime" in lowered or "manager" in lowered or "worker" in lowered:
        return "execution"
    if "evidence" in lowered or "artifact" in lowered or "snapshot" in lowered:
        return "evidence"
    return "program"


def _next_action(
    state: dict[str, Any],
    report: dict[str, Any],
    blockers: list[dict[str, str]],
    missing_quality: list[str],
    below_quality: list[str],
    invalid_quality: list[str],
) -> dict[str, str]:
    status = state.get("instance", {}).get("status")
    phase = str(state.get("phase") or "unknown")
    kinds = {item["kind"] for item in blockers}
    action = lambda kind, title, instruction, signal, owner, artifact, verify: {
        "kind": kind,
        "title": title,
        "instruction": instruction,
        "success_signal": signal,
        "owner": owner,
        "artifact": artifact,
        "verification": verify,
    }
    if status == "cancelled":
        return action("stop", "Keep cancellation authoritative",
            "Do not restart work. Version a replacement program only after an explicit new mandate.",
            "The instance remains cancelled with no lease, schedule, or active work.",
            "Program owner", "Replacement mandate or no artifact", "Run the strict brief and confirm cancellation remains the only terminal state.")
    if "control" in kinds:
        return action("repair_control", "Repair control authority",
            "Restore the transactional project record or its readable copies before any program decision.",
            "The control audit is clean and readable copies match committed authority.",
            "Control owner", ".company-os/control.db and deterministic exports", "Run audit; require a clean control-store report before continuing.")
    if not report.get("actor_issuer_ready"):
        return action("configure_issuer", "Restore decision authority",
            "Connect the externally controlled decision-issuer public key; do not create a project-local bypass.",
            "Governed commands can verify independent grants without exposing issuer secrets.",
            "Authority owner", "External issuer public-key attestation", "Run the strict brief and confirm decision authority is available.")
    if "evidence" in kinds:
        current = _objects(state.get("evidence", {}).get("reality" if phase == "reality_audit" else phase, []))
        only_missing = all("requires valid evidence" in item["message"] for item in blockers if item["kind"] == "evidence")
        if only_missing and not current:
            return action("record_evidence", f"Record {_label(phase)} evidence",
                "Capture the current product reality in one decision-grade artifact and have an independent reviewer challenge it.",
                "One immutable, current evidence record names the finding, decision impact, author, and independent reviewer.",
                "Product auditor + independent reviewer", f"{_label(phase)} evidence report",
                "Run the strict brief; the stage-evidence blocker must clear without weakening any gate.")
        return action("repair_evidence", f"Restore {_label(phase)} evidence",
            "Replace only the invalid named evidence through signed supersession, then re-audit.",
            "Every phase-required evidence item is current, immutable, and independently reviewed.",
            "Evidence owner + independent reviewer", f"Current {_label(phase)} evidence artifact", "Run the strict brief; the evidence blocker must disappear without a new error.")
    if "program" in kinds:
        return action("repair_program", "Restore program coherence",
            "Resolve the first program or work-contract violation before quality review or execution.",
            "The north star, current outcome, primary work, and program version agree.",
            "Program owner", "Versioned program contract", "Run audit and confirm no program blocker remains.")
    if "quality" in kinds or missing_quality or below_quality or invalid_quality:
        names = missing_quality + below_quality + invalid_quality
        detail = ", ".join(_label(name) for name in names[:4])
        if len(names) > 4:
            detail += f", and {len(names) - 4} more"
        bucket = "reality" if phase == "reality_audit" else phase
        current_evidence = _objects(state.get("evidence", {}).get(bucket, []))
        primary = next((item for item in _objects(state.get("portfolio", {}).get("active_work", [])) if item.get("primary")), {})
        artifact = next(
            (
                item.get("source_artifact_path") or item.get("artifact_path")
                for item in reversed(current_evidence)
                if item.get("work_id") == primary.get("id") and item.get("outcome_id") == primary.get("outcome_id")
            ),
            None,
        )
        if missing_quality and not below_quality and not invalid_quality:
            return action("audit_quality", f"Run the {_label(phase)} acceptance review",
                f"Have an independent product reviewer test the actual rendered journey against the acceptance matrix and score all {len(missing_quality)} required dimensions; do not score the specification.",
                "Every required dimension has independently authenticated, checkpoint-bound evidence; any score below its gate becomes the next concrete rework target.",
                "Independent product scorer + conflict-free reviewer", str(artifact or f"New {_label(phase)} acceptance report"),
                "Record the acceptance artifact, then run brief --strict; missing rows must become audit-valid scores or explicit below-gate rework.")
        if invalid_quality:
            target = _label(invalid_quality[0])
            return action("repair_quality_proof", f"Repair {target} proof",
                f"Replace the invalid {target} score contract with evidence and independent grants bound to the current checkpoint.",
                f"{target} is audit-valid; no numeric score is trusted before its full contract passes.",
                "Quality evidence owner + independent reviewer", str(artifact or f"Corrected {target} acceptance evidence"),
                "Run brief --strict and confirm the row is no longer Invalid before addressing another dimension.")
        if below_quality:
            target = _label(below_quality[0])
            return action("improve_quality", f"Raise {target}",
                f"Address the accepted review's highest-priority {target} defect, rerun that journey, and independently rescore only after the experience changes.",
                f"{target} reaches its required gate with new checkpoint-bound evidence.",
                "Feature owner + independent product reviewer", str(artifact or f"Updated {target} acceptance evidence"),
                "Re-run the named acceptance case and strict brief; the row must pass without invalidating another gate.")
        return action("close_quality", f"Close the {_label(phase)} quality gate",
            f"Improve the actual experience and independently rescore: {detail or 'all applicable dimensions'}.",
            "Every applicable critical score is at least 9 and every noncritical score is at least 8 with audit-valid proof.",
            "Feature owner + independent quality reviewer", str(artifact or f"New {_label(phase)} acceptance artifact"),
            "Run brief --strict; every required row must be audit-valid and at or above its gate.")
    if "execution" in kinds:
        message = next(item["message"] for item in blockers if item["kind"] == "execution")
        return action("resolve_execution", "Resolve the agent-team exception",
            f"Stop advancement and resolve this exact exception: {message}",
            "The affected manager or run has an attributable state, evidence, and explicit decision.",
            "Owning manager + master reviewer", "Manager phase report or runtime receipt", "Re-run the strict brief and require the execution blocker to clear.")
    if "authority" in kinds:
        return action("certify", "Obtain independent certification",
            "Have a conflict-free reviewer certify the exact current governance digest.",
            "Validation is current and signed without changing the program.",
            "Independent certifier", "Signed certification for the current digest", "Run brief --strict and confirm validation is current.")
    active = _objects(state.get("portfolio", {}).get("active_work", []))
    if not active:
        return action("choose_outcome", "Choose one visible outcome",
            "Commit one user-visible capability or bounded innovation bet and make it the primary lane.",
            "Exactly one ready primary work item names the user-visible outcome.",
            "Program owner", "Committed outcome and primary work contract", "Run brief and confirm one ready primary lane.")
    if not report.get("validation_valid"):
        return action("certify", "Obtain independent certification",
            "Have a conflict-free reviewer certify the exact current governance digest.",
            "Validation is current and signed without changing the program.",
            "Independent certifier", "Signed certification for the current digest", "Run brief --strict and confirm validation is current.")
    if status == "paused":
        return action("activate", "Activate the accepted program",
            "Activate only the certified instance; keep recurring scheduling off until launcher protection is proven.",
            "The instance is active and still unscheduled.",
            "Program owner", "Activation event", "Run brief and confirm active status with scheduling still off.")
    if not report.get("protected_launcher_ready"):
        return action("protect_launcher", "Establish external launcher authority",
            "Deploy an independently protected issuer and launcher outside the managed project.",
            "The external prerequisite is independently attested; no local bypass is used.",
            "Platform authority owner", "Protected launcher attestation", "Run audit from the protected launcher boundary.")
    if not state.get("controller", {}).get("schedule_enabled"):
        return action("arm_schedule", "Arm one bounded wake",
            "Enable one fenced project schedule and require an empty wake to stop without model work.",
            "The scheduler is ready with exactly one primary work item and no active lease.",
            "Protected launcher", "Fenced schedule record", "Observe one empty wake and one bounded work wake.")
    return action("begin_cycle", "Begin one bounded cycle",
        "Acquire the current program lease and execute only the next accepted outcome.",
        "One attributable cycle returns evidence, usage, review, and a terminal disposition.",
        "Primary work owner", "Cycle evidence and terminal review", "Finish the cycle with signed evidence and usage coverage.")


def _describe_changes(
    prior: dict[str, Any] | None,
    current: dict[str, Any],
    prior_revision: int | None,
    current_revision: int | None,
) -> list[dict[str, str]]:
    if prior is None:
        return [{
            "kind": "baseline",
            "summary": "No earlier authoritative revision is available for comparison.",
        }]
    changes: list[dict[str, str]] = []
    prior_strategy = prior.get("strategy", {})
    strategy = current.get("strategy", {})
    if prior_strategy.get("program_version") != strategy.get("program_version"):
        changes.append({
            "kind": "program",
            "summary": f"Program version changed from {prior_strategy.get('program_version')} to {strategy.get('program_version')}.",
        })
    if prior_strategy.get("current_outcome") != strategy.get("current_outcome"):
        changes.append({"kind": "direction", "summary": f"Current outcome changed to: {strategy.get('current_outcome')}."})
    if prior.get("phase") != current.get("phase"):
        changes.append({"kind": "phase", "summary": f"Stage moved from {_label(prior.get('phase'))} to {_label(current.get('phase'))}."})
    if prior.get("instance", {}).get("status") != current.get("instance", {}).get("status"):
        changes.append({"kind": "control", "summary": f"Project status changed to {_label(current.get('instance', {}).get('status'))}."})
    prior_work = {item.get("id"): item for item in _objects(prior.get("portfolio", {}).get("active_work", [])) if item.get("id")}
    current_work = {item.get("id"): item for item in _objects(current.get("portfolio", {}).get("active_work", [])) if item.get("id")}
    added_work = [str(item.get("title") or key) for key, item in current_work.items() if key not in prior_work]
    removed_work = [str(item.get("title") or key) for key, item in prior_work.items() if key not in current_work]
    if added_work:
        changes.append({"kind": "work", "summary": "Work added: " + ", ".join(added_work) + "."})
    if removed_work:
        changes.append({"kind": "work", "summary": "Work closed or removed: " + ", ".join(removed_work) + "."})
    prior_evidence = {str(item.get("id")) for items in prior.get("evidence", {}).values() for item in _objects(items) if item.get("id")}
    current_evidence = {str(item.get("id")) for items in current.get("evidence", {}).values() for item in _objects(items) if item.get("id")}
    if len(current_evidence - prior_evidence):
        changes.append({"kind": "evidence", "summary": f"{len(current_evidence - prior_evidence)} evidence record(s) became current."})
    if len(prior_evidence - current_evidence):
        changes.append({"kind": "evidence", "summary": f"{len(prior_evidence - current_evidence)} evidence record(s) left the current program."})
    prior_cycles = len(_objects(prior.get("feedback", {}).get("cycles", [])))
    current_cycles = len(_objects(current.get("feedback", {}).get("cycles", [])))
    if current_cycles != prior_cycles:
        changes.append({"kind": "feedback", "summary": f"Cycle count changed from {prior_cycles} to {current_cycles}."})
    if not changes:
        changes.append({"kind": "unchanged", "summary": "No operator-relevant governed field changed."})
    if prior_revision is not None and current_revision is not None:
        for item in changes:
            item["comparison"] = f"revision {prior_revision} → {current_revision}"
    return changes


def build_operator_brief(
    state: dict[str, Any],
    report: dict[str, Any],
    store_report: dict[str, Any] | None,
    *,
    phases: Iterable[str],
    critical_dimensions: dict[str, bool],
    prior_state: dict[str, Any] | None = None,
    prior_revision: int | None = None,
    change_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    phase_list = list(phases)
    phase = str(state.get("phase") or "unknown")
    phase_index = phase_list.index(phase) if phase in phase_list else -1
    errors = [str(item) for item in report.get("errors", []) if isinstance(item, str)]
    blockers = [{"kind": _blocker_kind(message), "message": message} for message in dict.fromkeys(errors)]
    if state.get("instance", {}).get("status") != "cancelled" and not report.get("actor_issuer_ready"):
        blockers.append({"kind": "authority", "message": "external decision issuer is unavailable"})
    required = [str(item) for item in report.get("applicable_quality_dimensions", [])]
    global_quality_errors = [
        error for error in errors
        if error.startswith("quality.") or error.startswith("quality threshold")
    ]
    quality_state = state.get("quality", {}) if isinstance(state.get("quality"), dict) else {}
    dimensions = quality_state.get("dimensions", {})
    # Source the critical threshold from governed state rather than repeating the
    # controller's literal, so the brief cannot misreport the gate if it changes.
    critical_threshold = quality_state.get("threshold", 9)
    if not isinstance(critical_threshold, (int, float)) or isinstance(critical_threshold, bool):
        critical_threshold = 9
    quality_rows: list[dict[str, Any]] = []
    missing_quality: list[str] = []
    below_quality: list[str] = []
    invalid_quality: list[str] = []
    for name in required:
        item = dimensions.get(name, {}) if isinstance(dimensions, dict) else {}
        score = item.get("score") if isinstance(item, dict) else None
        threshold = critical_threshold if critical_dimensions.get(name, True) else 8
        dimension_errors = [error for error in errors if f"quality dimension {name}" in error] + global_quality_errors
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score):
            status = "missing"
            score = None
            missing_quality.append(name)
        elif dimension_errors:
            status = "invalid"
            invalid_quality.append(name)
        elif score < threshold:
            status = "below_gate"
            below_quality.append(name)
        else:
            status = "pass"
        quality_rows.append({
            "dimension": name,
            "critical": bool(critical_dimensions.get(name, True)),
            "score": score,
            "threshold": threshold,
            "status": status,
            "audit_valid": not dimension_errors and status == "pass",
            "issues": dimension_errors,
            "evidence_count": len(item.get("evidence", [])) if isinstance(item, dict) and isinstance(item.get("evidence"), list) else 0,
        })

    active_work = []
    for item in _objects(state.get("portfolio", {}).get("active_work", [])):
        active_work.append({key: item.get(key) for key in (
            "id", "title", "type", "status", "primary", "owner", "user_visible_outcome", "execution_mode"
        )})
    evidence = state.get("evidence", {}) if isinstance(state.get("evidence"), dict) else {}
    evidence_rows = [
        {
            "bucket": bucket,
            "count": len(_objects(items)),
            "ids": [str(item.get("id")) for item in _objects(items) if item.get("id")],
            "references": list(dict.fromkeys(
                reference
                for item in _objects(items)
                if (reference := _safe_project_reference(item.get("source_artifact_path")))
            )),
        }
        for bucket, items in evidence.items()
    ]
    cycles = _objects(state.get("feedback", {}).get("cycles", []))
    runtime_adapter = state.get("runtime_adapter", {}) if isinstance(state.get("runtime_adapter"), dict) else {}
    attempts = _objects(runtime_adapter.get("attempts", []))
    inboxes = runtime_adapter.get("observation_inboxes", {}) if isinstance(runtime_adapter.get("observation_inboxes"), dict) else {}
    budget_errors = [error for error in errors if "budget" in error.lower()]

    def attempt_observation(attempt: dict[str, Any]) -> dict[str, Any] | None:
        inbox = inboxes.get(attempt.get("attempt_id"), {})
        observations = _objects(inbox.get("trusted_observations", [])) if isinstance(inbox, dict) else []
        trusted = [item for item in observations if item.get("trust") == "gateway_verified" and isinstance(item.get("claims"), dict)]
        return trusted[-1] if trusted else None

    def budget_exception(identity: str | None, attempt_id: str | None = None) -> bool:
        for error in budget_errors:
            lowered = error.lower()
            if (identity and identity in error) or (attempt_id and attempt_id in error):
                return True
            if lowered.startswith("runtime attempt budget") or "manifest" in lowered or "oversub" in lowered:
                return True
        return False
    fabric = state.get("execution_fabric", {}) if isinstance(state.get("execution_fabric"), dict) else {}
    managers = fabric.get("managers", {}) if isinstance(fabric.get("managers"), dict) else {}
    manager_rows = []
    for manager_id, manager in managers.items():
        if not isinstance(manager, dict):
            continue
        reports = _objects(manager.get("reports", []))
        decisions = _objects(manager.get("decisions", []))
        manager_attempt = next(
            (
                item for item in reversed(attempts)
                if item.get("role") == "manager" and item.get("manifest_identity_id") == manager_id
            ),
            {},
        )
        observation = attempt_observation(manager_attempt)
        observed_model = observation.get("claims", {}).get("observed_model") if observation else None
        last_decision = decisions[-1].get("decision") if decisions else None
        if manager.get("status") == "accepted":
            operating_state = "accepted"
        elif manager.get("status") == "terminated":
            operating_state = "terminated"
        elif manager.get("status") == "paused":
            operating_state = "paused"
        elif last_decision == "rework":
            operating_state = "in_rework"
        elif manager.get("status") == "awaiting_decision":
            operating_state = "awaiting_decision"
        elif reports:
            operating_state = "reporting"
        else:
            operating_state = manager.get("status") or "pending"
        manager_rows.append({
            "id": manager_id,
            "model": manager.get("model"),
            "outcome": manager.get("outcome"),
            "status": operating_state,
            "source_status": manager.get("status"),
            "next_phase": manager.get("next_phase"),
            "report_count": len(reports),
            "latest_report_phase": reports[-1].get("phase") if reports else None,
            "rework_rounds": _integer(manager.get("rework_rounds")),
            "decision_required": reports[-1].get("phase") if manager.get("status") == "awaiting_decision" and reports else None,
            "requested_model": manager_attempt.get("requested_model") or manager.get("model"),
            "observed_model": observed_model,
            "model_evidence": "gateway_verified" if observation and observed_model else "provider_unknown" if observation else "unverified",
            "budget_evidence": "exception" if budget_exception(manager_id, manager_attempt.get("attempt_id")) else "declared_only" if manager_attempt.get("budget") else "unknown",
        })
    safe_attempts = []
    for item in attempts:
        observation = attempt_observation(item)
        observed_model = observation.get("claims", {}).get("observed_model") if observation else None
        safe_attempts.append({
            key: item.get(key) for key in (
                "attempt_id", "manifest_identity_id", "role", "status", "requested_model",
                "provider", "parent_runtime_id",
            )
        } | {
            "observed_model": observed_model,
            "model_evidence": "gateway_verified" if observation and observed_model else "provider_unknown" if observation else "unverified",
            "budget_evidence": "exception" if budget_exception(item.get("manifest_identity_id"), item.get("attempt_id")) else "declared_only" if item.get("budget") else "unknown",
        })
    status = "ready" if report.get("ok") else "blocked"
    if state.get("instance", {}).get("status") == "cancelled":
        status = "cancelled"
    elif any(item["kind"] == "control" for item in blockers):
        status = "control_failure"
    elif not report.get("actor_issuer_ready"):
        status = "needs_authority"
    elif any(item["kind"] == "evidence" for item in blockers):
        status = "needs_evidence"
    elif any(item["kind"] == "quality" for item in blockers) or missing_quality or below_quality or invalid_quality:
        status = "needs_quality"
    elif any(item["kind"] == "authority" for item in blockers):
        status = "needs_authority"

    current_revision = store_report.get("revision") if isinstance(store_report, dict) else None
    changes = _describe_changes(prior_state, state, prior_revision, current_revision)
    change_kinds = {item["kind"] for item in changes}
    if {"program", "direction"}.intersection(change_kinds):
        impact = "Direction changed. Prior work and proof are historical; this program must establish its own evidence before execution."
    elif blockers:
        impact = f"The project cannot leave {_label(phase)} until the first governed blocker is resolved."
    else:
        impact = f"The {_label(phase)} gate is clear for its next governed decision."

    brief = {
        "schema": BRIEF_SCHEMA,
        "project": {
            "id": state.get("instance", {}).get("project_id"),
            "name": state.get("instance", {}).get("name"),
            "type": state.get("instance", {}).get("project_type"),
            "status": state.get("instance", {}).get("status"),
        },
        "program": {
            "version": state.get("strategy", {}).get("program_version"),
            "north_star": state.get("strategy", {}).get("north_star"),
            "current_outcome": state.get("strategy", {}).get("current_outcome"),
            "success_metric": state.get("strategy", {}).get("success_metric"),
        },
        "gate": {
            "status": status,
            "phase": phase,
            "phase_number": phase_index + 1 if phase_index >= 0 else None,
            "phase_count": len(phase_list),
            "comparison_window": {
                "from_revision": prior_revision,
                "to_revision": current_revision,
                "event_count": len(change_events or []),
            },
            "phase_track": [
                {
                    "phase": item,
                    "status": "complete" if index < phase_index else "current" if index == phase_index else "future",
                }
                for index, item in enumerate(phase_list)
            ],
            "changes": changes,
            "change_events": list(change_events or []),
            "impact": impact,
            "blockers": blockers,
            "warnings": [str(item) for item in report.get("warnings", []) if isinstance(item, str)],
            "next_action": _next_action(state, report, blockers, missing_quality, below_quality, invalid_quality),
        },
        "portfolio": {"active_work": active_work, "active_count": len(active_work)},
        "quality": {
            "ready": bool(report.get("quality_ready")),
            "passed": sum(1 for item in quality_rows if item["status"] == "pass"),
            "required": len(quality_rows),
            "missing": missing_quality,
            "below_gate": below_quality,
            "invalid": invalid_quality,
            "dimensions": quality_rows,
        },
        "evidence": {
            "valid_count": _integer(report.get("valid_evidence_count")),
            "buckets": evidence_rows,
        },
        "execution": {
            "fabric_status": report.get("execution_fabric_status"),
            "fabric_ready": bool(report.get("execution_fabric_ready")),
            "manager_count": len(managers),
            "manager_reports": sum(
                len(_objects(manager.get("reports", [])))
                for manager in managers.values() if isinstance(manager, dict)
            ),
            "managers": manager_rows,
            "runtime_attempts": safe_attempts,
            "schedule_enabled": bool(state.get("controller", {}).get("schedule_enabled")),
            "scheduler_ready": bool(report.get("scheduler_ready")),
            "protected_launcher_ready": bool(report.get("protected_launcher_ready")),
            "lease_active": state.get("controller", {}).get("lease") is not None,
            "cancellation_requested": bool(state.get("controller", {}).get("cancellation_requested")),
        },
        "feedback": {
            "cycles": len(cycles),
            "accepted_cycles": sum(1 for item in cycles if item.get("reviewer_decision") == "accepted"),
            "visible_cycles": sum(1 for item in cycles if item.get("user_visible_movement") is True),
            "metrics": {
                "cost": _metric(cycles, "cost_usd", integer=False, unit="USD"),
                "lead_time": _metric(cycles, "latency_minutes", integer=False, unit="minutes"),
                "tokens": _metric(cycles, "token_usage", integer=True, unit="tokens"),
            },
            "pending_adaptations": _integer(report.get("pending_adaptations")),
        },
        "authority": {
            "backend": store_report.get("backend") if isinstance(store_report, dict) else "legacy-json",
            "revision": store_report.get("revision") if isinstance(store_report, dict) else None,
            "store_ok": bool(store_report and store_report.get("ok")),
            "exports_match": bool(store_report and store_report.get("state_export_match") and store_report.get("events_export_match")),
            "validation_valid": bool(report.get("validation_valid")),
            "issuer_ready": bool(report.get("actor_issuer_ready")),
        },
        "non_claims": [
            "Requested model identity is not provider-observed identity.",
            "A clean local audit is not provider-runtime or production evidence.",
            "Scheduling is not ready until an external protected launcher is independently proven.",
        ],
    }
    return brief


def render_markdown(brief: dict[str, Any]) -> str:
    gate = brief["gate"]
    program = brief["program"]
    project = brief["project"]
    quality = brief["quality"]
    execution = brief["execution"]
    authority = brief["authority"]
    feedback = brief["feedback"]
    evidence = brief["evidence"]
    phase_bucket = "reality" if gate["phase"] == "reality_audit" else gate["phase"]
    phase_evidence = next((item for item in evidence["buckets"] if item["bucket"] == phase_bucket), {})
    decision_references = phase_evidence.get("references", []) if isinstance(phase_evidence, dict) else []
    decision_reference = next(
        (item for item in decision_references if "acceptance" in item.lower()),
        decision_references[0] if decision_references else "No current project reference",
    )
    def metric_text(metric: dict[str, Any], *, money: bool = False) -> str:
        total = metric["total_sources"]
        if total == 0:
            return "No observations"
        value = metric["value"]
        measured = "No usable observations" if value is None else (
            f"${value:,.2f}" if money else f"{value:,.0f}" if metric["unit"] == "tokens" else f"{value:,.1f} {metric['unit']}"
        )
        coverage = f"{metric['known_sources']}/{total} recorded"
        exceptions = []
        if metric["unknown_sources"]:
            exceptions.append(f"{metric['unknown_sources']} unknown")
        if metric["invalid_sources"]:
            exceptions.append(f"{metric['invalid_sources']} invalid")
        return " · ".join([measured, coverage, *exceptions])

    track = " → ".join(
        f"{_label(item['phase'])} [{_label(item['status'])}]" for item in gate["phase_track"]
    )
    quality_exceptions = [item for item in quality["dimensions"] if item["status"] != "pass"]
    lines = [
        f"# Company OS — {_markdown(project['name'])}",
        "",
        f"> **{_markdown(_label(gate['status']))}** · {_markdown(_label(gate['phase']))} · Program v{_markdown(program['version'])}",
        "",
        "## Latest governed change",
        "",
    ]
    for item in gate["changes"]:
        suffix = f" ({item['comparison']})" if item.get("comparison") else ""
        lines.append(f"- {_markdown(item['summary'] + suffix)}")
    comparison = gate["comparison_window"]
    comparison_label = (
        f"Update {comparison['from_revision']} → {comparison['to_revision']}"
        if comparison["from_revision"] is not None and comparison["to_revision"] is not None
        else "No revision comparison"
    )
    if gate["change_events"]:
        lines.extend(["", f"### Governed command trail · {_markdown(comparison_label)}", "", "| Update | Governed change | Command identity | Reference |", "| ---: | --- | --- | --- |"])
        for item in gate["change_events"]:
            references = ", ".join(f"{_label(key)}: {value}" for key, value in item.get("references", {}).items()) or "—"
            command = item.get("command") or "unkeyed"
            if item.get("command_key"):
                command = f"{command} · {item['command_key']}"
            lines.append(
                f"| {item.get('revision', '—')} | {_markdown(_label(item.get('event_type')))} | {_markdown(command)} | {_markdown(references)} |"
            )
    lines.extend([
        "",
        f"**Why it matters:** {_markdown(gate['impact'])}",
        "",
        f"## One move now — {_markdown(gate['next_action']['title'])}",
        "",
        _markdown(gate["next_action"]["instruction"]),
        "",
        f"- **Owner:** {_markdown(gate['next_action']['owner'])}",
        f"- **Output:** {_markdown(gate['next_action']['artifact'])}",
        f"- **Acceptance reference:** `{_markdown(decision_reference)}`",
        f"- **Done when:** {_markdown(gate['next_action']['success_signal'])}",
        f"- **Verify:** {_markdown(gate['next_action']['verification'])}",
        "",
        "## Direction",
        "",
        f"- **North star:** {_markdown(program['north_star'])}",
        f"- **Current outcome:** {_markdown(program['current_outcome'])}",
        f"- **Success metric:** {_markdown(program['success_metric'])}",
        "",
        "## Stage",
        "",
        f"{_markdown(track)}",
        f"Stage {gate['phase_number'] or '—'} of {gate['phase_count']}",
        "",
        "## Quality exceptions",
        "",
        f"**{quality['passed']} / {quality['required']} passed**" if quality["required"] else "**No quality gate applies until primary work is committed.**",
        "",
    ])
    if quality_exceptions:
        lines.extend(["| Dimension | Score | Gate | State |", "| --- | ---: | ---: | --- |"])
        for item in quality_exceptions:
            score = "—" if item["score"] is None else f"{item['score']:.1f}"
            lines.append(f"| {_markdown(_label(item['dimension']))} | {score} | {item['threshold']} | {_markdown(_label(item['status']))} |")
    elif quality["required"]:
        lines.append("- No quality exceptions. Passing dimensions are collapsed.")
    lines.extend(["", "## Active work", ""])
    if brief["portfolio"]["active_work"]:
        for item in brief["portfolio"]["active_work"]:
            primary = "Primary" if item.get("primary") else "Secondary"
            lines.append(
                f"- **{_markdown(item.get('title'))}** — {_markdown(primary)}, {_markdown(_label(item.get('status')))} · {_markdown(item.get('user_visible_outcome'))}"
            )
    else:
        lines.append("- No active work.")
    lines.extend([
        "",
        "## Agent team",
        "",
        f"- Team state: **{_markdown(_label(execution['fabric_status']))}** · **{execution['manager_count']} managers** · **{execution['manager_reports']} phase reports**",
    ])
    if execution["managers"]:
        lines.extend(["", "| Manager | State | Last report | Next decision | Requested / observed | Budget | Rework |", "| --- | --- | --- | --- | --- | --- | ---: |"])
        for item in execution["managers"]:
            lines.append(
                f"| {_markdown(item.get('id'))} | {_markdown(_label(item.get('status')))} | {_markdown(_label(item.get('latest_report_phase')))} | {_markdown(_label(item.get('decision_required') or item.get('next_phase')))} | {_markdown(item.get('requested_model'))} / {_markdown(item.get('observed_model'))} ({_markdown(_label(item.get('model_evidence')))}) | {_markdown(_label(item.get('budget_evidence')))} | {item.get('rework_rounds', 0)} |"
            )
    else:
        lines.append("- No manager is currently assigned.")
    lines.extend(["", "### Agent runs", ""])
    if execution["runtime_attempts"]:
        lines.extend(["| Run | Role | State | Requested | Observed | Model proof | Budget |", "| --- | --- | --- | --- | --- | --- | --- |"])
        for item in execution["runtime_attempts"]:
            lines.append(
                f"| {_markdown(item.get('attempt_id'))} | {_markdown(_label(item.get('role')))} | {_markdown(_label(item.get('status')))} | {_markdown(item.get('requested_model'))} | {_markdown(item.get('observed_model'))} | {_markdown(_label(item.get('model_evidence')))} | {_markdown(_label(item.get('budget_evidence')))} |"
            )
    else:
        lines.append("- No agent run has started for this program.")
    lines.extend([
        "",
        "## Trust and control",
        "",
        f"- Schedule: **{'on' if execution['schedule_enabled'] else 'off'}** · Lease: **{'active' if execution['lease_active'] else 'none'}** · Cancellation: **{'requested' if execution['cancellation_requested'] else 'clear'}**",
        f"- Project record: **{'protected local database' if authority['backend'] == 'sqlite' else 'legacy project file'} · update {_markdown(authority['revision'])}** · Integrity: **{'clean' if authority['store_ok'] else 'blocked'}** · Readable copies: **{'exact' if authority['exports_match'] else 'drifted'}**",
        f"- Decision authority: **{'available' if authority['issuer_ready'] else 'unavailable'}** · Independent certification: **{'current' if authority['validation_valid'] else 'not current'}**",
        f"- Evidence: **{brief['evidence']['valid_count']} valid records** across **{sum(1 for item in brief['evidence']['buckets'] if item['count'])} populated stages**",
        "",
        "## Feedback economy",
        "",
        f"- Cycles: **{feedback['cycles']}** · Accepted: **{feedback['accepted_cycles']}** · Visible: **{feedback['visible_cycles']}**",
        f"- Tokens: **{_markdown(metric_text(feedback['metrics']['tokens']))}**",
        f"- Cost: **{_markdown(metric_text(feedback['metrics']['cost'], money=True))}**",
        f"- Lead time: **{_markdown(metric_text(feedback['metrics']['lead_time']))}**",
        "",
        "## Blockers",
        "",
    ])
    if gate["blockers"]:
        for item in gate["blockers"]:
            lines.append(f"- **{_markdown(_label(item['kind']))}:** {_markdown(item['message'])}")
    else:
        lines.append("- No controller blocker.")
    if gate["warnings"]:
        lines.extend(["", "## Trust notes", ""])
        for warning in gate["warnings"]:
            lines.append(f"- {_markdown(warning)}")
    lines.extend(["", "## Evidence boundary", ""])
    for statement in brief["non_claims"]:
        lines.append(f"- {_markdown(statement)}")
    return "\n".join(lines) + "\n"


def render_html(brief: dict[str, Any]) -> str:
    """Render a self-contained, accessible, read-only command center."""
    gate = brief["gate"]
    program = brief["program"]
    project = brief["project"]
    quality = brief["quality"]
    execution = brief["execution"]
    authority = brief["authority"]
    feedback = brief["feedback"]
    evidence = brief["evidence"]

    def h(value: Any) -> str:
        return html.escape(" ".join(str(value if value not in (None, "") else "—").replace("\r", " ").replace("\n", " ").split()), quote=True)

    def metric(metric_value: dict[str, Any], *, money: bool = False) -> tuple[str, str]:
        total = metric_value["total_sources"]
        if total == 0:
            return "No observations", "0 sources"
        value = metric_value["value"]
        if value is None:
            primary = "No usable observations"
        elif money:
            primary = f"${value:,.2f}"
        elif metric_value["unit"] == "tokens":
            primary = f"{value:,.0f}"
        else:
            primary = f"{value:,.1f} {metric_value['unit']}"
        detail = f"{metric_value['known_sources']}/{total} recorded"
        if metric_value["unknown_sources"]:
            detail += f" · {metric_value['unknown_sources']} unknown"
        if metric_value["invalid_sources"]:
            detail += f" · {metric_value['invalid_sources']} invalid"
        return primary, detail

    changes = gate["changes"]
    lead_change = changes[0]["summary"] if changes else "No operator-relevant governed field changed."
    supporting_changes = changes[1:]
    change_facts = "".join(
        f'<li><span>{h(item["kind"])}</span><strong>{h(item["summary"])}</strong></li>'
        for item in supporting_changes
    ) or '<li><span>State</span><strong>No additional governed change.</strong></li>'
    def trail_item(item: dict[str, Any]) -> str:
        return (
            '<li>'
            f'<span class="trail-revision">Update {h(item.get("revision"))}</span>'
            f'<strong>{h(_label(item.get("event_type")))}</strong>'
            f'<span>{h(item.get("command") or "Unkeyed")} · {h(item.get("command_key") or "No command key")}</span>'
            f'<small>{h(", ".join(f"{_label(key)}: {value}" for key, value in item.get("references", {}).items()) or "No public reference")}</small>'
            '</li>'
        )

    def recent_trail_item(item: dict[str, Any]) -> str:
        references = item.get("references", {})
        reference = next(iter(references.values()), "No public reference") if isinstance(references, dict) else "No public reference"
        return (
            '<li>'
            f'<span class="trail-revision">Update {h(item.get("revision"))}</span>'
            f'<strong>{h(_label(item.get("event_type")))}</strong>'
            f'<span>{h(reference)}</span>'
            '</li>'
        )

    change_events = gate["change_events"]
    comparison = gate["comparison_window"]
    comparison_label = (
        f"Update {comparison['from_revision']} → {comparison['to_revision']}"
        if comparison["from_revision"] is not None and comparison["to_revision"] is not None
        else "No revision comparison"
    )
    event_word = "update" if len(change_events) == 1 else "updates"
    comparison_summary = f"View {len(change_events)} {event_word} in this comparison"
    recent_trail = "".join(recent_trail_item(item) for item in reversed(change_events[-4:]))
    if not recent_trail:
        recent_trail = '<li><strong>No governed event in this comparison window.</strong></li>'
    trail = "".join(
        trail_item(item)
        for item in change_events
    ) or '<li><strong>No governed event in this comparison window.</strong></li>'
    phases = "".join(
        f'<li class="stage stage--{h(item["status"])}" aria-label="{h(_label(item["phase"]))}: {h(_label(item["status"]))}">'
        f'<span class="stage-number">{index}</span><strong>{h(_label(item["phase"]))}</strong>'
        f'<span class="stage-state">{h(_label(item["status"]))}</span></li>'
        for index, item in enumerate(gate["phase_track"], 1)
    )
    quality_exceptions = [item for item in quality["dimensions"] if item["status"] != "pass"]
    def quality_score(item: dict[str, Any]) -> str:
        return "—" if item["score"] is None else f"{item['score']:.1f}"
    quality_rows = "".join(
        '<tr>'
        f'<th scope="row">{h(_label(item["dimension"]))}</th>'
        f'<td>{h(quality_score(item))}</td>'
        f'<td>{h(item["threshold"])}</td><td>{h(_label(item["status"]))}</td>'
        '</tr>'
        for item in quality_exceptions
    ) or '<tr><th scope="row">No exception</th><td colspan="3">All applicable rows pass.</td></tr>'
    quality_preview = "".join(
        f'<li><span class="exception-dot" aria-hidden="true"></span><strong>{h(_label(item["dimension"]))}</strong><span>{h(_label(item["status"]))}</span></li>'
        for item in quality_exceptions[:4]
    )
    if len(quality_exceptions) > 4:
        quality_preview += f'<li class="more">and {len(quality_exceptions) - 4} more exceptions</li>'
    elif not quality_exceptions:
        quality_preview = '<li class="more">No quality exceptions.</li>'
    active_work = "".join(
        '<article class="work-item">'
        f'<h2>{h(item.get("title"))}</h2><p>{h(item.get("user_visible_outcome"))}</p>'
        f'<dl><div><dt>Owner</dt><dd>{h(item.get("owner"))}</dd></div><div><dt>State</dt><dd>{h(_label(item.get("status")))}</dd></div></dl>'
        '</article>'
        for item in brief["portfolio"]["active_work"]
    ) or '<p class="empty">No active work.</p>'
    manager_rows = "".join(
        '<tr>'
        f'<th scope="row">{h(item.get("id"))}</th><td>{h(_label(item.get("status")))}</td>'
        f'<td>{h(_label(item.get("latest_report_phase")))}</td><td>{h(_label(item.get("decision_required") or item.get("next_phase")))}</td>'
        f'<td>{h(item.get("requested_model"))} / {h(item.get("observed_model"))}<small>{h(_label(item.get("model_evidence")))}</small></td>'
        f'<td>{h(_label(item.get("budget_evidence")))}</td></tr>'
        for item in execution["managers"]
    ) or '<tr><td colspan="6">No manager is currently assigned.</td></tr>'
    run_rows = "".join(
        '<tr>'
        f'<th scope="row">{h(item.get("attempt_id"))}</th><td>{h(_label(item.get("role")))}</td><td>{h(_label(item.get("status")))}</td>'
        f'<td>{h(item.get("requested_model"))}</td><td>{h(item.get("observed_model"))}<small>{h(_label(item.get("model_evidence")))}</small></td>'
        f'<td>{h(_label(item.get("budget_evidence")))}</td></tr>'
        for item in execution["runtime_attempts"]
    ) or '<tr><td colspan="6">No agent run has started for this program.</td></tr>'
    blocker_items = "".join(
        f'<li><strong>{h(_label(item["kind"]))}</strong><span>{h(item["message"])}</span></li>'
        for item in gate["blockers"]
    ) or '<li><span>No controller blocker.</span></li>'
    warning_items = "".join(f'<li>{h(item)}</li>' for item in gate["warnings"]) or '<li>No trust warning.</li>'
    non_claims = "".join(f'<li>{h(item)}</li>' for item in brief["non_claims"])
    token_value, token_detail = metric(feedback["metrics"]["tokens"])
    cost_value, cost_detail = metric(feedback["metrics"]["cost"], money=True)
    lead_value, lead_detail = metric(feedback["metrics"]["lead_time"])
    status_class = "blocked" if gate["status"] not in {"ready", "cancelled"} else gate["status"]
    certification_class = "good" if authority["validation_valid"] else "bad"
    if execution["schedule_enabled"]:
        schedule_class = "good" if execution["scheduler_ready"] else "bad"
        schedule_label = "On"
        schedule_detail = "Lease active" if execution["lease_active"] else "No lease"
    else:
        schedule_class = "safe"
        schedule_label = "Off — safe default"
        schedule_detail = "Launcher protected" if execution["protected_launcher_ready"] else "Launcher proof required"
    phase_bucket = "reality" if gate["phase"] == "reality_audit" else gate["phase"]
    phase_evidence = next((item for item in evidence["buckets"] if item["bucket"] == phase_bucket), {})
    decision_references = phase_evidence.get("references", []) if isinstance(phase_evidence, dict) else []
    decision_reference = next(
        (item for item in decision_references if "acceptance" in item.lower()),
        decision_references[0] if decision_references else "No current project reference",
    )
    decision_reference_href = (
        "/" + quote(decision_reference, safe="/")
        if decision_reference != "No current project reference"
        else None
    )
    handoff_work = next(
        (item for item in brief["portfolio"]["active_work"] if item.get("primary")),
        brief["portfolio"]["active_work"][0] if brief["portfolio"]["active_work"] else {},
    )
    decision_success = gate["next_action"]["success_signal"]
    decision_verification = gate["next_action"]["verification"]
    if gate["next_action"]["kind"] == "audit_quality":
        decision_success = f'{quality["required"]} / {quality["required"]} dimensions independently accepted at their gates.'
        decision_verification = "Record the report, then pass brief --strict."

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Company OS — {h(project["name"])}</title>
<style>
:root{{--canvas:#070907;--text:#f3f4ef;--muted:#9da198;--line:#292d28;--accent:#c9ff36;--danger:#ff6b61;--accent-tint:rgba(201,255,54,.07);--danger-tint:rgba(255,107,97,.07);--max:1440px;--gutter:clamp(18px,2.4vw,36px)}}
*{{box-sizing:border-box}} html{{background:var(--canvas);color-scheme:dark}} body{{margin:0;background:var(--canvas);color:var(--text);font-family:Inter,"SF Pro Text",ui-sans-serif,system-ui,-apple-system,sans-serif;line-height:1.45}}
a,summary{{-webkit-tap-highlight-color:transparent}} :focus-visible{{outline:2px solid var(--accent);outline-offset:4px}} .skip-link{{position:fixed;z-index:10;left:18px;top:12px;transform:translateY(-160%);padding:10px 14px;border-radius:6px;background:var(--accent);color:#070907;font-weight:800}} .skip-link:focus{{transform:none}} .shell{{width:min(100%,var(--max));margin:auto;border-inline:1px solid var(--line);min-height:100vh}}
.masthead{{display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;gap:12px;min-height:64px;padding:0 var(--gutter);border-bottom:1px solid var(--line)}} .brand,.project-name{{font-size:20px;font-weight:750;letter-spacing:-.02em}} .project-name{{text-align:center}} .status{{text-align:right;color:var(--muted);font-size:14px}} .status strong{{font-weight:650}} .status--ready strong{{color:var(--accent)}} .status--blocked strong,.status--cancelled strong{{color:var(--danger)}}
main>section,.operating-band,.facts{{border-bottom:1px solid var(--line)}} .label{{margin:0 0 14px;color:var(--muted);font-size:11px;font-weight:750;letter-spacing:.14em;text-transform:uppercase}}
.change-band{{display:grid;grid-template-columns:minmax(0,.85fr) minmax(420px,1.15fr);gap:42px;padding:30px var(--gutter)}} .lead-change{{font-family:"Arial Black",Arial,sans-serif;font-size:clamp(34px,4vw,58px);line-height:1.02;letter-spacing:-.045em;max-width:760px;margin:0 0 18px}} .change-impact{{max-width:68ch;margin:0 0 28px;color:var(--muted);font-size:14px}} .change-impact span{{margin-right:8px;color:var(--text);font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}} .change-facts{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-top:1px solid var(--line)}} .change-facts li{{padding:18px 20px 8px 0;border-right:1px solid var(--line)}} .change-facts span,.change-facts strong{{display:block}} .change-facts span{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.12em}} .change-facts strong{{margin-top:7px;font-size:15px;font-weight:520}}
.trail-panel{{border-left:1px solid var(--line);padding-left:42px}} details{{border-top:1px solid var(--line)}} summary{{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px 0;color:var(--text);font-size:12px;font-weight:750;letter-spacing:.12em;text-transform:uppercase}} summary::-webkit-details-marker{{display:none}} summary::after{{content:"+";font-size:19px;font-weight:400;color:var(--muted)}} details[open] summary::after{{content:"−"}} .trail{{list-style:none;margin:0 0 14px;padding:0}} .trail li{{display:grid;grid-template-columns:84px 1fr 1.3fr;gap:12px;padding:10px 0;border-top:1px solid rgba(255,255,255,.06);font-size:13px}} .trail-revision,.trail span,.trail small{{color:var(--muted)}} .trail small{{grid-column:2/-1}} .trail-all{{margin-top:2px}} .trail-all summary{{color:var(--muted)}}
.decision{{margin:0 var(--gutter) 4px;padding:22px;border:1px solid var(--accent);border-radius:10px;background:var(--accent-tint);display:grid;grid-template-columns:minmax(300px,1.55fr) repeat(4,minmax(125px,.65fr));align-items:stretch;animation:rise .45s ease-out both}} .decision-title{{display:grid;grid-template-columns:64px 1fr;gap:18px;align-items:center;padding-right:20px}} .decision-mark{{width:62px;height:62px;border:1px solid var(--accent);border-radius:50%;display:grid;place-items:center;color:var(--accent);font-size:15px;font-weight:850;letter-spacing:.06em}} .decision h1{{font-family:"Arial Black",Arial,sans-serif;font-size:clamp(28px,3vw,46px);line-height:1.03;letter-spacing:-.035em;margin:0}} .decision .label{{color:var(--accent);margin-bottom:7px}} .decision-link{{display:inline-block;margin-top:12px;color:var(--text);font-size:12px;text-underline-offset:4px}} .decision-context{{grid-column:1/-1;margin:18px 0 0;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}} .decision-context strong{{color:var(--text);font-weight:650}} .decision-meta{{padding:4px 18px;border-left:1px solid var(--line)}} .decision-meta dt{{color:var(--accent);font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}} .decision-meta dd{{margin:12px 0 0;font-size:14px}}
.journey{{padding:18px var(--gutter) 8px}} .stages{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:0}} .stage{{position:relative;min-height:88px;padding:0 18px 0 4px;border-top:1px solid var(--line)}} .stage:not(:last-child)::after{{content:"";position:absolute;right:0;top:-1px;width:20px;border-top:1px solid var(--muted)}} .stage-number,.stage strong,.stage-state{{display:block}} .stage-number{{margin-top:14px;color:var(--muted);font-variant-numeric:tabular-nums}} .stage strong{{margin:9px 0 12px;font-size:15px}} .stage-state{{width:max-content;border:1px solid #555b53;border-radius:4px;padding:3px 9px;color:var(--muted);font-size:10px;font-weight:750;letter-spacing:.08em;text-transform:uppercase}} .stage--complete .stage-state{{color:var(--text)}} .stage--current{{border-top-color:var(--accent)}} .stage--current .stage-number,.stage--current .stage-state{{color:var(--accent)}} .stage--current .stage-state{{border-color:var(--accent);animation:pulse 2.4s ease-in-out infinite}}
.operating-band{{display:grid;grid-template-columns:.95fr .95fr 1.05fr}} .operating-band>section{{min-width:0;padding:26px var(--gutter);border-right:1px solid var(--line)}} .operating-band>section:last-child{{border-right:0}} .quality-number{{font-size:22px;margin:0 0 12px}} .quality-number strong{{font-family:"Arial Black",Arial,sans-serif;font-size:36px;color:var(--danger)}} .exception-preview{{list-style:none;margin:0;padding:0}} .exception-preview li{{display:grid;grid-template-columns:10px 1fr auto;gap:10px;align-items:center;padding:4px 0;font-size:13px}} .exception-dot{{width:7px;height:7px;border-radius:50%;background:var(--danger)}} .exception-preview span:last-child,.exception-preview .more{{color:var(--muted)}} .work-item h2,.team-truth{{font-family:"Arial Black",Arial,sans-serif;font-size:clamp(25px,2.5vw,38px);line-height:1.08;letter-spacing:-.035em;margin:0 0 18px}} .work-item p{{max-width:46ch;color:var(--muted)}} dl{{margin:20px 0 0;display:flex;gap:30px}} dt{{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.12em}} dd{{margin:4px 0 0}} .team-truth+.team-truth{{border-top:1px solid var(--line);padding-top:18px}} .empty{{color:var(--muted)}}
.table-wrap{{overflow:auto;max-width:100%;padding-bottom:12px}} table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{padding:11px 12px;text-align:left;border-top:1px solid var(--line);vertical-align:top}} th{{font-weight:650}} td{{color:var(--muted)}} td small{{display:block;margin-top:3px}}
.facts{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}} .fact{{min-width:0;padding:20px 18px;border-right:1px solid var(--line)}} .fact:last-child{{border-right:0}} .fact strong,.fact span,.fact small{{display:block}} .fact strong{{font-size:14px;overflow-wrap:anywhere}} .fact span{{margin-bottom:8px;color:var(--muted);font-size:11px;letter-spacing:.09em;text-transform:uppercase}} .fact small{{margin-top:5px;color:var(--muted)}} .fact--bad strong{{color:var(--danger)}} .fact--good strong{{color:var(--accent)}} .fact--safe strong{{color:var(--text)}}
.disclosures{{padding:8px var(--gutter) 24px}} .disclosures details{{background:rgba(255,255,255,.015)}} .disclosures details[open]{{padding-bottom:14px}} .disclosures ul{{margin:0;padding:0 0 0 22px}} .disclosures li{{margin:8px 0;color:var(--muted)}} .disclosures dl{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:0}} .disclosures dl>div{{min-width:0;padding:14px 18px;border-top:1px solid var(--line)}} .disclosures dd,.disclosures code{{overflow-wrap:anywhere}} .blockers li{{display:grid;grid-template-columns:120px 1fr;gap:20px}} .blockers strong{{color:var(--danger)}} footer{{padding:22px var(--gutter);color:var(--muted);font-size:12px;border-top:1px solid var(--line)}}
@keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}} @keyframes pulse{{50%{{box-shadow:0 0 0 4px rgba(201,255,54,.08)}}}}
@media(max-width:1280px){{.decision{{grid-template-columns:repeat(4,minmax(0,1fr))}}.decision-title{{grid-column:1/-1;padding:0 0 20px}}.decision-meta:first-of-type{{border-left:0}}}}
@media(max-width:920px){{.masthead{{grid-template-columns:1fr auto}}.project-name{{display:none}}.change-band,.operating-band{{grid-template-columns:1fr}}.trail-panel{{border-left:0;padding:18px 0 0}}.decision{{grid-template-columns:1fr}}.decision-title{{grid-column:auto}}.decision-meta{{border-left:0;border-top:1px solid var(--line);padding:14px 0}}.stages{{grid-template-columns:1fr}}.stage{{min-height:auto;padding:12px 4px;border-top:1px solid var(--line);display:grid;grid-template-columns:28px 1fr auto;align-items:center}}.stage strong{{margin:0}}.stage-number{{margin:0}}.stage:not(:last-child)::after{{display:none}}.operating-band>section{{border-right:0;border-bottom:1px solid var(--line)}}.facts{{grid-template-columns:repeat(2,1fr)}}.fact{{border-bottom:1px solid var(--line)}}.disclosures dl{{grid-template-columns:1fr}}}}
@media(max-width:560px){{.masthead{{grid-template-columns:auto 1fr;padding-block:14px}}.brand{{font-size:17px}}.status{{font-size:12px}}main{{display:flex;flex-direction:column}}.decision{{order:1;margin-top:18px;padding:18px}}.change-band{{order:2;padding-top:22px}}.journey{{order:3}}.operating-band{{order:4}}.facts{{order:5}}.disclosures{{order:6}}.lead-change{{font-size:34px}}.change-facts{{grid-template-columns:1fr}}.decision-title{{grid-template-columns:46px 1fr;padding-bottom:14px}}.decision-mark{{width:44px;height:44px;font-size:12px}}.decision h1{{font-size:28px}}.decision-meta{{display:grid;grid-template-columns:88px 1fr;gap:12px;align-items:start;margin:0;padding:12px 0}}.decision-meta dd{{margin:0}}.facts{{grid-template-columns:1fr}}.trail li{{grid-template-columns:70px 1fr}}.trail-panel>.trail li:nth-child(n+3){{display:none}}.trail span,.trail small{{grid-column:2}}.blockers li{{grid-template-columns:1fr;gap:3px}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation:none!important;scroll-behavior:auto!important}}}}
@media print{{:root{{--canvas:#fff;--text:#111;--muted:#555;--line:#ccc;--accent:#456900;--danger:#9c1c14;--accent-tint:#f4f8eb}}.shell{{border:0}}details{{display:block}}details>summary{{list-style:none}}details>*:not(summary){{display:block!important}}}}
</style>
</head>
<body>
<a class="skip-link" href="#decision-heading">Skip to current decision</a>
<div class="shell">
<header class="masthead"><div class="brand">Company OS</div><div class="project-name">{h(project["name"])}</div><div class="status status--{h(status_class)}"><strong>{h(_label(gate["status"]))}</strong> · {h(_label(gate["phase"]))} · Program v{h(program["version"])}</div></header>
<main>
<section class="change-band" aria-labelledby="change-heading"><div><p class="label" id="change-heading">Latest governed change · {h(comparison_label)}</p><p class="lead-change">{h(lead_change)}</p><p class="change-impact"><span>Why now</span>{h(gate["impact"])}</p><ul class="change-facts">{change_facts}</ul></div><div class="trail-panel"><p class="label">Governed command trail · {h(comparison_label)}</p><ol class="trail">{recent_trail}</ol><details class="trail-all"><summary>{h(comparison_summary)}</summary><ol class="trail">{trail}</ol></details></div></section>
<section class="decision" aria-labelledby="decision-heading"><div class="decision-title"><span class="decision-mark" aria-hidden="true">{h(str(gate["phase_number"] or "—").zfill(2))}</span><div><p class="label">Current decision</p><h1 id="decision-heading">{h(gate["next_action"]["title"])}</h1><a class="decision-link" href="#decision-handoff">Inspect governed handoff ↓</a></div></div><dl class="decision-meta"><dt>Owner</dt><dd>{h(gate["next_action"]["owner"])}</dd></dl><dl class="decision-meta"><dt>Required output</dt><dd>{h(gate["next_action"]["artifact"])}</dd></dl><dl class="decision-meta"><dt>Done condition</dt><dd>{h(decision_success)}</dd></dl><dl class="decision-meta"><dt>Verification</dt><dd>{h(decision_verification)}</dd></dl><p class="decision-context"><strong>Outcome</strong> {h(program["current_outcome"])} · <strong>Success</strong> {h(program["success_metric"])}</p></section>
<section class="journey" aria-labelledby="journey-heading"><p class="label" id="journey-heading">Company OS seven-stage journey · Stage {h(gate["phase_number"])} of {h(gate["phase_count"])}</p><ol class="stages">{phases}</ol></section>
<div class="operating-band"><section aria-labelledby="quality-heading"><p class="label" id="quality-heading">Quality exceptions</p><p class="quality-number"><strong>{h(quality["passed"])}</strong> / {h(quality["required"])} independently accepted</p><ul class="exception-preview">{quality_preview}</ul><details><summary>View full quality evidence</summary><div class="table-wrap" tabindex="0"><table><thead><tr><th>Dimension</th><th>Score</th><th>Gate</th><th>State</th></tr></thead><tbody>{quality_rows}</tbody></table></div></details></section><section aria-labelledby="work-heading"><p class="label" id="work-heading">Primary work</p>{active_work}</section><section aria-labelledby="team-heading"><p class="label" id="team-heading">Agent team truth</p><p class="team-truth">{h("No manager is currently assigned." if not execution["managers"] else f"{execution['manager_count']} manager(s) are governed.")}</p><p class="team-truth">{h("No agent run has started for this program." if not execution["runtime_attempts"] else f"{len(execution['runtime_attempts'])} agent run(s) are recorded.")}</p><details><summary>Manager accountability</summary><div class="table-wrap" tabindex="0"><table><thead><tr><th>Manager</th><th>State</th><th>Last report</th><th>Decision</th><th>Model</th><th>Budget</th></tr></thead><tbody>{manager_rows}</tbody></table></div></details><details><summary>Agent runs</summary><div class="table-wrap" tabindex="0"><table><thead><tr><th>Run</th><th>Role</th><th>State</th><th>Requested</th><th>Observed</th><th>Budget</th></tr></thead><tbody>{run_rows}</tbody></table></div></details></section></div>
<section class="facts" aria-label="Trust and feedback"><div class="fact"><span>Protected project record</span><strong>Update {h(authority["revision"])}</strong><small>{"Readable copies exact" if authority["exports_match"] else "Readable copies drifted"}</small></div><div class="fact"><span>Decision authority</span><strong>{"Available" if authority["issuer_ready"] else "Unavailable"}</strong><small>{"Integrity clean" if authority["store_ok"] else "Integrity blocked"}</small></div><div class="fact fact--{certification_class}"><span>Certification</span><strong>{"Current" if authority["validation_valid"] else "Not current"}</strong></div><div class="fact fact--{schedule_class}"><span>Schedule</span><strong>{h(schedule_label)}</strong><small>{h(schedule_detail)}</small></div><div class="fact"><span>Token observations</span><strong>{h(token_value)}</strong><small>{h(token_detail)}</small></div><div class="fact"><span>Cost observations</span><strong>{h(cost_value)}</strong><small>{h(cost_detail)}</small></div><div class="fact"><span>Lead-time observations</span><strong>{h(lead_value)}</strong><small>{h(lead_detail)}</small></div></section>
<section class="disclosures" aria-label="Operational detail"><details {"open" if gate["blockers"] else ""}><summary>Blockers · {len(gate["blockers"])} active</summary><ul class="blockers">{blocker_items}</ul></details><details id="decision-handoff" open><summary>Governed decision handoff</summary><dl><div><dt>Project / program / update</dt><dd>{h(project["id"])} · v{h(program["version"])} · {h(authority["revision"])}</dd></div><div><dt>Outcome / work</dt><dd>{h(program["current_outcome"])} · {h(handoff_work.get("id") or "No active work")}</dd></div><div><dt>Action</dt><dd>{h(gate["next_action"]["kind"])} · {h(gate["next_action"]["instruction"])}</dd></div><div><dt>Acceptance reference</dt><dd>{f'<a href="{h(decision_reference_href)}"><code>{h(decision_reference)}</code></a>' if decision_reference_href else f'<code>{h(decision_reference)}</code>'}</dd></div><div><dt>Done condition</dt><dd>{h(gate["next_action"]["success_signal"])}</dd></div><div><dt>Verification</dt><dd>{h(gate["next_action"]["verification"])}</dd></div></dl></details><details><summary>Trust notes · {len(gate["warnings"])} active</summary><ul>{warning_items}</ul></details><details><summary>Evidence boundaries</summary><ul>{non_claims}</ul></details><details><summary>Outcome compass</summary><dl><div><dt>North star</dt><dd>{h(program["north_star"])}</dd></div><div><dt>Current outcome</dt><dd>{h(program["current_outcome"])}</dd></div><div><dt>Success metric</dt><dd>{h(program["success_metric"])}</dd></div></dl></details></section>
</main><footer>Read-only projection of governed Company OS authority. It cannot approve, schedule, or execute work.</footer>
</div>
</body>
</html>'''
