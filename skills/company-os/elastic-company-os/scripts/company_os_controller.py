#!/usr/bin/env python3
"""Deterministic validator/bootstrapper for isolated Elastic Company OS instances."""

from __future__ import annotations

import argparse
import base64
import contextvars
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

PHASES = (
    "reality_audit",
    "intelligence",
    "direction",
    "experience",
    "delivery",
    "verification",
    "learning",
)

PHASE_EVIDENCE = {
    "reality_audit": ("reality",),
    "intelligence": ("reality", "intelligence"),
    "direction": ("reality", "intelligence", "direction"),
    "experience": ("reality", "intelligence", "direction", "experience"),
    "delivery": ("reality", "intelligence", "direction", "experience", "delivery"),
    "verification": (
        "reality",
        "intelligence",
        "direction",
        "experience",
        "delivery",
        "verification",
    ),
    "learning": (
        "reality",
        "intelligence",
        "direction",
        "experience",
        "delivery",
        "verification",
        "learning",
    ),
}

BASE_DIMENSIONS = {
    "north_star_alignment": True,
    "user_value": True,
    "product_coherence": True,
    "differentiation": True,
    "innovation": True,
    "domain_fit": True,
    "customer_evidence": False,
    "technology_currency": True,
    "counterevidence": False,
    "information_architecture": True,
    "usability": True,
    "accessibility": True,
    "interaction_quality": True,
    "visual_quality": True,
    "motion_quality": False,
    "brand_cohesion": True,
    "agent_intelligence": True,
    "agent_controllability": True,
    "agent_transparency": True,
    "context_quality": True,
    "tool_appropriateness": True,
    "artifact_quality": True,
    "autonomy_value": True,
    "security": True,
    "privacy": True,
    "reliability": True,
    "latency": True,
    "cost_efficiency": True,
    "token_efficiency": False,
    "maintainability": True,
    "test_strength": True,
    "observability": True,
    "rollback_readiness": True,
    "adoption_potential": True,
    "commercial_leverage": True,
    "operational_readiness": True,
    "feedback_health": True,
    "evidence_integrity": True,
}

# Certification evaluates only the dimensions that can be meaningfully evidenced
# in the current phase. Delivery-only dimensions must not block an inspectable
# experience prototype, while a P0 interruption always carries its own safety
# gate.
PHASE_QUALITY_DIMENSIONS = {
    "reality_audit": {
        "north_star_alignment",
        "domain_fit",
        "evidence_integrity",
    },
    "intelligence": {
        "north_star_alignment",
        "domain_fit",
        "technology_currency",
        "counterevidence",
        "evidence_integrity",
    },
    "direction": {
        "north_star_alignment",
        "user_value",
        "product_coherence",
        "differentiation",
        "innovation",
        "domain_fit",
        "technology_currency",
        "counterevidence",
        "evidence_integrity",
    },
    "experience": {
        "north_star_alignment",
        "user_value",
        "product_coherence",
        "differentiation",
        "innovation",
        "domain_fit",
        "information_architecture",
        "usability",
        "accessibility",
        "interaction_quality",
        "visual_quality",
        "brand_cohesion",
        "evidence_integrity",
    },
    "delivery": {
        "north_star_alignment",
        "user_value",
        "product_coherence",
        "information_architecture",
        "usability",
        "accessibility",
        "interaction_quality",
        "visual_quality",
        "brand_cohesion",
        "security",
        "privacy",
        "reliability",
        "latency",
        "cost_efficiency",
        "maintainability",
        "test_strength",
        "observability",
        "rollback_readiness",
        "evidence_integrity",
    },
    "verification": {
        "north_star_alignment",
        "user_value",
        "product_coherence",
        "information_architecture",
        "usability",
        "accessibility",
        "interaction_quality",
        "visual_quality",
        "brand_cohesion",
        "security",
        "privacy",
        "reliability",
        "latency",
        "cost_efficiency",
        "maintainability",
        "test_strength",
        "observability",
        "rollback_readiness",
        "adoption_potential",
        "operational_readiness",
        "feedback_health",
        "evidence_integrity",
    },
    "learning": {
        "north_star_alignment",
        "user_value",
        "product_coherence",
        "information_architecture",
        "usability",
        "accessibility",
        "interaction_quality",
        "visual_quality",
        "brand_cohesion",
        "security",
        "privacy",
        "reliability",
        "latency",
        "cost_efficiency",
        "maintainability",
        "test_strength",
        "observability",
        "rollback_readiness",
        "adoption_potential",
        "operational_readiness",
        "feedback_health",
        "evidence_integrity",
    },
}

DELIVERY_WORK_QUALITY_DIMENSIONS = {
    "capability": {"adoption_potential", "commercial_leverage"},
    "innovation": {"innovation", "adoption_potential"},
    "enabler": {"tool_appropriateness", "artifact_quality"},
    "maintenance": {"reliability", "maintainability", "observability"},
    "p0": {"security", "privacy", "reliability", "observability", "rollback_readiness"},
}

DEPARTMENT_PRESETS = {
    "software": ["strategy", "product", "design", "engineering", "research", "commercial", "operations"],
    "service": ["strategy", "service-design", "delivery", "customer-success", "commercial", "operations"],
    "research": ["strategy", "research", "evidence-review", "product", "operations"],
    "content": ["strategy", "editorial", "creative", "distribution", "commercial", "operations"],
    "general": ["strategy", "product", "delivery", "commercial", "operations"],
}

ALLOWED_WORK_TYPES = {"capability", "innovation", "enabler", "maintenance", "p0"}
PRODUCT_OUTCOMES = {"reality", "intelligence", "experience", "capability", "learning", "adaptation"}
ACTIVE_WORK_STATUSES = {"ready", "running", "blocked"}
INSTANCE_STATUSES = {"paused", "active", "cancelled"}
EVIDENCE_BUCKETS = tuple(PHASE_EVIDENCE["learning"])
FABRIC_PHASES = (
    "charter",
    "discovery",
    "design",
    "execution",
    "verification",
    "integration",
)
FABRIC_DECISIONS = {"continue", "rework", "pause", "terminate"}
FABRIC_STATUSES = {"unconfigured", "ready", "running", "accepted", "paused", "terminated", "cancelled"}
PROTECTED_ADAPTATION_FIELDS = {
    "north_star",
    "authority",
    "approval_boundaries",
    "cancellation_precedence",
    "evidence_integrity",
    "cross_project_isolation",
    "meta_loop_depth",
}
CORE_VERSION = "2.6.0"
SCHEMA_VERSION = 9
ACTOR_PUBLIC_KEY_ENV = "COMPANY_OS_ACTOR_GRANT_PUBLIC_KEY"
RUNTIME_GATEWAY_PUBLIC_KEY_ENV = "COMPANY_OS_RUNTIME_GATEWAY_PUBLIC_KEY"
OBSERVATION_GATEWAY_KEYRING_ENV = "COMPANY_OS_OBSERVATION_GATEWAY_KEYRING"
# Frozen SHA-256 of the accepted Company OS Self-Hosting Phase 2 revision 2
# contract.  This controller stores neither decision-issuer private material nor
# provider credentials; the separately signed admission grant authorizes a
# single attempt under this public contract identity.
PHASE2_CONTRACT_DIGEST = "b83f727e472c95911a60757efb0769a0c39acf11f0c8a7051e1056e34b8b8348"
LEASE_TRANSITIONS = frozenset({
    "begin-cycle", "finish-cycle", "resolve-cycle", "release-lease",
    "record-fabric-phase", "decide-fabric-phase",
    "admit-runtime-attempt",
})
RUNTIME_AUDIT_ERROR_PREFIXES = (
    "runtime_adapter",
    "runtime adapter",
    "runtime attempt",
    "runtime admission",
    "manager runtime",
    "worker runtime",
    "admission-only runtime",
)
_CONTROL_STORE_MODULE: Any | None = None
_OPERATOR_BRIEF_MODULE: Any | None = None
_ACTIVE_CONTROL_STORE_TRANSACTION: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "company_os_control_store_transaction",
    default=None,
)
_ACTIVE_COMMAND_ENVELOPE: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "company_os_command_envelope",
    default=None,
)


class CommandReplay(RuntimeError):
    def __init__(self, result: dict[str, Any]):
        super().__init__("transactional command replay")
        self.result = result


