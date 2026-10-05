"""Optional real-browser regression for the generated legacy viewer."""

import functools
import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from test_cr3_regressions import write_files
from test_ford_adapter import _epl

from fsd.build import build


class LegacyBrowserSecurityTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('REPAIR_BUDDY_TEST_CHROME') and shutil.which('node'),
                         'browser gate requires Chrome, Node and Playwright')
    def test_built_html_and_svg_do_not_execute_or_request_source_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            requests = []

            class Handler(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def do_GET(self):
                    requests.append(self.path)
                    super().do_GET()

            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
                functools.partial(Handler, directory=str(root / 'site')))
            address = f'http://127.0.0.1:{server.server_port}'
            write_files(root / 'extracted', {'SAA/SAA.EPL': _epl(),
                'SAA/SAAG1000001.HTM': (
                    '<h1>Authored test</h1><p>Check voltage.</p>'
                    f'<img src="{address}/probe" onerror="window.fixture=1">'
                    '<img src="GOOD.SVG"><a href="SAAG1000001.HTM">Return</a>').encode(),
                'SAA/BAD.SVG': (b'<svg xmlns="http://www.w3.org/2000/svg" '
                                b'onclick="window.svgFixture=1"/>'),
                'SAA/GOOD.SVG': (b'<svg xmlns="http://www.w3.org/2000/svg">'
                                 b'<path d="M0 0h10"/></svg>')})
            build(root / 'extracted', root / 'site', log=lambda _: None)
            (root / 'site/probe.html').write_text('''<!doctype html><html><body>
              <iframe id="reader" src="/index.html#/wsm/saag1000001"></iframe>
              <script>
              fetch('/content/wsm/bad.svg').then(r=>r.text()).then(text=>{
                const svg=new DOMParser().parseFromString(text,'image/svg+xml').documentElement;
                document.body.append(document.importNode(svg,true));
                document.querySelector('svg').dispatchEvent(new MouseEvent('click'));
              });
              setTimeout(()=>{
                const reader=document.querySelector('iframe').contentWindow;
                const body=reader.document.body;
                document.documentElement.dataset.security =
                  !reader.fixture && !window.svgFixture &&
                  body.innerText.includes('Check voltage.') &&
                  !body.querySelector('[onerror],[onclick]') ? 'passed' : 'failed';
              },2500);
              </script></body></html>''')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(['node',
                    str(Path(__file__).with_name('legacy_browser_security.cjs')),
                    address + '/probe.html'],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr[-1000:])
                self.assertIn('security passed', result.stdout)
                self.assertNotIn('/probe', requests)
                self.assertIn('/content/wsm/saag1000001.html', requests)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
