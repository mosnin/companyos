# Company OS Capability Library

## Outcome

Company OS can discover thousands of external skills without placing their
instructions in the master, manager, or worker context. A Sol manager selects a
small exact bundle for a bounded outcome; Program Preflight binds that bundle;
the worker reads only the verified entrypoints it was assigned.

This is an additive capability plane. It does not alter the Company OS
master-manager-worker hierarchy, authority model, budgets, cancellation,
ownership, evidence, or acceptance barriers.

## Control flow

```text
pinned source evidence
        |
        v
metadata catalog ---- search ----> manager selection + rationale
        |                              |
        |                              v
        +------------------------> deterministic resolver
                                       |
                                       v
                           content-addressed assignment
                                       |
                                       v
                         deterministic host augmentation
                                       |
                                       v
                             Program Preflight packet
                                       |
                                       v
                         worker loads exact entrypoints only
                                       |
                                       v
                         artifact oracle + manager inspection
```

The catalog is the control plane; skill bodies are the data plane. Search reads
only compact metadata. Assignment carries locators and hashes, never full skill
text. Source repositories and installers are untrusted input, not authority.

## Trust pipeline

1. **Pin:** resolve canonical repository, commit, tree, observation time, and
   license evidence.
2. **Inventory:** enumerate skill entrypoints and dependencies without running
   repository scripts or installers.
3. **Classify:** map capabilities to domains and allowed roles; identify tools,
   permissions, conflicts, external effects, and authority-override language.
4. **Decide:** mark each capability approved, reference-only, quarantined, or
   rejected. Missing redistribution authority blocks vendoring.
5. **Materialize:** write one independently reviewed standalone `SKILL.md`
   wrapper around the reusable mechanism. Catalog v1 rejects sibling sidecars
   and never executes upstream installers or copies unbound resources. Preserve
   source/license evidence and exact file hashes.
6. **Assign:** the manager explicitly selects no more than the accepted
   task-local limits and records one `execution_order`. Requested IDs remain a
   canonical set; order is a separate, packet-bound instruction. The resolver
   rejects implicit injection, incomplete or duplicate order, and authority
   widening.
7. **Bind:** reproduce every assignment from the installed approved catalog.
   Program Preflight requires request domains and permissions to match the
   accepted task definition, requires workers to narrow their parent manager,
   and emits one exact binding only in the matching packet.
8. **Verify:** verify the compiled packet and every local entrypoint before
   reading. Catalog v1 accepts standalone wrappers only, preventing unbound
   sidecar resources. Sibling packets must contain no assignment metadata.
9. **Accept:** judge the resulting business artifact, not the presence of a
   skill or a passing resolver check.

## Anti-bloat rules

- Metadata is searchable by a deterministic script; the catalog is not pasted
  into prompts.
- External skills default to explicit loading and at most four per task.
- A manager can select zero skills.
- Search results are capped and contain no procedural body.
- Overlapping skills require one chosen primary; conflicting skills fail. A
  compatible bundle follows its manager-chosen `execution_order`, and each
  wrapper forbids autonomous discovery of unassigned companions.
- Strategy and decision frameworks default to managers. Production procedures
  default to workers. A capability must explicitly allow both to cross roles.
- Worker skill assignments must fit the manager's accepted scope, domains,
  permissions, and budget, but their procedural bodies are not loaded into the
  manager packet.
- Domains and skill permissions are definition-owned authority, not values a
  capability request can grant itself.

## Security boundary

- Never run a remote installer, `curl | bash`, repository hook, or package
  command during ingestion.
- Never merge an external `CLAUDE.md`, `AGENTS.md`, or equivalent into Company
  OS control instructions.
- A skill cannot grant filesystem, network, credential, deployment, messaging,
  financial, legal, or production authority.
- Symlinks, path escapes, hash drift, unknown licenses, unpinned sources,
  quarantined content, role mismatch, permission widening, and assignment
  tampering fail closed.
- Cybersecurity capabilities require a bounded defensive charter and remain
  quarantined until their exact use surface is independently reviewed.

## Release stages

1. Source inventory and dispositions for every requested repository.
2. Catalog/resolver source acceptance with adversarial tests.
3. Curated skill materialization with license and byte-closure evidence.
4. Program Preflight integration and a compact manager-to-worker assignment.
5. Independent review and a real bounded deliverable challenge.
6. Global installation only after source acceptance; runtime activation and
   recurring scheduling remain separate decisions.
