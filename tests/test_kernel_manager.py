import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "skills/company-os/elastic-company-os/scripts/kernel_manager.py"
SPEC = importlib.util.spec_from_file_location("kernels", SOURCE)
k = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k)


def package(ident="design-os", release="0.1.0", dependencies=None, **overrides):
    manifest = dict(schemaVersion=1, id=ident, name="@mosnin/" + ident, version=release, status="ready", companyOS=">=0.6.0 <0.7.0", entrypoints=["skills/main/SKILL.md"], dependencies=dependencies or {}, dataSchemaVersion=1, permissions=[])
    manifest.update(overrides)
    files = {"company-os.kernel.json": json.dumps(manifest), "package.json": json.dumps(dict(name=manifest["name"], version=release, publishConfig={"registry": k.REGISTRY})), "skills/main/SKILL.md": "# Kernel\nUseful instructions"}
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as archive:
        for name, content in files.items():
            entry = tarfile.TarInfo("package/" + name)
            data = content.encode()
            entry.size = len(data)
            archive.addfile(entry, io.BytesIO(data))
    data = out.getvalue()
    return data, "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()


class Registry:
    def __init__(self):
        self.packages = {}
        self.calls = 0
        self.offline = False

    def add(self, ident="design-os", release="0.1.0", **options):
        data, integrity = package(ident, release, **options)
        self.packages.setdefault(ident, {})[release] = {"dist": {"integrity": integrity}, "data": data}

    def metadata(self, ident):
        self.calls += 1
        if self.offline:
            raise ValueError("offline")
        return {"versions": self.packages[ident]}

    def archive(self, release):
        return release["data"]


class KernelsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Registry()
        self.registry.add()
        self.manager = k.KernelManager(self.temp.name, self.registry)

    def tearDown(self):
        self.temp.cleanup()

    def test_install_check_update_rollback_and_data_preservation(self):
        first = self.manager.install({"design-os": "^0.1.0"})
        data = self.manager.root / "data/design-os"
        data.mkdir()
        (data / "research.txt").write_text("user data")
        self.registry.add(release="0.1.1")
        checked = self.manager.initialize()
        self.assertEqual(checked["updateCheck"]["results"]["design-os"]["status"], "available")
        calls = self.registry.calls
        self.manager.initialize()
        self.assertEqual(self.registry.calls, calls)
        second = self.manager.install(first["desired"])
        self.assertEqual(second["installed"]["design-os"]["version"], "0.1.1")
        rolled = self.manager.rollback(1)
        self.assertEqual(rolled["installed"]["design-os"]["version"], "0.1.0")
        self.assertEqual((data / "research.txt").read_text(), "user data")

    def test_failure_leaves_active_state_unchanged(self):
        self.manager.install({"design-os": "^0.1.0"})
        before = (self.manager.root / "state.json").read_bytes()
        self.registry.add(release="0.1.1", companyOS=">=1.0.0 <2.0.0")
        with self.assertRaisesRegex(ValueError, "incompatible"):
            self.manager.install({"design-os": "^0.1.0"})
        self.assertEqual(before, (self.manager.root / "state.json").read_bytes())

    def test_offline_not_current(self):
        self.manager.install({"design-os": "^0.1.0"})
        self.registry.offline = True
        self.assertEqual(self.manager.initialize()["updateCheck"]["results"]["design-os"]["status"], "unknown")

    def test_altered_object_is_refused(self):
        state = self.manager.install({"design-os": "0.1.0"})
        root = self.manager.root / "objects" / state["installed"]["design-os"]["object"]
        (root / "skills/main/SKILL.md").write_text("local edit")
        with self.assertRaisesRegex(ValueError, "modified"):
            self.manager.install({"design-os": "0.1.0"})

    def test_cycle_and_conflict(self):
        self.registry.add(dependencies={"business-os": "0.1.0"})
        self.registry.add("business-os", dependencies={"design-os": "0.1.0"})
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.manager.install({"design-os": "0.1.0"})
        self.registry.add("business-os", dependencies={"design-os": "0.1.1"})
        self.registry.add(release="0.1.1")
        with self.assertRaisesRegex(ValueError, "cycle|conflict"):
            self.manager.install({"business-os": "0.1.0", "design-os": "0.1.0"})

    def test_draft_and_migration_are_refused(self):
        self.registry.add(status="draft")
        with self.assertRaisesRegex(ValueError, "draft"):
            self.manager.install({"design-os": "0.1.0"})
        self.registry.add()
        self.manager.install({"design-os": "^0.1.0"})
        self.registry.add(release="0.1.1", dataSchemaVersion=2)
        with self.assertRaisesRegex(ValueError, "migration"):
            self.manager.install({"design-os": "^0.1.0"})

    def test_no_cross_company_sync(self):
        self.manager.install({"design-os": "0.1.0"}, binding={"companyId": "a", "revision": 1})
        with self.assertRaisesRegex(ValueError, "different company"):
            self.manager.install({"design-os": "0.1.0"}, binding={"companyId": "b", "revision": 1})

    def test_bad_archives(self):
        for name, kind in [("package/../../escape", tarfile.REGTYPE), ("package/link", tarfile.SYMTYPE), ("package/link", tarfile.LNKTYPE), ("outside/a", tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind):
                out = io.BytesIO()
                with tarfile.open(fileobj=out, mode="w:gz") as archive:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    archive.addfile(member)
                data = out.getvalue()
                integrity = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
                with tempfile.TemporaryDirectory() as target, self.assertRaises(ValueError):
                    k.unpack(data, integrity, target)
        with self.assertRaisesRegex(ValueError, "integrity"):
            k.unpack(b"bad", "sha512-bad", self.temp.name)

    def test_ranges(self):
        self.assertTrue(k.satisfies("0.1.9", "^0.1.0"))
        self.assertFalse(k.satisfies("0.2.0", "^0.1.0"))
        for bad in ["latest", "*", "1", "1.0.0-beta", "^01.0.0", ">=2.0.0 <1.0.0"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                k.satisfies("1.0.0", bad)


if __name__ == "__main__":
    unittest.main()
