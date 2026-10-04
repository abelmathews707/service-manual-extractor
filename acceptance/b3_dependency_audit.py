"""Bounded one-hop original inspection, never recursive traversal or approval.

Manual text, tables and asset references are saved only to a caller-selected local
acceptance directory. Downstream metadata is inventoried without reading originals.
This is structural inspection, not rendered-layout or diagnostic acceptance.
"""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from acceptance.b3_extract import FORD
from acceptance.b3_quick_test import target_metadata
from sme.contract import ContractError
from sme.html_content import parse_html
from sme.library_export import open_current, search_export


def audit(source_id, evidence, eligible, load_original, *, ford_legacy=False, max_targets=16):
    """Callers supply current validated metadata/scope and a bounded original loader."""
    units = {u['id']: u for u in evidence['units'] if u['kind'] == 'section'}
    loaded = {}

    def inspect(unit_id):
        if unit_id not in units or eligible.get(unit_id) != 'confirmed':
            raise ContractError('dependency requires independent confirmed scope before text reads')
        if unit_id in loaded:
            return loaded[unit_id]
        unit = units[unit_id]
        if unit['citation']['kind'] != 'path' or not unit['citation']['path'].lower().endswith(
                ('.htm', '.html')):
            raise ContractError('dependency audit supports native HTML originals only')
        data = load_original(unit)
        if hashlib.sha256(data).hexdigest() != unit['original_sha256']:
            raise ContractError('dependency original hash changed')
        page = parse_html(data, unit['citation']['path'], ford_legacy=ford_legacy)
        loaded[unit_id] = {'unit_id': unit_id, 'citation': unit['citation'],
                           'original_sha256': unit['original_sha256'], 'scope': 'confirmed',
                           'page': page, 'visual_review': 'pending', 'quality': 'unreviewed'}
        return loaded[unit_id]

    source = inspect(source_id)
    direct = [dict(target_metadata(link['href'], source['citation'], evidence, eligible),
                   label=link['label']) for link in source['page']['references']]
    targets = list(dict.fromkeys(link['unit_id'] for link in direct
                                if link['scope'] == 'confirmed' and link['unit_id'] != source_id))
    if type(max_targets) is not int or not 0 <= max_targets <= 64 or len(targets) > max_targets:
        raise ContractError('dependency target budget exceeded before destination reads')
    for unit_id in targets:
        inspect(unit_id)
    for link in direct:
        destination = loaded.get(link['unit_id'])
        link['original_loaded'] = destination is not None
        link['fragment_state'] = 'not_checked'
        if destination is not None:
            fragment = link.get('fragment', '')
            link['fragment_state'] = ('present' if fragment in destination['page']['anchors']
                                      else 'missing') if fragment else 'whole_document'
        # Fragment presence is structural evidence only, not association approval.
        link['association'] = 'unreviewed'
    for unit_id in targets:
        destination = loaded[unit_id]
        destination['downstream'] = [dict(
            target_metadata(link['href'], destination['citation'], evidence, eligible),
            label=link['label'], traversal='not_followed')
            for link in destination['page']['references']]
    return {'contract': 'b3-dependency-audit/v1', 'source_unit_id': source_id,
            'direct_references': direct, 'documents': list(loaded.values()),
            'original_loads': list(loaded), 'direct_destination_count': len(targets),
            'recursive_original_loads': 0, 'asset_loads': 0,
            'quality_approvals': 0, 'association_approvals': 0, 'diagnostic_ready': False}


def run(b1, output):
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
    source = [u for u in evidence['units'] if u['kind'] == 'section' and u['citation'] == {
        'kind': 'path', 'path': 'originals/content/useni4/v3d/V3D3001.htm'}]
    if len(source) != 1:
        raise ContractError('Quick Test source metadata missing or ambiguous')
    package = next(p for p in read(generation / 'library.json')['packages']
                   if p['source_id'] == FORD)
    root = (generation / package['root']).resolve(strict=True)

    def load(unit):
        path = (root / unit['citation']['path']).resolve(strict=True)
        if not path.is_relative_to(root / 'originals'):
            raise ContractError('original path escapes preserved package')
        return path.read_bytes()

    report = audit(source[0]['id'], evidence, eligible, load, ford_legacy=True)
    report.update(configuration_id=config['id'], review_revision=review['revision'],
                  evidence_revision=evidence['revision'], scope_fingerprint=scope['fingerprint'],
                  audit_version=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    write_once(output / 'dependency-audit.json', report)
    return {'documents': len(report['documents']),
            'direct_references': len(report['direct_references']),
            'direct_destination_count': report['direct_destination_count'],
            'downstream_references': sum(len(d.get('downstream', [])) for d in report['documents']),
            'recursive_original_loads': 0, 'visual_review': 'pending', 'diagnostic_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1, args.output), indent=2))
