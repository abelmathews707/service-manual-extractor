"""Typed source records and independent content-quality decisions (B1).

Shape validation has no optional dependency. Source binding, diagnostic graph
completeness and review transitions are checked separately from JSON Schema.
None of these functions extracts or approves manual content automatically.
"""

import copy
import json
import math
import os
import re
import tempfile
from functools import lru_cache

from .applicability_contracts import (
    POLICY_VERSION,
    _citation,
    _timestamp,
    digest,
    validate_vocabulary,
)
from .contract import ContractError

RECORD_CONTRACT = 'structured-evidence/v1'
QUALITY_CONTRACT = 'structured-quality-review/v1'
QUALITY_POLICY = 'structured-quality-policy/v1'


@lru_cache(maxsize=2)
def _schema(name):
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schemas', name)
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _shape(value, rule, definitions, path='$'):
    """Validate the deliberately small schema vocabulary used by these contracts."""
    if '$ref' in rule:
        reference = rule['$ref']
        if not reference.startswith('#/$defs/'):
            raise ContractError('only bundled local schema references are supported')
        return _shape(value, definitions[reference.split('/')[-1]], definitions, path)
    for keyword in ('allOf', 'oneOf'):
        if keyword not in rule:
            continue
        successes = 0
        for choice in rule[keyword]:
            try:
                _shape(value, choice, definitions, path)
                successes += 1
            except ContractError:
                if keyword == 'allOf':
                    raise
        if keyword == 'oneOf' and successes != 1:
            raise ContractError(f'{path}: must match one typed shape')
    kind = rule.get('type')
    valid = {
        'object': isinstance(value, dict), 'array': isinstance(value, list),
        'string': isinstance(value, str), 'boolean': type(value) is bool,
        'integer': type(value) is int,
        'number': type(value) in (int, float) and math.isfinite(value),
    }
    if kind and not valid.get(kind, False):
        raise ContractError(f'{path}: expected {kind}')
    if 'const' in rule and value != rule['const']:
        raise ContractError(f'{path}: unsupported constant')
    if 'enum' in rule and value not in rule['enum']:
        raise ContractError(f'{path}: unsupported value')
    if isinstance(value, dict):
        if set(rule.get('required', ())) - set(value):
            raise ContractError(f'{path}: missing required fields')
        properties = rule.get('properties', {})
        if rule.get('additionalProperties') is False and set(value) - set(properties):
            raise ContractError(f'{path}: unexpected fields')
        for key, child in properties.items():
            if key in value:
                _shape(value[key], child, definitions, f'{path}.{key}')
    if isinstance(value, list):
        if len(value) < rule.get('minItems', 0) or len(value) > rule.get('maxItems', 100000):
            raise ContractError(f'{path}: invalid array length')
        if rule.get('uniqueItems') and len({digest(item) for item in value}) != len(value):
            raise ContractError(f'{path}: duplicate array items')
        if 'items' in rule:
            for index, item in enumerate(value):
                _shape(item, rule['items'], definitions, f'{path}[{index}]')
    if isinstance(value, str):
        if 'minLength' in rule and (len(value) < rule['minLength'] or not value.strip()):
            raise ContractError(f'{path}: empty text')
        if 'pattern' in rule and re.fullmatch(rule['pattern'], value) is None:
            raise ContractError(f'{path}: invalid spelling')
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise ContractError(f'{path}: non-finite number')
        if value < rule.get('minimum', -math.inf) or value > rule.get('maximum', math.inf):
            raise ContractError(f'{path}: number outside bounds')


def record_identity(record):
    return 'record_' + digest([record['binding']['source_id'],
                               record['binding']['unit_id'], record['type'],
                               record['locator']])[:32]


def record_digest(record):
    return digest({key: value for key, value in record.items() if key != 'record_sha256'})


def seal_records(records):
    """Assign identities/hashes only; caller must still validate and review."""
    value = {'contract': RECORD_CONTRACT, 'records': copy.deepcopy(records)}
    for record in value['records']:
        record['id'] = record_identity(record)
        record['record_sha256'] = record_digest(record)
    value['revision'] = digest(value)
    return value


def _references(record):
    payload = record['payload']
    links = [(identifier, None) for identifier in record['context_record_ids']]
    for field, kind in (('tool_ids', 'tool'), ('next_record_ids', 'procedure_step')):
        links.extend((identifier, kind) for identifier in payload.get(field, ()))
    for field in ('from_record_id', 'to_record_id', 'target_record_id'):
        if field in payload:
            links.append((payload[field], 'diagnostic_node'
                          if record['type'] == 'diagnostic_edge' else None))
    return links


