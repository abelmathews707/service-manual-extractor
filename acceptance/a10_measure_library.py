"""Measure a real immutable export without changing sources or reviews."""

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
from pathlib import Path
from time import perf_counter

from sme.library_export import SearchCancelled, open_current, search_export
from sme.source import MANIFEST_NAME


def read(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def measure(root, review, samples):
    generation, index = open_current(root, current_review_revision=review['revision'])
    folder = Path(generation)
    vocabulary = read(folder / 'vocabulary.json')
    library = read(folder / 'library.json')
    report = {'library_revision': index['library_revision'],
              'review_revision': review['revision'], 'samples': samples,
              'environment': {'system': platform.platform(),
                              'python': platform.python_version()},
              'packages': [], 'searches': []}
    for occurrence in library['packages']:
        package = folder / occurrence['root']
        manifest = read(package / MANIFEST_NAME)
        evidence = read(folder / 'evidence' / (occurrence['source_id'] + '.json'))
        docs = [doc for pub in manifest['publications'] for doc in pub['documents']]
        report['packages'].append({'source_id': occurrence['source_id'],
                                   'publications': len(manifest['publications']),
                                   'documents': len(docs),
                                   'asset_references': sum(len(doc['assets']) for doc in docs),
                                   'evidence_units': len(evidence['units']),
                                   'assertions': len(evidence['assertions'])})
    scopes = [({}, 'include_possible', True)]
    for config in vocabulary['configurations']:
        selection = {key: config[key] for key in
                     ('make_id', 'model_id', 'model_year', 'engine_id')}
        scopes.extend((selection, mode, False) for mode in
                      ('confirmed', 'include_possible'))
    for selection, mode, browse_all in scopes:
        timings = []
        loaded_bytes = 0

        def load(path):
            nonlocal loaded_bytes
            loaded_bytes += os.path.getsize(path)
            return read(path)

        for _ in range(samples):
            loaded_bytes = 0
            start = perf_counter()
            result = search_export(generation, index, selection, 'fuel', mode=mode,
                                   browse_all=browse_all, load_shard=load,
                                   current_review_revision=review['revision'])
            timings.append(perf_counter() - start)
        entry = index['scopes'][result['fingerprint']]
        report['searches'].append({'selection': selection, 'mode': mode,
                                   'browse_all': browse_all,
                                   'eligible': len(entry['scope']['eligible']),
                                   'loaded_shards': len(result['loaded_shard_ids']),
                                   'loaded_bytes_per_query': loaded_bytes,
                                   'results': len(result['results']),
                                   'median_seconds': statistics.median(timings),
                                   'p95_seconds': sorted(timings)[
                                       max(0, (95 * samples + 99) // 100 - 1)]})
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        return calls >= 3

    start = perf_counter()
    try:
        search_export(generation, index, {}, 'fuel', browse_all=True,
                      mode='include_possible',
                      cancelled=cancel, current_review_revision=review['revision'])
    except SearchCancelled:
        report['mid_shard_cancellation_seconds'] = perf_counter() - start
    else:
        raise AssertionError('broad query did not cancel between shards')
    report['max_process_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['generation_bytes'] = sum(path.stat().st_size for path in folder.rglob('*')
                                     if path.is_file())
    report['search_index_bytes'] = (folder / 'search-index.json').stat().st_size
    report['searchable_units'] = len({unit for shard in index['shards'].values()
                                      for unit in shard['unit_ids']})
    report['eligible_scope_rows'] = sum(len(item['scope']['eligible'])
                                        for item in index['scopes'].values())
    report['scopes'] = len(index['scopes'])
    report['shards'] = len(index['shards'])
    report['manifest_sha256'] = hashlib.sha256(
        (folder / 'library.json').read_bytes()).hexdigest()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    parser.add_argument('review')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 2 <= args.samples <= 100:
        parser.error('samples must be between 2 and 100')
    result = measure(args.library, read(args.review), args.samples)
    with open(args.output, 'x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
