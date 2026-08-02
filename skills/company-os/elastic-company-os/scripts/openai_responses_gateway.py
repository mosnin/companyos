#!/usr/bin/env python3
"""Fixture-only, feature-off adapter for the OpenAI Responses boundary.

This deliberately contains no provider client or network implementation.  The
only effect boundary is the injected, explicitly-marked fixture transport.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


COMMAND_SCHEMA = "company-os.openai-responses-gateway-command.v1"
REQUEST_KEYRING_SCHEMA = "company-os.openai-responses-request-keyring.v1"
RESULT_SCHEMA = "company-os.runtime-gateway-result.v1"
RECEIPT_SCHEMA = "company-os.runtime-receipt-attestation.v1"
FIXED_INPUT = "Return exactly READY. Do not call tools or perform external actions."
PROVIDER_FIXTURE_SCHEMA = "responses-fixture-no-tools-v1"
PROVIDER_BASE_FIELDS = {"id", "object", "created_at", "status", "model"}
PROVIDER_TERMINAL_FIELDS = PROVIDER_BASE_FIELDS | {"completed_at", "usage"}
PROVIDER_USAGE_FIELDS = {
    "input_tokens", "input_tokens_details", "output_tokens",
    "output_tokens_details", "total_tokens",
}
PROVIDER_INPUT_DETAIL_FIELDS = {"cached_tokens", "cache_write_tokens"}
PROVIDER_OUTPUT_DETAIL_FIELDS = {"reasoning_tokens"}
PROVIDER_USAGE_NUMERIC_PATHS = (
    ("input_tokens",),
    ("input_tokens_details", "cached_tokens"),
    ("input_tokens_details", "cache_write_tokens"),
    ("output_tokens",),
    ("output_tokens_details", "reasoning_tokens"),
    ("total_tokens",),
)
COMMAND_FIELDS = {
    "schema", "request_key_id", "gateway_request", "gateway_request_digest",
    "nonce", "issued_at", "expires_at",
}


class _ResponsesGatewayErrorType(type):
    """Treat the local verifier's fail-closed error as the same boundary error.

    The verifier is deliberately loaded by path in independent consumers, so
    its ``GatewayError`` class can have a distinct Python identity while still
    denoting this adapter's verification boundary.
    """

    def __subclasscheck__(cls, candidate: type[object]) -> bool:
        return (
            getattr(candidate, "__name__", None) == "GatewayError"
            and str(getattr(candidate, "__module__", "")).endswith("runtime_gateway")
        ) or super().__subclasscheck__(candidate)


class ResponsesGatewayError(ValueError, metaclass=_ResponsesGatewayErrorType):
    """A fixture-gateway command which must fail closed."""


def _module(name: str) -> Any:
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"company_os_{name}", path)
    if spec is None or spec.loader is None:
        raise ResponsesGatewayError("required local verifier is unavailable")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


runtime_gateway = _module("runtime_gateway")
observations = _module("runtime_observations")
runtime_lifecycle = _module("runtime_lifecycle")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ResponsesGatewayError(f"{field} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ResponsesGatewayError(f"{field} is invalid") from None
    if parsed.tzinfo is None:
        raise ResponsesGatewayError(f"{field} is invalid")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ResponsesGatewayError(f"{field} is invalid")
    return value


def _sha(value: Any, field: str) -> str:
    value = _text(value, field)
    if len(value) != 64 or any(item not in "0123456789abcdef" for item in value):
        raise ResponsesGatewayError(f"{field} is invalid")
    return value


def _owner_file(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except OSError:
        raise ResponsesGatewayError("protected fixture path is unavailable") from None
    if path.is_symlink() or not stat.S_ISREG(mode) or mode & 0o077:
        raise ResponsesGatewayError("protected fixture file is unsafe")


def _owner_only(path: Path, *, mode: int, kind: int | None = None) -> os.stat_result:
    """Validate ownership and exact private permissions without following links."""
    try:
        value = path.lstat()
    except OSError:
        raise ResponsesGatewayError("protected fixture path is unavailable") from None
    if path.is_symlink() or value.st_uid != os.getuid() or value.st_mode & 0o777 != mode:
        raise ResponsesGatewayError("protected fixture path is unsafe")
    if kind is not None and not kind(value.st_mode):
        raise ResponsesGatewayError("protected fixture path is unsafe")
    return value


def _has_symlink_component(path: Path) -> bool:
    """Check the supplied spelling, rather than resolving through a symlink."""
    current = Path(path).absolute()
    parts = current.parts
    probe = Path(parts[0])
    for component in parts[1:]:
        probe /= component
        try:
            if probe.is_symlink():
                return True
        except OSError:
            return True
    return False


def _public_key_fingerprint(path: Path) -> str:
    """Compare normalized DER public material rather than path or PEM spelling."""
    try:
        result = subprocess.run(
            ["openssl", "pkey", "-pubin", "-in", str(path), "-outform", "DER"],
            capture_output=True,
            check=False,
        )
    except OSError:
        raise ResponsesGatewayError("public-key verification support is unavailable") from None
    if result.returncode != 0 or not result.stdout:
        raise ResponsesGatewayError("public-key material is invalid")
    return _bytes_digest(result.stdout)


_SAFE_PROVIDER_TOKEN_PATHS = {
    ("usage", "input_tokens"),
    ("usage", "output_tokens"),
    ("usage", "total_tokens"),
    ("usage", "input_tokens_details"),
    ("usage", "output_tokens_details"),
    ("usage", "input_tokens_details", "cached_tokens"),
    ("usage", "input_tokens_details", "cache_write_tokens"),
    ("usage", "output_tokens_details", "reasoning_tokens"),
}


def _normalized_key(value: object) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", str(value)).casefold().replace("-", "_")


def _contains_secret(value: Any, *, key: str = "", path: tuple[str, ...] = ()) -> bool:
    """Reject authority-bearing input without ever reflecting it in diagnostics."""
    lowered = _normalized_key(key)
    current_path = (*path, lowered) if key else path
    safe_token_count = current_path in _SAFE_PROVIDER_TOKEN_PATHS
    if key != "admission_grant_token" and (
        any(word in lowered for word in (
            "secret", "credential", "password", "api_key", "private_key",
            "authorization", "access_token", "refresh_token", "bearer_token",
        ))
        or ((lowered == "token" or lowered.endswith("_token")) and not safe_token_count)
    ):
        return True
    if isinstance(value, dict):
        return any(
            _contains_secret(item, key=str(name), path=current_path)
            for name, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret(item, path=current_path) for item in value)
    if isinstance(value, str):
        sample = value.casefold()
        return bool(
            sample.startswith("sk-")
            or re.search(r"(?:authorization\s*:\s*)?(?:bearer|basic)\s+[^\s]{4,}", sample)
        )
    return False


def _provider_contains_credential(
    value: Any, *, key: str = "", path: tuple[str, ...] = ()
) -> bool:
    """Aggressive defense-in-depth for the accepted provider fixture shape."""
    lowered = _normalized_key(key)
    current_path = (*path, lowered) if key else path
    safe_token_count = current_path in _SAFE_PROVIDER_TOKEN_PATHS
    if key and not safe_token_count and (
        any(word in lowered for word in (
            "secret", "credential", "password", "authorization", "auth",
            "token", "jwt", "private_key", "signing_key", "api_key",
            "access_key", "client_key", "provider_key", "bearer",
        ))
        or lowered == "key"
        or lowered.endswith("_key")
        or lowered.endswith("_keys")
    ):
        return True
    if isinstance(value, dict):
        return any(
            _provider_contains_credential(item, key=str(name), path=current_path)
            for name, item in value.items()
        )
    if isinstance(value, list):
        return any(_provider_contains_credential(item, path=current_path) for item in value)
    if isinstance(value, str):
        sample = value.strip()
        return bool(
            sample.casefold().startswith("sk-")
            or re.search(
                r"(?:authorization\s*:\s*)?(?:bearer|basic)\s+[^\s]{4,}",
                sample,
                re.I,
            )
            or re.fullmatch(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", sample)
        )
    return False


def _validated_provider_usage(source: Any) -> dict[str, Any]:
    """Validate the complete versioned usage schema and all count provenance."""
    if (
        not isinstance(source, dict)
        or set(source) != PROVIDER_USAGE_FIELDS
        or not isinstance(source.get("input_tokens_details"), dict)
        or set(source["input_tokens_details"]) != PROVIDER_INPUT_DETAIL_FIELDS
        or not isinstance(source.get("output_tokens_details"), dict)
        or set(source["output_tokens_details"]) != PROVIDER_OUTPUT_DETAIL_FIELDS
    ):
        raise ResponsesGatewayError("provider terminal usage is invalid")

    numbers: dict[tuple[str, ...], int] = {}
    for path in PROVIDER_USAGE_NUMERIC_PATHS:
        value: Any = source
        for component in path:
            if not isinstance(value, dict):
                raise ResponsesGatewayError("provider terminal usage is invalid")
            value = value.get(component)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ResponsesGatewayError("provider terminal usage is invalid")
        numbers[path] = value

    input_tokens = numbers[("input_tokens",)]
    cached_tokens = numbers[("input_tokens_details", "cached_tokens")]
    cache_write_tokens = numbers[("input_tokens_details", "cache_write_tokens")]
    output_tokens = numbers[("output_tokens",)]
    reasoning_tokens = numbers[("output_tokens_details", "reasoning_tokens")]
    total_tokens = numbers[("total_tokens",)]
    if (
        total_tokens != input_tokens + output_tokens
        or cached_tokens + cache_write_tokens > input_tokens
        or reasoning_tokens > output_tokens
    ):
        raise ResponsesGatewayError("provider terminal usage is invalid")
    return source


class FixtureResponsesGateway:
    def __init__(
        self,
        *,
        socket_path: Path,
        state_path: Path,
        artifact_root: Path,
        request_keyring_path: Path,
        gateway_keyring_path: Path,
        gateway_key_id: str,
        gateway_private_key_path: Path,
        decision_public_key_path: Path,
        now: datetime,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.state_path = Path(state_path)
        self.artifact_root = Path(artifact_root)
        self.request_keyring_path = Path(request_keyring_path)
        self.gateway_keyring_path = Path(gateway_keyring_path)
        self.gateway_key_id = gateway_key_id
        self.gateway_private_key_path = Path(gateway_private_key_path)
        self.decision_public_key_path = Path(decision_public_key_path)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ResponsesGatewayError("fixture clock is invalid")
        self.now = now.astimezone(timezone.utc)

    def _boundary(self) -> Path:
        """Return the dedicated fixture root after rejecting all path escapes."""
        try:
            socket_mode = self.socket_path.lstat().st_mode
        except OSError:
            raise ResponsesGatewayError("fixture socket is unavailable") from None
        if _has_symlink_component(self.socket_path) or not stat.S_ISSOCK(socket_mode):
            raise ResponsesGatewayError("fixture socket is unsafe")
        _owner_only(self.socket_path, mode=0o600, kind=stat.S_ISSOCK)
        if _has_symlink_component(self.artifact_root) or not self.artifact_root.is_dir():
            raise ResponsesGatewayError("fixture artifact root is unsafe")
        try:
            artifact_mode = self.artifact_root.stat().st_mode
        except OSError:
            raise ResponsesGatewayError("fixture artifact root is unavailable") from None
        _owner_only(self.artifact_root, mode=0o700, kind=stat.S_ISDIR)
        root = self.socket_path.resolve().parent
        if _has_symlink_component(self.state_path) or self.state_path.resolve().parent != root:
            raise ResponsesGatewayError("fixture state path escapes its root")
        if self.artifact_root.resolve().parent != root:
            raise ResponsesGatewayError("fixture artifact root escapes its root")
        if self.state_path.exists():
            _owner_only(self.state_path, mode=0o600, kind=stat.S_ISREG)
        if (
            _has_symlink_component(self.decision_public_key_path)
            or not self.decision_public_key_path.is_file()
        ):
            raise ResponsesGatewayError("decision issuer public key is unavailable")
        lock = self.state_path.with_name(self.state_path.name + ".lock")
        if lock.exists():
            _owner_file(lock)
        return root

    def _load_request_key(self, key_id: str, valid_at: datetime) -> Path:
        try:
            keyring = observations.load_json_strict(self.request_keyring_path.resolve())
        except ValueError as exc:
            raise ResponsesGatewayError("request keyring is invalid") from exc
        if not isinstance(keyring, dict) or set(keyring) != {"schema", "keys"} or keyring.get("schema") != REQUEST_KEYRING_SCHEMA:
            raise ResponsesGatewayError("request keyring is invalid")
        if not isinstance(keyring["keys"], list):
            raise ResponsesGatewayError("request keyring is invalid")
        selected: dict[str, Any] | None = None
        for item in keyring["keys"]:
            required = {"key_id", "algorithm", "public_key_path", "status", "not_before", "not_after"}
            if not isinstance(item, dict) or set(item) != required:
                raise ResponsesGatewayError("request keyring is invalid")
            if item.get("key_id") == key_id:
                if selected is not None:
                    raise ResponsesGatewayError("request keyring is invalid")
                selected = item
        if selected is None or selected.get("algorithm") != "rsa-sha256" or selected.get("status") != "active":
            raise ResponsesGatewayError("request signing key is not active")
        not_before, not_after = _time(selected.get("not_before"), "not_before"), _time(selected.get("not_after"), "not_after")
        if not_before > valid_at or not_after <= valid_at or not_after <= not_before:
            raise ResponsesGatewayError("request signing key is outside its validity window")
        public = Path(_text(selected.get("public_key_path"), "public_key_path"))
        if not public.is_absolute():
            public = self.request_keyring_path.resolve().parent / public
        public = public.resolve()
        if not public.is_file() or public.is_symlink():
            raise ResponsesGatewayError("request public key is unavailable")
        return public

    def _verify_command(self, envelope: Any) -> tuple[dict[str, Any], dict[str, Any], str, str, str]:
        if not isinstance(envelope, dict) or set(envelope) != {"claims", "signature"}:
            raise ResponsesGatewayError("command envelope is invalid")
        claims = envelope.get("claims")
        if not isinstance(claims, dict) or set(claims) != COMMAND_FIELDS or claims.get("schema") != COMMAND_SCHEMA:
            raise ResponsesGatewayError("command claims are invalid")
        if _contains_secret({key: value for key, value in claims.items() if key != "gateway_request"}):
            raise ResponsesGatewayError("command contains forbidden authority")
        issued_at, expires_at = _time(claims.get("issued_at"), "issued_at"), _time(claims.get("expires_at"), "expires_at")
        if issued_at > self.now + timedelta(seconds=30) or expires_at <= self.now or expires_at <= issued_at or expires_at - issued_at > timedelta(minutes=5):
            raise ResponsesGatewayError("command validity window is invalid")
        request = self._request(claims.get("gateway_request"))
        request_digest = _sha(claims.get("gateway_request_digest"), "gateway_request_digest")
        if request_digest != _digest(request):
            raise ResponsesGatewayError("command request digest is invalid")
        public = self._load_request_key(_text(claims.get("request_key_id"), "request_key_id"), issued_at)
        try:
            observations.verify_signature(claims, envelope.get("signature"), public)
        except ValueError as exc:
            raise ResponsesGatewayError("command signature is invalid") from exc
        return claims, request, request_digest, _digest(claims), _public_key_fingerprint(public)

    def _request(self, request: Any) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ResponsesGatewayError("gateway request is invalid")
        fields = {"schema", "operation", "attempt", "provider_task_id", "admission_grant_token", "admission_grant_digest", "lease_fence", "external_effects_allowed", "request_digest"}
        if set(request) != fields or request.get("schema") != runtime_gateway.REQUEST_SCHEMA:
            raise ResponsesGatewayError("gateway request is invalid")
        unsigned = {key: value for key, value in request.items() if key != "request_digest"}
        if request.get("request_digest") != _digest(unsigned):
            raise ResponsesGatewayError("gateway request digest is invalid")
        operation = request.get("operation")
        if operation not in {"launch", "query", "observe", "cancel"} or request.get("external_effects_allowed") is not False:
            raise ResponsesGatewayError("gateway request is invalid")
        attempt = request.get("attempt")
        required_attempt = set(runtime_gateway.IMMUTABLE_ATTEMPT_FIELDS)
        if not isinstance(attempt, dict) or set(attempt) != required_attempt:
            raise ResponsesGatewayError("gateway request attempt is invalid")
        if attempt.get("provider") != "openai" or attempt.get("surface") != "responses-api" or attempt.get("requested_model") not in {"gpt-5.6-sol", "gpt-5.6-luna"}:
            raise ResponsesGatewayError("gateway request is outside the fixture canary")
        for field in ("attempt_id", "project_id", "work_id", "cycle_id", "parent_runtime_id", "role", "account", "idempotency_key"):
            _text(attempt.get(field), field)
        _sha(attempt.get("fabric_manifest_digest"), "fabric_manifest_digest")
        _sha(attempt.get("phase2_contract_digest"), "phase2_contract_digest")
        if attempt.get("capabilities") != ["emit_artifact", "read_project"]:
            raise ResponsesGatewayError("gateway request exceeds the fixture capabilities")
        if not isinstance(attempt.get("scope"), list) or attempt.get("scope_digest") != _digest(attempt["scope"]):
            raise ResponsesGatewayError("gateway request scope binding is invalid")
        if attempt.get("role") == "manager":
            if attempt.get("requested_model") != "gpt-5.6-sol" or attempt.get("parent_runtime_id") != "master":
                raise ResponsesGatewayError("gateway request manager identity is invalid")
        elif attempt.get("role") == "worker":
            if attempt.get("requested_model") != "gpt-5.6-luna" or attempt.get("parent_runtime_id") == "master":
                raise ResponsesGatewayError("gateway request worker identity is invalid")
        else:
            raise ResponsesGatewayError("gateway request role is invalid")
        budget = attempt.get("budget")
        expected_budget = {"time_minutes", "token_limit", "cost_usd", "max_concurrency", "max_retries"}
        if not isinstance(budget, dict) or set(budget) != expected_budget:
            raise ResponsesGatewayError("gateway request budget is invalid")
        if any(not isinstance(budget.get(name), int) or isinstance(budget[name], bool) or budget[name] < 0 for name in ("token_limit", "max_concurrency", "max_retries")):
            raise ResponsesGatewayError("gateway request budget is invalid")
        if any(not isinstance(budget.get(name), (int, float)) or isinstance(budget[name], bool) or not math.isfinite(budget[name]) or budget[name] < 0 for name in ("time_minutes", "cost_usd")) or budget["max_concurrency"] != 1 or budget["max_retries"] != 0:
            raise ResponsesGatewayError("gateway request budget is invalid")
        fence = request.get("lease_fence")
        if not isinstance(fence, dict) or any(fence.get(name) in (None, "") for name in ("lease_id", "generation", "owner", "program_version", "expires_at")):
            raise ResponsesGatewayError("gateway request lease fence is invalid")
        if not isinstance(fence.get("generation"), int) or isinstance(fence["generation"], bool) or fence["generation"] < 0 or fence.get("program_version") != attempt.get("program_version") or _time(fence["expires_at"], "lease_fence.expires_at") <= self.now:
            raise ResponsesGatewayError("gateway request lease fence is invalid")
        _sha(request.get("admission_grant_digest"), "admission_grant_digest")
        _text(request.get("admission_grant_token"), "admission_grant_token")
        if _contains_secret({key: value for key, value in request.items() if key != "admission_grant_token"}):
            raise ResponsesGatewayError("gateway request contains forbidden authority")
        task = request.get("provider_task_id")
        if operation in {"observe", "cancel"} and not isinstance(task, str):
            raise ResponsesGatewayError("gateway request lacks provider task identity")
        if operation in {"launch", "query"} and task is not None:
            raise ResponsesGatewayError("gateway request has invalid provider task identity")
        return request

    def _gateway_key(self) -> tuple[Path, str]:
        try:
            public = observations.load_gateway_key(self.gateway_keyring_path, _text(self.gateway_key_id, "gateway_key_id"), self.now)
        except ValueError as exc:
            raise ResponsesGatewayError("gateway signing key is unavailable") from exc
        _owner_only(self.gateway_private_key_path, mode=0o600, kind=stat.S_ISREG)
        # Compare only public material derived by OpenSSL; private key bytes are never read into Python or state.
        try:
            derived = subprocess.run(["openssl", "pkey", "-in", str(self.gateway_private_key_path), "-pubout"], capture_output=True, check=False)
        except OSError:
            raise ResponsesGatewayError("gateway signing support is unavailable") from None
        if derived.returncode != 0 or derived.stdout != public.read_bytes():
            raise ResponsesGatewayError("gateway private key does not match active public key")
        return public, _public_key_fingerprint(public)

    def _sign(self, claims: dict[str, Any]) -> dict[str, Any]:
        self._gateway_key()
        try:
            with tempfile.NamedTemporaryFile() as payload, tempfile.NamedTemporaryFile() as signature:
                payload.write(_canonical(claims).encode("utf-8"))
                payload.flush()
                result = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(self.gateway_private_key_path), "-out", signature.name, payload.name], capture_output=True, check=False)
                if result.returncode != 0:
                    raise ResponsesGatewayError("gateway signing failed")
                signature.seek(0)
                encoded = base64.urlsafe_b64encode(signature.read()).decode("ascii").rstrip("=")
        except OSError:
            raise ResponsesGatewayError("gateway signing support is unavailable") from None
        return {"claims": claims, "signature": encoded}

    def _empty_state(self) -> dict[str, Any]:
        return {"schema": "company-os.fixture-responses-gateway-state.v1", "commands": {}, "attempts": {}, "nonces": {}}

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty_state()
        _owner_file(self.state_path)
        try:
            state = observations.load_json_strict(self.state_path)
        except ValueError as exc:
            raise ResponsesGatewayError("fixture state is invalid") from exc
        if not isinstance(state, dict) or set(state) != {"schema", "commands", "attempts", "nonces"} or state.get("schema") != self._empty_state()["schema"]:
            raise ResponsesGatewayError("fixture state is invalid")
        if not all(isinstance(state[key], dict) for key in ("commands", "attempts", "nonces")):
            raise ResponsesGatewayError("fixture state is invalid")
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        data = _canonical(state).encode("utf-8")
        temporary = self.state_path.with_name(self.state_path.name + ".tmp-" + uuid.uuid4().hex)
        try:
            descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.state_path)
            os.chmod(self.state_path, 0o600)
            directory = os.open(str(self.state_path.parent), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ResponsesGatewayError("fixture state cannot be persisted") from exc

    def _raw_path(self, label: str, digest: str) -> tuple[Path, str]:
        relative = f"{label}-{digest}.json"
        path = self.artifact_root / relative
        if path.resolve().parent != self.artifact_root.resolve():
            raise ResponsesGatewayError("fixture artifact path escapes its root")
        return path, relative

    def _write_artifact(self, label: str, value: bytes) -> str:
        digest = _bytes_digest(value)
        path, relative = self._raw_path(label, digest)
        if path.exists():
            _owner_file(path)
            if path.read_bytes() != value:
                raise ResponsesGatewayError("fixture artifact collision")
            return relative
        temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
        try:
            descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
            directory = os.open(str(self.artifact_root), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ResponsesGatewayError("fixture artifact cannot be persisted") from exc
        return relative

    def _artifact_snapshot(self) -> set[str]:
        """Capture the serialized fixture artifact namespace under the gateway lock."""
        return {
            item.name
            for item in self.artifact_root.iterdir()
            if item.is_file() and not item.is_symlink()
        }

    def _cleanup_attempt_artifacts(self, before: set[str]) -> bool:
        """Remove only files created by the current serialized attempt."""
        clean = True
        try:
            candidates = list(self.artifact_root.iterdir())
        except OSError:
            return False
        for item in candidates:
            if item.name in before:
                continue
            try:
                if item.is_symlink() or not item.is_file():
                    clean = False
                    continue
                _owner_only(item, mode=0o600, kind=stat.S_ISREG)
                item.unlink()
            except (OSError, ResponsesGatewayError):
                clean = False
        try:
            directory = os.open(str(self.artifact_root), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            clean = False
        return clean

    def _persist_launch_unknown_after_effect(
        self,
        *,
        state: dict[str, Any],
        entry: dict[str, Any],
        artifact_snapshot: set[str],
    ) -> None:
        """Best-effort durable ambiguity boundary after a possible create effect."""
        cleanup_complete = self._cleanup_attempt_artifacts(artifact_snapshot)
        for field in ("model", "raw_retained", "result"):
            entry.pop(field, None)
        entry.update({
            "status": "launch_unknown",
            "provider_task_id": None,
            "terminal": False,
            "sequence": 1,
        })
        try:
            self._write_state(state)
        except ResponsesGatewayError:
            raise ResponsesGatewayError(
                "launch_state_unpersisted: provider create may have taken effect; "
                "the retained launching tombstone forbids automatic relaunch"
            ) from None
        if not cleanup_complete:
            raise ResponsesGatewayError(
                "provider create outcome is ambiguous and attempt artifact cleanup is incomplete"
            )

    def _provider(
        self,
        raw_bytes: bytes,
        request: dict[str, Any],
        operation: str,
        retained_task: str | None,
        *,
        retain: bool = True,
    ) -> dict[str, Any]:
        if not isinstance(raw_bytes, bytes):
            raise ResponsesGatewayError("fixture transport must return raw bytes")
        try:
            provider = observations.load_json_bytes_strict(raw_bytes)
        except ValueError as exc:
            raise ResponsesGatewayError("provider fixture JSON is invalid") from exc
        if (
            not isinstance(provider, dict)
            or _contains_secret(provider)
            or _provider_contains_credential(provider)
        ):
            raise ResponsesGatewayError("provider fixture is invalid")
        raw_status = provider.get("status")
        terminal = raw_status in {"completed", "failed", "cancelled", "incomplete"}
        expected_fields = PROVIDER_TERMINAL_FIELDS if terminal else PROVIDER_BASE_FIELDS
        if set(provider) != expected_fields or provider.get("object") != "response":
            raise ResponsesGatewayError("provider fixture schema is invalid")
        task_id = _text(provider.get("id"), "provider response id")
        model = _text(provider.get("model"), "provider response model")
        status = _text(provider.get("status"), "provider response status")
        if model != request["attempt"]["requested_model"]:
            raise ResponsesGatewayError("provider response model is not admitted")
        if retained_task is not None and task_id != retained_task:
            raise ResponsesGatewayError("provider response changes task identity")
        created_at = provider.get("created_at")
        if not isinstance(created_at, (int, float)) or isinstance(created_at, bool) or not math.isfinite(created_at):
            raise ResponsesGatewayError("provider response timestamp is invalid")
        try:
            provider_time = datetime.fromtimestamp(created_at, timezone.utc)
        except (OverflowError, OSError, ValueError):
            raise ResponsesGatewayError("provider response timestamp is invalid") from None
        if terminal:
            completed_at = provider.get("completed_at")
            if not isinstance(completed_at, (int, float)) or isinstance(completed_at, bool) or not math.isfinite(completed_at) or completed_at < created_at:
                raise ResponsesGatewayError("provider terminal timestamp is invalid")
            try:
                provider_time = datetime.fromtimestamp(completed_at, timezone.utc)
            except (OverflowError, OSError, ValueError):
                raise ResponsesGatewayError("provider terminal timestamp is invalid") from None
        if provider_time > self.now + runtime_gateway.MAX_FUTURE_SKEW:
            raise ResponsesGatewayError("provider response timestamp exceeds allowed clock skew")
        provider_usage: dict[str, Any] | None = None
        if terminal:
            source = _validated_provider_usage(provider.get("usage"))
            # Preserve the exact provider object.  Responses usage does not
            # establish a dollar cost, so it is intentionally not projected as
            # lifecycle telemetry until separately priced evidence exists.
            provider_usage = source
        if status not in {"in_progress", "queued", "completed", "failed", "cancelled", "incomplete"}:
            raise ResponsesGatewayError("provider response status is unsupported")
        normalized_status = {"completed": "succeeded", "failed": "failed", "cancelled": "cancelled", "incomplete": "failed"}.get(status)
        payload: dict[str, Any] = {
            "provider_status": status,
            "status": normalized_status,
            "usage": None,
            "fixed_input_sha256": _bytes_digest(FIXED_INPUT.encode("utf-8")),
            "provider_fixture_schema": PROVIDER_FIXTURE_SCHEMA,
        }
        if terminal:
            payload["provider_usage"] = provider_usage
            payload["cost_status"] = "unavailable"
        info = {
            "task_id": task_id,
            "model": model,
            "status": status,
            "terminal": terminal,
            "provider_time": _iso(provider_time),
            "payload": payload,
            "raw_sha": _bytes_digest(raw_bytes),
        }
        return self._retain_provider(info, raw_bytes) if retain else info

    def _retain_provider(self, info: dict[str, Any], raw_bytes: bytes) -> dict[str, Any]:
        """Retain exact bytes only after every positive-schema/identity check."""
        retained = {
            **info,
            "payload": dict(info["payload"]),
        }
        raw_source_path = self._write_artifact("provider", raw_bytes)
        retained["raw_source_path"] = raw_source_path
        retained["payload"].update({
            "provider_raw_artifact_path": raw_source_path,
            "provider_raw_sha256": _bytes_digest(raw_bytes),
            "provider_raw_size": len(raw_bytes),
        })
        return retained

    def _record(self, request: dict[str, Any], request_digest: str, event: str, info: dict[str, Any], sequence: int) -> tuple[dict[str, Any], dict[str, Any]]:
        attempt = request["attempt"]
        task = info.get("task_id")
        raw = {
            "provider": attempt["provider"], "surface": attempt["surface"], "account": attempt["account"],
            "provider_task_id": task, "provider_event_id": f"fixture-{_digest([request_digest, event, sequence, info.get('raw_sha', '')])}",
            "event_type": event, "provider_sequence": sequence, "provider_timestamp": info["provider_time"],
            "observed_model": info.get("model"), "payload": info["payload"],
        }
        raw_bytes = _canonical(raw).encode("utf-8")
        raw_path = self._write_artifact("observation", raw_bytes)
        issued = self.now
        received_at = max(self.now, _time(info["provider_time"], "provider_time"))
        claims = {
            "schema": RESULT_SCHEMA, "gateway_key_id": self.gateway_key_id, "request_digest": request["request_digest"],
            "operation": request["operation"], "provider": attempt["provider"], "surface": attempt["surface"], "account": attempt["account"],
            "provider_task_id": task, "provider_event_id": raw["provider_event_id"], "event_type": event,
            "provider_sequence": sequence, "provider_timestamp": info["provider_time"], "gateway_received_at": _iso(received_at),
            "observed_model": info.get("model"), "raw_artifact_path": raw_path, "raw_artifact_sha256": _bytes_digest(raw_bytes),
            "payload_sha256": _digest(raw["payload"]),
            "project_id": attempt["project_id"], "program_version": attempt["program_version"], "work_id": attempt["work_id"],
            "cycle_id": attempt["cycle_id"], "attempt_id": attempt["attempt_id"], "parent_runtime_id": attempt["parent_runtime_id"],
            "role": attempt["role"], "requested_model": attempt["requested_model"], "fabric_manifest_digest": attempt["fabric_manifest_digest"],
            "phase2_contract_digest": attempt["phase2_contract_digest"], "nonce": uuid.uuid4().hex,
            "issued_at": _iso(issued), "expires_at": _iso(issued + timedelta(minutes=4)),
        }
        return self._sign(claims), {"raw_path": raw_path, "raw_sha": _bytes_digest(raw_bytes), "event": event, "task_id": task, "model": info.get("model"), "provider_time": info["provider_time"], "payload": info["payload"], "sequence": sequence, "terminal": bool(info.get("terminal"))}

    def _unknown(self, request: dict[str, Any], request_digest: str, sequence: int) -> tuple[dict[str, Any], dict[str, Any]]:
        info = {"task_id": None, "model": None, "provider_time": _iso(self.now), "raw_sha": "", "payload": {"provider_status": "launch_unknown", "usage": None}}
        return self._record(request, request_digest, "launch_unknown", info, sequence)

    def handle(self, signed_command: dict[str, object], *, transport: object) -> dict[str, object]:
        self._boundary()
        if getattr(transport, "fixture_only", None) is not True or any(not callable(getattr(transport, name, None)) for name in ("create", "retrieve", "cancel")):
            raise ResponsesGatewayError("fixture transport is not explicitly fixture-only")
        claims, request, request_digest, command_digest, request_key_fingerprint = self._verify_command(signed_command)
        # Validate the distinct signing authority before creating a tombstone
        # or crossing the fixture transport boundary.
        _, gateway_key_fingerprint = self._gateway_key()
        if request_key_fingerprint == gateway_key_fingerprint:
            raise ResponsesGatewayError("request verification and result signing keys must be distinct")
        lock_path = self.state_path.with_name(self.state_path.name + ".lock")
        lock_flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(str(lock_path), lock_flags, 0o600)
            lock_stat = os.fstat(descriptor)
        except OSError:
            raise ResponsesGatewayError("fixture lock is unsafe") from None
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != os.getuid() or lock_stat.st_mode & 0o777 != 0o600:
            os.close(descriptor)
            raise ResponsesGatewayError("fixture lock is unsafe")
        try:
            os.chmod(lock_path, 0o600)
            with os.fdopen(descriptor, "r+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                state = self._load_state()
                nonce = claims["nonce"]
                prior_nonce = state["nonces"].get(nonce)
                if prior_nonce is not None and prior_nonce != command_digest:
                    raise ResponsesGatewayError("command nonce was already used")
                command = state["commands"].get(request_digest)
                if command is not None:
                    if command.get("command_digest") != command_digest:
                        raise ResponsesGatewayError("changed duplicate command conflicts")
                    if isinstance(command.get("result"), dict):
                        return command["result"]
                attempt_id = request["attempt"]["attempt_id"]
                entry = state["attempts"].get(attempt_id)
                operation = request["operation"]
                if entry is not None and (
                    entry.get("attempt_identity") != request["attempt"]
                    or entry.get("attempt_identity_digest") != _digest(request["attempt"])
                ):
                    raise ResponsesGatewayError("runtime attempt identity conflicts with retained admission")
                if operation == "launch":
                    if entry is not None:
                        if entry.get("request_digest") != request_digest:
                            raise ResponsesGatewayError("attempt launch conflicts")
                        if entry.get("status") == "raw_retained":
                            result, details = self._finish_retained(request, request_digest, entry)
                        elif entry.get("status") in {"launching", "launch_unknown"}:
                            result, details = self._unknown(request, request_digest, int(entry.get("sequence", 0)) + 1)
                            entry["status"] = "launch_unknown"
                        else:
                            raise ResponsesGatewayError("attempt launch state is invalid")
                    else:
                        entry = {"request_digest": request_digest, "status": "launching", "sequence": 0, "provider_task_id": None, "terminal": False, "attempt_identity": request["attempt"], "attempt_identity_digest": _digest(request["attempt"])}
                        state["attempts"][attempt_id] = entry
                        state["nonces"][nonce] = command_digest
                        self._write_state(state)  # durable pre-effect launch tombstone
                        try:
                            raw = transport.create(_canonical({"background": True, "input": FIXED_INPUT, "model": request["attempt"]["requested_model"], "store": False, "tools": []}).encode("utf-8"))
                        except Exception:
                            result, details = self._unknown(request, request_digest, 1)
                            entry["status"] = "launch_unknown"
                        else:
                            artifact_snapshot = self._artifact_snapshot()
                            try:
                                info = self._provider(
                                    raw, request, operation, None, retain=False
                                )
                                if any(
                                    other_id != attempt_id and other.get("provider_task_id") == info["task_id"]
                                    for other_id, other in state["attempts"].items()
                                    if isinstance(other, dict)
                                ):
                                    raise ResponsesGatewayError("provider task is already bound")
                                info = self._retain_provider(info, raw)
                                result, details = self._record(request, request_digest, "launch", info, 1)
                            except Exception as exc:
                                # The provider effect may already exist even when its
                                # returned identity or retained evidence is invalid.
                                # Persist the terminal transport ambiguity now; a
                                # later exact replay must never call create again.
                                self._persist_launch_unknown_after_effect(
                                    state=state,
                                    entry=entry,
                                    artifact_snapshot=artifact_snapshot,
                                )
                                if isinstance(exc, ResponsesGatewayError):
                                    raise
                                raise ResponsesGatewayError(
                                    "provider create outcome is ambiguous"
                                ) from None
                            # Persist identity and exact raw evidence first.  The optional fault
                            # seam deliberately leaves this state without a signed result.
                            entry.update({"status": "raw_retained", "provider_task_id": info["task_id"], "model": info["model"], "sequence": 1, "raw_retained": details, "terminal": bool(info["terminal"])})
                            try:
                                self._write_state(state)
                            except ResponsesGatewayError:
                                self._persist_launch_unknown_after_effect(
                                    state=state,
                                    entry=entry,
                                    artifact_snapshot=artifact_snapshot,
                                )
                                raise ResponsesGatewayError(
                                    "provider create outcome is ambiguous after identity retention failure"
                                ) from None
                            fault = getattr(transport, "fixture_fault_after_raw_retain", None)
                            if isinstance(fault, BaseException):
                                raise fault
                            entry["status"] = "terminal" if info["terminal"] else "active"
                    entry["sequence"] = details["sequence"]
                elif operation == "query":
                    if entry is None or entry.get("status") not in {"launching", "launch_unknown"}:
                        raise ResponsesGatewayError("query cannot reconcile this fixture attempt")
                    result, details = self._unknown(request, request_digest, int(entry.get("sequence", 0)) + 1)
                    entry["status"] = "launch_unknown"
                    entry["sequence"] = details["sequence"]
                else:
                    if entry is None or entry.get("provider_task_id") != request.get("provider_task_id"):
                        raise ResponsesGatewayError("operation task binding is invalid")
                    if operation == "cancel" and entry.get("cancel_unknown"):
                        raise ResponsesGatewayError("fixture cancellation remains terminally ambiguous")
                    if operation == "cancel" and entry.get("cancel_intent") and entry.get("cancel_result") is None:
                        # The process may have stopped after persisting intent and
                        # before a durable response.  A second provider cancel is
                        # unsafe because the first may already have taken effect.
                        entry["status"] = "cancel_unknown"
                        entry["cancel_unknown"] = True
                        entry["cancel_request_digest"] = request_digest
                        self._write_state(state)
                        raise ResponsesGatewayError("fixture cancellation remains terminally ambiguous")
                    if operation == "cancel" and entry.get("cancel_result") is not None:
                        if entry.get("cancel_request_digest") != request_digest:
                            raise ResponsesGatewayError("changed duplicate cancellation conflicts")
                        return entry["cancel_result"]
                    if operation == "observe" and command is not None and isinstance(command.get("result"), dict):
                        return command["result"]
                    if operation == "observe" and entry.get("terminal"):
                        result, details = self._finish_retained(request, request_digest, entry)
                        state["nonces"][nonce] = command_digest
                        state["commands"][request_digest] = {"command_digest": command_digest, "result": result}
                        self._write_state(state)
                        return result
                    if operation == "cancel":
                        entry["cancel_intent"] = True
                        entry["cancel_command_digest"] = command_digest
                        self._write_state(state)
                        try:
                            raw = transport.cancel(entry["provider_task_id"])
                            info = self._provider(raw, request, operation, entry["provider_task_id"])
                            event = "terminal" if info["terminal"] else "cancel_acknowledged"
                            result, details = self._record(request, request_digest, event, info, int(entry.get("sequence", 0)) + 1)
                        except BaseException:
                            # A cancel may have reached the provider; do not retry or
                            # serialize transport diagnostics (which may contain secrets).
                            entry["status"] = "cancel_unknown"
                            entry["cancel_unknown"] = True
                            entry["cancel_request_digest"] = request_digest
                            self._write_state(state)
                            raise ResponsesGatewayError("fixture cancellation outcome is ambiguous") from None
                    else:
                        raw = transport.retrieve(entry["provider_task_id"])
                        info = self._provider(raw, request, operation, entry["provider_task_id"])
                        event = "terminal" if info["terminal"] else "running"
                        result, details = self._record(request, request_digest, event, info, int(entry.get("sequence", 0)) + 1)
                    entry.update({"sequence": details["sequence"], "raw_retained": details, "terminal": bool(info["terminal"])})
                    if operation == "cancel":
                        entry["cancel_result"] = result
                        entry["cancel_request_digest"] = request_digest
                state["nonces"][nonce] = command_digest
                state["commands"][request_digest] = {"command_digest": command_digest, "result": result}
                entry["result"] = result
                self._write_state(state)
                return result
        finally:
            # fdopen owns descriptor on the normal path; only close it if opening the wrapper failed.
            try:
                os.close(descriptor)
            except OSError:
                pass

    def _finish_retained(self, request: dict[str, Any], request_digest: str, entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        details = entry.get("raw_retained")
        if not isinstance(details, dict):
            raise ResponsesGatewayError("retained raw fixture evidence is invalid")
        raw_path = self.artifact_root / str(details.get("raw_path", ""))
        if raw_path.resolve().parent != self.artifact_root.resolve() or not raw_path.is_file() or raw_path.is_symlink():
            raise ResponsesGatewayError("retained raw fixture evidence is missing")
        _owner_only(raw_path, mode=0o600, kind=stat.S_ISREG)
        try:
            raw_bytes = raw_path.read_bytes()
            raw = observations.load_json_bytes_strict(raw_bytes)
        except (OSError, ValueError) as exc:
            raise ResponsesGatewayError("retained normalized fixture evidence is invalid") from exc
        if _bytes_digest(raw_bytes) != details.get("raw_sha") or not isinstance(raw, dict) or set(raw) != runtime_gateway.RAW_FIELDS:
            raise ResponsesGatewayError("retained normalized fixture evidence is invalid")
        payload = details.get("payload")
        attempt = entry.get("attempt_identity")
        expected = {
            "provider": attempt.get("provider") if isinstance(attempt, dict) else None,
            "surface": attempt.get("surface") if isinstance(attempt, dict) else None,
            "account": attempt.get("account") if isinstance(attempt, dict) else None,
            "provider_task_id": details.get("task_id"),
            "event_type": details.get("event"),
            "provider_sequence": details.get("sequence"),
            "provider_timestamp": details.get("provider_time"),
            "observed_model": details.get("model"),
            "payload": payload,
        }
        if any(raw.get(field) != value for field, value in expected.items()):
            raise ResponsesGatewayError("retained normalized fixture evidence is invalid")
        if isinstance(payload, dict) and "provider_raw_artifact_path" in payload:
            source_path = self.artifact_root / str(payload.get("provider_raw_artifact_path"))
            if source_path.resolve().parent != self.artifact_root.resolve() or not source_path.is_file() or source_path.is_symlink():
                raise ResponsesGatewayError("retained provider fixture evidence is missing")
            _owner_only(source_path, mode=0o600, kind=stat.S_ISREG)
            try:
                source_bytes = source_path.read_bytes()
                source_value = observations.load_json_bytes_strict(source_bytes)
            except (OSError, ValueError) as exc:
                raise ResponsesGatewayError("retained provider fixture evidence is invalid") from exc
            if not isinstance(source_value, dict) or _bytes_digest(source_bytes) != payload.get("provider_raw_sha256") or len(source_bytes) != payload.get("provider_raw_size"):
                raise ResponsesGatewayError("retained provider fixture evidence is invalid")
        # Reconstruct only from byte-audited normalized facts.
        info = {"task_id": details.get("task_id"), "model": details.get("model"), "provider_time": details.get("provider_time"), "payload": payload, "raw_sha": details.get("raw_sha"), "terminal": bool(details.get("terminal"))}
        event = details.get("event")
        if event not in {"launch", "running", "terminal", "cancel_acknowledged"}:
            raise ResponsesGatewayError("retained raw fixture evidence is invalid")
        sequence = int(details.get("sequence", 0))
        if request.get("operation") == "observe" and details.get("terminal"):
            # The original create remains a launch fact.  A later observation
            # of the retained terminal raw evidence is a distinct terminal
            # fact, without another transport call.
            event = "terminal"
            sequence += 1
        result, new_details = self._record(request, request_digest, event, info, sequence)
        entry["status"] = "terminal" if details.get("terminal") else "active"
        entry["terminal"] = bool(details.get("terminal"))
        entry["result"] = result
        return result, new_details

    def attest_receipt(self, *, attempt: dict[str, object], provider_task_id: str, receipt_payload_hash: str) -> dict[str, object]:
        self._boundary()
        _sha(receipt_payload_hash, "receipt_payload_hash")
        _text(provider_task_id, "provider_task_id")
        if not isinstance(attempt, dict):
            raise ResponsesGatewayError("attempt is invalid")
        entry = self._load_state().get("attempts", {}).get(attempt.get("attempt_id"))
        if not isinstance(entry, dict) or entry.get("provider_task_id") != provider_task_id or not entry.get("terminal"):
            raise ResponsesGatewayError("terminal provider evidence is required before receipt attestation")
        identity = entry.get("attempt_identity")
        if not isinstance(identity, dict) or any(attempt.get(field) != identity.get(field) for field in runtime_gateway.IMMUTABLE_ATTEMPT_FIELDS):
            raise ResponsesGatewayError("receipt attempt identity differs from retained admission")
        lifecycle = attempt.get("lifecycle")
        if (
            not entry.get("cancel_intent")
            or not isinstance(entry.get("cancel_command_digest"), str)
            or not entry["cancel_command_digest"]
            or not isinstance(lifecycle, dict)
            or set(lifecycle) != set(runtime_lifecycle.empty_lifecycle())
            or lifecycle.get("status") != "cancelled"
            or lifecycle.get("terminal_status") != "cancelled"
            or lifecycle.get("provider_task_id") != provider_task_id
            or lifecycle.get("terminal_authority") != "provider_observation"
            or not isinstance(lifecycle.get("cancellation"), dict)
        ):
            raise ResponsesGatewayError("receipt attribution is not eligible")
        try:
            lifecycle_errors = runtime_lifecycle.audit_attempt(
                attempt,
                keyring_path=self.gateway_keyring_path,
                decision_public_key_path=self.decision_public_key_path,
            )
        except ValueError as exc:
            raise ResponsesGatewayError("cancelled lifecycle authority is invalid") from exc
        if lifecycle_errors:
            raise ResponsesGatewayError("cancelled lifecycle authority is invalid")
        terminal_result = entry.get("result")
        terminal_claims = (
            terminal_result.get("claims")
            if isinstance(terminal_result, dict)
            else None
        )
        if (
            not isinstance(terminal_claims, dict)
            or terminal_claims.get("event_type") != "terminal"
            or terminal_claims.get("provider_task_id") != provider_task_id
            or lifecycle.get("terminal_observation_digest") != _digest(terminal_claims)
            or lifecycle.get("terminal_provider_event_id")
            != terminal_claims.get("provider_event_id")
        ):
            raise ResponsesGatewayError("cancelled lifecycle does not bind terminal gateway evidence")
        details = entry.get("raw_retained")
        if not isinstance(details, dict):
            raise ResponsesGatewayError("terminal raw evidence is missing")
        raw_path = self.artifact_root / str(details.get("raw_path", ""))
        if raw_path.resolve().parent != self.artifact_root.resolve() or not raw_path.is_file() or raw_path.is_symlink():
            raise ResponsesGatewayError("terminal raw evidence is invalid")
        _owner_only(raw_path, mode=0o600, kind=stat.S_ISREG)
        try:
            raw_bytes = raw_path.read_bytes()
            raw = observations.load_json_bytes_strict(raw_bytes)
        except (OSError, ValueError) as exc:
            raise ResponsesGatewayError("terminal raw evidence is invalid") from exc
        if not isinstance(raw, dict) or set(raw) != runtime_gateway.RAW_FIELDS or _bytes_digest(raw_bytes) != details.get("raw_sha") or raw.get("provider_task_id") != provider_task_id or raw.get("payload") != details.get("payload"):
            raise ResponsesGatewayError("terminal raw evidence is invalid")
        payload = raw["payload"]
        if not isinstance(payload, dict):
            raise ResponsesGatewayError("terminal raw evidence is invalid")
        source_path = self.artifact_root / str(payload.get("provider_raw_artifact_path", ""))
        if source_path.resolve().parent != self.artifact_root.resolve() or not source_path.is_file() or source_path.is_symlink():
            raise ResponsesGatewayError("terminal provider raw evidence is invalid")
        _owner_only(source_path, mode=0o600, kind=stat.S_ISREG)
        try:
            source_bytes = source_path.read_bytes()
            source_value = observations.load_json_bytes_strict(source_bytes)
        except (OSError, ValueError) as exc:
            raise ResponsesGatewayError("terminal provider raw evidence is invalid") from exc
        if not isinstance(source_value, dict) or _bytes_digest(source_bytes) != payload.get("provider_raw_sha256") or len(source_bytes) != payload.get("provider_raw_size"):
            raise ResponsesGatewayError("terminal provider raw evidence is invalid")
        claims = {"schema": RECEIPT_SCHEMA, "gateway_key_id": self.gateway_key_id, "action": "attest-runtime-receipt", "project_id": attempt.get("project_id"), "attempt_id": attempt.get("attempt_id"), "provider_task_id": provider_task_id, "receipt_payload_hash": receipt_payload_hash, "nonce": uuid.uuid4().hex, "issued_at": _iso(self.now), "expires_at": _iso(self.now + timedelta(minutes=4))}
        return self._sign(claims)
