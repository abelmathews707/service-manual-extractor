"""Reviewed, hash-bound cross-unit links for engineering reference reading only.

This log approves a source-to-target association, never vehicle applicability,
content quality or diagnostic completeness. Endpoint records and their own quality
dependencies must be checked again when a link is opened. No link is followed here.
"""

import copy
import json
import os
import re
import tempfile

from .applicability_contracts import _timestamp, digest
from .contract import ContractError, _object, _sha
from .procedure_context import resolve_continuation
from .structured_contracts import record_digest, record_identity

CONTRACT = 'continuation-review/v1'
CHECKS = ('source_compared', 'target_compared', 'conditions_preserved')


def _id(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r'_[0-9a-f]{32}', value):
        raise ContractError('invalid continuation identity')


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ContractError('continuation review needs bounded nonempty text')


def validate_binding(binding):
    _object(binding, 'binding', ('source', 'target', 'reference', 'configuration_ids'))
    for endpoint in ('source', 'target'):
        item = binding[endpoint]
        _object(item, endpoint, ('record_id', 'record_sha256', 'unit_id'))
        _id(item['record_id'], 'record')
        _id(item['unit_id'], 'unit')
        _sha(item['record_sha256'], 'record_sha256')
    _text(binding['reference'])
    ids = binding['configuration_ids']
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise ContractError('continuation requires distinct reviewed configurations')
    for identifier in ids:
        _id(identifier, 'cfg')
    return binding


def link_identity(binding):
    """Stable association ID; endpoint hashes belong to its review revision."""
    return 'link_' + digest([binding['source']['record_id'], binding['target']['record_id'],
                             binding['reference'], sorted(binding['configuration_ids'])])[:32]


def bind_continuation(source, target, *, reference, configuration_ids):
    """Create a proposal binding after callers validate/compare both originals."""
    for record in (source, target):
        if record_identity(record) != record['id'] or record_digest(record) != \
                record['record_sha256']:
            raise ContractError('continuation endpoint identity/content changed')
        if not set(configuration_ids) <= set(record['applicability']['configuration_ids']):
            raise ContractError('continuation endpoint excludes reviewed configuration')
    if reference not in source['original_text']:
        raise ContractError('continuation reference must preserve a source quotation')
    binding = {name: {'record_id': record['id'], 'record_sha256': record['record_sha256'],
                      'unit_id': record['binding']['unit_id']}
               for name, record in (('source', source), ('target', target))}
    binding.update(reference=reference, configuration_ids=sorted(configuration_ids))
    return validate_binding(binding)


def _seal(value):
    value['revision'] = digest({key: item for key, item in value.items() if key != 'revision'})
    return value


def new_continuation_review():
    return _seal({'contract': CONTRACT, 'events': []})


def validate_review(value):
    _object(value, 'review', ('contract', 'events', 'revision'))
    if value['contract'] != CONTRACT or not isinstance(value['events'], list) or \
            value['revision'] != _seal(copy.deepcopy(value))['revision']:
        raise ContractError('invalid continuation review contract/revision')
    latest = {}
    parent = None
    for event in value['events']:
        _object(event, 'event', ('id', 'parent_id', 'link_id', 'binding', 'action', 'reviewer',
                                 'timestamp', 'reason', 'checks'))
        validate_binding(event['binding'])
        if event['link_id'] != link_identity(event['binding']) or event['parent_id'] != parent or \
                event['id'] != digest({k: v for k, v in event.items() if k != 'id'}):
            raise ContractError('continuation review chain/identity changed')
        _object(event['reviewer'], 'reviewer', ('id', 'kind'))
        _text(event['reviewer']['id'])
        if event['reviewer']['kind'] not in ('human', 'agent'):
            raise ContractError('unknown declared engineering reviewer kind')
        _timestamp(event['timestamp'], 'timestamp')
        _text(event['reason'])
        _object(event['checks'], 'checks', CHECKS)
        if any(type(event['checks'][key]) is not bool for key in CHECKS):
            raise ContractError('continuation checks must be booleans')
        prior = latest.get(event['link_id'])
        action = event['action']
        allowed = {'propose': ('approve', 'reject'), 'approve': ('revoke',),
                   'reject': ('propose',), 'revoke': ('propose',)}
        if (action not in allowed.get(prior['action'], ()) if prior else action != 'propose'):
            raise ContractError('invalid continuation review transition')
        if prior and action != 'propose' and event['binding'] != prior['binding']:
            raise ContractError('continuation binding changed during review')
        if action == 'approve' and not all(event['checks'].values()):
            raise ContractError('continuation approval requires all original comparison checks')
        latest[event['link_id']] = event
        parent = event['id']
    return latest


