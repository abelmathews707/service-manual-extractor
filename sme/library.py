"""Validated multi-package library and pre-search vehicle scope assembly."""

import json
import os
from itertools import combinations

from .applicability_contracts import (
    LIBRARY_CONTRACT,
    POLICY_VERSION,
    SCOPE_CONTRACT,
    digest,
    scope_fingerprint,
    sidecar_id,
    validate_evidence,
    validate_library,
    validate_review_overlay,
    validate_scope,
    validate_vocabulary,
)
from .contract import ContractError, load_manifest
from .matching import compile_evidence, match_unit
from .normalize import CONTENT_NAME, _local_file, validate_content
from .source import INVENTORY_NAME, MANIFEST_NAME, SourceError, _sha_file, validate_inventory


def verified_package(path, evidence=None, vocabulary=None):
    """Read a neutral package only after checking every original member hash."""
    root = os.path.abspath(path)
    if os.path.islink(path) or not os.path.isdir(root):
        raise SourceError('library package must be a regular directory')
    manifest = load_manifest(_local_file(root, MANIFEST_NAME))
    with open(_local_file(root, CONTENT_NAME), encoding='utf-8') as stream:
        content = validate_content(json.load(stream), manifest)
    with open(_local_file(root, INVENTORY_NAME), encoding='utf-8') as stream:
        inventory = validate_inventory(json.load(stream))
    if inventory['source_id'] != manifest['source']['id']:
        raise SourceError('library package inventory belongs to another source')
    for member in inventory['members']:
        if _sha_file(_local_file(root, member['path'])) != member['sha256']:
            raise SourceError(f'library original changed: {member["path"]}')
    if evidence is not None:
        if vocabulary is None:
            raise ContractError('evidence validation requires a vocabulary')
        validate_evidence(evidence, manifest, vocabulary)
        if evidence['content_sha256'] != _sha_file(_local_file(root, CONTENT_NAME)):
            raise SourceError('library evidence binds a different content generation')
    return {'root': root, 'manifest': manifest, 'content': content,
            'evidence': evidence, 'manifest_sha256': digest(manifest),
            'content_sha256': _sha_file(_local_file(root, CONTENT_NAME))}


def make_library(package_records, vocabulary, review, evidence_history=None):
    """Construct a v1 library manifest without collapsing source occurrences.

    ``package_records`` include a canonical library-relative ``root`` and the
    result of ``verified_package``. Distinct roots remain separate even when
    their source IDs and publication titles are identical.
    """
    validate_vocabulary(vocabulary)
    sources = {}
    for record in package_records:
        evidence = record['evidence']
        if evidence is not None:
            existing = sources.get(evidence['source_id'])
            if existing is not None and existing['revision'] != evidence['revision']:
                raise ContractError('one source ID has multiple evidence generations')
            sources[evidence['source_id']] = evidence
    validate_review_overlay(review, list(sources.values()), vocabulary,
                            evidence_history)
    packages = []
    for record in package_records:
        root = record['relative_root']
        source_id = record['manifest']['source']['id']
        packages.append({'occurrence_id': sidecar_id('occ', source_id, root),
                         'root': root, 'source_id': source_id,
                         'manifest_sha256': record['manifest_sha256'],
                         'content_sha256': record['content_sha256'],
                         'status': record.get('status', 'active'),
                         **({'superseded_by': record['superseded_by']}
                            if 'superseded_by' in record else {})})
    value = {'contract': LIBRARY_CONTRACT,
             'vocabulary_revision': vocabulary['revision'],
             'review_revision': review['revision'],
             'policy_version': POLICY_VERSION, 'packages': packages}
    value['revision'] = digest(value)
    package_index = {record['relative_root']: {
        'source_id': record['manifest']['source']['id'],
        'manifest_sha256': record['manifest_sha256'],
        'content_sha256': record['content_sha256']} for record in package_records}
    return validate_library(value, package_index)


def _scope_record(library, vocabulary, selection, mode, include_reference, browse_all,
                  eligible):
    result = {'contract': SCOPE_CONTRACT,
              'library_revision': library['revision'],
              'vocabulary_revision': vocabulary['revision'],
              'review_revision': library['review_revision'],
              'policy_version': POLICY_VERSION, 'selection': selection,
              'mode': mode, 'include_reference': include_reference,
              'browse_all': browse_all, 'eligible': eligible}
    result['fingerprint'] = scope_fingerprint(result)
    return result


