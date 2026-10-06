"""Prepare a real, unapproved cross-page reference candidate from reviewed scope.

Printed source markup is compared, but this command never grants content/link
approval. Original visual review and independent named-use review remain separate.
"""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from acceptance.b3_extract import FORD
from sme.continuation_review import (
    CHECKS,
    append_continuation_event,
    bind_continuation,
    new_continuation_review,
)
from sme.contract import ContractError
from sme.html_content import parse_html
from sme.library_export import open_current, search_export
from sme.procedure_extract import extract_html_decision
from sme.structured_contracts import new_quality_overlay, validate_records
from sme.structured_extract import compact


def run(b1, ordered_root, output, expected, *, timestamp):
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
    package = next(item for item in read(generation / 'library.json')['packages']
                   if item['source_id'] == FORD)
    bundles = {}
    for name, path in (('source', 'V3D2018.htm'), ('target', 'V3D3001.htm')):
        citation = {'kind': 'path', 'path': 'originals/content/useni4/v3d/' + path}
        units = [u for u in evidence['units']
                 if u['citation'] == citation and u['kind'] == 'section']
        if len(units) != 1 or eligible.get(units[0]['id']) != 'confirmed':
            raise ContractError('each link endpoint requires its own confirmed source scope')
        unit = units[0]
        data = (generation / package['root'] / citation['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != unit['original_sha256']:
            raise ContractError('link endpoint original bytes changed')
        if name == 'source':
            bundle = read(ordered_root / unit['id'] / 'records.json')
        else:
            binding = {key: evidence[key] for key in ('source_id', 'source_sha256',
                                                      'generation_sha256', 'content_sha256')}
            binding.update(evidence_revision=evidence['revision'], unit_id=unit['id'],
                           document_id=unit['document_id'],
                           original_sha256=unit['original_sha256'], citation=citation,
                           provenance='native')
            decision = {config['id']: {'state': 'confirmed', 'unit_id': unit['id'],
                                       'configuration_id': config['id']}}
            bundle, _ = extract_html_decision(
                data, binding, vocabulary, [config['id']], decision,
                anchor=expected['target_anchor'], missing_context=expected['unresolved'])
        validate_records(bundle, vocabulary, [evidence], source_texts={unit['id']: compact(
            parse_html(data, citation['path'], ford_legacy=True)['text'])})
        bundles[name] = bundle
    source = next(r for r in bundles['source']['records'] if r['type'] == 'procedure_step' and
                  r['payload'].get('step_label') == '8')
    target = next(r for r in bundles['target']['records'] if r['type'] == 'diagnostic_node' and
                  r['payload']['node_kind'] == 'decision')
    context = [r['original_text'] for r in bundles['target']['records']
               if r['type'] == 'procedure_step']
    branches = {r['payload']['label']: r['original_text'] for r in bundles['target']['records']
                if r['type'] == 'diagnostic_edge'}
    if (source['original_text'] != expected['source_reference'] or
            target['original_text'] != expected['question'] or branches != expected['branches'] or
            context != [expected['context']]):
        raise ContractError('link candidate differs from separately transcribed source markup')
    binding = bind_continuation(source, target, reference=expected['source_reference'],
                                configuration_ids=[config['id']])
    proposal = new_continuation_review()
    proposal = append_continuation_event(
        proposal, binding, action='propose', reviewer={'id': 'codex-b3-candidate', 'kind': 'agent'},
        timestamp=timestamp, reason='Candidate name-to-entry association only; original visual '
        'comparison and independent quality review are outstanding. Not diagnostic approval.',
        checks=dict.fromkeys(CHECKS, False), expected_revision=proposal['revision'])
    for bundle in bundles.values():
        folder = output / bundle['records'][0]['binding']['unit_id']
        folder.mkdir(parents=True, exist_ok=True)
        write_once(folder / 'records.json', bundle)
        write_once(folder / 'quality.json', new_quality_overlay())
    write_once(output / source['binding']['unit_id'] / 'continuation-review.json', proposal)
    report = {'source_unit_id': source['binding']['unit_id'],
              'target_unit_id': target['binding']['unit_id'],
              'link_id': proposal['events'][-1]['link_id'], 'binding': binding,
              'comparison': 'separately transcribed markup matches; visual review outstanding',
              'state': 'propose', 'quality_approvals': 0, 'link_approvals': 0,
              'diagnostic_ready': False}
    write_once(output / 'link-candidate-verification.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1_root', type=Path)
    parser.add_argument('ordered_root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('expected', type=Path)
    parser.add_argument('--timestamp', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.b1_root, args.ordered_root, args.output, read(args.expected),
                         timestamp=args.timestamp), indent=2))
