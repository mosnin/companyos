#!/usr/bin/env python3
"""Check exported organization topology; host readback remains the identity evidence."""
import argparse
import json
from pathlib import Path


def validate(organization):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(isinstance(organization, dict), 'organization must be an object')
    require(organization.get('schema') == 'company-os.organization.v1', 'unsupported organization')
    for field in ('instance_id', 'host', 'host_project_id', 'board_thread_id'):
        require(isinstance(organization.get(field), str) and bool(organization[field].strip()), f'missing {field}')
    actors = organization.get('actors')
    require(isinstance(actors, list) and bool(actors), 'actors required')
    indexed = {}
    for actor in actors:
        require(isinstance(actor, dict), 'actor must be an object')
        identity = actor.get('thread_id')
        require(isinstance(identity, str) and bool(identity.strip()) and not identity.startswith('client-'), 'canonical thread ID required')
        require(identity not in indexed, 'each actor requires its own conversation')
        indexed[identity] = actor
        require(actor.get('role') in ('board', 'executive', 'manager', 'worker'), 'invalid role')
        for field in ('instance_id', 'host', 'host_project_id'):
            require(actor.get(field) == organization[field], f'actor outside organization {field}')
        for field in ('creation_ref', 'readback_ref', 'charter_ref'):
            require(isinstance(actor.get(field), str) and bool(actor[field].strip()), f'missing actor {field}')
        if actor['role'] in ('executive', 'manager'):
            require(actor.get('requested_model') == 'gpt-6-astra', 'management requires Astra')
            require(actor.get('requested_reasoning_effort') == 'medium', 'management requires medium reasoning')
        elif actor['role'] == 'worker':
            require(actor.get('requested_model') == 'gpt-5.6-luna', 'workers retain Luna')
    board_id = organization['board_thread_id']
    require(board_id in indexed and indexed[board_id]['role'] == 'board', 'registered board missing')
    require(sum(actor['role'] == 'board' for actor in actors) == 1, 'exactly one board per organization')
    require(indexed[board_id].get('parent_thread_id') is None, 'board is organization root')
    for identity, actor in indexed.items():
        if identity == board_id:
            continue
        parent = indexed.get(actor.get('parent_thread_id'))
        require(parent is not None, 'parent conversation not registered')
        allowed = {'executive': ('board',), 'manager': ('executive',), 'worker': ('manager',)}
        require(parent['role'] in allowed[actor['role']], 'invalid management parent')
        for field in ('mandate_message_ref', 'acknowledgement_ref'):
            require(isinstance(actor.get(field), str) and bool(actor[field].strip()), f'missing {field}')
        seen = set()
        current = identity
        while current != board_id:
            require(current not in seen, 'management cycle')
            seen.add(current)
            require(current in indexed, 'disconnected hierarchy')
            current = indexed[current].get('parent_thread_id')
    return {'ok': True, 'actors': len(actors), 'status': 'topology_consistent',
            'host_authenticated': False, 'authority_granted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('organization', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(json.loads(args.organization.read_text()))))
    except (ValueError, OSError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
