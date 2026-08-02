# Phase 2 Fixture-Only OpenAI Responses Gateway — Implementation Contract

## Status and boundary

`CONTRACT_ONLY / FIXTURE_ONLY / FEATURE_OFF / RUNTIME_NO_GO`

This is the smallest provider-specific adapter permitted after
`PHASE_2_CONNECTOR_FEASIBILITY.md`.  It is a testable protected boundary for
the OpenAI Responses API.  It is **not** controller integration, a scheduler,
a deployment, a credential-provisioning mechanism, or evidence of a real
provider run.  It must never read ambient credentials, make a network call,
start a listener, or enable a feature flag in this phase.

The fixture adapter exists to turn a signed, admitted Company OS request into
a deterministic signed gateway result that the existing
`runtime_gateway.py`, `runtime_observations.py`, and `runtime_receipts.py`
verifiers can consume without changing their trust model.

## Required module and public interface

Add exactly one feature-off module at:

`skills/company-os/elastic-company-os/scripts/openai_responses_gateway.py`

It must expose:

```python
class ResponsesGatewayError(ValueError): ...

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
    ) -> None: ...

    def handle(
        self,
        signed_command: dict[str, object],
        *,
        transport: object,
    ) -> dict[str, object]: ...
```

`handle()` accepts an envelope with exactly `claims` and `signature`.
`claims` binds `gateway_request`, a canonical request digest, an issuer key
ID, nonce, issue time, and expiry.  The request must be an exact valid result
of `runtime_gateway.build_request`; its existing external admission-grant
token/digest is retained unchanged.  The gateway must verify the envelope
against the request keyring before it writes a tombstone or invokes the
fixture transport.

The command claims have exactly these fields:

```text
schema, request_key_id, gateway_request, gateway_request_digest,
nonce, issued_at, expires_at
```

`schema` is `company-os.openai-responses-gateway-command.v1`.  The request
keyring uses `company-os.openai-responses-request-keyring.v1` and the same
strict active-key, validity-window, RSA-SHA256, canonical-JSON, and
base64url-signature rules as the established observation gateway keyring.

The returned value is exactly the signed-result envelope accepted by
`runtime_gateway.verify_result()`: `{"claims": ..., "signature": ...}`. It
is signed with the gateway key, never with the request/decision key.

The fixture `transport` is injected, must carry the exact immutable marker
`fixture_only = True`, and has only these callable methods:

```python
transport.create(request_body: bytes) -> bytes
transport.retrieve(provider_task_id: str) -> bytes
transport.cancel(provider_task_id: str) -> bytes
```

Each method returns the raw UTF-8 JSON bytes that a real HTTP response would
have returned.  The adapter captures those bytes before parsing.  It must not
accept a decoded mapping in their place.  An unmarked transport is rejected
before state mutation or method invocation.  This module contains no HTTP
client, URL, API-key lookup, or network implementation.

## Filesystem and socket boundary

The adapter validates a local, testable boundary before any effect:

- `socket_path` is an existing Unix-domain socket, not a regular file, symlink,
  directory, or network address; its mode permits access only to the owner
  (`0o600` or stricter).
- `state_path` and `artifact_root` resolve under the same dedicated fixture
  root.  Symlink/path traversal and artifact paths outside that root reject.
- state, lock, and raw artifact files are owner-only (`0o600`); the artifact root is
  owner-only (`0o700`).
- no secret, private key, credential, authorization header, or provider token
  may be serialized into state, raw artifact, result claims, signature, or
  exception text.

The gateway private key may be read only by the signing operation.  Its public
key is supplied through the existing gateway keyring to Company OS.  Before
signing, the adapter verifies that the configured key ID is active at the
injected clock and that the private key matches that exact public key. Request
verification and result signing use cryptographically distinct normalized
public-key material, not merely different paths or key IDs; key substitution
fails before state mutation. The explicit `decision_public_key_path` pins the
issuer used to replay retained cancellation grants and is never read from
ambient configuration.

## Durable command semantics

