"""Static HTML interpretation. Source markup is data and is never executed."""

import base64
import binascii
import hashlib
import re
import struct
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from .source import SourceError

VOID = {
    'area',
    'base',
    'br',
    'col',
    'embed',
    'hr',
    'img',
    'input',
    'link',
    'meta',
    'param',
    'source',
    'track',
    'wbr',
}
EXCLUDED = {
    'script',
    'style',
    'noscript',
    'template',
    'iframe',
    'object',
    'embed',
    'form',
    'head',
    'svg',
}
SHELL = {'footer', 'branding', 'header'}
BLOCKS = {
    'p',
    'div',
    'section',
    'article',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'ul',
    'ol',
    'li',
    'table',
    'tr',
    'th',
    'td',
    'br',
    'hr',
    'pre',
    'blockquote',
}
SAFE_TAGS = BLOCKS | {
    'thead',
    'tbody',
    'tfoot',
    'caption',
    'strong',
    'b',
    'em',
    'i',
    'span',
    'sub',
    'sup',
    'code',
    'dl',
    'dt',
    'dd',
    'a',
    'img',
}
EVIDENCE = re.compile(
    r'\b(?:19|20)\d{2}\b|\b\d\.\d\s*(?:L\b|liter)|\bonly\b|\bexcept\b|'
    r'\b(?:diesel|gasoline|VIN|RPO|Silverado|Sierra|Chevrolet|GMC)\b',
    re.I,
)


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = None

    @property
    def classes(self):
        return set(self.attrs.get('class', '').split())

    def walk(self):
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed([item for item in node.children if isinstance(item, Node)]))


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.count = 0

    def handle_starttag(self, tag, attrs):
        # The observed exports omit optional </li>, </td> and </tr> tags.
        optional = {
            'li': ({'li'}, {'ul', 'ol'}),
            'tr': ({'tr'}, {'table'}),
            'td': ({'td', 'th'}, {'tr', 'table'}),
            'th': ({'td', 'th'}, {'tr', 'table'}),
            'p': ({'p'}, {'div', 'section', 'body'}),
            'a': ({'a'}, {'body'}),
        }
        if tag in optional:
            closing, boundary = optional[tag]
            for index in range(len(self.stack) - 1, 0, -1):
                if self.stack[index].tag in boundary:
                    break
                if self.stack[index].tag in closing:
                    del self.stack[index:]
                    break
        self.count += 1
        if self.count > 300_000 or len(self.stack) > 200:
            raise SourceError('HTML exceeds the node/depth limit')
        node = Node(tag, dict(attrs), parent=self.stack[-1])
        node.attrs = {key: value or '' for key, value in node.attrs.items()}
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def excluded(node):
    return (
        node.tag in EXCLUDED
        or node.tag in {'nav', 'footer', 'header'}
        or bool(node.classes & SHELL)
    )


def visible_nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        if excluded(node):
            continue
        yield node
        stack.extend(reversed([item for item in node.children if isinstance(item, Node)]))


def text_of(node, shell=True):
    parts = []

    def visit(item):
        if isinstance(item, str):
            parts.append(item)
            return
        if item.tag in EXCLUDED or (shell and excluded(item)):
            return
        if item.tag in BLOCKS:
            parts.append('\n')
        for child in item.children:
            visit(child)
        if item.tag in BLOCKS:
            parts.append('\n')

    visit(node)
    lines = [' '.join(line.split()) for line in ''.join(parts).splitlines()]
    return '\n'.join(line for line in lines if line)


def decode_html(data, ford_legacy=False):
    if len(data) > 32 * 1024 * 1024:
        raise SourceError('HTML exceeds the 32 MiB limit')
    if ford_legacy and data.startswith(b'\xff\xfe'):
        return data.decode('utf-16-le'), 'utf-16-le'
    encoding = 'utf-8-sig'
    declaration = re.search(rb'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', data[:4096], re.I)
    if declaration:
        encoding = declaration[1].decode('ascii').lower()
    if encoding not in {'utf-8', 'utf-8-sig', 'windows-1252', 'cp1252', 'iso-8859-1'}:
        raise SourceError(f'unsupported HTML encoding: {encoding}')
    try:
        return data.decode(encoding), encoding
    except UnicodeError as ex:
        if ford_legacy and encoding in {'utf-8', 'utf-8-sig'}:
            return data.decode('cp1252', errors='replace'), 'cp1252-fallback'
        raise SourceError(f'HTML cannot be decoded as {encoding}: {ex}') from None