def control_store_module() -> Any:
    """Load the bundled transactional store without relying on PYTHONPATH."""
    global _CONTROL_STORE_MODULE
    if _CONTROL_STORE_MODULE is not None:
        return _CONTROL_STORE_MODULE
    module_path = Path(__file__).resolve().with_name("control_store.py")
    spec = importlib.util.spec_from_file_location("company_os_control_store", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("transactional control store could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CONTROL_STORE_MODULE = module
    return module


def runtime_observation_module() -> Any:
    """Load the bundled observation verifier without relying on PYTHONPATH."""
    module_path = Path(__file__).resolve().with_name("runtime_observations.py")
    spec = importlib.util.spec_from_file_location("company_os_runtime_observations", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("runtime observation verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def operator_brief_module() -> Any:
    """Load the bundled read-only operator presenter without PYTHONPATH."""
    global _OPERATOR_BRIEF_MODULE
    if _OPERATOR_BRIEF_MODULE is not None:
        return _OPERATOR_BRIEF_MODULE
    module_path = Path(__file__).resolve().with_name("operator_brief.py")
    spec = importlib.util.spec_from_file_location("company_os_operator_brief", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("operator brief module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _OPERATOR_BRIEF_MODULE = module
    return module


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def state_path(project: Path) -> Path:
    return project.resolve() / ".company-os" / "control.json"


def template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "instance-template.json"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def empty_execution_fabric(program_version: int) -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "unconfigured",
        "program_version": program_version,
        "work_id": None,
        "cycle_id": None,
        "manifest": None,
        "manifest_digest": None,
        "configured_at": None,
        "managers": {},
        "decisions": [],
        "cancelled_at": None,
        "cancellation_reason": None,
    }


def empty_runtime_adapter(program_version: int) -> dict[str, Any]:
    return {"enabled": False, "status": "disabled", "program_version": program_version,
            "gateway_public_key_env": RUNTIME_GATEWAY_PUBLIC_KEY_ENV,
            "observation_gateway_keyring_env": OBSERVATION_GATEWAY_KEYRING_ENV,
            "phase2_contract_digest": PHASE2_CONTRACT_DIGEST,
            "provider_allowlist": [], "attempts": [], "observation_inboxes": {}}


def observation_expected_attempt(state: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    """Build the exact immutable admission binding expected by the gateway."""
    return {
        "status": attempt.get("status"),
        "admitted_at": attempt.get("admitted_at"),
        "project_id": state.get("instance", {}).get("project_id"),
        "program_version": attempt.get("program_version"),
        "work_id": attempt.get("work_id"),
        "cycle_id": attempt.get("cycle_id"),
        "attempt_id": attempt.get("attempt_id"),
        "parent_runtime_id": attempt.get("parent_runtime_id"),
        "role": attempt.get("role"),
        "requested_model": attempt.get("requested_model"),
        "provider": attempt.get("provider"),
        "surface": attempt.get("surface"),
        "account": attempt.get("account"),
        "provider_task_id": attempt.get("provider_task_id"),
        "fabric_manifest_digest": attempt.get("fabric_manifest_digest"),
        "phase2_contract_digest": attempt.get("phase2_contract_digest"),
    }


def canonical_runtime_scopes(value: Any) -> list[str]:
    """Canonicalize a full lexical scope set using the fabric's NFC/casefold rules."""
    if not isinstance(value, list) or not value:
        raise ValueError("scope must be a non-empty array")
    canonical: list[str] = []
    for raw in value:
        if (
            not isinstance(raw, str) or not raw or raw.startswith("/") or "\\" in raw
            or (len(raw) >= 3 and raw[0].isalpha() and raw[1:3] == ":/")
            or raw != raw.strip() or "//" in raw
        ):
            raise ValueError("scope must contain non-empty relative slash paths without aliases")
        parts = raw.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("scope must not contain empty, dot, or traversal segments")
        item = unicodedata.normalize("NFC", "/".join(parts)).casefold()
        if any(other == item or other.startswith(item + "/") or item.startswith(other + "/") for other in canonical):
            raise ValueError("scope contains duplicate or parent/child collisions")
        canonical.append(item)
    return sorted(canonical)


def runtime_admission_payload(
    args: Any, *, scope: list[str], budget: dict[str, Any], lease: dict[str, Any]
) -> dict[str, Any]:
    """The immutable launch-intent claims, before non-authoritative metadata.

    ``attempt_id`` identifies one execution attempt.  It is deliberately
    distinct from ``manifest_identity_id``: a manifest role can be attempted
    again only in a new governed cycle, while a retry of this launch intent is
    recognized exclusively by its idempotency key and exact payload.
    """
    return {
        "attempt_id": args.attempt_id,
        "manifest_identity_id": args.manifest_identity_id,
        "work_id": args.work_id,
        "cycle_id": args.cycle_id,
        "parent_runtime_id": args.parent_runtime_id,
        "role": args.role,
        "requested_model": args.requested_model,
        "provider": args.provider,
        "surface": args.surface,
        "account": args.account,
        "scope": scope,
        "scope_digest": hashlib.sha256(canonical_json(scope).encode("utf-8")).hexdigest(),
        "budget": budget,
        "fabric_manifest_digest": args.fabric_manifest_digest,
        "phase2_contract_digest": args.contract_digest,
        "idempotency_key": args.idempotency_key,
        "admitted_by": args.admitted_by,
        "lease_fence": {
            "lease_id": lease.get("lease_id"),
            "generation": lease.get("generation"),
            "owner": lease.get("owner"),
            "program_version": lease.get("program_version"),
            "expires_at": lease.get("expires_at"),
            "allowed_transitions": sorted(lease.get("allowed_transitions", [])),
        },
    }


def retained_runtime_admission_payload(attempt: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the exact signed admission intent from a retained record."""
    fields = (
        "attempt_id", "manifest_identity_id", "work_id", "cycle_id", "parent_runtime_id",
        "role", "requested_model", "provider", "surface", "account", "scope", "scope_digest",
        "budget", "fabric_manifest_digest", "phase2_contract_digest", "idempotency_key",
        "admitted_by", "lease_fence",
    )
    return {field: attempt.get(field) for field in fields}


def fabric_validator_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "autonomy-suite"
        / "orchestration"
        / "luna-execution-fabric"
        / "scripts"
        / "validate_fabric.py"
    )


def validate_fabric_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    validator = fabric_validator_path()
    if not validator.is_file():
        return {
            "valid": False,
            "errors": [f"Luna Execution Fabric validator is unavailable: {validator}"],
            "warnings": [],
            "summary": {},
        }
    spec = importlib.util.spec_from_file_location("company_os_luna_fabric_validator", validator)
    if spec is None or spec.loader is None:
        return {
            "valid": False,
            "errors": ["Luna Execution Fabric validator could not be loaded"],
            "warnings": [],
            "summary": {},
        }
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.validate(manifest)
    if not isinstance(result, dict):
        raise ValueError("Luna Execution Fabric validator returned an invalid result")
    return result


def fabric_manifest_digest(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()


def adaptation_proposal_digest(proposal: dict[str, Any]) -> str:
    """Stable digest of every adaptation claim the reviewer is asked to accept."""
    return hashlib.sha256(canonical_json({
        key: proposal.get(key)
        for key in (
            "id", "program_version", "failure_pattern", "hypothesis", "experiment",
            "success_metric", "rollback", "proposer", "time_cap_minutes",
            "cost_cap_usd", "changes", "meta_depth",
        )
    }).encode("utf-8")).hexdigest()


def transition_archive_digest(record: dict[str, Any]) -> str:
    """Digest one immutable program-transition archive without self-reference."""
    payload = deepcopy(record)
    payload.pop("archive_digest", None)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def program_transition_id(source_program_version: int, replacement_program_version: int) -> str:
    return f"program-transition-{source_program_version}-to-{replacement_program_version}"


def runtime_archive_sensitive_paths(value: Any, path: str = "runtime_adapter") -> list[str]:
    """Find provider-secret shaped fields while retaining signed audit grants."""
    sensitive: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if re.search(
                r"(^|_)(private(_key)?|secret|credential|password|api_key|access_token|refresh_token|authorization|cookie|session)(_|$)",
                str(key),
                re.I,
            ):
                sensitive.append(child)
            sensitive.extend(runtime_archive_sensitive_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            sensitive.extend(runtime_archive_sensitive_paths(item, f"{path}[{index}]"))
    return sensitive


def strategy_transition_payload(
    source_strategy: dict[str, Any], replacement_strategy: dict[str, Any]
) -> dict[str, Any]:
    """Bind both complete strategy documents for a deterministic replacement."""
    return {
        "source_strategy": deepcopy(source_strategy),
        "replacement_strategy": deepcopy(replacement_strategy),
    }


def exact_transition_event_binding(
    event_record: dict[str, Any],
    *,
    source_strategy: dict[str, Any],
    replacement_strategy: dict[str, Any],
) -> dict[str, Any]:
    event = event_record.get("event") if isinstance(event_record, dict) else None
    if not isinstance(event, dict):
        raise ValueError("stale transition repair requires the retained transition event")
    strategy_payload = strategy_transition_payload(source_strategy, replacement_strategy)
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("type"),
        "project_id": event.get("project_id"),
        "program_version": event.get("program_version"),
        "old_program_version": event.get("old_program_version"),
        "reason": event.get("reason"),
        "state_revision": event.get("state_revision"),
        "event_payload_sha256": event_record.get("payload_sha256"),
        "strategy_transition": strategy_payload,
        "strategy_transition_digest": hashlib.sha256(
            canonical_json(strategy_payload).encode("utf-8")
        ).hexdigest(),
    }


def reconstruct_legacy_program_replacement(
    source_state: dict[str, Any],
    transition_state: dict[str, Any],
    transition_event: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct the old replace path and reject any unrelated mutation."""
    source_version = source_state.get("strategy", {}).get("program_version")
    replacement_version = transition_state.get("strategy", {}).get("program_version")
    reason = transition_event.get("reason")
    if (
        not isinstance(source_version, int)
        or replacement_version != source_version + 1
        or transition_event.get("type") != "program_replaced"
        or transition_event.get("project_id") != source_state.get("instance", {}).get("project_id")
        or transition_event.get("program_version") != replacement_version
        or transition_event.get("old_program_version") != source_version
        or not isinstance(reason, str)
        or not reason
    ):
        raise ValueError("stale transition repair requires one exact replace-program event")

    source_feedback = source_state.get("feedback", {})
    transition_feedback = transition_state.get("feedback", {})
    old_evidence_archives = source_feedback.get("archived_evidence", [])
    new_evidence_archives = transition_feedback.get("archived_evidence", [])
    old_fabric_archives = source_feedback.get("archived_execution_fabrics", [])
    new_fabric_archives = transition_feedback.get("archived_execution_fabrics", [])
    if (
        not isinstance(old_evidence_archives, list)
        or not isinstance(new_evidence_archives, list)
        or len(new_evidence_archives) != len(old_evidence_archives) + 1
        or new_evidence_archives[:-1] != old_evidence_archives
        or not isinstance(old_fabric_archives, list)
        or not isinstance(new_fabric_archives, list)
        or len(new_fabric_archives) != len(old_fabric_archives) + 1
        or new_fabric_archives[:-1] != old_fabric_archives
    ):
        raise ValueError("stale transition repair found an unrelated transition archive mutation")
    evidence_archive = new_evidence_archives[-1]
    fabric_archive = new_fabric_archives[-1]
    if not isinstance(evidence_archive, dict) or not isinstance(fabric_archive, dict):
        raise ValueError("stale transition repair requires exact transition archives")
    archived_at = evidence_archive.get("archived_at")
    cancelled_at = fabric_archive.get("archived_at")
    if (
        not isinstance(archived_at, str)
        or not archived_at
        or not isinstance(cancelled_at, str)
        or not cancelled_at
    ):
        raise ValueError("stale transition repair requires retained transition timestamps")

    expected = deepcopy(source_state)
    expected_feedback = expected.setdefault("feedback", {})
    expected_feedback.setdefault("archived_evidence", []).append(
        {
            "program_version": source_version,
            "archived_at": archived_at,
            "reason": reason,
            "evidence": deepcopy(source_state.get("evidence", {})),
        }
    )
    expected_feedback.setdefault("archived_execution_fabrics", []).append(
        {
            "program_version": source_version,
            "archived_at": cancelled_at,
            "reason": reason,
            "execution_fabric": deepcopy(source_state.get("execution_fabric")),
        }
    )
    for work in source_state.get("portfolio", {}).get("active_work", []):
        expected["portfolio"].setdefault("cancelled_work", []).append(
            {
                **work,
                "status": "cancelled",
                "cancelled_at": cancelled_at,
                "reason": reason,
            }
        )
    old_lease = source_state.get("controller", {}).get("lease")
    if old_lease:
        expected["controller"].setdefault("revoked_leases", []).append(
            {**old_lease, "revoked_at": cancelled_at, "reason": "program_replaced"}
        )
    expected["controller"]["lease_generation"] += 1
    expected["controller"].update(
        {
            "lease": None,
            "validation": None,
            "validated": False,
            "schedule_enabled": False,
            "cancellation_requested": False,
            "restart_checkpoint": None,
        }
    )
    expected["instance"]["status"] = "paused"
    expected["portfolio"]["active_work"] = []
    expected["portfolio"]["committed_outcomes"] = []
    expected["evidence"] = {key: [] for key in EVIDENCE_BUCKETS}
    expected["phase"] = "reality_audit"
    replacement_strategy = transition_state.get("strategy", {})
    expected["strategy"].update(
        {
            "north_star": replacement_strategy.get("north_star"),
            "current_outcome": replacement_strategy.get("current_outcome"),
            "success_metric": replacement_strategy.get("success_metric"),
            "program_version": replacement_version,
            "program_updated_at": replacement_strategy.get("program_updated_at"),
        }
    )
    expected["strategy"]["program_fingerprint"] = strategy_fingerprint(expected["strategy"])
    expected["execution_fabric"] = empty_execution_fabric(replacement_version)
    expected["runtime_adapter"] = empty_runtime_adapter(replacement_version)
    return expected


def archive_program_transition_state(
    state: dict[str, Any],
    *,
    source_program_version: int,
    replacement_program_version: int,
    archived_at: str,
    reason: str,
    trigger: str,
    source_strategy: dict[str, Any],
    source_runtime_adapter: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Append exact adaptation, scorecard, and runtime snapshots for one boundary."""
    feedback = state.setdefault("feedback", {})
    adaptation_archives = feedback.setdefault("archived_adaptations", [])
    quality_archives = feedback.setdefault("archived_quality_scorecards", [])
    runtime_archives = feedback.setdefault("archived_runtime_adapters", [])
    if (
        not isinstance(adaptation_archives, list)
        or not isinstance(quality_archives, list)
        or not isinstance(runtime_archives, list)
    ):
        raise ValueError("program transition archives must be arrays")
    transition_id = program_transition_id(source_program_version, replacement_program_version)
    if any(
        isinstance(item, dict) and item.get("transition_id") == transition_id
        for item in [*adaptation_archives, *quality_archives, *runtime_archives]
    ):
        raise ValueError("program transition was already archived")
    common = {
        "transition_id": transition_id,
        "source_program_version": source_program_version,
        "replacement_program_version": replacement_program_version,
        "archived_at": archived_at,
        "reason": reason,
        "trigger": trigger,
        "source_strategy_digest": hashlib.sha256(
            canonical_json(source_strategy).encode("utf-8")
        ).hexdigest(),
    }
    adaptation_archive = {
        **common,
        "source_strategy": deepcopy(source_strategy),
        "previous_archive_digest": (
            adaptation_archives[-1].get("archive_digest")
            if adaptation_archives and isinstance(adaptation_archives[-1], dict)
            else None
        ),
        "pending_adaptations": deepcopy(feedback.get("pending_adaptations", [])),
        "applied_adaptations": deepcopy(feedback.get("applied_adaptations", [])),
    }
    adaptation_archive["archive_digest"] = transition_archive_digest(adaptation_archive)
    quality_archive = {
        **common,
        "previous_archive_digest": (
            quality_archives[-1].get("archive_digest")
            if quality_archives and isinstance(quality_archives[-1], dict)
            else None
        ),
        "quality": deepcopy(state.get("quality", {})),
    }
    quality_archive["archive_digest"] = transition_archive_digest(quality_archive)
    sensitive_paths = runtime_archive_sensitive_paths(source_runtime_adapter)
    if sensitive_paths:
        raise ValueError(
            f"runtime adapter contains secret-shaped fields and cannot be archived: {sensitive_paths}"
        )
    runtime_archive = {
        **common,
        "previous_archive_digest": (
            runtime_archives[-1].get("archive_digest")
            if runtime_archives and isinstance(runtime_archives[-1], dict)
            else None
        ),
        "runtime_adapter": deepcopy(source_runtime_adapter),
        "sensitive_paths": [],
    }
    runtime_archive["archive_digest"] = transition_archive_digest(runtime_archive)
    adaptation_archives.append(adaptation_archive)
    quality_archives.append(quality_archive)
    runtime_archives.append(runtime_archive)
    return adaptation_archive, quality_archive, runtime_archive


def audit_archived_evidence_set(
    state: dict[str, Any],
    archive: Any,
    source_program_version: int,
    errors: list[str],
    *,
    label: str,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Revalidate immutable evidence and return every retained authority actor."""
    actors: set[str] = set()
    evidence_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(archive, dict):
        errors.append(f"{label} must be an object")
        return evidence_by_id, actors
    if archive.get("program_version") != source_program_version:
        errors.append(f"{label} belongs to the wrong program")
    parse_time(archive.get("archived_at"), f"{label}.archived_at", errors)
    if not isinstance(archive.get("reason"), str) or not archive["reason"].strip():
        errors.append(f"{label}.reason is required")
    evidence = archive.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != set(EVIDENCE_BUCKETS):
        errors.append(f"{label}.evidence must define every governed bucket exactly once")
        return evidence_by_id, actors
    project_id = state.get("instance", {}).get("project_id")
    project_root = Path(str(state.get("instance", {}).get("project_root", ""))).resolve()
    seen_ids: set[str] = set()
    for bucket in EVIDENCE_BUCKETS:
        records = evidence.get(bucket)
        if not isinstance(records, list):
            errors.append(f"{label}.evidence.{bucket} must be an array")
            continue
        for index, item in enumerate(records):
            item_label = f"{label}.evidence.{bucket}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must be an object")
                continue
            evidence_id = item.get("id")
            if not isinstance(evidence_id, str) or not evidence_id:
                errors.append(f"{item_label}.id is required")
            elif evidence_id in seen_ids:
                errors.append(f"{item_label}.id is duplicated")
            else:
                seen_ids.add(evidence_id)
                evidence_by_id[evidence_id] = item
            if item.get("active", True) is not True:
                errors.append(f"{item_label} must preserve active source evidence")
            if item.get("outcome") != bucket:
                errors.append(f"{item_label}.outcome must be {bucket}")
            if item.get("project_id") != project_id:
                errors.append(f"{item_label} is not bound to this project")
            if item.get("program_version") != source_program_version:
                errors.append(f"{item_label} is not bound to the archived program")
            for field in ("source", "decision_impact", "author", "reviewer"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    errors.append(f"{item_label}.{field} is required")
            author = item.get("author")
            reviewer = item.get("reviewer")
            if isinstance(author, str) and author:
                actors.add(author)
            if isinstance(reviewer, str) and reviewer:
                actors.add(reviewer)
            if author and author == reviewer:
                errors.append(f"{item_label} lacks independent review")
            if evidence_snapshot_fields(item):
                digest = item.get("snapshot_sha256")
                snapshot = project_local_path(project_root, item.get("snapshot_path"))
                expected = (
                    evidence_snapshot_path(project_root, digest)
                    if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
                    else None
                )
                if (
                    expected is None
                    or snapshot != expected
                    or item.get("artifact_path") != item.get("snapshot_path")
                    or item.get("artifact_sha256") != digest
                ):
                    errors.append(f"{item_label} snapshot identity is not the exact content address")
                elif snapshot is None or snapshot.is_symlink() or not snapshot.is_file():
                    errors.append(f"{item_label} snapshot does not exist as an immutable file")
                elif sha256_file(snapshot) != digest:
                    errors.append(f"{item_label} snapshot digest does not match its bytes")
                source_path = item.get("source_artifact_path")
                if (
                    not isinstance(source_path, str)
                    or not source_path.strip()
                    or project_local_path(project_root, source_path) is None
                ):
                    errors.append(f"{item_label}.source_artifact_path must stay inside the project")
            else:
                digest = item.get("artifact_sha256")
                artifact = project_local_path(project_root, item.get("artifact_path"))
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    errors.append(f"{item_label}.artifact_sha256 must be a lowercase SHA-256")
                elif artifact is None or artifact.is_symlink() or not artifact.is_file():
                    errors.append(f"{item_label}.artifact_path does not exist as a project-local file")
                elif sha256_file(artifact) != digest:
                    errors.append(f"{item_label}.artifact_sha256 does not match the artifact")
            parse_time(item.get("observed_at"), f"{item_label}.observed_at", errors)
            freshness_days = item.get("freshness_days")
            if not isinstance(freshness_days, int) or isinstance(freshness_days, bool) or not 1 <= freshness_days <= 365:
                errors.append(f"{item_label}.freshness_days must be from 1 to 365")
            dimensions = item.get("quality_dimensions", [])
            if (
                not isinstance(dimensions, list)
                or len(dimensions) != len(set(dimensions))
                or any(name not in BASE_DIMENSIONS for name in dimensions)
            ):
                errors.append(f"{item_label}.quality_dimensions is not a unique governed dimension set")
            for field in ("outcome_id", "work_id", "cycle_id", "rubric_version"):
                if field in item and (not isinstance(item[field], str) or not item[field].strip()):
                    errors.append(f"{item_label}.{field} must be a non-empty string when supplied")
            for grant_name, actor_field in (
                ("reviewer_grant", "reviewer"),
                ("declarant_grant", "declarant"),
                ("adjudicator_grant", "adjudicator"),
            ):
                grant = item.get(grant_name)
                if grant is None:
                    continue
                grant_actor = (grant.get("claims") or {}).get("actor") if isinstance(grant, dict) else None
                if isinstance(grant_actor, str) and grant_actor:
                    actors.add(grant_actor)
                audit_stored_grant(
                    state,
                    grant,
                    errors,
                    f"{item_label}.{grant_name}",
                    {"actor": item.get(actor_field)},
                    expected_program_version=source_program_version,
                )
    return evidence_by_id, actors


def prepare_stale_program_transition_repair(
    state: dict[str, Any],
    *,
    source_state: dict[str, Any],
    transition_event_record: dict[str, Any],
    source_state_revision: int,
    source_state_digest: str,
    transition_state_revision: int,
    transition_state_digest: str,
) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    """Build the sole eligible mechanical repair without introducing authority."""
    current_version = state.get("strategy", {}).get("program_version")
    if not isinstance(current_version, int) or current_version < 2:
        raise ValueError("stale transition repair requires a replacement program")
    source_version = current_version - 1
    if (
        not isinstance(source_state_revision, int)
        or source_state_revision < 1
        or not isinstance(transition_state_revision, int)
        or transition_state_revision != source_state_revision + 1
        or not isinstance(source_state_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_state_digest)
        or not isinstance(transition_state_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", transition_state_digest)
    ):
        raise ValueError("stale transition repair requires exact contiguous state revisions")
    source_strategy = source_state.get("strategy") if isinstance(source_state, dict) else None
    if (
        not isinstance(source_state, dict)
        or source_state.get("instance", {}).get("project_id") != state.get("instance", {}).get("project_id")
        or not isinstance(source_strategy, dict)
        or source_strategy.get("program_version") != source_version
        or source_strategy.get("program_fingerprint") != strategy_fingerprint(source_strategy)
    ):
        raise ValueError("stale transition repair requires the exact prior strategy snapshot")
    transition_event = transition_event_record.get("event") if isinstance(transition_event_record, dict) else None
    event_binding = exact_transition_event_binding(
        transition_event_record,
        source_strategy=source_strategy,
        replacement_strategy=state.get("strategy", {}),
    )
    if (
        not isinstance(transition_event, dict)
        or event_binding.get("event_type") != "program_replaced"
        or event_binding.get("project_id") != state.get("instance", {}).get("project_id")
        or event_binding.get("program_version") != current_version
        or event_binding.get("old_program_version") != source_version
        or event_binding.get("state_revision") != transition_state_revision
        or not isinstance(event_binding.get("event_id"), str)
        or not event_binding["event_id"]
        or not isinstance(event_binding.get("event_payload_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", event_binding["event_payload_sha256"])
        or event_binding.get("strategy_transition_digest")
        != hashlib.sha256(
            canonical_json(event_binding.get("strategy_transition")).encode("utf-8")
        ).hexdigest()
    ):
        raise ValueError("stale transition repair requires the exact retained replace-program event")
    if reconstruct_legacy_program_replacement(source_state, state, transition_event) != state:
        raise ValueError("stale transition repair refuses an unrelated transition mutation")
    if state.get("schema_version") != SCHEMA_VERSION or state.get("core_version") != CORE_VERSION:
        raise ValueError("stale transition repair requires the current controller schema")
    if state.get("instance", {}).get("status") != "paused":
        raise ValueError("stale transition repair requires a paused instance")
    controller_state = state.get("controller", {})
    if controller_state.get("schedule_enabled") is not False:
        raise ValueError("stale transition repair requires scheduling to be disabled")
    if controller_state.get("lease") is not None:
        raise ValueError("stale transition repair refuses a live lease")
    feedback = state.get("feedback", {})
    if feedback.get("cycles") != []:
        raise ValueError("stale transition repair refuses retained cycle work")
    portfolio = state.get("portfolio", {})
    if portfolio.get("active_work") != [] or portfolio.get("committed_outcomes") != []:
        raise ValueError("stale transition repair refuses active or committed work")
    if any(items != [] for items in state.get("evidence", {}).values()):
        raise ValueError("stale transition repair refuses live evidence")
    fabric = state.get("execution_fabric", {})
    if (
        fabric.get("program_version") != current_version
        or fabric.get("status") != "unconfigured"
        or fabric.get("cycle_id") is not None
        or fabric.get("work_id") is not None
        or fabric.get("managers") not in ({}, None)
    ):
        raise ValueError("stale transition repair refuses configured execution work")
    runtime = state.get("runtime_adapter", {})
    if (
        runtime.get("program_version") != current_version
        or runtime.get("status") != "disabled"
        or runtime.get("enabled") is not False
        or runtime.get("attempts") != []
    ):
        raise ValueError("stale transition repair refuses runtime work")

    pending = feedback.get("pending_adaptations", [])
    applied = feedback.get("applied_adaptations", [])
    if not isinstance(pending, list) or not isinstance(applied, list) or not (pending or applied):
        raise ValueError("stale transition repair requires prior-program adaptations")
    if any(
        not isinstance(item, dict) or item.get("program_version") != source_version
        for item in [*pending, *applied]
    ):
        raise ValueError("stale transition repair accepts only the immediately prior program adaptations")

    quality = state.get("quality", {})
    dimensions = quality.get("dimensions", {})
    if not isinstance(dimensions, dict) or set(dimensions) != set(BASE_DIMENSIONS):
        raise ValueError("stale transition repair requires the complete quality scorecard")
    scored = [item for item in dimensions.values() if isinstance(item, dict) and item.get("score") is not None]
    if not scored:
        raise ValueError("stale transition repair requires a prior-program scored quality card")
    for item in scored:
        grants = (item.get("scorer_grant"), item.get("reviewer_grant"))
        if any(
            not isinstance(grant, dict)
            or not isinstance(grant.get("claims"), dict)
            or grant["claims"].get("program_version") != source_version
            for grant in grants
        ):
            raise ValueError("stale transition repair accepts only prior-program quality authority")

    evidence_archives = [
        item
        for item in feedback.get("archived_evidence", [])
        if isinstance(item, dict) and item.get("program_version") == source_version
    ]
    if len(evidence_archives) != 1:
        raise ValueError("stale transition repair requires one exact prior-program evidence archive")
    evidence_archive = evidence_archives[0]
    archived_at = evidence_archive.get("archived_at")
    reason = evidence_archive.get("reason")
    if not isinstance(archived_at, str) or not archived_at or not isinstance(reason, str) or not reason:
        raise ValueError("stale transition repair requires the original transition time and reason")
    if reason != event_binding.get("reason"):
        raise ValueError("stale transition repair reason does not match the retained transition event")
    archived_evidence_errors: list[str] = []
    _, evidence_actors = audit_archived_evidence_set(
        state,
        evidence_archive,
        source_version,
        archived_evidence_errors,
        label=f"archived evidence program {source_version}",
    )
    if archived_evidence_errors:
        raise ValueError(
            "stale transition repair requires audit-valid archived evidence: "
            + "; ".join(archived_evidence_errors)
        )

    candidate = deepcopy(state)
    candidate_feedback = candidate.setdefault("feedback", {})
    candidate_feedback.setdefault("archived_adaptations", [])
    candidate_feedback.setdefault("archived_quality_scorecards", [])
    candidate_feedback.setdefault("archived_runtime_adapters", [])
    candidate_feedback.setdefault("program_transition_repairs", [])
    adaptation_archive, quality_archive, runtime_archive = archive_program_transition_state(
        candidate,
        source_program_version=source_version,
        replacement_program_version=current_version,
        archived_at=archived_at,
        reason=reason,
        trigger="stale_transition_repair",
        source_strategy=source_strategy,
        source_runtime_adapter=source_state.get("runtime_adapter", {}),
    )
    candidate_feedback["pending_adaptations"] = []
    candidate_feedback["applied_adaptations"] = []
    clear_quality_scores(candidate)
    candidate_state_digest = governance_digest(candidate)
    payload = {
        "transition_id": adaptation_archive["transition_id"],
        "source_program_version": source_version,
        "replacement_program_version": current_version,
        "reason": reason,
        "adaptation_archive_digest": adaptation_archive["archive_digest"],
        "quality_archive_digest": quality_archive["archive_digest"],
        "runtime_archive_digest": runtime_archive["archive_digest"],
        "candidate_state_digest": candidate_state_digest,
        "source_state_revision": source_state_revision,
        "source_state_digest": source_state_digest,
        "transition_state_revision": transition_state_revision,
        "transition_state_digest": transition_state_digest,
        "transition_event": event_binding,
    }
    affected_actors: set[str] = set()
    for item in [*pending, *applied]:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("proposer"), str) and item["proposer"]:
            affected_actors.add(item["proposer"])
        grant_actor = (item.get("reviewer_grant") or {}).get("claims", {}).get("actor")
        if isinstance(grant_actor, str) and grant_actor:
            affected_actors.add(grant_actor)
    for item in dimensions.values():
        if not isinstance(item, dict):
            continue
        for grant_name in ("scorer_grant", "reviewer_grant"):
            grant_actor = (item.get(grant_name) or {}).get("claims", {}).get("actor")
            if isinstance(grant_actor, str) and grant_actor:
                affected_actors.add(grant_actor)
    affected_actors.update(evidence_actors)
    return candidate, payload, affected_actors


def fabric_phase_decision_payload(
    state: dict[str, Any],
    manager_id: str,
    phase: str,
    decision: str,
) -> dict[str, Any]:
    fabric = state.get("execution_fabric", {})
    manager = fabric.get("managers", {}).get(manager_id, {})
    reports = manager.get("reports", [])
    latest_report = reports[-1] if reports else {}
    return {
        "manifest_digest": fabric.get("manifest_digest"),
        "manager_id": manager_id,
        "phase": phase,
        "report_digest": latest_report.get("report_digest"),
        "decision": decision,
        "rework_rounds": manager.get("rework_rounds", 0),
    }


def strategy_fingerprint(strategy: dict[str, Any]) -> str:
    protected = {
        "north_star": strategy.get("north_star"),
        "current_outcome": strategy.get("current_outcome"),
        "success_metric": strategy.get("success_metric"),
        "constraints": strategy.get("constraints", []),
        "non_goals": strategy.get("non_goals", []),
        "program_version": strategy.get("program_version"),
    }
    return hashlib.sha256(canonical_json(protected).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: Any, field: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        errors.append(f"{field} must be timezone-aware ISO-8601")
        return None


def finite_nonnegative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def require_current_lease(state: dict[str, Any], args: argparse.Namespace, action: str) -> dict[str, Any]:
    """Require an exact, unexpired, program-bound lease before mutation."""
    lease = state.get("controller", {}).get("lease")
    if not isinstance(lease, dict):
        raise ValueError("an authoritative lease is required")
    if lease.get("lease_id") != getattr(args, "lease_id", None) or lease.get("generation") != getattr(args, "generation", None):
        raise ValueError("lease token is stale or does not own the controller")
    if lease.get("owner") != getattr(args, "owner", None):
        raise ValueError("lease owner does not match the caller")
    if lease.get("program_version") != state.get("strategy", {}).get("program_version"):
        raise ValueError("lease belongs to a stale program")
    expires_errors: list[str] = []
    expires = parse_time(lease.get("expires_at"), "controller.lease.expires_at", expires_errors)
    if expires_errors or not expires or expires <= datetime.now(timezone.utc):
        raise ValueError("lease is expired")
    allowed = lease.get("allowed_transitions")
    if not isinstance(allowed, list) or action not in allowed:
        raise ValueError(f"lease does not permit {action}")
    return lease


def require_running_cycle_lease_fence(state: dict[str, Any], args: argparse.Namespace, cycle_id: Any) -> dict[str, Any]:
    cycle = next(
        (item for item in state.get("feedback", {}).get("cycles", [])
         if isinstance(item, dict) and item.get("id") == cycle_id),
        None,
    )
    if (
        not cycle or cycle.get("status") != "running"
        or cycle.get("lease_id") != args.lease_id
        or cycle.get("lease_generation") != args.generation
    ):
        raise ValueError("running cycle is fenced by a different lease; recover it explicitly")
    return cycle


def lease_recovery_fences(lease: dict[str, Any]) -> set[tuple[Any, Any]]:
    fences = {(lease.get("lease_id"), lease.get("generation"))}
    for item in lease.get("recovery_chain", []):
        if isinstance(item, dict):
            fences.add((item.get("lease_id"), item.get("generation")))
    return fences


def project_local_path(project: Path, relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    resolved_project = project.resolve()
    resolved = (resolved_project / relative).resolve()
    try:
        resolved.relative_to(resolved_project)
    except ValueError:
        return None
    return resolved


EVIDENCE_SNAPSHOT_ROOT = ".company-os/evidence/sha256"


def evidence_is_active(item: dict[str, Any]) -> bool:
    """Omitted flags describe legacy records, which remain current until replaced."""
    return item.get("active", True) is True


def evidence_snapshot_path(project: Path, digest: str) -> Path:
    return project.resolve() / EVIDENCE_SNAPSHOT_ROOT / digest


def _snapshot_relative_path(project: Path, digest: str) -> str:
    return str(evidence_snapshot_path(project, digest).relative_to(project.resolve()))


def publish_evidence_snapshot(project: Path, content: bytes, digest: str) -> str:
    """Durably publish immutable evidence without replacing an existing digest.

    A crash before the state transaction leaves only an orphan blob.  It is not
    authoritative because no governed evidence record references it.
    """
    if _bytes_sha256(content) != digest:
        raise ValueError("evidence snapshot digest does not match its content")
    directory = project.resolve() / EVIDENCE_SNAPSHOT_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or directory.resolve() != directory:
        raise ValueError("evidence snapshot directory must not traverse a symlink")
    target = evidence_snapshot_path(project, digest)

    def verify_target() -> bool:
        if target.is_symlink() or not target.is_file():
            raise ValueError("content-addressed evidence snapshot is not an immutable regular file")
        if sha256_file(target) != digest:
            raise ValueError("content-addressed evidence snapshot bytes do not match its digest")
        return True

    if target.exists():
        verify_target()
        return _snapshot_relative_path(project, digest)
    temporary = directory / f".{digest}.{uuid.uuid4().hex}.tmp"
    try:
        _write_bytes_fsync(temporary, content)
        try:
            # link(2) has create-if-absent semantics.  Unlike replace(), it
            # cannot make a malicious or racing writer's bytes authoritative.
            os.link(temporary, target)
        except FileExistsError:
            verify_target()
        else:
            verify_target()
        _fsync_directory(directory)
    finally:
        if temporary.exists():
            temporary.unlink()
    return _snapshot_relative_path(project, digest)


def evidence_snapshot_fields(item: dict[str, Any]) -> bool:
    return "snapshot_path" in item or "snapshot_sha256" in item


def governance_digest(state: dict[str, Any]) -> str:
    """Hash all governable state, excluding only self-referential or live lease fields."""
    return control_store_module().governance_digest(state)


def evidence_digest(state: dict[str, Any]) -> str:
    """Backward-compatible name for the full governable-state digest."""
    return governance_digest(state)


def command_payload_hash(command: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json({"command": command, "payload": payload}).encode("utf-8")).hexdigest()


def quality_command_payload(values: Any) -> dict[str, Any]:
    getter = values.get if isinstance(values, dict) else lambda key, default=None: getattr(values, key, default)
    payload = {
        "dimension": getter("dimension"),
        "score": getter("score"),
        "evidence_ids": sorted(getter("evidence_ids", []) or []),
        "rubric_version": getter("rubric_version"),
        "scored_by": getter("scored_by"),
        "reviewed_by": getter("reviewed_by"),
        "outcome_id": getter("outcome_id"),
        "work_id": getter("work_id"),
        "cycle_id": getter("cycle_id"),
    }
    evidence_digest = getter("evidence_digest")
    if evidence_digest is not None:
        payload["evidence_digest"] = evidence_digest
    else:
        # Retain the v1 payload shape so historical signed grants remain
        # independently auditable. New scores use the complete evidence-set
        # digest instead of pretending several artifacts share one hash.
        payload["artifact_digest"] = getter("artifact_digest")
    return payload


def evidence_records_digest(
    evidence_by_id: dict[str, dict[str, Any]], evidence_ids: list[str]
) -> str:
    payload = [
        {
            key: evidence_by_id.get(evidence_id, {}).get(key)
            for key in (
                "id", "artifact_path", "artifact_sha256", "outcome_id",
                "work_id", "cycle_id", "rubric_version",
            )
        }
        for evidence_id in sorted(evidence_ids)
    ]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def completion_evidence_digest(state: dict[str, Any], evidence_ids: list[str]) -> str:
    evidence_by_id: dict[str, dict[str, Any]] = {
        item.get("id"): item
        for bucket in state.get("evidence", {}).values()
        for item in bucket
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    return evidence_records_digest(evidence_by_id, evidence_ids)


def finish_command_payload(state: dict[str, Any], values: Any) -> dict[str, Any]:
    getter = values.get if isinstance(values, dict) else lambda key, default=None: getattr(values, key, default)
    evidence_ids = sorted(getter("evidence_ids", []) or [])
    visibility = getter("user_visible_movement")
    if isinstance(visibility, str):
        visibility = visibility == "true"
    generation = getter("generation")
    if generation is None:
        generation = getter("lease_generation")
    cycle_id = getter("cycle_id")
    if cycle_id is None:
        cycle_id = getter("id")
    return {
        "cycle_id": cycle_id,
        "lease_id": getter("lease_id"),
        "generation": generation,
        "actual_outcome": getter("actual_outcome"),
        "evidence_ids": evidence_ids,
        "evidence_digest": completion_evidence_digest(state, evidence_ids),
        "cost_usd": getter("cost_usd"),
        "latency_minutes": getter("latency_minutes"),
        "token_usage": getter("token_usage"),
        "user_visible_movement": visibility,
        "work_disposition": getter("work_disposition"),
        "reviewer_decision": getter("reviewer_decision"),
        "reviewer": getter("reviewer"),
        "commit": getter("commit"),
        "ref": getter("ref"),
    }


def certification_command_payload(state: dict[str, Any], reviewer: str) -> dict[str, Any]:
    return {"governance_digest": governance_digest(state), "reviewer": reviewer, "decision": "accepted"}


def queue_command_payload(values: Any) -> dict[str, Any]:
    getter = values.get if isinstance(values, dict) else lambda key, default=None: getattr(values, key, default)
    primary = getter("primary")
    if isinstance(primary, str):
        primary = primary == "true"
    return {
        key: getter(key)
        for key in (
            "id", "type", "title", "user_visible_outcome", "claimed_progress", "owner",
            "outcome_id", "incident_ref", "severity", "justification", "incident_actor", "approval_actor",
            "repeat_override_reason", "repeat_override_reviewer",
        )
    } | {
        "primary": primary,
        "unlocks": sorted(getter("unlocks", []) or []),
        "execution_mode": getter("execution_mode", "single") or "single",
    }


def retained_queue_command_payload(work: dict[str, Any]) -> dict[str, Any]:
    approval = work.get("approval") if isinstance(work.get("approval"), dict) else {}
    repeat_override = (
        work.get("repeat_override") if isinstance(work.get("repeat_override"), dict) else {}
    )
    return queue_command_payload(
        {
            "id": work.get("id"),
            "type": work.get("type"),
            "title": work.get("title"),
            "user_visible_outcome": work.get("user_visible_outcome"),
            "claimed_progress": work.get("claimed_progress"),
            "owner": work.get("owner"),
            "primary": work.get("queued_primary"),
            "outcome_id": work.get("outcome_id"),
            "unlocks": work.get("unlocks", []),
            "incident_ref": work.get("incident_ref"),
            "severity": work.get("severity"),
            "justification": work.get("justification"),
            "incident_actor": work.get("incident_actor"),
            "approval_actor": approval.get("approved_by"),
            "repeat_override_reason": repeat_override.get("reason"),
            "repeat_override_reviewer": repeat_override.get("reviewer"),
            "execution_mode": work.get("execution_mode", "single"),
        }
    )


def protected_launcher_attestation() -> tuple[bool, str]:
    """Return the external launcher trust state.

    The local controller intentionally has no setting, token, file, or environment
    variable that can turn this on: an unrestricted scheduler could replace any of
    those. Deployment infrastructure must interpose a protected launcher and
    attest that boundary outside this process.
    """
    return (
        False,
        "external prerequisite: a protected launcher must verify issuer and scheduler authority outside this controller",
    )


def work_fingerprint(work: dict[str, Any]) -> str:
    def normalized(value: Any) -> Any:
        if isinstance(value, str):
            text = unicodedata.normalize("NFKC", value).casefold()
            text = "".join(character if character.isalnum() else " " for character in text)
            return " ".join(text.split())
        if isinstance(value, list):
            return sorted(normalized(item) for item in value)
        return value

    defaults = {"unlocks": [], "execution_mode": "single"}
    payload = {
        key: normalized(work.get(key, defaults.get(key)))
        for key in (
            "type",
            "outcome_id",
            "title",
            "user_visible_outcome",
            "claimed_progress",
            "unlocks",
            "execution_mode",
        )
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def completion_digest(work: dict[str, Any], cycle: dict[str, Any]) -> str:
    payload = {
        "work": {key: value for key, value in work.items() if key not in {"status", "completed_at", "completion", "completion_digest", "completion_cycle_id"}},
        "cycle": {key: value for key, value in cycle.items() if key != "completion_digest"},
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verify_asymmetric_signature(
    encoded_payload: str,
    encoded_signature: str,
    *,
    verification_key_pem: str | None = None,
) -> None:
    public_key_bytes: bytes
    if verification_key_pem is None:
        public_key_value = os.environ.get(ACTOR_PUBLIC_KEY_ENV)
        if not public_key_value:
            raise ValueError(f"{ACTOR_PUBLIC_KEY_ENV} is required for governed operations")
        public_key = Path(public_key_value).resolve()
        if not public_key.is_file():
            raise ValueError("configured actor-grant public key does not exist")
        public_key_bytes = public_key.read_bytes()
    else:
        public_key_bytes = verification_key_pem.encode("utf-8")
    try:
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        with tempfile.NamedTemporaryFile() as payload_file, tempfile.NamedTemporaryFile() as signature_file, tempfile.NamedTemporaryFile() as public_key_file:
            payload_file.write(encoded_payload.encode("ascii"))
            payload_file.flush()
            signature_file.write(signature)
            signature_file.flush()
            public_key_file.write(public_key_bytes)
            public_key_file.flush()
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", public_key_file.name, "-signature", signature_file.name, payload_file.name],
                capture_output=True,
                check=False,
            )
        if result.returncode != 0:
            raise ValueError
    except (OSError, ValueError, TypeError):
        raise ValueError("actor grant is malformed or has an invalid asymmetric signature") from None


def verify_actor_grant(
    state: dict[str, Any],
    grant: str,
    actor: str,
    action: str,
    *,
    resource: str,
    work_id: str,
    cycle_id: str,
    dimension: str,
    decision: str,
    payload_hash: str,
    consume: bool = True,
) -> dict[str, Any]:
    if not isinstance(grant, str) or not grant:
        raise ValueError("actor grant is required")
    try:
        encoded, signature = grant.split(".", 1)
        verify_asymmetric_signature(encoded, signature)
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    except (AttributeError, ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("actor grant is malformed or has an invalid asymmetric signature") from None
    expected = {
        "actor": actor,
        "action": action,
        "resource": resource,
        "project_id": state.get("instance", {}).get("project_id"),
        "program_version": state.get("strategy", {}).get("program_version"),
        "work_id": work_id,
        "cycle_id": cycle_id,
        "dimension": dimension,
        "decision": decision,
        "payload_hash": payload_hash,
    }
    if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("actor grant claims do not match this governed operation")
    grant_errors: list[str] = []
    expires = parse_time(payload.get("expiry"), "actor grant expiry", grant_errors)
    if grant_errors or not expires or (consume and expires <= datetime.now(timezone.utc)):
        raise ValueError("actor grant is expired")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise ValueError("actor grant lacks a nonce")
    consumed = state.setdefault("controller", {}).setdefault("consumed_grant_nonces", [])
    if consume and nonce in consumed:
        raise ValueError("actor grant nonce was already consumed")
    if consume:
        consumed.append(nonce)
    verification_key_path = Path(os.environ[ACTOR_PUBLIC_KEY_ENV]).resolve()
    verification_key_pem = verification_key_path.read_text(encoding="utf-8")
    return {
        "actor": actor,
        "claims": payload,
        "token": grant,
        "grant_digest": hashlib.sha256(grant.encode()).hexdigest(),
        "verification_key_pem": verification_key_pem,
        "verification_key_sha256": hashlib.sha256(verification_key_pem.encode("utf-8")).hexdigest(),
    }


def audit_stored_grant(
    state: dict[str, Any], grant: Any, errors: list[str], label: str,
    expected_claims: dict[str, Any] | None = None,
    *,
    expected_program_version: int | None = None,
) -> str:
    if not isinstance(grant, dict) or not isinstance(grant.get("claims"), dict) or not grant.get("token"):
        errors.append(f"{label} lacks a full signed grant")
        return "invalid"
    claims = grant["claims"]
    if claims.get("nonce") not in state.get("controller", {}).get("consumed_grant_nonces", []):
        errors.append(f"{label} nonce was not consumed")
        return "invalid"
    if expected_claims and any(claims.get(key) != value for key, value in expected_claims.items()):
        errors.append(f"{label} claims do not match the governed record")
        return "invalid"
    required_program = state.get("strategy", {}).get("program_version") if expected_program_version is None else expected_program_version
    if (
        claims.get("actor") != grant.get("actor")
        or claims.get("project_id") != state.get("instance", {}).get("project_id")
        or claims.get("program_version") != required_program
    ):
        errors.append(f"{label} claims do not match the governed project or program")
        return "invalid"
    token = grant["token"]
    if grant.get("grant_digest") != hashlib.sha256(token.encode()).hexdigest():
        errors.append(f"{label} grant digest does not match its token")
        return "invalid"
    try:
        encoded, signature = token.split(".", 1)
        token_claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if token_claims != claims:
            raise ValueError("stored claims differ from signed token")
        verification_key_pem = grant.get("verification_key_pem")
        verification_key_sha256 = grant.get("verification_key_sha256")
        if isinstance(verification_key_pem, str):
            if verification_key_sha256 != hashlib.sha256(verification_key_pem.encode("utf-8")).hexdigest():
                raise ValueError("stored verification-key digest does not match")
            verify_asymmetric_signature(encoded, signature, verification_key_pem=verification_key_pem)
            return "cryptographic"
        if os.environ.get(ACTOR_PUBLIC_KEY_ENV):
            try:
                verify_asymmetric_signature(encoded, signature)
            except ValueError:
                # A valid historical grant may have been issued before key
                # rotation. Without its retained old public key, do not call it
                # cryptographically replay-verified and do not make history
                # depend on the currently configured issuer.
                return "retained_legacy"
            else:
                return "current_issuer"
        # Legacy accepted records did not retain their public verification key.
        # Their token digest, exact claims, consumed nonce, and transactional
        # revision chain remain auditable, but cryptographic replay is impossible.
        return "retained_legacy"
    except ValueError as exc:
        errors.append(f"{label} is not audit-valid: {exc}")
        return "invalid"


def applicable_quality_dimensions(state: dict[str, Any]) -> set[str]:
    """Return the deterministic quality gate for the current phase and primary work."""
    active_work = state.get("portfolio", {}).get("active_work", [])
    primary = next(
        (item for item in active_work if isinstance(item, dict) and item.get("primary")),
        None,
    )
    if primary is None:
        return set()
    dimensions = set(PHASE_QUALITY_DIMENSIONS.get(state.get("phase"), set()))
    # Work-specific delivery checks are meaningful only once something can be
    # delivered or verified. This keeps production gates out of prototypes.
    if primary and state.get("phase") in {"delivery", "verification", "learning"}:
        dimensions.update(DELIVERY_WORK_QUALITY_DIMENSIONS.get(primary.get("type"), set()))
    # A typed P0 is the sole existing interruption path and is always safety-gated.
    if primary and primary.get("type") == "p0":
        dimensions.update(DELIVERY_WORK_QUALITY_DIMENSIONS["p0"])
    return dimensions


def primary_work(state: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in state.get("portfolio", {}).get("active_work", [])
            if isinstance(item, dict) and item.get("primary")
        ),
        None,
    )


def current_quality_checkpoint(state: dict[str, Any]) -> tuple[str, str, str]:
    work = primary_work(state)
    if not work:
        return ("", "", "")
    accepted_cycles = [
        cycle
        for cycle in state.get("feedback", {}).get("cycles", [])
        if isinstance(cycle, dict)
        and cycle.get("work_id") == work.get("id")
        and cycle.get("status") == "completed"
        and cycle.get("reviewer_decision") == "accepted"
    ]
    checkpoint = (
        str(accepted_cycles[-1].get("id"))
        if accepted_cycles
        else f"checkpoint:{state.get('phase')}:{state.get('strategy', {}).get('program_version')}:{work.get('work_fingerprint')}"
    )
    return (str(work.get("outcome_id") or ""), str(work.get("id") or ""), checkpoint)


def clear_quality_scores(state: dict[str, Any]) -> None:
    for item in state.get("quality", {}).get("dimensions", {}).values():
        if not isinstance(item, dict):
            continue
        for field in ("score", "rubric_version", "scored_by", "reviewed_by", "scorer_grant", "reviewer_grant", "binding"):
            item[field] = None
        item["evidence"] = []


def clear_quality_scores_citing(state: dict[str, Any], evidence_id: str) -> None:
    """Invalidate only scores whose proof set includes superseded evidence."""
    for item in state.get("quality", {}).get("dimensions", {}).values():
        if not isinstance(item, dict) or evidence_id not in item.get("evidence", []):
            continue
        for field in ("score", "rubric_version", "scored_by", "reviewed_by", "scorer_grant", "reviewer_grant", "binding"):
            item[field] = None
        item["evidence"] = []


def supersede_evidence_review_payload(
    args: Any,
    *,
    predecessor: dict[str, Any],
    replacement_id: str,
    artifact_digest: str,
    bucket: str,
    source_artifact_path: str,
) -> dict[str, Any]:
    getter = args.get if isinstance(args, dict) else lambda key, default=None: getattr(args, key, default)
    def replacement_value(key: str) -> Any:
        value = getter(key)
        return predecessor.get(key) if value is None else value

    return {
        "evidence_id": getter("evidence_id"),
        "old_artifact_sha256": predecessor.get("artifact_sha256"),
        "replacement_evidence_id": replacement_id,
        "new_artifact_sha256": artifact_digest,
        "outcome": bucket,
        "source_artifact_path": source_artifact_path,
        "source": getter("source"), "decision_impact": getter("decision_impact"),
        "author": getter("author"), "reviewer": getter("reviewer"), "reason": getter("reason"),
        "freshness_days": replacement_value("freshness_days"),
        "quality_dimensions": replacement_value("quality_dimensions"),
        "outcome_id": replacement_value("outcome_id"),
        "work_id": replacement_value("work_id"),
        "cycle_id": replacement_value("cycle_id"),
        "rubric_version": replacement_value("rubric_version"),
        "id": replacement_id,
    }


def evidence_record_digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def corrected_evidence_record(
    args: Any,
    *,
    predecessor: dict[str, Any],
    replacement_id: str,
    replacement_digest: str,
    source_artifact_path: str,
) -> dict[str, Any]:
    getter = args.get if isinstance(args, dict) else lambda key, default=None: getattr(args, key, default)
    snapshot_path = f"{EVIDENCE_SNAPSHOT_ROOT}/{replacement_digest}"
    return {
        **{
            key: deepcopy(predecessor.get(key))
            for key in ("outcome", "project_id", "program_version", "quality_dimensions", "outcome_id", "work_id", "cycle_id", "rubric_version")
            if key in predecessor
        },
        "id": replacement_id,
        "artifact_path": snapshot_path,
        "source_artifact_path": source_artifact_path,
        "artifact_sha256": replacement_digest,
        "snapshot_path": snapshot_path,
        "snapshot_sha256": replacement_digest,
        "active": True,
        "observed_at": getter("transition_at"),
        "freshness_days": getter("freshness_days"),
        "source": getter("source"),
        "decision_impact": getter("decision_impact"),
        "author": getter("declarant"),
        "reviewer": getter("adjudicator"),
        "supersedes_evidence_id": getter("evidence_id"),
        "correction_type": "git_commit_identity",
        "corrected_claim_path": "/commit",
    }


def correct_evidence_review_payload(
    args: Any,
    *,
    predecessor: dict[str, Any],
    replacement_id: str,
    replacement_digest: str,
    bucket: str,
    source_artifact_path: str,
) -> dict[str, Any]:
    getter = args.get if isinstance(args, dict) else lambda key, default=None: getattr(args, key, default)
    replacement = corrected_evidence_record(
        args,
        predecessor=predecessor,
        replacement_id=replacement_id,
        replacement_digest=replacement_digest,
        source_artifact_path=source_artifact_path,
    )
    return {
        "evidence_id": getter("evidence_id"),
        "predecessor_record_digest": evidence_record_digest(predecessor),
        "old_artifact_sha256": predecessor.get("artifact_sha256"),
        "replacement_evidence_id": replacement_id,
        "new_artifact_sha256": replacement_digest,
        "replacement_record_digest": evidence_record_digest(replacement),
        "project_id": predecessor.get("project_id"),
        "program_version": predecessor.get("program_version"),
        "outcome": bucket,
        "source_artifact_path": source_artifact_path,
        "source": getter("source"),
        "decision_impact": getter("decision_impact"),
        "reason": getter("reason"),
        "transition_at": getter("transition_at"),
        "correction_type": "git_commit_identity",
        "claim_path": "/commit",
        "old_value": getter("old_value"),
        "new_value": getter("new_value"),
        "verification": {
            "method": "git_rev_parse_commit",
            "resolved_commit": getter("new_value"),
        },
        "author": getter("declarant"),
        "reviewer": getter("adjudicator"),
        "freshness_days": getter("freshness_days"),
        "quality_dimensions": predecessor.get("quality_dimensions"),
        "outcome_id": predecessor.get("outcome_id"),
        "work_id": predecessor.get("work_id"),
        "cycle_id": predecessor.get("cycle_id"),
        "rubric_version": predecessor.get("rubric_version"),
        "id": replacement_id,
    }


def validate_fabric_report_payload(
    state: dict[str, Any],
    manager_id: str,
    phase: str,
    report: dict[str, Any],
    *,
    valid_evidence_ids: set[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    fabric = state.get("execution_fabric", {})
    work_id = fabric.get("work_id")
    cycle_id = fabric.get("cycle_id")
    if report.get("message_type") != "manager_phase_report":
        errors.append("message_type must be manager_phase_report")
    if report.get("program_id") != state.get("instance", {}).get("project_id"):
        errors.append("program_id must match the Company OS project")
    if report.get("program_version") != state.get("strategy", {}).get("program_version"):
        errors.append("program_version must match the Company OS program")
    if report.get("manager_id") != manager_id:
        errors.append("manager_id must match the governed manager")
    if report.get("phase") != phase:
        errors.append("phase must match the manager phase")
    if report.get("cycle_id") != cycle_id or not cycle_id:
        errors.append("cycle_id must match the running Company OS cycle")
    if report.get("status") != "ready_for_decision":
        errors.append("status must be ready_for_decision")
    if report.get("outcome_state") not in {"on_track", "at_risk", "blocked"}:
        errors.append("outcome_state must be on_track, at_risk, or blocked")
    for field in ("artifacts", "evidence_ids", "next_plan"):
        value = report.get(field)
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            errors.append(f"{field} must contain at least one non-empty value")
    for field in ("plan_variance", "dependencies", "risks"):
        value = report.get(field)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            errors.append(f"{field} must be a list of non-empty strings")
    if report.get("requested_decision") not in FABRIC_DECISIONS:
        errors.append("requested_decision is invalid")

    usage = report.get("usage")
    token_usage_fields = {
        "luna_tokens", "terra_tokens", "manager_sol_tokens", "reviewer_sol_tokens",
    }
    required_usage = token_usage_fields | {"elapsed_minutes"}
    if not isinstance(usage, dict):
        errors.append("usage must be an object")
    else:
        for field in required_usage:
            value = usage.get(field)
            if field in token_usage_fields and not nonnegative_integer(value):
                errors.append(f"usage.{field} must be a non-negative integer")
            elif field == "elapsed_minutes" and not finite_nonnegative_number(value):
                errors.append(f"usage.{field} must be a finite non-negative number")

    metrics = report.get("worker_metrics")
    required_metrics = {"accepted_first_pass", "reworked", "failed", "collisions"}
    if not isinstance(metrics, dict):
        errors.append("worker_metrics must be an object")
    else:
        for field in required_metrics:
            value = metrics.get(field)
            if not nonnegative_integer(value):
                errors.append(f"worker_metrics.{field} must be a non-negative integer")
        if metrics.get("collisions", 0) != 0:
            errors.append("worker write collisions require pause or rework")
        result_fields = ("accepted_first_pass", "reworked", "failed")
        if (
            phase in {"execution", "verification", "integration"}
            and all(nonnegative_integer(metrics.get(field)) for field in result_fields)
            and sum(metrics[field] for field in result_fields) < 1
        ):
            errors.append(f"{phase} must report at least one worker result")

    evidence_ids = report.get("evidence_ids", [])
    if isinstance(evidence_ids, list):
        for evidence_id in evidence_ids:
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                continue
            evidence = evidence_by_id.get(evidence_id)
            if evidence_id not in valid_evidence_ids or not evidence:
                errors.append(f"evidence id {evidence_id} is not valid Company OS evidence")
                continue
            if (
                evidence.get("program_version") != state.get("strategy", {}).get("program_version")
                or evidence.get("work_id") != work_id
                or evidence.get("cycle_id") != cycle_id
            ):
                errors.append(f"evidence id {evidence_id} is not bound to this fabric cycle")

    if phase == "verification":
        review = report.get("independent_review")
        if not isinstance(review, dict):
            errors.append("verification requires an independent_review object")
        else:
            if review.get("model") != "gpt-5.6-sol":
                errors.append("independent_review.model must be gpt-5.6-sol")
            if (
                not isinstance(review.get("reviewer"), str)
                or not review["reviewer"].strip()
                or review.get("reviewer") == manager_id
            ):
                errors.append("verification requires a distinct independent reviewer")
            if review.get("decision") != "accepted":
                errors.append("independent verification must be accepted")
            if not isinstance(review.get("evidence"), list) or not review["evidence"]:
                errors.append("independent verification requires evidence")
    return errors


def current_fabric_evidence(
    state: dict[str, Any],
    project: Path,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    evidence_by_id = {
        item.get("id"): item
        for bucket in state.get("evidence", {}).values()
        for item in bucket
        if isinstance(item, dict) and evidence_is_active(item) and isinstance(item.get("id"), str)
    }
    now = datetime.now(timezone.utc)
    valid: set[str] = set()
    for evidence_id, item in evidence_by_id.items():
        artifact = project_local_path(project, item.get("snapshot_path")) if evidence_snapshot_fields(item) else project_local_path(project, item.get("artifact_path"))
        expected_digest = item.get("snapshot_sha256") if evidence_snapshot_fields(item) else item.get("artifact_sha256")
        time_errors: list[str] = []
        observed = parse_time(item.get("observed_at"), "fabric evidence observed_at", time_errors)
        freshness = item.get("freshness_days")
        if (
            item.get("project_id") == state.get("instance", {}).get("project_id")
            and item.get("program_version") == state.get("strategy", {}).get("program_version")
            and artifact is not None
            and not artifact.is_symlink()
            and artifact.is_file()
            and expected_digest == sha256_file(artifact)
            and not time_errors
            and observed is not None
            and isinstance(freshness, int)
            and 1 <= freshness <= 365
            and observed <= now
            and now - observed <= timedelta(days=freshness)
            and isinstance(item.get("source"), str)
            and bool(item["source"].strip())
            and isinstance(item.get("decision_impact"), str)
            and bool(item["decision_impact"].strip())
            and isinstance(item.get("author"), str)
            and isinstance(item.get("reviewer"), str)
            and item.get("author") != item.get("reviewer")
        ):
            valid.add(evidence_id)
    return evidence_by_id, valid


def validate_execution_fabric_state(
    state: dict[str, Any],
    *,
    project_root: Path,
    valid_evidence_ids: set[str],
    evidence_by_id: dict[str, dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    fabric = state.get("execution_fabric")
    if not isinstance(fabric, dict):
        errors.append("execution_fabric must be an object")
        return {"ready_for_schedule": False, "accepted": False, "luna_token_share": None}

    status = fabric.get("status")
    if status not in FABRIC_STATUSES:
        errors.append("execution_fabric.status is invalid")
    if fabric.get("program_version") != state.get("strategy", {}).get("program_version"):
        errors.append("execution_fabric belongs to a stale program")

    if status == "unconfigured":
        if fabric.get("enabled"):
            errors.append("an unconfigured execution_fabric cannot be enabled")
        for field in ("work_id", "cycle_id", "manifest", "manifest_digest", "configured_at"):
            if fabric.get(field) is not None:
                errors.append(f"unconfigured execution_fabric.{field} must be null")
        if fabric.get("managers") not in ({}, None):
            errors.append("unconfigured execution_fabric.managers must be empty")
        return {"ready_for_schedule": False, "accepted": False, "luna_token_share": None}

    if not fabric.get("enabled"):
        errors.append("a configured execution_fabric must be enabled")
    manifest = fabric.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("execution_fabric.manifest must be an object")
        manifest = {}
    elif fabric.get("manifest_digest") != fabric_manifest_digest(manifest):
        errors.append("execution_fabric.manifest_digest does not match the manifest")
    manifest_artifact = project_local_path(project_root, fabric.get("manifest_path"))
    if manifest_artifact is None or not manifest_artifact.is_file():
        errors.append("execution_fabric.manifest_path must be a project-local file")
    elif fabric.get("manifest_sha256") != sha256_file(manifest_artifact):
        errors.append("execution_fabric.manifest_sha256 does not match")
    manifest_report = validate_fabric_manifest(manifest)
    if not manifest_report.get("valid"):
        errors.extend(
            f"execution_fabric manifest: {error}"
            for error in manifest_report.get("errors", ["validation failed"])
        )
    warnings.extend(
        f"execution_fabric manifest: {warning}"
        for warning in manifest_report.get("warnings", [])
    )
    if manifest.get("program_id") != state.get("instance", {}).get("project_id"):
        errors.append("execution_fabric manifest program_id must match the project")
    if manifest.get("program_version") != state.get("strategy", {}).get("program_version"):
        errors.append("execution_fabric manifest belongs to a stale program")
    if manifest.get("program_contract", {}).get("north_star") != state.get("strategy", {}).get("north_star"):
        errors.append("execution_fabric manifest north_star must match Company OS strategy")

    all_work = [
        item
        for bucket in ("active_work", "completed_work", "cancelled_work")
        for item in state.get("portfolio", {}).get(bucket, [])
        if isinstance(item, dict)
    ]
    work = next((item for item in all_work if item.get("id") == fabric.get("work_id")), None)
    if not work:
        errors.append("execution_fabric.work_id must reference governed work")
    else:
        if work.get("execution_mode", "single") != "luna_fabric":
            errors.append("execution_fabric work must use execution_mode luna_fabric")
        if manifest.get("outcome") != work.get("user_visible_outcome"):
            errors.append("execution_fabric outcome must match the governed user-visible outcome")

    if not fabric.get("configured_at"):
        errors.append("configured execution_fabric.configured_at is required")
    else:
        parse_time(fabric.get("configured_at"), "execution_fabric.configured_at", errors)

    managers = fabric.get("managers")
    manifest_managers = {
        manager.get("id"): manager
        for manager in manifest.get("managers", [])
        if isinstance(manager, dict) and isinstance(manager.get("id"), str)
    }
    if not isinstance(managers, dict) or set(managers) != set(manifest_managers):
        errors.append("execution_fabric.managers must match the validated manifest")
        managers = {}

    total_usage = {
        "luna_tokens": 0.0,
        "terra_tokens": 0.0,
        "manager_sol_tokens": 0.0,
        "reviewer_sol_tokens": 0.0,
    }
    for manager_id, manager in managers.items():
        label = f"execution_fabric.managers.{manager_id}"
        if not isinstance(manager, dict):
            errors.append(f"{label} must be an object")
            continue
        if manager.get("id") != manager_id:
            errors.append(f"{label}.id must match its key")
        if manager.get("status") not in {
            "pending",
            "awaiting_decision",
            "ready",
            "paused",
            "terminated",
            "accepted",
        }:
            errors.append(f"{label}.status is invalid")
        next_phase = manager.get("next_phase")
        if next_phase is not None and next_phase not in FABRIC_PHASES:
            errors.append(f"{label}.next_phase is invalid")
        rework_rounds = manager.get("rework_rounds")
        if not isinstance(rework_rounds, int) or not 0 <= rework_rounds <= 2:
            errors.append(f"{label}.rework_rounds must be from 0 to 2")
        reports = manager.get("reports")
        decisions = manager.get("decisions")
        if not isinstance(reports, list):
            errors.append(f"{label}.reports must be an array")
            reports = []
        if not isinstance(decisions, list):
            errors.append(f"{label}.decisions must be an array")
            decisions = []
        for report_index, entry in enumerate(reports):
            entry_label = f"{label}.reports[{report_index}]"
            if not isinstance(entry, dict) or not isinstance(entry.get("report"), dict):
                errors.append(f"{entry_label} must contain a report object")
                continue
            report = entry["report"]
            phase = entry.get("phase")
            if entry.get("report_digest") != hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest():
                errors.append(f"{entry_label}.report_digest does not match")
            artifact = project_local_path(project_root, entry.get("report_path"))
            if artifact is None or not artifact.is_file():
                errors.append(f"{entry_label}.report_path is not a project-local file")
            elif entry.get("report_sha256") != sha256_file(artifact):
                errors.append(f"{entry_label}.report_sha256 does not match")
            errors.extend(
                f"{entry_label}: {error}"
                for error in validate_fabric_report_payload(
                    state,
                    manager_id,
                    str(phase),
                    report,
                    valid_evidence_ids=valid_evidence_ids,
                    evidence_by_id=evidence_by_id,
                )
            )
            for field in total_usage:
                value = report.get("usage", {}).get(field, 0)
                if finite_nonnegative_number(value):
                    total_usage[field] += float(value)
        for decision_index, decision in enumerate(decisions):
            decision_label = f"{label}.decisions[{decision_index}]"
            if not isinstance(decision, dict):
                errors.append(f"{decision_label} must be an object")
                continue
            expected_payload = {
                "manifest_digest": fabric.get("manifest_digest"),
                "manager_id": manager_id,
                "phase": decision.get("phase"),
                "report_digest": decision.get("report_digest"),
                "decision": decision.get("decision"),
                "rework_rounds": decision.get("rework_rounds_before"),
            }
            if decision.get("payload") != expected_payload:
                errors.append(f"{decision_label}.payload does not match retained state")
            audit_stored_grant(
                state,
                decision.get("master_grant"),
                errors,
                f"{decision_label}.master_grant",
                {
                    "actor": decision.get("decided_by"),
                    "action": "fabric-phase-decision",
                    "resource": f"fabric:{manager_id}:{decision.get('phase')}",
                    "work_id": str(fabric.get("work_id")),
                    "cycle_id": str(fabric.get("cycle_id")),
                    "dimension": "execution-fabric",
                    "decision": str(decision.get("decision")),
                    "payload_hash": command_payload_hash("fabric-phase-decision", expected_payload),
                },
            )
        expected_phase: str | None = "charter"
        expected_status = "pending"
        counted_rework = 0
        report_digests = {
            entry.get("report_digest")
            for entry in reports
            if isinstance(entry, dict)
        }
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            if decision.get("phase") != expected_phase:
                errors.append(f"{label}.decisions do not follow the six phase barriers")
                break
            if decision.get("report_digest") not in report_digests:
                errors.append(f"{label}.decision does not reference a retained phase report")
            selected = decision.get("decision")
            if selected == "rework":
                counted_rework += 1
                expected_status = "ready"
            elif selected == "continue":
                if expected_phase == "integration":
                    expected_phase = None
                    expected_status = "accepted"
                else:
                    expected_phase = FABRIC_PHASES[FABRIC_PHASES.index(str(expected_phase)) + 1]
                    expected_status = "ready"
            elif selected == "pause":
                expected_status = "paused"
                break
            elif selected == "terminate":
                expected_status = "terminated"
                break
        undecided_reports = [
            entry
            for entry in reports
            if isinstance(entry, dict)
            and entry.get("report_digest")
            not in {
                decision.get("report_digest")
                for decision in decisions
                if isinstance(decision, dict)
            }
        ]
        if len(undecided_reports) > 1:
            errors.append(f"{label} has multiple reports awaiting a master decision")
        if undecided_reports:
            if undecided_reports[0].get("phase") != expected_phase:
                errors.append(f"{label} has a report outside the current phase barrier")
            expected_status = "awaiting_decision"
        if manager.get("next_phase") != expected_phase:
            errors.append(f"{label}.next_phase does not match its decision history")
        if manager.get("status") != expected_status:
            errors.append(f"{label}.status does not match its decision history")
        if manager.get("rework_rounds") != counted_rework:
            errors.append(f"{label}.rework_rounds does not match its decisions")

    model_tokens = sum(total_usage.values())
    luna_share = total_usage["luna_tokens"] / model_tokens if model_tokens > 0 else None
    if status == "accepted" and luna_share is None:
        errors.append("accepted execution_fabric lacks measured model usage")
    elif status == "accepted" and luna_share < 0.70:
        warnings.append("accepted execution_fabric used less than 70 percent Luna tokens")
    if status == "accepted" and any(
        manager.get("status") != "accepted" for manager in managers.values()
    ):
        errors.append("execution_fabric cannot be accepted before every manager")
    if status == "cancelled" and not fabric.get("cancelled_at"):
        errors.append("cancelled execution_fabric requires cancelled_at")
    ready_for_schedule = bool(
        fabric.get("enabled")
        and status == "ready"
        and fabric.get("cycle_id") is None
        and work
        and work.get("status") == "ready"
    )
    return {
        "ready_for_schedule": ready_for_schedule,
        "accepted": status == "accepted",
        "luna_token_share": luna_share,
    }


def _write_bytes_fsync(path: Path, value: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _transaction_marker_path(project: Path) -> Path:
    return project.resolve() / ".company-os" / "pending-state-event-transaction.json"


def _stage_state_event_transaction(
    project: Path,
    path: Path,
    state: dict[str, Any],
    event: dict[str, Any],
) -> Path:
    """Durably stage one state/event pair before either target is replaced."""
    directory = project.resolve() / ".company-os"
    transaction_id = uuid.uuid4().hex
    state_temp = directory / f".control.{transaction_id}.next"
    events_temp = directory / f".events.{transaction_id}.next"
    marker = _transaction_marker_path(project)
    if marker.exists():
        raise ValueError("a pending state/event transaction requires recovery")
    state_bytes = (json.dumps(state, indent=2) + "\n").encode("utf-8")
    events_path = directory / "events.jsonl"
    existing_events = events_path.read_bytes() if events_path.exists() else b""
    event_bytes = (json.dumps(event, sort_keys=True) + "\n").encode("utf-8")
    next_events = existing_events + event_bytes
    _write_bytes_fsync(state_temp, state_bytes)
    _write_bytes_fsync(events_temp, next_events)
    atomic_write_json(
        marker,
        {
            "schema": "company-os.state-event-transaction.v1",
            "transaction_id": transaction_id,
            "state_temp": state_temp.name,
            "events_temp": events_temp.name,
            "state_sha256": _bytes_sha256(state_bytes),
            "events_sha256": _bytes_sha256(next_events),
        },
    )
    _fsync_directory(directory)
    return marker


def _recover_state_event_transaction(project: Path) -> bool:
    """Finish a staged pair after a crash; never guess or discard ambiguity."""
    project = project.resolve()
    directory = project / ".company-os"
    marker = _transaction_marker_path(project)
    if not marker.exists():
        return False
    transaction = load_json(marker)
    required = {
        "schema", "transaction_id", "state_temp", "events_temp",
        "state_sha256", "events_sha256",
    }
    if set(transaction) != required or transaction.get("schema") != "company-os.state-event-transaction.v1":
        raise ValueError("pending state/event transaction marker is invalid")
    targets = (
        ("state_temp", "state_sha256", directory / "control.json"),
        ("events_temp", "events_sha256", directory / "events.jsonl"),
    )
    for temp_field, digest_field, target in targets:
        temp_name = transaction.get(temp_field)
        expected_digest = transaction.get(digest_field)
        if (
            not isinstance(temp_name, str)
            or Path(temp_name).name != temp_name
            or not temp_name.startswith(".")
            or not isinstance(expected_digest, str)
            or len(expected_digest) != 64
        ):
            raise ValueError("pending state/event transaction contains invalid paths or digests")
        if target.is_file() and sha256_file(target) == expected_digest:
            continue
        staged = directory / temp_name
        if not staged.is_file() or sha256_file(staged) != expected_digest:
            raise ValueError("pending state/event transaction cannot be recovered without exact staged bytes")
        os.replace(staged, target)
        _fsync_directory(directory)
    marker.unlink()
    for temp_field in ("state_temp", "events_temp"):
        staged = directory / str(transaction[temp_field])
        if staged.exists():
            staged.unlink()
    _fsync_directory(directory)
    return True


@contextmanager
def locked_state(project: Path, *, require_issuer: bool = True) -> Iterator[tuple[Path, dict[str, Any]]]:
    project = project.resolve()
    path = state_path(project)
    store_module = control_store_module()
    if not path.exists() and not store_module.exists(project):
        raise FileNotFoundError(f"no Company OS instance at {path}")
    if require_issuer:
        issuer = os.environ.get(ACTOR_PUBLIC_KEY_ENV)
        if not issuer or not Path(issuer).resolve().is_file():
            raise ValueError(f"{ACTOR_PUBLIC_KEY_ENV} must reference an external issuer public key")
    lock_path = project / ".company-os" / "control.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        # Resolve the authority only after acquiring the migration/controller
        # lock. A waiter must never continue on legacy JSON after another
        # process has committed the SQLite migration.
        store_exists = store_module.exists(project)
        if store_exists:
            transaction = None
            token = None
            succeeded = False
            try:
                store_report = store_module.audit(project)
                if not store_report["ok"]:
                    raise ValueError(
                        "transactional control store failed integrity audit: "
                        + "; ".join(store_report["errors"])
                    )
                store_module.repair_exports(project)
                transaction = store_module.begin(project)
                token = _ACTIVE_CONTROL_STORE_TRANSACTION.set(transaction)
                command = _ACTIVE_COMMAND_ENVELOPE.get()
                if command is not None:
                    retained = transaction.idempotency_lookup(
                        scope="controller-cli",
                        key=command["key"],
                        payload_sha256=command["payload_sha256"],
                    )
                    if retained is not None:
                        raise CommandReplay(retained["result"])
                yield path, transaction.state
                succeeded = True
            finally:
                if token is not None:
                    _ACTIVE_CONTROL_STORE_TRANSACTION.reset(token)
                if transaction is not None:
                    transaction.close(succeeded)
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        else:
            try:
                if _ACTIVE_COMMAND_ENVELOPE.get() is not None:
                    raise ValueError(
                        "migrate the legacy instance before running a mutating keyed command"
                    )
                _recover_state_event_transaction(project)
                state = load_json(path)
                yield path, state
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def persist_state_event(
    project: Path,
    path: Path,
    state: dict[str, Any],
    event_type: str,
    **event_fields: Any,
) -> None:
    event = {
        "at": utc_now(),
        "type": event_type,
        "project_id": state["instance"]["project_id"],
        "program_version": state["strategy"]["program_version"],
        **event_fields,
    }
    store_transaction = _ACTIVE_CONTROL_STORE_TRANSACTION.get()
    if store_transaction is not None:
        if store_transaction.project != project.resolve():
            raise ValueError("active transactional control store belongs to another project")
        command = _ACTIVE_COMMAND_ENVELOPE.get()
        if command is not None:
            event["command_envelope"] = {
                "name": command["name"],
                "key": command["key"],
                "payload_sha256": command["payload_sha256"],
            }
        revision = store_transaction.stage(state, event)
        if command is not None:
            store_transaction.record_idempotency(
                scope="controller-cli",
                key=command["key"],
                command_name=command["name"],
                payload_sha256=command["payload_sha256"],
                result={
                    "ok": True,
                    "command": command["name"],
                    "command_key": command["key"],
                    "event_type": event_type,
                    "state_revision": revision,
                    "event": event_fields,
                },
                created_at=event["at"],
            )
        return
    _stage_state_event_transaction(project, path, state, event)
    _recover_state_event_transaction(project)


def init_instance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    if not project.is_dir():
        print(json.dumps({"ok": False, "errors": [f"project directory does not exist: {project}"]}))
        return 2
    target = state_path(project)
    if target.exists():
        print(json.dumps({"ok": False, "errors": [f"instance already exists: {target}"]}))
        return 2

    state = deepcopy(load_json(template_path()))
    project_type = args.project_type if args.project_type in DEPARTMENT_PRESETS else "general"
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:12]
    state["instance"].update(
        {
            "project_id": f"{slugify(args.name)}-{digest}",
            "name": args.name,
            "project_root": str(project),
            "project_type": project_type,
            "status": "paused",
            "created_at": utc_now(),
        }
    )
    state["strategy"].update(
        {
            "north_star": args.north_star,
            "program_version": 1,
            "program_updated_at": utc_now(),
        }
    )
    state["strategy"]["program_fingerprint"] = strategy_fingerprint(state["strategy"])
    state["profile"]["departments"] = DEPARTMENT_PRESETS[project_type]
    state["profile"]["methods"] = ["discovery", "iterative_delivery", "stage_gates"]
    state["quality"]["dimensions"] = {
        name: {
            "critical": critical,
            "applicable": True,
            "score": None,
            "evidence": [],
            "rubric_version": None,
            "scored_by": None,
            "reviewed_by": None,
        }
        for name, critical in BASE_DIMENSIONS.items()
    }
    state["schema_version"] = SCHEMA_VERSION
    state["core_version"] = CORE_VERSION
    target.parent.mkdir(parents=True, exist_ok=False)
    initialized_at = utc_now()
    event = {
        "at": initialized_at,
        "type": "instance_initialized",
        "project_id": state["instance"]["project_id"],
        "program_version": state["strategy"]["program_version"],
        "core_version": state["core_version"],
    }
    control_store_module().initialize(project, state, event)
    print(json.dumps({"ok": True, "path": str(target), "project_id": state["instance"]["project_id"]}))
    return 0


def audit_archived_program_transitions(
    state: dict[str, Any], errors: list[str]
) -> None:
    """Reconstruct archived transition authority under each original program."""
    feedback = state.get("feedback", {})
    adaptation_archives = feedback.get("archived_adaptations", [])
    quality_archives = feedback.get("archived_quality_scorecards", [])
    runtime_archives = feedback.get("archived_runtime_adapters", [])
    repairs = feedback.get("program_transition_repairs", [])
    for name, collection in (
        ("archived_adaptations", adaptation_archives),
        ("archived_quality_scorecards", quality_archives),
        ("archived_runtime_adapters", runtime_archives),
        ("program_transition_repairs", repairs),
    ):
        if not isinstance(collection, list):
            errors.append(f"feedback.{name} must be an array")
            return

    adaptation_by_transition: dict[str, dict[str, Any]] = {}
    previous_digest: str | None = None
    required_adaptation_fields = (
        "id", "failure_pattern", "hypothesis", "experiment", "success_metric",
        "rollback", "proposer", "time_cap_minutes", "cost_cap_usd", "program_version",
    )
    for index, archive in enumerate(adaptation_archives):
        label = f"feedback.archived_adaptations[{index}]"
        if not isinstance(archive, dict):
            errors.append(f"{label} must be an object")
            continue
        transition_id = archive.get("transition_id")
        source_version = archive.get("source_program_version")
        replacement_version = archive.get("replacement_program_version")
        if not isinstance(transition_id, str) or not transition_id:
            errors.append(f"{label} lacks transition_id")
            continue
        if transition_id in adaptation_by_transition:
            errors.append(f"{label} duplicates transition_id {transition_id}")
        adaptation_by_transition[transition_id] = archive
        if (
            not isinstance(source_version, int)
            or not isinstance(replacement_version, int)
            or replacement_version != source_version + 1
            or transition_id != program_transition_id(source_version, replacement_version)
        ):
            errors.append(f"{label} has an invalid program boundary")
        if archive.get("trigger") not in {"program_replaced", "stale_transition_repair"}:
            errors.append(f"{label} has an invalid trigger")
        if archive.get("previous_archive_digest") != previous_digest:
            errors.append(f"{label} breaks the append-only digest chain")
        if archive.get("archive_digest") != transition_archive_digest(archive):
            errors.append(f"{label} archive digest is invalid")
        previous_digest = archive.get("archive_digest")
        source_strategy = archive.get("source_strategy")
        expected_strategy_digest = (
            hashlib.sha256(canonical_json(source_strategy).encode("utf-8")).hexdigest()
            if isinstance(source_strategy, dict)
            else None
        )
        if (
            not isinstance(source_strategy, dict)
            or source_strategy.get("program_version") != source_version
            or source_strategy.get("program_fingerprint") != strategy_fingerprint(source_strategy)
            or archive.get("source_strategy_digest") != expected_strategy_digest
        ):
            errors.append(f"{label} lacks an audit-valid source strategy snapshot")
        seen_ids: set[str] = set()
        for collection_name, allowed_statuses in (
            ("pending_adaptations", {"proposed"}),
            ("applied_adaptations", {"applied", "rejected"}),
        ):
            proposals = archive.get(collection_name)
            if not isinstance(proposals, list):
                errors.append(f"{label}.{collection_name} must be an array")
                continue
            for proposal in proposals:
                proposal_label = f"{label}.{collection_name} adaptation {proposal.get('id') if isinstance(proposal, dict) else None}"
                if not isinstance(proposal, dict):
                    errors.append(f"{proposal_label} must be an object")
                    continue
                proposal_id = proposal.get("id")
                if not isinstance(proposal_id, str) or proposal_id in seen_ids:
                    errors.append(f"{proposal_label} has a missing or duplicate id")
                else:
                    seen_ids.add(proposal_id)
                if proposal.get("status") not in allowed_statuses:
                    errors.append(f"{proposal_label} has an invalid status")
                if proposal.get("program_version") != source_version:
                    errors.append(f"{proposal_label} does not belong to its archived program")
                for field in required_adaptation_fields:
                    if proposal.get(field) in (None, ""):
                        errors.append(f"{proposal_label} lacks {field}")
                if proposal.get("meta_depth") != 1:
                    errors.append(f"{proposal_label} exceeds the meta-loop depth")
                if proposal.get("proposal_digest") != adaptation_proposal_digest(proposal):
                    errors.append(f"{proposal_label} proposal digest is invalid")
                if not nonnegative_integer(proposal.get("time_cap_minutes")):
                    errors.append(f"{proposal_label} time_cap_minutes is invalid")
                if not finite_nonnegative_number(proposal.get("cost_cap_usd")):
                    errors.append(f"{proposal_label} cost_cap_usd is invalid")
                protected = set(proposal.get("changes", [])) & PROTECTED_ADAPTATION_FIELDS
                if protected:
                    errors.append(f"{proposal_label} changes protected fields: {sorted(protected)}")
                if collection_name == "pending_adaptations":
                    if any(
                        proposal.get(field) not in (None, "")
                        for field in ("reviewer", "review_decision", "reviewed_at", "reviewer_grant")
                    ):
                        errors.append(f"{proposal_label} carries reviewed authority")
                    continue
                expected_decision = "accepted" if proposal.get("status") == "applied" else "rejected"
                if (
                    not proposal.get("reviewer")
                    or proposal.get("reviewer") == proposal.get("proposer")
                    or proposal.get("review_decision") != expected_decision
                ):
                    errors.append(f"{proposal_label} lacks an independent matching review")
                audit_stored_grant(
                    state,
                    proposal.get("reviewer_grant"),
                    errors,
                    f"{proposal_label} reviewer grant",
                    {
                        "actor": proposal.get("reviewer"),
                        "action": "review-adaptation",
                        "resource": f"adaptation:{proposal_id}",
                        "work_id": "",
                        "cycle_id": "",
                        "dimension": "meta-loop",
                        "decision": expected_decision,
                        "payload_hash": command_payload_hash(
                            "review-adaptation",
                            {
                                "adaptation_id": proposal_id,
                                "proposal_digest": proposal.get("proposal_digest"),
                                "reviewer": proposal.get("reviewer"),
                                "decision": expected_decision,
                            },
                        ),
                    },
                    expected_program_version=source_version,
                )

    evidence_archives_by_program: dict[int, list[dict[str, Any]]] = {}
    for archive in feedback.get("archived_evidence", []):
        if isinstance(archive, dict) and isinstance(archive.get("program_version"), int):
            evidence_archives_by_program.setdefault(archive["program_version"], []).append(archive)

    runtime_by_transition: dict[str, dict[str, Any]] = {}
    previous_digest = None
    for index, archive in enumerate(runtime_archives):
        label = f"feedback.archived_runtime_adapters[{index}]"
        if not isinstance(archive, dict):
            errors.append(f"{label} must be an object")
            continue
        transition_id = archive.get("transition_id")
        source_version = archive.get("source_program_version")
        replacement_version = archive.get("replacement_program_version")
        if not isinstance(transition_id, str) or not transition_id:
            errors.append(f"{label} lacks transition_id")
            continue
        if transition_id in runtime_by_transition:
            errors.append(f"{label} duplicates transition_id {transition_id}")
        runtime_by_transition[transition_id] = archive
        if (
            not isinstance(source_version, int)
            or not isinstance(replacement_version, int)
            or replacement_version != source_version + 1
            or transition_id != program_transition_id(source_version, replacement_version)
        ):
            errors.append(f"{label} has an invalid program boundary")
        if archive.get("previous_archive_digest") != previous_digest:
            errors.append(f"{label} breaks the append-only digest chain")
        if archive.get("archive_digest") != transition_archive_digest(archive):
            errors.append(f"{label} archive digest is invalid")
        previous_digest = archive.get("archive_digest")
        paired = adaptation_by_transition.get(transition_id)
        for field in (
            "source_program_version", "replacement_program_version", "archived_at",
            "reason", "trigger", "source_strategy_digest",
        ):
            if not isinstance(paired, dict) or archive.get(field) != paired.get(field):
                errors.append(f"{label} does not match its adaptation archive {field}")
        runtime_snapshot = archive.get("runtime_adapter")
        if not isinstance(runtime_snapshot, dict):
            errors.append(f"{label} lacks the exact runtime adapter snapshot")
            continue
        if runtime_snapshot.get("program_version") != source_version:
            errors.append(f"{label} runtime adapter belongs to the wrong program")
        sensitive_paths = runtime_archive_sensitive_paths(runtime_snapshot)
        if archive.get("sensitive_paths") != [] or sensitive_paths:
            errors.append(f"{label} retains secret-shaped runtime fields")
        attempts = runtime_snapshot.get("attempts")
        inboxes = runtime_snapshot.get("observation_inboxes")
        if not isinstance(attempts, list) or not isinstance(inboxes, dict):
            errors.append(f"{label} runtime attempts and observation inboxes are not preserved")
        else:
            attempt_ids = {
                item.get("attempt_id")
                for item in attempts
                if isinstance(item, dict) and isinstance(item.get("attempt_id"), str)
            }
            if len(attempt_ids) != len(attempts) or set(inboxes) != attempt_ids:
                errors.append(f"{label} runtime attempt/inbox identity is inconsistent")
            for attempt in attempts:
                if not isinstance(attempt, dict) or attempt.get("program_version") != source_version:
                    errors.append(f"{label} retains a runtime attempt outside its source program")
                    continue
                grant = attempt.get("actor_grant")
                audit_stored_grant(
                    state,
                    grant,
                    errors,
                    f"{label} runtime admission grant",
                    expected_program_version=source_version,
                )

    quality_by_transition: dict[str, dict[str, Any]] = {}
    previous_digest = None
    for index, archive in enumerate(quality_archives):
        label = f"feedback.archived_quality_scorecards[{index}]"
        if not isinstance(archive, dict):
            errors.append(f"{label} must be an object")
            continue
        transition_id = archive.get("transition_id")
        source_version = archive.get("source_program_version")
        replacement_version = archive.get("replacement_program_version")
        if not isinstance(transition_id, str) or not transition_id:
            errors.append(f"{label} lacks transition_id")
            continue
        if transition_id in quality_by_transition:
            errors.append(f"{label} duplicates transition_id {transition_id}")
        quality_by_transition[transition_id] = archive
        if (
            not isinstance(source_version, int)
            or not isinstance(replacement_version, int)
            or replacement_version != source_version + 1
            or transition_id != program_transition_id(source_version, replacement_version)
        ):
            errors.append(f"{label} has an invalid program boundary")
        if archive.get("previous_archive_digest") != previous_digest:
            errors.append(f"{label} breaks the append-only digest chain")
        if archive.get("archive_digest") != transition_archive_digest(archive):
            errors.append(f"{label} archive digest is invalid")
        previous_digest = archive.get("archive_digest")
        paired = adaptation_by_transition.get(transition_id)
        for field in (
            "source_program_version", "replacement_program_version", "archived_at",
            "reason", "trigger", "source_strategy_digest",
        ):
            if not isinstance(paired, dict) or archive.get(field) != paired.get(field):
                errors.append(f"{label} does not match its adaptation archive {field}")
        scorecard = archive.get("quality")
        if not isinstance(scorecard, dict) or scorecard.get("threshold") != 9:
            errors.append(f"{label} has an invalid quality scorecard")
            continue
        dimensions = scorecard.get("dimensions")
        if not isinstance(dimensions, dict) or set(dimensions) != set(BASE_DIMENSIONS):
            errors.append(f"{label} lacks the complete governed dimension set")
            continue
        evidence_matches = evidence_archives_by_program.get(source_version, [])
        evidence_actors: set[str] = set()
        if len(evidence_matches) != 1:
            errors.append(f"{label} requires one exact archived evidence set")
            evidence_by_id: dict[str, dict[str, Any]] = {}
        else:
            evidence_by_id, evidence_actors = audit_archived_evidence_set(
                state,
                evidence_matches[0],
                source_version,
                errors,
                label=f"{label} archived evidence",
            )
            if evidence_matches[0].get("reason") != archive.get("reason"):
                errors.append(f"{label} archived evidence reason does not match the transition")
        for name, item in dimensions.items():
            item_label = f"{label} quality dimension {name}"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must be an object")
                continue
            if item.get("critical") != BASE_DIMENSIONS[name]:
                errors.append(f"{item_label} changes its criticality")
            score = item.get("score")
            if score is None:
                if any(
                    item.get(field) not in (None, [], "")
                    for field in (
                        "evidence", "rubric_version", "scored_by", "reviewed_by",
                        "scorer_grant", "reviewer_grant", "binding",
                    )
                ):
                    errors.append(f"{item_label} has authority without a score")
                continue
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 10:
                errors.append(f"{item_label} score is invalid")
                continue
            binding = item.get("binding")
            evidence_ids = item.get("evidence")
            if (
                not isinstance(binding, dict)
                or not isinstance(evidence_ids, list)
                or not evidence_ids
                or len(evidence_ids) != len(set(evidence_ids))
            ):
                errors.append(f"{item_label} lacks an exact evidence binding")
                continue
            for field in ("outcome_id", "work_id", "cycle_id", "rubric_version"):
                if not isinstance(binding.get(field), str) or not binding[field]:
                    errors.append(f"{item_label} binding lacks {field}")
            if binding.get("rubric_version") != item.get("rubric_version"):
                errors.append(f"{item_label} binding rubric does not match")
            evidence_digest_value = binding.get("evidence_digest")
            artifact_digest = binding.get("artifact_digest")
            if bool(evidence_digest_value) == bool(artifact_digest):
                errors.append(f"{item_label} must bind exactly one evidence digest")
            elif evidence_digest_value is not None and evidence_digest_value != evidence_records_digest(evidence_by_id, evidence_ids):
                errors.append(f"{item_label} evidence digest is invalid")
            if (
                not item.get("scored_by")
                or not item.get("reviewed_by")
                or item.get("scored_by") == item.get("reviewed_by")
            ):
                errors.append(f"{item_label} lacks independent scoring authority")
            quality_values = {
                "dimension": name,
                "score": score,
                "evidence_ids": evidence_ids,
                "rubric_version": item.get("rubric_version"),
                "scored_by": item.get("scored_by"),
                "reviewed_by": item.get("reviewed_by"),
                "outcome_id": binding.get("outcome_id"),
                "work_id": binding.get("work_id"),
                "cycle_id": binding.get("cycle_id"),
                "artifact_digest": artifact_digest,
                "evidence_digest": evidence_digest_value,
            }
            grant_base = {
                "resource": f"quality:{name}",
                "work_id": binding.get("work_id"),
                "cycle_id": binding.get("cycle_id"),
                "dimension": name,
                "payload_hash": command_payload_hash(
                    "score-quality", quality_command_payload(quality_values)
                ),
            }
            audit_stored_grant(
                state, item.get("scorer_grant"), errors, f"{item_label} scorer grant",
                {
                    **grant_base, "actor": item.get("scored_by"), "action": "score-quality",
                    "decision": f"score:{score}",
                },
                expected_program_version=source_version,
            )
            audit_stored_grant(
                state, item.get("reviewer_grant"), errors, f"{item_label} reviewer grant",
                {
                    **grant_base, "actor": item.get("reviewed_by"), "action": "score-quality-review",
                    "decision": f"review:{score}",
                },
                expected_program_version=source_version,
            )
            for evidence_id in evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if (
                    not isinstance(evidence, dict)
                    or evidence.get("program_version") != source_version
                    or name not in evidence.get("quality_dimensions", [])
                    or evidence.get("outcome_id") != binding.get("outcome_id")
                    or evidence.get("work_id") != binding.get("work_id")
                    or evidence.get("cycle_id") != binding.get("cycle_id")
                    or evidence.get("rubric_version") != item.get("rubric_version")
                    or (
                        artifact_digest is not None
                        and evidence.get("artifact_sha256") != artifact_digest
                    )
                ):
                    errors.append(f"{item_label} cites invalid archived evidence {evidence_id}")

    if not (
        set(adaptation_by_transition)
        == set(quality_by_transition)
        == set(runtime_by_transition)
    ):
        errors.append("adaptation, quality, and runtime transition archives are not one-to-one")

    repair_by_transition: dict[str, dict[str, Any]] = {}
    for index, repair in enumerate(repairs):
        label = f"feedback.program_transition_repairs[{index}]"
        if not isinstance(repair, dict) or not isinstance(repair.get("transition_id"), str):
            errors.append(f"{label} must be an identified object")
            continue
        transition_id = repair["transition_id"]
        if transition_id in repair_by_transition:
            errors.append(f"{label} duplicates transition_id {transition_id}")
        repair_by_transition[transition_id] = repair
        adaptation_archive = adaptation_by_transition.get(transition_id)
        quality_archive = quality_by_transition.get(transition_id)
        runtime_archive = runtime_by_transition.get(transition_id)
        if not all(
            isinstance(item, dict)
            for item in (adaptation_archive, quality_archive, runtime_archive)
        ):
            errors.append(f"{label} lacks its paired archives")
            continue
        source_version = adaptation_archive.get("source_program_version")
        replacement_version = adaptation_archive.get("replacement_program_version")
        payload = repair.get("payload")
        if not isinstance(payload, dict):
            errors.append(f"{label} lacks its signed payload")
            continue
        candidate_digest = payload.get("candidate_state_digest")
        transition_event = payload.get("transition_event")
        strategy_transition = (
            transition_event.get("strategy_transition")
            if isinstance(transition_event, dict)
            else None
        )
        expected_strategy_transition_digest = (
            hashlib.sha256(canonical_json(strategy_transition).encode("utf-8")).hexdigest()
            if isinstance(strategy_transition, dict)
            else None
        )
        if (
            not isinstance(transition_event, dict)
            or set(transition_event) != {
                "event_id", "event_type", "project_id", "program_version",
                "old_program_version", "reason", "state_revision",
                "event_payload_sha256", "strategy_transition",
                "strategy_transition_digest",
            }
            or transition_event.get("event_type") != "program_replaced"
            or transition_event.get("project_id") != state.get("instance", {}).get("project_id")
            or transition_event.get("program_version") != replacement_version
            or transition_event.get("old_program_version") != source_version
            or transition_event.get("reason") != adaptation_archive.get("reason")
            or transition_event.get("state_revision") != payload.get("transition_state_revision")
            or not isinstance(transition_event.get("event_id"), str)
            or not transition_event["event_id"]
            or not isinstance(transition_event.get("event_payload_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", transition_event["event_payload_sha256"])
            or transition_event.get("strategy_transition_digest")
            != expected_strategy_transition_digest
            or not isinstance(strategy_transition, dict)
            or strategy_transition.get("source_strategy")
            != adaptation_archive.get("source_strategy")
            or strategy_transition.get("source_strategy", {}).get("program_version")
            != source_version
            or strategy_transition.get("replacement_strategy", {}).get("program_version")
            != replacement_version
            or strategy_transition.get("replacement_strategy", {}).get("program_fingerprint")
            != strategy_fingerprint(strategy_transition.get("replacement_strategy", {}))
        ):
            errors.append(f"{label} transition event binding is invalid")
        expected_payload = {
            "transition_id": transition_id,
            "source_program_version": source_version,
            "replacement_program_version": replacement_version,
            "reason": adaptation_archive.get("reason"),
            "adaptation_archive_digest": adaptation_archive.get("archive_digest"),
            "quality_archive_digest": quality_archive.get("archive_digest"),
            "runtime_archive_digest": runtime_archive.get("archive_digest"),
            "candidate_state_digest": candidate_digest,
            "source_state_revision": payload.get("source_state_revision"),
            "source_state_digest": payload.get("source_state_digest"),
            "transition_state_revision": payload.get("transition_state_revision"),
            "transition_state_digest": payload.get("transition_state_digest"),
            "transition_event": payload.get("transition_event"),
        }
        if (
            payload != expected_payload
            or not isinstance(candidate_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", candidate_digest)
            or not isinstance(payload.get("source_state_revision"), int)
            or payload.get("source_state_revision", 0) < 1
            or payload.get("transition_state_revision") != payload.get("source_state_revision") + 1
            or any(
                not isinstance(payload.get(field), str)
                or not re.fullmatch(r"[0-9a-f]{64}", payload[field])
                for field in ("source_state_digest", "transition_state_digest")
            )
        ):
            errors.append(f"{label} payload does not match its exact archives")
        affected_actors: set[str] = set()
        for item in [
            *adaptation_archive.get("pending_adaptations", []),
            *adaptation_archive.get("applied_adaptations", []),
        ]:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("proposer"), str) and item["proposer"]:
                affected_actors.add(item["proposer"])
            actor = (item.get("reviewer_grant") or {}).get("claims", {}).get("actor")
            if isinstance(actor, str) and actor:
                affected_actors.add(actor)
        for item in quality_archive.get("quality", {}).get("dimensions", {}).values():
            if not isinstance(item, dict):
                continue
            for grant_name in ("scorer_grant", "reviewer_grant"):
                actor = (item.get(grant_name) or {}).get("claims", {}).get("actor")
                if isinstance(actor, str) and actor:
                    affected_actors.add(actor)
        evidence_matches = evidence_archives_by_program.get(source_version, [])
        if len(evidence_matches) == 1:
            _, evidence_actors = audit_archived_evidence_set(
                state,
                evidence_matches[0],
                source_version,
                [],
                label=f"{label} archived evidence",
            )
            affected_actors.update(evidence_actors)
        if repair.get("reviewer") in affected_actors:
            errors.append(f"{label} reviewer is not independent")
        audit_stored_grant(
            state,
            repair.get("repair_grant"),
            errors,
            f"{label} repair grant",
            {
                "actor": repair.get("reviewer"),
                "action": "repair-program-transition",
                "resource": f"program-transition:{source_version}:{replacement_version}",
                "work_id": "",
                "cycle_id": "",
                "dimension": "state-integrity",
                "decision": "archive-stale-authority",
                "payload_hash": command_payload_hash("repair-program-transition", expected_payload),
            },
            expected_program_version=replacement_version,
        )

    for transition_id, archive in adaptation_by_transition.items():
        has_repair = transition_id in repair_by_transition
        if archive.get("trigger") == "stale_transition_repair" and not has_repair:
            errors.append(f"transition archive {transition_id} lacks independent repair authority")
        if archive.get("trigger") == "program_replaced" and has_repair:
            errors.append(f"transition archive {transition_id} has unnecessary repair authority")


def validate_state(
    state: dict[str, Any],
    *,
    now: datetime | None = None,
    expected_project: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    instance = state.get("instance", {})
    strategy = state.get("strategy", {})
    controller_state = state.get("controller", {})
    portfolio = state.get("portfolio", {})
    evidence = state.get("evidence", {})
    feedback = state.get("feedback", {})
    quality = state.get("quality", {})
    phase = state.get("phase")
    issuer_key_value = os.environ.get(ACTOR_PUBLIC_KEY_ENV)
    issuer_ready = bool(issuer_key_value and Path(issuer_key_value).resolve().is_file())
    protected_launcher_ready, protected_launcher_blocker = protected_launcher_attestation()
    project_root = Path(str(instance.get("project_root", ""))).resolve()

    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}; run upgrade")
    if state.get("core_version") != CORE_VERSION:
        errors.append(f"core_version must be {CORE_VERSION}; run upgrade")
    runtime = state.get("runtime_adapter")
    if not isinstance(runtime, dict):
        errors.append("runtime_adapter must be an object")
    else:
        if not isinstance(runtime.get("enabled"), bool) or runtime.get("status") not in {"disabled", "enabled"}:
            errors.append("runtime_adapter feature gate is invalid")
        elif runtime.get("enabled") != (runtime.get("status") == "enabled"):
            errors.append("runtime_adapter enabled flag and status disagree")
        if runtime.get("program_version") != strategy.get("program_version"):
            errors.append("runtime_adapter belongs to a stale program")
        if runtime.get("gateway_public_key_env") != RUNTIME_GATEWAY_PUBLIC_KEY_ENV:
            errors.append("runtime_adapter must use the separate runtime gateway public-key configuration")
        if runtime.get("observation_gateway_keyring_env") != OBSERVATION_GATEWAY_KEYRING_ENV:
            errors.append("runtime_adapter must use the separate observation-gateway keyring configuration")
        if runtime.get("phase2_contract_digest") != PHASE2_CONTRACT_DIGEST:
            errors.append("runtime_adapter must bind the frozen Phase 2 contract digest")
        if not isinstance(runtime.get("provider_allowlist"), list) or not isinstance(runtime.get("attempts"), list):
            errors.append("runtime_adapter allowlist and attempts must be arrays")
        else:
            allowlist_keys: set[tuple[str, str, str]] = set()
            for item in runtime["provider_allowlist"]:
                if not isinstance(item, dict) or set(item) != {"provider", "surface", "account"} or any(
                    not isinstance(item.get(key), str) or not item[key] for key in ("provider", "surface", "account")
                ):
                    errors.append("runtime_adapter provider allowlist entries must be unique provider/surface/account objects")
                    continue
                key = (item["provider"], item["surface"], item["account"])
                if key in allowlist_keys:
                    errors.append("runtime_adapter provider allowlist contains duplicates")
                allowlist_keys.add(key)
            attempt_ids: set[str] = set()
            idempotency_keys: set[str] = set()
            manifest_attempts: set[tuple[Any, Any, Any, Any]] = set()
            for attempt in runtime["attempts"]:
                if not isinstance(attempt, dict):
                    errors.append("runtime_adapter attempts must be objects")
                    continue
                if any(re.search(r"private|secret|credential", str(key), re.I) for key in attempt):
                    errors.append("runtime_adapter attempts must not retain private keys or credentials")
                required = (
                    "attempt_id", "manifest_identity_id", "work_id", "cycle_id", "parent_runtime_id",
                    "role", "requested_model", "provider", "surface", "account", "scope", "scope_digest",
                    "budget", "fabric_manifest_digest", "phase2_contract_digest", "idempotency_key",
                    "admitted_by", "lease_fence", "program_version", "lease_id", "lease_generation",
                    "lease_owner", "status", "actor_grant", "admitted_at",
                )
                if any(attempt.get(field) in (None, "") for field in required):
                    errors.append("runtime_adapter attempt is missing immutable admission fields")
                    continue
                if attempt.get("status") != "admitted" or attempt.get("provider_task_id") is not None:
                    errors.append("admission-only runtime attempts cannot contain lifecycle state or provider task IDs")
                if attempt.get("program_version") != strategy.get("program_version"):
                    errors.append("runtime attempt belongs to a stale program")
                if attempt.get("phase2_contract_digest") != PHASE2_CONTRACT_DIGEST:
                    errors.append("runtime attempt binds the wrong Phase 2 contract")
                if tuple(attempt.get(key) for key in ("provider", "surface", "account")) not in allowlist_keys:
                    errors.append("runtime attempt provider/surface/account is not allowlisted")
                try:
                    scope = canonical_runtime_scopes(attempt.get("scope"))
                    if scope != attempt.get("scope") or attempt.get("scope_digest") != hashlib.sha256(canonical_json(scope).encode("utf-8")).hexdigest():
                        errors.append("runtime attempt scope is not canonically bound")
                except ValueError as exc:
                    errors.append(f"runtime attempt scope is invalid: {exc}")
                if not isinstance(attempt.get("budget"), dict):
                    errors.append("runtime attempt budget must be an object")
                fence = attempt.get("lease_fence")
                if not isinstance(fence, dict) or fence.get("lease_id") != attempt.get("lease_id") or fence.get("generation") != attempt.get("lease_generation") or fence.get("owner") != attempt.get("lease_owner") or fence.get("program_version") != attempt.get("program_version") or "admit-runtime-attempt" not in fence.get("allowed_transitions", []):
                    errors.append("runtime attempt does not retain its exact admission lease fence")
                fabric = state.get("execution_fabric", {})
                if attempt.get("fabric_manifest_digest") != fabric.get("manifest_digest"):
                    errors.append("runtime attempt binds a stale fabric manifest")
                manifest = fabric.get("manifest") if isinstance(fabric.get("manifest"), dict) else {}
                manifest_matches: list[tuple[dict[str, Any], str | None]] = []
                for manager in manifest.get("managers", []):
                    if attempt.get("role") == "manager" and attempt.get("manifest_identity_id") == manager.get("id"):
                        manifest_matches.append((manager, None))
                    for worker in manager.get("workers", []):
                        if attempt.get("role") == "worker" and attempt.get("manifest_identity_id") == worker.get("id"):
                            manifest_matches.append((worker, manager.get("id")))
                if len(manifest_matches) != 1:
                    errors.append("runtime attempt does not map to exactly one current manifest identity")
                else:
                    identity, owner_manifest_id = manifest_matches[0]
                    if attempt.get("requested_model") != identity.get("model"):
                        errors.append("runtime attempt model does not match its manifest identity")
                    try:
                        if canonical_runtime_scopes(identity.get("write_scope")) != attempt.get("scope"):
                            errors.append("runtime attempt scope does not match its manifest identity")
                    except ValueError:
                        errors.append("runtime attempt manifest identity has invalid scope")
                    if canonical_json(attempt.get("budget")) != canonical_json(identity.get("budget")):
                        errors.append("runtime attempt budget does not match its manifest identity")
                    if attempt.get("role") == "manager":
                        if attempt.get("parent_runtime_id") != "master" or identity.get("model") != "gpt-5.6-sol":
                            errors.append("manager runtime attempt must have master parent and exact Sol model")
                    elif attempt.get("role") == "worker":
                        if identity.get("model") != "gpt-5.6-luna":
                            errors.append("worker runtime attempt must use the exact Luna model")
                        parent = next(
                            (item for item in runtime["attempts"] if isinstance(item, dict)
                             and item.get("attempt_id") == attempt.get("parent_runtime_id")
                             and item.get("role") == "manager"
                             and item.get("manifest_identity_id") == owner_manifest_id
                             and item.get("status") == "admitted"),
                            None,
                        )
                        if parent is None:
                            errors.append("worker runtime attempt does not bind its admitted owning manager")
                if attempt.get("attempt_id") in attempt_ids or attempt.get("idempotency_key") in idempotency_keys:
                    errors.append("runtime adapter attempts reuse an attempt ID or idempotency key")
                attempt_ids.add(attempt.get("attempt_id"))
                idempotency_keys.add(attempt.get("idempotency_key"))
                identity_key = tuple(attempt.get(key) for key in ("program_version", "work_id", "cycle_id", "manifest_identity_id"))
                if identity_key in manifest_attempts:
                    errors.append("runtime adapter admits a manifest identity more than once in one work cycle")
                manifest_attempts.add(identity_key)
                payload_hash = command_payload_hash("admit-runtime-attempt", retained_runtime_admission_payload(attempt))
                audit_stored_grant(
                    state, attempt.get("actor_grant"), errors, "runtime admission grant",
                    {
                        "actor": attempt.get("admitted_by"), "action": "admit-runtime-attempt",
                        "resource": f"runtime:{attempt.get('attempt_id')}", "work_id": attempt.get("work_id"),
                        "cycle_id": attempt.get("cycle_id"), "dimension": "runtime-admission",
                        "decision": "admitted", "payload_hash": payload_hash,
                    },
                )
            inboxes = runtime.get("observation_inboxes")
            if not isinstance(inboxes, dict):
                errors.append("runtime_adapter observation_inboxes must be an object")
            elif set(inboxes) != attempt_ids:
                errors.append("runtime_adapter must retain exactly one observation inbox per admitted attempt")
            else:
                observation_module = runtime_observation_module()
                keyring_value = os.environ.get(OBSERVATION_GATEWAY_KEYRING_ENV)
                keyring_path = Path(keyring_value).resolve() if keyring_value else Path("/nonexistent/company-os-observation-keyring.json")
                actor_key = Path(issuer_key_value).resolve() if issuer_key_value else None
                if keyring_value and actor_key == keyring_path:
                    errors.append("observation gateway and actor decision issuer must use distinct trust roots")
                for attempt in runtime["attempts"]:
                    if not isinstance(attempt, dict) or not isinstance(attempt.get("attempt_id"), str):
                        continue
                    inbox = inboxes.get(attempt["attempt_id"])
                    if not isinstance(inbox, dict):
                        errors.append(f"runtime observation inbox {attempt['attempt_id']} must be an object")
                        continue
                    if not isinstance(inbox.get("enabled"), bool) or inbox.get("status") not in {"disabled", "enabled"}:
                        errors.append("runtime observation inbox feature gate is invalid")
                    elif inbox.get("enabled") != (inbox.get("status") == "enabled"):
                        errors.append("runtime observation inbox enabled flag and status disagree")
                    if not runtime.get("enabled") and (
                        inbox.get("enabled") is not False or inbox.get("status") != "disabled"
                    ):
                        errors.append("runtime observation inbox cannot be enabled while the runtime adapter is disabled")
                    if inbox.get("enabled") is True and (
                        not keyring_value or not keyring_path.is_file()
                    ):
                        errors.append("enabled runtime observation inbox requires an external observation-gateway keyring")
                        continue
                    try:
                        observation_module.audit_retained_inbox(
                            inbox,
                            expected_attempt=observation_expected_attempt(state, attempt),
                            keyring_path=keyring_path,
                            artifact_root=project_root,
                            now=now,
                        )
                    except ValueError as exc:
                        errors.append(f"runtime observation inbox {attempt['attempt_id']} failed audit: {exc}")

    for field in ("project_id", "name", "project_root", "project_type"):
        if not instance.get(field):
            errors.append(f"instance.{field} is required")
    if instance.get("status") not in INSTANCE_STATUSES:
        errors.append(f"instance.status must be one of: {', '.join(sorted(INSTANCE_STATUSES))}")
    project_root = Path(str(instance.get("project_root", ""))).resolve()
    if expected_project is not None and project_root != expected_project.resolve():
        errors.append("instance.project_root does not match the audited project")
    if instance.get("project_root") and not project_root.is_dir():
        errors.append("instance.project_root does not exist")

    for field in ("north_star", "current_outcome", "success_metric"):
        if not strategy.get(field):
            errors.append(f"strategy.{field} is required before execution")
    program_version = strategy.get("program_version")
    if not isinstance(program_version, int) or program_version < 1:
        errors.append("strategy.program_version must be a positive integer")
    if parse_time(strategy.get("program_updated_at"), "strategy.program_updated_at", errors):
        pass
    expected_fingerprint = strategy_fingerprint(strategy)
    if strategy.get("program_fingerprint") != expected_fingerprint:
        errors.append("strategy.program_fingerprint does not match the authoritative program")

    if not isinstance(evidence, dict) or set(evidence) != set(EVIDENCE_BUCKETS):
        errors.append("evidence must define every governed evidence bucket exactly once")
        evidence = {key: evidence.get(key, []) if isinstance(evidence, dict) else [] for key in EVIDENCE_BUCKETS}

    valid_evidence_ids: set[str] = set()
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for bucket in EVIDENCE_BUCKETS:
        items = evidence.get(bucket, [])
        if not isinstance(items, list):
            errors.append(f"evidence.{bucket} must be an array")
            continue
        for index, item in enumerate(items):
            label = f"evidence.{bucket}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            before = len(errors)
            evidence_id = item.get("id")
            if not isinstance(evidence_id, str) or not evidence_id:
                errors.append(f"{label}.id is required")
            elif evidence_id in evidence_by_id:
                errors.append(f"evidence id {evidence_id} is duplicated")
            else:
                evidence_by_id[evidence_id] = item
            active = item.get("active", True)
            if not isinstance(active, bool):
                errors.append(f"{label}.active must be a boolean when supplied")
            elif active is not True:
                errors.append(f"{label} is inactive and must be retained only in archived evidence")
            if item.get("outcome") != bucket:
                errors.append(f"{label}.outcome must be {bucket}")
            if item.get("project_id") != instance.get("project_id"):
                errors.append(f"{label} is not bound to this project")
            if evidence_is_active(item) and item.get("program_version") != program_version:
                errors.append(f"{label} is stale for the current program")
            for field in ("source", "decision_impact", "author", "reviewer"):
                if not isinstance(item.get(field), str) or not item.get(field).strip():
                    errors.append(f"{label}.{field} is required")
            if item.get("author") and item.get("author") == item.get("reviewer"):
                errors.append(f"{label} lacks independent review")
            snapshot_present = evidence_snapshot_fields(item)
            if snapshot_present:
                digest = item.get("snapshot_sha256")
                snapshot = project_local_path(project_root, item.get("snapshot_path"))
                expected = evidence_snapshot_path(project_root, digest) if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else None
                if (
                    not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or not isinstance(item.get("snapshot_path"), str) or snapshot is None
                    or expected is None or snapshot != expected
                ):
                    errors.append(f"{label}.snapshot_path must be the exact project-local content address")
                elif snapshot.is_symlink() or not snapshot.is_file():
                    errors.append(f"{label}.snapshot_path does not exist as an immutable file")
                elif sha256_file(snapshot) != digest:
                    errors.append(f"{label}.snapshot_sha256 does not match the snapshot")
                if item.get("artifact_sha256") != digest:
                    errors.append(f"{label}.artifact_sha256 must match snapshot_sha256")
                if item.get("artifact_path") != item.get("snapshot_path"):
                    errors.append(f"{label}.artifact_path must equal snapshot_path for immutable evidence")
                source_path = item.get("source_artifact_path")
                if (
                    not isinstance(source_path, str)
                    or not source_path.strip()
                    or project_local_path(project_root, source_path) is None
                ):
                    errors.append(f"{label}.source_artifact_path must stay inside the project")
            else:
                # Legacy evidence is source-bound only until it is superseded.
                artifact = project_local_path(project_root, item.get("artifact_path"))
                if artifact is None:
                    errors.append(f"{label}.artifact_path must stay inside the project")
                elif not artifact.is_file():
                    errors.append(f"{label}.artifact_path does not exist")
                elif item.get("artifact_sha256") != sha256_file(artifact):
                    errors.append(f"{label}.artifact_sha256 does not match the artifact")
            observed = parse_time(item.get("observed_at"), f"{label}.observed_at", errors)
            freshness_days = item.get("freshness_days")
            if not isinstance(freshness_days, int) or not 1 <= freshness_days <= 365:
                errors.append(f"{label}.freshness_days must be from 1 to 365")
            elif observed:
                if observed > now:
                    errors.append(f"{label}.observed_at is in the future")
                elif now - observed > timedelta(days=freshness_days):
                    errors.append(f"{label} is stale")
            dimensions = item.get("quality_dimensions", [])
            if not isinstance(dimensions, list) or any(name not in BASE_DIMENSIONS for name in dimensions):
                errors.append(f"{label}.quality_dimensions contains an unknown dimension")
            for field in ("outcome_id", "work_id", "cycle_id", "rubric_version"):
                if field in item and (not isinstance(item[field], str) or not item[field].strip()):
                    errors.append(f"{label}.{field} must be a non-empty string when supplied")
            if len(errors) == before and isinstance(evidence_id, str) and evidence_is_active(item):
                valid_evidence_ids.add(evidence_id)

    archived_evidence = feedback.get("archived_evidence", [])
    if not isinstance(archived_evidence, list):
        errors.append("feedback.archived_evidence must be an array")
    else:
        archived_ids: set[str] = set()
        archives_by_id: dict[str, dict[str, Any]] = {}
        for index, archive in enumerate(archived_evidence):
            label = f"feedback.archived_evidence[{index}]"
            if not isinstance(archive, dict):
                errors.append(f"{label} must be an object")
                continue
            # Program replacement archives predate evidence supersession and
            # retain a whole evidence object under `evidence`.
            if archive.get("archive_kind") != "evidence_supersession":
                continue
            if not isinstance(archive, dict) or not isinstance(archive.get("record"), dict):
                errors.append(f"{label} must retain a full evidence record")
                continue
            old = archive["record"]
            old_id = old.get("id")
            if not isinstance(old_id, str) or not old_id or old_id in archived_ids or old_id in evidence_by_id:
                errors.append(f"{label}.record.id must be unique and not current")
            archived_ids.add(old_id) if isinstance(old_id, str) else None
            if isinstance(old_id, str):
                archives_by_id[old_id] = archive
            if archive.get("bucket") not in EVIDENCE_BUCKETS or old.get("outcome") != archive.get("bucket"):
                errors.append(f"{label} bucket does not match its archived record")
            if archive.get("project_id") != instance.get("project_id") or old.get("project_id") != instance.get("project_id"):
                errors.append(f"{label} is not bound to this project")
            if archive.get("old_snapshot_available") not in {True, False}:
                errors.append(f"{label}.old_snapshot_available must be boolean")
            if not isinstance(archive.get("superseded_by_evidence_id"), str) or not archive["superseded_by_evidence_id"]:
                errors.append(f"{label}.superseded_by_evidence_id is required")
            if old.get("superseded_by_evidence_id") != archive.get("superseded_by_evidence_id"):
                errors.append(f"{label} does not preserve predecessor linkage")
            if evidence_snapshot_fields(old):
                digest = old.get("snapshot_sha256")
                snapshot = project_local_path(project_root, old.get("snapshot_path"))
                expected = evidence_snapshot_path(project_root, digest) if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else None
                available = bool(expected and snapshot == expected and snapshot.is_file() and not snapshot.is_symlink() and sha256_file(snapshot) == digest)
                if archive.get("old_snapshot_available") != available:
                    errors.append(f"{label}.old_snapshot_available does not truthfully describe the archived snapshot")
                if not available:
                    errors.append(f"{label} references a missing or corrupt snapshot")
                if old.get("artifact_path") != old.get("snapshot_path"):
                    errors.append(f"{label}.record.artifact_path must equal snapshot_path")
            elif archive.get("old_snapshot_available") is not False:
                errors.append(f"{label} incorrectly claims a legacy snapshot exists")
        program_archive_records: dict[str, dict[str, Any]] = {}
        for index, archive in enumerate(archived_evidence):
            if not isinstance(archive, dict) or archive.get("archive_kind") == "evidence_supersession":
                continue
            archived_program_evidence = archive.get("evidence")
            if not isinstance(archived_program_evidence, dict):
                continue
            for bucket, records in archived_program_evidence.items():
                if bucket not in EVIDENCE_BUCKETS or not isinstance(records, list):
                    continue
                for record_index, record in enumerate(records):
                    label = f"feedback.archived_evidence[{index}].evidence.{bucket}[{record_index}]"
                    if not isinstance(record, dict):
                        errors.append(f"{label} must be an object")
                        continue
                    evidence_id = record.get("id")
                    if not isinstance(evidence_id, str) or not evidence_id:
                        errors.append(f"{label}.id is required")
                    elif evidence_id in program_archive_records or evidence_id in evidence_by_id or evidence_id in archives_by_id:
                        errors.append(f"{label}.id must be unique across evidence history")
                    else:
                        program_archive_records[evidence_id] = record
        all_history: dict[str, tuple[str, dict[str, Any]]] = {
            evidence_id: ("current", item) for evidence_id, item in evidence_by_id.items()
        }
        all_history.update({evidence_id: ("archived", archive["record"]) for evidence_id, archive in archives_by_id.items()})
        all_history.update({evidence_id: ("program_archive", item) for evidence_id, item in program_archive_records.items()})
        for index, archive in enumerate(archived_evidence):
            if not isinstance(archive, dict) or archive.get("archive_kind") != "evidence_supersession":
                continue
            label = f"feedback.archived_evidence[{index}]"
            old = archive.get("record")
            if not isinstance(old, dict):
                continue
            old_id = old.get("id")
            replacement_entry = all_history.get(archive.get("superseded_by_evidence_id"))
            replacement = replacement_entry[1] if replacement_entry else None
            transition_kind = archive.get("transition_kind", "structural_recovery")
            if not isinstance(replacement, dict):
                errors.append(f"{label} lacks its retained replacement")
            elif transition_kind == "semantic_retraction":
                correction_payload = archive.get("correction_payload")
                replacement_digest = replacement.get("artifact_sha256")
                replacement_snapshot = project_local_path(project_root, replacement.get("snapshot_path"))
                expected_replacement_snapshot = (
                    evidence_snapshot_path(project_root, replacement_digest)
                    if isinstance(replacement_digest, str) and re.fullmatch(r"[0-9a-f]{64}", replacement_digest)
                    else None
                )
                if (
                    replacement.get("snapshot_sha256") != replacement_digest
                    or expected_replacement_snapshot is None
                    or replacement_snapshot != expected_replacement_snapshot
                    or replacement.get("artifact_path") != replacement.get("snapshot_path")
                    or replacement_snapshot is None
                    or replacement_snapshot.is_symlink()
                    or not replacement_snapshot.is_file()
                    or sha256_file(replacement_snapshot) != replacement_digest
                ):
                    errors.append(f"{label} semantic successor snapshot is not the signed immutable content address")
                predecessor_digest_record = {
                    key: value for key, value in old.items()
                    if key not in {"superseded_by_evidence_id", "superseded_at"}
                }
                predecessor_digest_record["active"] = True
                expected_correction_payload = {
                    "evidence_id": old_id,
                    "predecessor_record_digest": evidence_record_digest(predecessor_digest_record),
                    "old_artifact_sha256": old.get("artifact_sha256"),
                    "replacement_evidence_id": replacement.get("id"),
                    "new_artifact_sha256": replacement.get("artifact_sha256"),
                    "replacement_record_digest": evidence_record_digest(replacement),
                    "project_id": old.get("project_id"),
                    "program_version": old.get("program_version"),
                    "outcome": archive.get("bucket"),
                    "source_artifact_path": replacement.get("source_artifact_path"),
                    "source": replacement.get("source"),
                    "decision_impact": replacement.get("decision_impact"),
                    "reason": archive.get("reason"),
                    "transition_at": archive.get("superseded_at"),
                    "correction_type": "git_commit_identity",
                    "claim_path": "/commit",
                    "old_value": correction_payload.get("old_value") if isinstance(correction_payload, dict) else None,
                    "new_value": correction_payload.get("new_value") if isinstance(correction_payload, dict) else None,
                    "verification": {
                        "method": "git_rev_parse_commit",
                        "resolved_commit": correction_payload.get("new_value") if isinstance(correction_payload, dict) else None,
                    },
                    "author": replacement.get("author"),
                    "reviewer": replacement.get("reviewer"),
                    "freshness_days": replacement.get("freshness_days"),
                    "quality_dimensions": replacement.get("quality_dimensions"),
                    "outcome_id": replacement.get("outcome_id"),
                    "work_id": replacement.get("work_id"),
                    "cycle_id": replacement.get("cycle_id"),
                    "rubric_version": replacement.get("rubric_version"),
                    "id": replacement.get("id"),
                }
                if correction_payload != expected_correction_payload:
                    errors.append(f"{label}.correction_payload does not match the retained semantic transition")
                if old.get("active") is not False:
                    errors.append(f"{label} semantic predecessor must remain inactive")
                if (
                    old.get("superseded_at") != archive.get("superseded_at")
                    or replacement.get("observed_at") != archive.get("superseded_at")
                ):
                    errors.append(f"{label} semantic transition timestamps do not match")
                if replacement.get("correction_type") != "git_commit_identity" or replacement.get("corrected_claim_path") != "/commit":
                    errors.append(f"{label} replacement lacks its typed Git-commit correction marker")
                if replacement.get("active") is not True:
                    errors.append(f"{label} semantic successor must remain active in retained history")
                if replacement.get("reviewer") in {
                    old.get("author"), old.get("reviewer"), replacement.get("author")
                }:
                    errors.append(f"{label} semantic correction adjudicator is not independent")
                try:
                    old_path = project_local_path(project_root, old.get("snapshot_path"))
                    new_path = project_local_path(project_root, replacement.get("snapshot_path"))
                    old_document = json.loads(old_path.read_text(encoding="utf-8")) if old_path else None
                    new_document = json.loads(new_path.read_text(encoding="utf-8")) if new_path else None
                    expected_document = deepcopy(old_document)
                    expected_document["commit"] = correction_payload.get("new_value")
                    if (
                        not isinstance(old_document, dict) or not isinstance(new_document, dict)
                        or old_document.get("commit") != correction_payload.get("old_value")
                        or new_document != expected_document
                    ):
                        raise ValueError
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                    errors.append(f"{label} semantic correction bytes do not differ only at /commit")
                new_value = correction_payload.get("new_value") if isinstance(correction_payload, dict) else None
                resolved_commit = subprocess.run(
                    ["git", "-C", str(project_root), "rev-parse", f"{new_value}^{{commit}}"],
                    capture_output=True, text=True, check=False,
                ) if isinstance(new_value, str) and re.fullmatch(r"[0-9a-f]{40}", new_value) else None
                if resolved_commit is None or resolved_commit.returncode != 0 or resolved_commit.stdout.strip() != new_value:
                    errors.append(f"{label} corrected Git commit is not locally verifiable")
                correction_hash = command_payload_hash("correct-evidence", correction_payload) if isinstance(correction_payload, dict) else ""
                declarant_status = audit_stored_grant(
                    state,
                    archive.get("declarant_grant"),
                    errors,
                    f"{label}.declarant_grant",
                    {
                        "actor": replacement.get("author"),
                        "action": "correct-evidence-declare",
                        "resource": f"evidence:{old_id}",
                        "work_id": "",
                        "cycle_id": "",
                        "dimension": "evidence",
                        "decision": "proposed",
                        "payload_hash": correction_hash,
                    },
                    expected_program_version=old.get("program_version"),
                )
                adjudicator_status = audit_stored_grant(
                    state,
                    archive.get("adjudicator_grant"),
                    errors,
                    f"{label}.adjudicator_grant",
                    {
                        "actor": replacement.get("reviewer"),
                        "action": "correct-evidence-adjudicate",
                        "resource": f"evidence:{old_id}",
                        "work_id": "",
                        "cycle_id": "",
                        "dimension": "evidence",
                        "decision": "accepted",
                        "payload_hash": correction_hash,
                    },
                    expected_program_version=old.get("program_version"),
                )
                if declarant_status == "retained_legacy" or adjudicator_status == "retained_legacy":
                    errors.append(f"{label} semantic correction cannot rely on a legacy unverifiable grant")
            elif transition_kind == "structural_recovery":
                review_payload = archive.get("review_payload")
                if not isinstance(review_payload, dict):
                    errors.append(f"{label} lacks its retained review payload")
                    continue
                expected_review_payload = {
                    "evidence_id": old_id,
                    "old_artifact_sha256": old.get("artifact_sha256"),
                    "replacement_evidence_id": replacement.get("id"),
                    "new_artifact_sha256": replacement.get("artifact_sha256"),
                    "outcome": archive.get("bucket"),
                    "source_artifact_path": replacement.get("source_artifact_path"),
                    "source": replacement.get("source"),
                    "decision_impact": replacement.get("decision_impact"),
                    "author": replacement.get("author"),
                    "reviewer": replacement.get("reviewer"),
                    "reason": archive.get("reason"),
                    "freshness_days": replacement.get("freshness_days"),
                    "quality_dimensions": replacement.get("quality_dimensions"),
                    "outcome_id": replacement.get("outcome_id"),
                    "work_id": replacement.get("work_id"),
                    "cycle_id": replacement.get("cycle_id"),
                    "rubric_version": replacement.get("rubric_version"),
                    "id": replacement.get("id"),
                }
                if review_payload != expected_review_payload:
                    errors.append(f"{label}.review_payload does not match the retained transition")
                grant_status = audit_stored_grant(
                    state,
                    archive.get("reviewer_grant"),
                    errors,
                    f"{label}.reviewer_grant",
                    {
                        "actor": replacement.get("reviewer"),
                        "action": "supersede-evidence",
                        "resource": f"evidence:{old_id}",
                        "work_id": "",
                        "cycle_id": "",
                        "dimension": "evidence",
                        "decision": "accepted",
                        "payload_hash": command_payload_hash("supersede-evidence", review_payload),
                    },
                    expected_program_version=old.get("program_version"),
                )
                if grant_status == "retained_legacy":
                    warning = "legacy evidence review is transactionally retained but lacks its historical public verification key"
                    if warning not in warnings:
                        warnings.append(warning)
            else:
                errors.append(f"{label}.transition_kind is invalid")
        successor_count: dict[str, int] = {}
        for evidence_id, (location, item) in all_history.items():
            successor = item.get("superseded_by_evidence_id")
            predecessor = item.get("supersedes_evidence_id")
            if location in {"current", "program_archive"} and predecessor not in (None, ""):
                archived = archives_by_id.get(predecessor)
                if not archived or archived.get("superseded_by_evidence_id") != evidence_id:
                    errors.append(f"evidence {evidence_id} has an unarchived predecessor linkage")
            if successor not in (None, ""):
                successor_count[successor] = successor_count.get(successor, 0) + 1
                target = all_history.get(successor)
                if target is None or target[1].get("supersedes_evidence_id") != evidence_id:
                    errors.append(f"evidence {evidence_id} has an inconsistent successor linkage")
                elif target[1].get("outcome") != item.get("outcome") or target[1].get("project_id") != item.get("project_id") or target[1].get("program_version") != item.get("program_version"):
                    errors.append(f"evidence {evidence_id} supersession crosses project, program, or bucket")
        if any(count > 1 for count in successor_count.values()):
            errors.append("evidence supersession history branches")
        for evidence_id in all_history:
            seen: set[str] = set()
            cursor = evidence_id
            while cursor in all_history:
                if cursor in seen:
                    errors.append(f"evidence supersession history cycles at {cursor}")
                    break
                seen.add(cursor)
                cursor = all_history[cursor][1].get("superseded_by_evidence_id")

    if phase not in PHASES:
        errors.append(f"phase must be one of: {', '.join(PHASES)}")
    else:
        for evidence_key in PHASE_EVIDENCE[phase]:
            bucket_ids = {
                item.get("id")
                for item in evidence.get(evidence_key, [])
                if isinstance(item, dict)
            }
            if not bucket_ids.intersection(valid_evidence_ids):
                errors.append(f"phase {phase} requires valid evidence.{evidence_key}")

    max_active = controller_state.get("max_active_work")
    if not isinstance(max_active, int) or not 1 <= max_active <= 3:
        errors.append("controller.max_active_work must be between 1 and 3")
    if controller_state.get("meta_loop_depth") != 1:
        errors.append("controller.meta_loop_depth must remain exactly 1")
    lease_generation = controller_state.get("lease_generation")
    if not isinstance(lease_generation, int) or lease_generation < 0:
        errors.append("controller.lease_generation must be a non-negative integer")
    restart_checkpoint = controller_state.get("restart_checkpoint")
    if restart_checkpoint is not None:
        if not isinstance(restart_checkpoint, dict):
            errors.append("controller.restart_checkpoint must be an object or null")
        else:
            restart_requirements = {
                "reason": "schema_upgrade",
                "to_schema_version": SCHEMA_VERSION,
                "program_version": program_version,
                "phase": "reality_audit",
                "status": "evidence_required",
            }
            if any(restart_checkpoint.get(key) != value for key, value in restart_requirements.items()):
                errors.append("controller.restart_checkpoint does not bind the fail-closed reality restart")
            if restart_checkpoint.get("from_program_version") != (
                program_version - 1 if isinstance(program_version, int) else None
            ):
                errors.append("controller.restart_checkpoint does not preserve monotonic program history")
            if not isinstance(restart_checkpoint.get("from_schema_version"), int):
                errors.append("controller.restart_checkpoint.from_schema_version is required")
            parse_time(
                restart_checkpoint.get("created_at"),
                "controller.restart_checkpoint.created_at",
                errors,
            )
            if (
                phase != "reality_audit"
                or instance.get("status") != "paused"
                or controller_state.get("schedule_enabled")
                or controller_state.get("lease") is not None
            ):
                errors.append("controller.restart_checkpoint requires a paused, unscheduled reality restart")

    lease = controller_state.get("lease")
    if lease:
        for field in ("lease_id", "owner", "expires_at", "generation", "program_version", "allowed_transitions"):
            if lease.get(field) in (None, ""):
                errors.append(f"controller.lease.{field} is required")
        expires = parse_time(lease.get("expires_at"), "controller.lease.expires_at", errors)
        if expires and expires <= now:
            errors.append("controller lease is stale")
        if lease.get("generation") != lease_generation:
            errors.append("controller lease generation is not authoritative")
        if lease.get("program_version") != program_version:
            errors.append("controller lease belongs to a stale program")
        if (
            not isinstance(lease.get("allowed_transitions"), list)
            or set(lease["allowed_transitions"]) != LEASE_TRANSITIONS
        ):
            errors.append("controller lease must enumerate the exact permitted transitions")
        recovery_chain = lease.get("recovery_chain", [])
        if not isinstance(recovery_chain, list) or any(
            not isinstance(item, dict)
            or not item.get("lease_id")
            or not isinstance(item.get("generation"), int)
            for item in recovery_chain
        ):
            errors.append("controller lease recovery_chain is invalid")
    cancellation_requested = controller_state.get("cancellation_requested") is True
    if cancellation_requested:
        if controller_state.get("schedule_enabled"):
            errors.append("cancellation must disable the scheduler")
        if lease is not None:
            errors.append("cancellation must revoke the active lease")
        if portfolio.get("active_work"):
            errors.append("cancellation must clear active work")
        if instance.get("status") not in {"paused", "cancelled"}:
            errors.append("cancellation must pause or cancel the instance")
        if state.get("execution_fabric", {}).get("status") not in {"unconfigured", "cancelled"}:
            errors.append("cancellation must propagate to the execution_fabric")
    if instance.get("status") != "active" and controller_state.get("schedule_enabled"):
        errors.append("a paused or cancelled instance cannot enable scheduling")

    allocation = portfolio.get("allocation", {})
    expected_keys = {"capability", "innovation", "enabler", "maintenance"}
    if not isinstance(allocation, dict) or set(allocation) != expected_keys:
        errors.append("portfolio allocation must define capability, innovation, enabler, and maintenance")
    elif any(not isinstance(value, (int, float)) or value < 0 for value in allocation.values()):
        errors.append("portfolio allocation values must be non-negative numbers")
    elif sum(allocation.values()) != 100:
        errors.append("portfolio allocation must total 100")
    else:
        if allocation["enabler"] > 10:
            errors.append("enabler allocation may not exceed 10 without a core policy change")
        if allocation["maintenance"] > 5:
            errors.append("maintenance allocation may not exceed 5 without a core policy change")
        if allocation["capability"] + allocation["innovation"] < 80:
            errors.append("capability plus innovation allocation must be at least 80")

    committed = portfolio.get("committed_outcomes", [])
    if not isinstance(committed, list):
        errors.append("portfolio.committed_outcomes must be an array")
        committed = []
    committed_ids: set[str] = set()
    for index, outcome in enumerate(committed):
        label = f"portfolio.committed_outcomes[{index}]"
        if not isinstance(outcome, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ("id", "title", "user_visible_outcome"):
            if not outcome.get(field):
                errors.append(f"{label}.{field} is required")
        if outcome.get("type") not in {"capability", "innovation"}:
            errors.append(f"{label}.type must be capability or innovation")
        if outcome.get("program_version") != program_version:
            errors.append(f"{label} belongs to a stale program")
        if outcome.get("id") in committed_ids:
            errors.append(f"committed outcome id {outcome.get('id')} is duplicated")
        elif outcome.get("id"):
            committed_ids.add(outcome["id"])

    active_work = portfolio.get("active_work", [])
    if not isinstance(active_work, list):
        errors.append("portfolio.active_work must be an array")
        active_work = []
    if isinstance(max_active, int) and len(active_work) > max_active:
        errors.append("active work exceeds the configured work-in-progress limit")
    ids: list[str] = []
    primary_count = 0
    for index, work in enumerate(active_work):
        label = f"portfolio.active_work[{index}]"
        if not isinstance(work, dict):
            errors.append(f"{label} must be an object")
            continue
        work_id = work.get("id")
        for field in ("id", "title", "user_visible_outcome", "owner"):
            if not isinstance(work.get(field), str) or not work.get(field).strip():
                errors.append(f"{label}.{field} is required")
        if isinstance(work_id, str) and work_id:
            ids.append(work_id)
        work_type = work.get("type")
        if work_type not in ALLOWED_WORK_TYPES:
            errors.append(f"work item {work_id} has invalid type")
        if work.get("execution_mode", "single") not in {"single", "luna_fabric"}:
            errors.append(f"work item {work_id} has invalid execution_mode")
        if work.get("status") not in ACTIVE_WORK_STATUSES:
            errors.append(f"work item {work_id} has invalid active status")
        if work.get("program_version") != program_version:
            errors.append(f"work item {work_id} belongs to a stale program")
        if work.get("work_fingerprint") != work_fingerprint(work):
            errors.append(f"work item {work_id} has an invalid semantic fingerprint")
        queue_payload = work.get("queue_payload")
        retained_queue_payload = retained_queue_command_payload(work)
        if not isinstance(queue_payload, dict):
            errors.append(f"work item {work_id} lacks its canonical queue payload")
        elif queue_payload != retained_queue_payload:
            errors.append(f"work item {work_id} queue payload does not match its retained governed record")
        queue_payload_digest = command_payload_hash("queue-work", retained_queue_payload)
        if work_type in {"capability", "innovation"}:
            outcome_id = work.get("outcome_id")
            if outcome_id not in committed_ids:
                errors.append(f"{work_type} work item {work_id} must reference a committed outcome")
        if work_type == "p0":
            for field in ("incident_ref", "severity", "justification", "incident_actor", "incident_grant", "approval"):
                if not work.get(field):
                    errors.append(f"p0 work item {work_id} requires {field}")
            if work.get("severity") != "P0":
                errors.append(f"p0 work item {work_id} severity must be P0")
            approval = work.get("approval") if isinstance(work.get("approval"), dict) else {}
            if approval.get("approved_by") in {None, work.get("owner"), work.get("incident_actor")}:
                errors.append(f"p0 work item {work_id} requires an independent approval actor")
            audit_stored_grant(
                state,
                work.get("incident_grant"),
                errors,
                f"p0 work item {work_id} incident grant",
                {
                    "actor": work.get("incident_actor"), "action": "p0-incident", "resource": work.get("incident_ref"),
                    "work_id": work_id, "cycle_id": "precycle", "dimension": "p0", "decision": "P0",
                    "payload_hash": queue_payload_digest,
                },
            )
            audit_stored_grant(
                state,
                approval.get("grant"),
                errors,
                f"p0 work item {work_id} approval grant",
                {
                    "actor": approval.get("approved_by"), "action": "p0-approve", "resource": work.get("incident_ref"),
                    "work_id": work_id, "cycle_id": "precycle", "dimension": "p0", "decision": "approved",
                    "payload_hash": queue_payload_digest,
                },
            )
        if isinstance(work.get("repeat_override"), dict):
            override = work["repeat_override"]
            if override.get("reviewer") in {None, work.get("owner")} or not override.get("reason"):
                errors.append(f"work item {work_id} repeat override lacks independent review")
            audit_stored_grant(
                state,
                override.get("grant"),
                errors,
                f"work item {work_id} repeat override grant",
                {
                    "actor": override.get("reviewer"), "action": "repeat-override", "resource": work.get("work_fingerprint"),
                    "work_id": work_id, "cycle_id": "prequeue", "dimension": "semantic-repeat", "decision": "accepted",
                    "payload_hash": queue_payload_digest,
                },
            )
        if work.get("primary"):
            primary_count += 1
        if work.get("claimed_progress") not in PRODUCT_OUTCOMES:
            errors.append(f"work item {work_id} has no valid progress outcome")
        if work_type in {"enabler", "maintenance"}:
            unlocks = work.get("unlocks")
            targets = {unlocks} if isinstance(unlocks, str) else set(unlocks or [])
            if not targets or not targets.issubset(committed_ids):
                errors.append(f"{work_type} work item {work_id} must unlock committed product outcomes")
            if work.get("claimed_progress") == "capability":
                errors.append(f"work item {work_id} cannot relabel enabler work as a capability")
            if work.get("primary") and phase in {"reality_audit", "intelligence", "direction", "experience"}:
                errors.append(f"{work_type} work item {work_id} cannot occupy the primary discovery lane")
    if len(ids) != len(set(ids)):
        errors.append("active work IDs must be unique")
    active_fingerprints = [work.get("work_fingerprint") for work in active_work if isinstance(work, dict)]
    if len(active_fingerprints) != len(set(active_fingerprints)):
        errors.append("active work cannot repeat a semantic work fingerprint")
    if len(active_work) > 0 and primary_count != 1:
        errors.append("active work must contain exactly one primary vertical slice")
    ready_primary_work = [
        work
        for work in active_work
        if isinstance(work, dict) and work.get("primary") and work.get("status") == "ready"
    ]
    for work in active_work:
        if (
            isinstance(work, dict)
            and work.get("primary")
            and work.get("type") in {"enabler", "maintenance"}
        ):
            errors.append(
                f"{work.get('type')} work item {work.get('id')} cannot be primary; use the existing typed p0 work type for a genuine interruption"
            )

    completed_work = portfolio.get("completed_work", [])
    if not isinstance(completed_work, list):
        errors.append("portfolio.completed_work must be an array")
        completed_work = []
    completed_work_ids: set[str] = set()
    for index, work in enumerate(completed_work):
        label = f"portfolio.completed_work[{index}]"
        if not isinstance(work, dict):
            errors.append(f"{label} must be an object")
            continue
        work_id = work.get("id")
        if not isinstance(work_id, str) or not work_id:
            errors.append(f"{label}.id is required")
        elif work_id in completed_work_ids:
            errors.append(f"completed work id {work_id} is duplicated")
        else:
            completed_work_ids.add(work_id)
        if work.get("status") != "completed":
            errors.append(f"{label}.status must be completed")
        if not isinstance(work.get("owner"), str) or not work.get("owner").strip():
            errors.append(f"{label}.owner is required")
        for field in ("completed_at", "completion_cycle_id", "completion"):
            if work.get(field) in (None, ""):
                errors.append(f"{label}.{field} is required")
        if not isinstance(work.get("completion_digest"), str) or not work.get("completion_digest"):
            errors.append(f"{label}.completion_digest is required")
        if isinstance(work.get("completion"), dict):
            for field in (
                "evidence_ids",
                "completion_evidence_digest",
                "cost_usd",
                "latency_minutes",
                "token_usage",
                "user_visible_movement",
                "reviewer_decision",
                "reviewer",
                "reviewer_grant",
            ):
                if field not in work["completion"]:
                    errors.append(f"{label}.completion.{field} is required")
        if work_id in ids:
            errors.append(f"completed work id {work_id} cannot remain active")
        if work.get("work_fingerprint") and work.get("work_fingerprint") in active_fingerprints:
            errors.append(f"completed work {work_id} repeats an active semantic fingerprint")

    completed_cycles: list[dict[str, Any]] = []
    cycles = feedback.get("cycles", [])
    if not isinstance(cycles, list):
        errors.append("feedback.cycles must be an array")
        cycles = []
    for index, cycle in enumerate(cycles):
        label = f"feedback.cycles[{index}]"
        if not isinstance(cycle, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ("id", "work_id", "work_type", "status", "started_at", "intended_outcome"):
            if cycle.get(field) in (None, ""):
                errors.append(f"{label}.{field} is required")
        if cycle.get("program_version") != program_version:
            errors.append(f"{label} belongs to a stale program")
        if cycle.get("work_type") not in ALLOWED_WORK_TYPES:
            errors.append(f"{label}.work_type is invalid")
        if cycle.get("status") not in {"running", "completed", "cancelled", "failed", "abandoned"}:
            errors.append(f"{label}.status is invalid")
        parse_time(cycle.get("started_at"), f"{label}.started_at", errors)
        if cycle.get("status") == "completed":
            completed_cycles.append(cycle)
            for field in (
                "finished_at",
                "actual_outcome",
                "evidence_ids",
                "completion_evidence_digest",
                "cost_usd",
                "latency_minutes",
                "token_usage",
                "user_visible_movement",
                "work_disposition",
                "reviewer_decision",
            ):
                if field not in cycle:
                    errors.append(f"{label}.{field} is required")
            parse_time(cycle.get("finished_at"), f"{label}.finished_at", errors)
            if cycle.get("actual_outcome") not in PRODUCT_OUTCOMES:
                errors.append(f"{label}.actual_outcome is invalid")
            if cycle.get("work_type") in {"enabler", "maintenance"} and cycle.get("actual_outcome") == "capability":
                errors.append(f"{label} cannot relabel {cycle.get('work_type')} work as a capability")
            evidence_ids = cycle.get("evidence_ids", [])
            if not isinstance(evidence_ids, list) or not set(evidence_ids).issubset(valid_evidence_ids):
                errors.append(f"{label}.evidence_ids are not valid project evidence")
            elif cycle.get("completion_evidence_digest") != completion_evidence_digest(state, evidence_ids):
                errors.append(f"{label}.completion_evidence_digest does not match its evidence")
            for field in ("cost_usd", "latency_minutes"):
                if not finite_nonnegative_number(cycle.get(field)):
                    errors.append(f"{label}.{field} must be a finite non-negative number")
            if not nonnegative_integer(cycle.get("token_usage")):
                errors.append(f"{label}.token_usage must be a non-negative integer")
            if not isinstance(cycle.get("user_visible_movement"), bool):
                errors.append(f"{label}.user_visible_movement must be boolean")
            if cycle.get("work_disposition") not in {"continue", "complete"}:
                errors.append(f"{label}.work_disposition is invalid")
            if cycle.get("reviewer_decision") not in {"accepted", "rejected"}:
                errors.append(f"{label}.reviewer_decision is invalid")
            if not isinstance(cycle.get("reviewer_grant"), dict) or cycle["reviewer_grant"].get("actor") != cycle.get("reviewer"):
                errors.append(f"{label}.reviewer_grant does not bind its reviewer")
            else:
                audit_stored_grant(
                    state,
                    cycle.get("reviewer_grant"),
                    errors,
                    f"{label}.reviewer_grant",
                    {
                        "actor": cycle.get("reviewer"),
                        "action": "finish-cycle",
                        "resource": f"cycle:{cycle.get('id')}",
                        "work_id": str(cycle.get("work_id")),
                        "cycle_id": str(cycle.get("id")),
                        "dimension": "completion",
                        "decision": f"{cycle.get('reviewer_decision')}:{cycle.get('work_disposition')}",
                        "payload_hash": command_payload_hash("finish-cycle", finish_command_payload(state, cycle)),
                    },
                )
            if cycle.get("work_disposition") == "complete" and cycle.get("reviewer_decision") != "accepted":
                errors.append(f"{label} cannot complete work after a rejected review")
            for field in ("commit", "ref"):
                if field in cycle and (not isinstance(cycle[field], str) or not cycle[field].strip()):
                    errors.append(f"{label}.{field} must be a non-empty string when supplied")
        if cycle.get("status") in {"abandoned", "failed"}:
            for field in ("finished_at", "resolution_reason", "resolved_by_lease"):
                if not cycle.get(field):
                    errors.append(f"{label}.{field} is required for resolved cycles")
            parse_time(cycle.get("finished_at"), f"{label}.finished_at", errors)

    completed_cycles_by_id = {
        cycle.get("id"): cycle
        for cycle in completed_cycles
        if isinstance(cycle.get("id"), str)
    }
    for index, work in enumerate(completed_work):
        if not isinstance(work, dict):
            continue
        label = f"portfolio.completed_work[{index}]"
        cycle = completed_cycles_by_id.get(work.get("completion_cycle_id"))
        if not cycle:
            errors.append(f"{label}.completion_cycle_id must reference a completed cycle")
            continue
        if cycle.get("work_id") != work.get("id") or cycle.get("work_disposition") != "complete":
            errors.append(f"{label}.completion_cycle_id does not complete this work")
            continue
        if work.get("completion_digest") != cycle.get("completion_digest"):
            errors.append(f"{label}.completion_digest does not match its completed cycle")
        elif work.get("completion_digest") != completion_digest(work, cycle):
            errors.append(f"{label}.completion_digest is not immutable")
        completion = work.get("completion")
        if isinstance(completion, dict):
            for field in (
                "evidence_ids",
                "completion_evidence_digest",
                "cost_usd",
                "latency_minutes",
                "token_usage",
                "user_visible_movement",
                "reviewer_decision",
                "reviewer",
                "reviewer_grant",
                "commit",
                "ref",
            ):
                if field in cycle and completion.get(field) != cycle.get(field):
                    errors.append(f"{label}.completion.{field} does not match its completed cycle")
            audit_stored_grant(
                state,
                completion.get("reviewer_grant"),
                errors,
                f"{label}.completion.reviewer_grant",
                {
                    "actor": completion.get("reviewer"),
                    "action": "finish-cycle",
                    "resource": f"cycle:{cycle.get('id')}",
                    "work_id": str(cycle.get("work_id")),
                    "cycle_id": str(cycle.get("id")),
                    "dimension": "completion",
                    "decision": f"{cycle.get('reviewer_decision')}:{cycle.get('work_disposition')}",
                    "payload_hash": command_payload_hash("finish-cycle", finish_command_payload(state, cycle)),
                },
            )

    if len(completed_cycles) >= 4:
        weights = [float(cycle.get("cost_usd") or cycle.get("latency_minutes") or 1) for cycle in completed_cycles]
        total_weight = sum(weights)
        actual = {work_type: 0.0 for work_type in expected_keys}
        for cycle, weight in zip(completed_cycles, weights):
            if cycle.get("work_type") in actual:
                actual[cycle["work_type"]] += weight
        if total_weight:
            actual_share = {key: 100 * value / total_weight for key, value in actual.items()}
            if actual_share["maintenance"] > allocation.get("maintenance", 0) + 0.001:
                errors.append("actual maintenance cycles exceed the portfolio ceiling")
            if actual_share["enabler"] > allocation.get("enabler", 0) + 0.001:
                errors.append("actual enabler cycles exceed the portfolio ceiling")
            if actual_share["capability"] + actual_share["innovation"] < 80:
                errors.append("actual capability plus innovation cycles are below 80 percent")
    if len(completed_cycles) >= 2:
        last_two = completed_cycles[-2:]
        if all(
            not cycle.get("user_visible_movement")
            and cycle.get("actual_outcome") not in {"reality", "intelligence", "experience", "learning", "adaptation"}
            for cycle in last_two
        ):
            errors.append("two consecutive cycles produced no accepted product movement or learning")

    fabric_report = validate_execution_fabric_state(
        state,
        project_root=project_root,
        valid_evidence_ids=valid_evidence_ids,
        evidence_by_id=evidence_by_id,
        errors=errors,
        warnings=warnings,
    )

    threshold = quality.get("threshold")
    if threshold != 9:
        errors.append("quality.threshold must remain 9")
    dimensions = quality.get("dimensions", {})
    if not isinstance(dimensions, dict) or set(dimensions) != set(BASE_DIMENSIONS):
        errors.append("quality.dimensions must contain the complete governed dimension set")
        dimensions = {}
    required_quality_dimensions = applicable_quality_dimensions(state)
    expected_outcome_id, expected_work_id, expected_checkpoint = current_quality_checkpoint(state)
    quality_ready = bool(required_quality_dimensions)
    for name, item in dimensions.items():
        if not isinstance(item, dict):
            errors.append(f"quality dimension {name} must be an object")
            quality_ready = False
            continue
        score = item.get("score")
        if score is not None and any(
            not isinstance(item.get(grant_name), dict)
            or item[grant_name].get("claims", {}).get("program_version") != program_version
            for grant_name in ("scorer_grant", "reviewer_grant")
        ):
            errors.append(f"quality dimension {name} belongs to a stale program")
            quality_ready = False
        required = name in required_quality_dimensions
        if required and not item.get("applicable", True):
            errors.append(f"quality dimension {name} is required for the current phase/work")
            quality_ready = False
        if not item.get("applicable", True):
            if not item.get("not_applicable_reason"):
                errors.append(f"quality dimension {name} needs a not-applicable reason")
            continue
        if not required:
            continue
        if score is None:
            quality_ready = False
            continue
        if not isinstance(score, (int, float)) or not 0 <= score <= 10:
            errors.append(f"quality dimension {name} score must be from 0 to 10")
            quality_ready = False
        elif score < (threshold if item.get("critical") else 8):
            required_score = threshold if item.get("critical") else 8
            prefix = "critical quality dimension" if item.get("critical") else "quality dimension"
            errors.append(f"{prefix} {name} is below {required_score}")
            quality_ready = False
        for field in ("rubric_version", "scored_by", "reviewed_by"):
            if not item.get(field):
                errors.append(f"quality dimension {name} lacks {field}")
                quality_ready = False
        for field, actor in (("scorer_grant", item.get("scored_by")), ("reviewer_grant", item.get("reviewed_by"))):
            if not isinstance(item.get(field), dict) or item[field].get("actor") != actor:
                errors.append(f"quality dimension {name} lacks authenticated {field}")
                quality_ready = False
        if item.get("scored_by") and item.get("scored_by") == item.get("reviewed_by"):
            errors.append(f"quality dimension {name} lacks independent review")
            quality_ready = False
        ids_for_dimension = item.get("evidence", [])
        binding = item.get("binding")
        if not isinstance(binding, dict):
            errors.append(f"quality dimension {name} lacks evidence binding")
            quality_ready = False
        else:
            for field in ("outcome_id", "work_id", "cycle_id", "rubric_version"):
                if not isinstance(binding.get(field), str) or not binding[field].strip():
                    errors.append(f"quality dimension {name} binding lacks {field}")
                    quality_ready = False
            evidence_set_digest = binding.get("evidence_digest")
            legacy_artifact_digest = binding.get("artifact_digest")
            if bool(evidence_set_digest) == bool(legacy_artifact_digest):
                errors.append(
                    f"quality dimension {name} binding must contain exactly one evidence digest"
                )
                quality_ready = False
            elif evidence_set_digest is not None and (
                not isinstance(evidence_set_digest, str)
                or evidence_set_digest != completion_evidence_digest(state, ids_for_dimension)
            ):
                errors.append(f"quality dimension {name} evidence digest does not match its evidence set")
                quality_ready = False
            if binding.get("rubric_version") != item.get("rubric_version"):
                errors.append(f"quality dimension {name} binding rubric does not match")
                quality_ready = False
            if (
                binding.get("outcome_id") != expected_outcome_id
                or binding.get("work_id") != expected_work_id
                or binding.get("cycle_id") != expected_checkpoint
            ):
                errors.append(f"quality dimension {name} is stale for the current primary checkpoint")
                quality_ready = False
        grant_claim_base = {
            "resource": f"quality:{name}",
            "work_id": expected_work_id,
            "cycle_id": expected_checkpoint,
            "dimension": name,
            "payload_hash": command_payload_hash(
                "score-quality",
                quality_command_payload(
                    {
                        "dimension": name,
                        "score": score,
                        "evidence_ids": ids_for_dimension,
                        "rubric_version": item.get("rubric_version"),
                        "scored_by": item.get("scored_by"),
                        "reviewed_by": item.get("reviewed_by"),
                        "outcome_id": (binding or {}).get("outcome_id"),
                        "work_id": (binding or {}).get("work_id"),
                        "cycle_id": (binding or {}).get("cycle_id"),
                        "artifact_digest": (binding or {}).get("artifact_digest"),
                        "evidence_digest": (binding or {}).get("evidence_digest"),
                    }
                ),
            ),
        }
        audit_stored_grant(
            state,
            item.get("scorer_grant"),
            errors,
            f"quality dimension {name} scorer grant",
            {**grant_claim_base, "actor": item.get("scored_by"), "action": "score-quality", "decision": f"score:{score}"},
        )
        audit_stored_grant(
            state,
            item.get("reviewer_grant"),
            errors,
            f"quality dimension {name} reviewer grant",
            {**grant_claim_base, "actor": item.get("reviewed_by"), "action": "score-quality-review", "decision": f"review:{score}"},
        )
        if not isinstance(ids_for_dimension, list) or not ids_for_dimension:
            errors.append(f"quality dimension {name} lacks evidence")
            quality_ready = False
        else:
            for evidence_id in ids_for_dimension:
                source = evidence_by_id.get(evidence_id)
                if evidence_id not in valid_evidence_ids or name not in (source or {}).get("quality_dimensions", []):
                    errors.append(f"quality dimension {name} cites invalid or unrelated evidence")
                    quality_ready = False
                elif (
                    source.get("outcome_id") != expected_outcome_id
                    or source.get("work_id") != expected_work_id
                    or source.get("cycle_id") != expected_checkpoint
                    or (
                        (binding or {}).get("artifact_digest") is not None
                        and source.get("artifact_sha256") != (binding or {}).get("artifact_digest")
                    )
                    or source.get("rubric_version") != item.get("rubric_version")
                ):
                    errors.append(f"quality dimension {name} evidence is stale for the current primary checkpoint")
                    quality_ready = False

    required_adaptation_fields = (
        "id", "failure_pattern", "hypothesis", "experiment", "success_metric",
        "rollback", "proposer", "time_cap_minutes", "cost_cap_usd", "program_version",
    )
    for collection_name, allowed_statuses in (
        ("pending_adaptations", {"proposed"}),
        ("applied_adaptations", {"applied", "rejected"}),
    ):
        for proposal in feedback.get(collection_name, []):
            if not isinstance(proposal, dict):
                errors.append("adaptation entries must be objects")
                continue
            if proposal.get("status") not in allowed_statuses:
                errors.append(f"adaptation {proposal.get('id')} has an invalid {collection_name} status")
            if collection_name == "pending_adaptations" and any(
                proposal.get(field) not in (None, "")
                for field in ("reviewer", "review_decision", "reviewed_at", "reviewer_grant")
            ):
                errors.append(f"pending adaptation {proposal.get('id')} carries reviewed authority")
            for field in required_adaptation_fields:
                if proposal.get(field) in (None, ""):
                    errors.append(f"adaptation {proposal.get('id')} lacks {field}")
            if proposal.get("program_version") != program_version:
                errors.append(f"adaptation {proposal.get('id')} belongs to a stale program")
            if proposal.get("meta_depth") != 1:
                errors.append(f"adaptation {proposal.get('id')} exceeds the meta-loop depth")
            if proposal.get("proposal_digest") != adaptation_proposal_digest(proposal):
                errors.append(f"adaptation {proposal.get('id')} proposal digest is invalid")
            if not nonnegative_integer(proposal.get("time_cap_minutes")):
                errors.append(f"adaptation {proposal.get('id')} time_cap_minutes must be a non-negative integer")
            if not finite_nonnegative_number(proposal.get("cost_cap_usd")):
                errors.append(f"adaptation {proposal.get('id')} cost_cap_usd must be a finite non-negative number")
            if proposal.get("status") in {"applied", "rejected"}:
                if not proposal.get("reviewer"):
                    errors.append(f"reviewed adaptation {proposal.get('id')} lacks an independent reviewer")
                if proposal.get("reviewer") == proposal.get("proposer"):
                    errors.append(f"adaptation {proposal.get('id')} is self-approved")
                expected_decision = "accepted" if proposal.get("status") == "applied" else "rejected"
                if proposal.get("review_decision") != expected_decision:
                    errors.append(f"adaptation {proposal.get('id')} review decision does not match its status")
                digest = proposal.get("proposal_digest")
                if not isinstance(digest, str) or not digest:
                    errors.append(f"adaptation {proposal.get('id')} lacks its proposal digest")
                else:
                    audit_stored_grant(
                        state, proposal.get("reviewer_grant"), errors,
                        f"adaptation {proposal.get('id')} reviewer grant",
                        {
                            "actor": proposal.get("reviewer"), "action": "review-adaptation",
                            "resource": f"adaptation:{proposal.get('id')}", "work_id": "",
                            "cycle_id": "", "dimension": "meta-loop", "decision": expected_decision,
                            "payload_hash": command_payload_hash("review-adaptation", {
                                "adaptation_id": proposal.get("id"), "proposal_digest": digest,
                                "reviewer": proposal.get("reviewer"), "decision": expected_decision,
                            }),
                        },
                    )
            protected = set(proposal.get("changes", [])) & PROTECTED_ADAPTATION_FIELDS
            if protected:
                errors.append(f"adaptation {proposal.get('id')} changes protected fields: {sorted(protected)}")

    audit_archived_program_transitions(state, errors)

    for candidate in feedback.get("core_promotion_candidates", []):
        project_ids = set(candidate.get("validated_project_ids", [])) if isinstance(candidate, dict) else set()
        if len(project_ids) < 3:
            errors.append(f"core promotion {candidate.get('id')} requires three independent projects")
        if candidate.get("proposer") == candidate.get("reviewer"):
            errors.append(f"core promotion {candidate.get('id')} requires independent review")

    validation = controller_state.get("validation")
    validation_valid = False
    if validation is not None:
        if not isinstance(validation, dict):
            errors.append("controller.validation must be an object or null")
        else:
            for field in ("program_version", "reviewer", "reviewed_at", "decision", "evidence_digest", "certifier_grant"):
                if validation.get(field) in (None, ""):
                    errors.append(f"controller.validation.{field} is required")
            parse_time(validation.get("reviewed_at"), "controller.validation.reviewed_at", errors)
            if validation.get("program_version") != program_version:
                errors.append("controller validation belongs to a stale program")
            if validation.get("decision") != "accepted":
                errors.append("controller validation must be accepted")
            if not isinstance(validation.get("certifier_grant"), dict) or validation["certifier_grant"].get("actor") != validation.get("reviewer"):
                errors.append("controller validation certifier grant does not bind its reviewer")
            else:
                _, cert_work_id, cert_checkpoint = current_quality_checkpoint(state)
                audit_stored_grant(
                    state,
                    validation.get("certifier_grant"),
                    errors,
                    "controller validation certifier grant",
                    {
                        "actor": validation.get("reviewer"),
                        "action": "certify",
                        "resource": "certification",
                        "work_id": cert_work_id,
                        "cycle_id": cert_checkpoint,
                        "dimension": str(phase),
                        "decision": "accepted",
                        "payload_hash": command_payload_hash(
                            "certify", certification_command_payload(state, str(validation.get("reviewer")))
                        ),
                    },
                )
            if validation.get("evidence_digest") != evidence_digest(state):
                errors.append("controller validation is stale for the current evidence or work")
            validation_valid = not any(error.startswith("controller validation") or error.startswith("controller.validation") for error in errors)

    reality_ready = bool(
        {
            item.get("id")
            for item in evidence.get("reality", [])
            if isinstance(item, dict)
        }.intersection(valid_evidence_ids)
    )
    direction_ready = all(
        bool(
            {
                item.get("id")
                for item in evidence.get(key, [])
                if isinstance(item, dict)
            }.intersection(valid_evidence_ids)
        )
        for key in ("reality", "intelligence", "direction", "experience")
    )
    primary_requires_fabric = bool(
        ready_primary_work
        and ready_primary_work[0].get("execution_mode", "single") == "luna_fabric"
    )
    if active_work and not quality_ready:
        errors.append(f"phase {phase} requires complete applicable quality evidence")
    scheduler_ready = (
        not errors
        and instance.get("status") == "active"
        and validation_valid
        and direction_ready
        and bool(strategy.get("current_outcome"))
        and bool(strategy.get("success_metric"))
        and not cancellation_requested
        and lease is None
        and len(ready_primary_work) == 1
        and (not primary_requires_fabric or fabric_report["ready_for_schedule"])
        and issuer_ready
        and protected_launcher_ready
    )
    if controller_state.get("schedule_enabled") and not scheduler_ready and lease is None:
        errors.append("scheduler is enabled before the controller is ready")
        scheduler_ready = False
    if not reality_ready:
        warnings.append("the instance has not completed a verified product/project reality audit")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "phase": phase,
        "program_version": program_version,
        "scheduler_ready": scheduler_ready,
        "quality_ready": quality_ready,
        "applicable_quality_dimensions": sorted(required_quality_dimensions),
        "validation_valid": validation_valid,
        "valid_evidence_count": len(valid_evidence_ids),
        "active_work_count": len(active_work),
        "ready_primary_work_count": len(ready_primary_work),
        "execution_fabric_status": state.get("execution_fabric", {}).get("status"),
        "execution_fabric_ready": fabric_report["ready_for_schedule"],
        "execution_fabric_accepted": fabric_report["accepted"],
        "luna_token_share": fabric_report["luna_token_share"],
        "actor_issuer_ready": issuer_ready,
        "protected_launcher_ready": protected_launcher_ready,
        "external_prerequisites": [] if protected_launcher_ready else [protected_launcher_blocker],
        "pending_adaptations": len(feedback.get("pending_adaptations", [])),
    }


def audit_instance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    path = state_path(project)
    store_module = control_store_module()
    store_exists = store_module.exists(project)
    if not path.exists() and not store_exists:
        print(json.dumps({"ok": False, "errors": [f"no Company OS instance at {path}"]}, indent=2))
        return 2
    try:
        store_report = store_module.audit(project) if store_exists else None
        state = store_module.load(project)[1] if store_exists else load_json(path)
        report = validate_state(state, expected_project=project)
        if store_report is not None:
            report["control_store"] = store_report
            report["errors"].extend(
                f"control store: {error}" for error in store_report["errors"]
            )
            if not store_report["state_export_match"] or not store_report["events_export_match"]:
                report["warnings"].append(
                    "transactional control exports drifted; the next governed command will rebuild them"
                )
            report["ok"] = not report["errors"]
        else:
            report["control_store"] = {
                "ok": False,
                "backend": "legacy-json",
                "migration_required": True,
            }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def brief_instance(args: argparse.Namespace) -> int:
    """Render a safe decision surface from authoritative project state."""
    project = Path(args.project).resolve()
    path = state_path(project)
    store_module = control_store_module()
    store_exists = store_module.exists(project)
    if not path.exists() and not store_exists:
        print(json.dumps({"ok": False, "errors": [f"no Company OS instance at {path}"]}, indent=2))
        return 2
    try:
        store_report = store_module.audit(project) if store_exists else None
        prior_state = None
        prior_revision = None
        change_events = []
        if store_exists:
            revision, state = store_module.load(project)
            requested_revision = getattr(args, "since_revision", None)
            if requested_revision is not None:
                if not isinstance(requested_revision, int) or isinstance(requested_revision, bool) or requested_revision < 1:
                    raise ValueError("--since-revision must be a positive integer")
                if requested_revision >= revision:
                    raise ValueError("--since-revision must be earlier than the current revision")
                prior_revision = requested_revision
            elif revision > 1:
                prior_revision = revision - 1
            if prior_revision is not None:
                prior_state = store_module.load_revision(project, prior_revision)
                change_events = store_module.load_change_events(project, prior_revision, revision)
        else:
            state = load_json(path)
        report = validate_state(state, expected_project=project)
        if store_report is not None:
            report["errors"].extend(
                f"control store: {error}" for error in store_report["errors"]
            )
            if not store_report["state_export_match"] or not store_report["events_export_match"]:
                report["warnings"].append(
                    "transactional control exports drifted; the next governed command will rebuild them"
                )
            report["ok"] = not report["errors"]
        else:
            report["errors"].append("control store migration is required")
            report["ok"] = False
        presenter = operator_brief_module()
        brief = presenter.build_operator_brief(
            state,
            report,
            store_report,
            phases=PHASES,
            critical_dimensions=BASE_DIMENSIONS,
            prior_state=prior_state,
            prior_revision=prior_revision,
            change_events=change_events,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    if args.format == "json":
        print(json.dumps(brief, indent=2, sort_keys=True))
    elif args.format == "html":
        print(presenter.render_html(brief), end="")
    else:
        print(presenter.render_markdown(brief), end="")
    return 1 if args.strict and brief["gate"]["status"] != "ready" else 0


def migrate_control_store(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    store_module = control_store_module()
    if store_module.exists(project):
        try:
            report = store_module.audit(project)
            if not report["ok"]:
                raise ValueError(
                    "transactional control store failed integrity audit: "
                    + "; ".join(report["errors"])
                )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
            return 2
        print(json.dumps({"ok": True, "changed": False, "revision": report["revision"], "backend": "sqlite"}))
        return 0
    try:
        with locked_state(project) as (_, state):
            if state.get("schema_version") != SCHEMA_VERSION or state.get("core_version") != CORE_VERSION:
                raise ValueError("upgrade the Company OS instance before migrating its control store")
            if state.get("instance", {}).get("project_root") != str(project):
                raise ValueError("instance project root does not match the migration target")
            report = validate_state(state, expected_project=project)
            if report["errors"]:
                raise ValueError(
                    "legacy instance failed validation: " + "; ".join(report["errors"])
                )
            event = {
                "at": utc_now(),
                "type": "control_store_migrated",
                "project_id": state["instance"]["project_id"],
                "program_version": state["strategy"]["program_version"],
                "backend": "sqlite",
            }
            revision = store_module.initialize(project, state, event)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "changed": True, "revision": revision, "backend": "sqlite"}))
    return 0


def upgrade_state(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("schema_version") == SCHEMA_VERSION and state.get("core_version") == CORE_VERSION:
        return state
    old_schema_version = state.get("schema_version")
    if old_schema_version not in {1, 2, 3, 4, 5, 6, 7, 8}:
        raise ValueError(f"unsupported schema version: {state.get('schema_version')}")
    old_program_version = state.get("strategy", {}).get("program_version")
    if not isinstance(old_program_version, int) or old_program_version < 1:
        raise ValueError("cannot upgrade without the true positive strategy.program_version")

    upgraded = deepcopy(state)
    upgraded_at = utc_now()
    new_program_version = old_program_version + 1

    feedback = upgraded.setdefault("feedback", {})
    upgrade_history = feedback.setdefault("schema_upgrade_history", [])
    if not isinstance(upgrade_history, list):
        raise ValueError("feedback.schema_upgrade_history must be an array")
    portfolio = upgraded.setdefault("portfolio", {})
    legacy_evidence = deepcopy(upgraded.get("evidence", {}))
    history_id = (
        f"schema-{old_schema_version}-to-{SCHEMA_VERSION}"
        f"-program-{old_program_version}-to-{new_program_version}-{uuid.uuid4().hex}"
    )
    upgrade_history.append(
        {
            "id": history_id,
            "reason": "schema_upgrade",
            "archived_at": upgraded_at,
            "from_schema_version": old_schema_version,
            "to_schema_version": SCHEMA_VERSION,
            "from_core_version": state.get("core_version"),
            "to_core_version": CORE_VERSION,
            "program_version": old_program_version,
            "next_program_version": new_program_version,
            "strategy": deepcopy(upgraded.get("strategy", {})),
            "portfolio": {
                name: deepcopy(portfolio.get(name, []))
                for name in ("committed_outcomes", "active_work", "completed_work", "cancelled_work")
            },
            "evidence": legacy_evidence,
            "feedback": {
                name: deepcopy(feedback.get(name, []))
                for name in ("cycles", "pending_adaptations", "applied_adaptations")
            },
            "execution_fabric": deepcopy(upgraded.get("execution_fabric")),
            "runtime_adapter": deepcopy(upgraded.get("runtime_adapter")),
        }
    )

    upgraded["schema_version"] = SCHEMA_VERSION
    upgraded["core_version"] = CORE_VERSION
    upgraded.setdefault("instance", {})["status"] = "paused"
    upgraded.setdefault("strategy", {})["program_version"] = new_program_version
    upgraded["strategy"]["program_updated_at"] = upgraded_at
    upgraded["strategy"]["program_fingerprint"] = strategy_fingerprint(upgraded["strategy"])
    upgraded["phase"] = "reality_audit"

    controller_state = upgraded.setdefault("controller", {})
    controller_state["validated"] = False
    controller_state["validation"] = None
    controller_state["schedule_enabled"] = False
    controller_state["cancellation_requested"] = False
    controller_state["consumed_grant_nonces"] = []
    old_generation = controller_state.get("lease_generation")
    controller_state["lease_generation"] = (old_generation if isinstance(old_generation, int) else 0) + 1
    revoked_leases = controller_state.setdefault("revoked_leases", [])
    if not isinstance(revoked_leases, list):
        raise ValueError("controller.revoked_leases must be an array")
    if controller_state.get("lease"):
        revoked_leases.append(
            {**controller_state["lease"], "revoked_at": upgraded_at, "reason": "schema_upgrade"}
        )
    controller_state["lease"] = None
    controller_state["last_cycle_at"] = None
    controller_state["restart_checkpoint"] = {
        "reason": "schema_upgrade",
        "from_schema_version": old_schema_version,
        "to_schema_version": SCHEMA_VERSION,
        "from_program_version": old_program_version,
        "program_version": new_program_version,
        "phase": "reality_audit",
        "status": "evidence_required",
        "created_at": upgraded_at,
        "history_id": history_id,
    }

    portfolio["committed_outcomes"] = []
    portfolio["active_work"] = []
    portfolio["completed_work"] = []
    portfolio["cancelled_work"] = []

    feedback.setdefault("archived_evidence", [])
    feedback.setdefault("archived_runtime_adapters", [])
    feedback.setdefault("archived_adaptations", [])
    feedback.setdefault("archived_quality_scorecards", [])
    feedback.setdefault("program_transition_repairs", [])
    upgraded["evidence"] = {key: [] for key in EVIDENCE_BUCKETS}
    feedback["cycles"] = []
    feedback["pending_adaptations"] = []
    feedback["applied_adaptations"] = []
    upgraded["execution_fabric"] = empty_execution_fabric(new_program_version)
    upgraded["runtime_adapter"] = empty_runtime_adapter(new_program_version)

    quality = upgraded.setdefault("quality", {})
    quality["threshold"] = 9
    old_dimensions = quality.get("dimensions", {})
    quality["dimensions"] = {
        name: {
            "critical": critical,
            "applicable": (
                old_dimensions.get(name, {}).get("applicable", True)
                if isinstance(old_dimensions, dict) and isinstance(old_dimensions.get(name), dict)
                else True
            ),
            "score": None,
            "evidence": [],
            "rubric_version": None,
            "scored_by": None,
            "reviewed_by": None,
            "scorer_grant": None,
            "reviewer_grant": None,
            "binding": None,
        }
        for name, critical in BASE_DIMENSIONS.items()
    }
    return upgraded


def upgrade_instance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project, require_issuer=False) as (path, state):
            upgraded = upgrade_state(state)
            if upgraded is state:
                print(json.dumps({"ok": True, "changed": False, "schema_version": SCHEMA_VERSION}))
                return 0
            persist_state_event(project, path, upgraded, "instance_upgraded", core_version=CORE_VERSION)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "changed": True, "schema_version": SCHEMA_VERSION}))
    return 0


def replace_program(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            if state.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("run upgrade before replacing the program")
            old_version = state["strategy"]["program_version"]
            old_strategy = deepcopy(state["strategy"])
            old_runtime_adapter = deepcopy(state.get("runtime_adapter", {}))
            state["feedback"].setdefault("archived_evidence", []).append(
                {
                    "program_version": old_version,
                    "archived_at": utc_now(),
                    "reason": args.reason,
                    "evidence": state["evidence"],
                }
            )
            cancelled_at = utc_now()
            for work in state["portfolio"].get("active_work", []):
                state["portfolio"].setdefault("cancelled_work", []).append(
                    {**work, "status": "cancelled", "cancelled_at": cancelled_at, "reason": args.reason}
                )
            old_lease = state["controller"].get("lease")
            if old_lease:
                state["controller"].setdefault("revoked_leases", []).append(
                    {**old_lease, "revoked_at": cancelled_at, "reason": "program_replaced"}
                )
            state["controller"]["lease_generation"] += 1
            state["controller"]["lease"] = None
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            state["controller"]["schedule_enabled"] = False
            state["controller"]["cancellation_requested"] = False
            state["controller"]["restart_checkpoint"] = None
            state["instance"]["status"] = "paused"
            state["portfolio"]["active_work"] = []
            state["portfolio"]["committed_outcomes"] = []
            state["evidence"] = {key: [] for key in EVIDENCE_BUCKETS}
            state["phase"] = "reality_audit"
            state["strategy"].update(
                {
                    "north_star": args.north_star,
                    "current_outcome": args.current_outcome,
                    "success_metric": args.success_metric,
                    "program_version": old_version + 1,
                    "program_updated_at": utc_now(),
                }
            )
            state["strategy"]["program_fingerprint"] = strategy_fingerprint(state["strategy"])
            archive_program_transition_state(
                state,
                source_program_version=old_version,
                replacement_program_version=old_version + 1,
                archived_at=cancelled_at,
                reason=args.reason,
                trigger="program_replaced",
                source_strategy=old_strategy,
                source_runtime_adapter=old_runtime_adapter,
            )
            state["feedback"]["pending_adaptations"] = []
            state["feedback"]["applied_adaptations"] = []
            clear_quality_scores(state)
            state["feedback"].setdefault("archived_execution_fabrics", []).append(
                {
                    "program_version": old_version,
                    "archived_at": cancelled_at,
                    "reason": args.reason,
                    "execution_fabric": deepcopy(state.get("execution_fabric")),
                }
            )
            state["execution_fabric"] = empty_execution_fabric(old_version + 1)
            state["runtime_adapter"] = empty_runtime_adapter(old_version + 1)
            persist_state_event(
                project,
                path,
                state,
                "program_replaced",
                old_program_version=old_version,
                reason=args.reason,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "program_version": old_version + 1, "status": "paused"}))
    return 0


def repair_program_transition(args: argparse.Namespace) -> int:
    """Archive one exact stale replace-program transition under independent authority."""
    project = Path(args.project).resolve()
    try:
        if not control_store_module().exists(project):
            raise ValueError("repair-program-transition requires the transactional control store")
        if _ACTIVE_COMMAND_ENVELOPE.get() is None:
            raise ValueError("repair-program-transition requires a stable command key")
        with locked_state(project) as (path, state):
            current_version = state.get("strategy", {}).get("program_version")
            source_version = current_version - 1 if isinstance(current_version, int) else None
            transition_id = (
                program_transition_id(source_version, current_version)
                if isinstance(source_version, int) and isinstance(current_version, int)
                else None
            )
            repairs = state.get("feedback", {}).get("program_transition_repairs", [])
            existing = next(
                (
                    item for item in repairs
                    if isinstance(item, dict) and item.get("transition_id") == transition_id
                ),
                None,
            )
            if existing is not None:
                raise ValueError(
                    "program transition is already repaired; only the original exact command receipt may be replayed"
                )

            store_transaction = _ACTIVE_CONTROL_STORE_TRANSACTION.get()
            if store_transaction is None or store_transaction.base_revision < 2:
                raise ValueError("repair requires the exact pre-transition state revision")
            source_state = store_transaction.load_revision(store_transaction.base_revision - 1)
            transition_event_record = store_transaction.load_event(store_transaction.base_revision)
            candidate, payload, affected_actors = prepare_stale_program_transition_repair(
                state,
                source_state=source_state,
                transition_event_record=transition_event_record,
                source_state_revision=store_transaction.base_revision - 1,
                source_state_digest=hashlib.sha256(
                    canonical_json(source_state).encode("utf-8")
                ).hexdigest(),
                transition_state_revision=store_transaction.base_revision,
                transition_state_digest=hashlib.sha256(
                    canonical_json(state).encode("utf-8")
                ).hexdigest(),
            )
            reviewer = args.reviewer.strip() if isinstance(args.reviewer, str) else ""
            if not reviewer:
                raise ValueError("repair reviewer must be a non-empty actor")
            if reviewer in affected_actors:
                raise ValueError("repair reviewer must be independent of every affected authority actor")
            repair_grant = verify_actor_grant(
                candidate,
                args.repair_grant,
                reviewer,
                "repair-program-transition",
                resource=f"program-transition:{payload['source_program_version']}:{payload['replacement_program_version']}",
                work_id="",
                cycle_id="",
                dimension="state-integrity",
                decision="archive-stale-authority",
                payload_hash=command_payload_hash("repair-program-transition", payload),
            )
            repaired_at = utc_now()
            candidate["feedback"].setdefault("program_transition_repairs", []).append(
                {
                    "transition_id": payload["transition_id"],
                    "source_program_version": payload["source_program_version"],
                    "replacement_program_version": payload["replacement_program_version"],
                    "reason": payload["reason"],
                    "repaired_at": repaired_at,
                    "reviewer": reviewer,
                    "payload": payload,
                    "repair_grant": repair_grant,
                }
            )
            persist_state_event(
                project,
                path,
                candidate,
                "program_transition_repaired",
                transition_id=payload["transition_id"],
                source_program_version=payload["source_program_version"],
                adaptation_archive_digest=payload["adaptation_archive_digest"],
                quality_archive_digest=payload["quality_archive_digest"],
                runtime_archive_digest=payload["runtime_archive_digest"],
                candidate_state_digest=payload["candidate_state_digest"],
                source_state_revision=payload["source_state_revision"],
                source_state_digest=payload["source_state_digest"],
                transition_state_revision=payload["transition_state_revision"],
                transition_state_digest=payload["transition_state_digest"],
                transition_event_id=payload["transition_event"]["event_id"],
                transition_event_payload_sha256=payload["transition_event"]["event_payload_sha256"],
                strategy_transition_digest=payload["transition_event"]["strategy_transition_digest"],
                reviewer=reviewer,
                repair_grant_digest=repair_grant["grant_digest"],
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({
        "ok": True,
        "transition_id": payload["transition_id"],
        "program_version": payload["replacement_program_version"],
        "idempotent": False,
    }))
    return 0


def cancel_instance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            cancelled_at = utc_now()
            old_lease = state["controller"].get("lease")
            if old_lease:
                state["controller"].setdefault("revoked_leases", []).append(
                    {**old_lease, "revoked_at": cancelled_at, "reason": args.reason}
                )
            for work in state["portfolio"].get("active_work", []):
                state["portfolio"].setdefault("cancelled_work", []).append(
                    {**work, "status": "cancelled", "cancelled_at": cancelled_at, "reason": args.reason}
                )
            for cycle in state.get("feedback", {}).get("cycles", []):
                if isinstance(cycle, dict) and cycle.get("status") == "running":
                    cycle.update(
                        {
                            "status": "cancelled",
                            "finished_at": cancelled_at,
                            "resolution_reason": args.reason,
                        }
                    )
            state["portfolio"]["active_work"] = []
            state["controller"]["lease_generation"] += 1
            state["controller"]["lease"] = None
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            state["controller"]["schedule_enabled"] = False
            state["controller"]["cancellation_requested"] = True
            state["instance"]["status"] = "cancelled"
            fabric = state.setdefault(
                "execution_fabric",
                empty_execution_fabric(state["strategy"]["program_version"]),
            )
            if fabric.get("status") != "unconfigured":
                fabric.update(
                    {
                        "status": "cancelled",
                        "cancelled_at": cancelled_at,
                        "cancellation_reason": args.reason,
                    }
                )
            persist_state_event(project, path, state, "instance_cancelled", reason=args.reason)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "status": "cancelled", "lease_revoked": bool(old_lease)}))
    return 0


def record_evidence(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            artifact = project_local_path(project, args.artifact)
            if artifact is None or not artifact.is_file() or artifact.is_symlink():
                raise ValueError("artifact must be an existing file inside the project")
            if args.author == args.reviewer:
                raise ValueError("evidence requires an independent reviewer")
            artifact_bytes = artifact.read_bytes()
            artifact_digest = _bytes_sha256(artifact_bytes)
            snapshot_path = publish_evidence_snapshot(project, artifact_bytes, artifact_digest)
            evidence_id = args.id or f"{args.outcome}-{uuid.uuid4().hex[:12]}"
            item = {
                "id": evidence_id,
                "outcome": args.outcome,
                "project_id": state["instance"]["project_id"],
                "program_version": state["strategy"]["program_version"],
                "artifact_path": snapshot_path,
                "source_artifact_path": str(artifact.relative_to(project)),
                "artifact_sha256": artifact_digest,
                "snapshot_path": snapshot_path,
                "snapshot_sha256": artifact_digest,
                "active": True,
                "observed_at": utc_now(),
                "freshness_days": args.freshness_days,
                "source": args.source,
                "decision_impact": args.decision_impact,
                "author": args.author,
                "reviewer": args.reviewer,
                "quality_dimensions": args.quality_dimensions or [],
            }
            for field in ("outcome_id", "work_id", "cycle_id", "rubric_version"):
                value = getattr(args, field, None)
                if value:
                    item[field] = value
            candidate = deepcopy(state)
            candidate["evidence"][args.outcome].append(item)
            report = validate_state(candidate, expected_project=project)
            item_errors = [
                error
                for error in report["errors"]
                if error.startswith(f"evidence.{args.outcome}")
                or evidence_id in error
            ]
            if item_errors:
                raise ValueError("; ".join(item_errors))
            state["evidence"][args.outcome].append(item)
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(project, path, state, "evidence_recorded", evidence_id=evidence_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "evidence_id": evidence_id, "outcome": args.outcome}))
    return 0


def supersede_evidence(args: argparse.Namespace) -> int:
    """Archive one drifted current record and install its snapshot-backed successor."""
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            controller_state = state.get("controller", {})
            if state.get("instance", {}).get("status") != "paused":
                raise ValueError("evidence recovery requires a paused instance")
            if controller_state.get("schedule_enabled"):
                raise ValueError("evidence recovery requires scheduling to remain disabled")
            if controller_state.get("lease") is not None:
                raise ValueError("evidence recovery requires no active lease")
            if controller_state.get("cancellation_requested"):
                raise ValueError("evidence recovery is unavailable after cancellation")
            if any(isinstance(cycle, dict) and cycle.get("status") == "running" for cycle in state.get("feedback", {}).get("cycles", [])):
                raise ValueError("evidence recovery requires no running cycle")
            matches = [
                (bucket, index, item) for bucket in EVIDENCE_BUCKETS
                for index, item in enumerate(state.get("evidence", {}).get(bucket, []))
                if isinstance(item, dict) and item.get("id") == args.evidence_id
            ]
            if len(matches) != 1:
                raise ValueError("superseded evidence ID must identify exactly one current evidence record")
            bucket, index, predecessor = matches[0]
            if not evidence_is_active(predecessor) or predecessor.get("program_version") != state["strategy"]["program_version"]:
                raise ValueError("only active current-program evidence may be superseded")
            if any(
                isinstance(cycle, dict) and cycle.get("status") == "completed" and args.evidence_id in cycle.get("evidence_ids", [])
                for cycle in state.get("feedback", {}).get("cycles", [])
            ):
                raise ValueError("completed cycle references the evidence and prevents supersession")
            fabric = state.get("execution_fabric", {})
            if fabric.get("status") == "accepted" and any(
                args.evidence_id in entry.get("report", {}).get("evidence_ids", [])
                for manager in fabric.get("managers", {}).values() if isinstance(manager, dict)
                for entry in manager.get("reports", []) if isinstance(entry, dict)
            ):
                raise ValueError("accepted fabric report references the evidence and prevents supersession")
            if args.author == args.reviewer:
                raise ValueError("evidence recovery requires an independent reviewer")
            artifact = project_local_path(project, args.artifact)
            if artifact is None or not artifact.is_file() or artifact.is_symlink():
                raise ValueError("artifact must be an existing regular file inside the project")
            if not isinstance(args.id, str) or not args.id.strip():
                raise ValueError("replacement evidence ID is required for signed supersession")
            replacement_id = args.id
            if replacement_id == args.evidence_id or any(
                isinstance(item, dict) and item.get("id") == replacement_id
                for records in state.get("evidence", {}).values() for item in records
            ):
                raise ValueError("replacement evidence ID already exists")
            if any(
                isinstance(archive, dict) and isinstance(archive.get("record"), dict)
                and archive["record"].get("id") == replacement_id
                for archive in state.get("feedback", {}).get("archived_evidence", [])
            ):
                raise ValueError("replacement evidence ID is already archived")
            bytes_ = artifact.read_bytes()
            digest = _bytes_sha256(bytes_)
            source_artifact_path = str(artifact.relative_to(project))
            review_payload = supersede_evidence_review_payload(
                args,
                predecessor=predecessor,
                replacement_id=replacement_id,
                artifact_digest=digest,
                bucket=bucket,
                source_artifact_path=source_artifact_path,
            )
            reviewer_grant = verify_actor_grant(
                state, args.reviewer_grant, args.reviewer, "supersede-evidence",
                resource=f"evidence:{args.evidence_id}", work_id="", cycle_id="",
                dimension="evidence", decision="accepted",
                payload_hash=command_payload_hash("supersede-evidence", review_payload),
            )
            snapshot_path = publish_evidence_snapshot(project, bytes_, digest)
            now = utc_now()
            replacement = {
                "id": replacement_id, "outcome": bucket,
                "project_id": state["instance"]["project_id"],
                "program_version": state["strategy"]["program_version"],
                "artifact_path": snapshot_path,
                "source_artifact_path": source_artifact_path,
                "artifact_sha256": digest,
                "snapshot_path": snapshot_path, "snapshot_sha256": digest, "active": True,
                "supersedes_evidence_id": args.evidence_id, "observed_at": now,
                "freshness_days": args.freshness_days if args.freshness_days is not None else predecessor.get("freshness_days"),
                "source": args.source, "decision_impact": args.decision_impact,
                "author": args.author, "reviewer": args.reviewer,
                "quality_dimensions": list(args.quality_dimensions) if args.quality_dimensions is not None else list(predecessor.get("quality_dimensions", [])),
                "reviewer_grant": reviewer_grant,
            }
            for field in ("outcome_id", "work_id", "cycle_id", "rubric_version"):
                value = getattr(args, field, None)
                if value is None:
                    value = predecessor.get(field)
                if value:
                    replacement[field] = value
            archived_record = deepcopy(predecessor)
            archived_record.update({"active": False, "superseded_by_evidence_id": replacement_id, "superseded_at": now})
            old_snapshot_available = False
            if evidence_snapshot_fields(archived_record):
                old_digest = archived_record.get("snapshot_sha256")
                old_snapshot = project_local_path(project, archived_record.get("snapshot_path"))
                old_snapshot_available = bool(
                    isinstance(old_digest, str) and old_snapshot == evidence_snapshot_path(project, old_digest)
                    and old_snapshot is not None and old_snapshot.is_file() and not old_snapshot.is_symlink()
                    and sha256_file(old_snapshot) == old_digest
                )
                if not old_snapshot_available:
                    raise ValueError("snapshot-backed predecessor must retain a valid immutable snapshot")
            candidate = deepcopy(state)
            candidate["evidence"][bucket][index] = replacement
            candidate.setdefault("feedback", {}).setdefault("archived_evidence", []).append({
                "archive_kind": "evidence_supersession",
                "project_id": state["instance"]["project_id"], "bucket": bucket, "record": archived_record,
                "old_snapshot_available": old_snapshot_available, "superseded_by_evidence_id": replacement_id,
                "superseded_at": now, "reason": args.reason, "review_payload": review_payload,
                "reviewer_grant": reviewer_grant,
            })
            clear_quality_scores_citing(candidate, args.evidence_id)
            candidate["controller"]["validation"] = None
            candidate["controller"]["validated"] = False
            candidate["controller"]["schedule_enabled"] = False
            baseline_errors = set(validate_state(state, expected_project=project)["errors"])
            candidate_errors = set(validate_state(candidate, expected_project=project)["errors"])
            evidence_label = f"evidence.{bucket}[{index}]"
            if not any(error.startswith(evidence_label) for error in baseline_errors):
                raise ValueError("named predecessor is not invalid and cannot be superseded")
            remaining_predecessor_errors = sorted(
                error for error in candidate_errors if error.startswith(evidence_label)
            )
            if remaining_predecessor_errors:
                raise ValueError(
                    "evidence recovery does not repair the named predecessor: "
                    + "; ".join(remaining_predecessor_errors)
                )
            introduced = candidate_errors - baseline_errors
            if introduced:
                raise ValueError("evidence recovery introduces validation errors: " + "; ".join(sorted(introduced)))
            if len(candidate_errors) >= len(baseline_errors):
                raise ValueError("evidence recovery did not remove an existing validation error")
            state["evidence"][bucket][index] = replacement
            state.setdefault("feedback", {}).setdefault("archived_evidence", []).append(candidate["feedback"]["archived_evidence"][-1])
            clear_quality_scores_citing(state, args.evidence_id)
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            state["controller"]["schedule_enabled"] = False
            persist_state_event(
                project, path, state, "evidence_superseded",
                predecessor_evidence_id=args.evidence_id,
                evidence_id=replacement_id,
                old_artifact_sha256=predecessor.get("artifact_sha256"),
                new_artifact_sha256=digest,
                old_snapshot_available=old_snapshot_available,
                outcome=bucket, reason=args.reason, reviewer=args.reviewer,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "evidence_id": replacement_id, "superseded_evidence_id": args.evidence_id, "outcome": bucket}))
    return 0


def correct_evidence(args: argparse.Namespace) -> int:
    """Replace one structurally valid JSON record whose Git commit claim is false.

    This is deliberately separate from structural evidence recovery. It supports
    exactly one typed semantic correction and requires two independently signed
    actor decisions before the old immutable bytes are retracted.
    """
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            controller_state = state.get("controller", {})
            if state.get("instance", {}).get("status") != "paused":
                raise ValueError("semantic evidence correction requires a paused instance")
            if controller_state.get("schedule_enabled"):
                raise ValueError("semantic evidence correction requires scheduling to remain disabled")
            if controller_state.get("lease") is not None:
                raise ValueError("semantic evidence correction requires no active lease")
            if controller_state.get("cancellation_requested"):
                raise ValueError("semantic evidence correction is unavailable after cancellation")
            if any(
                isinstance(cycle, dict) and cycle.get("status") == "running"
                for cycle in state.get("feedback", {}).get("cycles", [])
            ):
                raise ValueError("semantic evidence correction requires no running cycle")

            matches = [
                (bucket, index, item)
                for bucket in EVIDENCE_BUCKETS
                for index, item in enumerate(state.get("evidence", {}).get(bucket, []))
                if isinstance(item, dict) and item.get("id") == args.evidence_id
            ]
            if len(matches) != 1:
                raise ValueError("corrected evidence ID must identify exactly one current evidence record")
            bucket, index, predecessor = matches[0]
            if not evidence_is_active(predecessor) or predecessor.get("program_version") != state["strategy"]["program_version"]:
                raise ValueError("only active current-program evidence may be corrected")
            if predecessor.get("active") is not True:
                raise ValueError("semantic correction requires predecessor active=true explicitly")
            evidence_label = f"evidence.{bucket}[{index}]"
            predecessor_errors = [
                error
                for error in validate_state(state, expected_project=project)["errors"]
                if (
                    error.startswith(evidence_label)
                    # Lineage invariants are intentionally global rather than
                    # indexed by bucket.  A semantic correction must never be
                    # allowed to archive the offending record and thereby make
                    # one of these pre-existing errors disappear.
                    or error.startswith("evidence ")
                    or error.startswith("evidence supersession ")
                    or error.startswith("feedback.archived_evidence[")
                )
            ]
            if predecessor_errors:
                raise ValueError(
                    "semantic correction requires a structurally valid predecessor: "
                    + "; ".join(predecessor_errors)
                )
            if not evidence_snapshot_fields(predecessor):
                raise ValueError("semantic correction requires an immutable snapshot-backed predecessor")
            if any(
                isinstance(cycle, dict)
                and cycle.get("status") == "completed"
                and args.evidence_id in cycle.get("evidence_ids", [])
                for cycle in state.get("feedback", {}).get("cycles", [])
            ):
                raise ValueError("completed cycle evidence is terminal and cannot be corrected")
            if any(
                args.evidence_id in (work.get("completion") or {}).get("evidence_ids", [])
                for work in state.get("portfolio", {}).get("completed_work", [])
                if isinstance(work, dict) and isinstance(work.get("completion"), dict)
            ):
                raise ValueError("completed work evidence is terminal and cannot be corrected")
            fabric = state.get("execution_fabric", {})
            if fabric.get("status") == "accepted" and any(
                args.evidence_id in entry.get("report", {}).get("evidence_ids", [])
                for manager in fabric.get("managers", {}).values() if isinstance(manager, dict)
                for entry in manager.get("reports", []) if isinstance(entry, dict)
            ):
                raise ValueError("accepted execution-fabric evidence is terminal and cannot be corrected")

            replacement_id = args.id
            historical_ids = {
                item.get("id")
                for records in state.get("evidence", {}).values()
                for item in records if isinstance(item, dict)
            }
            historical_ids.update(
                archive.get("record", {}).get("id")
                for archive in state.get("feedback", {}).get("archived_evidence", [])
                if isinstance(archive, dict) and isinstance(archive.get("record"), dict)
            )
            if not isinstance(replacement_id, str) or not replacement_id.strip() or replacement_id in historical_ids:
                raise ValueError("replacement evidence ID must be new and non-empty")
            if args.declarant == args.adjudicator:
                raise ValueError("semantic correction requires distinct declarant and adjudicator")
            conflicted = {predecessor.get("author"), predecessor.get("reviewer"), args.declarant}
            conflicted.discard(None)
            if args.adjudicator in conflicted:
                raise ValueError("semantic correction adjudicator must be independent of predecessor and replacement actors")
            if not isinstance(args.reason, str) or not args.reason.strip():
                raise ValueError("semantic correction reason is required")
            transition_errors: list[str] = []
            transition_time = parse_time(args.transition_at, "semantic correction transition_at", transition_errors)
            current_time = datetime.now(timezone.utc)
            if (
                transition_errors or transition_time is None
                or transition_time > current_time + timedelta(seconds=5)
                or current_time - transition_time > timedelta(minutes=5)
            ):
                raise ValueError("semantic correction transition_at must be a current signed timestamp")

            artifact = project_local_path(project, args.artifact)
            if artifact is None or not artifact.is_file() or artifact.is_symlink():
                raise ValueError("replacement artifact must be an existing regular file inside the project")
            old_snapshot = project_local_path(project, predecessor.get("snapshot_path"))
            old_digest = predecessor.get("snapshot_sha256")
            if (
                old_snapshot is None or old_snapshot.is_symlink() or not old_snapshot.is_file()
                or not isinstance(old_digest, str) or sha256_file(old_snapshot) != old_digest
            ):
                raise ValueError("semantic correction predecessor snapshot is unavailable or corrupt")
            try:
                old_document = json.loads(old_snapshot.read_text(encoding="utf-8"))
                new_document = json.loads(artifact.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError("git_commit_identity correction requires valid JSON documents") from None
            if not isinstance(old_document, dict) or not isinstance(new_document, dict):
                raise ValueError("git_commit_identity correction requires JSON objects")
            if not re.fullmatch(r"[0-9a-f]{40}", args.old_value or "") or not re.fullmatch(r"[0-9a-f]{40}", args.new_value or ""):
                raise ValueError("git_commit_identity values must be full lowercase SHA-1 commit identifiers")
            if args.old_value == args.new_value or old_document.get("commit") != args.old_value or new_document.get("commit") != args.new_value:
                raise ValueError("git_commit_identity old and new values do not match the documents")
            expected_document = deepcopy(old_document)
            expected_document["commit"] = args.new_value
            if new_document != expected_document:
                raise ValueError("git_commit_identity replacement may differ only at /commit")
            resolved = subprocess.run(
                ["git", "-C", str(project), "rev-parse", f"{args.new_value}^{{commit}}"],
                capture_output=True, text=True, check=False,
            )
            if resolved.returncode != 0 or resolved.stdout.strip() != args.new_value:
                raise ValueError("corrected commit does not resolve to an exact local Git commit")

            replacement_bytes = artifact.read_bytes()
            replacement_digest = _bytes_sha256(replacement_bytes)
            source_artifact_path = str(artifact.relative_to(project))
            review_payload = correct_evidence_review_payload(
                args,
                predecessor=predecessor,
                replacement_id=replacement_id,
                replacement_digest=replacement_digest,
                bucket=bucket,
                source_artifact_path=source_artifact_path,
            )
            payload_hash = command_payload_hash("correct-evidence", review_payload)
            declarant_grant = verify_actor_grant(
                state, args.declarant_grant, args.declarant, "correct-evidence-declare",
                resource=f"evidence:{args.evidence_id}", work_id="", cycle_id="",
                dimension="evidence", decision="proposed", payload_hash=payload_hash,
            )
            adjudicator_grant = verify_actor_grant(
                state, args.adjudicator_grant, args.adjudicator, "correct-evidence-adjudicate",
                resource=f"evidence:{args.evidence_id}", work_id="", cycle_id="",
                dimension="evidence", decision="accepted", payload_hash=payload_hash,
            )

            snapshot_path = publish_evidence_snapshot(project, replacement_bytes, replacement_digest)
            now = args.transition_at
            replacement = corrected_evidence_record(
                args,
                predecessor=predecessor,
                replacement_id=replacement_id,
                replacement_digest=replacement_digest,
                source_artifact_path=source_artifact_path,
            )
            if snapshot_path != replacement["snapshot_path"]:
                raise ValueError("semantic correction snapshot path is not deterministic")
            archived_record = deepcopy(predecessor)
            archived_record.update({
                "active": False,
                "superseded_by_evidence_id": replacement_id,
                "superseded_at": now,
            })
            archive = {
                "archive_kind": "evidence_supersession",
                "transition_kind": "semantic_retraction",
                "project_id": state["instance"]["project_id"],
                "bucket": bucket,
                "record": archived_record,
                "old_snapshot_available": True,
                "superseded_by_evidence_id": replacement_id,
                "superseded_at": now,
                "reason": args.reason,
                "correction_payload": review_payload,
                "declarant_grant": declarant_grant,
                "adjudicator_grant": adjudicator_grant,
            }
            cited_quality_before = any(
                args.evidence_id in item.get("evidence", [])
                for item in state.get("quality", {}).get("dimensions", {}).values()
                if isinstance(item, dict)
            )
            candidate = deepcopy(state)
            candidate["evidence"][bucket][index] = replacement
            candidate.setdefault("feedback", {}).setdefault("archived_evidence", []).append(archive)
            clear_quality_scores_citing(candidate, args.evidence_id)
            candidate["controller"]["validation"] = None
            candidate["controller"]["validated"] = False
            candidate["controller"]["schedule_enabled"] = False
            baseline_errors = set(validate_state(state, expected_project=project)["errors"])
            candidate_errors = set(validate_state(candidate, expected_project=project)["errors"])
            intentional_readiness_errors = (
                {f"phase {state.get('phase')} requires complete applicable quality evidence"}
                if cited_quality_before else set()
            )
            introduced = (candidate_errors - baseline_errors) - intentional_readiness_errors
            if introduced:
                raise ValueError("semantic correction introduces validation errors: " + "; ".join(sorted(introduced)))

            state["evidence"][bucket][index] = replacement
            state.setdefault("feedback", {}).setdefault("archived_evidence", []).append(archive)
            clear_quality_scores_citing(state, args.evidence_id)
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            state["controller"]["schedule_enabled"] = False
            persist_state_event(
                project, path, state, "evidence_semantically_corrected",
                predecessor_evidence_id=args.evidence_id,
                evidence_id=replacement_id,
                correction_type="git_commit_identity",
                old_value=args.old_value,
                new_value=args.new_value,
                reviewer=args.adjudicator,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({
        "ok": True,
        "evidence_id": replacement_id,
        "corrected_evidence_id": args.evidence_id,
        "correction_type": "git_commit_identity",
        "outcome": bucket,
    }))
    return 0


def advance_phase(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            current = state.get("phase")
            if current not in PHASES or args.phase not in PHASES:
                raise ValueError("current and target phases must be governed phases")
            if PHASES.index(args.phase) != PHASES.index(current) + 1:
                raise ValueError("phase advancement must move exactly one stage")
            current_report = validate_state(state, expected_project=project)
            if state.get("portfolio", {}).get("active_work") and not current_report["quality_ready"]:
                raise ValueError(f"phase {current} cannot exit before current quality is ready")
            candidate = deepcopy(state)
            candidate["phase"] = args.phase
            clear_quality_scores(candidate)
            if current == "reality_audit" and args.phase == "intelligence":
                candidate["controller"]["restart_checkpoint"] = None
            report = validate_state(candidate, expected_project=project)
            phase_errors = [
                error
                for error in report["errors"]
                if error.startswith("evidence.")
                or (
                    error.startswith(f"phase {args.phase}")
                    and "requires complete applicable quality evidence" not in error
                )
            ]
            if phase_errors:
                raise ValueError("; ".join(phase_errors))
            state["phase"] = args.phase
            clear_quality_scores(state)
            if current == "reality_audit" and args.phase == "intelligence":
                state["controller"]["restart_checkpoint"] = None
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(project, path, state, "phase_advanced", from_phase=current, to_phase=args.phase)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "phase": args.phase}))
    return 0


def commit_outcome(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            outcomes = state["portfolio"]["committed_outcomes"]
            if any(outcome.get("id") == args.id for outcome in outcomes):
                raise ValueError("committed outcome id already exists")
            outcomes.append(
                {
                    "id": args.id,
                    "type": args.type,
                    "title": args.title,
                    "user_visible_outcome": args.user_visible_outcome,
                    "program_version": state["strategy"]["program_version"],
                    "status": "active",
                }
            )
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(project, path, state, "outcome_committed", outcome_id=args.id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "outcome_id": args.id}))
    return 0


def queue_work(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            active = state["portfolio"]["active_work"]
            if any(work.get("id") == args.id for work in active):
                raise ValueError("active work id already exists")
            if len(active) >= state["controller"]["max_active_work"]:
                raise ValueError("active work exceeds the configured work-in-progress limit")
            primary_eligible = args.type not in {"enabler", "maintenance"}
            if args.primary == "true" and not primary_eligible:
                raise ValueError(
                    "maintenance or enabler work cannot be primary; use the existing typed p0 work type for a genuine interruption"
                )
            if not active and not primary_eligible:
                raise ValueError("queue a capability, innovation, or typed p0 primary before maintenance or enabler work")
            if args.type in {"capability", "innovation"} and getattr(args, "outcome_id", None) not in {
                outcome.get("id") for outcome in state["portfolio"]["committed_outcomes"]
            }:
                raise ValueError("capability or innovation work must reference a committed outcome")
            if args.type == "p0":
                if (
                    getattr(args, "severity", None) != "P0"
                    or not getattr(args, "incident_ref", None)
                    or not getattr(args, "justification", None)
                    or not getattr(args, "incident_actor", None)
                    or not getattr(args, "approval_actor", None)
                    or args.incident_actor == args.approval_actor
                    or args.approval_actor == args.owner
                ):
                    raise ValueError("p0 work requires a P0 incident and independent specific approval actors")
            primary = args.primary == "true" or (not active and primary_eligible)
            if primary:
                for work in active:
                    work["primary"] = False
            canonical_queue_payload = queue_command_payload(args)
            canonical_queue_payload["primary"] = primary
            item = {
                "id": args.id,
                "type": args.type,
                "primary": primary,
                "title": args.title,
                "user_visible_outcome": args.user_visible_outcome,
                "claimed_progress": args.claimed_progress,
                "status": "ready",
                "program_version": state["strategy"]["program_version"],
                "owner": args.owner,
                "execution_mode": getattr(args, "execution_mode", "single"),
                "queued_primary": primary,
                "queue_payload": canonical_queue_payload,
            }
            if getattr(args, "outcome_id", None):
                item["outcome_id"] = args.outcome_id
            if args.unlocks:
                item["unlocks"] = args.unlocks
            if args.type == "p0":
                queue_payload_hash = command_payload_hash("queue-work", canonical_queue_payload)
                incident_grant = verify_actor_grant(
                    state, getattr(args, "incident_grant", None), args.incident_actor, "p0-incident",
                    resource=args.incident_ref, work_id=args.id, cycle_id="precycle",
                    dimension="p0", decision=args.severity, payload_hash=queue_payload_hash,
                )
                approval_grant = verify_actor_grant(
                    state, getattr(args, "approval_grant", None), args.approval_actor, "p0-approve",
                    resource=args.incident_ref, work_id=args.id, cycle_id="precycle",
                    dimension="p0", decision="approved", payload_hash=queue_payload_hash,
                )
                item.update(
                    {
                        "incident_ref": getattr(args, "incident_ref", None),
                        "severity": getattr(args, "severity", None),
                        "justification": getattr(args, "justification", None),
                        "incident_actor": args.incident_actor,
                        "incident_grant": incident_grant,
                        "approval": {"approved_by": args.approval_actor, "grant": approval_grant},
                    }
                )
            item["work_fingerprint"] = work_fingerprint(item)
            historic_fingerprints = {
                work.get("work_fingerprint")
                for work in state["portfolio"].get("completed_work", [])
                if isinstance(work, dict)
            }
            if item["work_fingerprint"] in historic_fingerprints:
                if (
                    not getattr(args, "repeat_override_reason", None)
                    or not getattr(args, "repeat_override_reviewer", None)
                    or args.repeat_override_reviewer == args.owner
                    or not getattr(args, "repeat_override_grant", None)
                ):
                    raise ValueError("semantic work fingerprint was already completed; an independently reviewed override is required")
                item["repeat_override"] = {
                    "reason": args.repeat_override_reason,
                    "reviewer": args.repeat_override_reviewer,
                    "grant": verify_actor_grant(
                        state, getattr(args, "repeat_override_grant", None), args.repeat_override_reviewer, "repeat-override",
                        resource=item["work_fingerprint"], work_id=args.id, cycle_id="prequeue",
                        dimension="semantic-repeat", decision="accepted",
                        payload_hash=command_payload_hash("queue-work", canonical_queue_payload),
                    ),
                }
            if primary:
                clear_quality_scores(state)
            candidate = deepcopy(state)
            candidate["portfolio"]["active_work"] = deepcopy(active) + [item]
            report = validate_state(candidate, expected_project=project)
            work_errors = [
                error
                for error in report["errors"]
                if args.id in error
                or error.startswith("active work")
                or error.startswith("portfolio.active_work")
            ]
            if work_errors:
                raise ValueError("; ".join(work_errors))
            state["portfolio"]["active_work"].append(item)
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(project, path, state, "work_queued", work_id=args.id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "work_id": args.id, "primary": primary}))
    return 0


def score_quality(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            if args.scored_by == args.reviewed_by:
                raise ValueError("quality scoring requires an independent reviewer")
            evidence_ids = sorted(args.evidence_ids)
            if len(evidence_ids) != len(set(evidence_ids)):
                raise ValueError("quality evidence ids must be unique")
            supplied_evidence_digest = getattr(args, "evidence_digest", None)
            supplied_artifact_digest = getattr(args, "artifact_digest", None)
            if bool(supplied_evidence_digest) == bool(supplied_artifact_digest):
                raise ValueError("quality scoring requires exactly one evidence digest")
            quality_payload_hash = command_payload_hash("score-quality", quality_command_payload(args))
            scorer_grant = verify_actor_grant(
                state, getattr(args, "scored_by_grant", None), args.scored_by, "score-quality",
                resource=f"quality:{args.dimension}", work_id=args.work_id, cycle_id=args.cycle_id,
                dimension=args.dimension, decision=f"score:{args.score}", payload_hash=quality_payload_hash,
            )
            reviewer_grant = verify_actor_grant(
                state, getattr(args, "reviewed_by_grant", None), args.reviewed_by, "score-quality-review",
                resource=f"quality:{args.dimension}", work_id=args.work_id, cycle_id=args.cycle_id,
                dimension=args.dimension, decision=f"review:{args.score}", payload_hash=quality_payload_hash,
            )
            if args.dimension not in state["quality"]["dimensions"]:
                raise ValueError("unknown quality dimension")
            expected_outcome, expected_work, expected_cycle = current_quality_checkpoint(state)
            if (args.outcome_id, args.work_id, args.cycle_id) != (expected_outcome, expected_work, expected_cycle):
                raise ValueError("quality score does not target the current primary checkpoint")
            known = {
                item.get("id"): item
                for bucket in state["evidence"].values()
                for item in bucket
                if isinstance(item, dict) and evidence_is_active(item)
            }
            for evidence_id in evidence_ids:
                item = known.get(evidence_id)
                if not item or args.dimension not in item.get("quality_dimensions", []):
                    raise ValueError("quality evidence is missing or unrelated to the dimension")
                if item.get("outcome_id") != args.outcome_id or item.get("work_id") != args.work_id or item.get("cycle_id") != args.cycle_id:
                    raise ValueError("quality evidence does not match the asserted outcome, work, and cycle binding")
                if supplied_artifact_digest is not None and item.get("artifact_sha256") != supplied_artifact_digest:
                    raise ValueError("quality evidence does not match the asserted artifact digest")
                if item.get("rubric_version") != args.rubric_version:
                    raise ValueError("quality evidence does not match the asserted rubric version")
            expected_evidence_digest = completion_evidence_digest(state, evidence_ids)
            if (
                supplied_evidence_digest is not None
                and supplied_evidence_digest != expected_evidence_digest
            ):
                raise ValueError("quality evidence digest does not match the asserted evidence set")
            binding_digest = (
                {"evidence_digest": supplied_evidence_digest}
                if supplied_evidence_digest is not None
                else {"artifact_digest": supplied_artifact_digest}
            )
            state["quality"]["dimensions"][args.dimension].update(
                {
                    "score": args.score,
                    "evidence": evidence_ids,
                    "rubric_version": args.rubric_version,
                    "scored_by": args.scored_by,
                    "reviewed_by": args.reviewed_by,
                    "scorer_grant": scorer_grant,
                    "reviewer_grant": reviewer_grant,
                    "binding": {
                        "outcome_id": args.outcome_id,
                        "work_id": args.work_id,
                        "cycle_id": args.cycle_id,
                        **binding_digest,
                        "rubric_version": args.rubric_version,
                    },
                }
            )
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(
                project,
                path,
                state,
                "quality_scored",
                dimension=args.dimension,
                score=args.score,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "dimension": args.dimension, "score": args.score}))
    return 0


def certify_instance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            _, cert_work_id, cert_checkpoint = current_quality_checkpoint(state)
            certifier_grant = verify_actor_grant(
                state, getattr(args, "reviewer_grant", None), args.reviewer, "certify",
                resource="certification", work_id=cert_work_id, cycle_id=cert_checkpoint,
                dimension=str(state.get("phase")), decision="accepted",
                payload_hash=command_payload_hash("certify", certification_command_payload(state, args.reviewer)),
            )
            involved_actors = {
                work.get("owner")
                for work in state["portfolio"].get("active_work", []) + state["portfolio"].get("completed_work", [])
                if isinstance(work, dict)
            }
            involved_actors.update(
                item.get(actor_field)
                for bucket in state["evidence"].values()
                for item in bucket
                if isinstance(item, dict)
                for actor_field in ("author", "reviewer")
            )
            involved_actors.update(
                cycle.get(actor_field)
                for cycle in state["feedback"].get("cycles", [])
                if isinstance(cycle, dict)
                for actor_field in ("reviewer",)
            )
            involved_actors.update(
                item.get(actor_field)
                for item in state["quality"].get("dimensions", {}).values()
                if isinstance(item, dict)
                for actor_field in ("scored_by", "reviewed_by")
            )
            involved_actors.discard(None)
            if args.reviewer in involved_actors:
                raise ValueError("certification reviewer must be independent of every work, evidence, cycle, and quality actor")
            candidate = deepcopy(state)
            candidate["controller"]["validation"] = None
            report = validate_state(candidate, expected_project=project)
            if report["errors"]:
                raise ValueError("; ".join(report["errors"]))
            state["controller"]["validation"] = {
                "program_version": state["strategy"]["program_version"],
                "reviewer": args.reviewer,
                "reviewed_at": utc_now(),
                "decision": "accepted",
                "evidence_digest": evidence_digest(state),
                "certifier_grant": certifier_grant,
            }
            state["controller"]["validated"] = True
            persist_state_event(project, path, state, "instance_certified", reviewer=args.reviewer)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "reviewer": args.reviewer}))
    return 0


def set_active_instance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            if state["controller"].get("cancellation_requested"):
                raise ValueError("replace the program before reactivating a cancelled instance")
            report = validate_state(state, expected_project=project)
            blocking = [
                error
                for error in report["errors"]
                if error != "a paused or cancelled instance cannot enable scheduling"
            ]
            if blocking or not report["validation_valid"]:
                raise ValueError("; ".join(blocking or ["instance lacks valid independent certification"]))
            state["instance"]["status"] = "active"
            persist_state_event(project, path, state, "instance_activated")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "status": "active"}))
    return 0


