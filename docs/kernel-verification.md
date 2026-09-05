# Kernel protocol v1 verification

Local verification on 2026-09-05; package publication and live deployment are
separate, still-required release steps.

- Full host suite: `env PATH=/opt/homebrew/opt/openssl@3/bin:$PATH
  TMPDIR=/private/tmp python3 -m unittest discover -s tests -q`: 777 tests,
  OK, one skipped. OpenSSL 3 and the physical macOS temporary path are required
  for existing RSA output/path-sensitive tests. Default macOS LibreSSL 3.3.6
  produced seven failures and four errors in the RSA-3072 text-output check;
  no production/test code was altered to bypass it.
- Kernel unit suite: nine tests pass; existing controller suite: 164 pass.
- `python3 scripts/check_kernel_repos.py`: all three sibling kernel repositories
  match the canonical schema/validator and validate (Product OS allowed as draft).
- `python3 scripts/test_kernel_packages.py`: real local npm archives for
  Business OS and Design OS installed, verified, initialized and retained after
  a failed update. Business package includes all 732 skill entrypoints; Design
  includes all 32. No publish/network call or package script execution occurs.
- Distribution manifest and 75 first-class skill surface verification pass.
- Business OS generated-surface/build checks pass; Design OS 28 tests and complete
  principle/journey registry validation pass.

The Business OS package test used source-library 1.2.0 from main. The separate
passive-adapter 1.3.0 integration must be combined and revalidated before release;
the package allowlist preserves its business_os_kernel directory. Package version
0.1.0 is intentionally independent from the source-library VERSION.

The companion web suite's only full-suite failure was reproduced on unchanged
main (`7116d6b`): provisioning fetch count expected 1, received 2. See its
docs/KERNEL-VERIFICATION.md for exact commands and counts. Kernel/MCP tests and
four light/dark browser cases pass. Docs test/lint/typecheck/build pass.

Release requires authenticated real-registry installation and tenant-bound MCP
receipt validation, publication access/reviewers, authorized backend deployment,
and the host's first-startup adapter. No kernel packages were published and no
live backend was deployed by these checks.
