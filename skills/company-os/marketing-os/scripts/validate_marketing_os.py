#!/usr/bin/env python3
"""Validate the Marketing OS pack, spawn template, and artifact contracts.

The template is a thinking overlay for the Marketing department. It cannot be
spawned as the master persona, a Luna worker, an orchestrator hop, or a
fourth executable hop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "company-os.marketing-os-spawn-template.v1"
TEMPLATE_ID = "marketing-os"
REQUIRED_SKILLS = ("manage-company-program", "marketing-os")
FORBIDDEN_ROLES = ("master", "worker")
USE_WHEN = (
    "audience_research",
    "campaign_brief",
    "marketing_copy",
    "marketing_pipeline",
    "marketing_scale",
)
SOURCE_FILES = (
    "00-index.txt",
    "01-pipeline.txt",
    "02-artifact-contracts.txt",
    "03-scale.txt",
    "04-context-and-memory.txt",
    "05-quality-and-authority.txt",
)
TOP_LEVEL = {
    "schema",
    "template_id",
    "role",
    "requested_model",
    "skills",
    "forbidden_roles",
    "source_pack",
    "authority",
    "use_when",
}
SKILL_MARKERS = (
    "thinking overlay for the marketing department",
    "do not send this skill to luna workers",
    "do not use it as the master persona",
    "does not own",
    "not a copy of that repository",
    "research packet → brief contract → copy packet",
    "do not spawn an orchestrator",
    "scale by independently accountable campaigns",
    "do not write copy without a brief digest",
    "sales-accepted qualified lead",
    "tokens follow the global bottleneck",
    "$execute-outcome-evaluator",
    "$force-first-execution",
    "a framework memo without a candidate is not progress",
)
ARTIFACT_SCHEMAS = {
    "audience-profile": "company-os.marketing-audience-profile.v1",
    "research-report": "company-os.marketing-research-report.v1",
    "campaign-brief": "company-os.marketing-campaign-brief.v1",
    "copy-packet": "company-os.marketing-copy-packet.v1",
}
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
CONFIDENCE = {"high", "medium", "low"}
BRIEF_STATUS = {"draft", "ready-for-review", "accepted", "stopped"}
COPY_FORMATS = {"linkedin-post", "email-sequence", "landing-page", "ad-copy", "other"}


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_object(value: Any, label: str, required: set[str]) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} must be an object"]
    extra = sorted(set(value) - required)
    missing = sorted(required - set(value))
    errors: list[str] = []
    if extra:
        errors.append(f"{label} has unknown keys: {', '.join(extra)}")
    if missing:
        errors.append(f"{label} missing keys: {', '.join(missing)}")
    return errors


def require_id(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        return [f"{label} must be a kebab-case identifier"]
    return []


def require_text(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label} must be a non-empty string"]
    return []


def require_digest(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        return [f"{label} must be a sha256 hex digest"]
    return []


def require_sourced_list(value: Any, label: str, *, maximum: int | None = None) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{label} must be a non-empty list"]
    if maximum is not None and len(value) > maximum:
        return [f"{label} exceeds {maximum} items"]
    errors: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"claim", "source"} and set(item) != {"quote", "source"}:
            # allow quote/source or claim/source
            if not isinstance(item, dict):
                errors.append(f"{label}[{index}] must be an object")
                continue
        text_key = "quote" if "quote" in item else "claim"
        errors.extend(require_object(item, f"{label}[{index}]", {text_key, "source"}))
        errors.extend(require_text(item.get(text_key), f"{label}[{index}].{text_key}"))
        errors.extend(require_text(item.get("source"), f"{label}[{index}].source"))
    return errors


def validate_audience_profile(payload: Any) -> list[str]:
    required = {
        "$schema", "profile_id", "subject", "job", "primary_pain",
        "voice_of_customer", "alternatives", "sources", "confidence", "gaps",
    }
    errors = require_object(payload, "audience-profile", required)
    if errors and not isinstance(payload, dict):
        return errors
    if payload.get("$schema") != ARTIFACT_SCHEMAS["audience-profile"]:
        errors.append("audience-profile.$schema drifted")
    errors.extend(require_id(payload.get("profile_id"), "profile_id"))
    for field in ("subject", "job", "primary_pain"):
        errors.extend(require_text(payload.get(field), field))
    errors.extend(require_sourced_list(payload.get("voice_of_customer"), "voice_of_customer", maximum=5))
    for field in ("alternatives", "sources", "gaps"):
        value = payload.get(field)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{field} must be a non-empty string list")
    if payload.get("confidence") not in CONFIDENCE:
        errors.append("audience-profile.confidence must be high, medium, or low")
    return errors


def validate_research_report(payload: Any) -> list[str]:
    required = {"$schema", "report_id", "question", "findings", "confidence", "gaps"}
    errors = require_object(payload, "research-report", required)
    if not isinstance(payload, dict):
        return errors
    if payload.get("$schema") != ARTIFACT_SCHEMAS["research-report"]:
        errors.append("research-report.$schema drifted")
    errors.extend(require_id(payload.get("report_id"), "report_id"))
    errors.extend(require_text(payload.get("question"), "question"))
    findings = payload.get("findings")
    if not isinstance(findings, list) or not findings or len(findings) > 5:
        errors.append("findings must be 1-5 items")
    else:
        for index, item in enumerate(findings):
            errors.extend(
                require_object(
                    item, f"findings[{index}]",
                    {"finding", "source", "confidence", "implication"},
                )
            )
            if isinstance(item, dict):
                for field in ("finding", "source", "implication"):
                    errors.extend(require_text(item.get(field), f"findings[{index}].{field}"))
                if item.get("confidence") not in CONFIDENCE:
                    errors.append(f"findings[{index}].confidence must be high, medium, or low")
    if payload.get("confidence") not in CONFIDENCE:
        errors.append("research-report.confidence must be high, medium, or low")
    gaps = payload.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        errors.append("gaps must be a non-empty list")
    return errors


def validate_campaign_brief(payload: Any) -> list[str]:
    required = {
        "$schema", "brief_id", "status", "goal", "audience_profile_digest",
        "promise", "differentiator", "proof", "deliverables", "constraints",
        "kill_rule", "qualified_lead", "brand_locator", "voice_locator",
        "measurement",
    }
    optional = {"client_locator"}
    if not isinstance(payload, dict):
        return ["campaign-brief must be an object"]
    errors = require_object(payload, "campaign-brief", required | (set(payload) & optional))
    if payload.get("$schema") != ARTIFACT_SCHEMAS["campaign-brief"]:
        errors.append("campaign-brief.$schema drifted")
    errors.extend(require_id(payload.get("brief_id"), "brief_id"))
    if payload.get("status") not in BRIEF_STATUS:
        errors.append("campaign-brief.status is invalid")
    for field in ("goal", "promise", "differentiator", "kill_rule", "qualified_lead", "brand_locator", "voice_locator"):
        errors.extend(require_text(payload.get(field), field))
    if isinstance(payload.get("goal"), str) and "awareness" in payload["goal"].casefold():
        errors.append("campaign-brief.goal must not use awareness as the object")
    errors.extend(require_digest(payload.get("audience_profile_digest"), "audience_profile_digest"))
    errors.extend(require_sourced_list(payload.get("proof"), "proof", maximum=5))
    deliverables = payload.get("deliverables")
    if not isinstance(deliverables, list) or not deliverables:
        errors.append("deliverables must be a non-empty list")
    else:
        for index, item in enumerate(deliverables):
            errors.extend(require_object(item, f"deliverables[{index}]", {"format", "quantity", "cta"}))
            if isinstance(item, dict):
                if item.get("format") not in COPY_FORMATS:
                    errors.append(f"deliverables[{index}].format is invalid")
                quantity = item.get("quantity")
                if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
                    errors.append(f"deliverables[{index}].quantity must be a positive integer")
                errors.extend(require_text(item.get("cta"), f"deliverables[{index}].cta"))
    constraints = payload.get("constraints")
    errors.extend(require_object(constraints if isinstance(constraints, dict) else {}, "constraints", {"never_claim", "required_approvals"}))
    measurement = payload.get("measurement")
    errors.extend(require_object(measurement if isinstance(measurement, dict) else {}, "measurement", {"primary_kpi", "target"}))
    if isinstance(measurement, dict) and isinstance(measurement.get("primary_kpi"), str):
        if "awareness" in measurement["primary_kpi"].casefold() or "impression" in measurement["primary_kpi"].casefold():
            errors.append("measurement.primary_kpi must not be awareness or impressions")
    return errors


def validate_copy_packet(payload: Any) -> list[str]:
    required = {
        "$schema", "packet_id", "brief_digest", "format", "body",
        "claims", "cta", "voice_check",
    }
    errors = require_object(payload, "copy-packet", required)
    if not isinstance(payload, dict):
        return errors
    if payload.get("$schema") != ARTIFACT_SCHEMAS["copy-packet"]:
        errors.append("copy-packet.$schema drifted")
    errors.extend(require_id(payload.get("packet_id"), "packet_id"))
    errors.extend(require_digest(payload.get("brief_digest"), "brief_digest"))
    if payload.get("format") not in COPY_FORMATS:
        errors.append("copy-packet.format is invalid")
    for field in ("body", "cta", "voice_check"):
        errors.extend(require_text(payload.get(field), field))
    errors.extend(require_sourced_list(payload.get("claims"), "claims"))
    return errors


def validate_spawn_template(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["spawn template must be an object"]
    extra = sorted(set(payload) - TOP_LEVEL)
    missing = sorted(TOP_LEVEL - set(payload))
    if extra:
        errors.append(f"unknown spawn keys: {', '.join(extra)}")
    if missing:
        errors.append(f"missing spawn keys: {', '.join(missing)}")
    if payload.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if payload.get("template_id") != TEMPLATE_ID:
        errors.append("template_id drifted")
    if payload.get("role") != "manager":
        errors.append("spawn role must be manager")
    if payload.get("requested_model") != "gpt-5.6-sol":
        errors.append("requested_model must remain gpt-5.6-sol")
    if payload.get("authority") != "thinking_overlay":
        errors.append("authority must be thinking_overlay")
    if payload.get("source_pack") != "references/source":
        errors.append("source_pack drifted")
    skills = payload.get("skills")
    if not isinstance(skills, list) or list(skills) != list(REQUIRED_SKILLS):
        errors.append("spawn skills must be the manager role skill plus marketing-os")
    forbidden = payload.get("forbidden_roles")
    if not isinstance(forbidden, list) or set(forbidden) != set(FORBIDDEN_ROLES):
        errors.append("forbidden_roles must be master and worker")
    use_when = payload.get("use_when")
    if not isinstance(use_when, list) or list(use_when) != list(USE_WHEN):
        errors.append("use_when must be the marketing-os lanes")
    return errors


def validate_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["missing SKILL.md"]
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\nname: marketing-os\n"):
        errors.append("SKILL.md name must be marketing-os")
    words = len(text.split())
    if words > 700:
        errors.append(f"SKILL.md exceeds 700 words: {words}")
    folded = text.casefold()
    for marker in SKILL_MARKERS:
        if marker not in folded:
            errors.append(f"SKILL.md missing required marker: {marker}")
    if "TODO" in text:
        errors.append("SKILL.md has unresolved TODO")
    if "mos-orchestrator" in folded or "always-on" in folded:
        errors.append("SKILL.md must not restore an always-on orchestrator")

    source_root = root / "references" / "source"
    for name in SOURCE_FILES:
        path = source_root / name
        if not path.is_file() or path.stat().st_size <= 0:
            errors.append(f"missing source file: {name}")
    extra = sorted(
        path.name
        for path in source_root.iterdir()
        if path.is_file() and path.name not in SOURCE_FILES
    )
    if extra:
        errors.append(f"unexpected source files: {', '.join(extra)}")
    pipeline = (source_root / "01-pipeline.txt").read_text(encoding="utf-8").casefold()
    if "do not spawn a router agent" not in pipeline:
        errors.append("pipeline must refuse a router agent")
    scale = (source_root / "03-scale.txt").read_text(encoding="utf-8").casefold()
    if "work-graph width" not in scale:
        errors.append("scale doctrine must use work-graph width")

    for host in ("openai.yaml", "grok.yaml", "claude.yaml"):
        host_path = root / "agents" / host
        if not host_path.is_file():
            errors.append(f"missing agents/{host}")
            continue
        host_text = host_path.read_text(encoding="utf-8")
        if "$marketing-os" not in host_text:
            errors.append(f"agents/{host} must invoke the skill")
        if "allow_implicit_invocation: false" not in host_text:
            errors.append(f"agents/{host} must disable implicit invocation")

    template_path = root / "assets" / "spawn-template.json"
    if not template_path.is_file():
        errors.append("missing spawn template")
    else:
        try:
            payload = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append("spawn template is unreadable JSON")
        else:
            errors.extend(validate_spawn_template(payload))

    examples = root / "assets" / "examples"
    validators = {
        "audience-profile.json": validate_audience_profile,
        "research-report.json": validate_research_report,
        "campaign-brief.json": validate_campaign_brief,
        "copy-packet.json": validate_copy_packet,
    }
    loaded: dict[str, Any] = {}
    for name, validator in validators.items():
        path = examples / name
        if not path.is_file():
            errors.append(f"missing example {name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"example {name} is unreadable JSON")
            continue
        errors.extend(validator(payload))
        loaded[name] = payload
        schema_path = root / "schemas" / name.replace(".json", ".schema.json")
        if not schema_path.is_file():
            errors.append(f"missing schema for {name}")
        else:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            expected = ARTIFACT_SCHEMAS[name.replace(".json", "")]
            if schema.get("$id") != expected:
                errors.append(f"{schema_path.name} $id drifted")

    if "audience-profile.json" in loaded and "campaign-brief.json" in loaded:
        expected = digest_bytes(canonical_bytes(loaded["audience-profile.json"]))
        actual = loaded["campaign-brief.json"].get("audience_profile_digest")
        if actual != expected:
            errors.append("campaign-brief audience_profile_digest does not match the example profile")
    if "campaign-brief.json" in loaded and "copy-packet.json" in loaded:
        expected = digest_bytes(canonical_bytes(loaded["campaign-brief.json"]))
        actual = loaded["copy-packet.json"].get("brief_digest")
        if actual != expected:
            errors.append("copy-packet brief_digest does not match the example brief")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_pack(args.root)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