def append_continuation_event(review, binding, *, action, reviewer, timestamp, reason,
                              checks, expected_revision):
    validate_review(review)
    if review['revision'] != expected_revision:
        raise ContractError('continuation review changed; review again')
    value = copy.deepcopy(review)
    event = {'parent_id': value['events'][-1]['id'] if value['events'] else None,
             'link_id': link_identity(binding), 'binding': copy.deepcopy(binding),
             'action': action, 'reviewer': reviewer, 'timestamp': timestamp,
             'reason': reason, 'checks': checks}
    event['id'] = digest(event)
    value['events'].append(event)
    _seal(value)
    validate_review(value)
    return value


def source_link_state(event, record, configuration_id, quality):
    """Recheck the source endpoint without reading any target content."""
    binding = event['binding']
    if event['action'] != 'approve':
        return event['action']
    if binding['source'] != {'record_id': record['id'],
                             'record_sha256': record['record_sha256'],
                             'unit_id': record['binding']['unit_id']}:
        return 'stale'
    if (record_identity(record) != record['id'] or
            record_digest(record) != record['record_sha256'] or
            binding['reference'] not in record['original_text']):
        raise ContractError('continuation source identity/quotation changed')
    if configuration_id not in binding['configuration_ids'] or configuration_id not in \
            record['applicability']['configuration_ids']:
        return 'outside_selection'
    if not (quality.get('approved') is True and quality.get('state') == 'approve' and
            quality.get('record_id') == record['id'] and
            quality.get('record_sha256') == record['record_sha256'] and
            quality.get('intended_use') == 'readable_reference' and
            quality.get('purpose') == 'engineering'):
        return 'source_quality_unapproved'
    return 'available'


def resolve_reviewed_target(binding, configuration_id, *, scope_for, load_unit, quality_for):
    """After source-link admission, check the independently scoped target and hash."""
    validate_binding(binding)
    if configuration_id not in binding['configuration_ids']:
        return {'state': 'withheld', 'reason': 'Link excludes selected configuration'}
    target = binding['target']
    result = resolve_continuation(
        target['record_id'], configuration_id, {target['record_id']: target['unit_id']},
        scope_for=scope_for, load_unit=load_unit, quality_for=quality_for,
        intended_use='readable_reference', purpose='engineering')
    if result['state'] == 'available' and \
            result['record']['record_sha256'] != target['record_sha256']:
        return {'state': 'withheld', 'reason': 'Reviewed destination changed; review link again'}
    return result


def save_continuation_review(path, review, *, expected_revision):
    """Atomic append with optimistic concurrency; callers serialize local writers."""
    validate_review(review)
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    if not os.path.isdir(parent) or os.path.islink(parent) or os.path.islink(target):
        raise ContractError('continuation destination must not be a symlink')
    previous = new_continuation_review()
    if os.path.exists(target):
        with open(target, encoding='utf-8') as stream:
            previous = json.load(stream)
    validate_review(previous)
    if previous['revision'] != expected_revision or \
            review['events'][:len(previous['events'])] != previous['events']:
        raise ContractError('continuation history changed or was removed')
    handle, stage = tempfile.mkstemp(prefix='.continuation-', dir=parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(review, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stage, target)
    finally:
        if os.path.exists(stage):
            os.unlink(stage)
