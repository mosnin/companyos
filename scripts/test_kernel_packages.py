#!/usr/bin/env python3
"""Pack real private sibling sources locally, then exercise the public installer.

No publication, registry access, secrets or external writes. Content stays in
temporary directories. Run after the repository contract/behavior tests.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
args = parser.parse_args()
core = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kernels", core / "skills/company-os/elastic-company-os/scripts/kernel_manager.py")
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)

class LocalRegistry:
    def __init__(self):
        self.releases = {}

    def metadata(self, ident):
        return {"versions": self.releases[ident]}

    def archive(self, release):
        return release["archive"].read_bytes()

with tempfile.TemporaryDirectory() as temporary:
    stage = Path(temporary)
    registry = LocalRegistry()
    for repo in ("business-OS", "design-os"):
        source = args.root / repo
        packed = subprocess.run(["npm", "pack", "--ignore-scripts", "--json", "--pack-destination", str(stage)], cwd=source, check=True, capture_output=True, text=True)
        package = json.loads(packed.stdout)[0]
        paths = {item["path"] for item in package["files"]}
        assert not any("__pycache__" in p or p.endswith(".pyc") or p.endswith(".npmrc") or p.startswith(".env") for p in paths), "Private or generated cache file in package"
        assert "company-os.kernel.json" in paths
        if repo == "business-OS":
            assert "LICENSE" in paths
            assert len([p for p in paths if p.startswith("skills/") and p.endswith("SKILL.md")]) >= 732
        else:
            assert ".agents/skills/design-os/SKILL.md" in paths
            assert len([p for p in paths if p.endswith("SKILL.md")]) == 32
        ident = package["name"].split("/")[1]
        registry.releases[ident] = {package["version"]: {"archive": stage / package["filename"], "dist": {"integrity": package["integrity"]}}}
        print(ident, package["version"], package["entryCount"], "files", package["unpackedSize"], "bytes")
    project = stage / "project"
    project.mkdir()
    manager = k.KernelManager(project, registry)
    state = manager.install({"business-os": "^0.1.0", "design-os": "^0.1.0"}, binding={"companyId": "fixture-company", "revision": 1})
    manager.verify(state)
    assert set(state["installed"]) == {"business-os", "design-os"}
    assert state["desiredRevision"] == 1
    manager.initialize()
    print("PASS: real npm archives installed, verified and initialized; no package code executed")
