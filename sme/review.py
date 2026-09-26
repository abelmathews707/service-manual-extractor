"""Portable append-only human review overlay and bounded shared-content leads."""

import copy
import json
import os
import re
import tempfile

from .applicability_contracts import (
    POLICY_VERSION,
    REVIEW_CONTRACT,
    digest,
    sidecar_id,
    validate_review_overlay,
    validate_vocabulary,
)
from .contract import ContractError

_IDENTIFIER = re.compile(r'(?<![A-Z0-9])[A-Z0-9]{4,}-[A-Z0-9-]{3,}(?![A-Z0-9])')


def _sets(evidence_sets):
    return [evidence_sets] if isinstance(evidence_sets, dict) else list(evidence_sets)


def new_overlay(evidence_sets, vocabulary):
    """Start a separate decision log; generated evidence remains immutable."""
    validate_vocabulary(vocabulary)
    sets = _sets(evidence_sets)
    value = {'contract': REVIEW_CONTRACT,
             'vocabulary_revision': vocabulary['revision'],
             'evidence_snapshots': sorted(
                 [{'source_id': item['source_id'], 'revision': item['revision']}
                  for item in sets], key=lambda item: item['source_id']),
             'policy_version': POLICY_VERSION, 'events': []}
    value['revision'] = digest(value)
    return validate_review_overlay(value, sets, vocabulary)


def _commit(overlay, events, evidence_sets, vocabulary, history=None):
    candidate = {**overlay, 'events': events}
    candidate['revision'] = digest({key: value for key, value in candidate.items()
                                    if key != 'revision'})
    return validate_review_overlay(candidate, _sets(evidence_sets), vocabulary, history)


def propose(overlay, evidence_sets, vocabulary, *, source_id, subject_id,
            relation, target_configuration_ids, evidence_ids, reviewer,
            timestamp, reason, proposal_id=None, history=None):
    """Append a cited, exact-scope proposal; this never grants applicability."""
    sets = _sets(evidence_sets)
    validate_review_overlay(overlay, sets, vocabulary, history)
    source = next((item for item in sets if item['source_id'] == source_id), None)
    if source is None:
        raise ContractError('proposal source is not in the current evidence set')
    assertions = {item['id']: item for item in source['assertions']}
    if not evidence_ids or any(identifier not in assertions for identifier in evidence_ids):
        raise ContractError('proposal must bind current source assertions')
    bindings = [{'id': identifier, 'digest': assertions[identifier]['digest']}
                for identifier in sorted(set(evidence_ids))]
    if proposal_id is None:
        proposal_id = digest([source_id, subject_id, relation,
                              sorted(set(target_configuration_ids)), bindings])
    event = {'action': 'propose', 'proposal_id': proposal_id,
             'subject_id': subject_id, 'relation': relation,
             'target_configuration_ids': sorted(set(target_configuration_ids)),
             'evidence_bindings': bindings, 'source_id': source_id,
             'evidence_revision': source['revision'],
             'vocabulary_revision': vocabulary['revision'],
             'policy_version': POLICY_VERSION, 'reviewer': reviewer,
             'timestamp': timestamp, 'reason': reason}
    event['id'] = sidecar_id('review', digest(event))
    return _commit(overlay, overlay['events'] + [event], sets, vocabulary, history)


def decide(overlay, evidence_sets, vocabulary, *, prior_event_id, action,
           reviewer, timestamp, reason, history=None):
    """Accept/reject a proposal or revoke/supersede an accepted decision."""
    sets = _sets(evidence_sets)
    validate_review_overlay(overlay, sets, vocabulary, history)
    prior = next((item for item in overlay['events'] if item['id'] == prior_event_id), None)
    if prior is None:
        raise ContractError('prior review event does not exist')
    event = {key: copy.deepcopy(value) for key, value in prior.items()
             if key not in ('id', 'action', 'prior_event_id', 'reviewer', 'timestamp', 'reason')}
    event.update(action=action, prior_event_id=prior_event_id, reviewer=reviewer,
                 timestamp=timestamp, reason=reason)
    event['id'] = sidecar_id('review', digest(event))
    return _commit(overlay, overlay['events'] + [event], sets, vocabulary, history)


def rebase(overlay, evidence_sets, vocabulary, history):
    """Move the current snapshot forward while retaining every historic event.

    The caller must retain old evidence snapshots in ``history``. An old
    acceptance becomes stale; it is never retargeted to new evidence by hash.
    """
    sets = _sets(evidence_sets)
    candidate = {**overlay,
                 'vocabulary_revision': vocabulary['revision'],
                 'evidence_snapshots': sorted(
                     [{'source_id': item['source_id'], 'revision': item['revision']}
                      for item in sets], key=lambda item: item['source_id'])}
    candidate['revision'] = digest({key: value for key, value in candidate.items()
                                    if key != 'revision'})
    return validate_review_overlay(candidate, sets, vocabulary, history)


