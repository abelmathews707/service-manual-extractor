"""Behavioral gates for structure, citations, provenance and verified publication."""
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_sources import pdf_bytes, write_file

from sme import cli
from sme.contract import validate_manifest
from sme.html_content import local_url, parse_html, safe_svg
from sme.normalize import CONTENT_NAME, digest, normalize_source, validate_content
from sme.pdf_content import pdf_text_pages, title_and_kind
from sme.source import INVENTORY_NAME, MANIFEST_NAME, SourceError, extract_source, inspect_source

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'html_manual')


def read_json(folder, name):
    with open(os.path.join(folder, name), encoding='utf-8') as stream:
        return json.load(stream)


class PdfClassificationTests(unittest.TestCase):
    def test_owner_manual_requires_an_owner_document_phrase(self):
        _, kind = title_and_kind(
            "2004 Chevrolet Silverado Owner Manual M\nSeats and Restraints"
        )
        self.assertEqual(kind, "owner")

    def test_plural_owners_guide_inside_first_page_is_owner_material(self):
        _, kind = title_and_kind(
            "Table of Contents\nIntroduction 4\n2003 F250/350/450/550 (f23)\n"
            "Owners Guide (post-2002-fmt)\nUSA English (fus)"
        )
        self.assertEqual(kind, "owner")

    def test_service_warning_and_manual_system_reference_are_not_owner_information(self):
        _, kind = title_and_kind(
            """2002 Chevrolet Silverado 1500
            2002 HEATER SYSTEMS Sierra & Silverado
            Obtain radio anti-theft protection code from owner prior to servicing.
            See the article in MANUAL A/C-HEATER SYSTEMS."""
        )
        self.assertEqual(kind, "unknown")


