#!/usr/bin/env python3
"""Reconcile source observations and publish via the existing revision-checked ledger."""
from copy import deepcopy

KIND = 'orchestration-alerts'
COLUMNS = ['Instance', 'Alert', 'Resource', 'Owner', 'Signal', 'Status', 'Revision', 'Sequence', 'Observed (Unix seconds)', 'Evidence']


def reconcile(content, packet):
    """Pure projection. Missing events are not resolutions. Clocks are host-supplied."""
    if not isinstance(packet, dict) or packet.get('schema') != 'company-os.alert-observations.v1':
        raise ValueError('unsupported alert observations')
    instance = packet.get('instance_id')
    if not isinstance(instance, str) or not instance or instance != instance.strip():
        raise ValueError('instance_id required')
    now, max_age = packet.get('now_s'), packet.get('max_age_s')
    if type(now) is not int or now < 0 or type(max_age) is not int or max_age <= 0:
        raise ValueError('valid clock and freshness allowance required')
    events = packet.get('events')
    if not isinstance(events, list):
        raise ValueError('events required')
    rows = content.get('alerts', {}).get('rows', [])
    index = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != len(COLUMNS) or not all(isinstance(x, str) for x in row):
            raise ValueError('invalid stored alert row')
        key = tuple(row[:2])
        if key in index or row[4] not in {'active', 'clear', 'unknown'}:
            raise ValueError('invalid or duplicate stored alert')
        if not row[7].isdigit() or not row[8].isdigit():
            raise ValueError('invalid stored observation ordering')
        index[key] = row[:]
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('event must be an object')
        for field in ('id', 'resource', 'owner', 'revision', 'evidence_ref'):
            if not isinstance(event.get(field), str) or not event[field] or event[field] != event[field].strip():
                raise ValueError('missing or ambiguous event ' + field)
        signal = event.get('signal')
        seq, at = event.get('sequence'), event.get('observed_at_s')
        if signal not in {'active', 'clear', 'unknown'} or type(seq) is not int or seq < 0 or type(at) is not int or not 0 <= at <= now:
            raise ValueError('invalid signal or observation ordering')
        key = (instance, event['id'])
        if key in seen:
            raise ValueError('duplicate observation')
        seen.add(key)
        row = [instance, event['id'], event['resource'], event['owner'], signal, '', event['revision'], str(seq), str(at), event['evidence_ref']]
        old = index.get(key)
        if old:
            if old[2] != row[2]:
                raise ValueError('alert identity cannot move to another resource')
            if seq < int(old[7]):
                continue
            if seq == int(old[7]):
                if row[:5] + row[6:] != old[:5] + old[6:]:
                    raise ValueError('conflicting observation at the same sequence')
                continue
            if at < int(old[8]):
                raise ValueError('new observation cannot move time backward')
        # Old evidence cannot clear an existing alert or introduce an actionable one.
        if now - at > max_age:
            continue
        index[key] = row
    for key, row in index.items():
        if key[0] != instance:
            continue
        if int(row[8]) > now:
            raise ValueError('clock predates stored observation')
        signal = row[4]
        row[5] = ('resolved' if signal == 'clear' else
                  'stale' if now - int(row[8]) > max_age else
                  'needs verification' if signal == 'unknown' else 'active')
    result = deepcopy(content)
    result['alerts'] = {'rows': [index[key] for key in sorted(index)]}
    return result


def sync(client, packet, *, branch):
    """One read/reconcile/CAS write. Errors and uncertain writes propagate; never retry blindly."""
    if not isinstance(branch, str) or not branch.strip() or branch.strip() == 'main':
        raise ValueError('an existing context branch is required')
    client.config_pull()
    registry = client.schema_describe(kind=KIND)
    template = next((k for k in registry.get('kinds', []) if k.get('kind') == KIND), None)
    field = next((f for f in (template or {}).get('fields', []) if f.get('id') == 'alerts'), None)
    if not field or field.get('type') != 'table' or [c.get('label') for c in field.get('columns', []) if isinstance(c, dict)] != COLUMNS:
        raise ValueError('hosted orchestration-alerts schema is unavailable or incompatible')
    document = client.document_get(KIND, branch=branch)
    if document.get('kind') != KIND or type(document.get('revision')) is not int or document['revision'] < 0:
        raise ValueError('invalid ledger document')
    content = document.get('content')
    if not isinstance(content, dict):
        raise ValueError('invalid ledger content')
    updated = reconcile(content, packet)
    if updated == content:
        return {'status': 'unchanged', 'revision': document['revision']}
    receipt = client.document_put(kind=KIND, doc_slug=document['slug'], branch=branch,
        base_revision=document['revision'], content=updated,
        message='Reconcile orchestration alerts against source observations')
    return {'status': 'write_returned', 'receipt': receipt}
