import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('routing',ROOT/'scripts/install_council_routing.py')
routing=importlib.util.module_from_spec(spec);spec.loader.exec_module(routing)

class RoutingTests(unittest.TestCase):
    def test_every_entrypoint_has_canonical_policy(self):
        section=(ROOT/'docs/council/routing.md').read_text().strip()
        for rel in routing.PATHS:
            self.assertIn(section,(ROOT/'skills'/rel).read_text())

    def test_install_preserves_existing_version_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d).resolve()
            original='---\nname: example\n---\n\n# Existing skill\n\nKeep prior user content.\n'
            for rel in routing.PATHS:
                p=target/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(original)
            first=routing.install(target)
            self.assertTrue(all(r['changed'] for r in first))
            self.assertTrue(all(not r['changed'] for r in routing.install(target)))
            for rel in routing.PATHS:
                p=target/rel
                self.assertIn('Keep prior user content.',p.read_text())
                self.assertEqual(next(p.parent.glob('*.pre-council-*')).read_text(),original)

    def test_malformed_marker_fails(self):
        with self.assertRaises(ValueError):routing.render('# Skill\n'+routing.BEGIN, 'section')

if __name__ == '__main__':unittest.main()
