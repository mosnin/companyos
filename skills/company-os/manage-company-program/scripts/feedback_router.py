#!/usr/bin/env python3
"""Pure manager feedback planner. No host calls, permissions, or persistence."""
import argparse
import hashlib
import json
from pathlib import Path

KINDS = {'ci_failure', 'review_changes', 'merge_conflict'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def plan(packet):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(isinstance(packet, dict) and packet.get('schema') == 'company-os.worker-feedback.v1', 'unsupported feedback packet')
    for key in ('instance_id', 'worker_thread_id', 'resource_id', 'current_revision'):
        require(isinstance(packet.get(key), str) and bool(packet[key].strip()), f'missing {key}')
    require(not packet['worker_thread_id'].startswith('client-'), 'canonical worker thread required')
    limit = packet.get('attempt_limit')
    require(type(limit) is int and 1 <= limit <= 10, 'explicit attempt_limit from 1 to 10 required')
    events, history = packet.get('events'), packet.get('history')
    require(isinstance(events, list) and isinstance(history, list), 'events and history required')
    state = packet.get('worker_state')
    require(state in {'idle', 'active', 'awaiting_approval', 'awaiting_input', 'exited', 'unknown'}, 'invalid worker state')
    require(isinstance(packet.get('observation_ref'), str) and bool(packet['observation_ref'].strip()), 'fresh host observation reference required')
    index = {}
    for row in history:
        require(isinstance(row, dict), 'history row must be object')
        key = row.get('event_key')
        require(isinstance(key, str) and key not in index, 'duplicate or invalid history key')
        require(row.get('status') in {'pending', 'sent', 'failed', 'unknown'}, 'invalid delivery status')
        require(type(row.get('attempts')) is int and row['attempts'] >= 0, 'invalid attempts')
        if row['status'] == 'sent':
            require(isinstance(row.get('delivery_ref'), str) and bool(row['delivery_ref'].strip()), 'sent requires native delivery reference')
        index[key] = row
    results, seen = [], set()
    for event in events:
        require(isinstance(event, dict) and event.get('kind') in KINDS, 'invalid feedback kind')
        for key in ('id', 'revision', 'evidence_ref'):
            require(isinstance(event.get(key), str) and bool(event[key].strip()), f'missing event {key}')
        # Explicit occurrence separates a genuinely recurring conflict from repeated polls.
        require(isinstance(event.get('occurrence_id'), str) and bool(event['occurrence_id'].strip()), 'occurrence_id required')
        event_key = digest({k: packet[k] for k in ('instance_id', 'worker_thread_id', 'resource_id')} | {
            'kind': event['kind'], 'id': event['id'], 'revision': event['revision'], 'occurrence_id': event['occurrence_id']})
        require(event_key not in seen, 'duplicate event')
        seen.add(event_key)
        signature = digest(event)
        prior = index.get(event_key)
        if prior:
            require(prior.get('signature') == signature, 'event changed without a new occurrence; reconcile source identity')
        if event['revision'] != packet['current_revision']:
            action = 'refresh_stale_evidence'
        elif prior and prior['status'] == 'sent':
            action = 'already_delivered'
        elif prior and prior['status'] in {'pending', 'unknown'}:
            action = 'reconcile_delivery'
        elif prior and prior['attempts'] >= limit:
            action = 'escalate_exhausted'
        elif state == 'awaiting_approval':
            action = 'escalate_approval'
        elif state in {'awaiting_input', 'exited', 'unknown'}:
            action = 'reconcile_worker'
        elif state == 'active':
            action = 'defer_until_idle'
        else:
            action = 'send_to_owner'
        results.append({'event_key': event_key, 'signature': signature, 'kind': event['kind'],
                        'action': action, 'worker_thread_id': packet['worker_thread_id'],
                        'evidence_ref': event['evidence_ref'],
                        'next_attempt': (prior['attempts'] if prior else 0) + 1 if action == 'send_to_owner' else None})
    return {'schema': 'company-os.worker-feedback-plan.v1', 'actions': results,
            'authority_granted': False, 'host_calls_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(plan(json.loads(args.packet.read_text())), indent=2))
    except (ValueError, TypeError, OSError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
