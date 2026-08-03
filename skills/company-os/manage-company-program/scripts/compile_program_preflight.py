#!/usr/bin/env python3
"""Compile and verify deterministic Company OS program preflight packets.

The compiler deliberately uses only the Python standard library.  Its input
documents are versioned JSON contracts, and its output is canonical JSON: no
timestamps, random identifiers, environment discovery, or host iteration
order are included in the binding.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
MANIFEST_SCHEMA_ID = "company-os.compiled-preflight.v1"
PACKET_ALGORITHM = "sha256(canonical-json-with-binding-canonical_sha256-null)"
INPUT_NAMES = ("program_semantics", "host_capabilities", "work_definitions")
SCHEMA_FILES = {
    "program_semantics": "program-semantics.schema.json",
    "host_capabilities": "host-capabilities.schema.json",
    "work_definitions": "work-definitions.schema.json",
}
SCHEMA_IDS = {
    "program_semantics": "company-os.program-semantics.v1",
    "host_capabilities": "company-os.host-capabilities.v1",
    "work_definitions": "company-os.work-definitions.v1",
}
PATH_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*[a-z0-9]$|^[a-z0-9]$")
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
LOCATOR_RE = re.compile(
    r"^(?:runtime|tool|module|workspace)://[a-z0-9][a-z0-9._/-]*$"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_CONSTANT_TYPES = {"integer", "string", "boolean"}
LIST_SORT_KEYS = (
    "term_id",
    "constant_id",
    "state_id",
    "prohibition_id",
    "evidence_id",
    "oracle_id",
    "capability_id",
    "runtime_id",
    "manager_id",
    "work_id",
    "deliverable_id",
    "source_id",
    "citation_id",
)


class PreflightError(ValueError):
    """Stable, readable compiler/verifier failure."""

    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        self.code = code
        self.message = message
        self.path = path
        suffix = f" at {path}" if path else ""
        super().__init__(f"{code}: {message}{suffix}")


class _SchemaError(PreflightError):
    pass


def canonical_bytes(value: Any) -> bytes:
    """Return the one canonical JSON representation used for every digest."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PreflightError("E_CANONICAL_JSON", f"value is not canonical JSON: {exc}") from exc
    return encoded.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _canonical_sort_key(value: Any) -> bytes:
    return canonical_bytes(value)


def _normalize_for_input_digest(value: Any) -> Any:
    """Normalize unordered contract collections before hashing them.

    Contract arrays are sets of named records or sets of scalar references.
    Sorting them here means host/authoring order cannot become an output field.
    """

    if isinstance(value, dict):
        return {
            key: _normalize_for_input_digest(value[key])
            for key in sorted(value)
        }
    if isinstance(value, list):
        normalized = [_normalize_for_input_digest(item) for item in value]
        if all(isinstance(item, (str, int, float, bool)) or item is None for item in normalized):
            return sorted(normalized, key=_canonical_sort_key)
        if all(isinstance(item, dict) for item in normalized) and normalized:
            for sort_key in LIST_SORT_KEYS:
                if all(sort_key in item for item in normalized):
                    return sorted(normalized, key=lambda item: str(item[sort_key]))
        return normalized
    return value


def _canonical_input_digest(value: Any) -> str:
    return canonical_digest(_normalize_for_input_digest(value))


def _path_text(path: Sequence[object]) -> str:
    rendered = "$"
    for item in path:
        if isinstance(item, int):
            rendered += f"[{item}]"
        else:
            rendered += f".{item}"
    return rendered


def _schema_error_code(path: str, message: str) -> str:
    lowered = f"{path} {message}".lower()
    if "owned_paths" in lowered or ".path" in lowered:
        return "E_SCOPE_PATH"
    if "locator" in lowered:
        return "E_LOCATOR_INVALID"
    if "citation" in lowered or "evidence" in lowered:
        return "E_EVIDENCE_CLOSURE"
    if "oracle" in lowered:
        return "E_MISSING_ORACLE"
    if ".type" in path.lower() or lowered.endswith(".type") or " type " in lowered:
        return "E_UNSUPPORTED_TYPE"
    if "unknown key" in lowered or "additional propert" in lowered:
        return "E_SCHEMA_UNKNOWN_KEY"
    return "E_SCHEMA"


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _validate_schema(value: Any, schema: Mapping[str, Any], path: Sequence[object] = ()) -> None:
    """Small strict JSON-Schema subset used by the bundled schemas."""

    current = _path_text(path)
    if "const" in schema and value != schema["const"]:
        message = f"must equal {schema['const']!r}"
        raise _SchemaError(_schema_error_code(current, message), message, current)
    if "enum" in schema and value not in schema["enum"]:
        message = f"must be one of {schema['enum']!r}"
        raise _SchemaError(_schema_error_code(current, message), message, current)

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, item) for item in types):
            message = f"has unsupported JSON type; expected {types!r}"
            raise _SchemaError(_schema_error_code(current, message), message, current)

    if "oneOf" in schema:
        successes = 0
        for option in schema["oneOf"]:
            try:
                _validate_schema(value, option, path)
            except PreflightError:
                continue
            successes += 1
        if successes != 1:
            message = "must match exactly one supported schema alternative"
            raise _SchemaError(_schema_error_code(current, message), message, current)
    if "anyOf" in schema:
        if not any(_schema_accepts(value, option, path) for option in schema["anyOf"]):
            message = "must match a supported schema alternative"
            raise _SchemaError(_schema_error_code(current, message), message, current)

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            message = f"missing required key(s): {', '.join(missing)}"
            raise _SchemaError(_schema_error_code(current, message), message, current)
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                message = f"unknown key(s): {', '.join(unknown)}"
                raise _SchemaError("E_SCHEMA_UNKNOWN_KEY", message, current)
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                _validate_schema(item, child_schema, (*path, key))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            message = f"must contain at least {schema['minItems']} item(s)"
            raise _SchemaError(_schema_error_code(current, message), message, current)
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            message = f"must contain no more than {schema['maxItems']} item(s)"
            raise _SchemaError(_schema_error_code(current, message), message, current)
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_schema(item, item_schema, (*path, index))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            message = f"must contain at least {schema['minLength']} character(s)"
            raise _SchemaError(_schema_error_code(current, message), message, current)
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            message = f"does not match required pattern {schema['pattern']!r}"
            raise _SchemaError(_schema_error_code(current, message), message, current)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            message = f"must be at least {schema['minimum']}"
            raise _SchemaError(_schema_error_code(current, message), message, current)


def _schema_accepts(value: Any, schema: Mapping[str, Any], path: Sequence[object]) -> bool:
    try:
        _validate_schema(value, schema, path)
    except PreflightError:
        return False
    return True


def _expand_schema_refs(node: Any, root: Mapping[str, Any]) -> Any:
    """Expand the local JSON-Schema refs used by the input assets."""

    if isinstance(node, list):
        return [_expand_schema_refs(item, root) for item in node]
    if not isinstance(node, dict):
        return node
    reference = node.get("$ref")
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/"):
            raise PreflightError("E_SCHEMA_ASSET", f"unsupported schema reference {reference!r}")
        target: Any = root
        for part in reference[2:].split("/"):
            if not isinstance(target, dict) or part not in target:
                raise PreflightError("E_SCHEMA_ASSET", f"unresolved schema reference {reference!r}")
            target = target[part]
        return _expand_schema_refs(target, root)
    return {key: _expand_schema_refs(item, root) for key, item in node.items()}


