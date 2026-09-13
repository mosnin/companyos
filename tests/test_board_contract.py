"""Fixture-only board handoff checks; these do not create or authenticate chats."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'skills/company-os/company-board/scripts/board_contract.py'
spec = importlib.util.spec_from_file_location('board_contract', PATH)
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


class BoardHandoffTests(unittest.TestCase):
    def setUp(self):
        self.session = dict(schema='company-os.board-session.v2', decision_id='fixture-decision', instance_id='fixture-instance-a',
                            host='fixture-host', host_project_id='fixture-project', board_thread_id='fixture-board',
                            executive_thread_id='fixture-executive', creation_ref='fixture-observation')
        self.context = dict(organization_id='fixture-org', business_slug='fixture-business',
                            retrieved_at='2026-09-13T10:00:00Z',
                            documents=[dict(id='strategy', revision=4, content_hash='fixture-hash')])
        binding = {key: self.session[key] for key in ('instance_id', 'host', 'host_project_id', 'board_thread_id', 'executive_thread_id')}
        binding.update(program_version=3, context_snapshot=copy.deepcopy(self.context))
        self.request = dict(decision_id='fixture-decision', project='fixture-instance-a', framework=binding)
        self.record = dict(schema='council-os.decision.v2', status='advisory', request_sha256=board.digest(self.request))
        self.disposition = dict(schema='company-os.board-disposition.v1', decision_id='fixture-decision',
                                request_sha256=board.digest(self.request), record_sha256=board.digest(self.record),
                                executive_thread_id='fixture-executive', action='adopt', rationale='fixture rationale',
                                management_owner='fixture-owner', success_metric='fixture metric', review_trigger='fixture trigger')

    def check(self, version=3):
        return board.validate(self.session, self.request, self.record, self.disposition, self.context, version)

    def test_valid_handoff_does_not_grant_authority(self):
        self.assertFalse(self.check()['authority_granted'])

    def test_cross_instance_or_chat_replay_rejected(self):
        for key in ('instance_id', 'host', 'host_project_id', 'board_thread_id', 'executive_thread_id'):
            original = self.session[key]
            self.session[key] = 'different'
            with self.assertRaises(ValueError): self.check()
            self.session[key] = original

    def test_other_decision_session_rejected(self):
        self.session['decision_id'] = 'other-decision'
        with self.assertRaisesRegex(ValueError, 'another decision'): self.check()

    def test_legacy_session_requires_rebinding(self):
        self.session['schema'] = 'company-os.board-session.v1'
        with self.assertRaisesRegex(ValueError, 'unsupported'): self.check()

    def test_stale_program_rejected(self):
        with self.assertRaises(ValueError): self.check(4)

    def test_context_revision_or_business_changed(self):
        self.context['documents'][0]['revision'] = 5
        with self.assertRaises(ValueError): self.check()
        self.context['documents'][0]['revision'] = 4
        self.context['business_slug'] = 'another-business'
        with self.assertRaises(ValueError): self.check()

    def test_refresh_time_does_not_invalidate_same_context(self):
        self.context['retrieved_at'] = '2026-09-13T10:05:00Z'
        self.assertTrue(self.check()['ok'])

    def test_altered_memo_rejected(self):
        self.record['memo'] = 'changed after executive disposition'
        with self.assertRaises(ValueError): self.check()

    def test_missing_executive_disposition_rejected(self):
        self.disposition.pop('action')
        with self.assertRaises(ValueError): self.check()

    def test_board_cannot_be_executive_chat(self):
        self.session['board_thread_id'] = self.session['executive_thread_id']
        self.request['framework']['board_thread_id'] = self.session['executive_thread_id']
        with self.assertRaises(ValueError): self.check()


if __name__ == '__main__':
    unittest.main()
