# CI Policy

Permanent CI is verification only.

1. CI checks out the branch that triggered the run.
2. CI never patches source files.
3. CI never commits or pushes.
4. CI never targets a retired development branch.
5. Temporary migration workflows are removed after migration.
6. One authoritative core workflow runs tests, controller checks, fabric validation, Python compilation, and distribution verification.
7. A green run proves the exact commit tested, not an amended tree created inside the workflow.