def local_url(current, href):
    """Return canonical path/fragment, or an explicit reason to block a URL."""
    if any(ord(char) < 32 for char in href):
        return None, '', 'control character in URL'
    try:
        url = urlsplit(href.replace('\\', '/'))
    except ValueError:
        return None, '', 'invalid URL'
    if url.scheme or url.netloc:
        return None, '', 'external or active URL is not fetched'
    path = unquote(url.path).replace('\\', '/')
    fragment = unquote(url.fragment)
    if path.startswith('/') or re.match(r'^[A-Za-z]:', path):
        return None, fragment, 'absolute URL is not a source-relative reference'
    if any(ord(char) < 32 for char in path + fragment):
        return None, '', 'encoded control character in URL'
    if url.query:
        return None, fragment, 'query-dependent reference is unsupported'
    if not path:
        return current, fragment, None
    parts = current.split('/')[:-1]
    for part in path.split('/'):
        if part == '..':
            if not parts:
                return None, fragment, 'reference escapes the source root'
            parts.pop()
        elif part not in {'', '.'}:
            parts.append(part)
    if not parts:
        return None, fragment, 'reference identifies a directory'
    return '/'.join(parts), fragment, None


def evidence(statement, path, level='document', selector=None):
    value = {'level': level, 'statement': statement, 'source_path': path}
    if selector:
        value['selector'] = selector
    return value


