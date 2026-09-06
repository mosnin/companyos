# Private Company OS kernels: protocol v1

Company OS is the host. Business OS, Design OS and future Product OS releases
remain independently versioned repositories and private GitHub Packages under
@mosnin. This implementation does not imply publication or live deployment.

## Ownership

Business OS is the required baseline at first authenticated host startup. Before
any saved request exists, kernels_status returns revision 0 and business-os at
^0.1.0. A report-only runtime key can install and report this default without
mutating selections. Other kernels are per-company opt-ins. The host startup
adapter owns first-install bootstrap; ordinary init remains check-only and repeat
startup must reuse already satisfied versions. Package version 0.1.0 is separate
from the source-library VERSION and passive adapter version, which may be newer.

| Repository | Responsibility |
| --- | --- |
| mosnin/companyos | Canonical contract, installer, initialization, lock state and recovery |
| mosnin/company-os-web | Tenant-scoped desired versions, admin requests, MCP and receipts |
| mosnin/company-os-docs | Public operator and author documentation |
| mosnin/business-OS | Private @mosnin/business-os business capability package |
| mosnin/design-os | Private @mosnin/design-os, preserving earlier ux-ui-os work |
| mosnin/product-os | Draft compatibility shell; product capabilities not authored yet |

Core and docs are public. Never copy private contents or credentials into them.
Package names and the protocol may be documented publicly. Legacy ux-ui-os is
preserved, not deleted.

## Durable storage

```text
<project>/.company-os/kernels/
  state.json                  # atomic active lock state
  operation.lock              # one writer per project
  history/<generation>.json   # retained rollback snapshots
  objects/<sha256>/           # verified package content
  data/<kernel-id>/           # company-owned outputs, not overwritten
  overrides/<kernel-id>/      # company-owned adaptations, not overwritten
```

State records protocol, Company OS distribution version, environment UUID,
generation, desired constraints, exact installed versions, archive SHA-512,
object SHA-256, every file hash, entrypoints, data schema versions, activation
time and update checks. Web-bound installs also record companyId and
desiredRevision. Distribution 0.6.0 is distinct from the controller's internal
core/state schema version. Existing governed ledger state is not replaced.

## Connect and install

Set secrets using a secret manager, never literal tokens in chat or source:

- COMPANY_OS_REGISTRY_TOKEN: classic GitHub PAT with read:packages and private package access.
- COMPANY_OS_MCP_URL: trusted HTTPS URL, normally https://www.companyos.sh/api/mcp.
- COMPANY_OS_MCP_TOKEN: tenant-bound runtime key explicitly granted kernels:report.

Read access is implied. Only a key changing selections needs kernels:manage.
Old write credentials acquire neither permission. In the web app open Settings,
Manage kernels, then Install. Connected Company OS registers and installs the
selection on its next sync; the web app shows installed versions after confirmation.
The web page is configuration only and contains no Company OS runtime or Update
button. Repeating a selection is idempotent. Only Company OS performs registry
checks and updates: adding a selection never authorizes upgrading another kernel.

From the Company OS checkout:

```sh
python3 scripts/kernels.py init --project /absolute/project
python3 scripts/kernels.py sync --project /absolute/project
python3 scripts/kernels.py status --project /absolute/project
```

Installed distributions use elastic-company-os/scripts/kernel_manager.py instead
of the repository wrapper. New project initialization creates kernel metadata.
At subsequent session initialization the coordinator invokes init once. A 24-hour
cache bounds checks; there is no per-task dispatch polling or silent updating.
No installed kernels means no registry request. Offline is unknown, not current.
Candidates still require compatibility validation before installation.

Sync pulls a tenant's desired revision, installs locally, then reports that exact
revision through MCP. A stale receipt cannot satisfy a newer request. The UI calls
receipts runtime-reported: the server cannot attest a remote filesystem. Each
environment belongs to its first reporting key. Key rotation currently requires
a separately initialized runtime identity. Reports are capped at 32 environments.

## Explicit updates and recovery

The MCP prompt update-kernels supports clients that expose prompts as slash
commands. Native slash registration differs by client. The Company OS coordinator
also maps explicit natural-language update requests to this workflow.