def set_schedule(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    enable = args.enabled == "true"
    try:
        with locked_state(project) as (path, state):
            if enable:
                report = validate_state(state, expected_project=project)
                if not report["scheduler_ready"]:
                    raise ValueError("; ".join(report["errors"] or ["scheduler readiness gate is closed"]))
            state["controller"]["schedule_enabled"] = enable
            persist_state_event(project, path, state, "schedule_changed", enabled=enable)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "schedule_enabled": enable}))
    return 0


def acquire_lease(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        if not isinstance(args.owner, str) or not args.owner.strip():
            raise ValueError("lease owner must be a non-empty string")
        if not isinstance(args.ttl_seconds, int) or isinstance(args.ttl_seconds, bool) or args.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        with locked_state(project) as (path, state):
            existing = state["controller"].get("lease")
            recovery_lease = False
            recovery_chain: list[dict[str, Any]] = []
            if existing:
                lease_errors: list[str] = []
                expires = parse_time(existing.get("expires_at"), "controller.lease.expires_at", lease_errors)
                if lease_errors or not expires or expires > datetime.now(timezone.utc):
                    raise ValueError("controller lease is already owned")
                state["controller"].setdefault("revoked_leases", []).append(
                    {**existing, "revoked_at": utc_now(), "reason": "expired_lease_reclaimed"}
                )
                state["controller"]["lease"] = None
                state["controller"]["lease_generation"] += 1
                inherited_fences = lease_recovery_fences(existing)
                recovery_lease = any(
                    cycle.get("status") == "running"
                    and (cycle.get("lease_id"), cycle.get("lease_generation")) in inherited_fences
                    for cycle in state["feedback"].get("cycles", [])
                    if isinstance(cycle, dict)
                )
                recovery_chain = [
                    {"lease_id": lease_id, "generation": generation}
                    for lease_id, generation in sorted(inherited_fences, key=lambda item: (str(item[0]), str(item[1])))
                    if lease_id is not None and generation is not None
                ]
            report = validate_state(state, expected_project=project)
            if not state["controller"].get("schedule_enabled"):
                raise ValueError("scheduling is disabled")
            if not recovery_lease and not report["scheduler_ready"]:
                raise ValueError("; ".join(report["errors"] or ["scheduler is not ready"]))
            generation = state["controller"]["lease_generation"] + 1
            lease_id = uuid.uuid4().hex
            state["controller"]["lease_generation"] = generation
            state["controller"]["lease"] = {
                "lease_id": lease_id,
                "owner": args.owner,
                "generation": generation,
                "program_version": state["strategy"]["program_version"],
                "allowed_transitions": sorted(LEASE_TRANSITIONS),
                "recovery_chain": recovery_chain,
                "acquired_at": utc_now(),
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=args.ttl_seconds)
                ).isoformat(),
            }
            persist_state_event(project, path, state, "lease_acquired", lease_id=lease_id, owner=args.owner, recovery=recovery_lease)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "lease_id": lease_id, "generation": generation}))
    return 0


