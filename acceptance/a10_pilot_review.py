"""Record three exact, agent-checked GM PDF sections for a disposable A10 pilot.

This review is not a production or owner approval. The source/evidence revisions,
page pairs and wording are intentionally pinned; changed input must be reviewed
again rather than silently inheriting these decisions.
"""

import argparse
import json
from datetime import datetime, timezone

from sme.applicability_contracts import validate_vocabulary
from sme.review import decide, new_overlay, propose, save_overlay

GM_SOURCE = 'src_241ae321543b966629942d2b1977d6eb'
GM_EVIDENCE_REVISION = '74cf95d517e58f677c87b92b1156741e83874f7f6d77d883d10e9e389c4eed84'
WIRING_PATH = '2006 - 2007/wiring engine.pdf'
ENGINE_PATH = '1998-2007/ENGINE PERFORMANCE.pdf'


def _one(items, description):
    if len(items) != 1:
        raise ValueError(f'{description}: expected one exact source record; got {len(items)}')
    return items[0]


def _diagram_pair(evidence, path, page, caption_page, model_header, engine_label):
    unit = _one([item for item in evidence['units']
                 if item['citation'] == {'kind': 'page', 'path': path, 'page': page}
                 and item['kind'] == 'region' and item['search']['state'] == 'whole'],
                f'page {page} searchable region')
    model = _one([item for item in evidence['assertions']
                  if item['citation'] == unit['citation'] and
                  item['statement'] == model_header and
                  item['support'] == 'source_supported'], f'page {page} vehicle header')
    caption = _one([item for item in evidence['assertions']
                    if item['citation'] == {'kind': 'page', 'path': path,
                                            'page': caption_page} and
                    item['statement'].startswith('Fig. ') and
                    engine_label in item['statement'] and
                    item['support'] == 'source_supported'],
                   f'page {caption_page} {engine_label} caption')
    return unit['id'], [model['id'], caption['id']]


def build_pilot_review(ford_evidence, gm_evidence, vocabulary):
    validate_vocabulary(vocabulary)
    if gm_evidence['source_id'] != GM_SOURCE or gm_evidence['revision'] != GM_EVIDENCE_REVISION:
        raise ValueError('GM evidence changed; inspect the original pages again')
    sources = [ford_evidence, gm_evidence]
    review = new_overlay(sources, vocabulary)
    configurations = {(item['model_year'], item['engine_id']): item['id']
                      for item in vocabulary['configurations']}
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for path, page, caption_page, year, label, engine_name in (
            (WIRING_PATH, 2, 3, 2006, '4.3L VIN X', '4.3L VIN X'),
            (WIRING_PATH, 10, 11, 2006, '4.8L VIN V', '4.8L VIN V'),
            (ENGINE_PATH, 87, 87, 2002, '4.3L VIN W & X', '4.3L VIN W')):
        subject, evidence_ids = _diagram_pair(
            gm_evidence, path, page, caption_page,
            f'{year} Chevrolet Silverado 1500', label)
        engine = _one([item for item in vocabulary['engines']
                       if item['name'] == engine_name], engine_name)
        reason = (f'Disposable A10 agent review: original PDF {path} page {page} '
                  f'contains the diagram/procedure and page {caption_page} names '
                  f'it as {label}; the header identifies {year} Chevrolet Silverado 1500. '
                  'No adjacent page or entire publication is approved.')
        review = propose(review, sources, vocabulary, source_id=GM_SOURCE,
                         subject_id=subject, relation='section_applies',
                         target_configuration_ids=[configurations[(year, engine['id'])]],
                         evidence_ids=evidence_ids, reviewer='codex-a10-agent-pilot',
                         timestamp=timestamp, reason=reason)
        review = decide(review, sources, vocabulary,
                        prior_event_id=review['events'][-1]['id'], action='accept',
                        reviewer='codex-a10-agent-pilot',
                        timestamp=timestamp,
                        reason=reason)
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ford_evidence')
    parser.add_argument('gm_evidence')
    parser.add_argument('vocabulary')
    parser.add_argument('output')
    args = parser.parse_args()
    with open(args.ford_evidence, encoding='utf-8') as stream:
        ford = json.load(stream)
    with open(args.gm_evidence, encoding='utf-8') as stream:
        gm = json.load(stream)
    with open(args.vocabulary, encoding='utf-8') as stream:
        vocabulary = json.load(stream)
    review = build_pilot_review(ford, gm, vocabulary)
    save_overlay(args.output, review, [ford, gm], vocabulary)
    print(json.dumps({'output': args.output, 'revision': review['revision'],
                      'events': len(review['events'])}, indent=2))


if __name__ == '__main__':
    main()
