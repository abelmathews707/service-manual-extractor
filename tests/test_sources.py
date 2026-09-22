"""Step 3 source-container safety and repeatability tests."""
import contextlib
import io
import json
import os
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile

from sme import cli
from sme.contract import validate_manifest, validate_operation
from sme.source import (
    INVENTORY_CONTRACT,
    INVENTORY_NAME,
    MANIFEST_NAME,
    Limits,
    SourceError,
    extract_source,
    inspect_source,
    validate_inventory,
)


def pdf_bytes(pages=('one', 'two')):
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


def write_file(root, relative, data=b'x'):
    path = os.path.join(root, *relative.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as file:
        file.write(data)
    return path


def html_files(prefix=''):
    prefix = prefix.rstrip('/')

    def name(path):
        return f'{prefix}/{path}' if prefix else path

    return {
        name('index.html'): b'<title>Example</title>',
        name('pages/1.html'): b'<h1>Procedure</h1>',
        name('images/one.svg'): b'<svg xmlns="http://www.w3.org/2000/svg"/>',
        name('empty.txt'): b'',
    }


def make_zip(path, files, directories=(), compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, 'w', compression=compression) as archive:
        for directory in directories:
            archive.writestr(directory.rstrip('/') + '/', b'')
        for name, data in files.items():
            archive.writestr(name, data)


def set_zip_encrypted_flag(path):
    with open(path, 'rb') as file:
        data = bytearray(file.read())
    local = data.index(b'PK\x03\x04')
    central = data.index(b'PK\x01\x02')
    local_flags = struct.unpack_from('<H', data, local + 6)[0] | 1
    central_flags = struct.unpack_from('<H', data, central + 8)[0] | 1
    struct.pack_into('<H', data, local + 6, local_flags)
    struct.pack_into('<H', data, central + 8, central_flags)
    with open(path, 'wb') as file:
        file.write(data)


class TestSourceRepeatability(unittest.TestCase):
    def test_inventory_schema_is_committed(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(
            root, 'schemas', 'service-manual-source-inventory-v1.schema.json',
        )
        with open(path, encoding='utf-8') as file:
            schema = json.load(file)
        self.assertEqual(schema['properties']['contract']['const'], INVENTORY_CONTRACT)

    def test_zip_and_folder_have_the_same_content_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = os.path.join(temporary, 'manual')
            os.makedirs(folder)
            for path, data in html_files().items():
                write_file(folder, path, data)
            os.makedirs(os.path.join(folder, 'unused-empty'))
            write_file(folder, '.DS_Store', b'ignored')
            archive = os.path.join(temporary, 'manual.zip')
            make_zip(archive, html_files(), directories=['unused-empty'])

            from_folder = inspect_source(folder)
            from_zip = inspect_source(archive)
            self.assertEqual(from_folder.content_sha256, from_zip.content_sha256)
            self.assertNotEqual(from_folder.source_id, from_zip.source_id)
            self.assertEqual((from_folder.container, from_zip.container),
                             ('directory', 'zip'))
            self.assertEqual(from_folder.ignored, ['.DS_Store'])

    def test_same_sized_change_gets_a_new_content_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            for path, data in html_files().items():
                write_file(folder, path, data)
            first = inspect_source(folder).content_sha256
            write_file(folder, 'pages/1.html', b'<h1>Different</h1>')
            second = inspect_source(folder).content_sha256
            self.assertNotEqual(first, second)

    def test_pdf_folder_records_pages_without_using_folder_as_vehicle_evidence(self):
        with tempfile.TemporaryDirectory(prefix='1998-2099-all-vehicles-') as folder:
            write_file(folder, 'articles/brakes.pdf', pdf_bytes(('one', 'two', 'three')))
            source = inspect_source(folder)
            self.assertEqual(source.format, 'pdf_collection_v1')
            self.assertEqual(source.publications[0].title, 'brakes')
            self.assertEqual(source.members[0].page_count, 3)
            self.assertNotIn('1998-2099', source.publications[0].title)


class TestArchiveSafety(unittest.TestCase):
    def _inspect_bad_member(self, member):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'bad.zip')
            files = html_files()
            files[member] = b'bad'
            make_zip(path, files)
            return inspect_source(path)

    def test_unsafe_archive_paths_are_reported_and_not_extracted(self):
        for member in ('../escape.txt', '/absolute.txt', 'C:/drive.txt',
                       'folder\\windows.txt', 'pages/control\x01.html',
                       '__MACOSX/../hidden-escape'):
            with self.subTest(member=member):
                source = self._inspect_bad_member(member)
                self.assertEqual(source.status, 'partial')
                self.assertIn('unsafe_path', {item['code'] for item in source.failures})

    def test_case_and_unicode_collisions_are_rejected(self):
        for pair in (('pages/A.html', 'pages/a.html'),
                     ('pages/Sub/one.html', 'pages/sub/two.html'),
                     ('pages/caf\N{LATIN SMALL LETTER E WITH ACUTE}.html',
                      'pages/cafe\N{COMBINING ACUTE ACCENT}.html')):
            with self.subTest(pair=pair), tempfile.TemporaryDirectory() as temporary:
                path = os.path.join(temporary, 'collision.zip')
                files = html_files()
                files[pair[0]] = b'one'
                files[pair[1]] = b'two'
                make_zip(path, files)
                source = inspect_source(path)
                self.assertIn('path_collision', {item['code'] for item in source.failures})

    def test_duplicate_zip_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'duplicate.zip')
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(path, 'w') as archive:
                    for name, data in html_files().items():
                        archive.writestr(name, data)
                    archive.writestr('pages/1.html', b'duplicate')
            source = inspect_source(path)
            self.assertIn('duplicate_member', {item['code'] for item in source.failures})

    def test_zip_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'symlink.zip')
            with zipfile.ZipFile(path, 'w') as archive:
                for name, data in html_files().items():
                    archive.writestr(name, data)
                link = zipfile.ZipInfo('images/link.svg')
                link.create_system = 3
                link.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(link, 'outside.svg')
            source = inspect_source(path)
            self.assertIn('symlink', {item['code'] for item in source.failures})

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlinks unavailable')
    def test_folder_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for path, data in html_files().items():
                write_file(folder, path, data)
            os.symlink('../index.html', os.path.join(folder, 'pages', 'link.html'))
            source = inspect_source(folder)
            self.assertIn('symlink', {item['code'] for item in source.failures})

    def test_encrypted_and_unsupported_compression_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            encrypted = os.path.join(temporary, 'encrypted.zip')
            make_zip(encrypted, html_files(), compression=zipfile.ZIP_STORED)
            set_zip_encrypted_flag(encrypted)
            source = inspect_source(encrypted)
            self.assertIn('encrypted_member', {item['code'] for item in source.failures})

            compressed = os.path.join(temporary, 'bzip2.zip')
            make_zip(compressed, html_files(), compression=zipfile.ZIP_BZIP2)
            source = inspect_source(compressed)
            self.assertIn('unsupported_compression',
                          {item['code'] for item in source.failures})

    def test_truncated_and_unknown_sources_fail_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = write_file(temporary, 'broken.zip', b'PK\x03\x04broken')
            with self.assertRaisesRegex(SourceError, 'invalid or truncated'):
                inspect_source(path)
            unknown = write_file(temporary, 'notes.txt', b'not a manual')
            with self.assertRaisesRegex(SourceError, 'unsupported file type'):
                inspect_source(unknown)

    def test_resource_limits_are_failures_not_silent_skips(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'large.zip')
            files = html_files()
            files['pages/repeated.html'] = b'A' * 10_000
            make_zip(path, files)
            cases = (
                (Limits(max_compression_ratio=2), 'compression_ratio_limit'),
                (Limits(max_files=2), 'file_limit'),
                (Limits(max_file_bytes=10), 'file_size_limit'),
                (Limits(max_total_bytes=30), 'total_size_limit'),
            )
            for limits, expected in cases:
                with self.subTest(expected=expected):
                    source = inspect_source(path, limits)
                    self.assertEqual(source.status, 'partial')
                    self.assertIn(expected, {item['code'] for item in source.failures})

    def test_overlapping_html_manual_roots_are_not_publishable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'overlap.zip')
            files = html_files()
            files.update(html_files('nested'))
            make_zip(path, files)
            source = inspect_source(path)
            self.assertEqual(source.status, 'partial')
            self.assertIn('overlapping_publications',
                          {item['code'] for item in source.failures})

    def test_corrupt_member_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'corrupt.zip')
            make_zip(path, html_files(), compression=zipfile.ZIP_STORED)
            with open(path, 'rb') as file:
                data = bytearray(file.read())
            marker = b'<h1>Procedure</h1>'
            data[data.index(marker)] ^= 0x01
            with open(path, 'wb') as file:
                file.write(data)
            source = inspect_source(path)
            self.assertEqual(source.status, 'partial')
            self.assertIn('unreadable_member', {item['code'] for item in source.failures})

    def test_pdf_collection_rejects_unrelated_files_and_accepts_a_single_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = os.path.join(temporary, 'pdfs')
            os.makedirs(folder)
            write_file(folder, 'one.pdf', pdf_bytes())
            write_file(folder, 'notes.txt', b'folder label is not evidence')
            source = inspect_source(folder)
            self.assertEqual(source.status, 'partial')
            self.assertIn('unsupported_member', {item['code'] for item in source.failures})

            standalone = write_file(temporary, 'standalone.pdf', pdf_bytes(('page',)))
            source = inspect_source(standalone)
            self.assertEqual(source.status, 'complete')
            self.assertEqual(source.container, 'file_collection')
            self.assertEqual(source.members[0].page_count, 1)


