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
    require(isinstance(packet, dict) and packet.get('schema') == 'company-os.worker-feedback.v2', 'unsupported feedback packet')
    for key in ('instance_id', 'worker_thread_id', 'resource_id', 'current_revision'):
        require(isinstance(packet.get(key), str) and bool(packet[key]) and packet[key] == packet[key].strip(), f'missing {key}')
    require(not packet['worker_thread_id'].startswith('client-'), 'canonical worker thread required')
    limit = packet.get('attempt_limit')
    require(type(limit) is int and 1 <= limit <= 10, 'explicit attempt_limit from 1 to 10 required')
    control = packet.get('control')
    require(isinstance(control, dict), 'control envelope required')
    for key in ('now_s', 'observed_at_s', 'max_age_s', 'deadline_s', 'repair_attempts', 'repair_limit'):
        require(type(control.get(key)) is int and control[key] >= 0, f'invalid control {key}')
    require(control['max_age_s'] > 0 and control['repair_limit'] > 0, 'positive age and repair limits required')
    require(control['observed_at_s'] <= control['now_s'], 'observation cannot be from the future')
    stale = control['now_s'] - control['observed_at_s'] > control['max_age_s']
    overdue = control['now_s'] >= control['deadline_s']
    remaining = max(0, control['repair_limit'] - control['repair_attempts'])
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
        if event['kind'] == 'merge_conflict':
            require(event.get('dependency_state') in {'ready', 'blocked', 'unknown'}, 'conflict dependency_state required')
        # Explicit occurrence separates a genuinely recurring conflict from repeated polls.
        require(isinstance(event.get('occurrence_id'), str) and bool(event['occurrence_id'].strip()), 'occurrence_id required')
        event_key = digest({k: packet[k] for k in ('instance_id', 'worker_thread_id', 'resource_id')} | {
            'kind': event['kind'], 'id': event['id'], 'revision': event['revision'], 'occurrence_id': event['occurrence_id']})
        require(event_key not in seen, 'duplicate event')
        seen.add(event_key)
        # Dependency readiness is a current observation, not a new defect identity.
        signature = digest({k: v for k, v in event.items() if k != 'dependency_state'})
        prior = index.get(event_key)
        if prior:
            require(prior.get('signature') == signature, 'event changed without a new occurrence; reconcile source identity')
        if prior and prior['status'] in {'pending', 'unknown'}:
            action = 'reconcile_delivery'
        elif stale:
            action = 'refresh_observation'
        elif event['revision'] != packet['current_revision']:
            action = 'refresh_stale_evidence'
        elif prior and prior['status'] == 'sent':
            action = 'already_delivered'
        elif overdue:
            action = 'escalate_deadline'
        elif remaining == 0:
            action = 'escalate_repair_budget'
        elif prior and prior['attempts'] >= limit:
            action = 'escalate_exhausted'
        elif state == 'awaiting_approval':
            action = 'escalate_approval'
        elif state in {'awaiting_input', 'exited', 'unknown'}:
            action = 'reconcile_worker'
        elif event.get('dependency_state') == 'blocked':
            action = 'wait_for_dependency'
        elif event.get('dependency_state') == 'unknown':
            action = 'refresh_dependency'
        elif state == 'active':
            action = 'defer_until_idle'
        else:
            action = 'send_to_owner'
            remaining -= 1
        results.append({'event_key': event_key, 'signature': signature, 'kind': event['kind'],
                        'action': action, 'worker_thread_id': packet['worker_thread_id'],
                        'evidence_ref': event['evidence_ref'],
                        'next_attempt': (prior['attempts'] if prior else 0) + 1 if action == 'send_to_owner' else None})
    return {'schema': 'company-os.worker-feedback-plan.v2', 'actions': results,
            'alerts': (['blocker_deadline_reached'] if overdue and events else []),
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