```sh
# Reconcile web configuration, preserving already installed versions
python3 scripts/kernels.py sync --project /absolute/project
# Local-only installation, also preserving already installed versions
python3 scripts/kernels.py install --kernel design-os --version '^0.1.0' --project /absolute/project
# Explicit update inside Company OS, for web-bound or local-only projects
python3 scripts/kernels.py update-kernels --project /absolute/project
# Check only, bypassing the initialization cache
python3 scripts/kernels.py check --project /absolute/project
# Retry receipt delivery after successful local installation
python3 scripts/kernels.py report --project /absolute/project
# Activate a retained generation as a new generation
python3 scripts/kernels.py rollback --generation 1 --project /absolute/project
```

Never broaden approved ranges automatically. Local-only changes clear the web
revision binding and cannot fulfill it without another sync. Existing roots stay
installed: v1 does not implement removal or garbage collection. Rollback verifies
previous files and leaves company data/overrides untouched. Data schema changes
require a separately reviewed migration plan and are refused. Receipt failure
after activation does not mean installation failed: inspect status then report,
without repeating the update. A newer web request requires fresh sync.
Sync preserves each existing version and verifies it satisfies all configured
constraints and exact dependencies. Missing kernels are installed. A selection
requiring an existing version to change stops for explicit Company OS update;
it cannot silently upgrade. Unchanged selections and bindings do not create a
new activation. update-kernels is the separate, explicit upgrade-enabled path;
for web-bound projects it pulls configuration and submits its runtime receipt.

## Safety and compatibility

schemas/kernel-v1.schema.json and the executable validator are canonical.
Each kernel declares matching package identity/version, host constraint,
entrypoints, exact kernel dependencies, dataSchemaVersion and empty permissions.
Stable grammar: exact x.y.z, ^x.y.z, ~x.y.z or >=x.y.z <x.y.z. No tags, wildcards,
prereleases or union ranges. Graph conflicts and cycles fail closed. The highest
satisfying release is validated; incompatibility stops the operation rather than
silently falling back to another version.

All packages stage before one atomic state activation. Archive integrity and safe
paths are verified. Traversal, duplicates, links, special files, sparse files and
oversized archives are refused. Modified installed files stop updates.
Unreferenced objects are inert. Package scripts never run. Kernel guidance cannot
grant tools, permissions or authority. Registry credentials go only to
npm.pkg.github.com; redirects are refused. MCP tokens go only to the configured
trusted HTTPS endpoint. Load only verified active entrypoints.

## Authoring and private publication

Each kernel has company-os.kernel.json, matching @mosnin package.json, a files
allowlist, .npmrc, bunfig.toml, validator and manual publish workflow. Ready means
structurally installable, not already published or quality-certified. Product OS
is draft and must fail publication/installation until real content exists.
Existing capability and behavioral tests remain mandatory.

```sh
python3 scripts/validate_company_os_kernel.py validate --package .
npm pack --ignore-scripts --dry-run
```

Bun is an npm-compatible client, not a separate registry. Raw bun add downloads
a package but does not register it as a kernel; use the Company OS installer for
activation and receipts. Publish only a reviewed matching vX.Y.Z tag through the
manual workflow. Configure required reviewers on kernel-release first. The
workflow requires a private repository and uses GITHUB_TOKEN. Cross-repository
installs need explicit package access grants. Confirm source/package visibility.

## Maintenance gate

Contract/lifecycle changes must update this guide, schema, initialization, tests,
MCP contracts and public docs together. Keep author validators byte-identical to
the canonical installer. Do not weaken old credentials, merge requested/installed
states or put company data inside objects. Regenerate the distribution manifest
after bundled changes. Future kernels enter the web catalog by reviewed PR after
contract and behavior validation.

References: [GitHub registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-npm-registry),
[Bun scopes](https://bun.sh/docs/pm/scopes-registries).

## Dev OS engineering kernel

Dev OS is an optional private `@mosnin/dev-os` protocol-v1 content package. It
provides engineering implementation, debugging, testing and verification guidance.
Company OS retains authority, state and acceptance; Design OS retains UX/UI
direction. Business OS remains the default baseline. Select Dev OS per company
and let the connected host install and report the requested revision.

The host activates one engineering navigator and loads specialist guidance on
demand. Installation runs no scripts and grants no permissions. Company outputs
and overrides remain outside immutable package objects. The standalone Dev OS
installer is not part of host initialization. Local package verification does not
prove registry publication, deployed availability or improved product outcomes.