class HtmlMeaningTests(unittest.TestCase):
    def test_inline_spacing_survives_in_structured_content(self):
        parsed = parse_html(b'<body><h1>Test</h1><p><b>Turn</b> <b>OFF</b></p></body>',
                            'pages/1.html')
        paragraph = next(node for node in parsed['structure'] if node['tag'] == 'p')
        self.assertEqual(paragraph['children'][1], ' ')
        self.assertIn('Turn OFF', parsed['text'])

    def test_main_content_and_parent_dtc_survive_without_shell_noise(self):
        parsed = parse_html(b'''<html><body><div class="header">
          <b class="branding">Advertisement</b><a class="breadcrumb-part">DTC B1017</a>
          </div><main class="main"><h1>Circuit Description</h1><p>Check connector.</p>
          <script>alert('bad')</script></main><footer>Footer ad</footer></body></html>''',
                            'pages/1.html')
        self.assertEqual(parsed['breadcrumbs'], ['DTC B1017'])
        self.assertEqual(parsed['text'], 'Circuit Description\nCheck connector.')
        self.assertNotIn('alert', json.dumps(parsed['structure']))

    def test_merged_table_cells_and_qualifiers_stay_in_structure(self):
        parsed = parse_html(b'''<body><h1>Check</h1><table><tr><th colspan="2">Action</th>
          <th>Yes</th><th>No</th></tr><tr><td rowspan="2">1</td><td>6.6L only</td>
          <td>Step 2</td><td>Stop</td></tr></table></body>''', 'pages/1.html')
        table = next(node for node in parsed['structure'] if node['tag'] == 'table')
        self.assertEqual(table['children'][0]['children'][0]['attrs']['colspan'], 2)
        self.assertEqual(table['children'][1]['children'][0]['attrs']['rowspan'], 2)
        self.assertTrue(any(e['level'] == 'table' and e['statement'] == '6.6L only'
                            for e in parsed['applicability']))

    def test_navigation_folder_without_href_keeps_hierarchy_and_routes(self):
        parsed = parse_html(b'''<body><h1>Repair</h1><ul><li class="li-folder">
          <a name="engine">Engine</a><ul><li><a href="one.html">Test</a></li>
          <li><a href="one.html">Alias</a></li></ul></li></ul></body>''', 'pages/tree.html')
        self.assertEqual(parsed['role'], 'navigation')
        self.assertEqual(parsed['text'], '')
        self.assertIn('engine', parsed['anchors'])
        self.assertIn(['Engine', 'Test'], [r['labels'] for r in parsed['navigation']])

    def test_captions_attach_to_next_image_and_keep_variant(self):
        parsed = parse_html(b'''<body><h1>Figures</h1><div class="imageHeader">
          <span class="imageCaption">6.0L CNG circuit</span></div><div class="imageHolder">
          <img src="../images/one.svg"></div><div class="imageHeader">
          <span class="imageCaption">Diesel connector</span></div>
          <img src="../images/two.png"></body>''', 'pages/1.html')
        self.assertEqual([f['caption'] for f in parsed['figures']],
                         ['6.0L CNG circuit', 'Diesel connector'])
        self.assertTrue(any(e['level'] == 'figure' for e in parsed['applicability']))

    def test_links_normalize_relative_escaped_and_windows_paths(self):
        for href in ('../pages/a%20b.html#DTC%20B1017', '..\\pages\\a%20b.html#DTC%20B1017'):
            self.assertEqual(local_url('pages/1.html', href),
                             ('pages/a b.html', 'DTC B1017', None))
        self.assertEqual(local_url('pages/1.html', '#step'), ('pages/1.html', 'step', None))
        for href in ('../../escape', '%2e%2e/%2e%2e/escape', 'https://example.com',
                     'javascript:alert(1)', '//host/path', 'C:/file', '/root', '%00bad'):
            self.assertIsNotNone(local_url('pages/1.html', href)[2], href)

    def test_encoding_and_missing_heading_are_explicit(self):
        parsed = parse_html(b'<meta charset="windows-1252"><p>\x93Check\x94</p>', 'p.html')
        self.assertIn('\u201cCheck\u201d', parsed['text'])
        self.assertTrue(any(w.startswith('missing_body') for w in parsed['warnings']))
        self.assertEqual(parsed['title'], 'p.html')
        for data in (b'<meta charset="UTF-7">bad', b'<body>\xff</body>'):
            with self.assertRaises(SourceError):
                parse_html(data, 'p.html')

    def test_large_flat_navigation_is_not_recursive_in_siblings(self):
        data = ('<body><ul>' + ''.join(f'<li><a href="{i}.html">{i}</a>'
                                     for i in range(5000)) + '</ul></body>').encode()
        parsed = parse_html(data, 'pages/tree.html')
        self.assertEqual(len(parsed['references']), 5000)
        self.assertEqual(parsed['role'], 'navigation')


