"""Bounded B3 original-inspected examples; licensed expected fields stay local.

GM is scoped to the existing reviewed page. Ford is explicit unmapped original
inspection, not selected-vehicle admission. No source review is manufactured.
"""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from sme.contract import ContractError
from sme.html_content import parse_html
from sme.library_export import open_current, search_export
from sme.procedure_extract import _record, extract_html_decision, extract_native_decision
from sme.structured_contracts import new_quality_overlay, validate_records
from sme.structured_extract import compact, pdf_region_text

FORD = 'src_7c2747f1e143b7a36697aae0f9f68f45'
GM = 'src_241ae321543b966629942d2b1977d6eb'


def run(b1, output, expected):
    vocabulary, review = read(b1 / 'vocabulary.json'), read(b1 / 'review.json')
    generation, index = open_current(str(b1 / 'library'),
                                  current_review_revision=review['revision'])
    generation = Path(generation)
    packages = {item['source_id']: generation / item['root']
                for item in read(generation / 'library.json')['packages']}
    reports = []
    for name, source_id, citation in (
            ('ford', FORD, {'kind': 'path',
                           'path': 'originals/content/useni4/v32/V325118.htm'}),
            ('gm', GM, {'kind': 'page', 'path': '1998-2007/ENGINE PERFORMANCE.pdf', 'page': 87})):
        source = read(generation / 'evidence' / (source_id + '.json'))
        units = [unit for unit in source['units'] if unit['citation'] == citation and
                 unit['kind'] == ('section' if name == 'ford' else 'region')]
        if len(units) != 1:
            raise ContractError('B3 source unit is ambiguous')
        unit = units[0]
        configurations, decisions = [], {}
        if name == 'gm':
            config = _configs(vocabulary)['gm-w']
            found = search_export(str(generation), index, _selection(config), '',
                                   current_review_revision=review['revision'])
            scope = next((item for item in index['scopes'][found['fingerprint']]['scope'][
                'eligible'] if item['unit_id'] == unit['id']), None)
            if scope is None or scope['state'] != 'confirmed':
                raise ContractError('GM procedure source lacks current confirmed eligibility')
            configurations = [config['id']]
            decisions[config['id']] = {'state': 'confirmed', 'unit_id': unit['id'],
                                       'configuration_id': config['id']}
        original = packages[source_id] / citation['path']
        if hashlib.sha256(original.read_bytes()).hexdigest() != unit['original_sha256']:
            raise ContractError('B3 original bytes changed')
        binding = {key: source[key] for key in ('source_id', 'source_sha256',
                                               'generation_sha256', 'content_sha256')}
        binding.update(evidence_revision=source['revision'], unit_id=unit['id'],
                       document_id=unit['document_id'], original_sha256=unit['original_sha256'],
                       citation=citation, provenance='native')
        if name == 'ford':
            bundle, links = extract_html_decision(
                original.read_bytes(), binding, vocabulary, [], {}, anchor='pptNC1',
                allow_unmapped=True,
                missing_context=['Introduction and target procedures unreviewed'])
            source_text = compact(parse_html(original.read_bytes(), citation['path'],
                                             ford_legacy=True)['text'])
        else:
            bbox = [.06, .93, .96, .99]
            text = pdf_region_text(original, 87, bbox)
            note_bbox = [.10, .887, .85, .927]
            note = compact(pdf_region_text(original, 87, note_bbox))
            if not note.startswith('NOTE: '):
                raise ContractError('GM note label changed')
            warning = _record('warning', binding, vocabulary, configurations,
                              {'kind': 'pdf_region', 'page': 87, 'bbox': note_bbox}, note,
                              {'severity': 'note', 'instruction': note.removeprefix('NOTE: ')})
            bundle, links = extract_native_decision(
                text, binding, vocabulary, configurations, decisions,
                locator={'kind': 'pdf_region', 'page': 87, 'bbox': bbox}, context=[warning],
                missing_context=['Prerequisite procedures and next-page targets unreviewed'])
            source_text = compact(pdf_region_text(original, 87, [0, 0, 1, 1]))
        validate_records(bundle, vocabulary, [source], source_texts={unit['id']: source_text})
        records = bundle['records']
        decision = next(r for r in records if r['type'] == 'diagnostic_node' and
                        r['payload']['node_kind'] == 'decision')
        branches = {r['payload']['label']: r['original_text'] for r in records
                    if r['type'] == 'diagnostic_edge'}
        if decision['payload']['operation'] != expected[name]['question']:
            raise ContractError('extracted question differs from frozen original transcription')
        if name == 'gm':
            step = next(r for r in records if r['type'] == 'procedure_step')
            if (step['payload']['instruction'] != expected[name]['instruction'] or
                    step['payload']['sequence'] != expected[name]['sequence'] or
                    branches != expected[name]['branches'] or
                    warning['payload']['instruction'] != expected[name]['warning']):
                raise ContractError('GM instruction/branches/warning differ from frozen fields')
        elif branches['Yes'] != expected[name]['yes'] or \
                len(links[0]['targets']) != expected[name]['no_target_count']:
            raise ContractError('Ford branch or continuation was lost')
        if decision['completeness']['state'] != 'incomplete':
            raise ContractError('unreviewed procedure was marked complete')
        folder = output / unit['id']
        folder.mkdir(parents=True, exist_ok=True)
        write_once(folder / 'records.json', bundle)
        write_once(folder / 'continuations.json', {'continuations': links})
        write_once(folder / 'quality.json', new_quality_overlay())
        reports.append({'source': name, 'unit_id': unit['id'], 'records': len(records),
                        'comparison': 'exact reviewed fields pass',
                        'continuations': len(links), 'state': 'incomplete',
                        'vehicle_admission': 'confirmed page' if configurations else
                                             'unmapped original inspection only'})
    report = {'examples': reports, 'automatic_approvals': 0, 'diagnostic_ready': False}
    write_once(output / 'verification.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1_root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('expected', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1_root, args.output, read(args.expected)), indent=2))
