"""An accepted PDF diagram review may use only its paired original caption."""

import unittest

from sme.matching import _adjacent_pdf_review_fills_missing


class AdjacentPdfReviewTests(unittest.TestCase):
    def setUp(self):
        self.unit = {'id': 'unit_test', 'kind': 'region',
                     'citation': {'kind': 'page', 'path': 'wiring.pdf', 'page': 2}}
        self.selection = {'engine_id': 'engine_43'}
        self.assertion = {
            'id': 'ev_caption', 'intent': 'include', 'support': 'source_supported',
            'provenance': 'native',
            'citation': {'kind': 'page', 'path': 'wiring.pdf', 'page': 3},
            'alternatives': [{
                'make': {'state': 'unknown'}, 'model': {'state': 'unknown'},
                'year': {'state': 'unknown'},
                'engine': {'state': 'exact', 'value': 'engine_43'},
                'qualifiers': {},
            }],
        }
        self.review = {'events': [{'id': 'review_accept', 'subject_id': 'unit_test',
                                   'evidence_bindings': [{'id': 'ev_caption'}]}]}

    def fills(self):
        return _adjacent_pdf_review_fills_missing(
            self.review, {'assertions': [self.assertion]}, ['review_accept'],
            self.unit, self.selection, ['engine'])

    def test_exact_next_page_native_caption_can_fill_reviewed_engine(self):
        self.assertTrue(self.fills())

    def test_other_page_file_engine_or_unaccepted_review_cannot_fill(self):
        self.assertion['citation']['page'] = 4
        self.assertFalse(self.fills())
        self.assertion['citation']['page'] = 3
        self.assertion['citation']['path'] = 'another.pdf'
        self.assertFalse(self.fills())
        self.assertion['citation']['path'] = 'wiring.pdf'
        self.assertion['alternatives'][0]['engine']['value'] = 'engine_48'
        self.assertFalse(self.fills())
        self.assertion['alternatives'][0]['engine']['value'] = 'engine_43'
        self.review['events'][0]['id'] = 'review_stale'
        self.assertFalse(self.fills())

    def test_ocr_proposal_and_non_pdf_are_not_engine_proof(self):
        self.assertion['provenance'] = 'ocr'
        self.assertFalse(self.fills())
        self.assertion['provenance'] = 'native'
        self.assertion['support'] = 'proposal'
        self.assertFalse(self.fills())
        self.assertion['support'] = 'source_supported'
        self.unit['kind'] = 'section'
        self.assertFalse(self.fills())


if __name__ == '__main__':
    unittest.main()
