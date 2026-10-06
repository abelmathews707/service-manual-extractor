"""Check vehicle boundaries and measured search on one disposable A10 export."""

import argparse
import json
import statistics
from time import perf_counter

from sme.contract import ContractError
from sme.library_export import SearchCancelled, open_current, search_export

WIRING = '2006 - 2007/wiring engine.pdf'
ENGINE = '1998-2007/ENGINE PERFORMANCE.pdf'
CABIN = '1998-2007/CABIN AIR FILTER.pdf'


def _read(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _unit(evidence, path, page):
    found = [item['id'] for item in evidence['units']
             if item['citation'] == {'kind': 'page', 'path': path, 'page': page}]
    if len(found) != 1:
        raise AssertionError(f'expected one cited unit: {path} page {page}')
    return found[0]


def _select(config):
    return {key: config[key] for key in
            ('make_id', 'model_id', 'model_year', 'engine_id')}


def verify(root, vocabulary, review, ford, gm):
    generation, index = open_current(root, current_review_revision=review['revision'])
    configurations = {(item['model_year'], item['engine_id']): item
                      for item in vocabulary['configurations']}
    engines = {item['name']: item['id'] for item in vocabulary['engines']}
    ford_scope = _select(configurations[(2003, engines['6.0L Power Stroke diesel'])])
    gm_w_scope = _select(configurations[(2002, engines['4.3L VIN W'])])
    gm_x_scope = _select(configurations[(2006, engines['4.3L VIN X'])])
    gm_v_scope = _select(configurations[(2006, engines['4.8L VIN V'])])
    mixed = _unit(gm, WIRING, 9)
    ford_sets = ford if isinstance(ford, list) else [ford]
    ford_ids = {item['id'] for source in ford_sets for item in source['units']}
    gm_ids = {item['id'] for item in gm['units']}
    cases = (
        ('ford', ford_scope, 'fuel', ford_ids, set()),
        ('gm_2002_vin_w', gm_w_scope, 'injector', gm_ids,
         {_unit(gm, ENGINE, 87)}),
        ('gm_2006_vin_x', gm_x_scope, 'Chevrolet', gm_ids,
         {_unit(gm, WIRING, 2)}),
        ('gm_2006_vin_v', gm_v_scope, 'Chevrolet', gm_ids,
         {_unit(gm, WIRING, 10)}),
    )
    report = {'library_revision': index['library_revision'],
              'review_revision': review['revision'], 'cases': {}}
    for name, selection, query, allowed, required in cases:
        started = perf_counter()
        result = search_export(generation, index, selection, query,
                               current_review_revision=review['revision'])
        elapsed = perf_counter() - started
        entry = index['scopes'][result['fingerprint']]
        eligible = {item['unit_id'] for item in entry['scope']['eligible']}
        if not eligible.issubset(allowed) or not required.issubset(eligible):
            raise AssertionError(f'{name}: wrong-source or missing required membership')
        if mixed in eligible or (name == 'ford' and eligible & gm_ids):
            raise AssertionError(f'{name}: wrong-engine or cross-make text entered scope')
        if not required.issubset({item['unit_id'] for item in result['results']}):
            raise AssertionError(f'{name}: reviewed section missing from query results')
        for shard_id in result['loaded_shard_ids']:
            if not set(index['shards'][shard_id]['unit_ids']).issubset(allowed):
                raise AssertionError(f'{name}: loaded a wrong-source text shard')
        report['cases'][name] = {'eligible': len(eligible),
                                 'results': len(result['results']),
                                 'loaded_shards': len(result['loaded_shard_ids']),
                                 'cold_search_seconds': elapsed}
    reference_ids = {item['id'] for item in gm['units']
                     if item['citation']['path'] == 'GENERIC TROUBLE CODES.pdf'}
    reference = search_export(generation, index, gm_w_scope, 'code',
                              include_reference=True,
                              current_review_revision=review['revision'])
    selected = {item['unit_id'] for item in index['scopes'][
        reference['fingerprint']]['scope']['eligible']}
    if not selected & reference_ids:
        raise AssertionError('opted-in generic reference is unavailable')
    report['reference_eligible'] = len(selected & reference_ids)
    cabin = _unit(gm, CABIN, 1)
    possible = search_export(generation, index, gm_w_scope, 'CABIN AIR FILTER',
                             mode='include_possible',
                             current_review_revision=review['revision'])
    possible_rows = {item['unit_id']: item for item in
                     index['scopes'][possible['fingerprint']]['scope']['eligible']}
    if (cabin not in {item['unit_id'] for item in possible['results']} or
            possible_rows[cabin]['state'] != 'possible' or
            'missing_engine' not in possible_rows[cabin]['reason_codes']):
        raise AssertionError('OCR cabin-filter page lost its possible-only state')
    confirmed = search_export(generation, index, gm_w_scope, 'CABIN AIR FILTER',
                              current_review_revision=review['revision'])
    later_year = search_export(generation, index, gm_x_scope, 'CABIN AIR FILTER',
                               mode='include_possible',
                               current_review_revision=review['revision'])
    if (cabin in {item['unit_id'] for item in confirmed['results']} or
            cabin in {item['unit_id'] for item in later_year['results']}):
        raise AssertionError('OCR cabin-filter page leaked into confirmed/later-year search')
    report['ocr_cabin_filter'] = 'possible for 2002; withheld for 2006 and confirmed mode'
    try:
        search_export(generation, index, ford_scope, 'fuel', cancelled=lambda: True,
                      current_review_revision=review['revision'])
    except SearchCancelled:
        report['cancellation'] = 'passed'
    else:
        raise AssertionError('cancelled query still ran')
    try:
        open_current(root, current_review_revision='0' * 64)
    except ContractError:
        report['stale_review_rejected'] = True
    else:
        raise AssertionError('stale review opened the export')
    samples = []
    for _ in range(30):
        started = perf_counter()
        search_export(generation, index, gm_w_scope, 'injector',
                      current_review_revision=review['revision'])
        samples.append(perf_counter() - started)
    report['warm_gm_2002_p95_seconds'] = sorted(samples)[28]
    report['warm_gm_2002_median_seconds'] = statistics.median(samples)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    parser.add_argument('vocabulary')
    parser.add_argument('review')
    parser.add_argument('ford_evidence')
    parser.add_argument('gm_evidence')
    parser.add_argument('--extra-ford-evidence', action='append', default=[])
    parser.add_argument('--output')
    args = parser.parse_args()
    ford = [_read(args.ford_evidence)] + [_read(path) for path in args.extra_ford_evidence]
    result = verify(args.library, _read(args.vocabulary), _read(args.review),
                    ford, _read(args.gm_evidence))
    if args.output:
        with open(args.output, 'x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
