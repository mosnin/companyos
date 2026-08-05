from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "skills/company-os/ui-design-quality"
BUNDLE_ROOT = UI_ROOT / "vendor/greensock-gsap"
RECEIPT_PATH = UI_ROOT / "references/greensock-gsap-source.json"

EXPECTED_COMMIT = "aed9cfd3277740755f6bfc1155c7aa645403b760"
EXPECTED_TREE = "445734a57cd547b25fbf81ba635468ab450048f4"
EXPECTED_REPOSITORY = "https://github.com/greensock/gsap-skills"
EXPECTED_SKILLS = (
    "gsap-core",
    "gsap-timeline",
    "gsap-scrolltrigger",
    "gsap-plugins",
    "gsap-utils",
    "gsap-react",
    "gsap-performance",
    "gsap-frameworks",
)
EXPECTED_FILES = {
    "vendor/greensock-gsap/LICENSE": "51b04b06556662dd817e8f4aa6d06bc7139dc73739e1319a7233cfde3e147b90",
    "vendor/greensock-gsap/llms.txt": "32dab4bde09bc822ac17ebc49ee2ff87ca8c304a1c6e0509aadde7223f78b42f",
    "vendor/greensock-gsap/gsap-core/SKILL.md": "3887b47e050ab5afbe2a9a820f23d39fa02ab785e06a343be44c6f91d84d12b3",
    "vendor/greensock-gsap/gsap-frameworks/SKILL.md": "842d9d3659ec3ddc8abbdc524708f8facf81f468ac25d0577f48c759c4fa31e6",
    "vendor/greensock-gsap/gsap-performance/SKILL.md": "cb5408d6fba707aabcbfe3320317a14c1f8fca6070074e5261047930f50d441e",
    "vendor/greensock-gsap/gsap-plugins/SKILL.md": "5838b856c74c07fbc9fa99b6dfd1eee34ea554c3e530c30e0d58014b707d70a4",
    "vendor/greensock-gsap/gsap-react/SKILL.md": "88e2a5312b45e8cc7b3c496637ff5bc9af2ae9c925b555c8b235b34cbc989d74",
    "vendor/greensock-gsap/gsap-scrolltrigger/SKILL.md": "9351b6666a4749c0740406ea363aaccb99a087ff45cc5e8b99a0f367facf3ef4",
    "vendor/greensock-gsap/gsap-timeline/SKILL.md": "1a8b0f39cc4be3ed3d834b89672e4ae2f151b901dc3450bebf10bbc45379fe02",
    "vendor/greensock-gsap/gsap-utils/SKILL.md": "1927bcc4ea95b38203404ad5ea1d060b15c4a886c65ae53e885ff1793aabe0ba",
}


def _frontmatter(path: Path) -> dict[str, str]:
    """Read the small YAML frontmatter contract without a runtime dependency."""

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} does not begin with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise AssertionError(f"{path} has no closing YAML frontmatter marker")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"unparseable frontmatter line in {path}: {line!r}")
        values[key.strip()] = value.strip()
    return values


class GreensockGsapSkillBundleTests(unittest.TestCase):
    def test_source_receipt_is_pinned_and_every_vendored_file_is_byte_exact(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(EXPECTED_REPOSITORY, receipt["source_repository"])
        self.assertEqual(EXPECTED_COMMIT, receipt["source_commit"])
        self.assertEqual(EXPECTED_TREE, receipt["source_tree"])
        self.assertEqual(EXPECTED_FILES, receipt["files"])

        actual_paths = {
            path.relative_to(UI_ROOT).as_posix()
            for path in BUNDLE_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(set(EXPECTED_FILES), actual_paths)
        for relative, digest in EXPECTED_FILES.items():
            path = UI_ROOT / relative
            self.assertFalse(path.is_symlink(), path)
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest(), path)

    def test_all_eight_skill_entrypoints_have_canonical_unique_frontmatter(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(EXPECTED_SKILLS), receipt["skills"])

        names: list[str] = []
        for path in sorted(BUNDLE_ROOT.glob("*/SKILL.md")):
            metadata = _frontmatter(path)
            name = metadata.get("name", "")
            description = metadata.get("description", "")
            self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$", path)
            self.assertLessEqual(len(name), 64, path)
            self.assertTrue(description, path)
            self.assertLessEqual(len(description), 1024, path)
            self.assertEqual("MIT", metadata.get("license"), path)
            self.assertEqual(path.parent.name, name, path)
            names.append(name)

        self.assertEqual(len(EXPECTED_SKILLS), len(names))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(sorted(EXPECTED_SKILLS), sorted(names))

    def test_upstream_mit_license_is_retained(self) -> None:
        license_path = BUNDLE_ROOT / "LICENSE"
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 GreenSock", license_text)
        self.assertEqual(EXPECTED_FILES["vendor/greensock-gsap/LICENSE"], hashlib.sha256(license_path.read_bytes()).hexdigest())
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual("MIT", receipt["license"])
        self.assertEqual("vendor/greensock-gsap/LICENSE", receipt["license_file"])
        self.assertEqual(EXPECTED_FILES["vendor/greensock-gsap/LICENSE"], receipt["license_sha256"])

    def test_bundle_is_progressive_and_on_demand(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        activation = receipt["activation"]
        self.assertEqual("progressive-on-demand", activation["policy"])
        self.assertFalse(activation["default_enabled"])
        self.assertEqual("vendor/greensock-gsap/llms.txt", activation["index"])

        index = (UI_ROOT / activation["index"]).read_text(encoding="utf-8")
        for skill in EXPECTED_SKILLS:
            self.assertIn(skill, index)
        # The bundle exposes no catch-all entrypoint: callers must choose a
        # matching skill directory from the compact index before loading it.
        self.assertFalse((BUNDLE_ROOT / "SKILL.md").exists())
        self.assertEqual(
            set(EXPECTED_SKILLS),
            {path.parent.name for path in BUNDLE_ROOT.glob("*/SKILL.md")},
        )

    def test_company_os_ui_gate_routes_gsap_without_forcing_it(self) -> None:
        gate = (UI_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Route advanced motion progressively", gate)
        self.assertIn("vendor/greensock-gsap/llms.txt", gate)
        self.assertIn("gsap-performance", gate)
        self.assertIn("smallest matching specialization", gate)
        self.assertIn("Do not load the complete bundle by default", gate)
        self.assertIn("install `gsap` without separate dependency authority", gate)
        self.assertIn("greensock-gsap-source.json", gate)
        self.assertIn("timeline/ScrollTrigger/plugin cleanup", gate)


if __name__ == "__main__":
    unittest.main()
