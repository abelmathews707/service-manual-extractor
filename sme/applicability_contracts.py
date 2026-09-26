"""Portable vehicle/applicability sidecar contracts, independent of manifest v1.

These validators freeze record shape and referential integrity. Matching and
persistent review transitions are implemented by later plan steps.
"""

import hashlib
import json
import re
from datetime import datetime

from sme.contract import ContractError, canonical_path, validate_manifest

VOCABULARY_CONTRACT = 'vehicle-vocabulary/v1'
EVIDENCE_CONTRACT = 'applicability-evidence/v1'
REVIEW_CONTRACT = 'applicability-review/v1'
LIBRARY_CONTRACT = 'service-manual-library/v1'
SCOPE_CONTRACT = 'vehicle-scope/v1'
POLICY_VERSION = 'vehicle-applicability-policy/v1'

MODES = ('confirmed', 'include_possible')
MODE_LABELS = {
    'confirmed': 'Confirmed matches',
    'include_possible': 'Include possible matches',
}
REFERENCE_LABEL = 'Include reference material'
REASON_CODES = (
    'explicit_source', 'reviewed', 'incomplete_selection', 'missing_make',
    'missing_model', 'missing_year', 'missing_engine', 'missing_qualifier',
    'conflicting_child', 'excluded_by_source', 'generic_reference',
    'unknown_identity', 'stale_review', 'mixed_content', 'pending_cross_make',
    'unmapped_package', 'no_eligible_units',
)
_SHA = re.compile(r'^[0-9a-f]{64}$')
_KEY = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
_ID = re.compile(r'^(make|model|engine|cfg|unit|ev|review|occ)_[0-9a-f]{32}$')
_ID_PREFIXES = {'make', 'model', 'engine', 'cfg', 'unit', 'ev', 'review', 'occ'}
_QUALIFIERS = {'transmission', 'drivetrain', 'vin', 'rpo', 'production_date',
               'market', 'cab', 'chassis', 'fuel'}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def sidecar_id(kind, *parts):
    if kind not in _ID_PREFIXES or not parts or any(not isinstance(p, str) or not p
                                                     for p in parts):
        raise ContractError('invalid sidecar ID kind or parts')
    material = ('vehicle-applicability-v1', kind) + parts
    return f'{kind}_{hashlib.sha256(chr(0).join(material).encode()).hexdigest()[:32]}'


def configuration_id(make_id, model_id, year, engine_id, qualifiers=None):
    return sidecar_id('cfg', make_id, model_id, str(year), engine_id,
                      canonical_json(qualifiers or {}))


def unit_id(generation_sha256, document_id, kind, selector):
    return sidecar_id('unit', generation_sha256, document_id, kind, selector)


def assertion_digest(assertion):
    return digest({key: value for key, value in assertion.items()
                   if key not in ('id', 'digest')})


def evidence_revision(value):
    return digest({key: item for key, item in value.items() if key != 'revision'})


def scope_fingerprint(value):
    fields = ('library_revision', 'vocabulary_revision', 'review_revision',
              'policy_version', 'selection', 'mode', 'include_reference', 'browse_all')
    return digest({key: value[key] for key in fields})


def _error(path, message):
    raise ContractError(f'{path}: {message}')


def _record(value, path, required, optional=()):
    if not isinstance(value, dict):
        _error(path, 'must be an object')
    missing = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if missing:
        _error(path, f'missing {", ".join(sorted(missing))}')
    if extra:
        _error(path, f'unknown fields {", ".join(sorted(extra))}')