def validate_records(value, vocabulary, evidence_sets, *, source_texts=None):
    """Require frozen source units, exact citations and valid vehicle references.

    ``source_texts`` maps unit IDs to normalized source text. When supplied,
    original quotations must resolve uniquely; HTML/PDF spatial selectors need
    original visual review as well. This check is not a quality approval.
    """
    schema = _schema('structured-evidence-v1.schema.json')
    _shape(value, schema, schema['$defs'])
    if value['revision'] != digest({k: v for k, v in value.items() if k != 'revision'}):
        raise ContractError('structured record revision changed')
    validate_vocabulary(vocabulary)
    configs = {item['id'] for item in vocabulary['configurations']}
    sources = {item['source_id']: item for item in evidence_sets}
    if len(sources) != len(evidence_sets):
        raise ContractError('duplicate structured evidence source')
    for source in sources.values():
        if (source['revision'] != digest({k: v for k, v in source.items() if k != 'revision'}) or
                source['vocabulary_revision'] != vocabulary['revision'] or
                len({unit['id'] for unit in source['units']}) != len(source['units'])):
            raise ContractError('structured evidence snapshot is changed, stale or duplicated')
    units = {source_id: {unit['id']: unit for unit in source['units']}
             for source_id, source in sources.items()}
    records = {}
    for record in value['records']:
        if record['id'] in records or record['id'] != record_identity(record):
            raise ContractError('duplicate or changed record identity')
        if record['record_sha256'] != record_digest(record):
            raise ContractError('record content hash changed')
        records[record['id']] = record
        binding = record['binding']
        source = sources.get(binding['source_id'])
        unit = units.get(binding['source_id'], {}).get(binding['unit_id'])
        if source is None or unit is None:
            raise ContractError('record does not resolve to a known source unit')
        for field in ('source_sha256', 'generation_sha256', 'content_sha256'):
            if binding[field] != source[field]:
                raise ContractError(f'record source binding changed: {field}')
        if binding['evidence_revision'] != source['revision']:
            raise ContractError('record evidence revision changed')
        for field in ('document_id', 'original_sha256', 'citation'):
            if binding[field] != unit[field]:
                raise ContractError(f'record unit binding changed: {field}')
        _citation(binding['citation'], 'structured.binding.citation')
        applicability = record['applicability']
        if (applicability['vocabulary_revision'] != vocabulary['revision'] or
                applicability['policy_version'] != POLICY_VERSION or
                not set(applicability['configuration_ids']) <= configs):
            raise ContractError('record vehicle vocabulary/policy is absent or stale')
        state = record['completeness']
        if (state['state'] == 'complete') != (not state['missing']):
            raise ContractError('completeness state disagrees with missing context')
        locator = record['locator']
        if locator['kind'] == 'html' and binding['citation']['kind'] != 'path':
            raise ContractError('HTML locator cannot identify a PDF page')
        if locator['kind'] == 'pdf_region':
            x0, y0, x1, y1 = locator['bbox']
            if (x0 >= x1 or y0 >= y1 or binding['citation']['kind'] != 'page' or
                    locator['page'] != binding['citation']['page']):
                raise ContractError('invalid page-region locator')
        if locator['kind'] == 'text_quote' and locator['quote'] != record['original_text']:
            raise ContractError('locator does not bind the exact original wording')
        if source_texts is not None:
            text = source_texts.get(binding['unit_id'])
            if text is None or record['original_text'] not in text:
                raise ContractError('original wording is absent from the bound unit')
            if locator['kind'] == 'text_quote':
                quoted = locator['prefix'] + locator['quote'] + locator['suffix']
                if text.count(quoted) != 1:
                    raise ContractError('quote context is absent or ambiguous')
        payload = record['payload']
        if record['type'] == 'specification':
            for item in payload['values']:
                normalized = item.get('normalized')
                if normalized and normalized['minimum'] > normalized['maximum']:
                    raise ContractError('specification range is reversed')
                if item['condition'] not in record['conditions']:
                    raise ContractError('specification operating condition was detached')
        if record['type'] == 'part_reference':
            relation = payload['relationship']
            if relation == 'supersedes' and 'target_identifier_original' not in payload:
                raise ContractError('supersession requires its original target')
            fit = payload.get('fits_configuration_ids', [])
            if ((relation == 'fits' and not fit) or
                    (relation != 'fits' and 'fits_configuration_ids' in payload) or
                    (relation != 'supersedes' and 'target_identifier_original' in payload) or
                    not set(fit) <= set(applicability['configuration_ids'])):
                raise ContractError('part mention/fitment/supersession were conflated')
    for record in records.values():
        for identifier, kind in _references(record):
            target = records.get(identifier)
            if target is None or (kind and target['type'] != kind):
                raise ContractError('structured relationship has an absent/wrong-type target')
            if not set(record['applicability']['configuration_ids']) <= set(
                    target['applicability']['configuration_ids']):
                raise ContractError('required context does not cover every declared vehicle')
        if record['type'] == 'diagnostic_node' and record['completeness']['state'] == 'complete':
            node = record['payload']
            edges = [item for item in records.values() if item['type'] == 'diagnostic_edge'
                     and item['payload']['from_record_id'] == record['id']]
            actual = [edge['payload']['label'] for edge in edges]
            expected = node['required_branch_labels']
            if set(actual) != set(expected) or len(actual) != len(set(actual)):
                raise ContractError('complete diagnostic node lost or duplicated a branch')
            if node['node_kind'] == 'decision' and len(expected) < 2:
                raise ContractError('complete decision requires its alternative branches')
            if node['node_kind'] == 'test' and not node['expected_results']:
                raise ContractError('complete diagnostic test requires expected readings')
            if node['node_kind'] == 'outcome' and expected:
                raise ContractError('terminal diagnostic outcome cannot hide outgoing branches')
            if any(edge['completeness']['state'] != 'complete' for edge in edges):
                raise ContractError('complete node depends on an incomplete branch')
    return value


