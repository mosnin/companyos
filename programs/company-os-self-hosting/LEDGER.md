# Company OS Self-Hosting Ledger

## Current checkpoint

- Canonical repository: `/Users/preston/Documents/Codex/company-os-core`
- Distribution version: `0.1.0`
- Imported controller: schema 8 / core 2.5
- Client work: frozen; Chippy is not an implementation target
- Recurring automation: disabled
- Production or customer effects: none

## Accepted evidence

### Phase 0 — canonical source acceptance candidate

- The previously unversioned Company OS and Autonomy Suite sources were copied
  byte-for-byte into one dedicated Git repository outside all client projects.
- A content-addressed distribution manifest covers both complete skill bundles.
- The installer stages and hashes every file, refuses a changed installation by
  default, restores the prior bundle if atomic replacement fails, and supports
  a read-only installed-source comparison.
- Clean bootstrap creates an isolated project instance and proves it remains
  fail-closed without reality, direction, evidence, issuer, or launcher gates.
- The project-local Gate 2 verifier is preserved under `reference/` and is
  explicitly unintegrated and feature-off.

Verification on 2026-08-01:

- Repository distribution/bootstrap tests: 4/4 pass.
- Canonical controller regression: 98/98 pass.
- Observation-gateway reference: 10/10 pass.
- Luna Execution Fabric validator self-test: pass.
- Python compilation: pass.
- Distribution manifest: verified.

## Not yet implemented

- Transactional durable control state.
- Canonical observation ingestion and lifecycle state.
- Provider launch or provider-observed identity.
- Real Sol manager or GPT-5.6 Luna worker execution.
- Heartbeats, terminal receipts, cancellation propagation, telemetry, or
  reconciliation from a provider.
- Self-hosted accepted capability or adaptation cycle.
- Protected launcher, external issuer deployment, or recurring scheduling.

## Exact next action

Integrate the accepted observation-gateway mechanics into the canonical
controller as a new feature-off schema slice. Retain the complete adversarial
matrix, add governed attempt lifecycle state without provider launch, and
independently reject any mutation or identity gap before moving to the durable
database adapter.
