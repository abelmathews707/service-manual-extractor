"""Executable Step 2 contract and compatibility tests.

All examples are authored for this repository. No vendor manual content or
local source path is required.
"""
import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from fsd import cli as ford_cli
from fsd.disc import DiscError
from fsd.probe import as_json
from sme import cli as neutral_cli
from sme.contract import (
    FORMATS,
    MANIFEST_CONTRACT,
    OPERATION_CONTRACT,
    ContractError,
    asset_id,
    canonical_path,
    document_id,
    publication_id,
    source_id,
    validate_manifest,
    validate_operation,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'tests', 'fixtures', 'html_manual')
ZERO = '0' * 64
ONE = '1' * 64
TWO = '2' * 64
THREE = '3' * 64


def source_record(format_, container, identity, digest, status='complete', failures=None):
    return {
        'id': source_id(format_, container, identity, digest),
        'format': format_,
        'container': container,
        'identity': identity,
        'sha256': digest,
        'status': status,
        'failures': failures or [],
        'extractor': {
            'name': 'service-manual-extractor',
            'version': '0.1.0',
            'revision': 'synthetic-step-2',
        },
    }


def applicability(level, statement, path, selector=None):
    value = {'level': level, 'statement': statement, 'source_path': path}
    if selector:
        value['selector'] = selector
    return value


def document(publication, path, title, digest, statement, citation=None, **changes):
    value = {
        'id': document_id(publication, path),
        'path': path,
        'title': title,
        'breadcrumbs': ['Example manual', title],
        'content_sha256': digest,
        'text': {'provenance': 'native', 'sha256': digest},
        'citations': [citation or {'kind': 'path', 'path': path}],
        'applicability': [applicability('document', statement, path, '.qualifier')],
        'references': [],
        'assets': [],
    }
    value.update(changes)
    return value


def publication(source, path, title, kind, documents, statement='Synthetic example only'):
    identity = publication_id(source['id'], path)
    return {
        'id': identity,
        'source_path': path,
        'title': title,
        'kind': kind,
        'applicability': [applicability('publication', statement, path)],
        'documents': documents(identity),
    }


def html_manifest():
    failure = {
        'code': 'missing_member',
        'message': 'A linked diagnostic page is absent from the source.',
        'path': 'pages/missing.html',
    }
    source = source_record(
        'workshop_manuals_html_v1', 'directory', 'synthetic/html-manual', ZERO,
        'partial', [failure],
    )

    def documents(publication_identity):
        shared = hashlib.sha256(
            b'Check the example circuit and repair an open connection.'
        ).hexdigest()
        diesel = document(
            publication_identity, 'pages/3738.html', 'Shared circuit test', shared,
            '6.6L diesel vehicles only.',
        )
        gasoline = document(
            publication_identity, 'pages/6193.html', 'Shared circuit test', shared,
            '8.1L gasoline vehicles only.',
        )
        fuel = document(
            publication_identity, 'pages/100.html', 'Fuel pressure test', ONE,
            'Example 1500 4.3L vehicles only.',
        )
        asset_path = 'images/fuel-routing.svg'
        fuel['assets'].append({
            'id': asset_id(fuel['id'], asset_path),
            'path': asset_path,
            'sha256': TWO,
            'media_type': 'image/svg+xml',
            'caption': 'Fuel supply routing',
        })
        raster_path = 'images/pressure-map.pbm'
        fuel['assets'].append({
            'id': asset_id(fuel['id'], raster_path),
            'path': raster_path,
            'sha256': THREE,
            'media_type': 'image/x-portable-bitmap',
            'caption': 'Example pressure map',
        })
        fuel['references'].append({
            'path': 'pages/missing.html',
            'status': 'missing',
            'reason': 'Linked file is absent from the source.',
        })
        leaf = document(
            publication_identity, 'pages/1066.html', 'Circuit description', THREE,
            'Diagnostic code B1017 parent context.',
        )
        leaf['breadcrumbs'] = ['Example manual', 'B1017', 'Circuit description']
        placeholder = document(
            publication_identity, 'external-car.html', 'Content not included', ZERO,
            'Another example vehicle.',
        )
        placeholder['references'].append({
            'path': 'external-source/index.html',
            'status': 'unavailable_by_source',
            'reason': 'The publisher intentionally omitted this vehicle.',
        })
        return [fuel, diesel, gasoline, leaf, placeholder]

    return {
        'contract': MANIFEST_CONTRACT,
        'source': source,
        'publications': [publication(
            source, 'index.html', 'Example Workshop Information', 'workshop', documents,
            '2006 Example 2500 — 6.6L diesel',
        )],
    }


