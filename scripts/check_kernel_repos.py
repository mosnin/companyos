#!/usr/bin/env python3
"""Check contract copies across sibling repositories without registry access."""
import argparse
from pathlib import Path
import subprocess
import sys
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
args = parser.parse_args()
core = Path(__file__).resolve().parents[1]
canonical = core / "skills/company-os/elastic-company-os/scripts/kernel_manager.py"
schema = core / "schemas/kernel-v1.schema.json"
for repo in ("business-OS", "design-os", "product-os"):
    target = args.root / repo
    schema_copy = target / ("contracts/kernel-v1.schema.json" if repo == "business-OS" else "schemas/kernel-v1.schema.json")
    for original, copy in ((canonical, target / "scripts/validate_company_os_kernel.py"), (schema, schema_copy)):
        if original.read_bytes() != copy.read_bytes():
            raise SystemExit("Contract drift: " + str(copy))
    command = [sys.executable, str(canonical), "validate", "--package", str(target)]
    if repo == "product-os":
        command.append("--allow-draft")
    subprocess.run(command, check=True)
print("PASS: three repositories, one kernel contract")