State is canonical JSON and atomic replace after fsync, under an owner-only
exclusive file lock that serializes duplicate or concurrent commands. It records only
non-secret identifiers, command/request digests, lifecycle status, raw
artifact metadata, and result digest.  It starts empty and is scoped to the
fixture root.

| Operation | Required transition | Idempotency rule |
| --- | --- | --- |
| `launch` | Persist `launching` tombstone before `transport.create` | Exact replay returns retained signed result. A changed replay conflicts. |
| ambiguous create | Persist `launch_unknown` in the same call when no valid response ID was durably retained, including returned-byte validation or retention failure after the possible effect | It never calls `create` again. Automatic transport reconciliation is terminally blocked. |
| `query` after `launch_unknown` | Return the retained blocked `launch_unknown` result without transport | A task with no durable Response ID cannot be retrieved. Only a future separately authorized, cryptographically proven external reconciliation may introduce an ID; that surface is out of scope. |
| `observe` | Use `retrieve` only for its retained provider task ID | It cannot change the task or model. |
| `cancel` | Persist cancellation intent before `transport.cancel` | Repeated cancel returns the same canonical cancellation result. |
| late terminal success | Retain the exact provider success as terminal raw evidence | The gateway never rewrites provider truth. The existing lifecycle's authoritative cancellation state dominates that late success, so it cannot revive acceptance. |

A connection/error after `create` but before a valid `response.id` is atomically
retained is not a retryable launch failure.  It is `launch_unknown`.  The
adapter cannot infer, search for, or create another task ID.

## Exact request and response bindings

For `launch`, the request body sent to the fixture must be byte-canonical JSON
with exactly these material constraints:

```json
{
  "model": "gpt-5.6-sol or gpt-5.6-luna exactly as admitted",
  "input": "Return exactly READY. Do not call tools or perform external actions.",
  "background": true,
  "store": false,
  "tools": []
}
```

Those are the exact five request keys. The fixed read-only input and its digest
are part of the implementation contract; work instructions cannot be injected
through this canary. No aliases, fallback models, tool definitions, hosted
tools, background false, storage true, URLs, headers, or credentials are
permitted.

Raw Responses JSON must be retained byte-for-byte and decoded strictly (UTF-8,
duplicate keys and non-finite constants rejected). A valid provider record has
all of:

The `responses-fixture-no-tools-v1` shape below is an explicit minimal fixture
schema for this canary. It is not represented as the complete live Responses
API object, and live provider compatibility remains a separate runtime gate.

- exact `responses-fixture-no-tools-v1` top-level fields only: `id`, `object`,
  `created_at`, `status`, and `model`, plus `completed_at` and `usage` only for
  a terminal status; `object` is exactly `response` and unknown fields reject;
- non-empty `id` bound as `provider_task_id`;
- non-empty returned `model` exactly equal to `requested_model`;
- non-empty provider `status` mapped deterministically to the existing event
  and lifecycle vocabulary;
- numeric Unix `created_at` and, for terminal responses, numeric Unix
  `completed_at`, converted to canonical UTC only after their exact source
  bytes are retained; provider timestamps remain distinct from gateway ISO
  sent/received/signed timestamps;
- a required terminal `usage` object with exactly the versioned input/output/
  total token fields and their exact cached/cache-write/reasoning detail fields,
  all non-negative integers. Every admitted number is validated through one
  schema-wide rule: booleans and numeric strings reject, total tokens equal
  input plus output, cached plus cache-write tokens cannot exceed input, and
  reasoning tokens cannot exceed output;
- a SHA-256 digest and size calculated directly from the captured provider
  bytes, plus a separate normalized `RAW_FIELDS` projection whose signed
  payload binds that provider-byte digest.

