# First Reality Contract

The First Reality Contract is a strict subset of the final product contract. It proves one connected user journey without allowing deferred final-scope capabilities to block R3.

Required fields:

```json
{
  "$schema": "company-os.first-reality-contract.v1",
  "objective_id": "objective",
  "journey_id": "first connected journey",
  "journey_steps": ["observable step"],
  "required_capability_ids": ["capability"],
  "required_artifact_class_ids": ["artifact class"],
  "required_observations": ["runtime evidence"],
  "deferred_capability_ids": ["final scope capability"],
  "deadline_fraction": 0.25,
  "contract_sha256": "content digest"
}
```

Candidate one is complete only when every first-reality artifact and observation exists. Deferred capabilities remain mandatory for final user usability and independent acceptance.

After R3, the controller expands scope in dependency order while preserving the working journey.
