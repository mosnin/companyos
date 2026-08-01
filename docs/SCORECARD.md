# Company OS Scorecard

Scores are evidence-bound. Future-phase dimensions are not rounded up to make
the current stage appear operational.

## Phase 0 applicable dimensions

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Canonical source ownership | 9.0 | Dedicated Git repository; installed skills are distributions. |
| Project/client separation | 9.0 | Company OS source is outside Chippy and client work is frozen. |
| Distribution integrity | 9.0 | Content-addressed manifest and exact installed-source comparison. |
| Reproducible bootstrap | 9.0 | Clean temporary project initialization and fail-closed audit test. |
| Change safety | 9.0 | Existing changed installs reject by default; staged replacement rolls back; state/event pairs recover from a partial replace. |
| Test strength | 9.0 | Repository, 100-controller, 7 canonical-integration, 10 reference, validator, and compile gates. |
| Evidence truthfulness | 9.0 | Reference, canonical, mock, runtime, and client evidence remain distinct. |
| Documentation and handoff | 8.5 | Architecture, roadmap, program contracts, and append-only ledger are colocated. |

Phase 0 passes its applicable 8/10 gate.

## Operational dimensions — not passed

| Dimension | Current evidence state |
| --- | --- |
| Durable distributed control | Not implemented |
| Runtime execution | Not implemented |
| Sol manager orchestration | Not observed |
| GPT-5.6 Luna labor | Not observed |
| Provider identity and telemetry | Signed observation ingestion is locally verified; no real provider observation or telemetry |
| Cancellation and recovery | Contract only; no real runtime evidence |
| Recursive adaptation | Not exercised |
| Protected scheduling | Disabled |
| Cross-project promotion | No qualifying project evidence |

Company OS must not be called operational until these dimensions become
applicable, independently evidenced, and score at least 8/10. Security,
authority, durability, cancellation, and evidence integrity require 9/10.
