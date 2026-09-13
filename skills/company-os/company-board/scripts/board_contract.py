#!/usr/bin/env python3
"""Validate exported board handoffs; performs no host calls or authority grants."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(value):
    # Council request/record digests use UTF-8 canonical JSON.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'missing {name}')
    return value


def validate(session, request, record, disposition, current_context, program_version):
    if session.get('schema') != 'company-os.board-session.v1':
        raise ValueError('unsupported board session')
    binding = request.get('framework', {})
    for key in ('instance_id', 'host', 'board_thread_id', 'executive_thread_id'):
        if text(session.get(key), key) != binding.get(key):
            raise ValueError(f'framework binding mismatch: {key}')
    text(session.get('creation_ref'), 'creation_ref')
    if session['board_thread_id'] == session['executive_thread_id']:
        raise ValueError('board needs a separate chat')
    if request.get('project') != session['instance_id']:
        raise ValueError('project must identify the framework instance')
    if type(program_version) is not int or program_version < 1 or binding.get('program_version') != program_version:
        raise ValueError('stale or invalid program version')
    snapshot = binding.get('context_snapshot', {})
    for key in ('organization_id', 'business_slug', 'retrieved_at'):
        text(snapshot.get(key), key)
    documents = snapshot.get('documents')
    if not isinstance(documents, list) or not documents:
        raise ValueError('canonical context documents required')
    seen = set()
    for document in documents:
        identity = text(document.get('id'), 'document id')
        if identity in seen:
            raise ValueError('duplicate context document')
        seen.add(identity)
        if document.get('revision') is None or document.get('revision') == '':
            raise ValueError('document revision required')
        text(document.get('content_hash'), 'content hash')
    # Retrieval time changes on refresh; identity and revision content must not.
    def material(value):
        return {k: value.get(k) for k in ('organization_id', 'business_slug')} | {
            'documents': sorted(value.get('documents', []), key=lambda row: row['id'])}
    if material(snapshot) != material(current_context):
        raise ValueError('context changed: re-ground and reconsult')
    text(current_context.get('retrieved_at'), 'current retrieval time')
    if record.get('schema') != 'council-os.decision.v2' or record.get('status') != 'advisory':
        raise ValueError('validated Council v2 advisory record required')
    if record.get('request_sha256') != digest(request):
        raise ValueError('council request mismatch')
    if disposition.get('schema') != 'company-os.board-disposition.v1':
        raise ValueError('unsupported disposition')
    for key, expected in {'decision_id': request.get('decision_id'),
                          'request_sha256': digest(request), 'record_sha256': digest(record),
                          'executive_thread_id': session['executive_thread_id']}.items():
        if disposition.get(key) != expected:
            raise ValueError(f'disposition mismatch: {key}')
    if disposition.get('action') not in ('adopt', 'modify', 'reject'):
        raise ValueError('executive disposition required')
    for key in ('rationale', 'management_owner', 'success_metric', 'review_trigger'):
        text(disposition.get(key), key)
    return {'ok': True, 'status': 'handoff_consistent', 'authority_granted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('session', 'request', 'record', 'disposition', 'current_context'):
        parser.add_argument(name, type=Path)
    parser.add_argument('current_program_version', type=int)
    args = parser.parse_args()
    try:
        values = [json.loads(getattr(args, name).read_text()) for name in
                  ('session', 'request', 'record', 'disposition', 'current_context')]
        print(json.dumps(validate(*values, args.current_program_version)))
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
