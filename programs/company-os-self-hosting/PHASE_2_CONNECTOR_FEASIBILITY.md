# Phase 2 Connector Feasibility

## Verdict

`DIRECT_RESPONSES_GATEWAY_DESIGN_GO / RUNTIME_NO_GO`

The smallest honest provider connector is a protected gateway that calls the
OpenAI Responses API directly. The current Codex CLI and app-server surfaces
are authenticated and expose task or turn usage, but they do not expose a
terminal provider Response object that binds the executed model. A requested
model, catalog entry, thread ID, or local process exit cannot be promoted to
provider-observed model evidence.

The official Responses object exposes the provider response ID, status, model,
timestamps, and usage. Background Responses can be retrieved and cancelled by
their bound response ID. These fields can satisfy the existing signed gateway
contract when their exact raw response bytes are retained and hashed.

Official references:

- <https://learn.chatgpt.com/docs/non-interactive-mode>
- <https://learn.chatgpt.com/docs/app-server>
- <https://developers.openai.com/api/docs/libraries/openai-cli#send-your-first-request>
- <https://developers.openai.com/api/docs/guides/background>

## Required gateway boundary

1. Run as an isolated process over a permission-restricted Unix socket.
2. Validate the signed Company OS request and persist a `launching` intent
   before contacting the provider.
3. Submit one exact `gpt-5.6-sol` or `gpt-5.6-luna` background Response with no
   tools for the first canary.
4. Capture and hash exact HTTP response bytes before parsing them.
5. Bind `response.id`, returned `response.model`, status, provider timestamps,
   total usage, raw digest, and gateway timestamps into the signed result.
6. Poll and cancel only by the retained response ID.
7. Keep the provider credential and signing key outside the repository and
   worker environment; Company OS receives only the gateway public key.
8. Reject aliases, missing model identity, missing usage, or any requested-
   versus-returned model mismatch.

## Ambiguous-launch rule

The inspected Responses documentation provides retrieve and cancel operations
for a known response ID, but no general recovery search for a create request
whose response ID was lost. A connection failure before durable retention of a
valid ID therefore becomes `launch_unknown`. It must never trigger a blind
relaunch. This preserves at-most-one behavior while requiring reconciliation
for a small class of ambiguous creates.

## Runtime acceptance matrix

Before enablement, the gateway must prove:

- one exact Sol and one exact Luna no-tool, read-only background canary;
- returned model, Response ID, terminal timestamps, usage, raw digest, and
  gateway signature;
- queued and in-progress cancellation plus exact repeated cancellation;
- model unavailable, permission, rate-limit, timeout, and provider 5xx paths;
- crash before request, after provider response, and before local persistence;
- connection loss before and after Response ID retention;
- duplicate launch/query/cancel, late completion after cancellation, raw-body
  tampering, signature substitution, expiry, replay, rotation, and clock skew.

## Current blocker

No dedicated Company OS OpenAI API credential is available in the current
process or repository environment. Chippy credentials are outside this
standalone program and remain frozen. The gateway can be implemented and
tested against signed fixtures, but live provider proof remains NO-GO until a
least-privilege, spend-limited Company OS credential is provisioned outside the
repository.
