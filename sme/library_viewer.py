"""Publish a reviewed, vehicle-scoped offline viewer from one library export."""

import hashlib
import html
import json
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone

from .applicability_contracts import (
    digest,
    scope_fingerprint,
    validate_library,
    validate_review_overlay,
    validate_vocabulary,
)
from .contract import ContractError
from .library import verified_package
from .library_export import open_current
from .normalize import _local_file
from .viewer import _copy_shell, _nav_insert, _prepare_assets, _render_node, _write_json


def _read(root, relative):
    with open(_local_file(root, relative), encoding='utf-8') as stream:
        return json.load(stream)


def _review_revision(path):
    if os.path.islink(path) or not stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode):
        raise ContractError('current review overlay must be a regular file')
    with open(path, encoding='utf-8') as stream:
        review = json.load(stream)
    if (review.get('contract') != 'applicability-review/v1' or
            review.get('revision') != digest({key: value for key, value in review.items()
                                              if key != 'revision'})):
        raise ContractError('current review overlay revision does not match its content')
    return review


def _site_id(occurrence, publication):
    value = hashlib.sha256((occurrence + '\0' + publication).encode()).hexdigest()[:32]
    return 'book_' + value


def _navigation_target(nodes, labels):
    current = nodes
    for label in labels:
        node = next((item for item in current if item['label'] == label), None)
        if node is None:
            return None
        current = node['children']
    return node['document_id']


def _verified_export(generation, index, current_revision):
    library = validate_library(_read(generation, 'library.json'))
    vocabulary = validate_vocabulary(_read(generation, 'vocabulary.json'))
    review = _read(generation, 'review.json')
    if (library['review_revision'] != current_revision or
            review['revision'] != current_revision or
            library['vocabulary_revision'] != vocabulary['revision'] or
            index['library_revision'] != library['revision'] or
            index['vocabulary_revision'] != vocabulary['revision'] or
            index['review_revision'] != current_revision or
            index['policy_version'] != library['policy_version']):
        raise ContractError('offline viewer export revisions do not agree')
    sources = {}
    packages = []
    for occurrence in library['packages']:
        if occurrence['status'] != 'active':
            continue
        evidence_name = f'evidence/{occurrence["source_id"]}.json'
        evidence = (_read(generation, evidence_name)
                    if os.path.isfile(os.path.join(generation, evidence_name)) else None)
        root = os.path.join(generation, occurrence['root'])
        package = verified_package(root, evidence, vocabulary if evidence else None)
        if (package['manifest_sha256'] != occurrence['manifest_sha256'] or
                package['content_sha256'] != occurrence['content_sha256'] or
                package['manifest']['source']['id'] != occurrence['source_id']):
            raise ContractError('offline viewer package differs from library identity')
        if evidence:
            sources[evidence['source_id']] = evidence
        packages.append((occurrence, package))
    validate_review_overlay(review, list(sources.values()), vocabulary)
    texts = {}
    for shard_id, shard in index['shards'].items():
        payload = _read(generation, shard['path'])
        if (digest(payload)[:32] != shard_id or
                {item['unit_id'] for item in payload} != set(shard['unit_ids'])):
            raise ContractError('offline viewer search shard changed')
        for item in payload:
            old = texts.setdefault(item['unit_id'], item)
            if old != item:
                raise ContractError('offline viewer shard projections disagree')
    for fingerprint, entry in index['scopes'].items():
        if (scope_fingerprint(entry['scope']) != fingerprint or
                entry['scope']['fingerprint'] != fingerprint or
                entry['scope']['library_revision'] != library['revision'] or
                entry['scope']['review_revision'] != current_revision):
            raise ContractError('offline viewer scope fingerprint changed')
        eligible = {item['unit_id'] for item in entry['scope']['eligible']}
        if entry['no_content'] != (not eligible):
            raise ContractError('offline viewer no-content flag disagrees')
        shard_units = set()
        for shard_id in entry['shard_ids']:
            members = set(index['shards'][shard_id]['unit_ids'])
            if not members.issubset(eligible):
                raise ContractError('offline viewer scope shard contains excluded text')
            shard_units.update(members)
        if shard_units != eligible:
            raise ContractError('offline viewer scope shards omit eligible text')
    return library, vocabulary, review, packages, texts


