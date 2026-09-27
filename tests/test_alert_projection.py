import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('alerts', Path(__file__).resolve().parents[1] / 'skills/company-os/company-context-ledger/scripts/alert_projection.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)

class AlertsTests(unittest.TestCase):
    def setUp(self):
        self.empty = {'alerts': {'rows': []}}
        self.packet = dict(schema='company-os.alert-observations.v1', instance_id='company-a', now_s=100, max_age_s=10,
            events=[dict(id='ready-pr-1', resource='repo/pr/1', owner='thread-1', revision='head-a', signal='active', sequence=1, observed_at_s=100, evidence_ref='read-1')])
    def test_clear_resolves_without_deleting_history(self):
        content = a.reconcile(self.empty, self.packet)
        self.packet['events'][0].update(signal='clear', sequence=2)
        updated = a.reconcile(content, self.packet)
        self.assertEqual(updated['alerts']['rows'][0][5], 'resolved')
        self.assertEqual(len(updated['alerts']['rows']), 1)
        self.assertEqual(content['alerts']['rows'][0][5], 'active')
    def test_missing_stale_and_unknown_do_not_resolve(self):
        content = a.reconcile(self.empty, self.packet)
        for events in ([], [dict(self.packet['events'][0], signal='clear', sequence=2)]):
            self.packet.update(now_s=111, events=events)
            self.assertEqual(a.reconcile(content, self.packet)['alerts']['rows'][0][5], 'stale')
        self.packet['events'] = [dict(id='ready-pr-1', resource='repo/pr/1', owner='thread-1', revision='head-a', signal='unknown', sequence=2, observed_at_s=111, evidence_ref='read-2')]
        self.assertEqual(a.reconcile(content, self.packet)['alerts']['rows'][0][5], 'needs verification')
    def test_replay_is_idempotent_and_old_event_cannot_reopen(self):
        self.packet['events'][0].update(signal='clear', sequence=2)
        content = a.reconcile(self.empty, self.packet)
        self.assertEqual(a.reconcile(content, self.packet), content)
        self.packet['events'][0].update(signal='active', sequence=1)
        self.assertEqual(a.reconcile(content, self.packet), content)
    def test_new_evidence_can_reopen(self):
        self.packet['events'][0]['signal'] = 'clear'
        content = a.reconcile(self.empty, self.packet)
        self.packet['events'][0].update(signal='active', sequence=2)
        self.assertEqual(a.reconcile(content, self.packet)['alerts']['rows'][0][5], 'active')
    def test_conflict_duplicate_and_wrong_resource_rejected(self):
        content = a.reconcile(self.empty, self.packet)
        for field, value in [('signal', 'clear'), ('resource', 'repo/pr/2')]:
            packet = copy.deepcopy(self.packet); packet['events'][0][field] = value
            with self.assertRaises(ValueError): a.reconcile(content, packet)
        self.packet['events'] *= 2
        with self.assertRaises(ValueError): a.reconcile(content, self.packet)
    def test_instance_isolation_and_no_initial_stale_action(self):
        content = a.reconcile(self.empty, self.packet)
        self.packet.update(instance_id='company-b', now_s=111)
        self.assertEqual(a.reconcile(content, self.packet), content)
    def test_future_clock_and_reordering_rejected(self):
        content = a.reconcile(self.empty, self.packet)
        self.packet['now_s'] = 99
        with self.assertRaises(ValueError): a.reconcile(content, self.packet)
        self.packet['now_s'] = 101; self.packet['events'][0].update(sequence=2, observed_at_s=99)
        with self.assertRaises(ValueError): a.reconcile(content, self.packet)
    def client(self):
        client=Mock()
        client.schema_describe.return_value={'kinds':[{'kind':a.KIND,'fields':[{'id':'alerts','type':'table','columns':[{'label':x} for x in a.COLUMNS]}]}]}
        client.document_get.return_value={'kind':a.KIND,'slug':a.KIND,'revision':4,'content':self.empty}
        return client
    def test_adapter_uses_revision_and_branch_and_skips_identical_write(self):
        client=self.client(); a.sync(client,self.packet,branch='agent-alerts')
        self.assertEqual(client.document_put.call_args.kwargs['base_revision'],4)
        self.assertEqual(client.document_put.call_args.kwargs['branch'],'agent-alerts')
        client.document_get.return_value['content']=a.reconcile(self.empty,self.packet)
        client.document_put.reset_mock()
        self.assertEqual(a.sync(client,self.packet,branch='agent-alerts')['status'],'unchanged')
        client.document_put.assert_not_called()
    def test_adapter_rejects_incompatible_schema_and_main(self):
        client=self.client(); client.schema_describe.return_value={'kinds':[]}
        with self.assertRaises(ValueError): a.sync(client,self.packet,branch='agent-alerts')
        with self.assertRaises(ValueError): a.sync(client,self.packet,branch='main')
        client.document_put.assert_not_called()
    def test_write_conflict_or_timeout_is_not_retried(self):
        for failure in (RuntimeError('revision conflict'),TimeoutError('unknown delivery')):
            client=self.client(); client.document_put.side_effect=failure
            with self.assertRaises(type(failure)): a.sync(client,self.packet,branch='agent-alerts')
            self.assertEqual(client.document_put.call_count,1)

    def test_public_client_method_uses_real_wire_names(self):
        path = Path(a.__file__).with_name('context_ledger.py')
        spec = importlib.util.spec_from_file_location('alert_client_test', path)
        client_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(client_module)
        client = client_module.ContextLedgerClient('https://fixture.invalid/mcp', 'cos_fixture')
        fixture = self.client()
        client._call_tool = Mock(side_effect=[{}, fixture.schema_describe.return_value,
            fixture.document_get.return_value, {'revision': 5}])
        result = client.reconcile_alerts(self.packet, branch='agent-alerts')
        self.assertEqual([c.args[0] for c in client._call_tool.call_args_list],
                         ['config_pull','schema_describe','document_get','document_put'])
        self.assertEqual(result['receipt']['revision'], 5)
