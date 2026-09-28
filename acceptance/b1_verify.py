"""Evaluate hand-reviewed, local-only B1 ground truth; this is not an extractor.

The input is authored separately from extraction by inspecting original pages.
It contains licensed source quotations and therefore must never be committed.
"""

import argparse
import copy
from pathlib import Path

from acceptance.a10_pilot_review import GM_SOURCE, _one
from acceptance.a10_verify_pilot import verify as verify_a10
from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_pilot_vocabulary import FORD_SOURCE
from sme.applicability_contracts import POLICY_VERSION, digest
from sme.contract import ContractError
from sme.library_export import open_current, search_export
from sme.matching import match_unit
from sme.structured_contracts import (
    append_quality_event,
    diagnostic_admission,
    new_quality_overlay,
    quality_state,
    record_digest,
    record_identity,
    seal_records,
    validate_records,
)

CHECKS = dict.fromkeys(('original_compared', 'values_and_units', 'qualifiers',
                       'context_complete', 'branches_complete', 'source_resolves'), True)
TIMESTAMP = '2026-09-28T20:00:00+00:00'


def _selection(config):
    result = {key: config[key] for key in ('make_id', 'model_id', 'model_year', 'engine_id')}
    if config['qualifiers']:
        result['qualifiers'] = config['qualifiers']
    return result


def _configs(vocabulary):
    names = {'v10': (2003, '6.8L V10'), 'cng': (2003, '6.8L CNG V10'),
             'diesel': (2003, '6.0L Power Stroke diesel'), 'gm-w': (2002, '4.3L VIN W'),
             'gm-x': (2006, '4.3L VIN X'), 'gm-v': (2006, '4.8L VIN V')}
    engines = {item['name']: item['id'] for item in vocabulary['engines']}
    return {name: _one([item for item in vocabulary['configurations']
                        if item['model_year'] == year and item['engine_id'] == engines[engine]],
                       name) for name, (year, engine) in names.items()}


def bind_ground_truth(gold, sources, packages, vocabulary):
    """Bind hand-entered values to source units; do not infer or extract values."""
    configs = _configs(vocabulary)
    content = {key: {doc['id']: doc for doc in read(root / '.sme-content.json')['documents']}
               for key, root in packages.items()}
    result, labels, texts = [], {}, {}
    for authored in gold['records']:
        source = sources[authored['source']]
        citation = {'kind': 'page' if 'page' in authored else 'path', 'path': authored['path']}
        if 'page' in authored:
            citation['page'] = authored['page']
        kind = 'region' if 'page' in authored else 'section'
        unit = _one([item for item in source['units']
                     if item['citation'] == citation and item['kind'] == kind], authored['label'])
        original = authored['original_text']
        locator = ({'kind': 'pdf_region', 'page': authored['page'], 'bbox': authored['bbox']}
                   if 'bbox' in authored else
                   {'kind': 'text_quote', 'quote': original, 'prefix': '', 'suffix': ''})
        doc = content[authored['source']][unit['document_id']]
        binding = {key: source[key] for key in ('source_id', 'source_sha256',
                                               'generation_sha256', 'content_sha256')}
        binding.update(evidence_revision=source['revision'], unit_id=unit['id'],
                       document_id=unit['document_id'], original_sha256=unit['original_sha256'],
                       citation=citation, provenance='ocr' if authored['label'] == 'gm-ocr-note'
                       else 'native', extraction_version='b1-hand-reviewed-ground-truth-v1')
        record = {'type': authored['type'], 'binding': binding, 'locator': locator,
                  'original_text': original, 'applicability': {
                      'vocabulary_revision': vocabulary['revision'],
                      'policy_version': POLICY_VERSION,
                      'configuration_ids': [configs[authored['configuration']]['id']]
                      if authored['configuration'] else []},
                  'conditions': authored['conditions'], 'context_record_ids': authored['context'],
                  'completeness': authored['completeness'],
                  'payload': copy.deepcopy(authored['payload'])}
        labels[authored['label']] = record_identity(record)
        result.append(record)
        texts[unit['id']] = ' '.join(doc['text'].split())
    for record in result:
        record['context_record_ids'] = [labels[label] for label in record['context_record_ids']]
        for field in ('tool_ids', 'next_record_ids'):
            if field in record['payload']:
                record['payload'][field] = [labels[label] for label in record['payload'][field]]
        for field in ('from_record_id', 'to_record_id', 'target_record_id'):
            if field in record['payload']:
                record['payload'][field] = labels[record['payload'][field]]
    bundle = seal_records(result)
    validate_records(bundle, vocabulary, list(sources.values()), source_texts=texts)
    return bundle, labels, configs, texts