def build_library_viewer(library_root, review_overlay, destination, title=None):
    """Build a fresh static site; never modify the library or legacy Ford path."""
    current_overlay = _review_revision(review_overlay)
    current_revision = current_overlay['revision']
    generation, index = open_current(library_root,
                                     current_review_revision=current_revision)
    if os.path.commonpath((os.path.realpath(generation),
                           os.path.realpath(review_overlay))) == os.path.realpath(generation):
        raise ContractError('current review overlay must be outside the immutable generation')
    library, vocabulary, review, packages, texts = _verified_export(
        generation, index, current_revision)
    if review != current_overlay:
        raise ContractError('current review overlay differs from the published snapshot')
    destination = os.path.abspath(destination)
    parent = os.path.dirname(destination)
    if (os.path.lexists(destination) or not os.path.isdir(parent) or
            os.path.islink(parent) or
            os.path.commonpath((os.path.realpath(library_root),
                                os.path.realpath(destination))) == os.path.realpath(library_root)):
        raise ContractError('offline viewer output must be fresh and outside the library')
    name = title.strip() if title and title.strip() else 'Service Manual Library'
    staging = tempfile.mkdtemp(prefix='.sme-library-viewer-', dir=parent)
    try:
        _copy_shell(staging, name)
        for relative in ('data', 'data/shards', 'content/manual-unit'):
            os.makedirs(os.path.join(staging, relative), exist_ok=True)
        _write_json(os.path.join(staging, 'data', 'library-index.json'), index)
        _write_json(os.path.join(staging, 'data', 'vocabulary.json'), vocabulary)
        for shard in index['shards'].values():
            source = _local_file(generation, shard['path'])
            target = os.path.join(staging, 'data', shard['path'])
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)

        books = []
        units = {}
        metadata_units = set()
        copied_assets = {}
        for occurrence, package in packages:
            manifest, content, evidence = (package['manifest'], package['content'],
                                           package['evidence'])
            records = json.loads(json.dumps(content['documents']))
            record_map = {item['id']: item for item in records}
            manifest_docs = {item['id']: item for publication in manifest['publications']
                             for item in publication['documents']}
            document_publications = {item['id']: publication['id']
                                     for publication in manifest['publications']
                                     for item in publication['documents']}
            routes = {item['document_id']: item['id'] for item in evidence['units']
                      if item['search']['state'] != 'metadata_only' or
                      'parent_unit_id' not in item} if evidence else {}
            asset_urls = _prepare_assets(package['root'], staging, records, copied_assets)
            for publication in manifest['publications']:
                book_id = _site_id(occurrence['occurrence_id'], publication['id'])
                navigation = []
                count = 0
                if evidence:
                    for unit in evidence['units']:
                        document_id = unit['document_id']
                        metadata_only = unit['search']['state'] == 'metadata_only'
                        if (document_publications[document_id] != publication['id'] or
                                (unit['id'] not in texts and (not metadata_only or
                                                             'parent_unit_id' in unit))):
                            continue
                        if metadata_only:
                            metadata_units.add(unit['id'])
                        count += 1
                        record = record_map[document_id]
                        document = manifest_docs[document_id]
                        labels = [value for value in
                                  (record.get('breadcrumbs') or document.get('breadcrumbs') or [])
                                  if value]
                        labels.append(document['title'])
                        if _navigation_target(navigation, labels) not in (None, unit['id']):
                            labels[-1] += ' · ' + unit['citation']['path']
                            if _navigation_target(navigation, labels) not in (None, unit['id']):
                                labels[-1] += ' · ' + unit['id'][-8:]
                        _nav_insert(navigation, labels, unit['id'])
                        existing = units.get(unit['id'])
                        if existing:
                            if book_id not in existing['books']:
                                existing['books'].append(book_id)
                            continue
                        fragment = os.path.join(staging, 'content', 'manual-unit',
                                                unit['id'] + '.html')
                        if unit['search']['state'] == 'whole' or metadata_only:
                            body = ''.join(_render_node(node, record, document_publications,
                                                        asset_urls, routes)
                                           for node in record['structure'])
                            if not body.strip():
                                body = '<pre class="source-projection">' + html.escape(
                                    record['text'] if metadata_only else
                                    texts[unit['id']]['text']) + '</pre>'
                        else:
                            body = '<pre class="source-projection">' + html.escape(
                                texts[unit['id']]['text']) + '</pre>'
                        with open(fragment, 'x', encoding='utf-8') as stream:
                            stream.write(body)
                        units[unit['id']] = {
                            'title': document['title'], 'books': [book_id],
                            'publication_title': publication['title'],
                            'publication_kind': publication['kind'],
                            'citation': unit['citation'],
                            'source_url': record.get('source_url'),
                            'provenance': document['text']['provenance'],
                            'path': record['original_path'],
                            'warnings': record['warnings'],
                            'metadata_only': metadata_only,
                            'mixed_content': unit['mixed_content'],
                        }
                books.append({'id': book_id, 'name': publication['title'],
                              'kind': publication['kind'],
                              'source_path': publication['source_path'],
                              'occurrence_id': occurrence['occurrence_id'],
                              'units': count, 'navigation': navigation})
        if set(units) - metadata_units != set(texts):
            raise ContractError('offline viewer could not bind every search unit')
        built = datetime.now(timezone.utc).isoformat(timespec='seconds')
        _write_json(os.path.join(staging, 'data', 'manifest.json'), {
            'viewerMode': 'library', 'title': name, 'books': books,
            'libraryRevision': library['revision'],
            'reviewRevision': review['revision'], 'builtAt': built,
            'counts': {'books': len(books), 'searchable': len(texts),
                       'unsearchable_originals': len(metadata_units)},
        })
        _write_json(os.path.join(staging, 'data', 'unit-details.json'), units)
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {'ok': True, 'output': destination, 'publications': len(books),
            'units': len(texts), 'unsearchable_originals': len(metadata_units),
            'library_revision': library['revision'],
            'review_revision': review['revision']}
