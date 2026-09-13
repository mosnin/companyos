import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('organization', ROOT / 'skills/company-os/company-board/scripts/organization_contract.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.org = dict(schema='company-os.organization.v1', instance_id='fixture', host='fixture-host',
                        host_project_id='fixture-project', board_thread_id='board', actors=[])
        for role, parent, model in [('board', None, 'gpt-6-astra'), ('executive', 'board', 'gpt-6-astra'),
                                    ('manager', 'executive', 'gpt-6-astra'), ('worker', 'manager', 'gpt-5.6-luna')]:
            self.org['actors'].append(dict(instance_id='fixture', host='fixture-host', host_project_id='fixture-project',
                thread_id=role, role=role, parent_thread_id=parent, requested_model=model,
                requested_reasoning_effort='medium', creation_ref='fixture-create', readback_ref='fixture-read',
                charter_ref='fixture-charter', mandate_message_ref='fixture-send', acknowledgement_ref='fixture-ack'))

    def test_full_tree(self):
        result = module.validate(self.org)
        self.assertEqual(result['actors'], 4)
        self.assertFalse(result['host_authenticated'])

    def test_distinct_conversations_required(self):
        self.org['actors'][2]['thread_id'] = 'executive'
        with self.assertRaisesRegex(ValueError, 'own conversation'): module.validate(self.org)

    def test_projectless_or_foreign_actor_rejected(self):
        self.org['actors'][1]['host_project_id'] = None
        with self.assertRaisesRegex(ValueError, 'outside'): module.validate(self.org)

    def test_wrong_parent_rejected(self):
        self.org['actors'][3]['parent_thread_id'] = 'board'
        with self.assertRaisesRegex(ValueError, 'parent'): module.validate(self.org)

    def test_cycle_rejected(self):
        second = copy.deepcopy(self.org['actors'][2]); second['thread_id'] = 'manager2'
        second['parent_thread_id'] = 'manager'
        self.org['actors'][2]['parent_thread_id'] = 'manager2'
        self.org['actors'].append(second)
        with self.assertRaises(ValueError): module.validate(self.org)

    def test_model_or_reasoning_drift_rejected(self):
        for field, value in [('requested_model', 'gpt-5.6-sol'), ('requested_reasoning_effort', 'high')]:
            org = copy.deepcopy(self.org); org['actors'][1][field] = value
            with self.assertRaises(ValueError): module.validate(org)

    def test_pending_id_or_missing_ack_rejected(self):
        org = copy.deepcopy(self.org); org['actors'][3]['thread_id'] = 'client-new-thread:pending'
        with self.assertRaises(ValueError): module.validate(org)
        self.org['actors'][1].pop('acknowledgement_ref')
        with self.assertRaises(ValueError): module.validate(self.org)

    def test_multiple_executives_are_separate_subtrees(self):
        second = copy.deepcopy(self.org['actors'][1]); second['thread_id'] = 'executive2'
        self.org['actors'].append(second)
        self.assertEqual(module.validate(self.org)['actors'], 5)