def _array(value, path, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        _error(path, 'must be an array' + (' with at least one item' if nonempty else ''))


def _text(value, path):
    if not isinstance(value, str) or not value.strip():
        _error(path, 'must be a non-empty string')


def _sha(value, path):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        _error(path, 'must be a lowercase SHA-256')


def _id(value, path, prefix):
    if not isinstance(value, str) or not _ID.fullmatch(value) or not value.startswith(prefix + '_'):
        _error(path, f'must be a {prefix} sidecar ID')


def _v1_id(value, path, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r'_[0-9a-f]{32}', value):
        _error(path, f'must be a {prefix} manifest-v1 ID')


def _year(value, path):
    if type(value) is not int or not 1886 <= value <= 2100:
        _error(path, 'must be a model year from 1886 through 2100')


def _timestamp(value, path):
    _text(value, path)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        _error(path, 'must be an ISO 8601 timestamp with timezone')
    if parsed.tzinfo is None:
        _error(path, 'must include a timezone')
    return parsed


def _revision(value, path, record):
    _sha(value, path)
    if value != digest({key: item for key, item in record.items() if key != 'revision'}):
        _error(path, 'does not match the canonical record content')


def _citation(value, path):
    _record(value, path, ('kind', 'path'), ('page', 'fragment'))
    if value['kind'] not in ('page', 'path'):
        _error(f'{path}.kind', 'must be page or path')
    try:
        if canonical_path(value['path']) != value['path']:
            _error(f'{path}.path', 'must use canonical relative spelling')
    except ContractError as exc:
        _error(f'{path}.path', str(exc))
    if value['kind'] == 'page':
        if type(value.get('page')) is not int or value['page'] < 1:
            _error(f'{path}.page', 'must be a positive page number')
    elif 'page' in value:
        _error(f'{path}.page', 'is only valid for a page citation')
    if 'fragment' in value:
        _text(value['fragment'], f'{path}.fragment')


def validate_vocabulary(value):
    """Validate canonical names, scoped aliases and known vehicle tuples."""
    _record(value, 'vocabulary', ('contract', 'revision', 'makes', 'models',
                                  'engines', 'configurations', 'aliases'))
    if value['contract'] != VOCABULARY_CONTRACT:
        _error('vocabulary.contract', 'unsupported contract')
    for field in ('makes', 'models', 'engines', 'configurations', 'aliases'):
        _array(value[field], f'vocabulary.{field}')
    ids = set()
    makes = {}
    models = {}
    engines = {}
    configurations = {}
    for index, make in enumerate(value['makes']):
        path = f'vocabulary.makes[{index}]'
        _record(make, path, ('id', 'key', 'name'))
        _keyed_entity(make, path, 'make', (make['key'],))
        _unique_id(make['id'], path, ids)
        makes[make['id']] = make
    for index, model in enumerate(value['models']):
        path = f'vocabulary.models[{index}]'
        _record(model, path, ('id', 'key', 'name', 'make_id'), ('family',))
        _id(model['make_id'], f'{path}.make_id', 'make')
        if model['make_id'] not in makes:
            _error(f'{path}.make_id', 'does not resolve to a make')
        _keyed_entity(model, path, 'model', (model['make_id'], model['key']))
        if 'family' in model:
            _text(model['family'], f'{path}.family')
        _unique_id(model['id'], path, ids)
        models[model['id']] = model
    for index, engine in enumerate(value['engines']):
        path = f'vocabulary.engines[{index}]'
        _record(engine, path, ('id', 'key', 'name', 'manufacturer', 'fuel',
                               'displacement_l'), ('code',))
        _text(engine['manufacturer'], f'{path}.manufacturer')
        if not _KEY.fullmatch(engine['manufacturer']):
            _error(f'{path}.manufacturer', 'must be a stable slug')
        _keyed_entity(engine, path, 'engine', (engine['manufacturer'], engine['key']))
        _text(engine['fuel'], f'{path}.fuel')
        if (type(engine['displacement_l']) not in (int, float) or
                not 0 < engine['displacement_l'] < 30):
            _error(f'{path}.displacement_l', 'must be a positive numeric displacement')
        if 'code' in engine:
            _text(engine['code'], f'{path}.code')
        _unique_id(engine['id'], path, ids)
        engines[engine['id']] = engine
    for index, config in enumerate(value['configurations']):
        path = f'vocabulary.configurations[{index}]'
        _record(config, path, ('id', 'make_id', 'model_id', 'model_year', 'engine_id',
                               'qualifiers'))
        for field, collection, prefix in (('make_id', makes, 'make'),
                                          ('model_id', models, 'model'),
                                          ('engine_id', engines, 'engine')):
            _id(config[field], f'{path}.{field}', prefix)
            if config[field] not in collection:
                _error(f'{path}.{field}', 'does not resolve in this vocabulary')
        if models[config['model_id']]['make_id'] != config['make_id']:
            _error(path, 'model belongs to a different make')
        _year(config['model_year'], f'{path}.model_year')
        _qualifier_values(config['qualifiers'], f'{path}.qualifiers')
        expected = configuration_id(config['make_id'], config['model_id'],
                                    config['model_year'], config['engine_id'],
                                    config['qualifiers'])
        _id(config['id'], f'{path}.id', 'cfg')
        if config['id'] != expected:
            _error(f'{path}.id', f'does not match tuple; expected {expected}')
        _unique_id(config['id'], path, ids)
        configurations[config['id']] = config
    alias_scopes = {}
    for index, alias in enumerate(value['aliases']):
        path = f'vocabulary.aliases[{index}]'
        _record(alias, path, ('literal', 'target_id', 'evidence'),
                ('make_id', 'year_start', 'year_end'))
        _text(alias['literal'], f'{path}.literal')
        target = alias['target_id']
        if target not in makes and target not in models and target not in engines:
            _error(f'{path}.target_id', 'does not resolve to a make, model or engine')
        if 'make_id' in alias and alias['make_id'] not in makes:
            _error(f'{path}.make_id', 'does not resolve to a make')
        if ('year_start' in alias) != ('year_end' in alias):
            _error(path, 'year_start and year_end must appear together')
        start, end = alias.get('year_start', 1886), alias.get('year_end', 2100)
        _year(start, f'{path}.year_start')
        _year(end, f'{path}.year_end')
        if start > end:
            _error(path, 'invalid alias year range')
        _record(alias['evidence'], f'{path}.evidence', ('source_id', 'citation'))
        _v1_id(alias['evidence']['source_id'], f'{path}.evidence.source_id', 'src')
        _citation(alias['evidence']['citation'], f'{path}.evidence.citation')
        key = (alias['literal'].casefold(), target.split('_', 1)[0])
        for previous in alias_scopes.get(key, []):
            make_overlap = ('make_id' not in previous or 'make_id' not in alias or
                            previous['make_id'] == alias['make_id'])
            year_overlap = max(previous.get('year_start', 1886), start) <= min(
                previous.get('year_end', 2100), end)
            if make_overlap and year_overlap and previous['target_id'] != target:
                _error(path, 'ambiguous alias overlaps a different target')
        alias_scopes.setdefault(key, []).append(alias)
    _revision(value['revision'], 'vocabulary.revision', value)
    return value


def _keyed_entity(value, path, kind, parts):
    _id(value['id'], f'{path}.id', kind)
    _text(value['key'], f'{path}.key')
    _text(value['name'], f'{path}.name')
    if not _KEY.fullmatch(value['key']):
        _error(f'{path}.key', 'must be a stable slug')
    expected = sidecar_id(kind, *parts)
    if value['id'] != expected:
        _error(f'{path}.id', f'does not match canonical key; expected {expected}')


def _unique_id(value, path, seen):
    if value in seen:
        _error(path, f'duplicate ID {value}')
    seen.add(value)


def _qualifier_values(value, path):
    if not isinstance(value, dict) or set(value) - _QUALIFIERS:
        _error(path, 'must use known qualifier names')
    for key, item in value.items():
        _text(item, f'{path}.{key}')


def _dimension(value, path, kind, ids=None):
    _record(value, path, ('state',), ('value', 'start', 'end'))
    state = value['state']
    allowed = {'unknown', 'not_applicable', 'exact'}
    if kind == 'engine' or kind == 'qualifier':
        allowed.add('all_in_scope')
    if kind == 'year':
        allowed.add('range')
    if state not in allowed:
        _error(f'{path}.state', 'unsupported state for this dimension')
    if state == 'exact':
        if set(value) != {'state', 'value'}:
            _error(path, 'exact requires only value')
        if kind == 'year':
            _year(value['value'], f'{path}.value')
        elif kind == 'qualifier':
            _text(value['value'], f'{path}.value')
        elif value['value'] not in ids:
            _error(f'{path}.value', 'does not resolve in the vocabulary')
    elif state == 'range':
        if set(value) != {'state', 'start', 'end'}:
            _error(path, 'range requires start and end')
        _year(value['start'], f'{path}.start')
        _year(value['end'], f'{path}.end')
        if value['start'] > value['end']:
            _error(path, 'invalid year range')
    elif set(value) != {'state'}:
        _error(path, f'{state} may not carry a value or range')


def _alternative(value, path, vocabulary):
    _record(value, path, ('make', 'model', 'year', 'engine', 'qualifiers'))
    makes = {item['id']: item for item in vocabulary['makes']}
    models = {item['id']: item for item in vocabulary['models']}
    engines = {item['id']: item for item in vocabulary['engines']}
    for field, ids in (('make', makes), ('model', models), ('year', None),
                       ('engine', engines)):
        _dimension(value[field], f'{path}.{field}', field, ids)
    qualifiers = value['qualifiers']
    if not isinstance(qualifiers, dict) or set(qualifiers) - _QUALIFIERS:
        _error(f'{path}.qualifiers', 'must use known qualifier names')
    for name, predicate in qualifiers.items():
        _dimension(predicate, f'{path}.qualifiers.{name}', 'qualifier')
    make = value['make']
    model = value['model']
    year = value['year']
    engine = value['engine']
    if model['state'] == 'exact':
        owner = models[model['value']]['make_id']
        if make['state'] != 'exact' or make['value'] != owner:
            _error(path, 'an exact model requires its exact make')
    if engine['state'] == 'all_in_scope' and not (
        make['state'] == model['state'] == 'exact' and year['state'] in ('exact', 'range')
    ):
        _error(path, 'all engines must be bounded by make, model and year')
    if (make['state'] == model['state'] == year['state'] == engine['state'] == 'exact'):
        match = any(config['make_id'] == make['value'] and
                    config['model_id'] == model['value'] and
                    config['model_year'] == year['value'] and
                    config['engine_id'] == engine['value']
                    for config in vocabulary['configurations'])
        if not match:
            _error(path, 'exact tuple is absent from known valid configurations')


def validate_evidence(value, manifest, vocabulary):
    """Bind immutable source statements and sidecar units to manifest v1."""
    validate_manifest(manifest)
    validate_vocabulary(vocabulary)
    _record(value, 'evidence', ('contract', 'revision', 'source_id', 'source_sha256',
                                'manifest_sha256', 'content_sha256',
                                'generation_sha256', 'vocabulary_revision',
                                'units', 'assertions'))
    if value['contract'] != EVIDENCE_CONTRACT:
        _error('evidence.contract', 'unsupported contract')
    if (value['source_id'] != manifest['source']['id'] or
            value['source_sha256'] != manifest['source']['sha256']):
        _error('evidence.source_id', 'does not match the immutable source')
    for field in ('source_sha256', 'manifest_sha256', 'content_sha256',
                  'generation_sha256', 'vocabulary_revision'):
        _sha(value[field], f'evidence.{field}')
    if value['manifest_sha256'] != digest(manifest):
        _error('evidence.manifest_sha256', 'does not match manifest content')
    if value['generation_sha256'] != digest([value['manifest_sha256'], value['content_sha256']]):
        _error('evidence.generation_sha256', 'does not match manifest/content generation')
    if value['vocabulary_revision'] != vocabulary['revision']:
        _error('evidence.vocabulary_revision', 'does not match vocabulary')
    _array(value['units'], 'evidence.units')
    _array(value['assertions'], 'evidence.assertions')
    publications = {p['id']: p for p in manifest['publications']}
    documents = {d['id']: d for p in manifest['publications'] for d in p['documents']}
    units = {}
    for index, unit in enumerate(value['units']):
        path = f'evidence.units[{index}]'
        _record(unit, path, ('id', 'document_id', 'kind', 'selector', 'original_sha256',
                             'citation', 'mixed_content', 'search'), ('parent_unit_id',))
        _v1_id(unit['document_id'], f'{path}.document_id', 'doc')
        document = documents.get(unit['document_id'])
        if document is None:
            _error(f'{path}.document_id', 'does not resolve to a document')
        if unit['kind'] not in ('section', 'table', 'figure', 'region'):
            _error(f'{path}.kind', 'unsupported unit kind')
        _text(unit['selector'], f'{path}.selector')
        _sha(unit['original_sha256'], f'{path}.original_sha256')
        if unit['original_sha256'] != document['content_sha256']:
            _error(f'{path}.original_sha256', 'does not match original document')
        _citation(unit['citation'], f'{path}.citation')
        _citation_in_document(unit['citation'], document, path)
        if type(unit['mixed_content']) is not bool:
            _error(f'{path}.mixed_content', 'must be boolean')
        _search_projection(unit['search'], f'{path}.search', unit['mixed_content'])
        expected = unit_id(value['generation_sha256'], unit['document_id'],
                           unit['kind'], unit['selector'])
        _id(unit['id'], f'{path}.id', 'unit')
        if unit['id'] != expected or unit['id'] in units:
            _error(f'{path}.id', 'must be unique and bound to generation/document/selector')
        units[unit['id']] = unit
    for unit in units.values():
        parent = unit.get('parent_unit_id')
        if parent:
            if parent not in units or units[parent]['document_id'] != unit['document_id']:
                _error(f'unit {unit["id"]}.parent_unit_id', 'must resolve within its document')
            seen = {unit['id']}
            while parent:
                if parent in seen:
                    _error(f'unit {unit["id"]}', 'parent cycle')
                seen.add(parent)
                parent = units[parent].get('parent_unit_id')
    assertions = {}
    for index, assertion in enumerate(value['assertions']):
        path = f'evidence.assertions[{index}]'
        _record(assertion, path, ('id', 'digest', 'subject_id', 'statement', 'citation',
                                  'intent', 'applies_to_descendants', 'derivation',
                                  'provenance', 'support', 'alternatives'), ('selector',))
        subject = assertion['subject_id']
        if subject not in publications and subject not in documents and subject not in units:
            _error(f'{path}.subject_id', 'does not resolve in manifest or sidecar units')
        _text(assertion['statement'], f'{path}.statement')
        _citation(assertion['citation'], f'{path}.citation')
        if subject in documents:
            _citation_in_document(assertion['citation'], documents[subject], path)
        if subject in units:
            document = documents[units[subject]['document_id']]
            _citation_in_document(assertion['citation'], document, path)
        if 'selector' in assertion:
            _text(assertion['selector'], f'{path}.selector')
        if assertion['intent'] not in ('include', 'exclude'):
            _error(f'{path}.intent', 'must be include or exclude')
        if type(assertion['applies_to_descendants']) is not bool:
            _error(f'{path}.applies_to_descendants', 'must be boolean')
        if assertion['derivation'] not in ('explicit_structured', 'explicit_text',
                                           'title_hint', 'filename_hint', 'heuristic'):
            _error(f'{path}.derivation', 'unsupported derivation')
        if assertion['provenance'] not in ('native', 'ocr', 'catalog'):
            _error(f'{path}.provenance', 'unsupported provenance')
        if assertion['support'] not in ('source_supported', 'proposal'):
            _error(f'{path}.support', 'unsupported support status')
        if assertion['support'] == 'source_supported' and (
            assertion['derivation'] not in ('explicit_structured', 'explicit_text') or
            assertion['provenance'] != 'native'
        ):
            _error(f'{path}.support', 'automatic source support requires explicit native evidence')
        _array(assertion['alternatives'], f'{path}.alternatives', nonempty=True)
        seen_alternatives = set()
        for alt_index, alternative in enumerate(assertion['alternatives']):
            _alternative(alternative, f'{path}.alternatives[{alt_index}]', vocabulary)
            encoded = canonical_json(alternative)
            if encoded in seen_alternatives:
                _error(path, 'duplicate correlated alternative')
            seen_alternatives.add(encoded)
        _sha(assertion['digest'], f'{path}.digest')
        expected_digest = assertion_digest(assertion)
        expected_id = sidecar_id('ev', value['source_id'], subject, expected_digest)
        if assertion['digest'] != expected_digest or assertion['id'] != expected_id:
            _error(path, 'ID or digest does not match immutable assertion content')
        if assertion['id'] in assertions:
            _error(path, 'duplicate assertion ID')
        assertions[assertion['id']] = assertion
    _revision(value['revision'], 'evidence.revision', value)
    return value


def _citation_in_document(citation, document, path):
    if not any(c['kind'] == citation['kind'] and c['path'] == citation['path'] and
               c.get('page') == citation.get('page')
               for c in document['citations']):
        _error(f'{path}.citation', 'does not resolve to an original document citation')


def _search_projection(value, path, mixed):
    _record(value, path, ('state',), ('text_sha256',))
    if value['state'] not in ('whole', 'isolated', 'metadata_only'):
        _error(f'{path}.state', 'unsupported search projection')
    if mixed and value['state'] == 'whole':
        _error(path, 'mixed-content unit may not expose whole text to scoped search')
    if value['state'] == 'isolated':
        _sha(value.get('text_sha256'), f'{path}.text_sha256')
    elif 'text_sha256' in value:
        _error(f'{path}.text_sha256', 'only isolated text has a projection hash')


def review_event_is_stale(event, review):
    """Return whether an event is bound to an older interpretation snapshot."""
    current_evidence = {item['source_id']: item['revision']
                        for item in review['evidence_snapshots']}
    return (event['evidence_revision'] != current_evidence.get(event['source_id']) or
            event['vocabulary_revision'] != review['vocabulary_revision'] or
            event['policy_version'] != review['policy_version'])


def _evidence_snapshot(value, path):
    _record(value, path, ('contract', 'revision', 'source_id', 'source_sha256',
                          'manifest_sha256', 'content_sha256',
                          'generation_sha256', 'vocabulary_revision',
                          'units', 'assertions'))
    if value['contract'] != EVIDENCE_CONTRACT:
        _error(path, 'unsupported evidence snapshot contract')
    _v1_id(value['source_id'], f'{path}.source_id', 'src')
    _revision(value['revision'], f'{path}.revision', value)


def validate_review_overlay(value, evidence_sets, vocabulary, evidence_history=None):
    """Validate append-only review events against current and saved evidence."""
    validate_vocabulary(vocabulary)
    _record(value, 'review', ('contract', 'revision', 'vocabulary_revision',
                              'evidence_snapshots', 'policy_version', 'events'))
    if value['contract'] != REVIEW_CONTRACT or value['policy_version'] != POLICY_VERSION:
        _error('review', 'unsupported contract or policy')
    if value['vocabulary_revision'] != vocabulary['revision']:
        _error('review.vocabulary_revision', 'does not match vocabulary')
    if isinstance(evidence_sets, dict):
        evidence_sets = [evidence_sets]
    _array(evidence_sets, 'evidence_sets')
    for index, item in enumerate(evidence_sets):
        _evidence_snapshot(item, f'evidence_sets[{index}]')
    current = {item['source_id']: item for item in evidence_sets}
    if len(current) != len(evidence_sets):
        _error('evidence_sets', 'duplicate source identity')
    _array(value['evidence_snapshots'], 'review.evidence_snapshots')
    snapshot_sources = set()
    for index, item in enumerate(value['evidence_snapshots']):
        path = f'review.evidence_snapshots[{index}]'
        _record(item, path, ('source_id', 'revision'))
        _v1_id(item['source_id'], f'{path}.source_id', 'src')
        _sha(item['revision'], f'{path}.revision')
        if item['source_id'] in snapshot_sources:
            _error(path, 'duplicate source identity')
        snapshot_sources.add(item['source_id'])
        if (item['source_id'] not in current or
                current[item['source_id']]['revision'] != item['revision']):
            _error(path, 'does not match current evidence snapshot')
    if snapshot_sources != set(current):
        _error('review.evidence_snapshots', 'must list every current evidence source')
    _array(value['events'], 'review.events')
    history = evidence_history or {}
    for revision, item in history.items():
        _evidence_snapshot(item, f'evidence_history[{revision}]')
        if item['revision'] != revision:
            _error('evidence_history', 'history key does not match snapshot revision')
    configs = {item['id'] for item in vocabulary['configurations']}
    events = {}
    terminal_events = set()
    for index, event in enumerate(value['events']):
        path = f'review.events[{index}]'
        _record(event, path, ('id', 'action', 'proposal_id', 'subject_id', 'relation',
                              'target_configuration_ids', 'evidence_bindings',
                              'source_id', 'evidence_revision',
                              'vocabulary_revision', 'policy_version',
                              'reviewer', 'timestamp', 'reason'), ('prior_event_id',))
        if event['action'] not in ('propose', 'accept', 'reject', 'revoke', 'supersede'):
            _error(f'{path}.action', 'unsupported review action')
        if event['relation'] not in ('section_applies', 'part_fits', 'part_mentioned',
                                     'duplicate_content', 'same_edition'):
            _error(f'{path}.relation', 'unsupported relation type')
        _v1_id(event['source_id'], f'{path}.source_id', 'src')
        for field in ('evidence_revision', 'vocabulary_revision'):
            _sha(event[field], f'{path}.{field}')
        _text(event['policy_version'], f'{path}.policy_version')
        snapshot = current.get(event['source_id'])
        if snapshot is None or snapshot['revision'] != event['evidence_revision']:
            snapshot = history.get(event['evidence_revision'])
        if snapshot is None or snapshot['source_id'] != event['source_id']:
            _error(path, 'evidence snapshot for review event is unavailable')
        assertions = {item['id']: item for item in snapshot['assertions']}
        valid_subjects = {item['id'] for item in snapshot['units']} | {
            item['subject_id'] for item in snapshot['assertions']}
        if event['subject_id'] not in valid_subjects:
            _error(f'{path}.subject_id', 'does not resolve to evidence subject')
        _text(event['proposal_id'], f'{path}.proposal_id')
        _text(event['reviewer'], f'{path}.reviewer')
        timestamp = _timestamp(event['timestamp'], f'{path}.timestamp')
        _text(event['reason'], f'{path}.reason')
        _array(event['target_configuration_ids'], f'{path}.target_configuration_ids',
               nonempty=True)
        if len(set(event['target_configuration_ids'])) != len(event['target_configuration_ids']):
            _error(path, 'duplicate review target')
        for target in event['target_configuration_ids']:
            _id(target, f'{path}.target_configuration_ids', 'cfg')
            if event['vocabulary_revision'] == vocabulary['revision'] and target not in configs:
                _error(f'{path}.target_configuration_ids', 'unknown vehicle configuration')
        _array(event['evidence_bindings'], f'{path}.evidence_bindings', nonempty=True)
        for binding in event['evidence_bindings']:
            _record(binding, f'{path}.evidence_bindings', ('id', 'digest'))
            if (binding['id'] not in assertions or
                    assertions[binding['id']]['digest'] != binding['digest']):
                _error(f'{path}.evidence_bindings', 'unbound or changed evidence')
        prior_id = event.get('prior_event_id')
        if event['action'] == 'propose':
            if prior_id:
                _error(path, 'proposal may not refer to a prior decision')
        else:
            if prior_id not in events:
                _error(f'{path}.prior_event_id', 'must refer to an earlier event')
            prior = events[prior_id]
            if timestamp < _timestamp(prior['timestamp'], f'{path}.prior_event_id'):
                _error(path, 'decision predates its proposal or approval')
            expected_action = 'propose' if event['action'] in ('accept', 'reject') else 'accept'
            if prior['action'] != expected_action or prior['proposal_id'] != event['proposal_id']:
                _error(path, 'invalid review transition')
            if prior_id in terminal_events:
                _error(path, 'prior decision already has a terminal action')
            for field in ('subject_id', 'relation', 'target_configuration_ids',
                          'evidence_bindings', 'source_id', 'evidence_revision',
                          'vocabulary_revision', 'policy_version'):
                if event[field] != prior[field]:
                    _error(path, f'{field} must match the prior scoped decision')
            terminal_events.add(prior_id)
        expected = sidecar_id('review', digest({k: v for k, v in event.items() if k != 'id'}))
        if event['id'] != expected or event['id'] in events:
            _error(f'{path}.id', 'must be unique and bound to event content')
        events[event['id']] = event
    _revision(value['revision'], 'review.revision', value)
    return value


def validate_library(value, package_index=None):
    """Validate a many-package reference list without reading manual files."""
    _record(value, 'library', ('contract', 'revision', 'vocabulary_revision',
                               'review_revision', 'policy_version', 'packages'))
    if value['contract'] != LIBRARY_CONTRACT or value['policy_version'] != POLICY_VERSION:
        _error('library', 'unsupported contract or policy')
    for field in ('vocabulary_revision', 'review_revision'):
        _sha(value[field], f'library.{field}')
    _array(value['packages'], 'library.packages')
    occurrences = {}
    roots = set()
    for index, package in enumerate(value['packages']):
        path = f'library.packages[{index}]'
        _record(package, path, ('occurrence_id', 'root', 'source_id',
                                'manifest_sha256', 'content_sha256', 'status'),
                ('superseded_by',))
        try:
            if canonical_path(package['root']) != package['root']:
                _error(f'{path}.root', 'must use canonical relative spelling')
        except ContractError as exc:
            _error(f'{path}.root', str(exc))
        _v1_id(package['source_id'], f'{path}.source_id', 'src')
        for field in ('manifest_sha256', 'content_sha256'):
            _sha(package[field], f'{path}.{field}')
        if package['status'] not in ('active', 'superseded'):
            _error(f'{path}.status', 'unsupported status')
        if (package['status'] == 'superseded') != ('superseded_by' in package):
            _error(path, 'superseded status requires successor; active status forbids one')
        expected = sidecar_id('occ', package['source_id'], package['root'])
        if package['occurrence_id'] != expected or expected in occurrences:
            _error(f'{path}.occurrence_id', 'duplicate or mismatched occurrence')
        if package['root'] in roots:
            _error(f'{path}.root', 'duplicate package root')
        roots.add(package['root'])
        occurrences[expected] = package
        if package_index is not None:
            observed = package_index.get(package['root'])
            if observed is None or any(observed.get(key) != package[key] for key in (
                'source_id', 'manifest_sha256', 'content_sha256')):
                _error(path, 'package reference is absent or has changed')
    for package in occurrences.values():
        successor = package.get('superseded_by')
        if successor and (successor not in occurrences or
                          occurrences[successor]['status'] != 'active' or
                          successor == package['occurrence_id']):
            _error('library.packages', 'superseded_by must resolve to another active occurrence')
    _revision(value['revision'], 'library.revision', value)
    return value


def validate_scope(value, library, vocabulary, eligible_unit_ids=None,
                   evidence_ids=None, review_event_ids=None):
    """Validate one pre-search eligibility export and its scope fingerprint."""
    validate_library(library)
    validate_vocabulary(vocabulary)
    _record(value, 'scope', ('contract', 'fingerprint', 'library_revision',
                             'vocabulary_revision', 'review_revision', 'policy_version',
                             'selection', 'mode', 'include_reference', 'browse_all',
                             'eligible'))
    if value['contract'] != SCOPE_CONTRACT:
        _error('scope.contract', 'unsupported contract')
    for field in ('library_revision', 'vocabulary_revision', 'review_revision',
                  'policy_version'):
        if field == 'library_revision':
            expected = library['revision']
        elif field == 'vocabulary_revision':
            expected = vocabulary['revision']
        else:
            expected = library[field]
        if value[field] != expected:
            _error(f'scope.{field}', 'does not match library/vocabulary snapshot')
    if value['mode'] not in MODES:
        _error('scope.mode', 'unsupported matching mode')
    for field in ('include_reference', 'browse_all'):
        if type(value[field]) is not bool:
            _error(f'scope.{field}', 'must be boolean')
    selection = value['selection']
    _record(selection, 'scope.selection', (), ('make_id', 'model_id', 'model_year',
                                               'engine_id', 'qualifiers'))
    makes = {item['id'] for item in vocabulary['makes']}
    models = {item['id']: item for item in vocabulary['models']}
    engines = {item['id'] for item in vocabulary['engines']}
    for field, collection in (('make_id', makes), ('model_id', models),
                               ('engine_id', engines)):
        if field in selection and selection[field] not in collection:
            _error(f'scope.selection.{field}', 'unknown canonical ID')
    for field, prerequisite in (('model_id', 'make_id'), ('model_year', 'model_id'),
                                 ('engine_id', 'model_year')):
        if field in selection and prerequisite not in selection:
            _error('scope.selection', f'{field} requires {prerequisite}')
    if 'model_id' in selection and models[selection['model_id']]['make_id'] != selection['make_id']:
        _error('scope.selection.model_id', 'belongs to another make')
    if 'model_year' in selection:
        _year(selection['model_year'], 'scope.selection.model_year')
    if 'qualifiers' in selection:
        _qualifier_values(selection['qualifiers'], 'scope.selection.qualifiers')
    if value['browse_all'] and selection:
        _error('scope.browse_all', 'browse-all requires an empty vehicle selection')
    if value['fingerprint'] != scope_fingerprint(value):
        _error('scope.fingerprint', 'does not match selected scope and revisions')
    _array(value['eligible'], 'scope.eligible')
    seen = set()
    for index, item in enumerate(value['eligible']):
        path = f'scope.eligible[{index}]'
        _record(item, path, ('unit_id', 'state', 'reason_codes', 'evidence_ids',
                             'review_event_ids'))
        if not isinstance(item['unit_id'], str) or not re.fullmatch(
            r'(pub|doc|unit)_[0-9a-f]{32}', item['unit_id']
        ):
            _error(f'{path}.unit_id', 'must be a publication, document or sidecar unit ID')
        if item['unit_id'] in seen or (eligible_unit_ids is not None and
                                       item['unit_id'] not in eligible_unit_ids):
            _error(f'{path}.unit_id', 'duplicate or dangling eligible unit')
        seen.add(item['unit_id'])
        if item['state'] not in ('confirmed', 'possible', 'reference'):
            _error(f'{path}.state', 'unsupported eligibility state')
        if item['state'] == 'possible' and value['mode'] == 'confirmed':
            _error(path, 'possible unit is not eligible in confirmed mode')
        if item['state'] == 'reference' and not value['include_reference']:
            _error(path, 'reference unit requires explicit opt-in')
        for field in ('reason_codes', 'evidence_ids', 'review_event_ids'):
            _array(item[field], f'{path}.{field}')
        if (not item['reason_codes'] or
                any(code not in REASON_CODES for code in item['reason_codes'])):
            _error(f'{path}.reason_codes', 'must contain known reason codes')
        for evidence_id in item['evidence_ids']:
            _id(evidence_id, f'{path}.evidence_ids', 'ev')
            if evidence_ids is not None and evidence_id not in evidence_ids:
                _error(f'{path}.evidence_ids', 'dangling evidence ID')
        for event_id in item['review_event_ids']:
            _id(event_id, f'{path}.review_event_ids', 'review')
            if review_event_ids is not None and event_id not in review_event_ids:
                _error(f'{path}.review_event_ids', 'dangling review event ID')
    if not selection and not value['browse_all'] and value['eligible']:
        _error('scope.eligible', 'empty non-browse selection may not search the library')
    if all(field in selection for field in ('make_id', 'model_id', 'model_year', 'engine_id')):
        known = any(config['make_id'] == selection['make_id'] and
                    config['model_id'] == selection['model_id'] and
                    config['model_year'] == selection['model_year'] and
                    config['engine_id'] == selection['engine_id']
                    for config in vocabulary['configurations'])
        if not known and value['eligible']:
            _error('scope.eligible', 'unknown vehicle tuple must have empty eligibility')
    return value
