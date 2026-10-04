"""Publish corrected evidence to a separate disposable B3 library, never live data."""

import argparse
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from acceptance.b3_extract import FORD
from acceptance.b3_symptom_scope import compare
from sme.applicability_contracts import review_event_is_stale
from sme.contract import ContractError
from sme.library_export import open_current, publish_library, search_export
from sme.review import rebase


def verify_scopes(stage, index, vocabulary, review, target_unit, snapshots):
    """Gate each actual shard read using metadata, including empty result searches."""
    checks = {}
    for name, config in _configs(vocabulary).items():
        # Resolve metadata without text to derive the independently admitted set.
        selected = search_export(stage, index, _selection(config), '',
                                 current_review_revision=review['revision'])
        eligible = {item['unit_id'] for item in index['scopes'][
            selected['fingerprint']]['scope']['eligible']}
        if (target_unit in eligible) != (name == 'diesel'):
            raise ContractError('candidate symptom-chart eligibility regression')
        forbidden = {u['id'] for s in snapshots
                     if (s['source_id'] == FORD) == name.startswith('gm')
                     for u in s['units']}
        paths = {str((Path(stage) / shard['path']).resolve()): shard
                 for shard in index['shards'].values()}
        reads = []

        def load(path, paths=paths, forbidden=forbidden, eligible=eligible, reads=reads):
            shard = paths.get(str(Path(path).resolve()))
            if shard is None:
                raise ContractError('candidate search requested an unknown shard')
            visited = set(shard['unit_ids'])
            if visited & forbidden or not visited <= eligible:
                raise ContractError('excluded text shard requested in candidate search')
            # This check occurs BEFORE reading its bytes, not after filtering hits.
            reads.append(shard['path'])
            return read(Path(path))

        found = search_export(stage, index, _selection(config), 'symptom', load_shard=load,
                              current_review_revision=review['revision'])
        if len(reads) != len(found['loaded_shard_ids']):
            raise ContractError('candidate search read audit is inconsistent')
        checks[name] = {'symptom_chart_eligible': target_unit in eligible,
                        'eligible_count': len(eligible),
                        'loaded_shards': found['loaded_shard_ids'],
                        'actual_shard_reads': reads, 'wrong_vehicle_text_loaded': False}
    return checks


def run(b1, candidate, output):
    if output.exists():
        raise ContractError('candidate publication needs a new output directory')
    vocabulary, old_review = read(b1 / 'vocabulary.json'), read(b1 / 'review.json')
    pointer_before = (b1 / 'library' / 'current.json').read_bytes()
    review_before = (b1 / 'review.json').read_bytes()
    generation, _ = open_current(str(b1 / 'library'),
                                  current_review_revision=old_review['revision'])
    generation = Path(generation)
    packages = read(generation / 'library.json')['packages']
    old = [read(generation / 'evidence' / (p['source_id'] + '.json')) for p in packages]
    ford = next(s for s in old if s['source_id'] == FORD)
    after = read(candidate / 'candidate-evidence.json')
    package = next(p for p in packages if p['source_id'] == FORD)
    delta = compare(ford, after, read(generation / package['root'] / '.sme-manifest.json'),
                    vocabulary)
    recorded = read(candidate / 'scope-recapture.json')
    if any(recorded[k] != value for k, value in delta.items()):
        raise ContractError('candidate differs from its recapture report')
    updated = [after if s['source_id'] == FORD else s for s in old]
    history = {ford['revision']: ford}
    review = rebase(old_review, updated, vocabulary, history)
    if review['events'] != old_review['events']:
        raise ContractError('rebasing changed historical review events')
    stale = [event['id'] for event in review['events'] if review_event_is_stale(event, review)]
    if not stale or any(event['source_id'] != FORD for event in review['events']
                        if event['id'] in stale):
        raise ContractError('unexpected stale-review boundary')
    sources = [{'package': str(generation / package['root']), 'evidence': snapshot}
               for package, snapshot in zip(packages, updated)]
    checks = {}

    def check(stage):
        index = read(Path(stage) / 'search-index.json')
        checks.update(verify_scopes(stage, index, vocabulary, review,
                                    delta['target_unit_id'], updated))

    output.mkdir(parents=True)
    write_once(output / 'vocabulary.json', vocabulary)
    write_once(output / 'review.json', review)
    write_once(output / 'evidence-history.json', history)
    result = publish_library(str(output / 'library'), sources, vocabulary, review,
                             evidence_history=history, before_activate=check,
                             progress=lambda event: print(json.dumps(event), flush=True))
    if ((b1 / 'library' / 'current.json').read_bytes() != pointer_before or
            (b1 / 'review.json').read_bytes() != review_before):
        raise ContractError('baseline pointer/review changed during candidate publication')
    report = {'publication': result, 'fixture_checks': checks,
              'preserved_review_events': len(review['events']), 'stale_event_ids': stale,
              'review_events_added': 0, 'baseline_pointer_and_review_unchanged': True,
              'live_activation': False, 'diagnostic_ready': False}
    write_once(output / 'candidate-publication.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1, args.candidate, args.output), indent=2))
