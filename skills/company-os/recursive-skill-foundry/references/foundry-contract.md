# Recursive Skill Foundry Contract

## Storage

All mutable foundry state is project isolated under `.company-os/skill-foundry`.

Candidate versions live at:

```text
.company-os/skill-foundry/candidates/<skill-name>/vNNNN/
  candidate.json
  validation.json
  simulation.json
  skill/<skill-name>/SKILL.md
```

Accepted project skills install under `.agents/skills/<skill-name>` unless an explicitly allowed `.codex/skills` root is chosen.

## Candidate invariants

1. Candidate metadata is content addressed.
2. The skill manifest covers every regular installable file.
3. Symlinks, traversal, absolute paths, unsupported top level folders, and oversized skills fail closed.
4. Candidate versions are append only.
5. Iteration creates a new version and binds the prior candidate digest.
6. A failing case is preserved under `examples/` before repair.

## Recursion invariants

1. Maximum depth is three.
2. Maximum nodes is twelve.
3. Names are unique.
4. Ancestor cycles and self dependency are rejected.
5. Child skills inherit narrower scope and authority.
6. The coordinator manifest binds exact component digests.

## Promotion invariants

1. Validation and simulation must pass.
2. Explicit skill requests may promote project locally after deterministic checks.
3. Learned mechanisms require two accepted independent run receipts.
4. Rejected field evidence blocks promotion.
5. Core promotion is not implemented as an automatic foundry action.
6. Registry and installed bytes are content addressed and verified before assignment.
7. One packet may assign at most four project skills.

## Navigation integration

Skill creation does not move the active product objective unless the original destination is a skill or the route is concretely blocked by the missing reusable capability. In every other case, capture learning after the product checkpoint. Research, abstraction, and documentation do not outrank the current actuator.
