"""Compare all selected Quick Test sections to a local PDF-reviewed transcription.

Only the independently eligible source original is loaded. Destination inventory
uses metadata alone; even confirmed destinations require later original/quality
review. No content, association, diagnostic or production approval is created.
"""

import argparse
import hashlib
import json
import posixpath
from pathlib import Path
from urllib.parse import urlsplit

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from acceptance.b3_extract import FORD
from sme.contract import ContractError
from sme.html_content import parse_html
from sme.library_export import open_current, search_export
from sme.procedure_extract import extract_html_decisions
from sme.structured_contracts import new_quality_overlay, validate_records
from sme.structured_extract import compact


def target_metadata(href, citation, evidence, eligible):
    """Classify a printed href using metadata only, never read destination bytes."""
    result = {'href': href, 'unit_id': None, 'scope': 'unresolved',
              'quality': 'not_reviewed', 'original_loaded': False}
    try:
        target = urlsplit(href)
    except ValueError:
        return dict(result, reason='Malformed destination')
    if target.scheme or target.netloc or target.query or any(c in href for c in ('\\', '%')):
        return dict(result, reason='External or unsupported destination')
    path = posixpath.normpath(posixpath.join(posixpath.dirname(citation['path']), target.path)) \
        if target.path else citation['path']
    if not path.startswith('originals/'):
        return dict(result, reason='Destination is outside source originals')
    units = [u for u in evidence['units'] if u['kind'] == 'section' and
             u['citation'] == {'kind': 'path', 'path': path}]
    if len(units) != 1:
        return dict(result, reason='Destination metadata missing or ambiguous')
    unit = units[0]
    state = eligible.get(unit['id'], 'excluded')
    return dict(result, unit_id=unit['id'], scope=state, fragment=target.fragment,
                reason='Independent original, fragment and quality review still required'
                if state == 'confirmed' else 'Destination is not independently confirmed')


def compare(bundle, inventory, expected):
    """Exact comparison with separately transcribed local expectations, not a golden generator."""
    by_id = {r['id']: r for r in bundle['records']}
    actual = []
    for section in inventory['sections']:
        records = [by_id[key] for key in section['record_ids']]
        actual.append({
            'anchor': section['anchor'],
            'heading': next(r['original_text'] for r in records if r['type'] == 'region'),
            'context': [r['original_text'] for r in records if r['type'] == 'procedure_step'],
            'question': by_id[section['decision_record_id']]['original_text'],
            'branches': {r['payload']['label']: r['original_text'] for r in records
                         if r['type'] == 'diagnostic_edge'},
            'references': [{'label': r['label'], 'targets': r['targets']}
                           for r in inventory['references']
                           if r['section_anchor'] == section['anchor']]})
    if actual != expected['sections']:
        raise ContractError('Quick Test differs from independently transcribed PDF/HTML comparison')
    if any(by_id[s['decision_record_id']]['completeness']['state'] != 'incomplete'
           for s in inventory['sections']):
        raise ContractError('Quick Test candidate must remain incomplete')


def run(b1, output, expected):
    vocabulary, review = read(b1 / 'vocabulary.json'), read(b1 / 'review.json')
    generation, index = open_current(str(b1 / 'library'),
                                      current_review_revision=review['revision'])
    generation = Path(generation)
    evidence = read(generation / 'evidence' / (FORD + '.json'))
    config = _configs(vocabulary)['diesel']
    scope = search_export(str(generation), index, _selection(config), '',
                          current_review_revision=review['revision'])
    eligible = {item['unit_id']: item['state'] for item in index['scopes'][
        scope['fingerprint']]['scope']['eligible']}
    citation = {'kind': 'path', 'path': 'originals/content/useni4/v3d/V3D3001.htm'}
    units = [u for u in evidence['units'] if u['citation'] == citation and u['kind'] == 'section']
    if len(units) != 1 or eligible.get(units[0]['id']) != 'confirmed':
        raise ContractError('Quick Test requires independent confirmed scope before original reads')
    unit = units[0]
    witness = expected['visual_review']
    if witness['pages_reviewed'] != [1, 2] or witness['reviewer_kind'] != 'agent' or \
            hashlib.sha256(Path(witness['pdf_path']).read_bytes()).hexdigest() != \
            witness['pdf_sha256']:
        raise ContractError('Quick Test PDF review witness is missing or changed')
    package = next(p for p in read(generation / 'library.json')['packages']
                   if p['source_id'] == FORD)
    data = (generation / package['root'] / citation['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != unit['original_sha256']:
        raise ContractError('Quick Test original bytes changed')
    binding = {key: evidence[key] for key in ('source_id', 'source_sha256',
                                              'generation_sha256', 'content_sha256')}
    binding.update(evidence_revision=evidence['revision'], unit_id=unit['id'],
                   document_id=unit['document_id'], original_sha256=unit['original_sha256'],
                   citation=citation, provenance='native')
    decisions = {config['id']: {'state': 'confirmed', 'unit_id': unit['id'],
                                'configuration_id': config['id']}}
    bundle, inventory = extract_html_decisions(
        data, binding, vocabulary, [config['id']], decisions,
        anchors=[s['anchor'] for s in expected['sections']], missing_context=expected['unresolved'])
    validate_records(bundle, vocabulary, [evidence], source_texts={unit['id']: compact(
        parse_html(data, citation['path'], ford_legacy=True)['text'])})
    compare(bundle, inventory, expected)
    destinations = [dict(target_metadata(candidate['href'], citation, evidence, eligible),
                         source_record_id=reference['record_id'],
                         candidate_record_id=candidate['record_id'])
                    for reference in inventory['references']
                    for candidate in reference['candidates']]
    folder = output / unit['id']
    folder.mkdir(parents=True, exist_ok=True)
    write_once(folder / 'records.json', bundle)
    write_once(folder / 'quality.json', new_quality_overlay())
    write_once(output / 'reference-inventory.json', inventory)
    report = {'unit_id': unit['id'], 'records': len(bundle['records']),
              'sections': len(inventory['sections']), 'branches': sum(
                  r['type'] == 'diagnostic_edge' for r in bundle['records']),
              'visual_review': witness, 'comparison': 'exact PDF-reviewed transcription passed',
              'expected_sha256': hashlib.sha256(json.dumps(
                  expected, sort_keys=True).encode()).hexdigest(),
              'bundle_revision': bundle['revision'], 'destinations': destinations,
              'unresolved': expected['unresolved'], 'destination_original_loads': 0,
              'quality_approvals': 0, 'link_approvals': 0, 'diagnostic_ready': False}
    write_once(output / 'quick-test-verification.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('expected', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1, args.output, read(args.expected)), indent=2))
