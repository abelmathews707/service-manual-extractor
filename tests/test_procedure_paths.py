"""Manufacturer-neutral authored conditional references, not real manual text."""

import copy
import unittest
from unittest.mock import patch

from test_structured_contracts import CHECKS, TIMESTAMP, fixtures

from sme.contract import ContractError
from sme.procedure_paths import attach_source_paths
from sme.structured_contracts import (
    append_quality_event,
    dependency_bindings,
    new_quality_overlay,
    quality_state,
    seal_records,
    validate_records,
)


def path_fixture():
    vocabulary, evidence, initial, _ = fixtures()
    warning = next(r for r in initial['records'] if r['type'] == 'warning')
    tool = next(r for r in initial['records'] if r['type'] == 'tool')
    step = copy.deepcopy(next(r for r in initial['records'] if r['type'] == 'procedure_step'))
    wording = 'For switch A, use range 2. If the meter blinks, repeat step 2 twice.'
    step.update(original_text=wording,
                locator={'kind': 'text_quote', 'quote': wording, 'prefix': '', 'suffix': ''})
    step['payload']['instruction'] = wording
    target = copy.deepcopy(step)
    target.update(original_text='Record the reading.',
                  locator={'kind': 'text_quote', 'quote': 'Record the reading.',
                           'prefix': '', 'suffix': ''})
    target['payload'].update(instruction='Record the reading.', sequence=2)
    bundle = seal_records([warning, tool, step, target])
    step, target = bundle['records'][-2:]
    paths = [{'kind': 'alternative', 'source_record_id': step['id'],
              'quotation': 'For switch A, use range 2.', 'condition_original': 'For switch A',
              'instruction_original': 'use range 2.', 'target_record_ids': [step['id']],
              'unresolved_reason': ''},
             {'kind': 'repeat', 'source_record_id': step['id'],
              'quotation': 'If the meter blinks, repeat step 2 twice.',
              'condition_original': 'If the meter blinks',
              'instruction_original': 'repeat step 2 twice.',
              'target_record_ids': [target['id']], 'unresolved_reason': ''}]
    config = step['applicability']['configuration_ids'][0]
    decisions = {config: {'state': 'confirmed', 'configuration_id': config,
                          'unit_id': step['binding']['unit_id']}}
    return vocabulary, evidence, bundle, {step['id']: paths}, decisions