class TestStagedExtraction(unittest.TestCase):
    def test_extract_preserves_paths_empty_files_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'manual.zip')
            make_zip(source_path, html_files(), directories=['unused-empty'])
            output = os.path.join(temporary, 'output')
            result = extract_source(source_path, output)
            validate_operation(result)
            self.assertTrue(result['ok'])
            self.assertEqual(result['output']['files_written'], 4)
            self.assertEqual(os.path.getsize(os.path.join(output, 'empty.txt')), 0)
            self.assertTrue(os.path.isdir(os.path.join(output, 'unused-empty')))
            with open(os.path.join(output, MANIFEST_NAME), encoding='utf-8') as file:
                validate_manifest(json.load(file))
            with open(os.path.join(output, INVENTORY_NAME), encoding='utf-8') as file:
                inventory = json.load(file)
            validate_inventory(inventory)
            self.assertEqual(inventory['contract'], INVENTORY_CONTRACT)
            self.assertEqual(inventory['empty_directories'], ['unused-empty'])
            inventory['selected_content_sha256'] = '0' * 64
            with self.assertRaisesRegex(SourceError, 'does not match'):
                validate_inventory(inventory)

    def test_exact_publication_selection_does_not_merge_manuals(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'two.zip')
            files = {}
            files.update(html_files('diesel'))
            files.update(html_files('gasoline'))
            make_zip(source_path, files)
            source = inspect_source(source_path)
            chosen = next(item for item in source.publications
                          if item.source_path == 'diesel/index.html')
            output = os.path.join(temporary, 'output')
            result = extract_source(source_path, output, [chosen.id])
            self.assertTrue(result['ok'])
            self.assertTrue(os.path.isfile(os.path.join(output, 'diesel', 'index.html')))
            self.assertFalse(os.path.exists(os.path.join(output, 'gasoline')))

    def test_extract_all_pdfs_preserves_explicit_empty_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'pdfs.zip')
            make_zip(
                source_path,
                {'articles/brakes.pdf': pdf_bytes(('page',))},
                directories=['empty-notes'],
            )
            output = os.path.join(temporary, 'output')
            result = extract_source(source_path, output)
            self.assertTrue(result['ok'])
            self.assertTrue(os.path.isdir(os.path.join(output, 'empty-notes')))
            with open(os.path.join(output, INVENTORY_NAME), encoding='utf-8') as file:
                inventory = json.load(file)
            self.assertEqual(inventory['empty_directories'], ['empty-notes'])

    def test_unknown_publication_and_existing_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'manual.zip')
            make_zip(source_path, html_files())
            with self.assertRaisesRegex(SourceError, 'unknown publication'):
                extract_source(source_path, os.path.join(temporary, 'one'), ['pub_' + 'f' * 32])
            output = os.path.join(temporary, 'existing')
            os.makedirs(output)
            os.symlink('outside', os.path.join(output, 'nested-link'))
            with self.assertRaisesRegex(SourceError, 'already exists'):
                extract_source(source_path, output)

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlinks unavailable')
    def test_symlink_parent_and_destination_inside_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_folder = os.path.join(temporary, 'source')
            os.makedirs(source_folder)
            for path, data in html_files().items():
                write_file(source_folder, path, data)
            real_parent = os.path.join(temporary, 'real-parent')
            os.makedirs(real_parent)
            linked_parent = os.path.join(temporary, 'linked-parent')
            os.symlink(real_parent, linked_parent)
            with self.assertRaisesRegex(SourceError, 'symbolic link'):
                extract_source(source_folder, os.path.join(linked_parent, 'output'))
            with self.assertRaisesRegex(SourceError, 'inside the source'):
                extract_source(source_folder, os.path.join(source_folder, 'output'))

    def test_interruption_removes_staging_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'manual.zip')
            make_zip(source_path, html_files())
            output = os.path.join(temporary, 'output')

            def interrupt(_member):
                raise KeyboardInterrupt

            with self.assertRaises(KeyboardInterrupt):
                extract_source(source_path, output, on_member=interrupt)
            self.assertFalse(os.path.exists(output))
            self.assertFalse(any(name.startswith('.output.sme-')
                                 for name in os.listdir(temporary)))

    def test_partial_source_never_publishes_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'bad.zip')
            files = html_files()
            files['../escape'] = b'bad'
            make_zip(source_path, files)
            output = os.path.join(temporary, 'output')
            result = extract_source(source_path, output)
            self.assertFalse(result['ok'])
            self.assertEqual(result['output']['files_written'], 0)
            self.assertFalse(os.path.exists(output))


class TestNeutralSourceCli(unittest.TestCase):
    def test_probe_and_extract_json_exit_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_path = os.path.join(temporary, 'manual.zip')
            make_zip(source_path, html_files())
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(['probe', source_path, '--json'])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())['operation'], 'probe')

            output = os.path.join(temporary, 'output')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(['extract', source_path, '-o', output, '--json'])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())['operation'], 'extract')

    def test_unsupported_source_uses_exit_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = write_file(temporary, 'unknown.txt', b'unknown')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(['probe', path, '--json'])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(stdout.getvalue())['ok'])

    def test_partial_source_uses_exit_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'partial.zip')
            files = html_files()
            files['../escape'] = b'bad'
            make_zip(path, files)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(['probe', path, '--json'])
            self.assertEqual(code, 1)
            value = json.loads(stdout.getvalue())
            self.assertFalse(value['ok'])
            self.assertEqual(value['source']['status'], 'partial')


if __name__ == '__main__':
    unittest.main()
