"""Shared offline-viewer gates for normalized manufacturer-neutral records."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sme import cli
from sme.normalize import normalize_source
from sme.source import SourceError, extract_source
from sme.viewer import build_viewer

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'html_manual')


def read_json(root, relative):
    with open(os.path.join(root, *relative.split('/')), encoding='utf-8') as stream:
        return json.load(stream)


class NeutralViewerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = self.temporary.name
        self.source = os.path.join(self.root, 'source')
        self.extracted = os.path.join(self.root, 'extracted')
        self.normalized = os.path.join(self.root, 'normalized')
        self.site = os.path.join(self.root, 'site')
        for folder, title in (('chevrolet', 'Chevrolet Truck Manual'),
                              ('ford', 'Ford Truck Manual')):
            target = os.path.join(self.source, folder)
            shutil.copytree(FIXTURE, target)
            index = Path(target, 'index.html')
            value = index.read_text(encoding='utf-8')
            value = value.replace('Example Workshop Information', title)
            index.write_text(value, encoding='utf-8')
            page = Path(target, 'pages', '100.html')
            page.write_text(page.read_text(encoding='utf-8').replace(
                '</body>', '<p><a href="1066.html">Circuit description</a></p></body>'),
                encoding='utf-8')
            Path(target, 'pages', 'tree.html').write_text('''<html><body><h1>Contents</h1>
              <ul><li class="li-folder"><a name="diagnostics">Diagnostics</a><ul>
              <li><a href="100.html">Fuel system</a></li>
              <li><a href="1066.html">Circuit tests</a></li></ul></li></ul>
              </body></html>''', encoding='utf-8')

    def build(self):
        extract_source(self.source, self.extracted)
        normalize_source(self.extracted, self.normalized)
        return build_viewer(self.normalized, self.site, 'Mixed Vehicle Manuals')

    def test_multiple_publications_share_search_navigation_and_local_assets(self):
        result = self.build()
        self.assertEqual(result['publications'], 2)
        manifest = read_json(self.site, 'data/manifest.json')
        library = read_json(self.site, 'data/library.json')
        search = read_json(self.site, 'data/search-docs.json')
        self.assertEqual(manifest['viewerMode'], 'neutral')
        self.assertEqual(len(manifest['books']), 2)
        self.assertEqual({row[4] for row in search}, {book['id'] for book in manifest['books']})
        self.assertTrue(all(book['navigation'] for book in manifest['books']))
        self.assertTrue(any(node['children'] for book in manifest['books']
                            for node in book['navigation']))
        self.assertEqual(len(library['documents']), result['documents'])
        self.assertTrue(os.listdir(os.path.join(self.site, 'content', 'assets')))

    def test_fragments_use_neutral_routes_and_label_unavailable_material(self):
        self.build()
        fragments = []
        folder = os.path.join(self.site, 'content', 'manual')
        for name in os.listdir(folder):
            fragments.append(Path(folder, name).read_text(encoding='utf-8'))
        joined = '\n'.join(fragments)
        self.assertIn('#/manual/', joined)
        self.assertIn('Diagram unavailable.', joined)
        self.assertNotIn('https://example.com', joined)
        self.assertNotIn('<script', joined.casefold())

    def test_shared_client_has_search_return_keyboard_and_narrow_screen_support(self):
        self.build()
        script = Path(self.site, 'assets', 'app.js').read_text(encoding='utf-8')
        css = Path(self.site, 'assets', 'app.css').read_text(encoding='utf-8')
        self.assertIn("viewerMode === 'neutral'", script)
        self.assertIn('Return to search results', script)
        self.assertIn('showing first', script)
        self.assertIn("e.key === '/'", script)
        self.assertIn('@media (max-width:820px)', css)
        self.assertIn('.missing-content', css)

    def test_cli_builds_fresh_site_and_refuses_output_inside_input(self):
        extract_source(self.source, self.extracted)
        normalize_source(self.extracted, self.normalized)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = cli.main(['build-viewer', self.normalized, '-o', self.site, '--json'])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(stdout.getvalue())['ok'])
        nested = os.path.join(self.normalized, 'site')
        with self.assertRaisesRegex(SourceError, 'inside'):
            build_viewer(self.normalized, nested)


if __name__ == '__main__':
    unittest.main()
