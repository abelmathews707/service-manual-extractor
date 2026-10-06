"""Local-only browser acceptance harness: refuse remote fetches and log shard loads.

This does not edit the built site. A restrictive response policy blocks remote
subresources; the injected test-only fetch log is inspectable through the DOM.
Loopback HTTP is still used for static-file access, as in normal offline use.
"""

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

INSTRUMENTATION = b"""
(() => {
  const requests = [], blocked = [];
  const original = window.fetch.bind(window);
  function record() {
    let output = document.getElementById('a10-network-log');
    if (!output) {
      output = document.createElement('output');
      output.id = 'a10-network-log'; output.hidden = true;
      document.documentElement.append(output);
    }
    output.textContent = JSON.stringify({requests, blocked});
  }
  window.fetch = (input, options) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.origin !== location.origin) {
      blocked.push(url.href); record();
      return Promise.reject(new Error('Remote fetch blocked by offline acceptance policy'));
    }
    requests.push(url.pathname); record();
    return original(input, options);
  };
  record();
})();
"""


class OfflineHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; connect-src 'self'; "
                         "img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self'; object-src 'self'; frame-src 'self'; "
                         "base-uri 'none'; form-action 'self'")
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/__a10_instrumentation.js':
            body = INSTRUMENTATION
            content_type = 'text/javascript; charset=utf-8'
        elif path in ('/', '/index.html'):
            with open(self.translate_path('/index.html'), 'rb') as stream:
                body = stream.read().replace(
                    b'</head>', b'<script src="/__a10_instrumentation.js"></script></head>')
            content_type = 'text/html; charset=utf-8'
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site')
    parser.add_argument('--port', type=int, default=5106)
    args = parser.parse_args()
    handler = partial(OfflineHandler, directory=args.site)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    print(json.dumps({'url': f'http://127.0.0.1:{args.port}/',
                      'remote_subresources': 'blocked', 'source_files': 'unchanged'}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