def resolve_scope(library, package_records, vocabulary, review, selection, *,
                  mode='confirmed', include_reference=False, browse_all=False,
                  evidence_history=None, compiled_sources=None, _validated=False):
    """Choose eligible unit IDs before accessing text or building an index."""
    if not _validated:
        validate_library(library)
        validate_vocabulary(vocabulary)
    sources = {record['evidence']['source_id']: record['evidence']
               for record in package_records if record['evidence'] is not None}
    compiled_sources = compiled_sources or {
        source_id: compile_evidence(item, next(record['manifest'] for record in package_records
                                               if record['evidence'] is not None and
                                               record['evidence']['source_id'] == source_id))
        for source_id, item in sources.items()}
    if not _validated:
        validate_review_overlay(review, list(sources.values()), vocabulary,
                                evidence_history)
    if (library['vocabulary_revision'] != vocabulary['revision'] or
            library['review_revision'] != review['revision']):
        raise ContractError('library eligibility snapshot is stale')
    if browse_all and selection:
        raise ContractError('browse-all requires an empty vehicle selection')
    decisions, occurrences = {}, {}
    active = {item['occurrence_id']: item for item in library['packages']
              if item['status'] == 'active'}
    for record in package_records:
        occurrence = sidecar_id('occ', record['manifest']['source']['id'],
                                record['relative_root'])
        if occurrence not in active:
            continue
        if (record['manifest_sha256'] != active[occurrence]['manifest_sha256'] or
                record['content_sha256'] != active[occurrence]['content_sha256']):
            raise ContractError('package record changed after library validation')
        evidence = record['evidence']
        if evidence is None:
            continue
        for unit in evidence['units']:
            unit_id = unit['id']
            if unit_id in decisions:
                occurrences[unit_id].append(occurrence)
                continue
            if browse_all:
                state = unit['search']['state']
                decision = {'state': 'possible', 'reason_codes': ['incomplete_selection'],
                            'search_eligible': mode == 'include_possible' and
                            state != 'metadata_only',
                            'evidence_ids': [], 'review_event_ids': [],
                            'missing_qualifiers': [], 'conflicts': []}
            else:
                decision = match_unit(evidence, record['manifest'], vocabulary,
                                      unit_id, selection, mode=mode,
                                      include_reference=include_reference,
                                      review=review, evidence_history=evidence_history,
                                      validate=False,
                                      compiled=compiled_sources[evidence['source_id']])
            decisions[unit_id] = decision
            occurrences[unit_id] = [occurrence]
    eligible = [{'unit_id': unit_id, 'state': decision['state'],
                 'reason_codes': decision['reason_codes'],
                 'evidence_ids': decision['evidence_ids'],
                 'review_event_ids': decision['review_event_ids']}
                for unit_id, decision in sorted(decisions.items())
                if decision['search_eligible']]
    scope = _scope_record(library, vocabulary, selection, mode, include_reference,
                          browse_all, eligible)
    evidence_ids = {item['id'] for source in sources.values()
                    for item in source['assertions']}
    review_ids = {item['id'] for item in review['events']}
    validate_scope(scope, library, vocabulary, set(decisions), evidence_ids, review_ids)
    counts = {}
    for decision in decisions.values():
        state = decision['state']
        counts[state] = counts.get(state, 0) + 1
    return {'scope': scope, 'decisions': decisions,
            'unit_occurrences': occurrences, 'counts': counts,
            'no_content': not bool(eligible)}


def scope_selections(vocabulary):
    """Finite known selections, including incomplete and unknown qualifiers."""
    validate_vocabulary(vocabulary)
    choices = [({}, False), ({}, True)]
    seen = set()
    for config in vocabulary['configurations']:
        full = {'make_id': config['make_id'], 'model_id': config['model_id'],
                'model_year': config['model_year'], 'engine_id': config['engine_id']}
        candidates = [
            {'make_id': config['make_id']},
            {'make_id': config['make_id'], 'model_id': config['model_id']},
            {'make_id': config['make_id'], 'model_id': config['model_id'],
             'model_year': config['model_year']},
            full,
        ]
        if config['qualifiers']:
            names = sorted(config['qualifiers'])
            # Export every qualifier-presence state up to a safe 64-subset
            # bound; larger combinations remain available to Python on demand.
            subsets = (range(1, len(names) + 1) if len(names) <= 6 else
                       (1, len(names) - 1, len(names)))
            for count in subsets:
                for chosen in combinations(names, count):
                    candidates.append({**full, 'qualifiers': {
                        name: config['qualifiers'][name] for name in chosen}})
        for selection in candidates:
            key = digest(selection)
            if key not in seen:
                choices.append((selection, False))
                seen.add(key)
    return choices
