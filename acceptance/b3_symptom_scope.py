"""Administrative evidence recapture, never selected diagnostic retrieval.

Recheck the immutable Ford package into a NEW local evidence snapshot. Existing
libraries/reviews are not edited, activated or approved. Full-source capture is an
administrative extraction operation, not permission to search excluded text.
"""

import argparse
import hashlib
import json
from pathlib import Path

from acceptance.b1_capture_evidence import read, write_once
from acceptance.b1_verify import _configs, _selection
from acceptance.b3_extract import FORD
from sme.applicability_contracts import validate_evidence, validate_review_overlay
from sme.contract import ContractError
from sme.evidence import capture_evidence
from sme.library_export import open_current
from sme.matching import match_unit

TARGET = 'originals/content/useni4/v3d/V3D3003.htm'


def compare(before, after, manifest, vocabulary):
    """Check administrative changes and fresh candidate scope without old approvals."""
    for snapshot in (before, after):
        validate_evidence(snapshot, manifest, vocabulary)
    for field in ('source_id', 'source_sha256', 'manifest_sha256', 'content_sha256',
                  'generation_sha256', 'vocabulary_revision'):
        if before[field] != after[field]:
            raise ContractError('scope comparison requires identical original generation')
    old = {u['id']: u for u in before['units']}
    new = {u['id']: u for u in after['units']}
    if old.keys() != new.keys() or before['assertions'] != after['assertions']:
        raise ContractError('scope recapture changed units or applicability statements')
    changes = []
    for identifier, unit in new.items():
        prior = old[identifier]
        if any(prior[k] != unit[k] for k in prior if k not in ('mixed_content', 'search')):
            raise ContractError('scope recapture unexpectedly changed source identity')
        if prior != unit:
            changes.append({'unit_id': identifier, 'citation': unit['citation'],
                            'before': {k: prior[k] for k in ('mixed_content', 'search')},
                            'after': {k: unit[k] for k in ('mixed_content', 'search')}})
    targets = [u for u in after['units'] if u['kind'] == 'section' and
               u['citation'] == {'kind': 'path', 'path': TARGET}]
    if len(targets) != 1:
        raise ContractError('symptom-chart metadata missing or ambiguous')
    target = targets[0]
    decisions = {}
    for name, config in _configs(vocabulary).items():
        decisions[name] = {
            'before': match_unit(before, manifest, vocabulary, target['id'],
                                 _selection(config), validate=False),
            'candidate': match_unit(after, manifest, vocabulary, target['id'],
                                    _selection(config), validate=False)}
    if decisions['diesel']['before']['reason_codes'] != ['mixed_content'] or \
            decisions['diesel']['candidate']['state'] != 'confirmed':
        raise ContractError('symptom-chart recapture did not resolve the expected false positive')
    if any(d['candidate']['search_eligible'] for name, d in decisions.items() if name != 'diesel'):
        raise ContractError('symptom-chart recapture broadened scope to another fixture')
    return {'contract': 'b3-symptom-scope-recapture/v1', 'source_id': after['source_id'],
            'before_revision': before['revision'], 'candidate_revision': after['revision'],
            'target_unit_id': target['id'], 'target_original_sha256': target['original_sha256'],
            'changed_units': changes, 'fixture_decisions': decisions,
            'review_events_added': 0, 'quality_approvals': 0, 'association_approvals': 0,
            'library_activated': False, 'diagnostic_ready': False}


def run(b1, output):
    vocabulary, review = read(b1 / 'vocabulary.json'), read(b1 / 'review.json')
    generation, _ = open_current(str(b1 / 'library'),
                                  current_review_revision=review['revision'])
    generation = Path(generation)
    library = read(generation / 'library.json')
    sources = [read(generation / 'evidence' / (p['source_id'] + '.json'))
               for p in library['packages'] if (generation / 'evidence' /
                                                (p['source_id'] + '.json')).exists()]
    validate_review_overlay(review, sources, vocabulary)
    before = next(s for s in sources if s['source_id'] == FORD)
    package = next(p for p in library['packages'] if p['source_id'] == FORD)
    root = (generation / package['root']).resolve(strict=True)
    if not root.is_relative_to(generation.resolve()):
        raise ContractError('package path escapes library generation')
    manifest = read(root / '.sme-manifest.json')
    # Rehash all originals; never bypass validation or mutate the old sidecar.
    after = capture_evidence(str(root), vocabulary)
    report = compare(before, after, manifest, vocabulary)
    report.update(review_revision=review['revision'],
                  old_review_reused=False,
                  capture_code_sha256=hashlib.sha256(
                      (Path(__file__).parents[1] / 'sme/evidence.py').read_bytes()).hexdigest())
    output.mkdir(parents=True, exist_ok=True)
    write_once(output / 'candidate-evidence.json', after)
    write_once(output / 'scope-recapture.json', report)
    return {k: v for k, v in report.items() if k not in ('changed_units', 'fixture_decisions')} | {
        'changed_unit_count': len(report['changed_units'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('b1', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.b1, args.output), indent=2))
