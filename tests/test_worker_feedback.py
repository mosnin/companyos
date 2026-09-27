import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('feedback', Path(__file__).resolve().parents[1] / 'skills/company-os/manage-company-program/scripts/feedback_router.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.packet = dict(schema='company-os.worker-feedback.v2', instance_id='fixture', worker_thread_id='worker',
            resource_id='repo/pr/1', current_revision='head-a', worker_state='idle', observation_ref='fixture-read',
            control=dict(now_s=100, observed_at_s=95, max_age_s=10, deadline_s=200, repair_attempts=0, repair_limit=10), attempt_limit=2, history=[], events=[dict(kind=k, id=k, revision='head-a', evidence_ref='fixture-'+k,
            occurrence_id='occurrence-1', **({'dependency_state': 'ready'} if k == 'merge_conflict' else {})) for k in ('ci_failure', 'review_changes', 'merge_conflict')])

    def actions(self):
        return module.plan(self.packet)['actions']

    def prior(self, status, attempts=1):
        action = self.actions()[0]
        self.packet['history'] = [dict(event_key=action['event_key'], signature=action['signature'],
                                       status=status, attempts=attempts, delivery_ref='fixture-send')]

    def test_all_failures_surface_independently(self):
        self.assertEqual([r['action'] for r in self.actions()], ['send_to_owner']*3)

    def test_sent_is_deduplicated_after_serialized_restart(self):
        import json
        self.prior('sent'); self.packet = json.loads(json.dumps(self.packet))
        self.assertEqual(self.actions()[0]['action'], 'already_delivered')
        self.assertEqual(self.actions()[1]['action'], 'send_to_owner')

    def test_uncertain_send_never_retries_blindly(self):
        for status in ('unknown', 'pending'):
            self.packet['history'] = []; self.prior(status)
            self.assertEqual(self.actions()[0]['action'], 'reconcile_delivery')

    def test_failed_retry_exhaustion_is_not_delivery(self):
        self.prior('failed', 2)
        self.assertEqual(self.actions()[0]['action'], 'escalate_exhausted')

    def test_failed_retry_within_budget(self):
        self.prior('failed', 1)
        self.assertEqual(self.actions()[0]['next_attempt'], 2)

    def test_approval_and_active_sessions_are_not_nudged(self):
        for state, action in [('awaiting_approval', 'escalate_approval'), ('active', 'defer_until_idle'), ('unknown', 'reconcile_worker')]:
            self.packet['worker_state'] = state
            self.assertTrue(all(r['action'] == action for r in self.actions()))

    def test_old_revision_does_not_receive_repair(self):
        self.packet['current_revision'] = 'head-b'
        self.assertTrue(all(r['action'] == 'refresh_stale_evidence' for r in self.actions()))

    def test_recurrence_rearms_only_with_new_occurrence(self):
        self.prior('sent')
        self.packet['events'][0]['occurrence_id'] = 'verified-recurrence-2'
        self.assertEqual(self.actions()[0]['action'], 'send_to_owner')

    def test_duplicate_or_mutated_event_rejected(self):
        self.prior('sent'); self.packet['events'][0]['evidence_ref'] = 'changed'
        with self.assertRaises(ValueError): self.actions()
        self.packet['history'] = []; self.packet['events'].append(copy.deepcopy(self.packet['events'][0]))
        with self.assertRaises(ValueError): self.actions()

    def test_pending_thread_and_fake_delivery_rejected(self):
        self.prior('sent'); self.packet['history'][0].pop('delivery_ref')
        with self.assertRaises(ValueError): self.actions()
        self.packet['history'] = []; self.packet['worker_thread_id'] = 'client-new-thread:pending'
        with self.assertRaises(ValueError): self.actions()

    def test_unknown_send_reconciles_even_after_revision_change(self):
        self.prior('unknown'); self.packet['current_revision'] = 'head-b'
        self.assertEqual(self.actions()[0]['action'], 'reconcile_delivery')

    def test_stale_observation_and_freshness_boundary(self):
        self.packet['control']['observed_at_s'] = 90
        self.assertEqual(self.actions()[0]['action'], 'send_to_owner')
        self.packet['control']['observed_at_s'] = 89
        self.assertTrue(all(r['action'] == 'refresh_observation' for r in self.actions()))

    def test_deadline_prevents_permanent_active_deferral(self):
        self.packet['worker_state'] = 'active'
        self.packet['control']['deadline_s'] = 100
        self.assertTrue(all(r['action'] == 'escalate_deadline' for r in self.actions()))

    def test_delivered_feedback_still_has_deadline_alert(self):
        self.prior('sent'); self.packet['control']['deadline_s'] = 100
        result = module.plan(self.packet)
        self.assertEqual(result['actions'][0]['action'], 'already_delivered')
        self.assertEqual(result['alerts'], ['blocker_deadline_reached'])

    def test_shared_budget_bounds_entire_batch(self):
        self.packet['control'].update(repair_attempts=9, repair_limit=10)
        self.assertEqual([r['action'] for r in self.actions()],
                         ['send_to_owner', 'escalate_repair_budget', 'escalate_repair_budget'])

    def test_new_occurrence_does_not_reset_shared_budget(self):
        self.packet['control'].update(repair_attempts=10)
        self.packet['events'][0]['occurrence_id'] = 'new'
        self.assertEqual(self.actions()[0]['action'], 'escalate_repair_budget')

    def test_parent_blocks_conflict_only_and_release_preserves_identity(self):
        before = self.actions()[2]
        for state, action in [('blocked', 'wait_for_dependency'), ('unknown', 'refresh_dependency')]:
            self.packet['events'][2]['dependency_state'] = state
            result = self.actions()
            self.assertEqual(result[0]['action'], 'send_to_owner')
            self.assertEqual(result[2]['action'], action)
            self.assertEqual(result[2]['signature'], before['signature'])
        self.packet['events'][2]['dependency_state'] = 'ready'
        self.assertEqual(self.actions()[2]['action'], 'send_to_owner')

    def test_bad_control_and_ambiguous_identity_rejected(self):
        original = copy.deepcopy(self.packet)
        for key, value in [('now_s', True), ('observed_at_s', 101), ('max_age_s', 0), ('repair_limit', -1)]:
            self.packet = copy.deepcopy(original); self.packet['control'][key] = value
            with self.assertRaises(ValueError): self.actions()
        self.packet = original; self.packet['worker_thread_id'] = ' client-new-thread:pending'
        with self.assertRaises(ValueError): self.actions()