def make_pdf(pages):
    """Generate a tiny valid PDF without adding a PDF file to the repository."""
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        f'<< /Type /Pages /Kids [{" ".join(f"{4 + i * 2} 0 R" for i in range(len(pages)))}] '
        f'/Count {len(pages)} >>'.encode(),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    for index, text in enumerate(pages):
        page_number = 4 + index * 2
        stream_number = page_number + 1
        stream = f'BT /F1 12 Tf 36 756 Td ({text}) Tj ET'.encode()
        objects.extend([
            (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
             f'/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_number} 0 R >>').encode(),
            b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
        ])
    data = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f'{number} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = len(data)
    data.extend(f'xref\n0 {len(objects) + 1}\n'.encode())
    data.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
        f'startxref\n{xref}\n%%EOF\n'.encode()
    )
    return bytes(data)


def pdf_manifest(pdf_bytes):
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    source = source_record('pdf_collection_v1', 'file_collection',
                           'synthetic/pdf-collection', digest)

    def documents(publication_identity):
        first = document(
            publication_identity, 'example.pdf/pages/1', 'Native text page', ONE,
            '2002 Example 1500',
            citation={'kind': 'page', 'path': 'example.pdf', 'page': 1},
        )
        second = document(
            publication_identity, 'example.pdf/pages/2', 'Scanned page', TWO,
            '2002 Example 1500',
            citation={'kind': 'page', 'path': 'example.pdf', 'page': 2},
            text={
                'provenance': 'ocr',
                'sha256': THREE,
                'derived_from_sha256': TWO,
                'tool': {'name': 'synthetic-ocr', 'version': '1'},
            },
        )
        return [first, second]

    return {
        'contract': MANIFEST_CONTRACT,
        'source': source,
        'publications': [publication(
            source, 'example.pdf', 'Example PDF Service Article', 'reference', documents,
            '2002 Example 1500',
        )],
    }


def ford_manifest(version):
    digest = str(version) * 64
    source = source_record(f'ford_tsp_disc_v{version}', 'disc',
                           f'synthetic/ford-v{version}', digest)

    def documents(publication_identity):
        return [document(
            publication_identity, 'SLB/SLB100.HTM', 'Synthetic Ford procedure', ONE,
            '2020 Example vehicle',
        )]

    return {
        'contract': MANIFEST_CONTRACT,
        'source': source,
        'publications': [publication(
            source, 'CONTENT/SLB.ARC', 'Synthetic Ford workshop manual',
            'workshop', documents, '2020 Example vehicle',
        )],
    }


class TestNeutralManifest(unittest.TestCase):
    def test_committed_json_schema_matches_the_python_contract_vocabulary(self):
        path = os.path.join(ROOT, 'schemas', 'service-manual-manifest-v1.schema.json')
        with open(path, encoding='utf-8') as file:
            schema = json.load(file)
        declared = schema['$defs']['source']['properties']['format']['enum']
        self.assertEqual(declared, list(FORMATS))
        self.assertEqual(schema['properties']['contract']['const'], MANIFEST_CONTRACT)
        path = os.path.join(ROOT, 'schemas', 'service-manual-operation-v1.schema.json')
        with open(path, encoding='utf-8') as file:
            operation_schema = json.load(file)
        self.assertEqual(operation_schema['properties']['contract']['const'],
                         OPERATION_CONTRACT)
        self.assertEqual(operation_schema['properties']['operation']['enum'],
                         ['probe', 'extract'])

    def test_authored_html_fixture_and_manifest(self):
        expected = [
            'index.html', 'pages/100.html', 'pages/1066.html', 'pages/3738.html',
            'pages/6193.html', 'external-car.html', 'images/fuel-routing.svg',
            'images/pressure-map.pbm',
        ]
        for relative in expected:
            self.assertTrue(os.path.isfile(os.path.join(HTML, *relative.split('/'))))
        value = validate_manifest(html_manifest())
        documents = value['publications'][0]['documents']
        repeated = [item for item in documents if item['title'] == 'Shared circuit test']
        self.assertEqual(repeated[0]['content_sha256'], repeated[1]['content_sha256'])
        self.assertNotEqual(repeated[0]['id'], repeated[1]['id'])
        self.assertNotEqual(repeated[0]['applicability'], repeated[1]['applicability'])
        self.assertNotEqual(repeated[0]['citations'], repeated[1]['citations'])

    def test_generated_pdf_records_native_and_ocr_text_separately(self):
        pdf = make_pdf(['Native example text', 'Scanned example page'])
        self.assertTrue(pdf.startswith(b'%PDF-1.4'))
        self.assertEqual(pdf.count(b'/Type /Page '), 2)
        value = validate_manifest(pdf_manifest(pdf))
        documents = value['publications'][0]['documents']
        self.assertEqual([item['text']['provenance'] for item in documents],
                         ['native', 'ocr'])
        self.assertEqual([item['citations'][0]['page'] for item in documents], [1, 2])

    def test_synthetic_ford_v1_and_v2_fit_the_neutral_contract(self):
        for version in (1, 2):
            with self.subTest(version=version):
                validate_manifest(ford_manifest(version))

    def test_unsupported_format_cannot_claim_a_valid_manifest(self):
        value = html_manifest()
        value['source']['format'] = 'unknown_html'
        with self.assertRaisesRegex(ContractError, 'unsupported format'):
            validate_manifest(value)

    def test_partial_source_requires_a_precise_failure(self):
        value = html_manifest()
        value['source']['failures'] = []
        with self.assertRaisesRegex(ContractError, 'must explain'):
            validate_manifest(value)

    def test_failed_source_cannot_publish_documents(self):
        value = html_manifest()
        value['source']['status'] = 'failed'
        with self.assertRaisesRegex(ContractError, 'empty for a failed source'):
            validate_manifest(value)

    def test_resolved_reference_must_name_a_document_in_the_manifest(self):
        value = html_manifest()
        value['publications'][0]['documents'][0]['references'] = [{
            'path': 'pages/unknown.html',
            'status': 'resolved',
            'target_id': 'doc_' + 'f' * 32,
        }]
        with self.assertRaisesRegex(ContractError, 'not present'):
            validate_manifest(value)

    def test_ocr_cannot_relabel_original_bytes(self):
        value = pdf_manifest(make_pdf(['one', 'two']))
        text = value['publications'][0]['documents'][1]['text']
        text['derived_from_sha256'] = ZERO
        with self.assertRaisesRegex(ContractError, 'original document bytes'):
            validate_manifest(value)

    def test_paths_are_portable_and_source_relative(self):
        self.assertEqual(canonical_path(r'pages\100.html'), 'pages/100.html')
        for bad in ('../secret', '/absolute', r'C:\manuals\one.html', '//server/share'):
            with self.subTest(path=bad), self.assertRaises(ContractError):
                canonical_path(bad)

    def test_operation_envelopes_distinguish_probe_and_extract(self):
        manifest = ford_manifest(1)
        source = manifest['source']
        publication_record = manifest['publications'][0]
        summary = {key: publication_record[key]
                   for key in ('id', 'source_path', 'title', 'kind')}
        probe = {
            'contract': OPERATION_CONTRACT,
            'operation': 'probe',
            'ok': True,
            'source': source,
            'publications': [summary],
            'output': None,
            'diagnostics': [],
        }
        validate_operation(probe)
        extract = dict(probe, operation='extract', output={
            'manifest_path': 'manifest.json', 'files_written': 2, 'bytes_written': 42,
        })
        validate_operation(extract)


