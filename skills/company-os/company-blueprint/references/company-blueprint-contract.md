# Company Blueprint contract

The blueprint is the durable operating definition of one company. It is not a
prompt, transcript, credential file, or project status report.

## Compilation invariants

1. One company ID and monotonic blueprint version identify the definition.
2. Mission, thesis, customers, offers, objectives, metrics, authority, and
   prohibited actions are concrete before execution.
3. Archetypes seed an organization but never override explicit operator
   decisions.
4. Requested capabilities must be covered by selected department packs before
   manager dispatch.
5. Skills, tools, playbooks, assets, knowledge, and integrations remain
   distinct registries with explicit references.
6. Capacity is derived from accepted outcomes and DAGs. Active concurrency is
   a separate host and budget decision.
7. Database configuration names an environment variable. Secrets never enter
   the blueprint or compiled artifacts. JSON secret keys, URI userinfo, and
   PEM private keys are secret material.
8. Scheduled routines compile as planned desired state. Blueprint cadence IDs
   must name routines in the selected organization. Runtime activation is a
   separate governed decision.
9. Every compiled file is canonical JSON and content-addressed in one
   manifest. Verification requires that exact artifact set; an empty or
   partial manifest must not verify.
10. Recompiling identical inputs produces identical bytes.
11. Extra fields, duplicate unknown IDs, and conflicting department overrides
    fail closed before any compiled output is accepted.

## Operator intake

The master asks only questions that materially change the blueprint. At
minimum, resolve:

- What company is this, why does it exist, and what makes its thesis distinct?
- Which customers and painful jobs does it serve?
- What does it sell, how does it earn revenue, and what must it never become?
- What outcomes matter in the next horizon and how are they measured now?
- Which systems, repositories, data, assets, and integrations already exist?
- Which actions require approval and which are categorically prohibited?
- What brand, design, content, legal, and operating references are canonical?
- Which unknowns block execution, who owns them, and how will they be resolved?

The master reflects the compiled result to the operator before activating any
external effect or recurring routine.