def _load_schema(kind: str) -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / SCHEMA_FILES[kind]
    try:
        value = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError("E_SCHEMA_ASSET", f"cannot load {schema_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError("E_SCHEMA_ASSET", f"schema asset is not an object: {schema_path}")
    return _expand_schema_refs(value, value)


def _read_json(path: Path, kind: str) -> dict[str, Any]:
    schema_kind = {
        "program semantics": "program_semantics",
        "host capabilities": "host_capabilities",
        "work definitions": "work_definitions",
    }.get(kind, kind)
    if schema_kind not in SCHEMA_FILES:
        raise PreflightError("E_SCHEMA_ASSET", f"unsupported input kind {kind!r}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PreflightError("E_INPUT_READ", f"cannot read {kind} input {path}: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError("E_INPUT_JSON", f"invalid {kind} JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError("E_SCHEMA_TYPE", f"{kind} input must be a JSON object")
    _validate_schema(value, _load_schema(schema_kind))
    return value


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or ID_RE.fullmatch(value) is None:
        raise PreflightError("E_SCHEMA_TYPE", f"{label} must be a canonical lowercase identifier")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreflightError("E_SCHEMA_TYPE", f"{label} must be a non-empty string")
    return value


def _alias_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize_artifact_text(value: str) -> bytes:
    """The normalized-nonempty oracle's byte normalization."""

    return unicodedata.normalize("NFC", value).strip().encode("utf-8")


def _validate_path(value: str, label: str) -> None:
    if (
        not isinstance(value, str)
        or PATH_RE.fullmatch(value) is None
        or value.startswith("/")
        or value.startswith("./")
        or value.endswith("/")
        or "//" in value
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or value != value.lower()
    ):
        raise PreflightError(
            "E_SCOPE_PATH",
            f"{label} must be an exact lowercase project-relative POSIX path",
        )


def _validate_locator(value: Any, label: str) -> str:
    if not isinstance(value, str) or LOCATOR_RE.fullmatch(value) is None:
        raise PreflightError(
            "E_LOCATOR_INVALID",
            f"{label} must be an explicit runtime/tool locator",
        )
    return value


def _index_unique(items: Iterable[Mapping[str, Any]], key: str, label: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in items:
        item_id = _require_id(item.get(key), f"{label}.{key}")
        if item_id in indexed:
            raise PreflightError("E_DUPLICATE_CONCEPT", f"duplicate {label} id {item_id!r}")
        indexed[item_id] = item
    return indexed


def _check_duplicate_labels(items: Mapping[str, Mapping[str, Any]], label: str) -> None:
    labels: dict[str, str] = {}
    for item_id, item in items.items():
        item_label = item.get("label")
        if not isinstance(item_label, str):
            continue
        normalized = _alias_key(item_label)
        if normalized in labels and labels[normalized] != item_id:
            raise PreflightError(
                "E_CONFLICTING_CONCEPT",
                f"{label} labels {labels[normalized]!r} and {item_id!r} conflict",
            )
        labels[normalized] = item_id


def _resolve_terms(
    values: Sequence[str],
    terms: Mapping[str, Mapping[str, Any]],
    aliases: Mapping[str, str],
    prohibited: Mapping[str, str],
    owner: str,
) -> list[str]:
    resolved: list[str] = []
    for raw in values:
        key = _alias_key(raw)
        if key in prohibited:
            raise PreflightError(
                "E_TERMINOLOGY_DRIFT",
                f"{owner} uses prohibited terminology {raw!r}; canonical term is {prohibited[key]!r}",
            )
        term_id = aliases.get(key)
        if term_id is None:
            raise PreflightError("E_UNKNOWN_ALIAS", f"{owner} uses unknown term alias {raw!r}")
        if term_id not in terms:
            raise PreflightError("E_UNKNOWN_ALIAS", f"{owner} resolves to unknown term {term_id!r}")
        if term_id not in resolved:
            resolved.append(term_id)
    return sorted(resolved)


def _typed_value_matches(declared: Any, value: Any) -> bool:
    return (
        (declared == "integer" and isinstance(value, int) and not isinstance(value, bool))
        or (declared == "string" and isinstance(value, str))
        or (declared == "boolean" and isinstance(value, bool))
    )


def _check_constant_type(constant: Mapping[str, Any]) -> None:
    constant_id = str(constant.get("constant_id"))
    declared = constant.get("type")
    if declared not in SUPPORTED_CONSTANT_TYPES:
        raise PreflightError(
            "E_UNSUPPORTED_TYPE",
            f"constant {constant_id!r} declares unsupported type {declared!r}",
        )
    value = constant.get("value")
    valid = _typed_value_matches(declared, value)
    if not valid:
        raise PreflightError(
            "E_SCHEMA_TYPE",
            f"constant {constant_id!r} value does not match declared type {declared!r}",
        )


def _check_scope(scope: Mapping[str, Any], owner: str) -> list[str]:
    paths = scope.get("owned_paths")
    if not isinstance(paths, list) or not paths:
        raise PreflightError("E_SCOPE_PATH", f"{owner} must declare owned_paths")
    checked: list[str] = []
    for path in paths:
        _validate_path(path, f"{owner}.owned_paths")
        if path in checked:
            raise PreflightError("E_SCOPE_OVERLAP", f"{owner} repeats owned path {path!r}")
        checked.append(path)
    for index, left in enumerate(checked):
        for right in checked[index + 1 :]:
            if _paths_overlap(left, right):
                raise PreflightError(
                    "E_SCOPE_OVERLAP",
                    f"{owner} contains overlapping/ancestor paths {left!r} and {right!r}",
                )
    return sorted(checked)


def _paths_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _path_in_scope(path: str, scope: Sequence[str]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in scope)


def _validate_host(
    host: Mapping[str, Any], required_capability_ids: Sequence[str]
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    runtimes = _index_unique(host["runtimes"], "runtime_id", "runtime")
    capabilities = _index_unique(host["capabilities"], "capability_id", "capability")
    for runtime_id, runtime in runtimes.items():
        if not runtime["available"]:
            continue
        _validate_locator(runtime.get("locator"), f"runtime {runtime_id}.locator")
    for capability_id, capability in capabilities.items():
        runtime_id = _require_id(capability.get("runtime_id"), f"capability {capability_id}.runtime_id")
        tool_locator = _validate_locator(
            capability.get("tool_locator"), f"capability {capability_id}.tool_locator"
        )
        runtime_locator = _validate_locator(
            capability.get("runtime_locator"), f"capability {capability_id}.runtime_locator"
        )
        runtime = runtimes.get(runtime_id)
        if runtime is None:
            raise PreflightError(
                "E_LOCATOR_INVALID",
                f"capability {capability_id!r} references missing runtime {runtime_id!r}",
            )
        if runtime_locator != runtime.get("locator"):
            raise PreflightError(
                "E_LOCATOR_INVALID",
                f"capability {capability_id!r} runtime locator does not bind to {runtime_id!r}",
            )
        if capability["available"] is not True or runtime["available"] is not True:
            if capability_id in required_capability_ids:
                raise PreflightError(
                    "E_CAPABILITY_UNAVAILABLE",
                    f"required capability {capability_id!r} or runtime {runtime_id!r} is unavailable",
                )
        # Keep this local assignment explicit: tool_locator is validated even
        # when the capability is unavailable, preventing fallback discovery.
        _ = tool_locator
    for capability_id in required_capability_ids:
        capability = capabilities.get(capability_id)
        if capability is None:
            raise PreflightError(
                "E_CAPABILITY_UNAVAILABLE",
                f"required capability {capability_id!r} is absent from the host manifest",
            )
        runtime = runtimes.get(capability["runtime_id"])
        if capability["available"] is not True or runtime is None or runtime["available"] is not True:
            raise PreflightError(
                "E_CAPABILITY_UNAVAILABLE",
                f"required capability {capability_id!r} is unavailable",
            )
    return capabilities, runtimes


def _validate_cross_bindings(
    semantics: Mapping[str, Any],
    definitions: Mapping[str, Any],
    terms: Mapping[str, Mapping[str, Any]],
    constants: Mapping[str, Mapping[str, Any]],
) -> None:
    constant_bindings = _index_unique(
        definitions["constant_bindings"], "constant_id", "constant binding"
    )
    if set(constant_bindings) != set(constants):
        missing = sorted(set(constants) - set(constant_bindings))
        extra = sorted(set(constant_bindings) - set(constants))
        raise PreflightError(
            "E_CONSTANT_DRIFT",
            f"constant binding closure mismatch; missing={missing!r}, extra={extra!r}",
        )
    for constant_id, binding in constant_bindings.items():
        constant = constants.get(constant_id)
        if constant is None:
            raise PreflightError("E_CONSTANT_DRIFT", f"binding references unknown constant {constant_id!r}")
        if (
            binding["expected_type"] != constant["type"]
            or not _typed_value_matches(binding["expected_type"], binding["expected_value"])
            or binding["expected_value"] != constant["value"]
            or binding["expected_unit"] != constant["unit"]
            or binding["expected_row_map"] != constant["row_map"]
        ):
            raise PreflightError(
                "E_CONSTANT_DRIFT",
                f"constant {constant_id!r} differs from its canonical type/value/unit/row-map binding",
            )

    term_bindings = _index_unique(definitions["term_bindings"], "term_id", "term binding")
    if set(term_bindings) != set(terms):
        missing = sorted(set(terms) - set(term_bindings))
        extra = sorted(set(term_bindings) - set(terms))
        raise PreflightError(
            "E_TERMINOLOGY_DRIFT",
            f"term binding closure mismatch; missing={missing!r}, extra={extra!r}",
        )
    for term_id, binding in term_bindings.items():
        term = terms.get(term_id)
        if term is None or binding["expected_label"] != term["label"]:
            raise PreflightError(
                "E_TERMINOLOGY_DRIFT",
                f"term {term_id!r} does not retain its canonical label",
            )
        if sorted(map(_alias_key, binding["required_aliases"])) != sorted(
            map(_alias_key, term["aliases"])
        ) or sorted(map(_alias_key, binding["prohibited_aliases"])) != sorted(
            map(_alias_key, term["prohibited_aliases"])
        ):
            raise PreflightError(
                "E_TERMINOLOGY_DRIFT",
                f"term {term_id!r} alias/prohibition binding drifted",
            )


def _build_term_indexes(
    terms: Mapping[str, Mapping[str, Any]]
) -> tuple[dict[str, str], dict[str, str]]:
    aliases: dict[str, str] = {}
    prohibited: dict[str, str] = {}
    for term_id, term in terms.items():
        values = [term["label"], *term["aliases"]]
        local: set[str] = set()
        for raw in values:
            key = _alias_key(raw)
            if not key:
                raise PreflightError("E_CONFLICTING_CONCEPT", f"term {term_id!r} has an empty alias")
            if key in local:
                raise PreflightError(
                    "E_CONFLICTING_CONCEPT",
                    f"term {term_id!r} repeats alias/label {raw!r}",
                )
            local.add(key)
            prior = aliases.get(key)
            if prior is not None and prior != term_id:
                raise PreflightError(
                    "E_ALIAS_COLLISION",
                    f"alias {raw!r} maps to both {prior!r} and {term_id!r}",
                )
            aliases[key] = term_id
        for raw in term["prohibited_aliases"]:
            key = _alias_key(raw)
            if key in aliases:
                raise PreflightError(
                    "E_ALIAS_COLLISION",
                    f"prohibited alias {raw!r} is also an allowed alias",
                )
            prior = prohibited.get(key)
            if prior is not None and prior != term_id:
                raise PreflightError(
                    "E_ALIAS_COLLISION",
                    f"prohibited alias {raw!r} maps to both {prior!r} and {term_id!r}",
                )
            prohibited[key] = term_id
    for term_id in terms:
        key = _alias_key(term_id)
        if key in prohibited:
            raise PreflightError(
                "E_ALIAS_COLLISION",
                f"term id {term_id!r} collides with a prohibited alias",
            )
        if key in aliases and aliases[key] != term_id:
            raise PreflightError(
                "E_ALIAS_COLLISION",
                f"term id {term_id!r} collides with another term alias",
            )
        aliases[key] = term_id
    return aliases, prohibited


def _reject_prohibited_text(
    value: str,
    prohibited: Mapping[str, str],
    owner: str,
) -> None:
    """Reject canonical terminology drift in authored decision text.

    Citation excerpts and prohibition definitions are deliberately excluded:
    they may need to quote the external or forbidden wording verbatim.  Labels,
    claims, and oracle probes are authored dispatch instructions and therefore
    must preserve the program's canonical vocabulary.
    """

    normalized = unicodedata.normalize("NFKC", value).casefold()
    for alias, term_id in prohibited.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
            raise PreflightError(
                "E_TERMINOLOGY_DRIFT",
                f"{owner} uses prohibited terminology {alias!r}; canonical term is {term_id!r}",
            )


def _validate_prohibition_applicability(
    prohibition_ids: Sequence[str],
    prohibitions: Mapping[str, Mapping[str, Any]],
    role: str,
    owner: str,
) -> None:
    for prohibition_id in prohibition_ids:
        applies_to = prohibitions[prohibition_id]["applies_to"]
        if "both" not in applies_to and role not in applies_to:
            raise PreflightError(
                "E_AUTHORITY",
                f"{owner} uses prohibition {prohibition_id!r} that does not apply to {role}",
            )


def _resolve_refs(values: Sequence[str], indexed: Mapping[str, Mapping[str, Any]], owner: str) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in indexed:
            raise PreflightError("E_UNKNOWN_REFERENCE", f"{owner} references unknown id {value!r}")
        if value in result:
            raise PreflightError("E_DUPLICATE_CONCEPT", f"{owner} repeats reference {value!r}")
        result.append(value)
    return sorted(result)


def _validate_oracle_probe(oracle: Mapping[str, Any], probe: str, owner: str) -> None:
    if oracle["rule"] == "normalized-nonempty" and not normalize_artifact_text(probe):
        raise PreflightError(
            "E_ORACLE_EMPTY",
            f"{owner} has whitespace-only output under normalized-nonempty oracle",
        )


def _validate_definitions(
    semantics: Mapping[str, Any],
    definitions: Mapping[str, Any],
    terms: Mapping[str, Mapping[str, Any]],
    constants: Mapping[str, Mapping[str, Any]],
    states: Mapping[str, Mapping[str, Any]],
    prohibitions: Mapping[str, Mapping[str, Any]],
    evidence_requirements: Mapping[str, Mapping[str, Any]],
    evidence_units: Mapping[str, Mapping[str, Any]],
    oracles: Mapping[str, Mapping[str, Any]],
    capabilities: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
    aliases, prohibited_aliases = _build_term_indexes(terms)
    _check_duplicate_labels(terms, "term")
    _check_duplicate_labels(constants, "constant")
    _validate_cross_bindings(semantics, definitions, terms, constants)
    _reject_prohibited_text(semantics["program_label"], prohibited_aliases, "program label")
    for constant_id, constant in constants.items():
        _reject_prohibited_text(constant["label"], prohibited_aliases, f"constant {constant_id} label")
    for state_id, state in states.items():
        _reject_prohibited_text(state["label"], prohibited_aliases, f"authority state {state_id} label")
    for evidence_id, requirement in evidence_requirements.items():
        _reject_prohibited_text(
            requirement["claim"], prohibited_aliases, f"evidence requirement {evidence_id} claim"
        )
    for evidence_id, unit in evidence_units.items():
        _reject_prohibited_text(unit["claim"], prohibited_aliases, f"evidence unit {evidence_id} claim")
    for oracle_id, oracle in oracles.items():
        _reject_prohibited_text(oracle["label"], prohibited_aliases, f"oracle {oracle_id} label")

    all_scopes: list[tuple[str, str]] = []
    all_deliverable_ids: set[str] = set()
    all_deliverable_paths: set[str] = set()
    referenced_evidence: set[str] = set()
    referenced_oracles: set[str] = set()
    managers = _index_unique(definitions["manager_definitions"], "manager_id", "manager")
    works = _index_unique(definitions["work_definitions"], "work_id", "work")
    actual_worker_ids: dict[str, list[str]] = {manager_id: [] for manager_id in managers}

    manager_packets: list[dict[str, Any]] = []
    for manager_id, manager in sorted(managers.items()):
        scope = _check_scope(manager["scope"], f"manager {manager_id}")
        all_scopes.extend((manager_id, path) for path in scope)
        state_id = manager["authority_state"]
        state = states.get(state_id)
        if state is None:
            raise PreflightError("E_UNKNOWN_REFERENCE", f"manager {manager_id!r} references unknown authority state")
        if state["kind"] != "manager":
            raise PreflightError("E_AUTHORITY", f"manager {manager_id!r} must use a manager authority state")
        prohibition_ids = _resolve_refs(manager["prohibition_ids"], prohibitions, f"manager {manager_id}")
        _validate_prohibition_applicability(
            prohibition_ids, prohibitions, "manager", f"manager {manager_id}"
        )
        cap_ids = _resolve_refs(manager["required_capabilities"], capabilities, f"manager {manager_id}")
        term_ids = _resolve_terms(
            manager["required_terms"], terms, aliases, prohibited_aliases, f"manager {manager_id}"
        )
        _reject_prohibited_text(manager["label"], prohibited_aliases, f"manager {manager_id} label")
        deliverables = _validate_deliverables(
            manager["deliverables"],
            f"manager {manager_id}",
            scope,
            oracles,
            evidence_requirements,
            evidence_units,
            constants,
            terms,
            aliases,
            prohibited_aliases,
            term_ids,
            all_deliverable_ids,
            all_deliverable_paths,
            referenced_evidence,
            referenced_oracles,
        )
        manager_packets.append(
            {
                "manager_id": manager_id,
                "label": manager["label"],
                "department_id": manager["department_id"],
                "scope": {"owned_paths": scope},
                "authority_state_id": state_id,
                "prohibition_ids": prohibition_ids,
                "required_capability_ids": cap_ids,
                "required_term_ids": term_ids,
                "deliverables": deliverables,
                "worker_ids": sorted(manager["worker_ids"]),
            }
        )

    manager_packet_by_id = {item["manager_id"]: item for item in manager_packets}

    work_packets: list[dict[str, Any]] = []
    for work_id, work in sorted(works.items()):
        manager_id = work["manager_id"]
        if manager_id not in managers:
            raise PreflightError("E_UNKNOWN_REFERENCE", f"work {work_id!r} references unknown manager {manager_id!r}")
        actual_worker_ids[manager_id].append(work_id)
        scope = _check_scope(work["scope"], f"work {work_id}")
        all_scopes.extend((work_id, path) for path in scope)
        state_id = work["authority_state"]
        state = states.get(state_id)
        if state is None:
            raise PreflightError("E_UNKNOWN_REFERENCE", f"work {work_id!r} references unknown authority state")
        if state["kind"] != "worker":
            raise PreflightError("E_AUTHORITY", f"work {work_id!r} must use a worker authority state")
        manager_state = states[managers[manager_id]["authority_state"]]
        if not state["delegable"] or state["state_id"] not in manager_state["delegated_states"]:
            raise PreflightError(
                "E_AUTHORITY",
                f"work {work_id!r} uses a worker authority state not delegated by manager {manager_id!r}",
            )
        prohibition_ids = _resolve_refs(work["prohibition_ids"], prohibitions, f"work {work_id}")
        _validate_prohibition_applicability(
            prohibition_ids, prohibitions, "worker", f"work {work_id}"
        )
        cap_ids = _resolve_refs(work["required_capabilities"], capabilities, f"work {work_id}")
        parent_packet = manager_packet_by_id[manager_id]
        missing_parent_prohibitions = sorted(
            set(parent_packet["prohibition_ids"]) - set(prohibition_ids)
        )
        if missing_parent_prohibitions:
            raise PreflightError(
                "E_AUTHORITY",
                f"work {work_id!r} drops parent prohibitions {missing_parent_prohibitions!r}",
            )
        widened_capabilities = sorted(
            set(cap_ids) - set(parent_packet["required_capability_ids"])
        )
        if widened_capabilities:
            raise PreflightError(
                "E_AUTHORITY",
                f"work {work_id!r} widens parent capabilities {widened_capabilities!r}",
            )
        term_ids = _resolve_terms(
            work["required_terms"], terms, aliases, prohibited_aliases, f"work {work_id}"
        )
        _reject_prohibited_text(work["label"], prohibited_aliases, f"work {work_id} label")
        deliverables = _validate_deliverables(
            work["deliverables"],
            f"work {work_id}",
            scope,
            oracles,
            evidence_requirements,
            evidence_units,
            constants,
            terms,
            aliases,
            prohibited_aliases,
            term_ids,
            all_deliverable_ids,
            all_deliverable_paths,
            referenced_evidence,
            referenced_oracles,
        )
        work_packets.append(
            {
                "work_id": work_id,
                "manager_id": manager_id,
                "label": work["label"],
                "scope": {"owned_paths": scope},
                "authority_state_id": state_id,
                "prohibition_ids": prohibition_ids,
                "required_capability_ids": cap_ids,
                "required_term_ids": term_ids,
                "deliverables": deliverables,
            }
        )

    for index, (left_owner, left_path) in enumerate(all_scopes):
        for right_owner, right_path in all_scopes[index + 1 :]:
            if _paths_overlap(left_path, right_path):
                raise PreflightError(
                    "E_SCOPE_OVERLAP",
                    f"writer scopes {left_owner!r}:{left_path!r} and {right_owner!r}:{right_path!r} overlap or have an ancestor",
                )

    for manager_id, manager in managers.items():
        expected = sorted(actual_worker_ids[manager_id])
        declared = sorted(manager["worker_ids"])
        if expected != declared:
            raise PreflightError(
                "E_WORKER_CLOSURE",
                f"manager {manager_id!r} worker_ids do not exactly close over work definitions",
            )

    missing_evidence = sorted(
        evidence_id
        for evidence_id, requirement in evidence_requirements.items()
        if requirement["required"] and evidence_id not in referenced_evidence
    )
    if missing_evidence:
        raise PreflightError(
            "E_EVIDENCE_CLOSURE",
            f"required evidence is not attached to any deliverable: {missing_evidence!r}",
        )
    missing_oracles = sorted(
        oracle_id
        for oracle_id, oracle in oracles.items()
        if oracle["required"] and oracle_id not in referenced_oracles
    )
    if missing_oracles:
        raise PreflightError(
            "E_MISSING_ORACLE",
            f"required artifact oracle is not attached to any deliverable: {missing_oracles!r}",
        )
    return manager_packets, work_packets, actual_worker_ids


def _validate_deliverables(
    deliverables: Sequence[Mapping[str, Any]],
    owner: str,
    scope: Sequence[str],
    oracles: Mapping[str, Mapping[str, Any]],
    evidence_requirements: Mapping[str, Mapping[str, Any]],
    evidence_units: Mapping[str, Mapping[str, Any]],
    constants: Mapping[str, Mapping[str, Any]],
    terms: Mapping[str, Mapping[str, Any]],
    aliases: Mapping[str, str],
    prohibited_aliases: Mapping[str, str],
    inherited_term_ids: Sequence[str],
    all_deliverable_ids: set[str],
    all_deliverable_paths: set[str],
    referenced_evidence: set[str],
    referenced_oracles: set[str],
) -> list[dict[str, Any]]:
    if not deliverables:
        raise PreflightError("E_DUPLICATE_DELIVERABLE", f"{owner} must declare at least one deliverable")
    normalized: list[dict[str, Any]] = []
    for item in sorted(deliverables, key=lambda value: value["deliverable_id"]):
        deliverable_id = item["deliverable_id"]
        _reject_prohibited_text(
            item["label"], prohibited_aliases, f"{owner}.{deliverable_id}.label"
        )
        _reject_prohibited_text(
            item["oracle_probe"], prohibited_aliases, f"{owner}.{deliverable_id}.oracle_probe"
        )
        if deliverable_id in all_deliverable_ids:
            raise PreflightError("E_DUPLICATE_DELIVERABLE", f"duplicate deliverable id {deliverable_id!r}")
        all_deliverable_ids.add(deliverable_id)
        path = item["path"]
        _validate_path(path, f"{owner}.{deliverable_id}.path")
        if path in all_deliverable_paths:
            raise PreflightError("E_DUPLICATE_DELIVERABLE", f"duplicate deliverable path {path!r}")
        all_deliverable_paths.add(path)
        if not _path_in_scope(path, scope):
            raise PreflightError(
                "E_SCOPE_PATH",
                f"deliverable {deliverable_id!r} path {path!r} escapes {owner} writer scope",
            )
        oracle_id = item["oracle_id"]
        oracle = oracles.get(oracle_id)
        if oracle is None:
            raise PreflightError(
                "E_MISSING_ORACLE",
                f"deliverable {deliverable_id!r} references missing oracle {oracle_id!r}",
            )
        referenced_oracles.add(oracle_id)
        _validate_oracle_probe(oracle, item["oracle_probe"], f"{owner}.{deliverable_id}")
        evidence_ids = _resolve_refs(item["evidence_ids"], evidence_units, f"deliverable {deliverable_id}")
        if not evidence_ids:
            raise PreflightError(
                "E_EVIDENCE_CLOSURE",
                f"deliverable {deliverable_id!r} must cite at least one evidence unit",
            )
        for evidence_id in evidence_ids:
            requirement = evidence_requirements.get(evidence_id)
            if requirement is None:
                raise PreflightError(
                    "E_EVIDENCE_CLOSURE",
                    f"deliverable {deliverable_id!r} references evidence without a requirement: {evidence_id!r}",
                )
            unit = evidence_units[evidence_id]
            if requirement["required"] and requirement["citation_required"]:
                citations = unit.get("citations")
                if not isinstance(citations, list) or len(citations) < requirement["minimum_citations"]:
                    raise PreflightError(
                        "E_EVIDENCE_CLOSURE",
                        f"evidence unit {evidence_id!r} lacks its required citation closure",
                    )
                for citation in citations:
                    if not citation.get("source_id", "").strip() or not citation.get("locator", "").strip() or not citation.get("excerpt", "").strip():
                        raise PreflightError(
                            "E_EVIDENCE_CLOSURE",
                            f"evidence unit {evidence_id!r} contains an uncited/empty citation",
                        )
            referenced_evidence.add(evidence_id)
        constant_ids = _resolve_refs(item["constant_ids"], constants, f"deliverable {deliverable_id}")
        item_term_ids: list[str] = []
        for raw_term in item["term_ids"]:
            if raw_term in terms:
                item_term_ids.append(raw_term)
            else:
                item_term_ids.extend(
                    _resolve_terms(
                        [raw_term],
                        terms,
                        aliases,
                        prohibited_aliases,
                        f"deliverable {deliverable_id}",
                    )
                )
        term_ids = sorted(set(inherited_term_ids) | set(item_term_ids))
        normalized.append(
            {
                "deliverable_id": deliverable_id,
                "label": item["label"],
                "path": path,
                "artifact_kind": item["artifact_kind"],
                "oracle_id": oracle_id,
                "oracle_probe": item["oracle_probe"],
                "evidence_ids": evidence_ids,
                "constant_ids": constant_ids,
                "term_ids": term_ids,
            }
        )
    return normalized


def _required_capabilities(semantics: Mapping[str, Any], definitions: Mapping[str, Any]) -> list[str]:
    values = [
        item["capability_id"]
        for item in semantics["required_capabilities"]
        if item["required"]
    ]
    for definition_key, id_key in (("manager_definitions", "manager_id"), ("work_definitions", "work_id")):
        for item in definitions[definition_key]:
            values.extend(item["required_capabilities"])
    return sorted(set(values))


def _source_bindings(documents: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for name in INPUT_NAMES:
        document = documents[name]
        result.append(
            {
                "name": name,
                "schema_id": document["$id"],
                "schema_version": document["schema_version"],
                "sha256": _canonical_input_digest(document),
            }
        )
    return result


def _resolve_semantic_object(indexed: Mapping[str, Mapping[str, Any]], ids: Sequence[str]) -> list[dict[str, Any]]:
    return [copy.deepcopy(indexed[item_id]) for item_id in sorted(set(ids))]


def _packet_semantic_slice(
    normalized: Mapping[str, Any],
    semantics: Mapping[str, Any],
    states: Mapping[str, Mapping[str, Any]],
    prohibitions: Mapping[str, Mapping[str, Any]],
    evidence_units: Mapping[str, Mapping[str, Any]],
    oracles: Mapping[str, Mapping[str, Any]],
    constants: Mapping[str, Mapping[str, Any]],
    terms: Mapping[str, Mapping[str, Any]],
    capabilities: Mapping[str, Mapping[str, Any]],
    runtimes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    deliverables = normalized["deliverables"]
    term_ids = set(normalized["required_term_ids"])
    constant_ids = set()
    evidence_ids = set()
    oracle_ids = set()
    for deliverable in deliverables:
        term_ids.update(deliverable["term_ids"])
        constant_ids.update(deliverable["constant_ids"])
        evidence_ids.update(deliverable["evidence_ids"])
        oracle_ids.add(deliverable["oracle_id"])
    authority = copy.deepcopy(states[normalized["authority_state_id"]])
    selected_prohibitions = _resolve_semantic_object(prohibitions, normalized["prohibition_ids"])
    selected_capabilities: list[dict[str, Any]] = []
    for capability_id in normalized["required_capability_ids"]:
        capability = copy.deepcopy(capabilities[capability_id])
        runtime = runtimes[capability["runtime_id"]]
        capability["runtime"] = {
            "runtime_id": runtime["runtime_id"],
            "runtime_type": runtime["runtime_type"],
            "available": runtime["available"],
            "locator": runtime["locator"],
        }
        selected_capabilities.append(capability)
    return {
        "terms": _resolve_semantic_object(terms, sorted(term_ids)),
        "constants": _resolve_semantic_object(constants, sorted(constant_ids)),
        "authority": authority,
        "prohibitions": selected_prohibitions,
        "evidence_units": _resolve_semantic_object(evidence_units, sorted(evidence_ids)),
        "artifact_oracles": _resolve_semantic_object(oracles, sorted(oracle_ids)),
        "capabilities": selected_capabilities,
    }


def _unsigned_bound(value: dict[str, Any]) -> tuple[dict[str, Any], str]:
    unsigned = copy.deepcopy(value)
    unsigned["binding"]["canonical_sha256"] = None
    return unsigned, canonical_digest(unsigned)


def _packet_filename(kind: str, packet_id: str, digest: str) -> str:
    return f"{kind}-{packet_id}-{digest[:16]}.json"


def _build_packet(
    kind: str,
    normalized: Mapping[str, Any],
    documents: Mapping[str, Mapping[str, Any]],
    input_bindings: list[dict[str, Any]],
    input_set_sha256: str,
    parent: Mapping[str, Any],
    semantic_indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[dict[str, Any], str]:
    semantics = documents["program_semantics"]
    packet_id = normalized["manager_id"] if kind == "manager" else normalized["work_id"]
    packet = {
        "$schema": "company-os.compiled-preflight.packet.v1",
        "schema_version": SCHEMA_VERSION,
        "packet_kind": kind,
        "packet_id": packet_id,
        "program": {
            "program_id": semantics["program_id"],
            "program_label": semantics["program_label"],
        },
        "input_bindings": copy.deepcopy(input_bindings),
        "input_set_sha256": input_set_sha256,
        "parent": copy.deepcopy(dict(parent)),
        "scope": copy.deepcopy(normalized["scope"]),
        "authority_state_id": normalized["authority_state_id"],
        "prohibition_ids": copy.deepcopy(normalized["prohibition_ids"]),
        "required_capability_ids": copy.deepcopy(normalized["required_capability_ids"]),
        "semantic_slice": _packet_semantic_slice(normalized, semantics, **semantic_indexes),
        "deliverables": copy.deepcopy(normalized["deliverables"]),
        "binding": {
            "algorithm": PACKET_ALGORITHM,
            "canonical_sha256": None,
        },
    }
    if kind == "manager":
        packet["worker_ids"] = copy.deepcopy(normalized["worker_ids"])
    digest = _unsigned_bound(packet)[1]
    packet["binding"]["canonical_sha256"] = digest
    return packet, digest


def _write_canonical(path: Path, value: Mapping[str, Any]) -> int:
    raw = canonical_bytes(value)
    path.write_bytes(raw)
    return len(raw)


def _ensure_empty_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        if output_dir.is_symlink() or not output_dir.is_dir():
            raise PreflightError("E_OUTPUT_DIR", f"output path is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise PreflightError("E_OUTPUT_DIR_NOT_EMPTY", f"output directory must be empty: {output_dir}")
    else:
        try:
            output_dir.mkdir(parents=True)
        except OSError as exc:
            raise PreflightError("E_OUTPUT_DIR", f"cannot create output directory {output_dir}: {exc}") from exc


def compile_program(
    semantics_path: str | Path,
    capabilities_path: str | Path,
    definitions_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Validate source contracts and compile a canonical output tree."""

    semantics = _read_json(Path(semantics_path), "program semantics")
    capabilities_doc = _read_json(Path(capabilities_path), "host capabilities")
    definitions = _read_json(Path(definitions_path), "work definitions")
    if semantics["program_id"] != capabilities_doc["program_id"] or semantics["program_id"] != definitions["program_id"]:
        raise PreflightError("E_INPUT_BINDING", "all inputs must declare the same program_id")
    if semantics["schema_version"] != SCHEMA_VERSION or capabilities_doc["schema_version"] != SCHEMA_VERSION or definitions["schema_version"] != SCHEMA_VERSION:
        raise PreflightError("E_INPUT_BINDING", "only schema version 1 is supported")

    terms = _index_unique(semantics["canonical_terms"], "term_id", "term")
    constants = _index_unique(semantics["constants"], "constant_id", "constant")
    states = _index_unique(semantics["authority_states"], "state_id", "authority state")
    prohibitions = _index_unique(semantics["prohibitions"], "prohibition_id", "prohibition")
    evidence_requirements = _index_unique(
        semantics["evidence_requirements"], "evidence_id", "evidence requirement"
    )
    oracles = _index_unique(semantics["artifact_oracles"], "oracle_id", "artifact oracle")
    _index_unique(
        semantics["required_capabilities"], "capability_id", "required capability"
    )
    required_caps = _required_capabilities(semantics, definitions)
    host_capabilities, runtimes = _validate_host(capabilities_doc, required_caps)
    evidence_units = _index_unique(definitions["evidence_units"], "evidence_id", "evidence unit")
    for constant in constants.values():
        _check_constant_type(constant)
        if constant["type"] == "integer" and constant["value"] < 0:
            raise PreflightError("E_CONSTANT_DRIFT", f"constant {constant['constant_id']!r} cannot be negative")
    row_maps: dict[str, str] = {}
    for constant_id, constant in constants.items():
        row_map = constant["row_map"]
        if row_map in row_maps and row_maps[row_map] != constant_id:
            raise PreflightError("E_CONFLICTING_CONCEPT", f"constants share budget row-map {row_map!r}")
        row_maps[row_map] = constant_id
    for state_id, state in states.items():
        if state["kind"] == "worker" and state["delegable"] is not True:
            raise PreflightError("E_AUTHORITY", f"worker authority state {state_id!r} is not delegable")
        for delegated in state["delegated_states"]:
            if delegated not in states:
                raise PreflightError("E_AUTHORITY", f"authority state {state_id!r} delegates unknown state {delegated!r}")
    for prohibition_id, prohibition in prohibitions.items():
        applies_to = prohibition["applies_to"]
        if len(applies_to) != len(set(applies_to)) or (
            "both" in applies_to and len(applies_to) != 1
        ):
            raise PreflightError(
                "E_AUTHORITY",
                f"prohibition {prohibition_id!r} has ambiguous role applicability",
            )
    for evidence_id, requirement in evidence_requirements.items():
        if requirement["required"] and evidence_id not in evidence_units:
            raise PreflightError("E_EVIDENCE_CLOSURE", f"required evidence unit {evidence_id!r} is absent")
    for evidence_id, unit in evidence_units.items():
        if not unit["claim"].strip():
            raise PreflightError("E_EVIDENCE_CLOSURE", f"evidence unit {evidence_id!r} has an empty claim")
        if not unit["citations"]:
            raise PreflightError("E_EVIDENCE_CLOSURE", f"evidence unit {evidence_id!r} is uncited")

    manager_normalized, work_normalized, _ = _validate_definitions(
        semantics,
        definitions,
        terms,
        constants,
        states,
        prohibitions,
        evidence_requirements,
        evidence_units,
        oracles,
        host_capabilities,
    )
    documents = {
        "program_semantics": semantics,
        "host_capabilities": capabilities_doc,
        "work_definitions": definitions,
    }
    input_bindings = _source_bindings(documents)
    input_set_sha256 = canonical_digest(input_bindings)
    semantic_indexes = {
        "states": states,
        "prohibitions": prohibitions,
        "evidence_units": evidence_units,
        "oracles": oracles,
        "constants": constants,
        "terms": terms,
        "capabilities": host_capabilities,
        "runtimes": runtimes,
    }
    output_dir_path = Path(output_dir)
    _ensure_empty_output_dir(output_dir_path)
    manager_dir = output_dir_path / "manager-packets"
    work_dir = output_dir_path / "work-packets"
    manager_dir.mkdir()
    work_dir.mkdir()

    manager_refs: list[dict[str, Any]] = []
    manager_digests: dict[str, str] = {}
    for normalized in manager_normalized:
        packet, digest = _build_packet(
            "manager",
            normalized,
            documents,
            input_bindings,
            input_set_sha256,
            {"kind": "program-preflight", "input_set_sha256": input_set_sha256},
            semantic_indexes,
        )
        packet_name = _packet_filename("manager", normalized["manager_id"], digest)
        packet_size = _write_canonical(manager_dir / packet_name, packet)
        if packet_size > 12 * 1024:
            raise PreflightError("E_PACKET_SIZE", f"manager packet {normalized['manager_id']!r} exceeds 12 KiB")
        manager_digests[normalized["manager_id"]] = digest
        manager_refs.append(
            {"packet_id": normalized["manager_id"], "path": f"manager-packets/{packet_name}", "sha256": digest, "size": packet_size}
        )

    work_refs: list[dict[str, Any]] = []
    for normalized in work_normalized:
        manager_id = normalized["manager_id"]
        packet, digest = _build_packet(
            "work",
            normalized,
            documents,
            input_bindings,
            input_set_sha256,
            {"kind": "manager-packet", "manager_id": manager_id, "packet_sha256": manager_digests[manager_id]},
            semantic_indexes,
        )
        packet_name = _packet_filename("work", normalized["work_id"], digest)
        packet_size = _write_canonical(work_dir / packet_name, packet)
        if packet_size > 12 * 1024:
            raise PreflightError("E_PACKET_SIZE", f"work packet {normalized['work_id']!r} exceeds 12 KiB")
        work_refs.append(
            {"packet_id": normalized["work_id"], "path": f"work-packets/{packet_name}", "sha256": digest, "size": packet_size}
        )

    manifest: dict[str, Any] = {
        "$schema": "company-os.compiled-preflight.v1",
        "schema_version": SCHEMA_VERSION,
        "manifest_kind": "program-preflight",
        "program": {
            "program_id": semantics["program_id"],
            "program_label": semantics["program_label"],
        },
        "input_bindings": input_bindings,
        "input_set_sha256": input_set_sha256,
        "contract_summary": {
            "term_ids": sorted(terms),
            "constant_ids": sorted(constants),
            "authority_state_ids": sorted(states),
            "prohibition_ids": sorted(prohibitions),
            "required_evidence_ids": sorted(
                evidence_id for evidence_id, item in evidence_requirements.items() if item["required"]
            ),
            "oracle_ids": sorted(oracles),
            "required_capability_ids": required_caps,
        },
        "packet_counts": {"managers": len(manager_refs), "workers": len(work_refs)},
        "manager_packets": sorted(manager_refs, key=lambda item: item["packet_id"]),
        "work_packets": sorted(work_refs, key=lambda item: item["packet_id"]),
        "binding": {"algorithm": PACKET_ALGORITHM, "canonical_sha256": None},
    }
    manifest_digest = _unsigned_bound(manifest)[1]
    manifest["binding"]["canonical_sha256"] = manifest_digest
    manifest_size = _write_canonical(output_dir_path / "compiled-preflight.json", manifest)
    return {
        "manifest": manifest,
        "manifest_sha256": manifest_digest,
        "manifest_size": manifest_size,
        "manager_packets": manager_refs,
        "work_packets": work_refs,
        "output_dir": str(output_dir_path),
    }


def _safe_relative_output_path(value: str) -> Path:
    if not isinstance(value, str) or value.startswith("/") or "\\" in value:
        raise PreflightError("E_PACKET_MUTATED", f"packet path is not project-relative: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PreflightError("E_PACKET_MUTATED", f"packet path is not canonical: {value!r}")
    path = Path(*parts)
    if str(path) != value:
        raise PreflightError("E_PACKET_MUTATED", f"packet path is not canonical: {value!r}")
    return path


def _read_canonical_output(path: Path, code: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PreflightError(code, f"cannot read output {path}: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError(code, f"output is not valid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise PreflightError(code, f"output is not canonical JSON bytes: {path}")
    return value


def _verify_packet_structure(packet: Mapping[str, Any], expected_kind: str, expected_id: str) -> None:
    required = {
        "$schema", "schema_version", "packet_kind", "packet_id", "program",
        "input_bindings", "input_set_sha256", "parent", "scope", "authority_state_id",
        "prohibition_ids", "required_capability_ids", "semantic_slice", "deliverables", "binding",
    }
    if expected_kind == "manager":
        required.add("worker_ids")
    if set(packet) != required:
        extra = sorted(set(packet) - required)
        missing = sorted(required - set(packet))
        raise PreflightError("E_UNBOUND_OUTPUT", f"packet keys differ; extra={extra!r}, missing={missing!r}")
    if packet["packet_kind"] != expected_kind or packet["packet_id"] != expected_id:
        raise PreflightError("E_PACKET_MUTATED", f"packet identity mismatch for {expected_kind}:{expected_id}")
    if packet["schema_version"] != SCHEMA_VERSION or packet["$schema"] != "company-os.compiled-preflight.packet.v1":
        raise PreflightError("E_PACKET_MUTATED", "packet schema binding is invalid")
    if packet["binding"].get("algorithm") != PACKET_ALGORITHM:
        raise PreflightError("E_UNBOUND_OUTPUT", "packet binding algorithm is not supported")
    if not HEX64_RE.fullmatch(packet["binding"].get("canonical_sha256", "")):
        raise PreflightError("E_PACKET_MUTATED", "packet canonical sha256 is invalid")
    unsigned = copy.deepcopy(dict(packet))
    unsigned["binding"]["canonical_sha256"] = None
    if canonical_digest(unsigned) != packet["binding"]["canonical_sha256"]:
        raise PreflightError("E_PACKET_MUTATED", f"packet {expected_id!r} canonical sha256 does not verify")
    if not isinstance(packet["input_bindings"], list) or not isinstance(packet["input_set_sha256"], str):
        raise PreflightError("E_UNBOUND_OUTPUT", "packet input bindings are malformed")
    if canonical_digest(packet["input_bindings"]) != packet["input_set_sha256"]:
        raise PreflightError("E_UNBOUND_OUTPUT", "packet input_set_sha256 is not bound to input_bindings")
    _check_scope(packet["scope"], f"packet {expected_id}")


def _validate_output_reference(reference: Any, kind: str) -> Mapping[str, Any]:
    if not isinstance(reference, dict):
        raise PreflightError("E_UNBOUND_OUTPUT", f"{kind} packet reference is not an object")
    expected_keys = {"packet_id", "path", "sha256", "size"}
    if set(reference) != expected_keys:
        raise PreflightError("E_UNBOUND_OUTPUT", f"{kind} packet reference keys are not exact")
    if not isinstance(reference["packet_id"], str) or ID_RE.fullmatch(reference["packet_id"]) is None:
        raise PreflightError("E_UNBOUND_OUTPUT", f"{kind} packet reference id is invalid")
    if not isinstance(reference["sha256"], str) or HEX64_RE.fullmatch(reference["sha256"]) is None:
        raise PreflightError("E_UNBOUND_OUTPUT", f"{kind} packet reference sha256 is invalid")
    if not isinstance(reference["size"], int) or isinstance(reference["size"], bool) or reference["size"] < 1:
        raise PreflightError("E_UNBOUND_OUTPUT", f"{kind} packet reference size is invalid")
    return reference


def _validate_input_bindings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or [item.get("name") for item in value if isinstance(item, dict)] != list(INPUT_NAMES):
        raise PreflightError("E_UNBOUND_OUTPUT", "input bindings are not the exact ordered source set")
    validated: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"name", "schema_id", "schema_version", "sha256"}:
            raise PreflightError("E_UNBOUND_OUTPUT", "input binding keys are not exact")
        if item["name"] not in SCHEMA_IDS:
            raise PreflightError("E_UNBOUND_OUTPUT", f"input binding name is unknown: {item['name']!r}")
        if item["schema_id"] != SCHEMA_IDS[item["name"]] or item["schema_version"] != SCHEMA_VERSION:
            raise PreflightError("E_UNBOUND_OUTPUT", f"input binding schema is invalid for {item['name']!r}")
        if not isinstance(item["sha256"], str) or HEX64_RE.fullmatch(item["sha256"]) is None:
            raise PreflightError("E_UNBOUND_OUTPUT", f"input binding sha256 is invalid for {item['name']!r}")
        validated.append(item)
    return validated


def verify_output(
    output_dir: str | Path,
    semantics_path: str | Path | None = None,
    capabilities_path: str | Path | None = None,
    definitions_path: str | Path | None = None,
) -> dict[str, Any]:
    """Verify the output tree and recompile it from all three bound sources."""

    root = Path(output_dir)
    if root.is_file():
        if root.name != "compiled-preflight.json":
            raise PreflightError("E_MANIFEST_MUTATED", f"verify input is not compiled-preflight.json: {root}")
        root = root.parent
    manifest_path = root / "compiled-preflight.json"
    manifest = _read_canonical_output(manifest_path, "E_MANIFEST_MUTATED")
    required_manifest_keys = {
        "$schema", "schema_version", "manifest_kind", "program", "input_bindings",
        "input_set_sha256", "contract_summary", "packet_counts", "manager_packets",
        "work_packets", "binding",
    }
    if set(manifest) != required_manifest_keys:
        extra = sorted(set(manifest) - required_manifest_keys)
        missing = sorted(required_manifest_keys - set(manifest))
        raise PreflightError("E_UNBOUND_OUTPUT", f"manifest keys differ; extra={extra!r}, missing={missing!r}")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["manifest_kind"] != "program-preflight":
        raise PreflightError("E_MANIFEST_MUTATED", "manifest schema binding is invalid")
    if manifest["binding"].get("algorithm") != PACKET_ALGORITHM:
        raise PreflightError("E_UNBOUND_OUTPUT", "manifest binding algorithm is not supported")
    manifest_unsigned = copy.deepcopy(manifest)
    manifest_unsigned["binding"]["canonical_sha256"] = None
    manifest_digest = manifest["binding"].get("canonical_sha256")
    if not isinstance(manifest_digest, str) or not HEX64_RE.fullmatch(manifest_digest):
        raise PreflightError("E_MANIFEST_MUTATED", "manifest canonical sha256 is invalid")
    if canonical_digest(manifest_unsigned) != manifest_digest:
        raise PreflightError("E_MANIFEST_MUTATED", "manifest canonical sha256 does not verify")
    _validate_input_bindings(manifest["input_bindings"])
    if canonical_digest(manifest["input_bindings"]) != manifest["input_set_sha256"]:
        raise PreflightError("E_UNBOUND_OUTPUT", "manifest input_set_sha256 is not bound to input_bindings")
    if manifest["packet_counts"] != {
        "managers": len(manifest["manager_packets"]),
        "workers": len(manifest["work_packets"]),
    }:
        raise PreflightError("E_UNBOUND_OUTPUT", "manifest packet counts do not close over packet references")

    if not all((semantics_path, capabilities_path, definitions_path)):
        raise PreflightError(
            "E_INPUT_BINDING",
            "source-bound verification requires program semantics, host capabilities, and work definitions",
        )
    sources = {
        "program_semantics": _read_json(Path(semantics_path), "program semantics"),
        "host_capabilities": _read_json(Path(capabilities_path), "host capabilities"),
        "work_definitions": _read_json(Path(definitions_path), "work definitions"),
    }
    expected_bindings = _source_bindings(sources)
    if expected_bindings != manifest["input_bindings"]:
        raise PreflightError("E_INPUT_BINDING", "compiled manifest input bindings do not match supplied sources")

    expected_paths: set[str] = {"compiled-preflight.json"}
    manager_by_id: dict[str, Mapping[str, Any]] = {}
    for reference in sorted(manifest["manager_packets"], key=lambda item: item["packet_id"]):
        reference = _validate_output_reference(reference, "manager")
        packet_id = reference["packet_id"]
        if packet_id in manager_by_id:
            raise PreflightError("E_UNBOUND_OUTPUT", f"duplicate manager packet reference {packet_id!r}")
        relative = _safe_relative_output_path(reference["path"])
        if relative.parts[0] != "manager-packets" or relative.suffix != ".json":
            raise PreflightError("E_PACKET_MUTATED", f"manager packet path is invalid: {reference['path']!r}")
        if relative.name != _packet_filename("manager", packet_id, reference["sha256"]):
            raise PreflightError("E_UNBOUND_OUTPUT", f"manager packet filename is not content-addressed: {packet_id!r}")
        expected_paths.add(str(relative))
        packet_path = root / relative
        packet = _read_canonical_output(packet_path, "E_PACKET_MUTATED")
        _verify_packet_structure(packet, "manager", packet_id)
        if reference["sha256"] != packet["binding"]["canonical_sha256"] or reference["size"] != packet_path.stat().st_size:
            raise PreflightError("E_PACKET_MUTATED", f"manager packet reference does not bind {packet_id!r}")
        if packet["input_bindings"] != manifest["input_bindings"] or packet["input_set_sha256"] != manifest["input_set_sha256"]:
            raise PreflightError("E_UNBOUND_OUTPUT", f"manager packet {packet_id!r} is not bound to manifest inputs")
        if packet["parent"] != {"kind": "program-preflight", "input_set_sha256": manifest["input_set_sha256"]}:
            raise PreflightError("E_UNBOUND_OUTPUT", f"manager packet {packet_id!r} has an invalid parent binding")
        manager_by_id[packet_id] = packet

    work_ids: set[str] = set()
    for reference in sorted(manifest["work_packets"], key=lambda item: item["packet_id"]):
        reference = _validate_output_reference(reference, "work")
        packet_id = reference["packet_id"]
        if packet_id in work_ids:
            raise PreflightError("E_UNBOUND_OUTPUT", f"duplicate work packet reference {packet_id!r}")
        work_ids.add(packet_id)
        relative = _safe_relative_output_path(reference["path"])
        if relative.parts[0] != "work-packets" or relative.suffix != ".json":
            raise PreflightError("E_PACKET_MUTATED", f"work packet path is invalid: {reference['path']!r}")
        if relative.name != _packet_filename("work", packet_id, reference["sha256"]):
            raise PreflightError("E_UNBOUND_OUTPUT", f"work packet filename is not content-addressed: {packet_id!r}")
        expected_paths.add(str(relative))
        packet_path = root / relative
        packet = _read_canonical_output(packet_path, "E_PACKET_MUTATED")
        _verify_packet_structure(packet, "work", packet_id)
        if reference["sha256"] != packet["binding"]["canonical_sha256"] or reference["size"] != packet_path.stat().st_size:
            raise PreflightError("E_PACKET_MUTATED", f"work packet reference does not bind {packet_id!r}")
        if packet["input_bindings"] != manifest["input_bindings"] or packet["input_set_sha256"] != manifest["input_set_sha256"]:
            raise PreflightError("E_UNBOUND_OUTPUT", f"work packet {packet_id!r} is not bound to manifest inputs")
        parent = packet["parent"]
        manager_id = parent.get("manager_id") if isinstance(parent, dict) else None
        if parent.get("kind") != "manager-packet" or manager_id not in manager_by_id or parent.get("packet_sha256") != manager_by_id[manager_id]["binding"]["canonical_sha256"]:
            raise PreflightError("E_UNBOUND_OUTPUT", f"work packet {packet_id!r} has an invalid manager parent binding")

    for directory_name in ("manager-packets", "work-packets"):
        directory = root / directory_name
        if not directory.is_dir() or directory.is_symlink():
            raise PreflightError("E_PACKET_EXTRA", f"required packet directory is missing or unsafe: {directory_name}")
        for path in directory.rglob("*"):
            if path.is_symlink() or not path.is_file():
                raise PreflightError("E_PACKET_EXTRA", f"unsafe or extra packet output: {path}")
            relative = str(path.relative_to(root))
            if relative not in expected_paths:
                raise PreflightError("E_PACKET_EXTRA", f"extra packet output: {relative}")
    for path in root.iterdir():
        if path.name not in {"compiled-preflight.json", "manager-packets", "work-packets"}:
            raise PreflightError("E_PACKET_EXTRA", f"extra output at root: {path.name}")

    with tempfile.TemporaryDirectory(prefix="company-os-preflight-verify-") as temp_dir:
        expected_root = Path(temp_dir) / "expected"
        compile_program(
            Path(semantics_path),
            Path(capabilities_path),
            Path(definitions_path),
            expected_root,
        )
        actual_files = {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        expected_files = {
            str(path.relative_to(expected_root)): path.read_bytes()
            for path in expected_root.rglob("*")
            if path.is_file()
        }
        if set(actual_files) != set(expected_files):
            raise PreflightError(
                "E_UNBOUND_OUTPUT",
                "compiled output path set differs from deterministic source recompilation",
            )
        for relative in sorted(expected_files):
            if actual_files[relative] != expected_files[relative]:
                raise PreflightError(
                    "E_PACKET_MUTATED",
                    f"compiled output differs from deterministic source recompilation: {relative}",
                )
    return {
        "manifest_sha256": manifest_digest,
        "manager_count": len(manager_by_id),
        "work_count": len(work_ids),
        "output_dir": str(root),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile", help="validate inputs and compile packets")
    compile_parser.add_argument("--semantics", "--program-semantics", dest="semantics", required=True)
    compile_parser.add_argument("--capabilities", "--host-capabilities", dest="capabilities", required=True)
    compile_parser.add_argument("--definitions", "--work-definitions", dest="definitions", required=True)
    compile_parser.add_argument("--output-dir", "--output", dest="output_dir", required=True)
    verify_parser = subparsers.add_parser("verify", help="verify a compiled output tree")
    verify_parser.add_argument("--output-dir", "--output", "--manifest", dest="output_dir", required=True)
    verify_parser.add_argument("--semantics", "--program-semantics", dest="semantics", required=True)
    verify_parser.add_argument("--capabilities", "--host-capabilities", dest="capabilities", required=True)
    verify_parser.add_argument("--definitions", "--work-definitions", dest="definitions", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "compile":
            result = compile_program(args.semantics, args.capabilities, args.definitions, args.output_dir)
            print(
                f"compiled {result['manifest_sha256']} managers={len(result['manager_packets'])} "
                f"workers={len(result['work_packets'])} output={result['output_dir']}"
            )
        else:
            result = verify_output(args.output_dir, args.semantics, args.capabilities, args.definitions)
            print(
                f"verified {result['manifest_sha256']} managers={result['manager_count']} "
                f"workers={result['work_count']} output={result['output_dir']}"
            )
    except PreflightError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


# Friendly aliases for callers importing the bounded compiler as a module.
compile_preflight = compile_program
verify_preflight = verify_output


if __name__ == "__main__":
    raise SystemExit(main())
