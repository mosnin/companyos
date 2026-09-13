# Reconcile orchestration alerts

Use `ContextLedgerClient.reconcile_alerts(packet, branch="existing-overlay")`
from the existing client after authorized source reads. This publishes a context
projection through `config_pull`, `schema_describe`, `document_get`, and
revision-checked `document_put`. It does not own dispatch or start polling.

The Company OS Web registry must expose `orchestration-alerts` version 1 with
its ten-column `alerts` table. The client checks the shape before writing and
reports an unavailable schema rather than attempting an incompatible commit.
Use the existing branch creation and merge authority process. A returned write
receipt is not a merge to main; the branch view shows the draft projection until
an authorized owner lands it. Do not claim the main view was updated from a draft.

Packet shape:

```json
{
  "schema": "company-os.alert-observations.v1",
  "instance_id": "company-instance",
  "now_s": 100,
  "max_age_s": 30,
  "events": [{
    "id": "ready-pr-42",
    "resource": "repository/pr/42",
    "owner": "canonical-worker-thread",
    "revision": "current-head-sha",
    "signal": "clear",
    "sequence": 2,
    "observed_at_s": 100,
    "evidence_ref": "native-source-read-reference"
  }]
}
```

These are fixture times; real packets use integer Unix seconds. The host assigns
monotonically increasing observation sequences per instance and alert using its
existing serialized records. Retries preserve the same sequence and payload.
Keep alert IDs stable across source revisions and owner reassignment, and bind
each ID to one resource. The host verifies company, resource, worker ownership,
and source evidence; the helper cannot authenticate these declarations.

For a ready-to-merge alert, `active` requires current checks, required review and
mergeability to support that condition. A definitively merged/closed PR or a fresh
failure of a required condition yields `clear`. An unavailable provider, failed
lookup, or unknown mergeability yields `unknown`, never `clear`. Other alert
classes likewise require explicit evidence that their triggering condition ended.
Do not turn a newer code revision alone into proof of a successful repair.

The projection keeps active, resolved, stale, and needs-verification states.
Only active means currently actionable. Missing observations do not resolve an
alert. Stale input cannot introduce an active alert or clear an existing one.
Other instances are preserved; old sequences cannot overwrite newer evidence.
A changed payload at the same sequence is an error requiring source reconciliation.
Resolved rows remain in the current register and all commits remain in history.

On revision conflict, reread the document and reconcile the same observations.
On timeout, inspect the branch head and compare the intended projection before
retrying. The helper deliberately propagates both errors without blind retries.
No-op observations do not create extra document revisions. Replacing a projection
or rolling back code must preserve delivery history and source ordering.

Local fixture validation covers the state transition and wire contract. Hosted
schema rollout, real authenticated writes/readback, and rendered branch/main views
are separate acceptance evidence. No background notification daemon or merge
authority is added by this procedure.
