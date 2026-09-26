"""Build the shared offline viewer from a normalized neutral package.

The neutral builder deliberately consumes only the versioned manifest and
content sidecar.  It never invokes the Ford ``.EPL`` parser and never executes
source HTML or source scripts.
"""

import hashlib
import html
import json
import os
import shutil
import stat
import tempfile
from collections import defaultdict

from fsd.build import VIEWER, build_search

from .contract import canonical_path, load_manifest
from .normalize import CONTENT_NAME, validate_content
from .source import MANIFEST_NAME, SourceError


def _json(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _write_json(path, value):
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(',', ':'))


def _local_file(root, relative):
    if canonical_path(relative) != relative or '\\' in relative:
        raise SourceError(f'non-canonical viewer input path: {relative!r}')
    current = root
    for part in relative.split('/'):
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise SourceError(f'viewer input contains a symbolic link: {relative}')
    if not stat.S_ISREG(os.stat(current, follow_symlinks=False).st_mode):
        raise SourceError(f'viewer input is not a regular file: {relative}')
    return current


def _copy_hashed(source, target, expected):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    digest = hashlib.sha256()
    with open(source, 'rb') as incoming, open(target, 'xb') as outgoing:
        while True:
            block = incoming.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            outgoing.write(block)
    if digest.hexdigest() != expected:
        raise SourceError(f'viewer input hash changed: {source}')


def _safe_title(title):
    return title.strip() if isinstance(title, str) and title.strip() else 'Service Manual Library'


def _copy_shell(staging, title):
    version = str(
        int(
            max(
                os.path.getmtime(os.path.join(root, name))
                for root, _, names in os.walk(VIEWER)
                for name in names
            )
        )
    )
    substitutions = {
        '__V__': version,
        '__TITLE__': html.escape(title),
        '__BRAND_MARK__': 'MANUALS',
        '__BRAND_NAME__': html.escape(title),
        '__BRAND_SUB__': 'Offline service information',
    }
    for root, _, names in os.walk(VIEWER):
        relative = os.path.relpath(root, VIEWER)
        destination = staging if relative == '.' else os.path.join(staging, relative)
        os.makedirs(destination, exist_ok=True)
        for name in names:
            if name.startswith('.'):
                continue
            target = os.path.join(destination, name)
            shutil.copyfile(os.path.join(root, name), target)
            if name.endswith(('.html', '.js', '.css')):
                with open(target, encoding='utf-8') as stream:
                    value = stream.read()
                for marker, replacement in substitutions.items():
                    value = value.replace(marker, replacement)
                with open(target, 'w', encoding='utf-8') as stream:
                    stream.write(value)


def _nav_insert(nodes, labels, document_id):
    current = nodes
    for index, raw in enumerate(labels):
        label = raw.strip() if isinstance(raw, str) else ''
        if not label:
            continue
        node = next((item for item in current if item['label'] == label), None)
        if node is None:
            node = {'label': label, 'children': [], 'document_id': None}
            current.append(node)
        if index == len(labels) - 1:
            node['document_id'] = document_id
        current = node['children']


