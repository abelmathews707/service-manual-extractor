"""Persist an explicitly witnessed B3 engineering reference review in a NEW root.

This does not perform visual review: the caller must inspect the supplied PDFs
and record the exact compared dependencies first. It never grants diagnostic,
production or vehicle-applicability approval. Candidate inputs stay unchanged.
"""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _selection
from sme.applicability_contracts import _timestamp, digest
from sme.continuation_review import (
    CHECKS,
    append_continuation_event,
    bind_continuation,
    validate_review,
)
from sme.contract import ContractError
from sme.html_content import parse_html
from sme.library_export import open_current, search_export
from sme.structured_contracts import (
    append_quality_event,
    dependency_bindings,
    new_quality_overlay,
    quality_state,
    record_digest,
    validate_records,
)
from sme.structured_extract import compact


def reviewed_logs(bundles, proposal, witness):
    """Validate declared visual comparison; bind only two readable-reference reviews."""
    latest = validate_review(proposal)
    if len(latest) != 1 or next(iter(latest.values()))['action'] != 'propose':
        raise ContractError('expected one currently proposed reference')
    event = next(iter(latest.values()))
    if witness['contract'] != 'b3-visual-reference-review/v1' or \
            witness['proposal_revision'] != proposal['revision']:
        raise ContractError('visual witness does not bind the current proposal')
    if _timestamp(witness['timestamp'], 'timestamp') < _timestamp(event['timestamp'], 'timestamp'):
        raise ContractError('visual review cannot predate the proposal')
    if witness['reviewer']['kind'] != 'agent':
        raise ContractError('this acceptance helper records declared agent engineering review')
    if set(witness['link_checks']) != set(CHECKS) or \
            any(value is not True for value in witness['link_checks'].values()):
        raise ContractError('all link comparison checks require explicit visual review')
    quality, endpoints = {}, {}
    for name in ('source', 'target'):
        bundle, compared = bundles[name], witness['endpoints'][name]
        bound = event['binding'][name]
        records = bundle['records']
        record = next((r for r in records if r['id'] == bound['record_id']), None)
        if record is None or record['binding']['unit_id'] != bound['unit_id'] or \
                record['record_sha256'] != bound['record_sha256'] or \
                any(record_digest(r) != r['record_sha256'] for r in records):
            raise ContractError('reference endpoint or dependencies changed')
        if bundle['revision'] != digest({k: v for k, v in bundle.items() if k != 'revision'}) or \
                compared['bundle_revision'] != bundle['revision']:
            raise ContractError('visual witness binds another record revision')
        if compared['reviewed_dependencies'] != dependency_bindings(record['id'], records):
            raise ContractError('visual comparison omitted or changed a required dependency')
        pdf = Path(compared['pdf_path'])
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != compared['pdf_sha256']:
            raise ContractError('visually reviewed PDF bytes changed')
        pages = compared['pages_reviewed']
        if (not isinstance(pages, list) or not pages or
                any(type(page) is not int or page < 1 for page in pages) or
                pages != sorted(set(pages))):
            raise ContractError('visual review must declare distinct positive PDF pages')
        checks = compared['checks']
        if (any(checks.get(key) is not True for key in
                ('original_compared', 'values_and_units', 'qualifiers', 'source_resolves')) or
                checks.get('context_complete') is not False or
                checks.get('branches_complete') is not False):
            raise ContractError('this partial benchmark must retain incomplete context/branches')
        overlay = new_quality_overlay()
        for action in ('propose', 'approve'):
            overlay = append_quality_event(
                overlay, records, record_id=record['id'], action=action,
                intended_use='readable_reference', purpose='engineering',
                reviewer=witness['reviewer'], timestamp=witness['timestamp'],
                reason=witness['reason'], checks=checks,
                prior_event_id=overlay['events'][-1]['id'] if overlay['events'] else None)
        if quality_state(record['id'], records, overlay, intended_use='diagnostic_instruction',
                         purpose='engineering')['approved']:
            raise ContractError('reference review must not grant diagnostic approval')
        quality[name] = overlay
        endpoints[name] = record
    rebound = bind_continuation(endpoints['source'], endpoints['target'],
                                reference=event['binding']['reference'],
                                configuration_ids=event['binding']['configuration_ids'])
    if rebound != event['binding']:
        raise ContractError('current endpoints do not match the proposed association')
    approved = append_continuation_event(
        proposal, event['binding'], action='approve', reviewer=witness['reviewer'],
        timestamp=witness['timestamp'], reason=witness['reason'], checks=witness['link_checks'],
        expected_revision=proposal['revision'])
    return quality, approved


