# Product Checkpoint Contract

A verified product increment becomes durable before its lane closes.

The checkpoint records:

- mission and objective IDs;
- candidate and capability IDs;
- exact product paths and SHA-256 digests;
- verification receipts;
- Git commit identity when Git is available;
- quarantined paths excluded from the checkpoint;
- checkpoint timestamp and digest.

No accepted product artifact may remain untracked longer than the configured checkpoint deadline. Governance records cannot satisfy product durability. Integration is continuous and accepted product, verification repair, and governance metadata should remain separable commits where practical.