def parse_html(data, path, ford_legacy=False):
    decoded, encoding = decode_html(data, ford_legacy=ford_legacy)
    parser = TreeParser()
    parser.feed(decoded)
    parser.close()
    root = parser.root
    all_nodes = list(root.walk())
    body = next((node for node in all_nodes if node.tag == 'body'), root)
    main = next((node for node in all_nodes if 'main' in node.classes), body)
    nodes = list(visible_nodes(main))
    headings = [text_of(node) for node in nodes if node.tag == 'h1' and text_of(node)]
    title = (
        headings[0]
        if headings
        else next(
            (text_of(node) for node in all_nodes if node.tag == 'title' and text_of(node)), path
        )
    )
    breadcrumbs = [
        text_of(node, shell=False)
        for node in all_nodes
        if 'breadcrumb-part' in node.classes and text_of(node, shell=False)
    ]
    anchors = sorted(
        {
            node.attrs.get('id') or node.attrs.get('name')
            for node in all_nodes
            if node.attrs.get('id') or (node.tag == 'a' and node.attrs.get('name'))
        }
    )
    filename = path.rsplit('/', 1)[-1].casefold()
    role = 'procedure'
    if filename == 'external-car.html':
        role = 'unavailable'
    elif filename in {'index.html', '404.html'}:
        role = 'landing'
    elif any('li-folder' in node.classes for node in nodes):
        role = 'navigation'
    elif any(node.tag in {'ul', 'ol'} for node in nodes) and not any(
        node.tag in {'p', 'table', 'img'} for node in nodes
    ):
        role = 'navigation'
    warnings = []
    if body is root:
        warnings.append('missing_body: parsed HTML fragment')
    if not headings:
        warnings.append('missing_heading: title falls back to metadata or path')
    applicability = []
    for index, crumb in enumerate(breadcrumbs):
        if EVIDENCE.search(crumb):
            applicability.append(evidence(crumb, path, selector=f'breadcrumb:{index}'))
    if EVIDENCE.search(title):
        applicability.append(evidence(title, path, selector='heading'))
    for index, node in enumerate(nodes):
        explicit = node.classes & {
            'vehicle',
            'warning',
            'qualifier',
            'other-warning',
            'other-variant',
        }
        if not explicit and node.tag not in {'p', 'td', 'th', 'li'}:
            continue
        if node.tag == 'li' and any(
            isinstance(c, Node) and c.tag in {'ul', 'ol'} for c in node.children
        ):
            continue
        statement = text_of(node)
        if not statement:
            continue
        if explicit or (node.tag in {'p', 'td', 'th', 'li'} and EVIDENCE.search(statement)):
            ancestor = node
            level = 'document'
            while ancestor and ancestor is not main:
                if ancestor.tag == 'table':
                    level = 'table'
                    break
                ancestor = ancestor.parent
            applicability.append(evidence(statement, path, level, f'node:{index}'))
    links = []
    link_indices = {}
    # Retain footer/breadcrumb links for audit, with their role separate from search.
    for node in all_nodes:
        if node.tag != 'a' or 'href' not in node.attrs:
            continue
        target, fragment, reason = local_url(path, node.attrs['href'])
        context = 'content'
        ancestor = node
        while ancestor:
            if ancestor.tag in {'nav', 'footer', 'header'} or ancestor.classes & SHELL:
                context = 'navigation' if ancestor.tag == 'nav' else 'shell'
                break
            ancestor = ancestor.parent
        link_indices[id(node)] = len(links)
        links.append(
            {
                'href': node.attrs['href'],
                'label': text_of(node, shell=False),
                'path': target,
                'fragment': fragment,
                'context': context,
                'source_fragment': node.attrs['href'].partition('#')[2],
                'status': 'blocked' if reason else 'pending',
                'reason': reason,
            }
        )
    figures = []
    image_indices = {}
    caption = ''
    for node in nodes:
        if 'imageCaption' in node.classes or node.tag == 'figcaption':
            caption = text_of(node)
        if node.tag != 'img':
            continue
        holder = node.parent
        if holder and holder.tag == 'figure':
            local_caption = next((text_of(n) for n in holder.walk() if n.tag == 'figcaption'), '')
        else:
            local_caption = ''
        label = local_caption or caption or node.attrs.get('alt', '')
        href = node.attrs.get('src', '')
        target, fragment, reason = (
            local_url(path, href) if href else (None, '', 'image has no source')
        )
        image_indices[id(node)] = len(figures)
        figures.append(
            {
                'href': href,
                'path': target,
                'caption': label,
                'status': 'blocked' if reason else 'pending',
                'reason': reason,
            }
        )
        if label and EVIDENCE.search(label):
            applicability.append(evidence(label, path, 'figure', f'figure:{len(figures) - 1}'))
        caption = ''

    def structure(node, parent_tag=''):
        if isinstance(node, str):
            if node.strip():
                return [node]
            return (
                [' ']
                if node
                and parent_tag
                in {
                    'p',
                    'span',
                    'a',
                    'b',
                    'strong',
                    'em',
                    'i',
                    'td',
                    'th',
                    'li',
                    'div',
                    'section',
                    'h1',
                    'h2',
                    'h3',
                    'h4',
                    'h5',
                    'h6',
                }
                else []
            )
        if excluded(node):
            return []
        children = [item for child in node.children for item in structure(child, node.tag)]
        if node.tag not in SAFE_TAGS:
            return children
        attrs = {}
        for name in ('colspan', 'rowspan') if node.tag in {'td', 'th'} else ():
            raw = node.attrs.get(name, '1')
            if not raw.isdigit() or not 1 <= int(raw) <= 1000:
                raise SourceError(f'invalid table {name}: {raw!r}')
            attrs[name] = int(raw)
        if node.tag == 'a' and id(node) in link_indices:
            attrs['reference'] = link_indices[id(node)]
        if node.tag == 'img':
            attrs['figure'] = image_indices[id(node)]
        return [{'tag': node.tag, 'attrs': attrs, 'children': children}]

    navigation = []
    for node in all_nodes:
        if node.tag != 'a':
            continue
        ancestors = []
        parent = node.parent
        while parent:
            if parent.tag == 'li':
                label = next(
                    (
                        text_of(child, shell=False)
                        for child in parent.children
                        if isinstance(child, Node) and child.tag == 'a'
                    ),
                    '',
                )
                if label:
                    ancestors.append(label)
            parent = parent.parent
        if ancestors:
            navigation.append(
                {
                    'labels': list(reversed(ancestors)),
                    'reference': link_indices.get(id(node)),
                    'anchor': node.attrs.get('name') or node.attrs.get('id'),
                }
            )
    text = text_of(main)
    return {
        'title': title,
        'breadcrumbs': breadcrumbs,
        'role': role,
        'anchors': anchors,
        'text': text if role == 'procedure' else '',
        'visible_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'structure': structure(main),
        'references': links,
        'figures': figures,
        'applicability': applicability,
        'navigation': navigation,
        'encoding': encoding,
        'warnings': warnings,
    }


SVG_TAGS = {
    'svg',
    'g',
    'defs',
    'path',
    'rect',
    'circle',
    'ellipse',
    'line',
    'polyline',
    'polygon',
    'text',
    'tspan',
    'title',
    'desc',
    'clipPath',
    'linearGradient',
    'radialGradient',
    'stop',
    'view',
    'marker',
    'image',
}
SVG_ATTRS = set(
    (
        'id x y x1 x2 y1 y2 dx dy width height viewBox preserveAspectRatio '
        'd points cx cy r rx ry fill stroke stroke-width stroke-linecap '
        'stroke-linejoin stroke-miterlimit stroke-dasharray stroke-dashoffset '
        'fill-rule clip-rule opacity fill-opacity stroke-opacity transform '
        'font-family font-size font-weight font-style font-stretch text-anchor '
        'dominant-baseline clip-path offset stop-color stop-opacity '
        'gradientUnits gradientTransform version color text-decoration '
        'marker-end marker-start marker-mid refX refY markerUnits markerWidth '
        'markerHeight orient visibility href'
    ).split()
)
SVG_NS = 'http://www.w3.org/2000/svg'


