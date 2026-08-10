from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "skills/company-os/engineering-execution-constitution/scripts/engineering_contract.py"
spec = importlib.util.spec_from_file_location("engineering_contract", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class EngineeringContractTests(unittest.TestCase):
    def master(self):
        return mod.root({"contract_id":"master","objective_id":"obj","engineering_rigor":8,"security_verification":"static","required_skills":["typescript"],"write_scopes":[]})

    def test_recursive_children_can_strengthen_but_not_weaken(self):
        mid = mod.derive(self.master(), {"contract_id":"mid","objective_id":"obj","manager_level":"mid","engineering_rigor":9,"required_skills":["react"],"write_scopes":["frontend/auth"]})
        self.assertEqual(mid["engineering_rigor"], 9)
        self.assertEqual(mid["required_skills"], ["react", "typescript"])
        lower = mod.derive(mid, {"contract_id":"lower","objective_id":"obj","manager_level":"lower","security_verification":"authorized_pentest","write_scopes":["frontend/auth/components"]})
        self.assertEqual(lower["security_verification"], "authorized_pentest")
        with self.assertRaises(mod.ContractError):
            mod.derive(mid, {"contract_id":"weak","objective_id":"obj","manager_level":"lower","engineering_rigor":7,"write_scopes":[]})
        with self.assertRaises(mod.ContractError):
            mod.derive(mid, {"contract_id":"weak","objective_id":"obj","manager_level":"lower","runtime_observation_required":False,"write_scopes":[]})

    def test_worker_inherits_every_required_skill(self):
        mid = mod.derive(self.master(), {"contract_id":"mid","objective_id":"obj","manager_level":"mid","required_skills":["postgres"],"write_scopes":[]})
        lower = mod.derive(mid, {"contract_id":"lower","objective_id":"obj","manager_level":"lower","required_skills":["security"],"write_scopes":[]})
        worker = mod.derive(lower, {"contract_id":"worker","objective_id":"obj","manager_level":"worker","required_skills":["playwright"],"write_scopes":["tests/auth"]})
        self.assertEqual(worker["required_skills"], ["playwright", "postgres", "security", "typescript"])
        self.assertTrue(worker["independent_review_required"])
        self.assertTrue(worker["original_objective_acceptance_required"])

    def test_parallel_writers_cannot_share_resource_boundary(self):
        a = mod.derive(self.master(), {"contract_id":"a","objective_id":"obj","manager_level":"mid","write_scopes":["backend/auth"]})
        b = mod.derive(self.master(), {"contract_id":"b","objective_id":"obj","manager_level":"mid","write_scopes":["backend/auth"]})
        with self.assertRaises(mod.ContractError): mod.assert_nonoverlap([a,b])

if __name__ == "__main__": unittest.main()
