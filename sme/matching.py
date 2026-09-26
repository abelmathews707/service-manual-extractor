"""Deterministic, pre-search vehicle applicability decisions for one source unit."""

from .applicability_contracts import (
    MODES,
    review_event_is_stale,
    validate_evidence,
    validate_review_overlay,
    validate_vocabulary,
)
from .contract import ContractError

_FIELDS = ('make', 'model', 'year', 'engine')
_SELECTION = ('make_id', 'model_id', 'model_year', 'engine_id')
_MISSING = {'make': 'missing_make', 'model': 'missing_model',
            'year': 'missing_year', 'engine': 'missing_engine'}


def _result(state, reason, evidence=(), events=(), missing=(), conflicts=(), mode='confirmed'):
    return {'state': state, 'reason_codes': [reason],
            'search_eligible': state in ('confirmed', 'reference') or
            (state == 'possible' and mode == 'include_possible'),
            'evidence_ids': sorted(set(evidence)),
            'review_event_ids': sorted(set(events)),
            'missing_qualifiers': sorted(set(missing)),
            'conflicts': sorted(set(conflicts))}


def compile_evidence(evidence, manifest):
    """Index one validated sidecar once for many scope/unit decisions."""
    assertions = {}
    for item in evidence['assertions']:
        assertions.setdefault(item['subject_id'], []).append(item)
    return {'units': {item['id']: item for item in evidence['units']},
            'documents': {doc['id']: (doc, pub) for pub in manifest['publications']
                          for doc in pub['documents']},
            'assertions': assertions}


def _ancestry(context, unit_id):
    units = context['units']
    documents = context['documents']
    if unit_id not in units:
        raise ContractError('unit does not exist in evidence sidecar')
    ancestors = [unit_id]
    parent = units[unit_id].get('parent_unit_id')
    while parent:
        ancestors.append(parent)
        parent = units[parent].get('parent_unit_id')
    doc, publication = documents[units[unit_id]['document_id']]
    ancestors.extend((doc['id'], publication['id']))
    return units[unit_id], publication, ancestors


def _predicate(predicate, selected, field):
    state = predicate['state']
    if state == 'not_applicable':
        return 'match'
    if state == 'unknown':
        return 'unknown'
    if selected is None:
        return 'missing_selection'
    if state == 'all_in_scope':
        return 'match'
    if state == 'range':
        return 'match' if predicate['start'] <= selected <= predicate['end'] else 'different'
    return 'match' if predicate['value'] == selected else 'different'


def _alternative(alternative, selection):
    unknown, missing_selection, missing_qualifiers = [], [], []
    for field, key in zip(_FIELDS, _SELECTION):
        outcome = _predicate(alternative[field], selection.get(key), field)
        if outcome == 'different':
            return 'different', [], [], []
        if outcome == 'unknown':
            unknown.append(field)
        if outcome == 'missing_selection':
            missing_selection.append(field)
    selected_qualifiers = selection.get('qualifiers', {})
    for name, predicate in alternative['qualifiers'].items():
        outcome = _predicate(predicate, selected_qualifiers.get(name), name)
        if outcome == 'different':
            return 'different', [], [], []
        if outcome in ('unknown', 'missing_selection'):
            missing_qualifiers.append(name)
    return 'match', unknown, missing_selection, missing_qualifiers


def _assertion_match(assertion, selection):
    matches = [_alternative(alt, selection) for alt in assertion['alternatives']]
    viable = [item for item in matches if item[0] == 'match']
    if not viable:
        return None
    return min(viable, key=lambda item: (len(item[1]) + len(item[2]) + len(item[3]),
                                         item[1], item[2], item[3]))


def _review_state(review, ancestry, config_id):
    if review is None or config_id is None:
        return [], [], []
    events = review['events']
    terminal = {event['prior_event_id'] for event in events if 'prior_event_id' in event}
    accepted, pending, stale = [], [], []
    for event in events:
        if (event['subject_id'] not in ancestry or
                config_id not in event['target_configuration_ids'] or
                event['relation'] != 'section_applies' or event['id'] in terminal):
            continue
        if event['action'] == 'accept':
            (stale if review_event_is_stale(event, review) else accepted).append(event['id'])
        elif event['action'] == 'propose' and not review_event_is_stale(event, review):
            pending.append(event['id'])
    return accepted, pending, stale


