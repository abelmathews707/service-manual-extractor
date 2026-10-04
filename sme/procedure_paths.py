"""Bind reviewed source-quote recipes without inventing executable branch logic.

No free-text condition evaluation, transmission inference, repetition arithmetic,
link following, vehicle approval or content-quality approval occurs here.
"""

import copy
import hashlib
from pathlib import Path

from .contract import ContractError
from .procedure_extract import _covers_configurations
from .structured_contracts import (
    _references,
    _schema,
    _shape,
    _validate_source_paths,
    seal_records,
)
from .structured_extract import _scope

MISSING = 'Conditional source paths require complete graph and independent quality review'


def attach_source_paths(bundle, recipes, vocabulary, decisions):
    """Enrich a caller-validated native unit using explicit record-bound recipes.

    ``recipes`` maps owning step IDs to nonempty lists of ``source_path`` payloads.
    Original wording, context and source identities are retained. Empty target
    lists require an unresolved reason, never a guessed destination. The caller
    must validate the result against current immutable originals afterward.
    """
    if not isinstance(recipes, dict) or not recipes:
        raise ContractError('source paths need a nonempty original-reviewed recipe')
    # Require eligibility before inspecting instruction text or recipe quotations.
    for record in bundle['records']:
        _scope(record['binding'], record['applicability']['configuration_ids'], decisions)
        if record['binding']['provenance'] != 'native':
            raise ContractError('OCR conditional paths need separate original-layout extraction')
    schema = _schema('structured-evidence-v1.schema.json')
    _shape(bundle, schema, schema['$defs'])
    if seal_records(bundle['records']) != bundle:
        raise ContractError('conditional input record identities or content changed')
    records = copy.deepcopy(bundle['records'])
    index = {r['id']: r for r in records}
    if len(index) != len(records) or len({r['binding']['unit_id'] for r in records}) != 1:
        raise ContractError('conditional extraction requires one distinct-record source unit')
    version = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for identifier, paths in recipes.items():
        record = index.get(identifier)
        if record is None or record['type'] != 'procedure_step' or \
                'source_paths' in record['payload']:
            raise ContractError('conditional recipe must name an unannotated procedure step')
        record['payload']['source_paths'] = copy.deepcopy(paths)
        _shape(record['payload'], schema['$defs']['procedure_step'], schema['$defs'])
        record['binding']['extraction_version'] = 'b3-source-paths-v1:' + version + ':' + \
            record['binding']['extraction_version']
    for record in records:
        if record['type'] == 'procedure_step':
            record['payload']['next_record_ids'] = []
            record['completeness'] = {'state': 'incomplete', 'missing': sorted(
                {*record['completeness']['missing'], MISSING})}
        for target, kind in _references(record):
            other = index.get(target)
            if other is None or (kind and other['type'] != kind) or not set(
                    record['applicability']['configuration_ids']) <= set(
                        other['applicability']['configuration_ids']):
                raise ContractError('conditional context/target is absent or outside vehicle scope')
        for path in record['payload'].get('source_paths', ()):
            if not _covers_configurations(path['quotation'], vocabulary,
                                           record['applicability']['configuration_ids']):
                raise ContractError('conditional quotation has conflicting vehicle restrictions')
    _validate_source_paths(index)
    result = seal_records(records)
    # Ensure enrichment never edits original evidence wording as a side effect.
    if any(before['original_text'] != after['original_text']
           for before, after in zip(bundle['records'], result['records'])):
        raise ContractError('conditional enrichment changed original wording')
    return result
