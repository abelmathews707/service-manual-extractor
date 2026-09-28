"""Run local-only structural recipes and compare B2 output with frozen B1 gold.

Recipes contain source locators/headers/row labels, never expected numeric
values. They and licensed outputs stay outside Git. No review is auto-approved.
"""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection, bind_ground_truth
from sme.contract import ContractError
from sme.html_content import parse_html
from sme.library_export import open_current, search_export
from sme.structured_contracts import new_quality_overlay, seal_records, validate_records
from sme.structured_extract import (
    extract_html,
    extract_native_line,
    extract_part_mentions,
    pdf_region_text,
)


def run(root, output, recipes):
    vocabulary, review = read(root / 'vocabulary.json'), read(root / 'review.json')
    generation, index = open_current(str(root / 'library'),
                                      current_review_revision=review['revision'])
    generation = Path(generation)
    library = read(generation / 'library.json')
    configs = _configs(vocabulary)
    packages = {item['source_id']: generation / item['root'] for item in library['packages']}
    sources = {key: read(root / 'evidence' / (key + '.json')) for key in packages}
    results, reports, texts = [], [], {}
    for recipe in recipes['units']:
        source = sources[recipe['source_id']]
        citation = recipe['citation']
        units = [unit for unit in source['units'] if unit['citation'] == citation and
                 unit['kind'] == ('region' if citation['kind'] == 'page' else 'section')]
        if len(units) != 1:
            raise ContractError('recipe unit is absent/ambiguous')
        unit = units[0]
        configurations, decisions = [], {}
        if recipe.get('configuration'):
            config = configs[recipe['configuration']]
            found = search_export(str(generation), index, _selection(config), '',
                                   current_review_revision=review['revision'])
            eligible = next((item for item in index['scopes'][found['fingerprint']][
                'scope']['eligible'] if item['unit_id'] == unit['id']), None)
            if eligible is None or eligible['state'] != 'confirmed':
                raise ContractError('recipe content is not confirmed for selected vehicle')
            configurations = [config['id']]
            decisions[config['id']] = {'state': 'confirmed', 'unit_id': unit['id'],
                                       'configuration_id': config['id']}
        elif recipe['kind'] != 'part_review' or not recipe.get('unfiltered_original_review'):
            raise ContractError('unmapped extraction is only explicit original part review')
        # Only after scope resolution may this unit's original/normalized content be read.
        package = packages[source['source_id']]
        original = package / citation['path']
        if original.is_symlink() or '..' in Path(citation['path']).parts:
            raise ContractError('unsafe original source locator')
        if hashlib.sha256(original.read_bytes()).hexdigest() != unit['original_sha256']:
            raise ContractError('original source changed')
        text = (parse_html(original.read_bytes(), citation['path'], ford_legacy=True)['text']
                if original.suffix.lower() in ('.htm', '.html') else
                pdf_region_text(original, citation['page'], recipe['bbox']))
        texts[unit['id']] = ' '.join(text.split())
        binding = {key: source[key] for key in ('source_id', 'source_sha256',
                                               'generation_sha256', 'content_sha256')}
        binding.update(evidence_revision=source['revision'], unit_id=unit['id'],
                       document_id=unit['document_id'], original_sha256=unit['original_sha256'],
                       citation=citation, provenance='native')
        if recipe['kind'] == 'html':
            bundle, abstentions = extract_html(original.read_bytes(), binding, vocabulary,
                                               configurations, decisions, recipe['tables'])
        elif recipe['kind'] == 'part_review':
            bundle, abstentions = extract_part_mentions(
                text, binding, vocabulary, configurations, decisions,
                pattern=recipe['pattern'], namespace=recipe['namespace'], allow_unmapped=True)
        elif recipe['kind'] == 'native_pdf':
            bundle, abstentions = extract_native_line(
                text, binding, vocabulary, configurations, decisions,
                locator={'kind': 'pdf_region', 'page': citation['page'], 'bbox': recipe['bbox']},
                pattern=recipe['pattern'], condition=recipe['condition'])
        else:
            raise ContractError('unknown recipe kind')
        validate_records(bundle, vocabulary, [source], source_texts=texts)
        results.extend(bundle['records'])
        reports.append({'unit_id': unit['id'], 'records': len(bundle['records']),
                        'abstentions': abstentions})
        destination = output / unit['id']
        destination.mkdir(parents=True, exist_ok=True)
        write_once(destination / 'records.json', bundle)
        write_once(destination / 'quality.json', new_quality_overlay())

    # Gold binding reads the frozen small benchmark after extraction, not as recipe input.
    gold = read(root / 'ground-truth.json')
    selected_sources = {name: sources[recipe['source_id']]
                        for name, recipe in [('ford', recipes['units'][0]),
                                              ('gm', next(item for item in recipes['units']
                                                          if item['kind'] == 'native_pdf'))]}
    gold_packages = {name: packages[source['source_id']]
                     for name, source in selected_sources.items()}
    expected, labels, _, _ = bind_ground_truth(gold, selected_sources, gold_packages, vocabulary)
    comparisons = []
    for label in recipes['gold_labels']:
        target = next(item for item in expected['records'] if item['id'] == labels[label])
        matches = [item for item in results if item['type'] == target['type'] and
                   item['original_text'] == target['original_text']]
        if len(matches) != 1 or matches[0]['payload'] != target['payload'] or \
                matches[0]['conditions'] != target['conditions']:
            raise ContractError('extracted fields disagree with independently entered gold: ' +
                                label)
        comparisons.append({'label': label, 'result': 'exact_fields_conditions_pass'})
    report = {'records': len(results), 'units': reports, 'gold_comparisons': comparisons,
              'production_diagnostic_approvals': 0,
              'library_revision': index['library_revision'],
              'record_revision': seal_records(results)['revision']}
    write_once(output / 'verification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1_root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('recipes', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1_root, args.output, read(args.recipes)), indent=2))


if __name__ == '__main__':
    main()