def _static_png(value):
    """Accept only bounded, structurally valid inline PNG bytes in SVG images."""
    prefix = 'data:image/png;base64,'
    if not value.startswith(prefix):
        raise SourceError('SVG image must be an inline PNG, not a network resource')
    encoded = value[len(prefix) :]
    if len(encoded) > 8 * 1024 * 1024:
        raise SourceError('inline PNG exceeds the size limit')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise SourceError('invalid inline PNG base64') from None
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise SourceError('inline image is not a PNG')
    position = 8
    seen_header = False
    seen_end = False
    while position + 12 <= len(data):
        size = int.from_bytes(data[position : position + 4], 'big')
        kind = data[position + 4 : position + 8]
        end = position + 12 + size
        if end > len(data):
            raise SourceError('truncated inline PNG chunk')
        body = data[position + 8 : position + 8 + size]
        crc = int.from_bytes(data[end - 4 : end], 'big')
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise SourceError('inline PNG CRC mismatch')
        if not seen_header:
            if kind != b'IHDR' or size != 13:
                raise SourceError('inline PNG lacks an IHDR chunk')
            width, height = struct.unpack('>II', body[:8])
            if not width or not height or width * height > 40_000_000:
                raise SourceError('inline PNG dimensions exceed the limit')
            seen_header = True
        if kind == b'IEND':
            if size or end != len(data):
                raise SourceError('inline PNG has trailing bytes')
            seen_end = True
            break
        position = end
    if not seen_end:
        raise SourceError('inline PNG lacks an IEND chunk')


def safe_svg(data):
    """Produce a static SVG subset; reject active/unknown markup, never fetch resources."""
    if len(data) > 16 * 1024 * 1024:
        raise SourceError('SVG exceeds the 16 MiB limit')
    try:
        data.decode('utf-8-sig')
    except UnicodeError:
        raise SourceError('only UTF-8 SVG input is supported') from None
    if b'\x00' in data or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise SourceError('SVG DTD/entities are unsupported')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as ex:
        raise SourceError(f'invalid SVG: {ex}') from None
    if root.tag != f'{{{SVG_NS}}}svg':
        raise SourceError('SVG root/namespace is unsupported')
    ids = set()
    references = []
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > 100_000 or depth > 100:
            raise SourceError('SVG exceeds node/depth limit')
        tag = node.tag.removeprefix('{' + SVG_NS + '}')
        if tag not in SVG_TAGS:
            raise SourceError(f'unsupported SVG element: {tag}')
        for child in list(node):
            if child.tag == f'{{{SVG_NS}}}metadata':
                node.remove(child)
            else:
                stack.append((child, depth + 1))
        if 'style' in node.attrib:
            # Permit only ordinary presentation declarations from the same allowlist.
            for declaration in node.attrib.pop('style').split(';'):
                if not declaration.strip():
                    continue
                key, separator, value = declaration.partition(':')
                key = key.strip()
                if not separator or key not in SVG_ATTRS or key in {'id', 'd', 'points'}:
                    raise SourceError('unsupported SVG style declaration')
                node.set(key, value.strip())
        for key, value in list(node.attrib.items()):
            if key.startswith('data-'):
                del node.attrib[key]
                continue
            if key == '{http://www.w3.org/XML/1998/namespace}space':
                del node.attrib[key]
                continue
            if key not in SVG_ATTRS:
                raise SourceError(f'unsupported SVG attribute: {key}')
            if key == 'href':
                if tag != 'image':
                    raise SourceError('SVG href is only supported on an image')
                _static_png(value)
                continue
            if any(
                token in value.casefold()
                for token in ('javascript:', 'data:', 'http:', 'https:', '\\', '@')
            ):
                raise SourceError('external or active SVG value')
            if 'url' in value.casefold():
                match = re.fullmatch(r'url\(#([A-Za-z_][\w.-]*)\)', value)
                if not match:
                    raise SourceError('only internal SVG paint references are supported')
                references.append(match[1])
            if key == 'id':
                if value in ids:
                    raise SourceError('duplicate SVG ID')
                ids.add(value)
    if set(references) - ids:
        raise SourceError('missing SVG paint target')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