def _match_unit(evidence, manifest, vocabulary, unit_id, selection, *,
                mode='confirmed', include_reference=False, review=None,
                evidence_history=None, validate=True, compiled=None):
    """Return the effective decision and trace, without text-similarity promotion.

    Each call evaluates inherited source restrictions before review approvals.
    A5 intentionally returns one unit at a time; A6 will assemble many packages
    and resolve pre-search allowlists from these decisions.
    """
    if mode not in MODES:
        raise ContractError('unsupported matching mode')
    if not isinstance(selection, dict) or any(
            key not in ('make_id', 'model_id', 'model_year', 'engine_id', 'qualifiers')
            for key in selection):
        raise ContractError('selection must use canonical vehicle fields')
    for field, prerequisite in (('model_id', 'make_id'), ('model_year', 'model_id'),
                                 ('engine_id', 'model_year')):
        if field in selection and prerequisite not in selection:
            raise ContractError(f'{field} requires {prerequisite}')
    if evidence is None:
        return _result('unmapped', 'unmapped_package', mode=mode)
    if validate:
        validate_vocabulary(vocabulary)
        validate_evidence(evidence, manifest, vocabulary)
        if review is not None:
            validate_review_overlay(review, evidence, vocabulary, evidence_history)
    context = compiled or compile_evidence(evidence, manifest)
    unit, publication, ancestry = _ancestry(context, unit_id)
    if not selection:
        return _result('excluded', 'no_eligible_units', mode=mode)
    known_configs = {item['id']: item for item in vocabulary['configurations']}
    config_id = None
    if all(key in selection for key in _SELECTION):
        config_id = next((identifier for identifier, config in known_configs.items()
                          if (config['make_id'], config['model_id'], config['model_year'],
                              config['engine_id']) == tuple(selection[key] for key in _SELECTION)),
                         None)
        if config_id is None:
            return _result('excluded', 'no_eligible_units', mode=mode)
    if publication['kind'] == 'reference':
        if include_reference:
            return _result('reference', 'generic_reference', mode=mode)
        return _result('excluded', 'generic_reference', mode=mode)
    if unit['search']['state'] == 'metadata_only' and unit['mixed_content']:
        return _result('excluded', 'mixed_content', mode=mode)
    applicable = [item for subject in ancestry
                  for item in context['assertions'].get(subject, [])
                  if subject == unit_id or item['applies_to_descendants']]
    by_subject = {}
    for assertion in applicable:
        by_subject.setdefault(assertion['subject_id'], []).append(assertion)
    accepted, pending, stale = _review_state(review, ancestry, config_id)
    other_pending = []
    if review is not None and config_id is not None:
        terminal = {event['prior_event_id'] for event in review['events']
                    if 'prior_event_id' in event}
        other_pending = [event['id'] for event in review['events']
                         if event['action'] == 'propose' and event['id'] not in terminal
                         and event['subject_id'] in ancestry
                         and config_id in event['target_configuration_ids']
                         and not review_event_is_stale(event, review)]
    positive, proposals, contradictions = [], [], []
    source_missing, proposal_missing = [], []
    source_qualifiers, proposal_qualifiers = [], []
    unknown_make = False
    for subject in ancestry:
        group = by_subject.get(subject, [])
        includes = [item for item in group if item['intent'] == 'include']
        excludes = [item for item in group if item['intent'] == 'exclude']
        for item in excludes:
            if item['support'] == 'source_supported' and _assertion_match(item, selection):
                reason = 'conflicting_child' if subject == unit_id or subject in ancestry[:-2] \
                    else 'excluded_by_source'
                return _result('excluded', reason, [item['id']], accepted,
                               conflicts=[item['id']], mode=mode)
        supported = [item for item in includes if item['support'] == 'source_supported']
        group_matches = [(item, _assertion_match(item, selection)) for item in includes]
        matches = [(item, value) for item, value in group_matches if value is not None]
        if supported and not any(value is not None for item, value in group_matches
                                 if item['support'] == 'source_supported'):
            contradictions += [item['id'] for item in supported]
            if subject in ancestry[:-2] and len(ancestry) > 3:
                return _result('excluded', 'conflicting_child', conflicts=contradictions,
                               mode=mode)
        if matches:
            best = min(matches, key=lambda pair: (pair[0]['support'] != 'source_supported',
                                                 len(pair[1][1]) + len(pair[1][2]) +
                                                 len(pair[1][3])))
            item, value = best
            (positive if item['support'] == 'source_supported' else proposals).append(item['id'])
            (source_missing if item['support'] == 'source_supported'
             else proposal_missing).extend(value[1])
            (source_qualifiers if item['support'] == 'source_supported'
             else proposal_qualifiers).extend(value[3])
            unknown_make |= 'make' in value[1]
        elif includes and not supported:
            # A title or OCR hint for another known make is not a Ford hit.
            if all(_assertion_match(item, selection) is None for item in includes):
                contradictions += [item['id'] for item in includes]
    if not accepted and stale:
        return _result('excluded', 'stale_review', positive + proposals, stale,
                       mode=mode)
    if not accepted and (pending or other_pending) and not positive and not proposals:
        return _result('excluded', 'pending_cross_make',
                       events=pending + other_pending, mode=mode)
    if not accepted and contradictions:
        return _result('excluded', 'excluded_by_source', conflicts=contradictions,
                       mode=mode)
    if accepted and contradictions and unit_id in by_subject:
        accepted_subjects = {event['subject_id'] for event in review['events']
                             if event['id'] in accepted}
        if unit_id not in accepted_subjects:
            return _result('excluded', 'conflicting_child', conflicts=contradictions,
                           events=accepted, mode=mode)
    if (unknown_make and not positive and not accepted) or (
            not positive and not proposals and not accepted and not pending):
        return _result('unmapped', 'unknown_identity', mode=mode)
    missing = source_missing if positive else proposal_missing
    missing_qualifiers = source_qualifiers if positive else proposal_qualifiers
    if accepted and (missing_qualifiers or missing) and by_subject.get(unit_id):
        reason = ('missing_qualifier' if missing_qualifiers else
                  next((_MISSING[field] for field in _FIELDS if field in missing),
                       'missing_qualifier'))
        return _result('possible' if mode == 'include_possible' else 'excluded',
                       reason, positive + proposals, accepted, missing_qualifiers,
                       mode=mode)
    if accepted:
        return _result('confirmed', 'reviewed', positive + proposals, accepted,
                       missing_qualifiers, mode=mode)
    if pending and not positive and not proposals:
        return _result('excluded', 'pending_cross_make', events=pending, mode=mode)
    if not positive and not proposals:
        return _result('unmapped', 'unknown_identity', mode=mode)
    if not positive:
        reason = next((_MISSING[field] for field in _FIELDS if field in missing),
                      'missing_qualifier')
        state = 'possible' if mode == 'include_possible' else 'excluded'
        return _result(state, reason, proposals, pending, missing_qualifiers, mode=mode)
    if len(selection) < 4 or not all(key in selection for key in _SELECTION):
        return _result('possible' if mode == 'include_possible' else 'excluded',
                       'incomplete_selection', positive + proposals, mode=mode)
    if missing_qualifiers:
        return _result('possible' if mode == 'include_possible' else 'excluded',
                       'missing_qualifier', positive + proposals, missing=missing_qualifiers,
                       mode=mode)
    if missing:
        reason = next((_MISSING[field] for field in _FIELDS if field in missing),
                      'missing_qualifier')
        return _result('possible' if mode == 'include_possible' else 'excluded',
                       reason, positive + proposals, mode=mode)
    return _result('confirmed', 'explicit_source', positive + proposals, mode=mode)


def match_unit(evidence, manifest, vocabulary, unit_id, selection, *,
               mode='confirmed', include_reference=False, review=None,
               evidence_history=None, validate=True, compiled=None):
    """Evaluate one unit and mark metadata-only units ineligible for text search."""
    result = _match_unit(evidence, manifest, vocabulary, unit_id, selection,
                         mode=mode, include_reference=include_reference,
                         review=review, evidence_history=evidence_history,
                         validate=validate, compiled=compiled)
    if evidence is not None:
        unit = (compiled['units'][unit_id] if compiled else
                next(item for item in evidence['units'] if item['id'] == unit_id))
        if unit['search']['state'] == 'metadata_only':
            result['search_eligible'] = False
    return result
