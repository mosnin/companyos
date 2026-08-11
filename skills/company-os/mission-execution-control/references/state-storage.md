# Mission State Storage

The canonical mission state is stored under the objective workspace and sealed by SHA-256. Updates are atomic at the director boundary.

Recommended paths:

```text
.company-os/outcomes/<objective>/mission-execution-state.json
.company-os/outcomes/<objective>/first-reality-contract.json
.company-os/outcomes/<objective>/governor-decision.json
.company-os/outcomes/<objective>/work-admissions/
.company-os/outcomes/<objective>/scheduler/
.company-os/outcomes/<objective>/checkpoints/
```

Every fabric binds the exact mission state and governor decision digests. Stale fabrics fail verification.