Missing/inconsistent identity, status, timestamps, or terminal usage fails
closed. Requested model never fills a missing observed model. A returned model
mismatch has no signed success envelope, no task admission, and no receipt.
Provider-shaped credentials (`access_token`, `client_token`, `provider_token`,
`bearer_token`, authorization fields, and Bearer/Basic credential values) fail
before raw retention. Legitimate token counts are permitted only at the exact
contracted `usage` paths; transformed/redacted evidence is never mislabeled as
the exact provider response. Duplicate provider-task identity is also rejected
before retaining the conflicting body.

## Existing verifier compatibility

The adapter emits `company-os.runtime-gateway-result.v1` records compatible
with `runtime_gateway.verify_result()`, and raw artifacts with the exact
`RAW_FIELDS` shape expected there.  It emits only the existing
`launch`, `launch_unknown`, `running`, `heartbeat`, `cancel_acknowledged`, and
`terminal` event vocabulary. Provider status and usage are nested in the raw
`payload`, retaining the exact source facts required by lifecycle telemetry.

For receipt attribution, the gateway exposes a fixture-only helper to sign a
`company-os.runtime-receipt-attestation.v1` envelope using the same distinct
gateway signing key. It binds the exact `attempt_id`, `provider_task_id`,
receipt payload hash, key ID, nonce, issue time, and expiry required by
`runtime_gateway.verify_receipt_attestation()`. The helper rejects until the
gateway has retained exact terminal raw bytes with exact terminal usage for
that task.

The Responses object supplies token usage, not authoritative dollar cost. The
adapter therefore retains the exact provider `usage` object as
`provider_usage`, emits `cost_status: unavailable`, and emits no numeric
`cost_usd`. It must never invent `$0`. A successful completion receipt remains
NO-GO until a separate signed, versioned pricing attestation or provider
billing record supplies conservative cost. This phase can attest a cancelled
terminal receipt only when the exact admitted identity's entire lifecycle
deterministically replays from retained signed gateway observations and a full
cancellation decision grant verifies against the explicitly pinned decision
issuer. The replay binds the exact project, program, work, cycle, attempt,
provider task, capabilities, terminal event, and cancellation payload.
Caller-supplied claims or an otherwise valid grant without a replay-valid
lifecycle are insufficient. Because this fixture deliberately lacks
authoritative priced usage, no current fixture path is expected to satisfy the
full receipt gate. A caller-supplied success state can never override
cancellation.

```python
gateway.attest_receipt(
    *,
    attempt: dict[str, object],
    provider_task_id: str,
    receipt_payload_hash: str,
) -> dict[str, object]
```

## Mandatory negative and fault behaviour

All failure paths are fail-closed and leave the previously committed state
byte-equivalent unless their explicitly required tombstone is the transition:

- unsigned, expired, future-skewed, replayed, malformed, wrong-key, or
  signature-substituted command;
- regular/symlink/world-readable socket or state/artifact path;
- secret-bearing command, result, fixture bytes, or exception string;
- malformed/raw-tampered/duplicate-key provider bytes;
- changed duplicate command, duplicate provider task, or task substitution;
- model alias/mismatch, missing model/ID/status/timestamp/usage, negative or
  non-integer usage, or decreasing terminal evidence;
- create crash before effect, after effect before ID persistence, after exact
  bytes before signed-result persistence, and signed result replay after
  restart;
- duplicate poll/cancel, late completion after cancellation, cancellation
  acknowledgement mismatch, and cancellation replay;
- ambiguous cancel after a possible provider effect, retained as
  `cancel_unknown` with no automatic repeated cancel;
- gateway signing-key rotation, retired/unknown key, request-key substitution,
  signature tamper, expiry, nonce replay, and clock skew.

No test fixture is runtime proof.  A direct real API integration, credential
provisioning, provider error/cancellation fault evidence, and controller
integration each remain separate acceptance work.

The deterministic fixture transport may expose the non-callable
`fixture_fault_after_raw_retain` test attribute. When present, the adapter
raises that injected `BaseException` only after the exact provider bytes and
their identity metadata are durably retained but before the signed result is
persisted. On restart, the adapter must finish the signed result from those
retained bytes without another provider call. This test-only fault seam does
not authorize a network transport or runtime listener.
