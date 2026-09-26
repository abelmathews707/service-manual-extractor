"""A4 discovery and cautious source-evidence capture."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_applicability_contracts import make_vocabulary
from test_ford_adapter import _files
from test_formats import make_arc, make_v1_arc, payload
from test_sources import pdf_bytes

from sme.applicability_contracts import VOCABULARY_CONTRACT, digest, validate_evidence
from sme.contract import load_manifest
from sme.discovery import discover_folder
from sme.evidence import capture_evidence, write_evidence
from sme.ford_adapter import import_ford
from sme.normalize import normalize_source
from sme.ocr_selection import plan_ocr, run_toolkit_ocr
from sme.orchestrate import process_folder
from sme.source import SourceError, extract_source

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'html_manual')


def empty_vocabulary():
    value = {'contract': VOCABULARY_CONTRACT, 'makes': [], 'models': [],
             'engines': [], 'configurations': [], 'aliases': []}
    value['revision'] = digest(value)
    return value


class EvidenceCaptureTest(unittest.TestCase):
    def test_ford_svg_qualifier_is_bound_to_original_diagram(self):
        with tempfile.TemporaryDirectory() as root:
            disc = os.path.join(root, 'disc')
            directory = os.path.join(disc, 'content', 'useni4')
            os.makedirs(directory)
            files = {
                'ECO.EPL': b'<workunit><code>ECO</code><type>EVTM</type></workunit>',
                'ECOCELTTL.XML': (b'<root><cell><number>1</number>'
                                  b'<title>Starting</title></cell></root>'),
                'ECOCEL_001.XML': b'<root><page><num>1</num><file>ECO001001</file></page></root>',
                'ECO001001.XML': b'<root><page><title>Starting circuit</title></page></root>',
                'ECO001001.SVG': (b'<svg xmlns="http://www.w3.org/2000/svg">'
                                   b'<desc><Modelyear>2012</Modelyear>'
                                   b'<Modelname>F-SUPER DUTY</Modelname><QualifierList>'
                                   b'<Qualifier>6.2L Engine only</Qualifier></QualifierList>'
                                   b'</desc><rect width="10" height="10"/></svg>'),
            }
            Path(directory, 'ECO.arc').write_bytes(make_arc({name: payload(stored=[data])
                                                              for name, data in files.items()}))
            package = os.path.join(root, 'package')
            import_ford(disc, package, ['content/useni4/eco.arc'])
            evidence = capture_evidence(package, empty_vocabulary())
            qualifier = next(item for item in evidence['assertions']
                             if '6.2L Engine only' in item['statement'])
            self.assertTrue(qualifier['citation']['path'].endswith('ECO001001.SVG'))
            self.assertEqual(qualifier['intent'], 'include')
            self.assertEqual(qualifier['support'], 'proposal')

    @unittest.skipUnless(os.environ.get('RUN_REAL_OCR') == '1',
                         'set RUN_REAL_OCR=1 for the local toolkit integration gate')
    def test_toolkit_ocr_hash_bound_cache_roundtrip(self):
        import fitz

        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, 'scanned.pdf')
            raster = fitz.open()
            raster_page = raster.new_page(width=500, height=200)
            raster_page.insert_text((30, 110), 'FUEL SYSTEM', fontsize=38)
            image = raster_page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes('png')
            raster.close()
            document = fitz.open()
            page = document.new_page()
            page.insert_image(fitz.Rect(30, 30, 530, 230), stream=image)
            document.save(source)
            document.close()
            extracted = os.path.join(root, 'extracted')
            normalized = os.path.join(root, 'normalized')
            cache = os.path.join(root, 'cache')
            os.mkdir(cache)
            extract_source(source, extracted)
            normalize_source(extracted, normalized)
            path = plan_ocr(normalized)['publications'][0]['source_path']
            toolkit = os.environ['TOOLKIT_ROOT']
            result = run_toolkit_ocr(normalized, path, toolkit, cache)
            self.assertFalse(result['cached'])
            self.assertEqual(result['pages'], [1])
            self.assertTrue(os.path.isfile(result['ocr_map']))
            self.assertTrue(run_toolkit_ocr(normalized, path, toolkit, cache)['cached'])
            refreshed = os.path.join(root, 'refreshed-normalized')
            normalize_source(extracted, refreshed, ocr_manifest=result['ocr_map'])
            manifest = load_manifest(os.path.join(refreshed, '.sme-manifest.json'))
            self.assertEqual(manifest['publications'][0]['documents'][0]['text']['provenance'],
                             'ocr')

    def test_ocr_triage_separates_image_only_and_short_native_footer(self):
        try:
            import fitz
        except ImportError:
            self.skipTest('PyMuPDF is required for the authored image-page fixture')
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, 'image-page.pdf')
            pdf = fitz.open()
            page = pdf.new_page()
            image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), 0)
            image.clear_with(255)
            page.insert_image(fitz.Rect(50, 50, 300, 300), stream=image.tobytes('png'))
            page = pdf.new_page()
            page.insert_image(fitz.Rect(50, 50, 300, 300), stream=image.tobytes('png'))
            page.insert_text((50, 350), 'Footer')
            pdf.save(source)
            pdf.close()
            extracted = os.path.join(root, 'extracted')
            normalized = os.path.join(root, 'normalized')
            extract_source(source, extracted)
            normalize_source(extracted, normalized)
            plan = plan_ocr(normalized)
            item = plan['publications'][0]
            self.assertEqual(item['auto_pages'], [1])
            self.assertEqual(item['review_pages'], [2])
            self.assertEqual(item['pages'][1]['state'], 'review_low_text_with_image')

    def test_mixed_folder_routes_and_counts_unsupported(self):
        with tempfile.TemporaryDirectory() as root:
            disc = os.path.join(root, 'ford-disc')
            directory = os.path.join(disc, 'content', 'useni4')
            os.makedirs(directory)
            Path(directory, 'SAA.arc').write_bytes(make_arc(dict(_files())))
            Path(directory, 'SBB.arc').write_bytes(make_v1_arc(_files('SBB')))
            shutil.copytree(FIXTURE, os.path.join(root, 'html-manual'))
            Path(root, 'article.pdf').write_bytes(pdf_bytes(('manual title',)))
            Path(root, 'notes.txt').write_text('not a manual')
            found = discover_folder(root)
            by_name = {item['name']: item for item in found['sources']}
            self.assertEqual(by_name['ford-disc']['route'], 'ford-import')
            self.assertEqual(by_name['html-manual']['route'], 'extract')
            self.assertEqual(by_name['article.pdf']['format'], 'pdf_collection_v1')
            self.assertEqual(by_name['notes.txt']['status'], 'unsupported')
            self.assertEqual(found['counts']['recognized'], 3)
            self.assertEqual(found['counts']['unsupported'], 1)
            output = os.path.join(os.path.dirname(root), os.path.basename(root) + '-processed')
            try:
                with self.assertRaisesRegex(SourceError, 'non-Ford child'):
                    process_folder(root, output, include_names=['html-manual'],
                                   ford_archives={'html-manual': ['content/useni4/saa.arc']})
                first = process_folder(root, output,
                                       include_names=['ford-disc', 'html-manual',
                                                      'article.pdf', 'notes.txt'])
                produced = [package for item in first['results']
                            for package in item['packages']]
                self.assertEqual(len(produced), 4)
                self.assertTrue(all(not item['cached'] for item in produced))
                second = process_folder(root, output)
                cached = [package for item in second['results']
                          for package in item['packages']]
                self.assertEqual(len(cached), 4)
                self.assertTrue(all(item['cached'] for item in cached))
                self.assertEqual(second['unsupported'], ['notes.txt'])
                previous_html = next(item['path'] for row in second['results']
                                     if row['name'] == 'html-manual'
                                     for item in row['packages'])
                html_page = Path(root, 'html-manual', 'pages', '100.html')
                html_page.write_bytes(html_page.read_bytes().replace(
                    b'</body>', b'<p>Changed edition</p></body>'))
                third = process_folder(root, output, include_names=['html-manual'])
                new_html = third['results'][0]['packages'][0]
                self.assertFalse(new_html['cached'])
                self.assertNotEqual(new_html['path'], previous_html)
                self.assertTrue(os.path.isdir(previous_html))
            finally:
                if os.path.isdir(output):
                    shutil.rmtree(output)

    def test_html_pdf_and_ford_emit_same_unconfirmed_evidence_contract(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = empty_vocabulary()
            html_source = os.path.join(root, 'html-source')
            shutil.copytree(FIXTURE, html_source)
            page = Path(html_source, 'pages', '100.html')
            page.write_text(page.read_text().replace('</body>',
                            '<p>6.0L diesel only; except 8.1L gasoline.</p></body>'))
            html_extract = os.path.join(root, 'html-extract')
            html_package = os.path.join(root, 'html-package')
            extract_source(html_source, html_extract)
            normalize_source(html_extract, html_package)

            pdf_source = os.path.join(root, '2007 folder name.pdf')
            Path(pdf_source).write_bytes(pdf_bytes(('2006 Chevrolet Silverado 1500',)))
            pdf_extract = os.path.join(root, 'pdf-extract')
            pdf_package = os.path.join(root, 'pdf-package')
            extract_source(pdf_source, pdf_extract)
            normalize_source(pdf_extract, pdf_package)

            disc = os.path.join(root, 'disc')
            directory = os.path.join(disc, 'content', 'useni4')
            os.makedirs(directory)
            Path(directory, 'SAA.arc').write_bytes(make_arc(dict(_files())))
            ford_package = os.path.join(root, 'ford-package')
            import_ford(disc, ford_package, ['content/useni4/saa.arc'])

            for package in (html_package, pdf_package, ford_package):
                with self.subTest(package=package):
                    evidence = capture_evidence(package, vocabulary)
                    manifest = load_manifest(os.path.join(package, '.sme-manifest.json'))
                    validate_evidence(evidence, manifest, vocabulary)
                    self.assertTrue(evidence['units'])
                    self.assertTrue(evidence['assertions'])
                    self.assertTrue(all(item['support'] == 'proposal'
                                        for item in evidence['assertions']))
                    self.assertTrue(all(item['alternatives'][0]['engine'] ==
                                        {'state': 'unknown'}
                                        for item in evidence['assertions']))
            html_evidence = capture_evidence(html_package, vocabulary)
            self.assertTrue(any(unit['mixed_content'] and
                                unit['search']['state'] == 'metadata_only'
                                for unit in html_evidence['units']))
            pdf_evidence = capture_evidence(pdf_package, vocabulary)
            self.assertFalse(any(item['subject_id'] == load_manifest(
                os.path.join(pdf_package, '.sme-manifest.json'))['publications'][0]['id']
                and item['applies_to_descendants'] for item in pdf_evidence['assertions']))

            mapped = make_vocabulary()
            ford_mapped = capture_evidence(ford_package, mapped)
            self.assertTrue(any(item['derivation'] == 'explicit_structured' and
                                item['support'] == 'source_supported' and
                                item['alternatives'][0]['model']['state'] == 'exact'
                                for item in ford_mapped['assertions']))
            pdf_mapped = capture_evidence(pdf_package, mapped)
            self.assertTrue(any(item['derivation'] == 'title_hint' and
                                item['support'] == 'proposal' and
                                item['alternatives'][0]['model']['state'] == 'exact'
                                for item in pdf_mapped['assertions']))

            vocabulary_path = os.path.join(root, 'vocabulary.json')
            Path(vocabulary_path).write_text(json.dumps(vocabulary))
            destination = os.path.join(root, 'evidence.json')
            first = write_evidence(ford_package, vocabulary_path, destination)
            self.assertFalse(first['cached'])
            self.assertTrue(write_evidence(ford_package, vocabulary_path,
                                           destination)['cached'])
            original = Path(html_package, 'pages', '100.html')
            original.write_bytes(original.read_bytes() + b'changed')
            with self.assertRaisesRegex(SourceError, 'original package member changed'):
                capture_evidence(html_package, vocabulary)


if __name__ == '__main__':
    unittest.main()