def dependency_bindings(record_id, records):
    """Bind all reachable context, tools, steps and diagnostic edges by hash."""
    index = {item['id']: item for item in records}
    seen = set()
    pending = [record_id]
    while pending:
        identifier = pending.pop()
        if identifier in seen:
            continue
        if identifier not in index:
            raise ContractError('quality dependency is absent')
        seen.add(identifier)
        pending.extend(target for target, _ in _references(index[identifier]))
        pending.extend(item['id'] for item in records if item['type'] == 'diagnostic_edge'
                       and item['payload']['from_record_id'] == identifier)
    return [{'record_id': identifier, 'record_sha256': index[identifier]['record_sha256']}
            for identifier in sorted(seen)]


def dependency_digest(record_id, records):
    return digest(dependency_bindings(record_id, records))


def new_quality_overlay():
    value = {'contract': QUALITY_CONTRACT, 'policy_version': QUALITY_POLICY, 'events': []}
    value['revision'] = digest(value)
    return value


def _quality_id(event):
    return 'quality_' + digest({key: item for key, item in event.items() if key != 'id'})[:32]


def validate_quality_overlay(value, record_history):
    """Keep historical reviewed records so changed evidence can become stale."""
    schema = _schema('structured-quality-review-v1.schema.json')
    _shape(value, schema, schema['$defs'])
    if value['revision'] != digest({k: v for k, v in value.items() if k != 'revision'}):
        raise ContractError('quality overlay revision changed')
    historic = {(item['id'], item['record_sha256']): item for item in record_history}
    events = {}
    heads = {}
    for event in value['events']:
        if event['id'] in events or event['id'] != _quality_id(event):
            raise ContractError('duplicate or changed quality event')
        _timestamp(event['timestamp'], 'quality.timestamp')
        record = historic.get((event['record_id'], event['record_sha256']))
        if record is None or record_digest(record) != record['record_sha256']:
            raise ContractError('quality decision has no retained bound record')
        bound = []
        for item in event['dependency_bindings']:
            target = historic.get((item['record_id'], item['record_sha256']))
            if target is None or record_digest(target) != item['record_sha256']:
                raise ContractError('quality dependency has no retained valid record')
            bound.append(target)
        if (event['dependency_bindings'] != dependency_bindings(event['record_id'], bound) or
                event['dependencies_sha256'] != digest(event['dependency_bindings'])):
            raise ContractError('quality context bindings are incomplete or changed')
        key = (event['record_id'], event['intended_use'], event['purpose'])
        prior = events.get(event.get('prior_event_id'))
        if event['action'] == 'propose':
            if 'prior_event_id' in event:
                raise ContractError('quality proposal cannot claim a prior transition')
        else:
            if prior is None or heads.get(key) != prior['id']:
                raise ContractError('quality transition must follow the current decision')
            for field in ('record_id', 'record_sha256', 'dependencies_sha256',
                          'dependency_bindings', 'intended_use', 'purpose'):
                if prior[field] != event[field]:
                    raise ContractError('quality transition broadened its record/use scope')
            allowed = {'approve': {'propose'}, 'reject': {'propose'}, 'revoke': {'approve'}}
            if prior['action'] not in allowed[event['action']]:
                raise ContractError('invalid quality review transition')
            if (_timestamp(event['timestamp'], 'timestamp') <
                    _timestamp(prior['timestamp'], 'prior')):
                raise ContractError('quality history cannot move backward in time')
        if event['action'] == 'approve':
            checks = event['checks']
            if not checks['original_compared'] or not checks['source_resolves']:
                raise ContractError('quality approval needs original comparison/source resolution')
            if event['intended_use'] != 'readable_reference' and (
                    record['completeness']['state'] != 'complete' or not all(checks.values())):
                raise ContractError('instruction approval requires complete checked context')
            if event['intended_use'] != 'readable_reference' and any(
                    item['completeness']['state'] != 'complete' for item in bound):
                raise ContractError('quality approval depends on incomplete context')
            if event['purpose'] == 'production' and event['reviewer']['kind'] != 'human':
                raise ContractError('agent engineering review is not production human approval')
        events[event['id']] = event
        heads[key] = event['id']
    return value