def quality_event(overlay, records, record_id, action, *, prior=None, history=()):
    return append_quality_event(overlay, records, record_id=record_id, action=action,
                                intended_use='structured_reference', purpose='engineering',
                                reviewer={'id': 'codex-b1-original-review', 'kind': 'agent'},
                                timestamp=TIMESTAMP, reason='B1 original visually compared; '
                                'bounded reference only, not production or diagnosis',
                                checks=CHECKS,
                                prior_event_id=prior, history=history)


def verify(root, gold):
    if not __debug__:
        raise ValueError('acceptance checks require Python assertions enabled (no -O)')
    vocabulary, review = read(root / 'vocabulary.json'), read(root / 'review.json')
    generation, index = open_current(str(root / 'library'),
                                      current_review_revision=review['revision'])
    generation = Path(generation)
    library = read(generation / 'library.json')
    packages = {key: generation / _one([item for item in library['packages']
                                        if item['source_id'] == identifier], key)['root']
                for key, identifier in (('ford', FORD_SOURCE), ('gm', GM_SOURCE))}
    sources = {key: read(root / 'evidence' / (identifier + '.json'))
               for key, identifier in (('ford', FORD_SOURCE), ('gm', GM_SOURCE))}
    bundle, labels, configs, texts = bind_ground_truth(gold, sources, packages, vocabulary)
    records = bundle['records']
    by_id = {record['id']: record for record in records}
    quality = new_quality_overlay()
    for record in records:
        if record['completeness']['state'] != 'complete':
            continue
        quality = quality_event(quality, records, record['id'], 'propose')
        quality = quality_event(quality, records, record['id'], 'approve',
                                 prior=quality['events'][-1]['id'])

    def state(identifier, overlay=quality, current=records, history=()):
        return quality_state(identifier, current, overlay, intended_use='structured_reference',
                             purpose='engineering', history=history)

    def search(case):
        result = search_export(str(generation), index, _selection(configs[case['configuration']]),
                               case['query'], mode=case.get('mode', 'confirmed'),
                               current_review_revision=review['revision'])
        eligible = {item['unit_id']: item for item in index['scopes'][
            result['fingerprint']]['scope']['eligible']}
        forbidden = ({item['id'] for item in sources['gm']['units']}
                     if case['configuration'] in ('v10', 'cng', 'diesel') else
                     {item['id'] for item in sources['ford']['units']})
        if set(eligible) & forbidden:
            raise AssertionError('cross-brand evidence entered search eligibility')
        for shard in result['loaded_shard_ids']:
            loaded = set(index['shards'][shard]['unit_ids'])
            if loaded & forbidden or not loaded <= set(eligible):
                raise AssertionError('excluded text shard was loaded')
        return result, eligible

    results = []
    for case in gold['scenarios']:
        label = case.get('record') or case.get('required') or case.get('forbidden') or 'ford-ckp'
        record = by_id[labels[label]]
        kind = case['kind']
        if kind in ('search', 'exclusion'):
            found, eligible = search(case)
            unit = record['binding']['unit_id']
            if kind == 'search':
                assert eligible[unit]['state'] == case['expected_state'], case['id']
                retrieved = unit in {item['unit_id'] for item in found['results']}
                assert retrieved == case.get('baseline_retrieves', True), case['id']
            else:
                assert unit not in eligible, case['id']
        elif kind == 'qualifier':
            selection = _selection(configs['v10']) | {'qualifiers': case['qualifiers']}
            decision = match_unit(sources['ford'], read(packages['ford'] / '.sme-manifest.json'),
                                  vocabulary, record['binding']['unit_id'], selection,
                                  review=review, validate=False)
            assert decision['state'] == case['expected_state'], case['id']
            assert not decision['search_eligible'], case['id']
        elif kind == 'fields':
            assert record['payload'] == case['expected'], case['id']
        elif kind == 'quality':
            assert state(record['id'])['approved'] == case['expected_engineering_structured']
            production = quality_state(record['id'], records, quality,
                                        intended_use='diagnostic_instruction')
            assert production['approved'] == case['expected_production_diagnostic']
            match = {'unit_id': record['binding']['unit_id'], 'state': 'confirmed',
                     'configuration_id': configs['v10']['id']}
            assert not diagnostic_admission(record, configs['v10']['id'], match, production)
            assert not diagnostic_admission(record, configs['v10']['id'], match,
                                             state(record['id']))
        elif kind == 'stale':
            changed = copy.deepcopy(records)
            dependency = next(item for item in changed if item['id'] == labels[case['dependency']])
            dependency['payload']['instruction'] += ' [authored stale-review test mutation]'
            changed = seal_records(changed)['records']
            assert state(record['id'], current=changed, history=records)['state'] == 'stale'
        elif kind == 'revoke':
            prior = next(event['id'] for event in reversed(quality['events'])
                         if event['record_id'] == record['id'])
            revoked = quality_event(quality, records, record['id'], 'revoke', prior=prior)
            assert not state(record['id'], overlay=revoked)['approved']
        elif kind == 'incomplete':
            assert record['completeness']['state'] != 'complete'
            proposed = append_quality_event(new_quality_overlay(), records, record_id=record['id'],
                                            action='propose', intended_use='diagnostic_instruction',
                                            purpose='engineering',
                                            reviewer={'id': 'test', 'kind': 'agent'},
                                            timestamp=TIMESTAMP, reason='Abstention test',
                                            checks=CHECKS)
            try:
                append_quality_event(proposed, records, record_id=record['id'], action='approve',
                                     intended_use='diagnostic_instruction', purpose='engineering',
                                     reviewer={'id': 'test', 'kind': 'agent'}, timestamp=TIMESTAMP,
                                     reason='Must refuse incomplete instructions', checks=CHECKS,
                                     prior_event_id=proposed['events'][-1]['id'])
            except ContractError:
                pass
            else:
                raise AssertionError('incomplete/ambiguous instruction approved')
        elif kind == 'branches':
            edges = [item for item in records if item['type'] == 'diagnostic_edge' and
                     item['payload']['from_record_id'] == record['id']]
            assert [edge['payload']['label'] for edge in edges] == case['expected_labels']
            assert [edge['payload']['condition'] for edge in edges] == case['expected_conditions']
            assert record['completeness']['state'] == 'incomplete'
        elif kind == 'example':
            assert (record['type'] == case['expected_type'] and
                    record['type'] != case['forbidden_type'])
            assert 'Example' in record['payload']['caption_original']
        elif kind == 'unreadable':
            unreadable = texts | {record['binding']['unit_id']: ''}
            try:
                validate_records(bundle, vocabulary, list(sources.values()),
                                 source_texts=unreadable)
            except ContractError:
                pass
            else:
                raise AssertionError('unreadable source was silently supplied an answer')
        elif kind == 'concern':
            assert record['binding']['citation']['path'] == case['required_reference']
            assert len(case['pending_roles']) >= 3 and len(case['questions']) >= 3
            assert not quality_state(record['id'], records, quality,
                                     intended_use='diagnostic_instruction')['approved']
        else:
            raise ValueError(f'unknown scenario kind: {kind}')
        result = {'id': case['id'], 'split': case['split'], 'result': 'passed'}
        if kind == 'search':
            result['retrieved'] = retrieved
            result['future_expected_retrieves'] = case.get('future_expected_retrieves', True)
            if not retrieved:
                result['result'] = 'retrieval_baseline_miss'
                result['limitation'] = case['baseline_reason']
        results.append(result)
    all_sources = [read(path) for path in sorted((root / 'evidence').glob('*.json'))]
    regression = verify_a10(str(root / 'library'), vocabulary, review,
                            [s for s in all_sources if s['source_id'] != GM_SOURCE], sources['gm'])
    misses = [item['id'] for item in results if item['result'] == 'retrieval_baseline_miss']
    report = {'status': 'engineering_contract_pass_with_retrieval_gaps',
              'contract_safety_checks_passed': len(results),
              'retrieval_baseline_misses': misses, 'ground_truth_sha256': digest(gold),
              'record_revision': bundle['revision'], 'quality_revision': quality['revision'],
              'library_revision': index['library_revision'], 'review_revision': review['revision'],
              'records': len(records), 'types': sorted({record['type'] for record in records}),
              'production_diagnostic_approvals': 0, 'scenarios': results,
              'a10_regression': regression,
              'not_tested': ['AI answer generation', 'production human approval',
                            'full V10 no-start diagnosis', 'bulk B2/B3 extraction']}
    assert all(record_digest(record) == record['record_sha256'] for record in records)
    write_once(root / 'structured-records.json', bundle)
    write_once(root / 'structured-quality-review.json', quality)
    # Timing measurements vary; report files are explicitly versioned by the caller.
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acceptance_root', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.acceptance_root, read(args.acceptance_root / 'ground-truth.json'))
    write_once(args.report, result)
    import json
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
