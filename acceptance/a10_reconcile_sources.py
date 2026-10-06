"""Reconcile old Ford citations and derived hashes against the real A10 export."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from sme.ford_adapter import BRIDGE_NAME, resolve_legacy_citation
from sme.library_export import open_current
from sme.normalize import CONTENT_NAME
from sme.source import INVENTORY_NAME, MANIFEST_NAME


def read(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def sha(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def reconcile(root, review, baseline):
    generation, index = open_current(root, current_review_revision=review['revision'])
    folder = Path(generation)
    library = read(folder / 'library.json')
    bridges = []
    originals = 0
    derived = set()
    retained_members = {}
    report = {'library_revision': index['library_revision'], 'packages': []}
    for occurrence in library['packages']:
        package = folder / occurrence['root']
        manifest = read(package / MANIFEST_NAME)
        inventory = read(package / INVENTORY_NAME)
        content = read(package / CONTENT_NAME)
        for member in inventory['members']:
            if sha(package / member['path']) != member['sha256']:
                raise AssertionError(f'original hash changed: {member["path"]}')
            originals += 1
            parts = Path(member['path']).parts
            if len(parts) >= 2:
                retained_members.setdefault((parts[-2].casefold(), parts[-1].casefold()),
                                             []).append(member['sha256'])
        for record in content['documents']:
            for asset in record['figures']:
                if asset.get('render_sha256'):
                    path = package / asset['render_path']
                    if path not in derived:
                        if sha(path) != asset['render_sha256']:
                            raise AssertionError(f'derived asset hash changed: {path}')
                        derived.add(path)
        bridge_path = package / BRIDGE_NAME
        if bridge_path.is_file():
            bridge = read(bridge_path)
            bridges.append(bridge)
            docs = [doc for pub in manifest['publications'] for doc in pub['documents']]
            if {item['document_id'] for item in bridge['references']} != {
                    doc['id'] for doc in docs}:
                raise AssertionError('Ford bridge omitted a normalized document')
            report['packages'].append({'source_id': occurrence['source_id'],
                                       'documents': len(docs),
                                       'bridge_citations': len(bridge['references']),
                                       'citation_kinds': dict(Counter(
                                           doc['citations'][0]['kind'] for doc in docs))})
    candidates = {}
    for bridge in bridges:
        for item in bridge['references']:
            key = (item['legacy_book_key'].casefold(),
                   item['legacy_relative_path'].casefold())
            candidates.setdefault(key, []).append((bridge, item))
    connection = sqlite3.connect(f'file:{baseline}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute('SELECT d.id,d.source_key,d.path,d.metadata_json,'
                              'b.source_key AS book_key FROM documents d '
                              'JOIN books b ON b.id=d.book_id').fetchall()
    missing = []
    exact = 0
    page_expansions = 0
    metadata_retained = []
    for row in rows:
        locator = Path(row['path'] or row['source_key']).name
        found = candidates.get((row['book_key'].casefold(), locator.casefold()), [])
        if not found:
            # The old wiring reader uses source_key rather than the local SVG path.
            found = candidates.get((row['book_key'].casefold(),
                                    row['source_key'].casefold()), [])
        if not found:
            hashes = retained_members.get((row['book_key'].casefold(), locator.casefold()), [])
            if (Path(locator).suffix.casefold() == '.xml' and row['path'] and
                    Path(row['path']).is_file() and sha(row['path']) in hashes):
                metadata_retained.append({'id': row['id'], 'book': row['book_key'],
                                          'locator': locator,
                                          'disposition': 'original XML retained byte-for-byte; '
                                          'not a searchable manual page'})
                continue
            missing.append({'id': row['id'], 'book': row['book_key'], 'locator': locator})
            continue
        ids = set()
        for bridge, item in found:
            resolved = resolve_legacy_citation(
                bridge, item['legacy_book_key'], item['legacy_relative_path'],
                page=item['legacy_page'])
            ids.add(resolved['document_id'])
        exact += 1
        page_expansions += max(0, len(ids) - 1)
    connection.close()
    report.update({'original_members_verified': originals,
                   'unique_derived_assets_verified': len(derived),
                   'legacy_documents': len(rows), 'legacy_documents_resolved': exact,
                   'additional_page_resolutions': page_expansions,
                   'legacy_metadata_originals_retained': metadata_retained,
                   'missing_legacy_citations': missing})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    parser.add_argument('review')
    parser.add_argument('baseline_database')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = reconcile(args.library, read(args.review), args.baseline_database)
    with open(args.output, 'x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: len(value) if isinstance(value, list) else value
                      for key, value in result.items()}, indent=2))
    if result['missing_legacy_citations']:
        raise SystemExit('old Ford citations need explicit reconciliation')


if __name__ == '__main__':
    main()
