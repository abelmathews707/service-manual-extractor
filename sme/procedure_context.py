"""Resolve one reviewed continuation without inheriting its caller's eligibility.

The routing index contains IDs only. Callers provide current scope decisions,
validated record loading and quality state resolved against current dependencies.
This primitive never searches for substitutes when a target cannot be admitted.
"""

from .contract import ContractError
from .structured_contracts import record_digest, record_identity


def resolve_continuation(record_id, configuration_id, record_units, *, scope_for,
                         load_unit, quality_for, intended_use='structured_reference',
                         purpose='engineering'):
    """Check target scope before loading text, then its independent current quality.

    This is a single hop. Callers must repeat it for every expansion and bound
    traversal/cycles. ``load_unit`` must validate original hashes, library identity,
    vocabulary and source quotations before returning records. ``quality_for``
    must use the current dependency closure, not a cached approval boolean.
    """
    if (intended_use not in ('readable_reference', 'structured_reference',
                             'diagnostic_instruction') or
            purpose not in ('engineering', 'production')):
        raise ContractError('unsupported continuation review use/purpose')
    unit_id = record_units.get(record_id)
    if unit_id is None:
        return {'state': 'unresolved', 'reason': 'Target record has no reviewed source locator'}
    decision = scope_for(unit_id, configuration_id)
    if (decision.get('state') != 'confirmed' or decision.get('unit_id') != unit_id or
            decision.get('configuration_id') != configuration_id):
        return {'state': 'withheld', 'reason': 'Target vehicle applicability is not confirmed'}
    records = load_unit(unit_id)
    matches = [item for item in records if item['id'] == record_id]
    if len(matches) != 1:
        return {'state': 'unresolved', 'reason': 'Target record is missing or duplicated'}
    record = matches[0]
    if (record['binding']['unit_id'] != unit_id or record_identity(record) != record_id or
            record_digest(record) != record['record_sha256']):
        raise ContractError('continuation identity or content changed')
    if configuration_id not in record['applicability']['configuration_ids']:
        return {'state': 'withheld', 'reason': 'Target record excludes selected configuration'}
    quality = quality_for(record, intended_use, purpose)
    approved = (quality.get('approved') is True and quality.get('state') == 'approve' and
                quality.get('record_id') == record_id and
                quality.get('record_sha256') == record['record_sha256'] and
                quality.get('intended_use') == intended_use and quality.get('purpose') == purpose)
    complete = record['completeness']['state'] == 'complete'
    if not approved or (intended_use != 'readable_reference' and not complete):
        return {'state': 'withheld', 'reason': 'Target content quality is unapproved or incomplete'}
    return {'state': 'available', 'record': record, 'applicability': decision,
            'quality': quality, 'complete': complete}
