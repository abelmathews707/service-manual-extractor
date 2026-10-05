"""Static allowlist for source fragments inserted into the legacy viewer."""

import html
from html.parser import HTMLParser
from urllib.parse import urlsplit

from sme.html_content import SAFE_TAGS


class _Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in SAFE_TAGS:
            return
        safe = []
        for name, value in attrs:
            if value is None:
                continue
            if name in {'href', 'src'}:
                try:
                    parsed = urlsplit(value)
                except ValueError:
                    continue
                if (parsed.scheme or parsed.netloc or value.startswith('\\') or
                        '\\' in value or any(ord(c) < 32 for c in value)):
                    continue
                if (name == 'href' and tag != 'a') or (name == 'src' and tag != 'img'):
                    continue
            elif name not in {'id', 'name', 'class', 'alt', 'title', 'colspan',
                              'rowspan', 'width', 'height', 'scope'}:
                continue
            safe.append(f' {name}="{html.escape(value, quote=True)}"')
        self.parts.append('<' + tag + ''.join(safe) + '>')

    def handle_endtag(self, tag):
        if tag in SAFE_TAGS and tag not in {'img', 'br', 'hr'}:
            self.parts.append('</' + tag + '>')

    def handle_data(self, data):
        self.parts.append(html.escape(data))


def safe_fragment(value):
    parser = _Fragment()
    parser.feed(value)
    parser.close()
    return ''.join(parser.parts)