def run(b1, candidate, witness, output):
    """Recheck both current scopes BEFORE original bytes, then persist reviewed copies."""
    report = read(candidate / 'link-candidate-verification.json')
    proposal = read(candidate / report['source_unit_id'] / 'continuation-review.json')
    latest = validate_review(proposal)
    if len(latest) != 1 or report['binding'] != next(iter(latest.values()))['binding']:
        raise ContractError('candidate report differs from its review binding')
    binding = report['binding']
    if any(report[name + '_unit_id'] != binding[name]['unit_id'] for name in ('source', 'target')):
        raise ContractError('candidate report has inconsistent endpoint identities')
    vocabulary, review = read(b1 / 'vocabulary.json'), read(b1 / 'review.json')
    generation, index = open_current(str(b1 / 'library'),
                                     current_review_revision=review['revision'])
    generation = Path(generation)
    eligible = {}
    for identifier in binding['configuration_ids']:
        config = next(c for c in vocabulary['configurations'] if c['id'] == identifier)
        scope = search_export(str(generation), index, _selection(config), '',
                              current_review_revision=review['revision'])
        eligible[identifier] = {item['unit_id']: item['state'] for item in
                                index['scopes'][scope['fingerprint']]['scope']['eligible']}
    # Resolve every endpoint's metadata eligibility before reading either original.
    for endpoint in ('source', 'target'):
        unit_id = binding[endpoint]['unit_id']
        if any(units.get(unit_id) != 'confirmed' for units in eligible.values()):
            raise ContractError('both reference endpoints require current confirmed scope')
    bundles = {}
    for endpoint in ('source', 'target'):
        unit_id = binding[endpoint]['unit_id']
        folder = candidate / unit_id
        if read(folder / 'quality.json')['events']:
            raise ContractError('acceptance input must remain an unapproved candidate')
        bundle = read(folder / 'records.json')
        source_id = bundle['records'][0]['binding']['source_id']
        evidence = read(generation / 'evidence' / (source_id + '.json'))
        unit = next(u for u in evidence['units'] if u['id'] == unit_id)
        package = next(p for p in read(generation / 'library.json')['packages']
                       if p['source_id'] == source_id)
        if any(r['binding']['unit_id'] != unit_id for r in bundle['records']):
            raise ContractError('candidate mixes source units')
        data = (generation / package['root'] / unit['citation']['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != unit['original_sha256']:
            raise ContractError('original source bytes changed since review')
        validate_records(bundle, vocabulary, [evidence], source_texts={unit_id: compact(
            parse_html(data, unit['citation']['path'], ford_legacy=True)['text'])})
        bundles[endpoint] = bundle
    qualities, approved = reviewed_logs(bundles, proposal, witness)
    # Nothing above writes or changes the input. A separate root preserves history.
    output.mkdir(parents=True, exist_ok=False)
    for name, bundle in bundles.items():
        folder = output / binding[name]['unit_id']
        folder.mkdir()
        write_once(folder / 'records.json', bundle)
        write_once(folder / 'quality.json', qualities[name])
    write_once(output / report['source_unit_id'] / 'continuation-review.json', approved)
    write_once(output / 'visual-review.json', witness)
    result = {key: report[key] for key in
              ('source_unit_id', 'target_unit_id', 'link_id', 'binding')}
    result.update(state='approve', intended_use='readable_reference', purpose='engineering',
                  visual_review_sha256=digest(witness), applicability_revision=review['revision'],
                  quality_approvals=2, link_approvals=1, diagnostic_ready=False,
                  complete_real_procedure_acceptance='pending')
    write_once(output / 'reference-review-verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1_root', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('witness', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1_root, args.candidate, read(args.witness), args.output), indent=2))
