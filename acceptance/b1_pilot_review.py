"""Exact agent-reviewed B1 reading scopes; never production diagnostic approval.

These source revisions are deliberately frozen after original page inspection.
Different evidence must be reviewed again. No book-wide acceptance is created.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from acceptance.a10_pilot_review import ENGINE_PATH, GM_SOURCE, WIRING_PATH, _diagram_pair, _one
from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_pilot_vocabulary import FORD_SOURCE, V10_HEADING, V10_PATH
from sme.applicability_contracts import validate_vocabulary
from sme.review import decide, new_overlay, propose

EXPECTED = {
    FORD_SOURCE: '7cb03804658a4f80771eef4835abcfc26a3265992bc1ac852b3fe5434ddea7b3',
    GM_SOURCE: '9020f279b12936a6565ce336e5bafc31c22f3a7cc6e391ebc6e082f521da23b5',
}


def build_review(sources, vocabulary):
    validate_vocabulary(vocabulary)
    by_source = {item['source_id']: item for item in sources}
    if any(by_source.get(identifier, {}).get('revision') != revision
           for identifier, revision in EXPECTED.items()):
        raise ValueError('B1 evidence changed; inspect original pages again')
    engines = {item['name']: item['id'] for item in vocabulary['engines']}
    configs = {(item['model_year'], item['engine_id']): item['id']
               for item in vocabulary['configurations']}
    ford = by_source[FORD_SOURCE]
    unit = _one([item for item in ford['units'] if item['citation'] ==
                 {'kind': 'path', 'path': V10_PATH} and item['kind'] == 'section'],
                'V10 reference-values page')
    if unit['original_sha256'] != (
            '20f3a62c0efb61105d18f9af9d8c51a60c9a8f77a993651a9314830cd7e33442'):
        raise ValueError('V10 original changed')
    heading = _one([item for item in ford['assertions']
                    if item['subject_id'] == unit['id'] and item['statement'] == V10_HEADING
                    and item['provenance'] == 'native' and item.get('selector') == 'heading'],
                   'native V10 heading')
    catalog = _one([item for item in ford['assertions']
                    if item['statement'] == '2003 F-250 All Gasoline Engines'
                    and item['derivation'] == 'explicit_structured'
                    and item['citation']['path'] == 'originals/content/useni4/v32/V32.epl'],
                   'original V32 vehicle entry')
    requests = [(FORD_SOURCE, unit['id'], [heading['id'], catalog['id']],
                 configs[(2003, engines['6.8L V10'])],
                 'Original V32 catalog identifies 2003 F-250 gasoline coverage; the native '
                 'page heading limits this exact page to 6.8L E/F-Series automatic. '
                 'Workshop identification codes distinguish VIN S gasoline V10 from VIN Z '
                 'CNG and list 4R100 codes. Owner-declared 4WD/4R100 is not a decoded VIN. '
                 'Reading applicability only: no complete no-start procedure or quality approval.')]
    gm = by_source[GM_SOURCE]
    for path, page, caption_page, year, label, engine in (
            (WIRING_PATH, 2, 3, 2006, '4.3L VIN X', '4.3L VIN X'),
            (WIRING_PATH, 10, 11, 2006, '4.8L VIN V', '4.8L VIN V'),
            (ENGINE_PATH, 87, 87, 2002, '4.3L VIN W & X', '4.3L VIN W')):
        subject, bindings = _diagram_pair(gm, path, page, caption_page,
                                          f'{year} Chevrolet Silverado 1500', label)
        requests.append((GM_SOURCE, subject, bindings, configs[(year, engines[engine])],
                         f'Original PDF {path}, pages {page}/{caption_page}, visually checked '
                         f'for {year} Chevrolet Silverado 1500 and {label}. Exact page only; '
                         'not a complete circuit/procedure, quality approval '
                         'or production signoff.'))
    review = new_overlay(sources, vocabulary)
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for source, subject, bindings, config, reason in requests:
        reason = 'Disposable B1 agent engineering review. ' + reason
        review = propose(review, sources, vocabulary, source_id=source, subject_id=subject,
                         relation='section_applies', target_configuration_ids=[config],
                         evidence_ids=bindings, reviewer='codex-b1-agent-pilot',
                         timestamp=timestamp, reason=reason)
        review = decide(review, sources, vocabulary, prior_event_id=review['events'][-1]['id'],
                        action='accept', reviewer='codex-b1-agent-pilot',
                        timestamp=timestamp, reason=reason)
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acceptance_root', type=Path)
    args = parser.parse_args()
    sources = [read(path) for path in sorted((args.acceptance_root / 'evidence').glob('*.json'))]
    vocabulary = read(args.acceptance_root / 'vocabulary.json')
    write_once(args.acceptance_root / 'review.json', build_review(sources, vocabulary))


if __name__ == '__main__':
    main()