class ProcedurePathTests(unittest.TestCase):
    def setUp(self):
        self.vocab, self.evidence, self.bundle, self.recipes, self.decisions = path_fixture()

    def enriched(self):
        result = attach_source_paths(self.bundle, self.recipes, self.vocab, self.decisions)
        validate_records(result, self.vocab, [self.evidence], source_texts={
            self.bundle['records'][0]['binding']['unit_id']: ' '.join(
                r['original_text'] for r in self.bundle['records'])})
        return result

    def test_separate_quotes_and_targets_keep_full_wording_without_execution_edges(self):
        before = copy.deepcopy(self.bundle)
        value = self.enriched()
        self.assertEqual(before, self.bundle)
        step = value['records'][-2]
        self.assertEqual(step['payload']['source_paths'], self.recipes[step['id']])
        for original, current in zip(before['records'], value['records']):
            self.assertEqual(original['original_text'], current['original_text'])
            if current['type'] == 'procedure_step':
                self.assertEqual(current['completeness']['state'], 'incomplete')
                self.assertEqual(current['payload']['next_record_ids'], [])
        # A self-reference is bounded dependency data, not automatic execution.
        self.assertEqual(len(dependency_bindings(step['id'], value['records'])), 4)

    def test_unresolved_target_requires_reason_without_a_guessed_destination(self):
        path = next(iter(self.recipes.values()))[-1]
        path.update(target_record_ids=[], unresolved_reason='Interrupted step is not identified')
        self.enriched()
        path['unresolved_reason'] = ''
        with self.assertRaises(ContractError):
            self.enriched()
        path.update(target_record_ids=[self.bundle['records'][-1]['id']],
                    unresolved_reason='unknown')
        with self.assertRaises(ContractError):
            self.enriched()

    def test_changed_or_detached_quotes_and_duplicate_recipes_fail(self):
        original = copy.deepcopy(self.recipes)
        for change in ({'condition_original': 'Invented condition'},
                       {'instruction_original': 'use range 99.'}, {'quotation': 'range'},
                       {'source_record_id': self.bundle['records'][0]['id']}):
            self.recipes = copy.deepcopy(original)
            next(iter(self.recipes.values()))[0].update(change)
            with self.assertRaises(ContractError):
                self.enriched()
        self.recipes = copy.deepcopy(original)
        paths = next(iter(self.recipes.values()))
        paths.append(paths[0].copy())
        with self.assertRaises(ContractError):
            self.enriched()

    def test_missing_or_wrong_type_targets_fail(self):
        path = next(iter(self.recipes.values()))[-1]
        for target in ('record_' + 'f' * 32, self.bundle['records'][0]['id']):
            path['target_record_ids'] = [target]
            with self.assertRaises(ContractError):
                self.enriched()

    def test_semantic_validator_rejects_complete_or_linear_conditional_step(self):
        bundle = self.enriched()
        for update in ('complete', 'linear'):
            records = copy.deepcopy(bundle['records'])
            if update == 'complete':
                records[-2]['completeness'] = {'state': 'complete', 'missing': []}
            else:
                records[-2]['payload']['next_record_ids'] = [records[-1]['id']]
            with self.assertRaises(ContractError):
                validate_records(seal_records(records), self.vocab, [self.evidence])

    def test_target_change_stales_reference_review_and_incomplete_blocks_diagnostic_approval(self):
        bundle = self.enriched()
        step = bundle['records'][-2]
        quality = new_quality_overlay()
        arguments = {'record_id': step['id'], 'intended_use': 'readable_reference',
                     'purpose': 'engineering', 'reviewer': {'id': 'authored', 'kind': 'agent'},
                     'timestamp': TIMESTAMP, 'reason': 'Authored example only', 'checks': CHECKS}
        for action in ('propose', 'approve'):
            quality = append_quality_event(
                quality, bundle['records'], action=action, **arguments,
                prior_event_id=quality['events'][-1]['id'] if quality['events'] else None)
        changed = copy.deepcopy(bundle['records'])
        changed[-1]['conditions'].append('Authored new condition')
        self.assertEqual(quality_state(step['id'], seal_records(changed)['records'], quality,
                                       intended_use='readable_reference', purpose='engineering',
                                       history=bundle['records'])['state'], 'stale')
        arguments['intended_use'] = 'diagnostic_instruction'
        proposed = append_quality_event(new_quality_overlay(), bundle['records'], action='propose',
                                         **arguments)
        with self.assertRaises(ContractError):
            append_quality_event(proposed, bundle['records'], action='approve', **arguments,
                                 prior_event_id=proposed['events'][-1]['id'])

    def test_scope_and_ocr_fail_before_inspecting_recipe_text(self):
        cfg = next(iter(self.decisions))
        for reason in ('scope', 'ocr'):
            self.decisions[cfg]['state'] = 'excluded' if reason == 'scope' else 'confirmed'
            if reason == 'ocr':
                self.bundle['records'][0]['binding']['provenance'] = 'ocr'
            with patch('sme.procedure_paths._shape') as inspect:
                with self.assertRaises(ContractError):
                    attach_source_paths(self.bundle, self.recipes, self.vocab, self.decisions)
                inspect.assert_not_called()

    def test_target_wrong_vehicle_and_cross_unit_are_rejected(self):
        for field in ('vehicle', 'unit'):
            records = copy.deepcopy(self.bundle['records'])
            if field == 'vehicle':
                records[-1]['applicability']['configuration_ids'] = []
            else:
                records[-1]['binding']['unit_id'] = 'unit_' + 'a' * 32
            changed = seal_records(records)
            with self.assertRaises(ContractError):
                attach_source_paths(changed, self.recipes, self.vocab, self.decisions)

    def test_portable_schema_accepts_paths_and_rejects_extra_execution_fields(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('optional jsonschema is not installed')

        from sme.structured_contracts import _schema
        schema = _schema('structured-evidence-v1.schema.json')
        bundle = self.enriched()
        jsonschema.validate(bundle, schema)
        bundle['records'][-2]['payload']['source_paths'][0]['execute'] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bundle, schema)


if __name__ == '__main__':
    unittest.main()