def release_lease(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            lease = require_current_lease(state, args, "release-lease")
            if any(
                cycle.get("status") == "running"
                and (cycle.get("lease_id"), cycle.get("lease_generation")) in lease_recovery_fences(lease)
                for cycle in state["feedback"].get("cycles", [])
                if isinstance(cycle, dict)
            ):
                raise ValueError("resolve the running cycle with abandon, recover, or fail before releasing its lease")
            state["controller"]["lease"] = None
            persist_state_event(project, path, state, "lease_released", lease_id=args.lease_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "released": args.lease_id}))
    return 0


def resolve_cycle(args: argparse.Namespace) -> int:
    """Resolve a fenced running cycle after an expired/recovered lease."""
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            require_current_lease(state, args, "resolve-cycle")
            cycle = next((item for item in state["feedback"]["cycles"] if item.get("id") == args.cycle_id), None)
            if not cycle or cycle.get("status") != "running":
                raise ValueError("cycle is missing or not running")
            work = next((item for item in state["portfolio"]["active_work"] if item.get("id") == cycle.get("work_id")), None)
            if not work:
                raise ValueError("running cycle has no active work to resolve")
            if args.action == "recover":
                cycle.update(
                    {
                        "lease_id": args.lease_id,
                        "lease_generation": args.generation,
                        "recovered_at": utc_now(),
                        "recovery_reason": args.reason,
                    }
                )
            else:
                cycle.update(
                    {
                        "status": "abandoned" if args.action == "abandon" else "failed",
                        "finished_at": utc_now(),
                        "resolution_reason": args.reason,
                        "resolved_by_lease": args.lease_id,
                    }
                )
                work["status"] = "ready" if args.action == "abandon" else "blocked"
                state["controller"]["schedule_enabled"] = False
                state["controller"]["validation"] = None
                state["controller"]["validated"] = False
                if args.action == "fail":
                    state["instance"]["status"] = "paused"
                if (
                    work.get("execution_mode", "single") == "luna_fabric"
                    and state.get("execution_fabric", {}).get("work_id") == work.get("id")
                ):
                    state["execution_fabric"]["status"] = "paused"
            persist_state_event(project, path, state, "cycle_resolved", cycle_id=args.cycle_id, action=args.action)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "cycle_id": args.cycle_id, "action": args.action}))
    return 0


