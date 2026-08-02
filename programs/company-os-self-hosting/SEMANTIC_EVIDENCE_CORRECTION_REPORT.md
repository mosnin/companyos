# Company OS Semantic Evidence Correction

## Decision

Company OS 0.4.1 installed correctly, but its first canonical-install evidence
record contained a full Git commit value that did not resolve to the accepted
release. The immutable snapshot was byte-valid, so structural
`supersede-evidence` correctly refused to replace it. Certification remains
NO-GO until the false claim is retired through a separately governed semantic
transition.

## Bounded correction

`correct-evidence` supports exactly one correction type:
`git_commit_identity` at JSON path `/commit`.

The transition requires all of the following:

- a paused, unscheduled, lease-free, cycle-idle instance;
- one snapshot-backed, explicit `active: true`, current-program predecessor
  (legacy implicit-active records are rejected before grant verification or
  snapshot publication);
- a replacement JSON object that differs only at `/commit`;
- full lowercase 40-character old and new commit identifiers;
- a new identifier that resolves locally as the exact Git commit object;
- a signed correction declarant and a different, conflict-free signed
  adjudicator;
- a signed payload covering the complete predecessor-record digest, both
  immutable artifact hashes, both IDs, old/new values, typed claim path,
  locally verified commit result, the complete successor-record digest,
  signed transition timestamp, governance binding, and reason;
- no completed-cycle/work or accepted-fabric reference to the predecessor.

The transition archives the old bytes and record append-only as a
`semantic_retraction`, creates bidirectional lineage, clears any quality score
that cited the predecessor, invalidates certification, keeps scheduling off,
and commits the state, ordered event, and consumed grant nonces atomically.
Replacement bytes are published first to the immutable content store. If the
authoritative transaction is rejected afterward, its revision, event, exports,
and grant nonces remain unchanged; an unreferenced immutable blob may remain as
non-authoritative residue for future reference-aware garbage collection.

## Non-bypass properties

- Structural `supersede-evidence` remains unchanged and cannot replace a
  byte-valid record.
- The semantic command cannot modify arbitrary JSON fields.
- A reviewer involved in the predecessor or replacement cannot adjudicate the
  correction.
- Failed, replayed, tampered, terminal, or broader corrections cannot advance
  the authoritative SQLite revision.
- Audit reconstruction re-verifies the old/new byte delta, local Git object,
  canonical content-addressed paths, exact successor record, lineage,
  transition timestamps, retained grants, and signed correction payload—even
  after a later program archives the successor.

## Verification status

Focused unit tests cover accepted correction, immutable lineage, broader-edit
rejection, authority conflict, signed-payload substitution, terminal
references, audit tampering, and transactional command replay/conflict.
The complete release matrix and independent implementation review remain the
acceptance boundary before this command is used on authoritative Company OS
evidence.

## Non-claims

This change does not prove provider execution, GPT-5.6 Sol or Luna identity,
protected scheduling, multi-project runtime isolation, or Chippy onboarding.
