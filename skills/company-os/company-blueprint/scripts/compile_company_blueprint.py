#!/usr/bin/env python3
"""Compile a Company OS blueprint into deterministic operating artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any


SCHEMA = "company-os.company-blueprint.v1"
COMPILED_SCHEMA = "company-os.compiled-company.v1"
MANIFEST_SCHEMA = "company-os.compiled-company-manifest.v1"
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
AGENT_SLOT_FIELDS = {
    "forbidden_roles",
    "id",
    "management_tier",
    "origin",
    "outcome",
    "requested_model",
    "role",
    "skills",
    "source_slot_id",
    "status",
}
MANAGER_FORBIDDEN = {"master", "worker"}
WORKER_FORBIDDEN = {"master", "manager"}
CRON_FIELD_RE = re.compile(r"^[0-9*,\-/]+$")
CADENCE_PERIODS = ("daily", "weekly", "monthly")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?:api[_-]?key|api[_-]?token|access[_-]?token|secret|password|passwd|pwd|private[_-]?key)"
    r"\s*[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{8,}",
    re.IGNORECASE,
)
DSN_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqps?|"
    r"mssql|sqlserver|cockroach(?:db)?|cassandra|jdbc:[a-z0-9]+)://",
    re.IGNORECASE,
)
URI_USERINFO_RE = re.compile(
    r"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/:@]+@",
    re.IGNORECASE,
)
PEM_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")
TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"sk-(?:proj-|svc-|live-|test-)?[A-Za-z0-9_-]{10,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r")",
)
BEARER_RE = re.compile(r"bearer\s+[A-Za-z0-9._\-+/=]{16,}", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEPARTMENTS = ROOT / "assets" / "department-packs.json"
DEFAULT_ARCHETYPES = ROOT / "assets" / "company-archetypes.json"
DEFAULT_PLAYBOOKS = ROOT / "assets" / "playbook-library.json"
REQUIRED_ARTIFACTS = (
    "agent-registry.json",
    "asset-registry.json",
    "capabilities.json",
    "integration-registry.json",
    "knowledge-graph.json",
    "organization.json",
    "routine-plan.json",
    "storage-plan.json",
    "work-graph.json",
)
BLUEPRINT_FIELDS = {
    "$schema",
    "assets",
    "authority",
    "blueprint_version",
    "brand",
    "cadence",
    "company_id",
    "execution_ready",
    "identity",
    "integrations",
    "knowledge",
    "market",
    "objectives",
    "operating_model",
    "storage",
    "unknowns",
}
MANIFEST_FIELDS = {"$schema", "blueprint_sha256", "blueprint_version", "company_id", "files"}


class BlueprintError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BlueprintError(f"value is not canonical JSON: {exc}") from exc


def atomic_write_bytes(path: Path, value: bytes) -> None:
    """Replace one compiled file without following a symlink into another instance."""
    if path.is_symlink():
        raise BlueprintError(f"refusing to write through symlink: {path.name}")
    if path.exists() and not path.is_file():
        raise BlueprintError(f"compiled artifact must be a regular file: {path.name}")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def require_real_output(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink() or not output.is_dir():
        raise BlueprintError("output must be a real directory")
    return output


def assert_output_company_binding(output: Path, company_id: str) -> None:
    manifest_path = output / "manifest.json"
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return
    existing = read_json(manifest_path, "existing compiled manifest")
    bound = existing.get("company_id")
    if isinstance(bound, str) and bound and bound != company_id:
        raise BlueprintError(
            f"output is already bound to company {bound}; refusing to overwrite with {company_id}"
        )


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BlueprintError(f"{label} must be a regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlueprintError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise BlueprintError(f"{label} must be a JSON object")
    return value


def require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        raise BlueprintError(f"{label} must be a canonical kebab-case identifier")
    return value


def reject_secret_material(value: Any, label: str) -> None:
    """Fail closed when a blueprint or compiled artifact contains secrets or DSNs."""
    serialized = canonical_bytes(value).decode("utf-8")
    if (
        SECRET_ASSIGNMENT_RE.search(serialized)
        or DSN_RE.search(serialized)
        or URI_USERINFO_RE.search(serialized)
        or PEM_PRIVATE_KEY_RE.search(serialized)
        or TOKEN_RE.search(serialized)
        or BEARER_RE.search(serialized)
    ):
        raise BlueprintError(f"{label} appears to contain secret material")


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BlueprintError(f"{label} must be a non-empty string")
    return value.strip()


def parse_cron(value: Any, label: str) -> tuple[str, str, str, str, str]:
    raw = require_text(value, label)
    parts = raw.split()
    if len(parts) != 5 or any(CRON_FIELD_RE.fullmatch(part) is None for part in parts):
        raise BlueprintError(f"{label} must be a 5-field cron expression")
    return parts[0], parts[1], parts[2], parts[3], parts[4]


def cron_period(value: Any, label: str) -> str:
    _minute, _hour, day_of_month, _month, day_of_week = parse_cron(value, label)
    if day_of_month != "*" and day_of_week == "*":
        return "monthly"
    if day_of_week != "*" and day_of_month == "*":
        return "weekly"
    if day_of_month == "*" and day_of_week == "*":
        return "daily"
    raise BlueprintError(f"{label} is ambiguous about daily, weekly, or monthly period")


def require_string_list(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise BlueprintError(f"{label} must be a{' non-empty' if nonempty else ''} list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise BlueprintError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise BlueprintError(f"{label} must not contain duplicates")
    return list(value)


def require_object(value: Any, label: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BlueprintError(f"{label} must be an object")
    if set(value) != fields:
        raise BlueprintError(f"{label} fields differ from the contract")
    return value


def require_object_fields(
    value: Any,
    label: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BlueprintError(f"{label} must be an object")
    allowed = required | (optional or set())
    keys = set(value)
    if not required <= keys or not keys <= allowed:
        raise BlueprintError(f"{label} fields differ from the contract")
    return value


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise BlueprintError(f"{label} is invalid")
    return value


def index_by_id(items: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise BlueprintError(f"{label} must be a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise BlueprintError(f"{label}[{index}] must be an object")
        item_id = require_id(item.get("id"), f"{label}[{index}].id")
        if item_id in indexed:
            raise BlueprintError(f"duplicate {label} id: {item_id}")
        indexed[item_id] = item
    return indexed


def validate_department_catalog(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    departments = index_by_id(value.get("departments"), "department catalog")
    expected = {
        "id", "mission", "capabilities", "decision_rights", "inputs", "outputs",
        "interfaces", "metrics", "playbooks", "required_approvals", "routines",
        "skills", "tools", "agent_slots",
    }
    routine_ids: set[str] = set()
    slot_ids: set[str] = set()
    for department_id, department in departments.items():
        if set(department) != expected:
            raise BlueprintError(f"department {department_id} fields differ from the contract")
        require_text(department["mission"], f"department {department_id}.mission")
        for field in (
            "capabilities", "decision_rights", "inputs", "outputs", "interfaces",
            "metrics", "playbooks", "required_approvals", "skills", "tools",
        ):
            items = require_string_list(department[field], f"department {department_id}.{field}", nonempty=True)
            if field in {"capabilities", "playbooks"}:
                for item in items:
                    require_id(item, f"department {department_id}.{field}")
        if not isinstance(department["routines"], list):
            raise BlueprintError(f"department {department_id}.routines must be a list")
        for routine in department["routines"]:
            if not isinstance(routine, dict) or set(routine) != {"id", "cadence", "playbook"}:
                raise BlueprintError(f"department {department_id} routine has an invalid shape")
            routine_id = require_id(routine["id"], f"department {department_id}.routine.id")
            if routine_id in routine_ids:
                raise BlueprintError(f"duplicate routine id: {routine_id}")
            routine_ids.add(routine_id)
            cron_period(routine["cadence"], f"routine {routine_id}.cadence")
            require_id(routine["playbook"], f"routine {routine_id}.playbook")
            if routine["playbook"] not in department["playbooks"]:
                raise BlueprintError(f"routine {routine_id} references a playbook outside its department")
        validate_department_agent_slots(department, slot_ids)
    return departments


def validate_agent_slot(slot: Any, department_id: str, slot_ids: set[str]) -> dict[str, Any]:
    if not isinstance(slot, dict) or set(slot) != AGENT_SLOT_FIELDS:
        raise BlueprintError(f"department {department_id} agent slot fields differ from the contract")
    slot_id = require_id(slot["id"], f"department {department_id}.agent_slot.id")
    if slot_id in slot_ids:
        raise BlueprintError(f"duplicate agent slot id: {slot_id}")
    slot_ids.add(slot_id)
    require_id(slot["source_slot_id"], f"{slot_id}.source_slot_id")
    require_text(slot["outcome"], f"{slot_id}.outcome")
    skills = require_string_list(slot["skills"], f"{slot_id}.skills", nonempty=True)
    for skill in skills:
        require_id(skill, f"{slot_id}.skills")
    forbidden = require_string_list(slot["forbidden_roles"], f"{slot_id}.forbidden_roles", nonempty=True)
    role = require_text(slot["role"], f"{slot_id}.role")
    tier = require_text(slot["management_tier"], f"{slot_id}.management_tier")
    origin = require_text(slot["origin"], f"{slot_id}.origin")
    status = require_text(slot["status"], f"{slot_id}.status")
    model = require_text(slot["requested_model"], f"{slot_id}.requested_model")
    if origin not in {"catalog", "stored"}:
        raise BlueprintError(f"{slot_id}.origin must be catalog or stored")
    if status not in {"template", "stored"}:
        raise BlueprintError(f"{slot_id}.status must be template or stored")
    if origin == "catalog" and (status != "template" or slot["source_slot_id"] != slot_id):
        raise BlueprintError(f"{slot_id} catalog templates must be self-sourced templates")
    if origin == "stored" and status != "stored":
        raise BlueprintError(f"{slot_id} stored slots must have status stored")
    if role == "manager":
        if tier not in {"middle", "low_level"}:
            raise BlueprintError(f"{slot_id} manager tier must be middle or low_level")
        if "manage-company-program" not in skills:
            raise BlueprintError(f"{slot_id} manager slot must include manage-company-program")
        if not MANAGER_FORBIDDEN.issubset(set(forbidden)):
            raise BlueprintError(f"{slot_id} manager slot must forbid master and worker")
        if model != "gpt-5.6-sol":
            raise BlueprintError(f"{slot_id} manager requested_model must remain gpt-5.6-sol")
    elif role == "worker":
        if tier != "staff":
            raise BlueprintError(f"{slot_id} worker tier must be staff")
        if "execute-bounded-task" not in skills:
            raise BlueprintError(f"{slot_id} worker slot must include execute-bounded-task")
        if not WORKER_FORBIDDEN.issubset(set(forbidden)):
            raise BlueprintError(f"{slot_id} worker slot must forbid master and manager")
        if model != "gpt-5.6-luna":
            raise BlueprintError(f"{slot_id} worker requested_model must remain gpt-5.6-luna")
    else:
        raise BlueprintError(f"{slot_id}.role must be manager or worker")
    if tier == "senior":
        raise BlueprintError(f"{slot_id} must not store the Company OS master as a department slot")
    return slot


def validate_department_agent_slots(department: dict[str, Any], slot_ids: set[str]) -> list[dict[str, Any]]:
    department_id = department["id"]
    slots = department.get("agent_slots")
    if not isinstance(slots, list) or not slots:
        raise BlueprintError(f"department {department_id} must store at least one agent slot")
    local_ids: set[str] = set()
    validated = [validate_agent_slot(slot, department_id, local_ids) for slot in slots]
    slot_ids.update(local_ids)
    if not any(slot["role"] == "manager" for slot in validated):
        raise BlueprintError(f"department {department_id} must store a manager slot")
    for slot in validated:
        if slot["source_slot_id"] not in local_ids:
            raise BlueprintError(f"{slot['id']} source_slot_id is not in the department")
    return validated


def validate_archetype_catalog(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    archetypes = index_by_id(value.get("archetypes"), "archetype catalog")
    for archetype_id, archetype in archetypes.items():
        if set(archetype) != {"id", "default_departments", "required_capabilities"}:
            raise BlueprintError(f"archetype {archetype_id} fields differ from the contract")
        require_string_list(archetype["default_departments"], f"archetype {archetype_id}.default_departments", nonempty=True)
        capabilities = require_string_list(archetype["required_capabilities"], f"archetype {archetype_id}.required_capabilities", nonempty=True)
        for capability in capabilities:
            require_id(capability, f"archetype {archetype_id}.required_capabilities")
    return archetypes


def validate_playbook_catalog(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    playbooks = index_by_id(value.get("playbooks"), "playbook catalog")
    for playbook_id, playbook in playbooks.items():
        if set(playbook) != {"id", "outcome", "steps", "evidence"}:
            raise BlueprintError(f"playbook {playbook_id} fields differ from the contract")
        require_text(playbook["outcome"], f"playbook {playbook_id}.outcome")
        require_string_list(playbook["steps"], f"playbook {playbook_id}.steps", nonempty=True)
        require_string_list(playbook["evidence"], f"playbook {playbook_id}.evidence", nonempty=True)
    return playbooks


def validate_blueprint(value: dict[str, Any]) -> None:
    require_object(value, "blueprint", BLUEPRINT_FIELDS)
    if value.get("$schema") != SCHEMA:
        raise BlueprintError(f"blueprint.$schema must be {SCHEMA!r}")
    require_id(value.get("company_id"), "blueprint.company_id")
    version = value.get("blueprint_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise BlueprintError("blueprint.blueprint_version must be a positive integer")
    if value.get("execution_ready") is not True:
        raise BlueprintError("blueprint.execution_ready must be true before compilation")

    identity = require_object(
        value.get("identity"),
        "blueprint.identity",
        {"legal_name", "operating_name", "mission", "thesis", "values"},
    )
    for field in ("legal_name", "operating_name", "mission", "thesis"):
        require_text(identity.get(field), f"blueprint.identity.{field}")
    require_string_list(identity.get("values"), "blueprint.identity.values", nonempty=True)

    market = require_object(
        value.get("market"),
        "blueprint.market",
        {"customer_segments", "problems", "offers"},
    )
    for field in ("customer_segments", "problems", "offers"):
        require_string_list(market.get(field), f"blueprint.market.{field}", nonempty=True)

    objectives = index_by_id(value.get("objectives"), "blueprint.objectives")
    priorities: set[int] = set()
    for objective_id, objective in objectives.items():
        if set(objective) != {"id", "outcome", "metric", "baseline", "target", "horizon", "priority"}:
            raise BlueprintError(f"objective {objective_id} fields differ from the contract")
        for field in ("outcome", "metric", "baseline", "target", "horizon"):
            require_text(objective.get(field), f"objective {objective_id}.{field}")
        priority = objective.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 1:
            raise BlueprintError(f"objective {objective_id}.priority must be positive")
        if priority in priorities:
            raise BlueprintError("objective priorities must be unique")
        priorities.add(priority)

    operating = require_object(
        value.get("operating_model"),
        "blueprint.operating_model",
        {"archetypes", "requested_capabilities", "department_overrides"},
    )
    archetypes = require_string_list(operating.get("archetypes"), "operating_model.archetypes", nonempty=True)
    for archetype_id in archetypes:
        require_id(archetype_id, "operating_model.archetypes")
    capabilities = require_string_list(
        operating.get("requested_capabilities"),
        "operating_model.requested_capabilities",
        nonempty=True,
    )
    for capability in capabilities:
        require_id(capability, "requested capability")
    overrides = operating.get("department_overrides")
    if not isinstance(overrides, list):
        raise BlueprintError("operating_model.department_overrides must be a list")
    seen_overrides: set[str] = set()
    for index, override in enumerate(overrides):
        if not isinstance(override, dict) or set(override) != {"department_id", "enabled", "reason"}:
            raise BlueprintError(f"department override {index} has an invalid shape")
        department_id = require_id(override.get("department_id"), f"department override {index}.department_id")
        if department_id in seen_overrides:
            raise BlueprintError(f"duplicate department override: {department_id}")
        seen_overrides.add(department_id)
        if not isinstance(override.get("enabled"), bool):
            raise BlueprintError(f"department override {index}.enabled must be boolean")
        require_text(override.get("reason"), f"department override {index}.reason")

    authority = require_object(
        value.get("authority"),
        "blueprint.authority",
        {"approval_required", "prohibited_actions"},
    )
    require_string_list(authority.get("approval_required"), "authority.approval_required")
    require_string_list(authority.get("prohibited_actions"), "authority.prohibited_actions")

    brand = require_object(value.get("brand"), "blueprint.brand", {"principles", "references"})
    require_string_list(brand.get("principles"), "brand.principles", nonempty=True)
    if not isinstance(brand.get("references"), list):
        raise BlueprintError("brand.references must be a list")

    knowledge = require_object(
        value.get("knowledge"),
        "blueprint.knowledge",
        {"classifications", "retention_policy", "sources"},
    )
    require_string_list(knowledge.get("classifications"), "knowledge.classifications", nonempty=True)
    require_text(knowledge.get("retention_policy"), "knowledge.retention_policy")
    if not isinstance(knowledge.get("sources"), list):
        raise BlueprintError("knowledge.sources must be a list")

    assets = value.get("assets")
    if not isinstance(assets, list):
        raise BlueprintError("blueprint.assets must be a list")
    asset_ids: set[str] = set()
    for index, asset in enumerate(assets):
        require_object_fields(asset, f"asset {index}", {"id", "kind", "locator"}, {"content_sha256"})
        asset_id = require_id(asset.get("id"), f"asset {index}.id")
        if asset_id in asset_ids:
            raise BlueprintError(f"duplicate asset id: {asset_id}")
        asset_ids.add(asset_id)
        require_text(asset.get("kind"), f"asset {asset_id}.kind")
        require_text(asset.get("locator"), f"asset {asset_id}.locator")
        if "content_sha256" in asset:
            require_sha256(asset.get("content_sha256"), f"asset {asset_id}.content_sha256")

    integrations = value.get("integrations")
    if not isinstance(integrations, list):
        raise BlueprintError("blueprint.integrations must be a list")
    integration_ids: set[str] = set()
    for index, integration in enumerate(integrations):
        require_object_fields(
            integration,
            f"integration {index}",
            {"id", "kind", "locator", "permission_mode"},
            {"credential_reference"},
        )
        integration_id = require_id(integration.get("id"), f"integration {index}.id")
        if integration_id in integration_ids:
            raise BlueprintError(f"duplicate integration id: {integration_id}")
        integration_ids.add(integration_id)
        if integration.get("kind") not in {"mcp", "plugin", "api", "repository", "database", "filesystem", "human"}:
            raise BlueprintError(f"integration {integration_id}.kind is invalid")
        require_text(integration.get("locator"), f"integration {integration_id}.locator")
        if integration.get("permission_mode") not in {"read_only", "proposal_only", "approved_write", "unavailable"}:
            raise BlueprintError(f"integration {integration_id}.permission_mode is invalid")
        if "credential_reference" in integration:
            reference = integration.get("credential_reference")
            if not isinstance(reference, str) or ENV_NAME_RE.fullmatch(reference) is None:
                raise BlueprintError(f"integration {integration_id}.credential_reference must name an environment variable")

    cadence = require_object(value.get("cadence"), "blueprint.cadence", set(CADENCE_PERIODS))
    cadence_ids = [require_id(cadence.get(field), f"cadence.{field}") for field in CADENCE_PERIODS]
    if len(set(cadence_ids)) != len(cadence_ids):
        raise BlueprintError("blueprint.cadence must name distinct routines")

    storage = require_object(value.get("storage"), "blueprint.storage", {"adapter", "dsn_env", "schema"})
    if storage.get("adapter") != "postgresql":
        raise BlueprintError("only the portable postgresql storage contract is currently supported")
    dsn_env = require_text(storage.get("dsn_env"), "storage.dsn_env")
    if ENV_NAME_RE.fullmatch(dsn_env) is None:
        raise BlueprintError("storage.dsn_env must name an environment variable")
    schema = require_text(storage.get("schema"), "storage.schema")
    if re.fullmatch(r"[a-z][a-z0-9_]*", schema) is None:
        raise BlueprintError("storage.schema must be a safe PostgreSQL identifier")

    unknowns = value.get("unknowns")
    if not isinstance(unknowns, list):
        raise BlueprintError("blueprint.unknowns must be a list")
    unknown_ids: set[str] = set()
    for index, item in enumerate(unknowns):
        if not isinstance(item, dict) or set(item) != {"id", "question", "blocking", "owner", "resolution"}:
            raise BlueprintError(f"unknown {index} has an invalid shape")
        unknown_id = require_id(item.get("id"), f"unknown {index}.id")
        if unknown_id in unknown_ids:
            raise BlueprintError(f"duplicate unknown id: {unknown_id}")
        unknown_ids.add(unknown_id)
        require_text(item.get("question"), f"unknown {index}.question")
        if not isinstance(item.get("blocking"), bool):
            raise BlueprintError(f"unknown {index}.blocking must be boolean")
        require_text(item.get("owner"), f"unknown {index}.owner")
        require_text(item.get("resolution"), f"unknown {index}.resolution")
    blocking = [item for item in unknowns if item.get("blocking") is True]
    if blocking:
        raise BlueprintError("execution-ready blueprint contains blocking unknowns")

    reject_secret_material(value, "blueprint")


def select_departments(
    blueprint: dict[str, Any],
    department_catalog: dict[str, Any],
    archetype_catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    departments = validate_department_catalog(department_catalog)
    archetypes = validate_archetype_catalog(archetype_catalog)
    operating = blueprint["operating_model"]
    requested = set(operating["requested_capabilities"])
    selected_ids: set[str] = set()
    required = set(requested)
    for archetype_id in operating["archetypes"]:
        archetype = archetypes.get(archetype_id)
        if archetype is None:
            raise BlueprintError(f"unknown company archetype: {archetype_id}")
        selected_ids.update(require_string_list(archetype.get("default_departments"), f"archetype {archetype_id}.default_departments"))
        required.update(require_string_list(archetype.get("required_capabilities"), f"archetype {archetype_id}.required_capabilities"))

    for department_id in list(selected_ids):
        if department_id not in departments:
            raise BlueprintError(f"archetype references unknown department: {department_id}")

    overrides: dict[str, bool] = {}
    for override in operating["department_overrides"]:
        department_id = override["department_id"]
        if department_id not in departments:
            raise BlueprintError(f"override references unknown department: {department_id}")
        overrides[department_id] = override["enabled"]
    for department_id, enabled in overrides.items():
        if enabled:
            selected_ids.add(department_id)
        else:
            selected_ids.discard(department_id)

    covered = {
        capability
        for department_id in selected_ids
        for capability in departments[department_id].get("capabilities", [])
    }
    for capability in sorted(required - covered):
        candidates = sorted(
            department_id
            for department_id, department in departments.items()
            if capability in department.get("capabilities", []) and overrides.get(department_id) is not False
        )
        if not candidates:
            raise BlueprintError(f"E_REQUIRED_CAPABILITY_UNAVAILABLE: {capability}")
        selected_ids.add(candidates[0])
        covered.update(departments[candidates[0]].get("capabilities", []))

    missing = sorted(required - covered)
    if missing:
        raise BlueprintError(f"required capabilities remain uncovered: {missing}")
    return [departments[item] for item in sorted(selected_ids)], sorted(required)


def compile_artifacts(
    blueprint: dict[str, Any],
    selected: list[dict[str, Any]],
    required_capabilities: list[str],
    playbook_catalog: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    company_id = blueprint["company_id"]
    blueprint_version = blueprint["blueprint_version"]
    department_ids = [department["id"] for department in selected]
    skills = sorted({skill for department in selected for skill in department["skills"]})
    tools = sorted({tool for department in selected for tool in department["tools"]})
    playbook_ids = sorted({playbook for department in selected for playbook in department["playbooks"]})
    available_playbooks = validate_playbook_catalog(playbook_catalog)
    missing_playbooks = sorted(set(playbook_ids) - set(available_playbooks))
    if missing_playbooks:
        raise BlueprintError(f"department packs reference missing playbooks: {missing_playbooks}")
    playbooks = [available_playbooks[playbook_id] for playbook_id in playbook_ids]

    organization = {
        "$schema": COMPILED_SCHEMA,
        "blueprint_version": blueprint_version,
        "capacity_policy": {
            "manager_capacity_source": "accepted-outcome-graph",
            "manager_concurrency_source": "dependency-width-host-budget-and-observed-performance",
            "topology_mode": "elastic_work_graph",
            "worker_capacity_source": "manager-task-dag",
            "worker_concurrency_source": "dependency-width-resource-leases-and-observed-performance",
        },
        "company_id": company_id,
        "department_count": len(selected),
        "departments": selected,
    }
    capabilities = {
        "$schema": "company-os.compiled-capability-map.v1",
        "company_id": company_id,
        "playbooks": playbooks,
        "required_capabilities": required_capabilities,
        "resolution_policy": "verify every required skill and tool against the live host before program dispatch",
        "skills": [{"id": skill, "status": "requires-host-preflight"} for skill in skills],
        "tools": [{"id": tool, "status": "requires-host-preflight"} for tool in tools],
    }

    routines: list[dict[str, Any]] = []
    for department in selected:
        for routine in department["routines"]:
            routines.append(
                {
                    "activation_state": "planned",
                    "cadence": routine["cadence"],
                    "department_id": department["id"],
                    "id": routine["id"],
                    "playbook": routine["playbook"],
                    "required_approvals": department["required_approvals"],
                }
            )
    routines.sort(key=lambda item: item["id"])
    routine_by_id = {item["id"]: item for item in routines}
    company_cadence: dict[str, str] = {}
    for period in CADENCE_PERIODS:
        routine_id = blueprint["cadence"][period]
        named = routine_by_id.get(routine_id)
        if named is None:
            raise BlueprintError(
                f"cadence.{period} references a routine outside the selected organization "
                f"and not in the compiled organization: {routine_id}"
            )
        observed = cron_period(named["cadence"], f"routine {routine_id}.cadence")
        if observed != period:
            raise BlueprintError(
                f"cadence.{period} names {routine_id} which runs on a {observed} cadence"
            )
        company_cadence[period] = routine_id
    routine_plan = {
        "$schema": "company-os.compiled-routine-plan.v1",
        "activation_policy": "feature-off-until-runtime-scheduler-and-cancellation-gates-pass",
        "cadence": company_cadence,
        "company_cadence": company_cadence,
        "company_id": company_id,
        "routines": routines,
    }

    if "executive-strategy" not in department_ids:
        raise BlueprintError("work graph requires the selected organization to include executive-strategy")
    tasks = [
        {
            "acceptance": ["Company blueprint is operator-accepted and hash-bound"],
            "department_id": "executive-strategy",
            "depends_on": [],
            "id": "initialize-company-direction",
            "outcome": "Establish accepted company direction and objectives",
        }
    ]
    if "program-management" in department_ids:
        tasks.append(
            {
                "acceptance": ["Program portfolio maps every objective to an owner and evidence"],
                "department_id": "program-management",
                "depends_on": ["initialize-company-direction"],
                "id": "initialize-program-portfolio",
                "outcome": "Translate objectives into an accountable program portfolio",
            }
        )
    foundation = "initialize-program-portfolio" if "program-management" in department_ids else "initialize-company-direction"
    for department_id in department_ids:
        if department_id in {"executive-strategy", "program-management"}:
            continue
        tasks.append(
            {
                "acceptance": [f"{department_id} charter, capabilities, interfaces, and scorecard are accepted"],
                "department_id": department_id,
                "depends_on": [foundation],
                "id": f"activate-{department_id}",
                "outcome": f"Activate the {department_id} operating pack",
            }
        )
    task_ids = {task["id"] for task in tasks}
    for task in tasks:
        if task["department_id"] not in department_ids:
            raise BlueprintError(f"work graph task {task['id']} references an unselected department")
        if any(dependency not in task_ids for dependency in task["depends_on"]):
            raise BlueprintError(f"work graph task {task['id']} has a dangling dependency")
    work_graph = {
        "$schema": "company-os.compiled-work-graph.v1",
        "company_id": company_id,
        "tasks": sorted(tasks, key=lambda item: item["id"]),
    }

    nodes: list[dict[str, Any]] = [
        {"id": f"company:{company_id}", "kind": "company", "label": blueprint["identity"]["operating_name"]}
    ]
    edges: list[dict[str, str]] = []
    for objective in sorted(blueprint["objectives"], key=lambda item: item["id"]):
        node_id = f"objective:{objective['id']}"
        nodes.append(
            {
                "baseline": objective["baseline"],
                "horizon": objective["horizon"],
                "id": node_id,
                "kind": "objective",
                "label": objective["outcome"],
                "metric": objective["metric"],
                "priority": objective["priority"],
                "target": objective["target"],
            }
        )
        edges.append({"from": f"company:{company_id}", "kind": "pursues", "to": node_id})
    for department in selected:
        node_id = f"department:{department['id']}"
        nodes.append({"id": node_id, "kind": "department", "label": department["mission"]})
        edges.append({"from": f"company:{company_id}", "kind": "operates", "to": node_id})
        for objective in blueprint["objectives"]:
            edges.append({"from": node_id, "kind": "contributes-to", "to": f"objective:{objective['id']}"})
    for skill in skills:
        node_id = f"skill:{skill}"
        nodes.append({"id": node_id, "kind": "skill", "label": skill})
        for department in selected:
            if skill in department["skills"]:
                edges.append({"from": f"department:{department['id']}", "kind": "uses", "to": node_id})
    for department in selected:
        for slot in department["agent_slots"]:
            node_id = f"agent-slot:{slot['id']}"
            nodes.append({"id": node_id, "kind": "agent-slot", "label": slot["outcome"]})
            edges.append({"from": f"department:{department['id']}", "kind": "stores", "to": node_id})
            if slot["origin"] == "stored" and slot["source_slot_id"] != slot["id"]:
                edges.append({
                    "from": f"agent-slot:{slot['source_slot_id']}",
                    "kind": "cloned-as",
                    "to": node_id,
                })

    assets = []
    for asset in blueprint["assets"]:
        asset_id = asset["id"]
        compiled_asset = {"id": asset_id, "kind": asset["kind"], "locator": asset["locator"]}
        if "content_sha256" in asset:
            compiled_asset["content_sha256"] = asset["content_sha256"]
        assets.append(compiled_asset)
        nodes.append({"id": f"asset:{asset_id}", "kind": "asset", "label": asset_id})
        edges.append({"from": f"company:{company_id}", "kind": "references", "to": f"asset:{asset_id}"})
    integrations = []
    for integration in blueprint["integrations"]:
        integration_id = integration["id"]
        compiled_integration = {
            "id": integration_id,
            "kind": integration["kind"],
            "locator": integration["locator"],
            "permission_mode": integration["permission_mode"],
        }
        if "credential_reference" in integration:
            compiled_integration["credential_reference"] = integration["credential_reference"]
        integrations.append(compiled_integration)
        nodes.append({"id": f"integration:{integration_id}", "kind": "integration", "label": integration_id})
        edges.append({"from": f"company:{company_id}", "kind": "connects", "to": f"integration:{integration_id}"})
    knowledge_graph = {
        "$schema": "company-os.compiled-knowledge-graph.v1",
        "classifications": list(blueprint["knowledge"]["classifications"]),
        "company_id": company_id,
        "edges": sorted(edges, key=lambda item: (item["from"], item["kind"], item["to"])),
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "retention_policy": blueprint["knowledge"]["retention_policy"],
        "sources": list(blueprint["knowledge"]["sources"]),
    }
    node_ids = {node["id"] for node in knowledge_graph["nodes"]}
    if any(edge["from"] not in node_ids or edge["to"] not in node_ids for edge in knowledge_graph["edges"]):
        raise BlueprintError("compiled knowledge graph contains a dangling edge")

    asset_registry = {
        "$schema": "company-os.compiled-asset-registry.v1",
        "assets": sorted(assets, key=lambda item: item["id"]),
        "brand": {
            "principles": list(blueprint["brand"]["principles"]),
            "references": list(blueprint["brand"]["references"]),
        },
        "company_id": company_id,
    }
    integration_registry = {
        "$schema": "company-os.compiled-integration-registry.v1",
        "company_id": company_id,
        "credential_policy": "environment-or-provider-managed-reference-only",
        "integrations": sorted(integrations, key=lambda item: item["id"]),
    }
    storage_plan = {
        "$schema": "company-os.compiled-storage-plan.v1",
        "adapter": blueprint["storage"]["adapter"],
        "company_id": company_id,
        "dsn_env": blueprint["storage"]["dsn_env"],
        "portability": ["neon", "supabase", "amazon-rds", "google-cloud-sql", "self-managed-postgresql"],
        "schema": blueprint["storage"]["schema"],
    }
    agent_slots = []
    for department in selected:
        for slot in department["agent_slots"]:
            agent_slots.append(
                {
                    "department_id": department["id"],
                    "forbidden_roles": list(slot["forbidden_roles"]),
                    "id": slot["id"],
                    "management_tier": slot["management_tier"],
                    "origin": slot["origin"],
                    "outcome": slot["outcome"],
                    "requested_model": slot["requested_model"],
                    "role": slot["role"],
                    "skills": list(slot["skills"]),
                    "source_slot_id": slot["source_slot_id"],
                    "status": slot["status"],
                }
            )
    agent_registry = {
        "$schema": "company-os.compiled-agent-registry.v1",
        "activation_policy": "templates-not-running-agents",
        "company_id": company_id,
        "slots": sorted(agent_slots, key=lambda item: item["id"]),
    }
    return {
        "agent-registry.json": agent_registry,
        "asset-registry.json": asset_registry,
        "capabilities.json": capabilities,
        "integration-registry.json": integration_registry,
        "knowledge-graph.json": knowledge_graph,
        "organization.json": organization,
        "routine-plan.json": routine_plan,
        "storage-plan.json": storage_plan,
        "work-graph.json": work_graph,
    }


def store_agent_slot(
    catalog_path: Path,
    department_id: str,
    slot_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    catalog = read_json(catalog_path, "department catalog")
    departments = validate_department_catalog(catalog)
    department = departments.get(department_id)
    if department is None:
        raise BlueprintError(f"unknown department: {department_id}")
    slot = read_json(slot_path, "agent slot")
    if slot.get("origin") != "stored" or slot.get("status") != "stored":
        raise BlueprintError("created agents must be stored as origin=stored status=stored slots")
    existing_ids = {item["id"] for item in department["agent_slots"]}
    new_id = require_id(slot.get("id"), "stored agent slot.id")
    if new_id in existing_ids:
        raise BlueprintError(f"agent slot already stored: {new_id}")
    source_id = require_id(slot.get("source_slot_id"), "stored agent slot.source_slot_id")
    source = next((item for item in department["agent_slots"] if item["id"] == source_id), None)
    if source is None:
        raise BlueprintError(f"source_slot_id is not in {department_id}: {source_id}")
    if slot.get("role") != source["role"] or slot.get("management_tier") != source["management_tier"]:
        raise BlueprintError("stored agent must keep the source role and management tier")
    if slot.get("requested_model") != source["requested_model"]:
        raise BlueprintError("stored agent must keep the source requested_model")
    updated = copy_department_with_slot(catalog, department_id, slot)
    validate_department_catalog(updated)
    raw = canonical_bytes(updated)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and (output_path.is_symlink() or not output_path.is_file()):
        raise BlueprintError("store-agent output must be a regular file")
    if output_path.resolve() == DEFAULT_DEPARTMENTS.resolve():
        raise BlueprintError("do not store created agents into the shared department catalog")
    output_path.write_bytes(raw)
    return {
        "ok": True,
        "department_id": department_id,
        "slot_id": new_id,
        "source_slot_id": source_id,
        "catalog_sha256": digest_bytes(raw),
        "status": "stored",
        "running": False,
    }


def copy_department_with_slot(
    catalog: dict[str, Any],
    department_id: str,
    slot: dict[str, Any],
) -> dict[str, Any]:
    departments = []
    for department in catalog["departments"]:
        if department["id"] != department_id:
            departments.append(department)
            continue
        cloned = dict(department)
        cloned["agent_slots"] = list(department["agent_slots"]) + [slot]
        departments.append(cloned)
    updated = dict(catalog)
    updated["departments"] = departments
    return updated


def compile_blueprint(
    blueprint_path: Path,
    output: Path,
    department_catalog_path: Path = DEFAULT_DEPARTMENTS,
    archetype_catalog_path: Path = DEFAULT_ARCHETYPES,
    playbook_catalog_path: Path = DEFAULT_PLAYBOOKS,
) -> dict[str, Any]:
    blueprint = read_json(blueprint_path, "blueprint")
    validate_blueprint(blueprint)
    departments = read_json(department_catalog_path, "department catalog")
    reject_secret_material(departments, "department catalog")
    archetypes = read_json(archetype_catalog_path, "archetype catalog")
    reject_secret_material(archetypes, "archetype catalog")
    playbooks = read_json(playbook_catalog_path, "playbook catalog")
    reject_secret_material(playbooks, "playbook catalog")
    selected, required = select_departments(blueprint, departments, archetypes)
    artifacts = compile_artifacts(blueprint, selected, required, playbooks)
    if set(artifacts) != set(REQUIRED_ARTIFACTS):
        raise BlueprintError("compiler emitted an unexpected artifact set")
    for name, artifact in artifacts.items():
        reject_secret_material(artifact, f"compiled artifact {name}")
    output = require_real_output(output)
    assert_output_company_binding(output, blueprint["company_id"])
    unexpected = sorted(
        path.name
        for path in output.iterdir()
        if path.name not in set(artifacts) | {"manifest.json"}
    )
    if unexpected:
        raise BlueprintError(f"output contains unexpected files: {unexpected}")
    for name in (*artifacts, "manifest.json"):
        if (output / name).is_symlink():
            raise BlueprintError(f"refusing to write through symlink: {name}")
    files: list[dict[str, Any]] = []
    for name, artifact in sorted(artifacts.items()):
        raw = canonical_bytes(artifact)
        atomic_write_bytes(output / name, raw)
        files.append({"path": name, "sha256": digest_bytes(raw), "size": len(raw)})
    blueprint_raw = canonical_bytes(blueprint)
    manifest = {
        "$schema": MANIFEST_SCHEMA,
        "blueprint_sha256": digest_bytes(blueprint_raw),
        "blueprint_version": blueprint["blueprint_version"],
        "company_id": blueprint["company_id"],
        "files": files,
    }
    atomic_write_bytes(output / "manifest.json", canonical_bytes(manifest))
    verify_compiled(output)
    return manifest


def verify_compiled(output: Path) -> dict[str, Any]:
    if output.is_symlink() or not output.is_dir():
        raise BlueprintError("compiled output must be a real directory")
    if any(path.is_symlink() or path.is_dir() for path in output.iterdir()):
        raise BlueprintError("compiled output contains unsafe entries")
    manifest_path = output / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BlueprintError("compiled manifest is missing or unsafe")
    raw_manifest = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlueprintError(f"compiled manifest is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise BlueprintError("compiled manifest must be a JSON object")
    if raw_manifest != canonical_bytes(manifest):
        raise BlueprintError("compiled manifest is not canonical")
    require_object(manifest, "compiled manifest", MANIFEST_FIELDS)
    if manifest.get("$schema") != MANIFEST_SCHEMA:
        raise BlueprintError("compiled manifest schema is invalid")
    require_id(manifest.get("company_id"), "manifest.company_id")
    version = manifest.get("blueprint_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise BlueprintError("manifest.blueprint_version must be a positive integer")
    require_sha256(manifest.get("blueprint_sha256"), "manifest.blueprint_sha256")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise BlueprintError("compiled manifest files must be a non-empty list")
    seen_paths: set[str] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            raise BlueprintError(f"manifest.files[{index}] has an invalid shape")
        path_name = item["path"]
        if (
            not isinstance(path_name, str)
            or path_name != Path(path_name).name
            or path_name in {"", ".", "..", "manifest.json"}
            or "/" in path_name
            or "\\" in path_name
        ):
            raise BlueprintError(f"manifest.files[{index}].path is unsafe")
        if path_name in seen_paths:
            raise BlueprintError(f"duplicate manifest path: {path_name}")
        seen_paths.add(path_name)
        size = item["size"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise BlueprintError(f"manifest.files[{index}].size is invalid")
        require_sha256(item["sha256"], f"manifest.files[{index}].sha256")
    if [item["path"] for item in files] != sorted(REQUIRED_ARTIFACTS):
        raise BlueprintError("compiled manifest file set differs from the contract")
    actual_names = {path.name for path in output.iterdir() if path.is_file()}
    if actual_names != set(REQUIRED_ARTIFACTS) | {"manifest.json"}:
        raise BlueprintError("compiled output file set differs from manifest")
    for item in files:
        path = output / item["path"]
        if path.is_symlink() or not path.is_file():
            raise BlueprintError(f"compiled artifact is missing or unsafe: {item['path']}")
        raw = path.read_bytes()
        if len(raw) != item["size"] or digest_bytes(raw) != item["sha256"]:
            raise BlueprintError(f"compiled artifact drifted: {item['path']}")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlueprintError(f"compiled artifact is not valid UTF-8 JSON: {item['path']}") from exc
        if raw != canonical_bytes(parsed):
            raise BlueprintError(f"compiled artifact is not canonical: {item['path']}")
        reject_secret_material(parsed, f"compiled artifact {item['path']}")
    return {"ok": True, "company_id": manifest["company_id"], "files": len(files)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--departments", type=Path, default=DEFAULT_DEPARTMENTS)
    parser.add_argument("--archetypes", type=Path, default=DEFAULT_ARCHETYPES)
    parser.add_argument("--playbooks", type=Path, default=DEFAULT_PLAYBOOKS)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--store-agent", type=Path)
    parser.add_argument("--department", type=str)
    args = parser.parse_args()
    try:
        if args.store_agent is not None:
            if not args.department:
                parser.error("--department is required with --store-agent")
            result = store_agent_slot(
                args.departments,
                args.department,
                args.store_agent,
                args.output,
            )
        elif args.verify:
            result = verify_compiled(args.output)
        else:
            if args.blueprint is None:
                parser.error("--blueprint is required unless --verify is used")
            result = compile_blueprint(
                args.blueprint,
                args.output,
                args.departments,
                args.archetypes,
                args.playbooks,
            )
        print(canonical_bytes(result).decode("utf-8"), end="")
        return 0
    except (BlueprintError, OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        print(canonical_bytes({"ok": False, "error": str(exc)}).decode("utf-8"), end="")
        return 1


if __name__ == "__main__":
    sys.exit(main())