def begin_cycle(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            require_current_lease(state, args, "begin-cycle")
            work = next(
                (item for item in state["portfolio"]["active_work"] if item.get("id") == args.work_id),
                None,
            )
            if not work or work.get("status") != "ready":
                raise ValueError("work item is missing or not ready")
            if not work.get("primary"):
                raise ValueError("only the ready primary work item may begin a scheduled cycle")
            if any(cycle.get("status") == "running" for cycle in state["feedback"]["cycles"]):
                raise ValueError("another cycle is already running")
            if work.get("execution_mode", "single") == "luna_fabric":
                fabric = state.get("execution_fabric", {})
                if (
                    fabric.get("status") != "ready"
                    or fabric.get("work_id") != work.get("id")
                    or fabric.get("cycle_id") is not None
                ):
                    raise ValueError("luna_fabric work requires a ready program-bound execution fabric")
                evidence_by_id, valid_evidence_ids = current_fabric_evidence(state, project)
                fabric_errors: list[str] = []
                fabric_warnings: list[str] = []
                fabric_state = validate_execution_fabric_state(
                    state,
                    project_root=project,
                    valid_evidence_ids=valid_evidence_ids,
                    evidence_by_id=evidence_by_id,
                    errors=fabric_errors,
                    warnings=fabric_warnings,
                )
                if fabric_errors or not fabric_state["ready_for_schedule"]:
                    raise ValueError(
                        "; ".join(fabric_errors or ["execution fabric is not ready"])
                    )
            cycle_id = uuid.uuid4().hex
            work["status"] = "running"
            state["feedback"]["cycles"].append(
                {
                    "id": cycle_id,
                    "program_version": state["strategy"]["program_version"],
                    "work_id": args.work_id,
                    "work_type": work["type"],
                    "status": "running",
                    "started_at": utc_now(),
                    "intended_outcome": args.intended_outcome,
                    "lease_id": args.lease_id,
                    "lease_generation": args.generation,
                }
            )
            if work.get("execution_mode", "single") == "luna_fabric":
                state["execution_fabric"]["cycle_id"] = cycle_id
                state["execution_fabric"]["status"] = "running"
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(project, path, state, "cycle_started", cycle_id=cycle_id, work_id=args.work_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "cycle_id": cycle_id}))
    return 0


