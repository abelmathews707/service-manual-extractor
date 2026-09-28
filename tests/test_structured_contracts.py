"""Authored B1 examples: original context, branches and independent approvals."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from test_applicability_contracts import make_evidence, make_manifest, make_vocabulary

from sme.applicability_contracts import POLICY_VERSION, digest
from sme.contract import ContractError
from sme.structured_contracts import (
    _schema,
    append_quality_event,
    diagnostic_admission,
    new_quality_overlay,
    quality_state,
    record_identity,
    save_quality_overlay,
    seal_records,
    validate_quality_overlay,
    validate_records,
)

CHECKS = dict.fromkeys(('original_compared', 'values_and_units', 'qualifiers',
                       'context_complete', 'branches_complete', 'source_resolves'), True)
TIMESTAMP = '2026-09-28T12:00:00+00:00'


def fixtures():
    vocabulary = make_vocabulary()
    evidence = make_evidence(make_manifest(), vocabulary)
    unit = evidence['units'][0]
    configuration = vocabulary['configurations'][0]['id']
    binding = {key: evidence[key] for key in ('source_id', 'source_sha256',
                                             'generation_sha256', 'content_sha256')}
    binding.update(evidence_revision=evidence['revision'], unit_id=unit['id'],
                   document_id=unit['document_id'], original_sha256=unit['original_sha256'],
                   citation=unit['citation'], provenance='native', extraction_version='authored-b1')

    def record(kind, label, payload):
        item = {'type': kind, 'binding': copy.deepcopy(binding),
                'locator': {'kind': 'text_quote', 'quote': label, 'prefix': '', 'suffix': ''},
                'original_text': label,
                'applicability': {'vocabulary_revision': vocabulary['revision'],
                                  'policy_version': POLICY_VERSION,
                                  'configuration_ids': [configuration]},
                'conditions': ['warmed idle'], 'context_record_ids': [],
                'completeness': {'state': 'complete', 'missing': []}, 'payload': payload}
        item['id'] = record_identity(item)
        return item

    warning = record('warning', 'Authored warning: stop if the test fixture leaks.',
                     {'severity': 'warning', 'instruction': 'Stop if the fixture leaks.'})
    tool = record('tool', 'Authored tool: example meter.',
                  {'name': 'Example meter', 'required_operation': 'Measure example signal'})
    specification = record('specification', 'Authored warmed-idle signal range: 2 to 4 V.',
                           {'subject': 'Example signal', 'quantity': 'voltage', 'values': [
                               {'condition': 'warmed idle', 'original_value': '2 to 4',
                                'original_unit': 'V',
                                'normalized': {'minimum': 2, 'maximum': 4, 'unit': 'V'}}]})
    specification['context_record_ids'] = [warning['id']]
    step = record('procedure_step', 'Authored step: connect the example meter.',
                  {'sequence': 1, 'instruction': 'Connect the example meter.',
                   'tool_ids': [tool['id']], 'next_record_ids': []})
    step['context_record_ids'] = [warning['id']]
    decision = record('diagnostic_node', 'Authored decision: is the example signal present?',
                      {'node_kind': 'decision', 'operation': 'Check example signal',
                       'expected_results': ['present', 'absent'],
                       'required_branch_labels': ['Yes', 'No']})
    yes = record('diagnostic_node', 'Authored terminal: example signal present.',
                 {'node_kind': 'outcome', 'operation': 'Record present',
                  'expected_results': [], 'required_branch_labels': []})
    no = record('diagnostic_node', 'Authored terminal: example signal absent.',
                {'node_kind': 'outcome', 'operation': 'Record absent',
                 'expected_results': [], 'required_branch_labels': []})
    edges = [record('diagnostic_edge', f'Authored {label} branch of the example decision.',
                    {'from_record_id': decision['id'], 'to_record_id': target['id'],
                     'label': label, 'condition': condition})
             for label, target, condition in [('Yes', yes, 'present'), ('No', no, 'absent')]]
    part = record('part_reference', 'Authored part mention: DEMO-123.',
                  {'identifier_original': 'DEMO-123', 'namespace': 'authored',
                   'relationship': 'mentioned'})
    region = record('region', 'Authored figure: example connector.',
                    {'kind': 'figure', 'caption_original': 'Example connector'})
    relationship = record('relationship', 'Authored reference to the example connector.',
                          {'relation': 'diagram_for', 'target_record_id': region['id'],
                           'condition': 'warmed idle'})
    bundle = seal_records([warning, tool, specification, step, decision, yes, no,
                           *edges, part, region, relationship])
    text = '\n'.join(item['original_text'] for item in bundle['records'])
    return vocabulary, evidence, bundle, {unit['id']: text}


class StructuredRecordTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.evidence, self.bundle, self.texts = fixtures()

    def validate(self, bundle=None, texts=None):
        return validate_records(bundle or self.bundle, self.vocabulary, [self.evidence],
                                source_texts=self.texts if texts is None else texts)

    def changed(self, kind, change):
        records = copy.deepcopy(self.bundle['records'])
        change(next(item for item in records if item['type'] == kind))
        return seal_records(records)

    def test_all_nine_typed_examples_validate_against_bound_source(self):
        self.assertIs(self.validate(), self.bundle)
        self.assertEqual(len({r['type'] for r in self.bundle['records']}), 9)

    def test_portable_schema_and_stdlib_shape_checker_agree(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('optional jsonschema is not installed')
        schema = _schema('structured-evidence-v1.schema.json')
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(self.bundle, schema)
        bad = self.changed('specification', lambda r: r['payload'].update(unknown=1))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
        with self.assertRaises(ContractError):
            self.validate(bad)

    def test_original_locator_hash_and_vocabulary_must_resolve(self):
        for kind, change in [
            ('specification', lambda r: r['binding'].update(original_sha256='f' * 64)),
            ('specification', lambda r: r['applicability'].update(vocabulary_revision='f' * 64)),
            ('region', lambda r: r['binding'].update(citation={'kind': 'path', 'path': '../bad'})),
        ]:
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                self.validate(self.changed(kind, change))

    def test_quote_must_be_original_and_unique(self):
        with self.assertRaises(ContractError):
            self.validate(texts={key: text * 2 for key, text in self.texts.items()})
        with self.assertRaises(ContractError):
            self.validate(texts=dict.fromkeys(self.texts, 'unrelated text'))

    def test_specification_cannot_lose_condition_reverse_range_or_use_nan(self):
        changes = [lambda r: r.update(conditions=[]),
                   lambda r: r['payload']['values'][0]['normalized'].update(minimum=5),
                   lambda r: r['payload']['values'][0]['normalized'].update(minimum=float('nan'))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.validate(self.changed('specification', change))

    def test_absent_numeric_value_is_not_zero(self):
        value = self.changed('specification',
                             lambda r: r['payload']['values'][0].pop('normalized'))
        self.validate(value)
        self.assertNotIn('normalized', next(r for r in value['records']
                                           if r['type'] == 'specification')['payload']['values'][0])

    def test_part_mention_does_not_establish_fit_or_supersession(self):
        for relation in ('fits', 'supersedes'):
            with self.subTest(relation=relation), self.assertRaises(ContractError):
                self.validate(self.changed('part_reference',
                                           lambda r, relation=relation: r['payload'].update(
                                               relationship=relation)))

    def test_complete_graph_cannot_drop_a_branch(self):
        records = [r for r in self.bundle['records']
                   if not (r['type'] == 'diagnostic_edge' and r['payload']['label'] == 'No')]
        with self.assertRaises(ContractError):
            self.validate(seal_records(records))
        decision = next(r for r in records if r['type'] == 'diagnostic_node')
        decision['completeness'] = {'state': 'incomplete', 'missing': ['No branch']}
        self.validate(seal_records(records))

    def test_dangling_targets_and_other_vehicle_context_are_rejected(self):
        with self.assertRaises(ContractError):
            self.validate(self.changed('relationship', lambda r: r['payload'].update(
                target_record_id='record_' + 'f' * 32)))
        with self.assertRaises(ContractError):
            self.validate(self.changed('warning', lambda r: r['applicability'].update(
                configuration_ids=[self.vocabulary['configurations'][1]['id']])))

    def test_pdf_region_must_match_page_and_not_have_inverted_coordinates(self):
        records = copy.deepcopy(self.bundle['records'])
        region = next(r for r in records if r['type'] == 'region')
        region['locator'] = {'kind': 'pdf_region', 'page': 2, 'bbox': [0, 0, 1, 1]}
        with self.assertRaises(ContractError):
            self.validate(seal_records(records))

    def test_every_type_rejects_absent_required_payload(self):
        for kind in {r['type'] for r in self.bundle['records']}:
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                self.validate(self.changed(kind, lambda r: r.update(payload={})))


class QualityReviewTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.evidence, self.bundle, self.texts = fixtures()
        self.records = self.bundle['records']
        self.record = next(r for r in self.records if r['type'] == 'specification')

    def event(self, overlay, action, *, records=None, kind='human', purpose='production',
              use='diagnostic_instruction', checks=None, prior=None):
        return append_quality_event(
            overlay, records or self.records, record_id=self.record['id'], action=action,
            intended_use=use, purpose=purpose,
            reviewer={'id': 'authored-test-reviewer', 'kind': kind},
            timestamp=TIMESTAMP, reason='Authored original compared independently',
            checks=CHECKS if checks is None else checks, prior_event_id=prior)

    def approved(self, **kwargs):
        overlay = self.event(new_quality_overlay(), 'propose', **kwargs)
        return self.event(overlay, 'approve', prior=overlay['events'][-1]['id'], **kwargs)

    def test_both_approvals_are_required_for_same_record_and_vehicle(self):
        overlay = self.approved()
        quality = quality_state(self.record['id'], self.records, overlay,
                                intended_use='diagnostic_instruction')
        configuration = self.record['applicability']['configuration_ids'][0]
        match = {'state': 'confirmed', 'unit_id': self.record['binding']['unit_id'],
                 'configuration_id': configuration}
        self.assertTrue(diagnostic_admission(self.record, configuration, match, quality))
        self.assertFalse(diagnostic_admission(self.record, configuration,
                                              {**match, 'state': 'possible'}, quality))
        self.assertFalse(diagnostic_admission(self.record, configuration, match,
                                              {'state': 'unreviewed', 'approved': False}))
        self.assertFalse(diagnostic_admission(self.record,
                                              self.vocabulary['configurations'][1]['id'],
                                              match, quality))
        self.assertFalse(diagnostic_admission(self.record, configuration, match,
                                              {**quality, 'record_id': 'record_' + 'f' * 32}))
        self.assertFalse(diagnostic_admission(self.record, configuration,
                                              {**match, 'configuration_id': 'wrong'}, quality))

    def test_agent_engineering_approval_is_not_production_signoff(self):
        overlay = self.approved(kind='agent', purpose='engineering')
        self.assertFalse(quality_state(self.record['id'], self.records, overlay,
                                       intended_use='diagnostic_instruction')['approved'])
        quality = quality_state(self.record['id'], self.records, overlay,
                                intended_use='diagnostic_instruction', purpose='engineering')
        configuration = self.record['applicability']['configuration_ids'][0]
        match = {'state': 'confirmed', 'unit_id': self.record['binding']['unit_id'],
                 'configuration_id': configuration}
        self.assertFalse(diagnostic_admission(self.record, configuration, match, quality))
        self.assertTrue(diagnostic_admission(self.record, configuration, match, quality,
                                             purpose='engineering'))
        with self.assertRaises(ContractError):
            self.approved(kind='agent')

    def test_missing_context_or_unchecked_original_cannot_be_approved(self):
        for field in CHECKS:
            with self.subTest(field=field), self.assertRaises(ContractError):
                self.approved(checks={**CHECKS, field: False})
        records = copy.deepcopy(self.records)
        warning = next(r for r in records if r['type'] == 'warning')
        warning['completeness'] = {'state': 'incomplete', 'missing': ['governing warning']}
        records = seal_records(records)['records']
        with self.assertRaises(ContractError):
            self.approved(records=records)

    def test_reference_approval_never_becomes_diagnostic_approval(self):
        overlay = self.approved(use='readable_reference')
        self.assertFalse(quality_state(self.record['id'], self.records, overlay,
                                       intended_use='diagnostic_instruction')['approved'])

    def test_changed_warning_invalidates_dependent_approval(self):
        overlay = self.approved()
        records = copy.deepcopy(self.records)
        next(r for r in records if r['type'] == 'warning')['payload']['instruction'] += ' Changed.'
        records = seal_records(records)['records']
        state = quality_state(self.record['id'], records, overlay,
                              intended_use='diagnostic_instruction', history=self.records)
        self.assertEqual(state['state'], 'stale')
        self.assertFalse(state['approved'])

    def test_revoke_reject_invalid_transition_and_backdated_review(self):
        overlay = self.approved()
        revoked = self.event(overlay, 'revoke', prior=overlay['events'][-1]['id'])
        self.assertEqual(quality_state(self.record['id'], self.records, revoked,
                                       intended_use='diagnostic_instruction')['state'], 'revoke')
        with self.assertRaises(ContractError):
            self.event(revoked, 'approve', prior=revoked['events'][-1]['id'])
        proposal = self.event(new_quality_overlay(), 'propose')
        rejected = self.event(proposal, 'reject', prior=proposal['events'][-1]['id'])
        self.assertFalse(quality_state(self.record['id'], self.records, rejected,
                                       intended_use='diagnostic_instruction')['approved'])
        with self.assertRaises(ContractError):
            append_quality_event(proposal, self.records, record_id=self.record['id'],
                                 action='approve', intended_use='diagnostic_instruction',
                                 purpose='production', reviewer={'id': 'test', 'kind': 'human'},
                                 timestamp='2026-09-27T12:00:00+00:00', reason='Backdated',
                                 checks=CHECKS, prior_event_id=proposal['events'][-1]['id'])

    def test_quality_log_has_portable_shape_and_cannot_drop_dependencies(self):
        overlay = self.approved()
        try:
            import jsonschema
        except ImportError:
            jsonschema = None
        if jsonschema:
            schema = _schema('structured-quality-review-v1.schema.json')
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.validate(overlay, schema)
        altered = copy.deepcopy(overlay)
        altered['events'][-1]['dependency_bindings'] = []
        altered['revision'] = digest({k: v for k, v in altered.items() if k != 'revision'})
        with self.assertRaises(ContractError):
            validate_quality_overlay(altered, self.records)

    def test_all_nine_types_withhold_ambiguous_context(self):
        kinds = {item['type'] for item in self.records}
        for kind in kinds:
            records = copy.deepcopy(self.records)
            record = next(item for item in records if item['type'] == kind)
            record['completeness'] = {'state': 'ambiguous', 'missing': ['authored lost context']}
            records = seal_records(records)['records']
            proposed = append_quality_event(
                new_quality_overlay(), records, record_id=record['id'], action='propose',
                intended_use='diagnostic_instruction', purpose='engineering',
                reviewer={'id': 'authored', 'kind': 'agent'}, timestamp=TIMESTAMP,
                reason='Ambiguous original requires abstention', checks=CHECKS)
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                append_quality_event(
                    proposed, records, record_id=record['id'], action='approve',
                    intended_use='diagnostic_instruction', purpose='engineering',
                    reviewer={'id': 'authored', 'kind': 'agent'}, timestamp=TIMESTAMP,
                    reason='Cannot approve incomplete context', checks=CHECKS,
                    prior_event_id=proposed['events'][-1]['id'])

    def test_quality_save_cannot_truncate_or_edit_history(self):
        overlay = self.approved()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'quality.json'
            save_quality_overlay(path, overlay, self.records)
            with self.assertRaises(ContractError):
                save_quality_overlay(path, new_quality_overlay(), self.records)
            self.assertEqual(json.loads(path.read_text()), overlay)
            revoked = self.event(overlay, 'revoke', prior=overlay['events'][-1]['id'])
            save_quality_overlay(path, revoked, self.records)
            self.assertEqual(json.loads(path.read_text()), revoked)


if __name__ == '__main__':
    unittest.main()
