# Update Company OS kernels

Read the current project's configured versions first. Run the trusted installed
kernel manager's update-kernels --project <path>. A web-bound runtime pulls its
configuration and reports completion; local-only runtimes use saved constraints.
The web app stores configuration and cannot execute this operation. Ordinary sync
preserves installed versions and only adds missing kernels. Never broaden approved ranges, run
package lifecycle scripts or invent receipts. Preserve active state on failure.
See docs/kernels.md.