def validate_completion_evidence(
    state: dict[str, Any], project: Path, cycle: dict[str, Any], work: dict[str, Any], evidence_ids: set[str]
) -> None:
    evidence_by_id = {
        item.get("id"): item
        for bucket in state.get("evidence", {}).values()
        for item in bucket
        if isinstance(item, dict) and evidence_is_active(item)
    }
    now = datetime.now(timezone.utc)
    for evidence_id in evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if not item:
            raise ValueError("cycle outcome requires recorded project evidence")
        artifact = project_local_path(project, item.get("snapshot_path")) if evidence_snapshot_fields(item) else project_local_path(project, item.get("artifact_path"))
        expected_digest = item.get("snapshot_sha256") if evidence_snapshot_fields(item) else item.get("artifact_sha256")
        freshness_errors: list[str] = []
        observed = parse_time(item.get("observed_at"), "completion evidence observed_at", freshness_errors)
        if (
            artifact is None
            or artifact.is_symlink()
            or not artifact.is_file()
            or expected_digest != sha256_file(artifact)
            or freshness_errors
            or not isinstance(item.get("freshness_days"), int)
            or not observed
            or now - observed > timedelta(days=item["freshness_days"])
        ):
            raise ValueError("completion evidence hash or freshness is no longer valid")
        if (
            item.get("project_id") != state["instance"]["project_id"]
            or item.get("program_version") != state["strategy"]["program_version"]
            or item.get("outcome_id") != work.get("outcome_id")
            or item.get("work_id") != work.get("id")
            or item.get("cycle_id") != cycle.get("id")
            or not item.get("decision_impact")
            or not item.get("rubric_version")
        ):
            raise ValueError("completion evidence is not relevant or fully bound to this work cycle")


