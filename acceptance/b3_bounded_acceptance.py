"""Owner-approved bounded B3 gate; never upgrades partial records or approvals.

Re-extract the frozen real examples against independent local transcriptions.
Full required-dependency closure is deferred T1 work, not claimed by this report.
Licensed originals, expected fields and generated reports stay outside Git.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b3_extract import run as native_run
from acceptance.b3_ordered_extract import run as ordered_run
from acceptance.b3_quick_test import run as quick_run
from sme.contract import ContractError
from sme.procedure_graph import graph_completeness
from sme.structured_contracts import append_quality_event, new_quality_overlay, seal_records

QUICK = 'unit_45ab991c0e78c5ab3417dee3fe703139'
ORDERED = 'unit_7f9e2dc4e80b9a5215d971cdca9b960c'
GM = 'unit_a3642598b2524a21890f6fed4f55a40d'


def verify_bundle(bundle, baseline):
    """Exact frozen comparison plus attempted instruction promotion in memory only."""
    for value in (bundle, baseline):
        if seal_records(value['records']) != value:
            raise ContractError('bounded benchmark record identity/content changed')

    def fields(value):
        records = copy.deepcopy(value['records'])
        for record in records:
            # Parser/validator code revisions legitimately change these hashes.
            # Compare EVERY other field, including source bindings and record IDs.
            record.pop('record_sha256')
            record['binding'].pop('extraction_version')
        return records

    if fields(bundle) != fields(baseline):
        raise ContractError('bounded benchmark differs from frozen source-compared records')
    version_changes = [{'record_id': new['id'],
                        'before': old['binding']['extraction_version'],
                        'after': new['binding']['extraction_version']}
                       for new, old in zip(bundle['records'], baseline['records'])
                       if new['binding']['extraction_version'] !=
                       old['binding']['extraction_version']]
    checks = dict.fromkeys(('original_compared', 'values_and_units', 'qualifiers',
                           'context_complete', 'branches_complete', 'source_resolves'), True)
    graphs, blocked = [], []
    for record in bundle['records']:
        if record['type'] not in ('procedure_step', 'diagnostic_node', 'diagnostic_edge'):
            continue
        if record['completeness']['state'] != 'incomplete':
            raise ContractError('partial real benchmark was promoted to complete')
        graph = graph_completeness(record['id'], bundle['records'])
        if graph['state'] != 'incomplete' or graph['diagnostic_ready']:
            raise ContractError('partial real graph gained completeness/readiness')
        graphs.append(graph)
        for use in ('structured_reference', 'diagnostic_instruction'):
            args = {'record_id': record['id'], 'intended_use': use, 'purpose': 'engineering',
                    'reviewer': {'id': 'b3-negative-acceptance-test', 'kind': 'agent'},
                    'timestamp': '2026-10-04T00:00:00+00:00',
                    'reason': 'In-memory negative test only, not an actual original review',
                    'checks': checks}
            proposal = append_quality_event(new_quality_overlay(), bundle['records'],
                                             action='propose', **args)
            try:
                append_quality_event(proposal, bundle['records'], action='approve', **args,
                                     prior_event_id=proposal['events'][-1]['id'])
            except ContractError as error:
                if 'instruction approval requires complete checked context' not in str(error):
                    raise
            else:
                raise ContractError('incomplete benchmark gained instruction-quality approval')
        blocked.append(record['id'])
    if not blocked:
        raise ContractError('benchmark has no incomplete procedure/branch records to check')
    return {'records': len(bundle['records']), 'revision': bundle['revision'],
            'exact_source_and_semantic_field_comparison': True,
            'extraction_version_changes': version_changes,
            'baseline_revision': baseline['revision'],
            'instruction_promotions_blocked': blocked,
            'graphs': graphs, 'persisted_quality_events_added': 0, 'diagnostic_ready': False}


def run(b1, b3, output):
    if output.exists():
        raise ContractError('bounded acceptance requires a new output directory')
    expectations = ('quick-test-all-expected-v1.json', 'ordered-expected-v1.json',
                    'nested-expected-v1.json', 'conditional-path-recipe-v1.json',
                    'expected-fields.json')
    hashes = {name: hashlib.sha256((b3 / name).read_bytes()).hexdigest()
              for name in expectations}
    quick_run(b1, output / 'quick-test', read(b3 / expectations[0]))
    ordered_run(b1, output / 'ordered', read(b3 / expectations[1]),
                nested_expected=read(b3 / expectations[2]), path_recipe=read(b3 / expectations[3]))
    native_run(b1, output / 'native', read(b3 / expectations[4]))
    examples = {}
    for name, unit, old in (('quick-test', QUICK, 'quick-test-records-v1'),
                             ('ordered', ORDERED, 'conditional-records-v1'),
                             ('native', GM, 'records-v2')):
        bundle = read(output / name / unit / 'records.json')
        examples[name] = verify_bundle(bundle, read(b3 / old / unit / 'records.json'))
        if read(output / name / unit / 'quality.json')['events']:
            raise ContractError('bounded re-extraction added quality events')
    inventory = read(output / 'quick-test/reference-inventory.json')
    boundaries = {
        'quick_test_references': inventory['references'],
        'quick_test_required_context': read(b3 / expectations[0])['unresolved'],
        'ordered_conditional_paths': read(b3 / expectations[3])['paths'],
        'gm_boundary': {
            'unit_id': GM, 'included': 'Page 87 step 3, temperature warning, Yes/No alternatives',
            'blocked_prerequisites': ['Diagnostic System Check - Engine Controls',
                                     'Fuel Injector Coil Test (4.3L VIN W & X)'],
            'blocked_continuations': ['Next step on page 88',
                                      'Full balance-test context, figure and later steps'],
            'execution_permitted': False},
        'policy': 'Source targets/printed groupings are not approved execution edges. '
                  'All unresolved required dependencies remain blocked, never success terminals.',
        'full_dependency_review': 'Deferred T1 intensive testing', 'diagnostic_ready': False}
    write_once(output / 'boundaries.json', boundaries)
    report = {'contract': 'b3-bounded-acceptance/v1',
              'extractor_gate': 'passed', 'app_gate': 'must be verified separately',
              'benchmark': examples, 'expected_file_sha256': hashes,
              'boundary_sha256': hashlib.sha256(
                  (output / 'boundaries.json').read_bytes()).hexdigest(),
              'complete_real_workflow': False, 'diagnostic_ready': False,
              'review_events_added': 0, 'deferred': 'T1 full required-dependency testing'}
    write_once(output / 'verification.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('b1', 'b3', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = run(args.b1, args.b3, args.output)
    print(json.dumps({key: value for key, value in result.items()
                      if key != 'benchmark'}, indent=2))