def append_quality_event(overlay, records, *, record_id, action, intended_use,
                         purpose, reviewer, timestamp, reason, checks, prior_event_id=None,
                         history=()):
    """Return an append-only validated decision; never mutate the caller's log."""
    record = next((item for item in records if item['id'] == record_id), None)
    if record is None:
        raise ContractError('quality target record is absent')
    candidate = copy.deepcopy(overlay)
    event = {'record_id': record_id, 'record_sha256': record['record_sha256'],
             'dependencies_sha256': dependency_digest(record_id, records),
             'dependency_bindings': dependency_bindings(record_id, records),
             'action': action, 'intended_use': intended_use, 'purpose': purpose,
             'reviewer': reviewer, 'timestamp': timestamp, 'reason': reason, 'checks': checks}
    if prior_event_id is not None:
        event['prior_event_id'] = prior_event_id
    event['id'] = _quality_id(event)
    candidate['events'].append(event)
    candidate['revision'] = digest({k: v for k, v in candidate.items() if k != 'revision'})
    validate_quality_overlay(candidate, list(history) + list(records))
    return candidate


def quality_state(record_id, records, overlay, *, intended_use, purpose='production',
                  history=()):
    """Resolve quality only; this function never grants vehicle applicability."""
    validate_quality_overlay(overlay, list(history) + list(records))
    record = next((item for item in records if item['id'] == record_id), None)
    if record is None:
        raise ContractError('quality target record is absent')
    found = [event for event in overlay['events'] if event['record_id'] == record_id
             and event['intended_use'] == intended_use and event['purpose'] == purpose]
    if not found:
        return {'state': 'unreviewed', 'approved': False}
    event = found[-1]
    if (event['record_sha256'] != record['record_sha256'] or
            event['dependencies_sha256'] != dependency_digest(record_id, records)):
        return {'state': 'stale', 'approved': False}
    return {'state': event['action'], 'approved': event['action'] == 'approve',
            'event_id': event['id'], 'purpose': purpose, 'intended_use': intended_use,
            'record_id': record['id'], 'record_sha256': record['record_sha256']}


def save_quality_overlay(path, overlay, record_history):
    """Atomically preserve quality history, independently of applicability files."""
    validate_quality_overlay(overlay, record_history)
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    if not os.path.isdir(parent) or os.path.islink(parent) or os.path.islink(target):
        raise ContractError('quality destination needs a regular parent and no symlink')
    if os.path.exists(target):
        with open(target, encoding='utf-8') as stream:
            previous = json.load(stream)
        validate_quality_overlay(previous, record_history)
        if overlay['events'][:len(previous['events'])] != previous['events']:
            raise ContractError('quality history cannot be edited or removed')
    handle, stage = tempfile.mkstemp(prefix='.quality-', suffix='.json', dir=parent)
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


def diagnostic_admission(record, configuration_id, applicability_decision, quality,
                         *, purpose='production'):
    """Two gates on a caller-validated, configuration-bound scope decision.

    Engineering acceptance must opt in explicitly; it cannot stand in for
    human production approval. Raw unbound matcher results are insufficient.
    """
    if purpose not in ('production', 'engineering'):
        raise ContractError('unsupported diagnostic review purpose')
    return (applicability_decision.get('state') == 'confirmed'
            and applicability_decision.get('unit_id') == record['binding']['unit_id']
            and applicability_decision.get('configuration_id') == configuration_id
            and configuration_id in record['applicability']['configuration_ids']
            and record['completeness']['state'] == 'complete'
            and quality.get('approved') is True
            and quality.get('record_id') == record['id']
            and quality.get('record_sha256') == record['record_sha256']
            and quality.get('purpose') == purpose
            and quality.get('intended_use') == 'diagnostic_instruction')