def finish_cycle(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            require_current_lease(state, args, "finish-cycle")
            if not finite_nonnegative_number(args.cost_usd):
                raise ValueError("cost_usd must be a finite non-negative number")
            if not finite_nonnegative_number(args.latency_minutes):
                raise ValueError("latency_minutes must be a finite non-negative number")
            if not nonnegative_integer(args.token_usage):
                raise ValueError("token_usage must be a non-negative integer")
            cycle = next(
                (item for item in state["feedback"]["cycles"] if item.get("id") == args.cycle_id),
                None,
            )
            if not cycle or cycle.get("status") != "running":
                raise ValueError("cycle is missing or not running")
            if cycle.get("lease_id") != args.lease_id or cycle.get("lease_generation") != args.generation:
                raise ValueError("cycle is fenced by a different lease; recover it explicitly")
            reviewer_grant = verify_actor_grant(
                state, getattr(args, "reviewer_grant", None), args.reviewer, "finish-cycle",
                resource=f"cycle:{args.cycle_id}", work_id=str(cycle.get("work_id")), cycle_id=args.cycle_id,
                dimension="completion", decision=f"{args.reviewer_decision}:{args.work_disposition}",
                payload_hash=command_payload_hash("finish-cycle", finish_command_payload(state, args)),
            )
            evidence_ids = set(args.evidence_ids)
            work = next(
                (item for item in state["portfolio"]["active_work"] if item.get("id") == cycle["work_id"]),
                None,
            )
            if not work:
                raise ValueError("cycle work is no longer active")
            if (
                work.get("execution_mode", "single") == "luna_fabric"
                and args.work_disposition == "complete"
                and (
                    state.get("execution_fabric", {}).get("status") != "accepted"
                    or state.get("execution_fabric", {}).get("work_id") != work.get("id")
                    or state.get("execution_fabric", {}).get("cycle_id") != cycle.get("id")
                )
            ):
                raise ValueError(
                    "luna_fabric work cannot complete before every manager integration is master-accepted"
                )
            if (
                work.get("execution_mode", "single") == "luna_fabric"
                and args.work_disposition == "complete"
            ):
                evidence_by_id, valid_fabric_evidence = current_fabric_evidence(
                    state,
                    project,
                )
                fabric_errors: list[str] = []
                fabric_warnings: list[str] = []
                fabric_state = validate_execution_fabric_state(
                    state,
                    project_root=project,
                    valid_evidence_ids=valid_fabric_evidence,
                    evidence_by_id=evidence_by_id,
                    errors=fabric_errors,
                    warnings=fabric_warnings,
                )
                if fabric_errors or not fabric_state["accepted"]:
                    raise ValueError(
                        "; ".join(
                            fabric_errors
                            or ["execution fabric acceptance is not audit-valid"]
                        )
                    )
            if not evidence_ids:
                raise ValueError("cycle outcome requires recorded project evidence")
            validate_completion_evidence(state, project, cycle, work, evidence_ids)
            if args.work_disposition == "complete" and args.reviewer_decision != "accepted":
                raise ValueError("a rejected review must continue the work; it cannot complete it")
            cycle.update(
                {
                    "status": "completed",
                    "finished_at": utc_now(),
                    "actual_outcome": args.actual_outcome,
                    "evidence_ids": args.evidence_ids,
                    "completion_evidence_digest": completion_evidence_digest(state, args.evidence_ids),
                    "cost_usd": args.cost_usd,
                    "latency_minutes": args.latency_minutes,
                    "token_usage": args.token_usage,
                    "user_visible_movement": args.user_visible_movement == "true",
                    "work_disposition": args.work_disposition,
                    "reviewer_decision": args.reviewer_decision,
                    "reviewer": args.reviewer,
                    "reviewer_grant": reviewer_grant,
                }
            )
            if args.commit:
                cycle["commit"] = args.commit
            if args.ref:
                cycle["ref"] = args.ref
            if work:
                if args.work_disposition == "complete":
                    completion = {
                        "evidence_ids": list(args.evidence_ids),
                        "completion_evidence_digest": completion_evidence_digest(state, args.evidence_ids),
                        "cost_usd": args.cost_usd,
                        "latency_minutes": args.latency_minutes,
                        "token_usage": args.token_usage,
                        "user_visible_movement": args.user_visible_movement == "true",
                        "reviewer_decision": args.reviewer_decision,
                        "reviewer": args.reviewer,
                        "reviewer_grant": reviewer_grant,
                    }
                    if args.commit:
                        completion["commit"] = args.commit
                    if args.ref:
                        completion["ref"] = args.ref
                    archived = {
                        **work,
                        "status": "completed",
                        "completed_at": cycle["finished_at"],
                        "completion_cycle_id": cycle["id"],
                        "completion": completion,
                    }
                    digest = completion_digest(archived, cycle)
                    cycle["completion_digest"] = digest
                    archived["completion_digest"] = digest
                    state["portfolio"].setdefault("completed_work", []).append(archived)
                    state["portfolio"]["active_work"] = [
                        item for item in state["portfolio"]["active_work"] if item.get("id") != work.get("id")
                    ]
                else:
                    work["status"] = "ready"
                    if work.get("execution_mode", "single") == "luna_fabric":
                        state["execution_fabric"]["status"] = "paused"
            state["controller"]["last_cycle_at"] = cycle["finished_at"]
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            state["controller"]["schedule_enabled"] = False
            candidate_report = validate_state(state, expected_project=project)
            drift_errors = [
                error
                for error in candidate_report["errors"]
                if "actual " in error or "two consecutive cycles" in error
            ]
            if drift_errors:
                state["controller"]["schedule_enabled"] = False
                state["instance"]["status"] = "paused"
                state["feedback"]["failure_patterns"].append(
                    {
                        "id": f"drift-{uuid.uuid4().hex[:12]}",
                        "program_version": state["strategy"]["program_version"],
                        "observed_at": utc_now(),
                        "pattern": "; ".join(drift_errors),
                        "affected_cycles": [item["id"] for item in state["feedback"]["cycles"][-2:]],
                    }
                )
            persist_state_event(
                project,
                path,
                state,
                "cycle_finished",
                cycle_id=args.cycle_id,
                work_disposition=args.work_disposition,
                reviewer_decision=args.reviewer_decision,
                drift_paused=bool(drift_errors),
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "cycle_id": args.cycle_id,
                "work_disposition": args.work_disposition,
                "drift_paused": bool(drift_errors),
            }
        )
    )
    return 0


def configure_execution_fabric(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        manifest_path = project_local_path(project, args.manifest)
        if manifest_path is None or not manifest_path.is_file():
            raise ValueError("manifest must be a project-local JSON file")
        manifest = load_json(manifest_path)
        manifest_report = validate_fabric_manifest(manifest)
        if not manifest_report.get("valid"):
            raise ValueError("; ".join(manifest_report.get("errors", ["manifest is invalid"])))
        with locked_state(project) as (path, state):
            if state.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("run upgrade before configuring the execution fabric")
            if state.get("core_version") != CORE_VERSION:
                raise ValueError("Company OS core version is stale")
            if state.get("strategy", {}).get("program_fingerprint") != strategy_fingerprint(
                state.get("strategy", {})
            ):
                raise ValueError("Company OS strategy fingerprint is invalid")
            if state.get("controller", {}).get("cancellation_requested"):
                raise ValueError("replace the cancelled program before configuring execution")
            if state.get("controller", {}).get("lease") is not None:
                raise ValueError("cannot configure the execution fabric while a lease is active")
            work = next(
                (
                    item
                    for item in state.get("portfolio", {}).get("active_work", [])
                    if item.get("id") == args.work_id
                ),
                None,
            )
            if not work or not work.get("primary") or work.get("status") != "ready":
                raise ValueError("execution fabric requires the ready primary work item")
            if work.get("execution_mode", "single") != "luna_fabric":
                raise ValueError("work item must use execution_mode luna_fabric")
            if any(
                cycle.get("status") == "running"
                for cycle in state.get("feedback", {}).get("cycles", [])
                if isinstance(cycle, dict)
            ):
                raise ValueError("cannot reconfigure the execution fabric during a running cycle")
            if manifest.get("program_id") != state["instance"]["project_id"]:
                raise ValueError("manifest program_id must match the Company OS project_id")
            if manifest.get("program_version") != state["strategy"]["program_version"]:
                raise ValueError("manifest program_version must match the Company OS program")
            if manifest.get("outcome") != work.get("user_visible_outcome"):
                raise ValueError("manifest outcome must match the governed user-visible outcome")
            if manifest.get("program_contract", {}).get("north_star") != state["strategy"]["north_star"]:
                raise ValueError("manifest north_star must match Company OS strategy")
            configured_at = utc_now()
            state["execution_fabric"] = {
                "enabled": True,
                "status": "ready",
                "program_version": state["strategy"]["program_version"],
                "work_id": args.work_id,
                "cycle_id": None,
                "manifest": manifest,
                "manifest_digest": fabric_manifest_digest(manifest),
                "manifest_path": str(manifest_path.relative_to(project)),
                "manifest_sha256": sha256_file(manifest_path),
                "configured_at": configured_at,
                "managers": {
                    manager["id"]: {
                        "id": manager["id"],
                        "model": manager["model"],
                        "outcome": manager["outcome"],
                        "status": "pending",
                        "next_phase": "charter",
                        "rework_rounds": 0,
                        "reports": [],
                        "decisions": [],
                    }
                    for manager in manifest["managers"]
                },
                "decisions": [],
                "cancelled_at": None,
                "cancellation_reason": None,
            }
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            state["controller"]["schedule_enabled"] = False
            persist_state_event(
                project,
                path,
                state,
                "execution_fabric_configured",
                work_id=args.work_id,
                manifest_digest=state["execution_fabric"]["manifest_digest"],
            )
            manifest_digest = state["execution_fabric"]["manifest_digest"]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "work_id": args.work_id,
                "manifest_digest": manifest_digest,
                "status": "ready",
            }
        )
    )
    return 0


def record_fabric_phase(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        report_path = project_local_path(project, args.report)
        if report_path is None or not report_path.is_file():
            raise ValueError("report must be a project-local JSON file")
        report = load_json(report_path)
        with locked_state(project) as (path, state):
            require_current_lease(state, args, "record-fabric-phase")
            fabric = state.get("execution_fabric", {})
            if fabric.get("status") != "running" or not fabric.get("cycle_id"):
                raise ValueError("execution fabric is not bound to a running cycle")
            require_running_cycle_lease_fence(state, args, fabric.get("cycle_id"))
            manager = fabric.get("managers", {}).get(args.manager_id)
            if not manager:
                raise ValueError("manager is not admitted by the execution fabric")
            phase = manager.get("next_phase")
            if phase is None or manager.get("status") not in {"pending", "ready"}:
                raise ValueError("manager is not ready to report a phase")
            evidence_by_id, valid_evidence_ids = current_fabric_evidence(state, project)
            report_errors = validate_fabric_report_payload(
                state,
                args.manager_id,
                phase,
                report,
                valid_evidence_ids=valid_evidence_ids,
                evidence_by_id=evidence_by_id,
            )
            if report_errors:
                raise ValueError("; ".join(report_errors))
            digest = hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()
            manager["reports"].append(
                {
                    "phase": phase,
                    "attempt": 1 + sum(
                        1 for item in manager["reports"] if item.get("phase") == phase
                    ),
                    "report": report,
                    "report_digest": digest,
                    "report_path": str(report_path.relative_to(project)),
                    "report_sha256": sha256_file(report_path),
                    "recorded_at": utc_now(),
                }
            )
            manager["status"] = "awaiting_decision"
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(
                project,
                path,
                state,
                "execution_fabric_phase_reported",
                manager_id=args.manager_id,
                phase=phase,
                report_digest=digest,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "manager_id": args.manager_id, "phase": phase, "report_digest": digest}))
    return 0


def decide_fabric_phase(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            require_current_lease(state, args, "decide-fabric-phase")
            fabric = state.get("execution_fabric", {})
            if fabric.get("status") != "running":
                raise ValueError("execution fabric is not running")
            require_running_cycle_lease_fence(state, args, fabric.get("cycle_id"))
            manager = fabric.get("managers", {}).get(args.manager_id)
            if not manager or manager.get("status") != "awaiting_decision":
                raise ValueError("manager has no phase report awaiting a decision")
            phase = manager.get("next_phase")
            latest = manager.get("reports", [])[-1]
            report = latest["report"]
            report_artifact = project_local_path(project, latest.get("report_path"))
            if (
                report_artifact is None
                or not report_artifact.is_file()
                or latest.get("report_sha256") != sha256_file(report_artifact)
                or latest.get("report_digest")
                != hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()
            ):
                raise ValueError("manager phase report integrity changed before master decision")
            evidence_by_id, valid_evidence_ids = current_fabric_evidence(state, project)
            report_errors = validate_fabric_report_payload(
                state,
                args.manager_id,
                phase,
                report,
                valid_evidence_ids=valid_evidence_ids,
                evidence_by_id=evidence_by_id,
            )
            if report_errors:
                raise ValueError("; ".join(report_errors))
            if args.decision == "continue" and report.get("outcome_state") == "blocked":
                raise ValueError("a blocked manager report cannot continue")
            if args.decided_by == args.manager_id:
                raise ValueError("a manager cannot approve its own phase")
            if args.decision == "rework" and manager.get("rework_rounds", 0) >= 2:
                raise ValueError("manager rework budget is exhausted")
            payload = fabric_phase_decision_payload(
                state,
                args.manager_id,
                phase,
                args.decision,
            )
            master_grant = verify_actor_grant(
                state,
                args.master_grant,
                args.decided_by,
                "fabric-phase-decision",
                resource=f"fabric:{args.manager_id}:{phase}",
                work_id=str(fabric.get("work_id")),
                cycle_id=str(fabric.get("cycle_id")),
                dimension="execution-fabric",
                decision=args.decision,
                payload_hash=command_payload_hash("fabric-phase-decision", payload),
            )
            decision = {
                "phase": phase,
                "decision": args.decision,
                "decided_by": args.decided_by,
                "decided_at": utc_now(),
                "report_digest": latest["report_digest"],
                "rework_rounds_before": manager.get("rework_rounds", 0),
                "payload": payload,
                "master_grant": master_grant,
            }
            manager["decisions"].append(decision)
            fabric["decisions"].append(
                {
                    "manager_id": args.manager_id,
                    "phase": phase,
                    "decision": args.decision,
                    "decided_at": decision["decided_at"],
                    "report_digest": latest["report_digest"],
                }
            )
            if args.decision == "rework":
                manager["rework_rounds"] += 1
                manager["status"] = "ready"
            elif args.decision == "pause":
                manager["status"] = "paused"
                fabric["status"] = "paused"
            elif args.decision == "terminate":
                manager["status"] = "terminated"
                fabric["status"] = "terminated"
            elif phase == "integration":
                manager["status"] = "accepted"
                manager["next_phase"] = None
                if all(
                    item.get("status") == "accepted"
                    for item in fabric["managers"].values()
                ):
                    fabric["status"] = "accepted"
            else:
                manager["next_phase"] = FABRIC_PHASES[FABRIC_PHASES.index(phase) + 1]
                manager["status"] = "ready"
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(
                project,
                path,
                state,
                "execution_fabric_phase_decided",
                manager_id=args.manager_id,
                phase=phase,
                decision=args.decision,
            )
            fabric_status = fabric["status"]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "manager_id": args.manager_id,
                "phase": phase,
                "decision": args.decision,
                "fabric_status": fabric_status,
            }
        )
    )
    return 0