def load_overlay(path, evidence_sets, vocabulary, history=None):
    with open(path, encoding='utf-8') as stream:
        value = json.load(stream)
    return validate_review_overlay(value, _sets(evidence_sets), vocabulary, history)


def save_overlay(path, overlay, evidence_sets, vocabulary, history=None):
    """Atomically save a validated overlay without erasing prior log events."""
    validate_review_overlay(overlay, _sets(evidence_sets), vocabulary, history)
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    if not os.path.isdir(parent) or os.path.islink(parent) or os.path.islink(target):
        raise ContractError('review destination must have a regular parent and no symlink')
    if os.path.exists(target):
        with open(target, encoding='utf-8') as stream:
            previous = json.load(stream)
        if (previous.get('contract') != REVIEW_CONTRACT or
                previous.get('policy_version') != POLICY_VERSION or
                {item['source_id'] for item in previous.get('evidence_snapshots', [])} !=
                {item['source_id'] for item in overlay['evidence_snapshots']}):
            raise ContractError('existing review file belongs to another review set')
        if overlay['events'][:len(previous['events'])] != previous['events']:
            raise ContractError('review history cannot be edited or removed')
    handle, stage = tempfile.mkstemp(prefix='.review-', suffix='.json', dir=parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(overlay, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stage, target)
    finally:
        if os.path.exists(stage):
            os.unlink(stage)
    return target


def shared_content_proposals(sources, vocabulary, limit=100):
    """Suggest, never approve, exact duplicates or contextual part references.

    ``sources`` are dicts with validated evidence and normalized content. A
    lead is emitted only when the target has an exact known vehicle tuple and
    the source has a cited assertion on the relevant document/unit. This is a
    bounded review queue, not a cross-manual fitment assertion.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ContractError('proposal limit must be 1–1000')
    configurations = {item['id']: item for item in vocabulary['configurations']}
    records = []
    for source in sources:
        evidence = source['evidence']
        assertions = evidence['assertions']
        titles = {document['id']: document['title']
                  for publication in source.get('manifest', {}).get('publications', [])
                  for document in publication['documents']}
        units = {unit['document_id']: unit for unit in evidence['units']
                 if unit['kind'] in ('section', 'region', 'table')}
        for document in source['content']['documents']:
            unit = units.get(document['id'])
            if not unit:
                continue
            cited = [item for item in assertions if item['subject_id'] == unit['id']]
            if not cited:
                continue
            text = document.get('text', '')
            identifiers = set(_IDENTIFIER.findall(text.upper()))
            records.append({'source_id': evidence['source_id'], 'unit': unit,
                            'document': document, 'assertions': cited,
                            'title': titles.get(document['id'], document.get('title', '')),
                            'identifiers': identifiers})
    results, seen = [], set()
    for source in records:
        for target in records:
            if source['source_id'] == target['source_id']:
                continue
            source_text = source['document'].get('text', '')
            target_text = target['document'].get('text', '')
            same_text = (len(source_text) >= 80 and
                         digest(source_text) == digest(target_text))
            shared_ids = source['identifiers'] & target['identifiers']
            title = target['title']
            explicit_link = bool(len(title) >= 8 and re.search(
                r'\b(?:see|refer to)\s+' + re.escape(title) + r'\b',
                source_text, re.I))
            if not same_text and not shared_ids and not explicit_link:
                continue
            target_ids = set()
            for assertion in target['assertions']:
                for alternative in assertion['alternatives']:
                    if all(alternative[key]['state'] == 'exact'
                           for key in ('make', 'model', 'year', 'engine')):
                        for identifier, config in configurations.items():
                            if (config['make_id'], config['model_id'], config['model_year'],
                                config['engine_id']) == tuple(
                                    alternative[key]['value']
                                    for key in ('make', 'model', 'year', 'engine')):
                                target_ids.add(identifier)
            if not target_ids:
                continue
            relation = ('duplicate_content' if same_text else
                        'section_applies' if explicit_link else 'part_mentioned')
            key = (source['source_id'], source['unit']['id'],
                   target['source_id'], target['unit']['id'], relation)
            if key in seen:
                continue
            seen.add(key)
            results.append({'source_id': source['source_id'],
                            'subject_id': source['unit']['id'], 'relation': relation,
                            'target_configuration_ids': sorted(target_ids),
                            'evidence_ids': sorted(item['id'] for item in source['assertions']),
                            'basis': {'target_source_id': target['source_id'],
                                      'target_unit_id': target['unit']['id'],
                                      'shared_identifiers': sorted(shared_ids),
                                      'same_text': same_text,
                                      'explicit_cross_reference': explicit_link}})
            if len(results) == limit:
                return results
    return results