class SvgPolicyTests(unittest.TestCase):
    def test_static_geometry_is_retained_and_metadata_removed(self):
        result = safe_svg(b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
          <metadata><vendor>https://unused.example</vendor></metadata>
          <path d="M0 0 L10 10" style="stroke:black;fill:none"/></svg>''')
        self.assertIn(b'M0 0 L10 10', result)
        self.assertNotIn(b'http://unused', result)
        self.assertNotIn(b'metadata', result)

    def test_active_external_and_unreviewed_features_are_blocked(self):
        for body in ('<script>alert(1)</script>', '<foreignObject/>',
                     '<image href="https://example.com/p.png"/>',
                     '<path onclick="bad()"/>', '<path fill="url(https://example.com)"/>',
                     '<path style="filter:blur(1px)"/>', '<path fill="url(#missing)"/>'):
            with self.subTest(body=body), self.assertRaises(SourceError):
                safe_svg(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>'.encode())
        with self.assertRaises(SourceError):
            safe_svg(b'<!DOCTYPE svg [<!ENTITY a "x">]><svg xmlns="http://www.w3.org/2000/svg"/>')


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.source = os.path.join(self.root, 'source')
        self.extracted = os.path.join(self.root, 'extracted')
        self.output = os.path.join(self.root, 'normalized')
        shutil.copytree(FIXTURES, self.source)

    def run_html(self):
        extract_source(self.source, self.extracted)
        result = normalize_source(self.extracted, self.output)
        manifest = read_json(self.output, MANIFEST_NAME)
        content = read_json(self.output, CONTENT_NAME)
        validate_manifest(manifest)
        validate_content(content, manifest)
        return result, manifest, content

    def test_fixture_end_to_end_retains_separate_variant_citations_and_assets(self):
        result, manifest, content = self.run_html()
        self.assertTrue(result['ok'])
        docs = {d['path']: d for d in manifest['publications'][0]['documents']}
        self.assertNotEqual(docs['pages/3738.html']['id'], docs['pages/6193.html']['id'])
        self.assertIn('6.6L', docs['pages/3738.html']['applicability'][0]['statement'])
        self.assertIn('8.1L', docs['pages/6193.html']['applicability'][0]['statement'])
        records = {r['original_path']: r for r in content['documents']}
        self.assertFalse(records['index.html']['search_eligible'])
        self.assertFalse(records['external-car.html']['search_eligible'])
        figures = records['pages/100.html']['figures']
        self.assertEqual(figures[0]['status'], 'safe_svg')
        self.assertTrue(os.path.isfile(os.path.join(self.output, figures[0]['render_path'])))
        self.assertEqual(figures[1]['status'], 'unsupported')
        self.assertEqual(read_json(self.output, INVENTORY_NAME),
                         read_json(self.extracted, INVENTORY_NAME))

    def test_links_distinguish_missing_fragment_omission_and_external(self):
        write_file(self.source, 'pages/refs.html', b'''<body><h1>Links</h1><a id="here"></a>
          <a href="#here">self</a><a href="#absent">bad fragment</a>
          <a href="../external-car.html">other car</a><a href="missing.html">missing</a>
          <a href="https://example.com/api">external</a></body>''')
        _, _, content = self.run_html()
        record = next(r for r in content['documents'] if r['original_path'] == 'pages/refs.html')
        self.assertEqual([r['status'] for r in record['references']],
                         ['resolved', 'missing', 'unavailable_by_source', 'missing', 'blocked'])

    def test_exporter_encoded_anchor_names_retain_exact_target(self):
        write_file(self.source, 'pages/encoded.html', b'''<body><h1>Anchors</h1>
          <a name="DTC%20B1017/"></a><a href="#DTC%20B1017/">Diagnosis</a></body>''')
        _, _, content = self.run_html()
        record = next(r for r in content['documents'] if r['original_path'] == 'pages/encoded.html')
        self.assertEqual(record['references'][0]['status'], 'resolved')
        self.assertEqual(record['references'][0]['target_fragment'], 'DTC%20B1017/')

    def test_identical_text_different_breadcrumbs_does_not_become_context_alias(self):
        for name, engine in (('one', 'Diesel'), ('two', 'Gasoline')):
            write_file(self.source, f'pages/{name}.html', f'''<body><div class="header">
              <a class="breadcrumb-part">{engine}</a></div><div class="main">
              <h1>Test</h1><p>Check circuit.</p></div></body>'''.encode())
        _, _, content = self.run_html()
        record = next(r for r in content['documents'] if r['original_path'] == 'pages/one.html')
        self.assertEqual(len(record['same_text_ids']), 1)
        self.assertEqual(record['context_alias_ids'], [])

    def test_changed_file_fails_without_publishing_or_mutating_source(self):
        extract_source(self.source, self.extracted)
        write_file(self.extracted, 'images/fuel-routing.svg', b'changed')
        with self.assertRaisesRegex(SourceError, 'hash/size changed'):
            normalize_source(self.extracted, self.output)
        self.assertFalse(os.path.exists(self.output))
        self.assertFalse(any('.normalized.sme-' in p for p in os.listdir(self.root)))

    def test_partial_input_and_existing_output_are_refused(self):
        extract_source(self.source, self.extracted)
        os.makedirs(self.output)
        with self.assertRaisesRegex(SourceError, 'fresh'):
            normalize_source(self.extracted, self.output)
        manifest = read_json(self.extracted, MANIFEST_NAME)
        manifest['source'].update(
            status='partial', failures=[{'code': 'damage', 'message': 'test'}])
        with patch('sme.normalize._json', side_effect=[manifest,
                   read_json(self.extracted, INVENTORY_NAME)]):
            with self.assertRaisesRegex(SourceError, 'partial source'):
                normalize_source(self.extracted, os.path.join(self.root, 'other'))

    def test_parse_failure_is_partial_and_other_documents_survive(self):
        write_file(self.source, 'pages/bad.html', b'<meta charset="unknown">broken')
        result, manifest, content = self.run_html()
        self.assertFalse(result['ok'])
        self.assertEqual(content['status'], 'partial')
        self.assertEqual(content['failures'][0]['path'], 'pages/bad.html')
        self.assertEqual(manifest['source']['status'], 'complete')
        self.assertGreater(result['documents'], 0)

    def test_interruption_cleans_staging(self):
        extract_source(self.source, self.extracted)
        with patch('sme.normalize._html_publication', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                normalize_source(self.extracted, self.output)
        self.assertFalse(os.path.exists(self.output))
        self.assertFalse(any('.normalized.sme-' in p for p in os.listdir(self.root)))

    def test_content_tampering_is_detected(self):
        _, manifest, content = self.run_html()
        modified = copy.deepcopy(content)
        next(r for r in modified['documents'] if r['search_eligible'])['text'] = 'wrong'
        with self.assertRaisesRegex(SourceError, 'text hash'):
            validate_content(modified, manifest)

    def test_unsafe_structure_is_rejected_by_content_validator(self):
        _, manifest, content = self.run_html()
        content['documents'][0]['structure'] = [
            {'tag': 'script', 'attrs': {}, 'children': ['bad()']}]
        with self.assertRaisesRegex(SourceError, 'unsafe content structure'):
            validate_content(content, manifest)

    def test_full_inventory_classifies_outside_selection(self):
        multiple = os.path.join(self.root, 'multiple')
        shutil.copytree(self.source, os.path.join(multiple, 'one'))
        shutil.copytree(self.source, os.path.join(multiple, 'two'))
        write_file(multiple, 'one/pages/cross.html',
                   b'<body><h1>Cross</h1><a href="../../two/pages/100.html">Other</a></body>')
        source = inspect_source(multiple)
        chosen = next(pub.id for pub in source.publications if pub.root == 'one')
        full = os.path.join(self.root, 'full')
        extract_source(multiple, full)
        extract_source(multiple, self.extracted, [chosen])
        normalize_source(self.extracted, self.output,
                         source_inventory=os.path.join(full, INVENTORY_NAME))
        content = read_json(self.output, CONTENT_NAME)
        cross = next(r for r in content['documents']
                     if r['original_path'] == 'one/pages/cross.html')
        self.assertEqual(cross['references'][0]['status'], 'outside_selection')

    def test_missing_and_active_figures_never_get_render_paths(self):
        write_file(self.source, 'images/active.svg',
                   b'<svg xmlns="http://www.w3.org/2000/svg"><script>bad()</script></svg>')
        write_file(self.source, 'pages/bad-images.html', b'''<body><h1>Images</h1>
          <img src="../images/absent.png"><img src="../images/active.svg"></body>''')
        result, _, content = self.run_html()
        figures = next(r['figures'] for r in content['documents']
                       if r['original_path'] == 'pages/bad-images.html')
        self.assertEqual([f['status'] for f in figures], ['missing', 'unsupported'])
        self.assertTrue(all('render_path' not in f for f in figures))
        self.assertGreaterEqual(result['unavailable_figures'], 2)

    def test_published_content_satisfies_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('jsonschema is an optional development dependency')
        _, _, content = self.run_html()
        schema = read_json(os.path.join(os.path.dirname(FIXTURES), '..', '..', 'schemas'),
                           'service-manual-content-v1.schema.json')
        jsonschema.Draft202012Validator(schema).validate(content)

    def test_cli_normalize_json_and_exit(self):
        extract_source(self.source, self.extracted)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = cli.main(['normalize', self.extracted, '-o', self.output, '--json'])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(stdout.getvalue())['ok'])


class PdfPageTests(unittest.TestCase):
    def normalize_pdf(self, native, ocr_pages=None, bad_hash=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = temporary.name
        source = write_file(root, 'source/manual.pdf', pdf_bytes(('native', '')))
        extracted, output = os.path.join(root, 'extracted'), os.path.join(root, 'output')
        extract_source(source, extracted)
        mapping_path = None
        if ocr_pages is not None:
            derived = pdf_bytes(('native', 'derived scan text'))
            write_file(root, 'derived.pdf', derived)
            member = read_json(extracted, INVENTORY_NAME)['members'][0]
            mapping = {'contract': 'service-manual-ocr-map/v1', 'entries': [{
                'source_path': 'manual.pdf', 'source_sha256': member['sha256'],
                'derived_path': 'derived.pdf', 'derived_sha256': '0' * 64 if bad_hash else
                digest(derived), 'page_count': 2, 'tool': {'name': 'test-ocr', 'version': '1'},
            }]}
            mapping_path = write_file(root, 'ocr.json', json.dumps(mapping).encode())
        with patch('sme.normalize.pdf_text_pages', return_value=(native, [])), patch(
                'sme.pdf_content.pdf_text_pages', return_value=(ocr_pages, [])):
            result = normalize_source(extracted, output, mapping_path)
        return result, read_json(output, MANIFEST_NAME), read_json(output, CONTENT_NAME)

    def test_mixed_native_ocr_pages_retain_original_citations(self):
        result, manifest, content = self.normalize_pdf(
            ['2006 Example truck\nEngine test', ''], ['ignored replacement', '6.6L diesel scan'])
        self.assertTrue(result['ok'])
        docs = manifest['publications'][0]['documents']
        self.assertEqual([d['text']['provenance'] for d in docs], ['native', 'ocr'])
        self.assertEqual(docs[1]['citations'], [{'kind': 'page', 'path': 'manual.pdf', 'page': 2}])
        self.assertEqual(docs[1]['text']['derived_from_sha256'], docs[1]['content_sha256'])
        self.assertIn('2006 Example', content['documents'][0]['text'])
        self.assertNotEqual(docs[0]['id'], docs[1]['id'])
        validate_manifest(manifest)
        validate_content(content, manifest)

    def test_image_only_page_without_ocr_is_unsearchable_but_cited(self):
        result, manifest, content = self.normalize_pdf(['Title', ''])
        self.assertTrue(result['ok'])
        self.assertEqual(manifest['publications'][0]['documents'][1]['text'],
                         {'provenance': 'none'})
        self.assertFalse(content['documents'][1]['search_eligible'])
        self.assertEqual(content['documents'][1]['figures'][0]['page'], 2)

    def test_wrong_ocr_hash_cannot_publish_searchable_pages(self):
        result, _, content = self.normalize_pdf(['native', ''], ['native', 'scan'], bad_hash=True)
        self.assertFalse(result['ok'])
        self.assertEqual(content['documents'], [])
        self.assertIn('hash', content['failures'][0]['message'])

    @unittest.skipUnless(shutil.which('pdfinfo') and shutil.which('pdftotext'),
                         'Poppler integration requires pdfinfo and pdftotext')
    def test_real_poppler_retains_blank_page_boundaries(self):
        with tempfile.TemporaryDirectory() as root:
            path = write_file(root, 'pages.pdf', pdf_bytes(('first', '', 'third')))
            pages, _ = pdf_text_pages(path, 3)
            self.assertEqual(pages, ['first', '', 'third'])
            with self.assertRaises(SourceError):
                pdf_text_pages(path, 2)


if __name__ == '__main__':
    unittest.main()