def propose_adaptation(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            protected = set(args.changes) & PROTECTED_ADAPTATION_FIELDS
            if protected:
                raise ValueError(f"adaptation changes protected fields: {sorted(protected)}")
            if not nonnegative_integer(args.time_cap_minutes):
                raise ValueError("time_cap_minutes must be a non-negative integer")
            if not finite_nonnegative_number(args.cost_cap_usd):
                raise ValueError("cost_cap_usd must be a finite non-negative number")
            adaptation_id = args.id or f"adapt-{uuid.uuid4().hex[:12]}"
            proposal = {
                "id": adaptation_id,
                "program_version": state["strategy"]["program_version"],
                "failure_pattern": args.failure_pattern,
                "hypothesis": args.hypothesis,
                "experiment": args.experiment,
                "success_metric": args.success_metric,
                "rollback": args.rollback,
                "proposer": args.proposer,
                "time_cap_minutes": args.time_cap_minutes,
                "cost_cap_usd": args.cost_cap_usd,
                "changes": args.changes,
                "meta_depth": 1,
                "status": "proposed",
                "proposed_at": utc_now(),
            }
            proposal["proposal_digest"] = adaptation_proposal_digest(proposal)
            state["feedback"]["pending_adaptations"].append(proposal)
            persist_state_event(project, path, state, "adaptation_proposed", adaptation_id=adaptation_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "adaptation_id": adaptation_id}))
    return 0


def review_adaptation(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            proposal = next(
                (
                    item
                    for item in state["feedback"]["pending_adaptations"]
                    if item.get("id") == args.id
                ),
                None,
            )
            if not proposal:
                raise ValueError("pending adaptation not found")
            if proposal.get("proposer") == args.reviewer:
                raise ValueError("adaptation cannot be self-reviewed")
            proposal_digest = proposal.get("proposal_digest")
            if proposal_digest != adaptation_proposal_digest(proposal):
                raise ValueError("adaptation proposal digest is invalid")
            reviewer_grant = verify_actor_grant(
                state, args.reviewer_grant, args.reviewer, "review-adaptation",
                resource=f"adaptation:{args.id}", work_id="", cycle_id="", dimension="meta-loop",
                decision=args.decision,
                payload_hash=command_payload_hash("review-adaptation", {
                    "adaptation_id": args.id, "proposal_digest": proposal_digest,
                    "reviewer": args.reviewer, "decision": args.decision,
                }),
            )
            state["feedback"]["pending_adaptations"].remove(proposal)
            reviewed = {
                **proposal,
                "reviewer": args.reviewer,
                "review_decision": args.decision,
                "reviewed_at": utc_now(),
                "reviewer_grant": reviewer_grant,
                "status": "applied" if args.decision == "accepted" else "rejected",
            }
            state["feedback"]["applied_adaptations"].append(reviewed)
            state["controller"]["validation"] = None
            state["controller"]["validated"] = False
            persist_state_event(
                project,
                path,
                state,
                "adaptation_reviewed",
                adaptation_id=args.id,
                decision=args.decision,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({"ok": True, "adaptation_id": args.id, "decision": args.decision}))
    return 0


def admit_runtime_attempt(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    try:
        with locked_state(project) as (path, state):
            lease = require_current_lease(state, args, "admit-runtime-attempt")
            runtime = state.get("runtime_adapter", {})
            required_text = {
                "attempt_id": args.attempt_id,
                "manifest_identity_id": args.manifest_identity_id,
                "work_id": args.work_id,
                "cycle_id": args.cycle_id,
                "parent_runtime_id": args.parent_runtime_id,
                "requested_model": args.requested_model,
                "provider": args.provider,
                "surface": args.surface,
                "account": args.account,
                "fabric_manifest_digest": args.fabric_manifest_digest,
                "contract_digest": args.contract_digest,
                "idempotency_key": args.idempotency_key,
                "admitted_by": args.admitted_by,
            }
            if any(
                not isinstance(value, str) or not value or value != value.strip()
                for value in required_text.values()
            ):
                raise ValueError("runtime admission identifiers and bindings must be non-empty trimmed strings")
            if not runtime.get("enabled") or runtime.get("status") != "enabled":
                raise ValueError("runtime adapter is feature-off")
            allowlist = runtime.get("provider_allowlist")
            attempts = runtime.get("attempts")
            if (
                not isinstance(allowlist, list)
                or not isinstance(attempts, list)
                or any(
                    not isinstance(item, dict)
                    or set(item) != {"provider", "surface", "account"}
                    or any(
                        not isinstance(item.get(key), str)
                        or not item[key]
                        or item[key] != item[key].strip()
                        for key in ("provider", "surface", "account")
                    )
                    for item in allowlist
                )
                or len({
                    (item["provider"], item["surface"], item["account"])
                    for item in allowlist
                }) != len(allowlist)
                or any(not isinstance(item, dict) for item in attempts)
            ):
                raise ValueError("runtime adapter configuration is invalid")
            retained_runtime_errors = [
                error
                for error in validate_state(state, expected_project=project)["errors"]
                if error.startswith(RUNTIME_AUDIT_ERROR_PREFIXES)
            ]
            if retained_runtime_errors:
                raise ValueError(
                    "runtime adapter retained state failed audit: "
                    + "; ".join(retained_runtime_errors)
                )
            if runtime.get("program_version") != state.get("strategy", {}).get("program_version"):
                raise ValueError("runtime adapter belongs to a stale program")
            fabric = state.get("execution_fabric", {})
            if fabric.get("status") != "running" or fabric.get("work_id") != args.work_id or fabric.get("cycle_id") != args.cycle_id:
                raise ValueError("runtime admission requires the exact running luna_fabric cycle")
            manifest = fabric.get("manifest", {})
            cycle = require_running_cycle_lease_fence(state, args, args.cycle_id)
            if cycle.get("work_id") != args.work_id or cycle.get("program_version") != state["strategy"]["program_version"]:
                raise ValueError("runtime admission must bind the current running work cycle")
            manifest_digest = fabric.get("manifest_digest")
            if not isinstance(manifest, dict) or not isinstance(manifest_digest, str) or fabric_manifest_digest(manifest) != manifest_digest:
                raise ValueError("runtime admission requires the current admitted fabric manifest")
            manifest_report = validate_fabric_manifest(manifest)
            if not manifest_report.get("valid"):
                raise ValueError("runtime admission requires a valid current fabric manifest")
            if args.fabric_manifest_digest != manifest_digest:
                raise ValueError("fabric_manifest_digest does not bind the current fabric")
            if args.contract_digest != PHASE2_CONTRACT_DIGEST or runtime.get("phase2_contract_digest") != PHASE2_CONTRACT_DIGEST:
                raise ValueError("contract_digest does not match the frozen Phase 2 contract")
            if {"provider": args.provider, "surface": args.surface, "account": args.account} not in allowlist:
                raise ValueError("provider, surface, and account are not allowlisted")
            try:
                budget = json.loads(args.budget)
                scope = json.loads(args.scope)
            except (TypeError, json.JSONDecodeError):
                raise ValueError("scope and budget must be canonical JSON")
            if not isinstance(budget, dict):
                raise ValueError("budget must be a canonical object")
            scope = canonical_runtime_scopes(scope)
            candidate: dict[str, Any] | None = None
            owner_manifest_id: str | None = None
            for manager in manifest.get("managers", []):
                if args.role == "manager" and args.manifest_identity_id == manager.get("id") and args.parent_runtime_id == "master":
                    candidate = manager
                for worker in manager.get("workers", []):
                    if args.role == "worker" and args.manifest_identity_id == worker.get("id"):
                        if candidate is not None:
                            raise ValueError("runtime manifest identity is ambiguous")
                        candidate = worker
                        owner_manifest_id = manager.get("id")
            if candidate is None or args.role not in {"manager", "worker"}:
                raise ValueError("runtime identity or parent is not admitted by the manifest")
            if args.role == "manager":
                if candidate.get("model") != "gpt-5.6-sol":
                    raise ValueError("manager admission requires the exact Sol manifest model")
            else:
                if candidate.get("model") != "gpt-5.6-luna":
                    raise ValueError("worker admission requires the exact Luna manifest model")
                parent = next(
                    (item for item in attempts
                     if item.get("attempt_id") == args.parent_runtime_id
                     and item.get("role") == "manager"
                     and item.get("manifest_identity_id") == owner_manifest_id
                     and item.get("status") == "admitted"),
                    None,
                )
                if parent is None:
                    raise ValueError("worker admission requires its already admitted manager runtime parent")
            try:
                candidate_scope = canonical_runtime_scopes(candidate.get("write_scope"))
            except ValueError as exc:
                raise ValueError(f"manifest scope is not canonical: {exc}") from None
            if args.requested_model != candidate.get("model") or scope != candidate_scope:
                raise ValueError("requested model or scope does not match the admitted manifest identity")
            if canonical_json(budget) != canonical_json(candidate.get("budget")):
                raise ValueError("runtime budget does not match the admitted manifest identity")
            payload = runtime_admission_payload(args, scope=scope, budget=budget, lease=lease)
            for item in attempts:
                same_payload = all(item.get(key) == value for key, value in payload.items())
                if item.get("idempotency_key") == args.idempotency_key:
                    if same_payload:
                        print(json.dumps({"ok": True, "attempt_id": args.attempt_id, "status": "admitted", "idempotent": True}))
                        return 0
                    raise ValueError("runtime idempotency key conflicts with a different admission payload")
                if item.get("attempt_id") == args.attempt_id:
                    raise ValueError("runtime attempt ID already consumed")
                if (
                    item.get("program_version") == state["strategy"]["program_version"]
                    and item.get("work_id") == args.work_id
                    and item.get("cycle_id") == args.cycle_id
                    and item.get("manifest_identity_id") == args.manifest_identity_id
                ):
                    raise ValueError("manifest identity already has an admitted attempt in this work cycle")
            grant = verify_actor_grant(state, args.actor_grant, args.admitted_by, "admit-runtime-attempt", resource=f"runtime:{args.attempt_id}", work_id=args.work_id, cycle_id=args.cycle_id, dimension="runtime-admission", decision="admitted", payload_hash=command_payload_hash("admit-runtime-attempt", payload))
            attempts.append({**payload, "program_version": state["strategy"]["program_version"], "lease_id": args.lease_id, "lease_generation": args.generation, "lease_owner": args.owner, "status": "admitted", "provider_task_id": None, "admitted_by": args.admitted_by, "actor_grant": grant, "admitted_at": utc_now()})
            runtime["observation_inboxes"][args.attempt_id] = runtime_observation_module().empty_inbox()
            persist_state_event(project, path, state, "runtime_attempt_admitted", attempt_id=args.attempt_id, idempotency_key=args.idempotency_key)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2)); return 2
    print(json.dumps({"ok": True, "attempt_id": args.attempt_id, "status": "admitted"})); return 0


def ingest_runtime_observation(args: argparse.Namespace) -> int:
    """Verify and retain one provider observation without advancing lifecycle."""
    project = Path(args.project).resolve()
    try:
        with locked_state(project, require_issuer=False) as (path, state):
            if state.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("run upgrade before ingesting runtime observations")
            runtime = state.get("runtime_adapter")
            if not isinstance(runtime, dict):
                raise ValueError("runtime adapter configuration is invalid")
            if runtime.get("enabled") is not True or runtime.get("status") != "enabled":
                raise ValueError("runtime adapter is feature-off")
            attempts = runtime.get("attempts")
            inboxes = runtime.get("observation_inboxes")
            if not isinstance(attempts, list) or not isinstance(inboxes, dict):
                raise ValueError("runtime observation state is invalid")
            matches = [
                item for item in attempts
                if isinstance(item, dict) and item.get("attempt_id") == args.attempt_id
            ]
            if len(matches) != 1:
                raise ValueError("runtime observation requires exactly one admitted attempt")
            attempt = matches[0]
            inbox = inboxes.get(args.attempt_id)
            if not isinstance(inbox, dict):
                raise ValueError("runtime observation inbox is missing")
            if inbox.get("enabled") is not True or inbox.get("status") != "enabled":
                raise ValueError("runtime observation inbox is feature-off")

            keyring_value = os.environ.get(OBSERVATION_GATEWAY_KEYRING_ENV)
            if not keyring_value:
                raise ValueError(f"{OBSERVATION_GATEWAY_KEYRING_ENV} is required")
            keyring_path = Path(keyring_value).resolve()
            if not keyring_path.is_file():
                raise ValueError("configured observation-gateway keyring does not exist")
            actor_key_value = os.environ.get(ACTOR_PUBLIC_KEY_ENV)
            if actor_key_value and Path(actor_key_value).resolve() == keyring_path:
                raise ValueError("observation gateway and actor decision issuer must use distinct trust roots")

            envelope_path = project_local_path(project, args.envelope)
            if envelope_path is None or not envelope_path.is_file():
                raise ValueError("observation envelope must be an existing project-local file")
            observation_module = runtime_observation_module()
            envelope = observation_module.load_json_strict(envelope_path)

            retained_runtime_errors = [
                error for error in validate_state(state, expected_project=project)["errors"]
                if error.startswith(RUNTIME_AUDIT_ERROR_PREFIXES)
            ]
            if retained_runtime_errors:
                raise ValueError(
                    "runtime adapter retained state failed audit: "
                    + "; ".join(retained_runtime_errors)
                )
            candidate_inbox, result = observation_module.verify_and_ingest(
                inbox,
                envelope,
                expected_attempt=observation_expected_attempt(state, attempt),
                keyring_path=keyring_path,
                artifact_root=project,
            )
            if result.get("idempotent") is True:
                print(json.dumps({
                    "ok": True,
                    "attempt_id": args.attempt_id,
                    "status": "verified",
                    "event_key": result.get("event_key"),
                    "idempotent": True,
                }))
                return 0
            candidate = deepcopy(state)
            candidate["runtime_adapter"]["observation_inboxes"][args.attempt_id] = candidate_inbox
            candidate_errors = [
                error for error in validate_state(candidate, expected_project=project)["errors"]
                if error.startswith(RUNTIME_AUDIT_ERROR_PREFIXES)
            ]
            if candidate_errors:
                raise ValueError(
                    "runtime observation candidate failed audit: " + "; ".join(candidate_errors)
                )
            state["runtime_adapter"]["observation_inboxes"][args.attempt_id] = candidate_inbox
            accepted_record = candidate_inbox["trusted_observations"][-1]
            persist_state_event(
                project,
                path,
                state,
                "runtime_observation_verified",
                attempt_id=args.attempt_id,
                event_key=result.get("event_key"),
                observation_digest=accepted_record.get("observation_digest"),
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps({
        "ok": True,
        "attempt_id": args.attempt_id,
        "status": "verified",
        "event_key": result.get("event_key"),
        "idempotent": False,
    }))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create an isolated project instance")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--project-type", default="general", choices=sorted(DEPARTMENT_PRESETS))
    init_parser.add_argument("--north-star", required=True)
    init_parser.set_defaults(handler=init_instance)
    audit_parser = subparsers.add_parser("audit", help="validate gates and readiness")
    audit_parser.add_argument("--project", required=True)
    audit_parser.set_defaults(handler=audit_instance)
    brief_parser = subparsers.add_parser("brief", help="render the human operator command center")
    brief_parser.add_argument("--project", required=True)
    brief_parser.add_argument("--format", choices=("markdown", "json", "html"), default="markdown")
    brief_parser.add_argument("--since-revision", type=int, help="compare with one earlier authoritative revision")
    brief_parser.add_argument("--strict", action="store_true", help="exit nonzero when a governed gate is blocked")
    brief_parser.set_defaults(handler=brief_instance)
    upgrade_parser = subparsers.add_parser(
        "upgrade", help="upgrade a schema v1-v8 instance fail-closed"
    )
    upgrade_parser.add_argument("--project", required=True)
    upgrade_parser.set_defaults(handler=upgrade_instance)
    migrate_store_parser = subparsers.add_parser(
        "migrate-control-store",
        help="make the project-local SQLite store authoritative",
    )
    migrate_store_parser.add_argument("--project", required=True)
    migrate_store_parser.set_defaults(handler=migrate_control_store)
    replace_parser = subparsers.add_parser("replace-program", help="version a changed mandate")
    replace_parser.add_argument("--project", required=True)
    replace_parser.add_argument("--north-star", required=True)
    replace_parser.add_argument("--current-outcome", required=True)
    replace_parser.add_argument("--success-metric", required=True)
    replace_parser.add_argument("--reason", required=True)
    replace_parser.set_defaults(handler=replace_program)
    repair_transition_parser = subparsers.add_parser(
        "repair-program-transition",
        help="archive one exact stale prior-program transition under independent authority",
    )
    repair_transition_parser.add_argument("--project", required=True)
    repair_transition_parser.add_argument("--reviewer", required=True)
    repair_transition_parser.add_argument("--repair-grant", required=True)
    repair_transition_parser.set_defaults(handler=repair_program_transition)
    cancel_parser = subparsers.add_parser("cancel", help="authoritatively cancel work and leases")
    cancel_parser.add_argument("--project", required=True)
    cancel_parser.add_argument("--reason", required=True)
    cancel_parser.set_defaults(handler=cancel_instance)
    evidence_parser = subparsers.add_parser("record-evidence", help="record hashed project evidence")
    evidence_parser.add_argument("--project", required=True)
    evidence_parser.add_argument("--outcome", choices=EVIDENCE_BUCKETS, required=True)
    evidence_parser.add_argument("--artifact", required=True)
    evidence_parser.add_argument("--source", required=True)
    evidence_parser.add_argument("--decision-impact", required=True)
    evidence_parser.add_argument("--author", required=True)
    evidence_parser.add_argument("--reviewer", required=True)
    evidence_parser.add_argument("--freshness-days", type=int, default=30)
    evidence_parser.add_argument("--quality-dimensions", nargs="*", default=[])
    evidence_parser.add_argument("--outcome-id")
    evidence_parser.add_argument("--work-id")
    evidence_parser.add_argument("--cycle-id")
    evidence_parser.add_argument("--rubric-version")
    evidence_parser.add_argument("--id")
    evidence_parser.set_defaults(handler=record_evidence)
    supersede_parser = subparsers.add_parser("supersede-evidence", help="archive drifted evidence and record its immutable successor")
    supersede_parser.add_argument("--project", required=True)
    supersede_parser.add_argument("--evidence-id", required=True)
    supersede_parser.add_argument("--artifact", required=True)
    supersede_parser.add_argument("--source", required=True)
    supersede_parser.add_argument("--decision-impact", required=True)
    supersede_parser.add_argument("--author", required=True)
    supersede_parser.add_argument("--reviewer", required=True)
    supersede_parser.add_argument("--reviewer-grant", required=True)
    supersede_parser.add_argument("--reason", required=True)
    supersede_parser.add_argument("--freshness-days", type=int)
    supersede_parser.add_argument("--quality-dimensions", nargs="*", default=None)
    supersede_parser.add_argument("--outcome-id")
    supersede_parser.add_argument("--work-id")
    supersede_parser.add_argument("--cycle-id")
    supersede_parser.add_argument("--rubric-version")
    supersede_parser.add_argument("--id", required=True)
    supersede_parser.set_defaults(handler=supersede_evidence)
    correct_parser = subparsers.add_parser(
        "correct-evidence",
        help="dually authorize one typed semantic correction to immutable evidence",
    )
    correct_parser.add_argument("--project", required=True)
    correct_parser.add_argument("--evidence-id", required=True)
    correct_parser.add_argument("--artifact", required=True)
    correct_parser.add_argument("--source", required=True)
    correct_parser.add_argument("--decision-impact", required=True)
    correct_parser.add_argument("--reason", required=True)
    correct_parser.add_argument("--declarant", required=True)
    correct_parser.add_argument("--adjudicator", required=True)
    correct_parser.add_argument("--declarant-grant", required=True)
    correct_parser.add_argument("--adjudicator-grant", required=True)
    correct_parser.add_argument("--old-value", required=True)
    correct_parser.add_argument("--new-value", required=True)
    correct_parser.add_argument("--transition-at", required=True)
    correct_parser.add_argument("--freshness-days", type=int, default=30)
    correct_parser.add_argument("--id", required=True)
    correct_parser.set_defaults(handler=correct_evidence)
    phase_parser = subparsers.add_parser("advance-phase", help="advance exactly one evidenced phase")
    phase_parser.add_argument("--project", required=True)
    phase_parser.add_argument("--phase", choices=PHASES, required=True)
    phase_parser.set_defaults(handler=advance_phase)
    outcome_parser = subparsers.add_parser("commit-outcome", help="commit a product outcome")
    outcome_parser.add_argument("--project", required=True)
    outcome_parser.add_argument("--id", required=True)
    outcome_parser.add_argument("--type", choices=("capability", "innovation"), required=True)
    outcome_parser.add_argument("--title", required=True)
    outcome_parser.add_argument("--user-visible-outcome", required=True)
    outcome_parser.set_defaults(handler=commit_outcome)
    work_parser = subparsers.add_parser("queue-work", help="queue governed active work")
    work_parser.add_argument("--project", required=True)
    work_parser.add_argument("--id", required=True)
    work_parser.add_argument("--type", choices=sorted(ALLOWED_WORK_TYPES), required=True)
    work_parser.add_argument("--title", required=True)
    work_parser.add_argument("--user-visible-outcome", required=True)
    work_parser.add_argument("--claimed-progress", choices=sorted(PRODUCT_OUTCOMES), required=True)
    work_parser.add_argument("--owner", required=True)
    work_parser.add_argument(
        "--execution-mode",
        choices=("single", "luna_fabric"),
        default="single",
    )
    work_parser.add_argument("--outcome-id")
    work_parser.add_argument("--primary", choices=("true", "false"), default="false")
    work_parser.add_argument("--unlocks", nargs="*", default=[])
    work_parser.add_argument("--incident-ref")
    work_parser.add_argument("--severity", choices=("P0",))
    work_parser.add_argument("--justification")
    work_parser.add_argument("--incident-actor")
    work_parser.add_argument("--incident-grant")
    work_parser.add_argument("--approval-actor")
    work_parser.add_argument("--approval-grant")
    work_parser.add_argument("--repeat-override-reason")
    work_parser.add_argument("--repeat-override-reviewer")
    work_parser.add_argument("--repeat-override-grant")
    work_parser.set_defaults(handler=queue_work)
    quality_parser = subparsers.add_parser("score-quality", help="record reviewed quality evidence")
    quality_parser.add_argument("--project", required=True)
    quality_parser.add_argument("--dimension", choices=sorted(BASE_DIMENSIONS), required=True)
    quality_parser.add_argument("--score", type=float, required=True)
    quality_parser.add_argument("--evidence-ids", nargs="+", required=True)
    quality_parser.add_argument("--rubric-version", required=True)
    quality_parser.add_argument("--scored-by", required=True)
    quality_parser.add_argument("--reviewed-by", required=True)
    quality_parser.add_argument("--scored-by-grant", required=True)
    quality_parser.add_argument("--reviewed-by-grant", required=True)
    quality_parser.add_argument("--outcome-id", required=True)
    quality_parser.add_argument("--work-id", required=True)
    quality_parser.add_argument("--cycle-id", required=True)
    quality_digest_group = quality_parser.add_mutually_exclusive_group(required=True)
    quality_digest_group.add_argument(
        "--evidence-digest",
        help="SHA-256 of the canonical complete evidence set (preferred)",
    )
    quality_digest_group.add_argument(
        "--artifact-digest",
        help="legacy single-artifact SHA-256 retained for signed-history compatibility",
    )
    quality_parser.set_defaults(handler=score_quality)
    certify_parser = subparsers.add_parser("certify", help="independently certify current evidence")
    certify_parser.add_argument("--project", required=True)
    certify_parser.add_argument("--reviewer", required=True)
    certify_parser.add_argument("--reviewer-grant", required=True)
    certify_parser.set_defaults(handler=certify_instance)
    activate_parser = subparsers.add_parser("activate", help="activate an independently certified instance")
    activate_parser.add_argument("--project", required=True)
    activate_parser.set_defaults(handler=set_active_instance)
    schedule_parser = subparsers.add_parser("set-schedule", help="enable or disable scheduling")
    schedule_parser.add_argument("--project", required=True)
    schedule_parser.add_argument("--enabled", choices=("true", "false"), required=True)
    schedule_parser.set_defaults(handler=set_schedule)
    acquire_parser = subparsers.add_parser("acquire-lease", help="acquire the fenced controller lease")
    acquire_parser.add_argument("--project", required=True)
    acquire_parser.add_argument("--owner", required=True)
    acquire_parser.add_argument("--ttl-seconds", type=int, default=1800)
    acquire_parser.set_defaults(handler=acquire_lease)
    release_parser = subparsers.add_parser("release-lease", help="release an owned controller lease")
    release_parser.add_argument("--project", required=True)
    release_parser.add_argument("--lease-id", required=True)
    release_parser.add_argument("--generation", type=int, required=True)
    release_parser.add_argument("--owner", required=True)
    release_parser.set_defaults(handler=release_lease)
    resolve_parser = subparsers.add_parser("resolve-cycle", help="abandon, recover, or fail a fenced running cycle")
    resolve_parser.add_argument("--project", required=True)
    resolve_parser.add_argument("--lease-id", required=True)
    resolve_parser.add_argument("--generation", type=int, required=True)
    resolve_parser.add_argument("--owner", required=True)
    resolve_parser.add_argument("--cycle-id", required=True)
    resolve_parser.add_argument("--action", choices=("abandon", "recover", "fail"), required=True)
    resolve_parser.add_argument("--reason", required=True)
    resolve_parser.set_defaults(handler=resolve_cycle)
    begin_parser = subparsers.add_parser("begin-cycle", help="begin one leased work cycle")
    begin_parser.add_argument("--project", required=True)
    begin_parser.add_argument("--lease-id", required=True)
    begin_parser.add_argument("--generation", type=int, required=True)
    begin_parser.add_argument("--owner", required=True)
    begin_parser.add_argument("--work-id", required=True)
    begin_parser.add_argument("--intended-outcome", required=True)
    begin_parser.set_defaults(handler=begin_cycle)
    finish_parser = subparsers.add_parser("finish-cycle", help="finish a leased cycle with evidence")
    finish_parser.add_argument("--project", required=True)
    finish_parser.add_argument("--lease-id", required=True)
    finish_parser.add_argument("--generation", type=int, required=True)
    finish_parser.add_argument("--owner", required=True)
    finish_parser.add_argument("--cycle-id", required=True)
    finish_parser.add_argument("--actual-outcome", choices=sorted(PRODUCT_OUTCOMES), required=True)
    finish_parser.add_argument("--evidence-ids", nargs="+", required=True)
    finish_parser.add_argument("--cost-usd", type=float, required=True)
    finish_parser.add_argument("--latency-minutes", type=float, required=True)
    finish_parser.add_argument("--token-usage", type=int, required=True)
    finish_parser.add_argument("--user-visible-movement", choices=("true", "false"), required=True)
    finish_parser.add_argument("--work-disposition", choices=("continue", "complete"), required=True)
    finish_parser.add_argument("--reviewer-decision", choices=("accepted", "rejected"), required=True)
    finish_parser.add_argument("--reviewer", required=True)
    finish_parser.add_argument("--reviewer-grant", required=True)
    finish_parser.add_argument("--commit")
    finish_parser.add_argument("--ref")
    finish_parser.set_defaults(handler=finish_cycle)
    fabric_parser = subparsers.add_parser(
        "configure-fabric",
        help="bind a validated Sol-manager/Luna-worker manifest to primary work",
    )
    fabric_parser.add_argument("--project", required=True)
    fabric_parser.add_argument("--work-id", required=True)
    fabric_parser.add_argument("--manifest", required=True)
    fabric_parser.set_defaults(handler=configure_execution_fabric)
    report_parser = subparsers.add_parser(
        "record-fabric-phase",
        help="record one manager phase report for master review",
    )
    report_parser.add_argument("--project", required=True)
    report_parser.add_argument("--manager-id", required=True)
    report_parser.add_argument("--report", required=True)
    report_parser.add_argument("--lease-id", required=True)
    report_parser.add_argument("--generation", type=int, required=True)
    report_parser.add_argument("--owner", required=True)
    report_parser.set_defaults(handler=record_fabric_phase)
    decision_parser = subparsers.add_parser(
        "decide-fabric-phase",
        help="record an authenticated master decision on a manager phase",
    )
    decision_parser.add_argument("--project", required=True)
    decision_parser.add_argument("--manager-id", required=True)
    decision_parser.add_argument("--decision", choices=sorted(FABRIC_DECISIONS), required=True)
    decision_parser.add_argument("--decided-by", required=True)
    decision_parser.add_argument("--master-grant", required=True)
    decision_parser.add_argument("--lease-id", required=True)
    decision_parser.add_argument("--generation", type=int, required=True)
    decision_parser.add_argument("--owner", required=True)
    decision_parser.set_defaults(handler=decide_fabric_phase)
    admission_parser = subparsers.add_parser(
        "admit-runtime-attempt",
        help="record one feature-gated, signed pre-launch runtime admission",
    )
    admission_parser.add_argument("--project", required=True)
    admission_parser.add_argument("--lease-id", required=True)
    admission_parser.add_argument("--generation", type=int, required=True)
    admission_parser.add_argument("--owner", required=True)
    admission_parser.add_argument("--work-id", required=True)
    admission_parser.add_argument("--cycle-id", required=True)
    admission_parser.add_argument("--attempt-id", required=True)
    admission_parser.add_argument("--manifest-identity-id", required=True)
    admission_parser.add_argument("--parent-runtime-id", required=True)
    admission_parser.add_argument("--role", choices=("manager", "worker"), required=True)
    admission_parser.add_argument("--requested-model", required=True)
    admission_parser.add_argument("--provider", required=True)
    admission_parser.add_argument("--surface", required=True)
    admission_parser.add_argument("--account", required=True)
    admission_parser.add_argument("--scope", required=True, help="canonical JSON array matching the full manifest write scope")
    admission_parser.add_argument("--budget", required=True, help="canonical JSON object matching the manifest budget")
    admission_parser.add_argument("--fabric-manifest-digest", required=True)
    admission_parser.add_argument("--contract-digest", required=True)
    admission_parser.add_argument("--idempotency-key", required=True)
    admission_parser.add_argument("--admitted-by", required=True)
    admission_parser.add_argument("--actor-grant", required=True)
    admission_parser.set_defaults(handler=admit_runtime_attempt)
    observation_parser = subparsers.add_parser(
        "ingest-runtime-observation",
        help="verify and retain one attempt-scoped provider observation",
    )
    observation_parser.add_argument("--project", required=True)
    observation_parser.add_argument("--attempt-id", required=True)
    observation_parser.add_argument("--envelope", required=True)
    observation_parser.set_defaults(handler=ingest_runtime_observation)
    propose_parser = subparsers.add_parser("propose-adaptation", help="propose a bounded meta-loop change")
    propose_parser.add_argument("--project", required=True)
    propose_parser.add_argument("--failure-pattern", required=True)
    propose_parser.add_argument("--hypothesis", required=True)
    propose_parser.add_argument("--experiment", required=True)
    propose_parser.add_argument("--success-metric", required=True)
    propose_parser.add_argument("--rollback", required=True)
    propose_parser.add_argument("--proposer", required=True)
    propose_parser.add_argument("--time-cap-minutes", type=int, required=True)
    propose_parser.add_argument("--cost-cap-usd", type=float, required=True)
    propose_parser.add_argument("--changes", nargs="+", required=True)
    propose_parser.add_argument("--id")
    propose_parser.set_defaults(handler=propose_adaptation)
    review_parser = subparsers.add_parser("review-adaptation", help="independently review an adaptation")
    review_parser.add_argument("--project", required=True)
    review_parser.add_argument("--id", required=True)
    review_parser.add_argument("--reviewer", required=True)
    review_parser.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    review_parser.add_argument("--reviewer-grant", required=True)
    review_parser.set_defaults(handler=review_adaptation)
    for mutating_parser in (
        replace_parser,
        repair_transition_parser,
        cancel_parser,
        evidence_parser,
        supersede_parser,
        correct_parser,
        phase_parser,
        outcome_parser,
        work_parser,
        quality_parser,
        certify_parser,
        activate_parser,
        schedule_parser,
        acquire_parser,
        release_parser,
        resolve_parser,
        begin_parser,
        finish_parser,
        fabric_parser,
        report_parser,
        decision_parser,
        propose_parser,
        review_parser,
    ):
        mutating_parser.add_argument(
            "--command-key",
            required=True,
            help="stable caller-generated key for exact transactional retry",
        )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    command_key = getattr(args, "command_key", None)
    token = None
    command_envelope = None
    if command_key is not None:
        if not isinstance(command_key, str) or not command_key.strip() or command_key != command_key.strip():
            print(json.dumps({"ok": False, "errors": ["command_key must be a non-empty trimmed string"]}, indent=2))
            return 2
        payload = {
            key: value
            for key, value in vars(args).items()
            if key not in {"handler", "command_key"}
        }
        command_envelope = {
            "name": args.command,
            "key": command_key,
            "payload_sha256": command_payload_hash(args.command, payload),
        }
        token = _ACTIVE_COMMAND_ENVELOPE.set(command_envelope)
    try:
        if command_envelope is None:
            return int(args.handler(args))
        captured = io.StringIO()
        with redirect_stdout(captured):
            result_code = int(args.handler(args))
        if result_code != 0:
            sys.stdout.write(captured.getvalue())
            return result_code
        project = Path(args.project).resolve()
        store_module = control_store_module()
        if store_module.exists(project):
            connection = store_module.connect(project)
            try:
                retained = store_module.idempotency_lookup(
                    connection,
                    store_module.load(project)[1]["instance"]["project_id"],
                    "controller-cli",
                    command_envelope["key"],
                    command_envelope["payload_sha256"],
                )
            finally:
                connection.close()
            if retained is not None:
                print(json.dumps(retained["result"]))
                return 0
        sys.stdout.write(captured.getvalue())
        return result_code
    except CommandReplay as replay:
        print(json.dumps(replay.result))
        return 0
    finally:
        if token is not None:
            _ACTIVE_COMMAND_ENVELOPE.reset(token)


if __name__ == "__main__":
    sys.exit(main())
