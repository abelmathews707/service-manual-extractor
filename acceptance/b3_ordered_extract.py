"""Compare a scoped real Ford ordered procedure; expected wording stays local."""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from acceptance.b3_extract import FORD
from sme.contract import ContractError
from sme.html_content import TreeParser, decode_html, parse_html, text_of
from sme.library_export import open_current, search_export
from sme.ordered_procedure import extract_html_ordered_steps
from sme.procedure_extract import _record
from sme.procedure_paths import attach_source_paths
from sme.structured_contracts import new_quality_overlay, validate_records
from sme.structured_extract import _selector, compact


def run(b1, output, expected, *, nested_expected=None, path_recipe=None):
    vocabulary, review = read(b1 / 'vocabulary.json'), read(b1 / 'review.json')
    generation, index = open_current(str(b1 / 'library'),
                                      current_review_revision=review['revision'])
    generation = Path(generation)
    source = read(generation / 'evidence' / (FORD + '.json'))
    citation = {'kind': 'path', 'path': 'originals/content/useni4/v3d/V3D2018.htm'}
    unit = next(item for item in source['units']
                if item['citation'] == citation and item['kind'] == 'section')
    config = _configs(vocabulary)['diesel']
    found = search_export(str(generation), index, _selection(config), '',
                          current_review_revision=review['revision'])
    membership = next((item for item in index['scopes'][found['fingerprint']]['scope'][
        'eligible'] if item['unit_id'] == unit['id']), None)
    if membership is None or membership['state'] != 'confirmed':
        raise ContractError('ordered procedure lacks its own confirmed vehicle scope')
    package = next(item for item in read(generation / 'library.json')['packages']
                   if item['source_id'] == FORD)
    original = generation / package['root'] / citation['path']
    data = original.read_bytes()
    if hashlib.sha256(data).hexdigest() != unit['original_sha256']:
        raise ContractError('ordered source bytes changed')
    binding = {key: source[key] for key in ('source_id', 'source_sha256',
                                           'generation_sha256', 'content_sha256')}
    binding.update(evidence_revision=source['revision'], unit_id=unit['id'],
                   document_id=unit['document_id'], original_sha256=unit['original_sha256'],
                   citation=citation, provenance='native')
    decisions = {config['id']: {'state': 'confirmed', 'unit_id': unit['id'],
                                'configuration_id': config['id']}}
    parser = TreeParser()
    parser.feed(decode_html(data, ford_legacy=True)[0])
    parser.close()
    nodes = {_selector(node): node for node in parser.root.walk() if node.parent is not None}
    body = 'html:nth-of-type(1) > body:nth-of-type(1) > '
    context = []
    for number in range(1, 7):
        selector = body + f'p:nth-of-type({number})'
        text = compact(text_of(nodes[selector]))
        kind = 'warning' if number in (3, 6) else 'region'
        payload = {'severity': 'caution' if number == 3 else 'note', 'instruction': text} \
            if kind == 'warning' else {'kind': 'text', 'caption_original': text}
        context.append(_record(kind, binding, vocabulary, [config['id']],
                               {'kind': 'html', 'selector': selector}, text, payload))
    bundle = extract_html_ordered_steps(
        data, binding, vocabulary, [config['id']], decisions,
        list_selectors=[body + f'ol:nth-of-type({number})' for number in range(1, 9)],
        context=context, coverage_reviewed=True, ford_legacy=True,
        extract_nested=nested_expected is not None,
        missing_context=['Quick Test prerequisite/continuation requires independent review',
                         'Conditional repeat paths and transmission alternatives require review'])
    validate_records(bundle, vocabulary, [source], source_texts={unit['id']: compact(
        parse_html(data, citation['path'], ford_legacy=True)['text'])})
    all_steps = [r for r in bundle['records'] if r['type'] == 'procedure_step']
    steps = [r for r in all_steps if 'parent_record_id' not in r['payload']]
    if ([r['original_text'] for r in steps] != expected['steps'] or
            [r['original_text'] for r in context] != expected['context'] or
            [r['payload']['sequence'] for r in steps] != list(range(1, 9)) or
            any(r['completeness']['state'] != expected['state'] for r in all_steps) or
            any(r['payload']['next_record_ids'] for r in all_steps)):
        raise ContractError('ordered instructions/context differ from frozen original comparison')
    children = [r for r in all_steps if 'parent_record_id' in r['payload']]
    if nested_expected is not None:
        parent = next(r for r in steps if r['payload']['sequence'] == 3)
        if ([{'label': r['payload']['step_label'], 'instruction': r['payload']['instruction']}
             for r in children] != nested_expected['substeps'] or
                parent['payload']['instruction'] != nested_expected['parent_instruction'] or
                any(r['payload']['parent_record_id'] != parent['id'] for r in children)):
            raise ContractError('nested steps differ from independently recorded source structure')
    path_count = 0
    if path_recipe is not None:
        if nested_expected is None:
            raise ContractError('source path comparison requires printed nested labels')
        if hashlib.sha256(Path(path_recipe['pdf_path']).read_bytes()).hexdigest() != \
                path_recipe['pdf_sha256']:
            raise ContractError('visually reviewed source-path PDF changed')
        by_label = {r['payload']['step_label']: r for r in all_steps}
        recipes = {}
        for item in path_recipe['paths']:
            owner = by_label[item['owner_label']]
            source_ref = item['source']
            if set(source_ref) == {'step_label'}:
                source_record = by_label[source_ref['step_label']]
            elif set(source_ref) == {'context_index'} and \
                    type(source_ref['context_index']) is int and \
                    0 <= source_ref['context_index'] < len(context):
                source_record = context[source_ref['context_index']]
            else:
                raise ContractError('source-path recipe has an unknown source reference')
            path = {key: item[key] for key in ('kind', 'quotation', 'condition_original',
                                              'instruction_original', 'unresolved_reason')}
            path.update(source_record_id=source_record['id'],
                        target_record_ids=[by_label[label]['id']
                                           for label in item['target_labels']])
            recipes.setdefault(owner['id'], []).append(path)
            path_count += 1
        bundle = attach_source_paths(bundle, recipes, vocabulary, decisions)
        validate_records(bundle, vocabulary, [source], source_texts={unit['id']: compact(
            parse_html(data, citation['path'], ford_legacy=True)['text'])})
    folder = output / unit['id']
    folder.mkdir(parents=True, exist_ok=True)
    write_once(folder / 'records.json', bundle)
    write_once(folder / 'quality.json', new_quality_overlay())
    report = {'unit_id': unit['id'], 'records': len(bundle['records']), 'steps': len(steps),
              'substeps': len(children),
              'source_paths': path_count,
              'context_records': len(context), 'comparison': 'exact original transcription passed',
              'vehicle': 'confirmed Ford diesel, not V10', 'state': 'incomplete',
              'quality_approvals': 0, 'diagnostic_ready': False}
    write_once(output / 'ordered-verification.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1_root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('expected', type=Path)
    parser.add_argument('--nested-expected', type=Path)
    parser.add_argument('--source-paths', type=Path)
    args = parser.parse_args()
    nested = read(args.nested_expected) if args.nested_expected else None
    paths = read(args.source_paths) if args.source_paths else None
    print(json.dumps(run(args.b1_root, args.output, read(args.expected), nested_expected=nested,
                         path_recipe=paths),
                     indent=2))