def _navigation(publication, records, documents):
    tree = []
    publication_records = [
        record for record in records if record['publication_id'] == publication['id']
    ]
    for record in publication_records:
        document = documents[record['id']]
        if record['role'] == 'pdf_page':
            number = record['page']
            first = ((number - 1) // 100) * 100 + 1
            last = first + 99
            labels = [
                os.path.basename(record['original_path']),
                f'Pages {first}–{last}',
                f'Page {number}',
            ]
            _nav_insert(tree, labels, record['id'])
            continue
        routes = [route.get('labels', []) for route in record.get('navigation_routes', [])]
        if not routes:
            labels = list(document.get('breadcrumbs') or [])
            labels.append(document['title'])
            routes = [labels]
        seen = set()
        for labels in routes:
            labels = tuple(label for label in labels if label)
            if not labels or labels in seen:
                continue
            seen.add(labels)
            _nav_insert(tree, labels, record['id'])
    return tree


def _render_node(node, record, document_publications, asset_urls):
    if isinstance(node, str):
        return html.escape(node)
    tag = node['tag']
    attrs = node['attrs']
    children = ''.join(
        _render_node(child, record, document_publications, asset_urls) for child in node['children']
    )
    values = []
    for key in ('rowspan', 'colspan'):
        if key in attrs:
            values.append(f' {key}="{int(attrs[key])}"')
    if 'reference' in attrs:
        reference = record['references'][attrs['reference']]
        label = children or html.escape(
            reference.get('label') or reference.get('href') or 'reference'
        )
        if reference['status'] == 'resolved':
            target = reference['target_id']
            publication = document_publications[target]
            fragment = reference.get('target_fragment') or reference.get('fragment') or ''
            anchor = '#' + fragment if fragment else ''
            return (
                f'<a href="#/manual/{publication}/{target}" data-source-anchor="'
                f'{html.escape(anchor, quote=True)}">{label}</a>'
            )
        reason = reference.get('reason') or 'target unavailable'
        return (
            f'<span class="unavailable-link" title="{html.escape(reason, quote=True)}">'
            f'{label} <span class="pill">{html.escape(reference["status"])}</span></span>'
        )
    if 'figure' in attrs:
        figure = record['figures'][attrs['figure']]
        caption = figure.get('caption') or 'Diagram'
        url = asset_urls.get((record['id'], attrs['figure']))
        if url:
            return (
                f'<figure class="manual-figure"><img src="{html.escape(url, quote=True)}" '
                f'alt="{html.escape(caption, quote=True)}" loading="lazy" decoding="async">'
                f'<figcaption>{html.escape(caption)}</figcaption></figure>'
            )
        reason = figure.get('reason') or figure.get('status') or 'unavailable'
        return (
            f'<span class="missing-content"><b>Diagram unavailable.</b> '
            f'{html.escape(reason)}</span>'
        )
    return f'<{tag}{"".join(values)}>{children}</{tag}>'


def _prepare_assets(root, staging, records):
    urls = {}
    copied = {}
    asset_root = os.path.join(staging, 'content', 'assets')
    source_root = os.path.join(staging, 'content', 'sources')
    for record in records:
        for index, figure in enumerate(record['figures']):
            if figure['status'] not in {'safe_svg', 'raster'}:
                continue
            relative = figure['render_path']
            expected = figure['render_sha256']
            extension = os.path.splitext(relative)[1].lower()
            name = expected + extension
            target = os.path.join(asset_root, name)
            if expected not in copied:
                _copy_hashed(_local_file(root, relative), target, expected)
                copied[expected] = target
            urls[(record['id'], index)] = f'content/assets/{name}'
        if record['role'] != 'pdf_page':
            continue
        figure = record['figures'][0]
        expected = figure['sha256']
        name = expected + '.pdf'
        target = os.path.join(source_root, name)
        if expected not in copied:
            _copy_hashed(_local_file(root, record['original_path']), target, expected)
            copied[expected] = target
        record['source_url'] = f'content/sources/{name}#page={record["page"]}'
    return urls


def build_viewer(package, destination, title=None):
    """Verify *package* and atomically publish a manufacturer-neutral site."""
    root = os.path.abspath(package)
    if os.path.islink(root) or not os.path.isdir(root):
        raise SourceError('viewer input must be a regular normalized directory')
    manifest_path = _local_file(root, MANIFEST_NAME)
    content_path = _local_file(root, CONTENT_NAME)
    manifest = load_manifest(manifest_path)
    content = validate_content(_json(content_path), manifest)
    destination = os.path.abspath(destination)
    parent = os.path.dirname(destination)
    if os.path.lexists(destination) or not os.path.isdir(parent) or os.path.islink(parent):
        raise SourceError('viewer output must be fresh with an existing regular parent directory')
    try:
        inside = os.path.commonpath((os.path.realpath(root), os.path.realpath(destination))) == (
            os.path.realpath(root)
        )
    except ValueError:
        inside = False
    if inside:
        raise SourceError('viewer output may not be inside the normalized package')

    publications = manifest['publications']
    site_title = _safe_title(
        title or (publications[0]['title'] if len(publications) == 1 else 'Service Manual Library')
    )
    staging = tempfile.mkdtemp(prefix=f'.{os.path.basename(destination)}.sme-viewer-', dir=parent)
    try:
        _copy_shell(staging, site_title)
        os.makedirs(os.path.join(staging, 'data'), exist_ok=True)
        os.makedirs(os.path.join(staging, 'content', 'manual'), exist_ok=True)
        records = json.loads(json.dumps(content['documents']))
        documents = {
            document['id']: document
            for publication in publications
            for document in publication['documents']
        }
        document_publications = {
            document['id']: publication['id']
            for publication in publications
            for document in publication['documents']
        }
        asset_urls = _prepare_assets(root, staging, records)
        record_map = {record['id']: record for record in records}
        docs = []
        backlinks = defaultdict(list)
        client_documents = {}
        for publication in publications:
            for document in publication['documents']:
                record = record_map[document['id']]
                fragment = ''.join(
                    _render_node(node, record, document_publications, asset_urls)
                    for node in record['structure']
                )
                with open(
                    os.path.join(staging, 'content', 'manual', document['id'] + '.html'),
                    'w',
                    encoding='utf-8',
                ) as stream:
                    stream.write(fragment)
                for reference in record['references']:
                    if reference['status'] == 'resolved':
                        backlinks[reference['target_id']].append(document['id'])
                client_documents[document['id']] = {
                    'id': document['id'],
                    'publication_id': publication['id'],
                    'title': document['title'],
                    'role': record['role'],
                    'breadcrumbs': document.get('breadcrumbs', []),
                    'path': record['original_path'],
                    'page': record.get('page'),
                    'source_url': record.get('source_url'),
                    'text_provenance': document['text']['provenance'],
                    'applicability': document['applicability'],
                    'warnings': record['warnings'],
                    'unavailable_references': sum(
                        reference['status'] != 'resolved' for reference in record['references']
                    ),
                    'unavailable_figures': sum(
                        figure['status'] in {'missing', 'unsupported', 'blocked'}
                        for figure in record['figures']
                    ),
                }
                if record['search_eligible']:
                    docs.append(
                        (
                            'manual',
                            document['id'],
                            document['title'],
                            record['text'],
                            publication['id'],
                        )
                    )

        books = []
        for publication in publications:
            ids = [document['id'] for document in publication['documents']]
            searchable = sum(record_map[identifier]['search_eligible'] for identifier in ids)
            books.append(
                {
                    'id': publication['id'],
                    'name': publication['title'],
                    'kind': publication['kind'],
                    'source_path': publication['source_path'],
                    'applicability': publication['applicability'],
                    'documents': len(ids),
                    'searchable': searchable,
                    'navigation': _navigation(publication, records, documents),
                    'landing_id': next(
                        (
                            identifier
                            for identifier in ids
                            if record_map[identifier]['role'] == 'landing'
                        ),
                        ids[0] if ids else None,
                    ),
                }
            )
        inverted, lengths = build_search(
            [(role, identifier, name, text) for role, identifier, name, text, _ in docs]
        )
        search_docs = [
            [row[0], row[1], row[2], lengths[index], row[4]] for index, row in enumerate(docs)
        ]
        viewer_manifest = {
            'viewerMode': 'neutral',
            'title': site_title,
            'sourceLabel': 'Normalized service-manual package',
            'sourceStatus': manifest['source']['status'],
            'contentStatus': content['status'],
            'failures': content['failures'],
            'books': books,
            'counts': {
                'books': len(books),
                'documents': len(client_documents),
                'searchable': len(search_docs),
            },
        }
        _write_json(os.path.join(staging, 'data', 'manifest.json'), viewer_manifest)
        _write_json(
            os.path.join(staging, 'data', 'library.json'),
            {
                'documents': client_documents,
            },
        )
        _write_json(
            os.path.join(staging, 'data', 'backlinks.json'),
            {
                'pages': {key: sorted(set(value)) for key, value in backlinks.items()},
                'connSheets': {},
            },
        )
        _write_json(os.path.join(staging, 'data', 'search-docs.json'), search_docs)
        _write_json(os.path.join(staging, 'data', 'search-index.json'), inverted)
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        'ok': True,
        'output': destination,
        'title': site_title,
        'publications': len(books),
        'documents': len(client_documents),
        'searchable_documents': len(search_docs),
        'content_status': content['status'],
        'failures': content['failures'],
    }