class TestNeutralCli(unittest.TestCase):
    def test_contract_discovery_is_machine_readable_and_has_no_readers_yet(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = neutral_cli.main(['contract', '--json'])
        self.assertEqual(code, 0)
        value = json.loads(output.getvalue())
        self.assertEqual(value['manifest_contract'], MANIFEST_CONTRACT)
        self.assertEqual(value['neutral_readers'], [])
        self.assertEqual(value['legacy_entry_points'], ['python3 -m fsd'])

    def test_validate_manifest_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'manifest.json')
            with open(path, 'w', encoding='utf-8') as file:
                json.dump(html_manifest(), file)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(neutral_cli.main(['validate-manifest', path]), 0)
            with open(path, 'w', encoding='utf-8') as file:
                json.dump({'contract': 'wrong'}, file)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(neutral_cli.main(['validate-manifest', path]), 1)


class _ContextSource:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class TestFordCompatibilityFreeze(unittest.TestCase):
    def setUp(self):
        self.info = {
            'label': 'TEST',
            'source': 'directory',
            'origin': '/synthetic/TEST',
            'deep': False,
            'archives': [],
            'warnings': ['No .ARC archives found.'],
            'ok': False,
        }

    def test_existing_probe_json_shape_and_format_are_unchanged(self):
        expected = (\
            '{\n'
            '  "label": "TEST",\n'
            '  "source": "directory",\n'
            '  "origin": "/synthetic/TEST",\n'
            '  "deep": false,\n'
            '  "archives": [],\n'
            '  "warnings": [\n'
            '    "No .ARC archives found."\n'
            '  ],\n'
            '  "ok": false\n'
            '}'
        )
        self.assertEqual(as_json(self.info), expected)

    def test_existing_probe_exit_codes_remain_zero_one_and_two(self):
        for ok, expected in ((True, 0), (False, 1)):
            value = dict(self.info, ok=ok)
            with mock.patch('fsd.cli.open_source', return_value=_ContextSource()), \
                    mock.patch('fsd.probe.probe', return_value=value), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ford_cli.main(['probe', 'synthetic', '--json']), expected)
        with mock.patch('fsd.cli.open_source', side_effect=DiscError('unreadable')), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ford_cli.main(['probe', 'synthetic']), 2)

    def test_existing_command_names_are_unchanged(self):
        parser = ford_cli.make_parser()
        action = next(action for action in parser._actions
                      if getattr(action, 'choices', None))
        self.assertEqual(list(action.choices),
                         ['probe', 'extract', 'build', 'all', 'serve', 'iso'])


if __name__ == '__main__':
    unittest.main()
