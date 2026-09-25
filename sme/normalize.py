"""Normalize a verified Step 3 extraction into a self-contained, cited package."""
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile

from .contract import (
    asset_id,
    canonical_path,
    document_id,
    validate_manifest,
)
from .html_content import SAFE_TAGS, parse_html, safe_svg
from .pdf_content import load_ocr_entry, page_content, pdf_text_pages, title_and_kind
from .source import INVENTORY_NAME, MANIFEST_NAME, SourceError, validate_inventory

CONTENT_CONTRACT = 'service-manual-content/v1'
CONTENT_NAME = '.sme-content.json'
DERIVED = '.sme-derived'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _write_json(path, value):
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def _local_file(root, relative):
    if canonical_path(relative) != relative or '\\' in relative:
        raise SourceError(f'non-canonical package path: {relative!r}')
    current = root
    for part in relative.split('/'):
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise SourceError(f'package path contains a symbolic link: {relative}')
    if not stat.S_ISREG(os.stat(current, follow_symlinks=False).st_mode):
        raise SourceError(f'package member is not a regular file: {relative}')
    return current


def _copy_verified(root, staging, member):
    source = _local_file(root, member['path'])
    target = os.path.join(staging, *member['path'].split('/'))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    sha = hashlib.sha256()
    size = 0
    with open(source, 'rb') as incoming, open(target, 'xb') as outgoing:
        while True:
            block = incoming.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > member['size']:
                raise SourceError(f'package member grew after inspection: {member["path"]}')
            sha.update(block)
            outgoing.write(block)
    if size != member['size'] or sha.hexdigest() != member['sha256']:
        raise SourceError(f'package member hash/size changed: {member["path"]}')


def _base_document(publication, path, original, title, citations, text):
    return {'id': document_id(publication['id'], path), 'path': path, 'title': title,
            'content_sha256': original['sha256'], 'text': text, 'citations': citations,
            'applicability': [], 'references': [], 'assets': [], 'breadcrumbs': []}


def _content_record(document, publication, original_path, text, role, **extra):
    return dict(id=document['id'], publication_id=publication['id'],
                original_path=original_path, role=role, text=text,
                search_eligible=bool(text) and role in {'procedure', 'pdf_page'},
                structure=[], references=[], figures=[], anchors=[], navigation=[],
                same_text_ids=[], context_alias_ids=[], warnings=[], **extra)


def _asset(document, member, caption):
    return {'id': asset_id(document['id'], member['path']), 'path': member['path'],
            'sha256': member['sha256'], 'media_type': member['media_type'],
            'caption': caption}


def _prepare_figures(document, content, members, staging):
    seen = set()
    for figure in content['figures']:
        path = figure['path']
        if figure['status'] == 'blocked':
            continue
        member = members.get(path)
        if not member:
            figure.update(status='missing', reason='asset absent from verified selection')
            continue
        if path not in seen:
            document['assets'].append(_asset(document, member, figure['caption']))
            seen.add(path)
        figure['sha256'] = member['sha256']
        local = os.path.join(staging, *path.split('/'))
        with open(local, 'rb') as stream:
            header = stream.read(32)
        if path.casefold().endswith('.svg'):
            try:
                with open(local, 'rb') as stream:
                    sanitized = safe_svg(stream.read(16 * 1024 * 1024 + 1))
                safe_path = f'{DERIVED}/{digest(sanitized)}.svg'
                os.makedirs(os.path.join(staging, DERIVED), exist_ok=True)
                with open(os.path.join(staging, safe_path), 'wb') as stream:
                    stream.write(sanitized)
                figure.update(status='safe_svg', reason=None, render_path=safe_path,
                              render_sha256=digest(sanitized))
            except SourceError as ex:
                figure.update(status='unsupported', reason=str(ex))
        elif ((member['media_type'] == 'image/png' and header.startswith(b'\x89PNG\r\n\x1a\n'))
              or (member['media_type'] == 'image/jpeg' and header.startswith(b'\xff\xd8\xff'))
              or (member['media_type'] == 'image/gif' and header[:6] in
                  {b'GIF87a', b'GIF89a'})):
            figure.update(status='raster', reason=None, render_path=path,
                          render_sha256=member['sha256'])
        else:
            figure.update(status='unsupported', reason='unsupported image type or signature')


def _resolve_links(manifest, records, members, known_paths):
    docs = {doc['id']: doc for pub in manifest['publications'] for doc in pub['documents']}
    by_path = {record['original_path']: record for record in records
               if record['role'] != 'pdf_page'}
    for content in records:
        document = docs[content['id']]
        for link in content['references']:
            if link['status'] == 'blocked':
                continue
            path = link['path']
            target = by_path.get(path)
            if target and target['role'] == 'unavailable':
                link.update(status='unavailable_by_source', reason='publisher omitted this content')
            elif (target and link['fragment'] and link['fragment'] not in target['anchors']
                  and link['source_fragment'] not in target['anchors']):
                link.update(status='missing', reason='target fragment is absent')
            elif target:
                link.update(status='resolved', reason=None, target_id=target['id'])
                if link['fragment']:
                    link['target_fragment'] = link['fragment'] if link['fragment'] in (
                        target['anchors']) else link['source_fragment']
            elif path in members:
                link.update(status='unsupported', reason='target is not a normalized HTML document')
            elif path in known_paths:
                link.update(status='outside_selection',
                            reason='verified source inventory places target outside selection')
            else:
                link.update(status='missing', reason='target absent from verified selection')
            # v1 manifest has a smaller vocabulary; full classifications stay in the sidecar.
            status = link['status'] if link['status'] != 'unsupported' else 'missing'
            ref = {'path': path, 'status': status}
            if status == 'resolved':
                ref['target_id'] = link['target_id']
            else:
                ref['reason'] = link['reason']
            if ref not in document['references']:
                document['references'].append(ref)
    # Preserve every navigation route independently, including aliases for one target.
    for content in records:
        for route in content['navigation']:
            index = route['reference']
            if index is None:
                continue
            link = content['references'][index]
            if link['status'] == 'resolved':
                target = by_path[link['path']]
                target.setdefault('navigation_routes', []).append({
                    'source_path': content['original_path'], 'labels': route['labels'],
                    'fragment': link['fragment'],
                })
                if not docs[target['id']]['breadcrumbs']:
                    docs[target['id']]['breadcrumbs'] = route['labels']


def _aliases(manifest, records):
    docs = {doc['id']: doc for pub in manifest['publications'] for doc in pub['documents']}
    groups = {}
    for content in records:
        if content['role'] != 'procedure' or not content['text']:
            continue
        key = (content['publication_id'], digest(content['text'].encode()))
        groups.setdefault(key, []).append(content)
    for group in groups.values():
        contexts = {}
        for content in group:
            doc = docs[content['id']]
            context = {'breadcrumbs': doc['breadcrumbs'], 'title': doc['title'],
                       'applicability': [(x['level'], x['statement'])
                                         for x in doc['applicability']],
                       'figures': [(f['caption'], f.get('sha256')) for f in content['figures']],
                       'structure': content['structure'],
                       'links': [(r['path'], r['fragment']) for r in content['references']]}
            key = digest(json.dumps(context, sort_keys=True).encode())
            contexts.setdefault(key, []).append(content['id'])
            content['same_text_ids'] = sorted(c['id'] for c in group if c is not content)
        for ids in contexts.values():
            for content in group:
                if content['id'] in ids:
                    content['context_alias_ids'] = sorted(i for i in ids if i != content['id'])


def _html_publication(publication, member_paths, members, staging, records, failures):
    for path in member_paths:
        if not path.casefold().endswith(('.html', '.htm')):
            continue
        member = members[path]
        try:
            with open(os.path.join(staging, *path.split('/')), 'rb') as stream:
                parsed = parse_html(stream.read(32 * 1024 * 1024 + 1), path)
            text = parsed['text']
            text_info = {'provenance': 'native', 'sha256': digest(text.encode())} if text else {
                'provenance': 'none'}
            doc = _base_document(publication, path, member, parsed['title'],
                                 [{'kind': 'path', 'path': path}], text_info)
            doc['applicability'] = parsed.pop('applicability')
            doc['breadcrumbs'] = parsed.pop('breadcrumbs')
            parsed.pop('title')
            role = parsed.pop('role')
            parsed.pop('text')
            content = _content_record(doc, publication, path, text, role)
            content.update(parsed)
            _prepare_figures(doc, content, members, staging)
            publication['documents'].append(doc)
            records.append(content)
            if path == publication['source_path']:
                publication['title'] = doc['title']
                publication['applicability'] = [dict(item, level='publication')
                                                for item in doc['applicability']]
        except (OSError, SourceError, ValueError, RecursionError) as ex:
            failures.append({'path': path, 'code': 'html_normalization_failed', 'message': str(ex)})
    entry = next((r for r in records if r['original_path'] == publication['source_path']), None)
    if entry:
        for record in records:
            if (record['publication_id'] == publication['id'] and
                    record.get('visible_text_sha256') == entry['visible_text_sha256']):
                record.update(role='landing', text='', search_eligible=False)
                doc = next(d for d in publication['documents'] if d['id'] == record['id'])
                doc['text'] = {'provenance': 'none'}


def _pdf_publication(publication, member, staging, records, ocr, ocr_base):
    path = member['path']
    native, warnings = pdf_text_pages(os.path.join(staging, *path.split('/')),
                                      member['page_count'])
    derived = None
    if ocr:
        derived, derived_warnings = load_ocr_entry(ocr, member, ocr_base)
        warnings.extend(derived_warnings)
    first = native[0] or (derived[0] if derived else '')
    publication['title'], publication['kind'] = title_and_kind(first)
    for number, native_text in enumerate(native, 1):
        text = native_text or (derived[number - 1] if derived else '')
        provenance = 'native' if native_text else ('ocr' if text else 'none')
        metadata, applicability = page_content(
            text, member, number, provenance, ocr['tool'] if ocr else None)
        # Logical record paths are distinct from original citation paths and never opened.
        logical = f'{DERIVED}/pages/{publication["id"]}/{number:06d}'
        doc = _base_document(publication, logical, member,
                             f'{publication["title"]} — page {number}',
                             [{'kind': 'page', 'path': path, 'page': number}], metadata)
        doc['applicability'] = applicability
        doc['assets'] = [_asset(doc, member, f'Original PDF page {number}')]
        content = _content_record(doc, publication, path, text, 'pdf_page', page=number)
        content['warnings'] = warnings if number == 1 else []
        content['figures'] = [{'path': path, 'page': number, 'status': 'original_pdf_page',
                               'caption': f'Original PDF page {number}',
                               'sha256': member['sha256']}]
        if provenance == 'ocr':
            content['ocr'] = {key: ocr[key] for key in
                              ('source_sha256', 'derived_sha256', 'page_count', 'tool')}
        if not text:
            content['warnings'].append('no_searchable_text: original page remains available')
        publication['documents'].append(doc)
        records.append(content)
        if number == 1:
            publication['applicability'] = [dict(item, level='publication')
                                            for item in applicability]


def validate_content(value, manifest):
    if not isinstance(value, dict) or set(value) != {
            'contract', 'source_id', 'status', 'failures', 'documents'}:
        raise SourceError('invalid content envelope')
    if value['contract'] != CONTENT_CONTRACT or value['source_id'] != manifest['source']['id']:
        raise SourceError('content contract/source does not match the manifest')
    if value['status'] not in {'complete', 'partial'} or bool(value['failures']) != (
            value['status'] == 'partial'):
        raise SourceError('content status does not match failures')
    documents = {d['id']: (pub['id'], d) for pub in manifest['publications']
                 for d in pub['documents']}
    seen = set()
    for content in value['documents']:
        identifier = content['id']
        if identifier in seen or identifier not in documents:
            raise SourceError('content document ID is duplicated or absent from manifest')
        seen.add(identifier)
        publication, doc = documents[identifier]
        if publication != content['publication_id']:
            raise SourceError('content belongs to the wrong publication')
        if canonical_path(content['original_path']) != content['original_path']:
            raise SourceError('invalid original content path')
        if content['text'] and digest(content['text'].encode()) != doc['text'].get('sha256'):
            raise SourceError('content text hash differs from the manifest')
        if not content['text'] and doc['text']['provenance'] != 'none':
            raise SourceError('empty content claims searchable text')
        if content['search_eligible'] != (bool(content['text']) and content['role'] in {
                'procedure', 'pdf_page'}):
            raise SourceError('invalid search eligibility')
        if content['role'] == 'pdf_page' and doc['citations'] != [
                {'kind': 'page', 'path': content['original_path'], 'page': content['page']}]:
            raise SourceError('PDF content citation/page mismatch')
        if content['role'] not in {'procedure', 'landing', 'navigation', 'unavailable', 'pdf_page'}:
            raise SourceError('unsupported content role')
        stack = list(content['structure'])
        while stack:
            node = stack.pop()
            if isinstance(node, str):
                continue
            if not isinstance(node, dict) or set(node) != {'tag', 'attrs', 'children'} or (
                    node['tag'] not in SAFE_TAGS):
                raise SourceError('unsafe content structure node')
            attrs = node['attrs']
            if not isinstance(attrs, dict) or set(attrs) - {
                    'rowspan', 'colspan', 'reference', 'figure'}:
                raise SourceError('unsafe content structure attributes')
            for key, number in attrs.items():
                if type(number) is not int or number < 0:
                    raise SourceError('invalid structure attribute number')
                if key in {'rowspan', 'colspan'} and not 1 <= number <= 1000:
                    raise SourceError('invalid table span')
                if key == 'reference' and number >= len(content['references']):
                    raise SourceError('structure reference is out of range')
                if key == 'figure' and number >= len(content['figures']):
                    raise SourceError('structure figure is out of range')
            if not isinstance(node['children'], list):
                raise SourceError('structure children must be an array')
            stack.extend(node['children'])
        for reference in content['references']:
            if reference['status'] not in {'resolved', 'missing', 'outside_selection',
                                            'unavailable_by_source', 'blocked', 'unsupported'}:
                raise SourceError('unclassified content reference')
            if reference['status'] == 'resolved' and reference.get('target_id') not in documents:
                raise SourceError('resolved content reference has no target')
            if reference['status'] != 'resolved' and not reference.get('reason'):
                raise SourceError('unresolved content reference must retain a reason')
        for figure in content['figures']:
            if figure['status'] not in {'safe_svg', 'raster', 'original_pdf_page',
                                         'missing', 'unsupported', 'blocked'}:
                raise SourceError('unclassified figure')
            if figure['status'] in {'safe_svg', 'raster'}:
                if canonical_path(figure['render_path']) != figure['render_path']:
                    raise SourceError('unsafe figure rendering path')
                if figure['status'] == 'safe_svg' and not figure['render_path'].startswith(
                        DERIVED + '/'):
                    raise SourceError('safe SVG must reference a sanitized derivative')
        for key in ('same_text_ids', 'context_alias_ids'):
            if any(target not in documents or target == identifier for target in content[key]):
                raise SourceError('alias points to an absent or identical document')
    if seen != set(documents):
        raise SourceError('manifest document is missing its content')
    return value


def normalize_source(extracted, destination, ocr_manifest=None, source_inventory=None):
    """Verify, copy and normalize into a fresh output; never alter the extraction."""
    root = os.path.abspath(extracted)
    if os.path.islink(root) or not os.path.isdir(root):
        raise SourceError('normalization input must be a regular extracted directory')
    manifest = validate_manifest(_json(_local_file(root, MANIFEST_NAME)))
    inventory = validate_inventory(_json(_local_file(root, INVENTORY_NAME)))
    if manifest['source']['status'] != 'complete':
        raise SourceError('partial source cannot be normalized as a verified source')
    if manifest['source']['id'] != inventory['source_id']:
        raise SourceError('inventory source identity differs from manifest')
    if manifest['source']['format'] not in {'workshop_manuals_html_v1', 'pdf_collection_v1'}:
        raise SourceError('normalization is unsupported for this source format')
    if any(pub['documents'] for pub in manifest['publications']):
        raise SourceError('input has already been normalized; use the Step 3 extraction')
    members = {m['path']: m for m in inventory['members']}
    if manifest['source']['format'] == 'pdf_collection_v1' and any(
            type(m.get('page_count')) is not int or m['page_count'] < 1
            for m in members.values()):
        raise SourceError('PDF inventory is missing verified page counts')
    for path in members:
        if path.split('/')[0].casefold() in {CONTENT_NAME, DERIVED}:
            raise SourceError('source conflicts with reserved normalization metadata paths')
    selections = {p['id']: p for p in inventory['publications']}
    if set(selections) != {p['id'] for p in manifest['publications']}:
        raise SourceError('inventory publication selection differs from manifest')
    owned = set()
    for pub in manifest['publications']:
        selection = selections[pub['id']]
        if selection['source_path'] != pub['source_path']:
            raise SourceError('inventory publication path differs from manifest')
        paths = set(selection['member_paths'])
        if pub['source_path'] not in paths or owned & paths:
            raise SourceError('publication paths are absent or overlap')
        if manifest['source']['format'] == 'pdf_collection_v1' and paths != {pub['source_path']}:
            raise SourceError('PDF publication must contain exactly its original file')
        owned.update(paths)
    if owned != set(members):
        raise SourceError('inventory contains unassigned members')
    known_paths = set(members)
    if source_inventory:
        full = validate_inventory(_json(source_inventory))
        if (full['source_id'] != inventory['source_id'] or
                full['source_content_sha256'] != inventory['source_content_sha256']):
            raise SourceError('reference inventory identifies a different source')
        known_members = {m['path']: m for m in full['members']}
        if any(known_members.get(p) != member for p, member in members.items()):
            raise SourceError('reference inventory does not match selected files')
        known_paths = set(known_members)
    ocr_entries = {}
    ocr_base = os.getcwd()
    if ocr_manifest:
        mapping = _json(ocr_manifest)
        if not isinstance(mapping, dict) or set(mapping) != {'contract', 'entries'} or (
                mapping['contract'] != 'service-manual-ocr-map/v1'):
            raise SourceError('unsupported OCR map contract')
        ocr_base = os.path.dirname(os.path.abspath(ocr_manifest))
        if not isinstance(mapping['entries'], list):
            raise SourceError('OCR mapping entries must be an array')
        for entry in mapping['entries']:
            if not isinstance(entry, dict):
                raise SourceError('OCR mapping entry must be an object')
            path = entry.get('source_path')
            if path not in members or path in ocr_entries:
                raise SourceError('OCR mapping references an absent or duplicate source path')
            ocr_entries[path] = entry
    destination = os.path.abspath(destination)
    parent = os.path.dirname(destination)
    if os.path.lexists(destination) or not os.path.isdir(parent) or os.path.islink(parent):
        raise SourceError('output must be fresh with an existing regular parent directory')
    real_root, real_out = os.path.realpath(root), os.path.realpath(destination)
    try:
        inside = os.path.commonpath((real_root, real_out)) == real_root
    except ValueError:
        inside = False
    if inside:
        raise SourceError('normalization output may not be inside the input')
    staging = tempfile.mkdtemp(prefix=f'.{os.path.basename(destination)}.sme-', dir=parent)
    manifest = copy.deepcopy(manifest)
    records, failures = [], []
    try:
        for member in inventory['members']:
            _copy_verified(root, staging, member)
        for directory in inventory['empty_directories']:
            os.makedirs(os.path.join(staging, *directory.split('/')), exist_ok=True)
        for pub in manifest['publications']:
            if manifest['source']['format'] == 'workshop_manuals_html_v1':
                _html_publication(pub, selections[pub['id']]['member_paths'], members,
                                  staging, records, failures)
            else:
                try:
                    _pdf_publication(pub, members[pub['source_path']], staging, records,
                                     ocr_entries.get(pub['source_path']), ocr_base)
                except (OSError, SourceError, subprocess.SubprocessError) as ex:
                    failures.append({'path': pub['source_path'],
                                     'code': 'pdf_normalization_failed', 'message': str(ex)})
        _resolve_links(manifest, records, members, known_paths)
        _aliases(manifest, records)
        content = {'contract': CONTENT_CONTRACT, 'source_id': manifest['source']['id'],
                   'status': 'partial' if failures else 'complete', 'failures': failures,
                   'documents': records}
        validate_manifest(manifest)
        validate_content(content, manifest)
        _write_json(os.path.join(staging, MANIFEST_NAME), manifest)
        _write_json(os.path.join(staging, INVENTORY_NAME), inventory)
        _write_json(os.path.join(staging, CONTENT_NAME), content)
        if os.path.lexists(destination):
            raise SourceError('destination appeared during normalization')
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {'ok': not failures, 'status': content['status'], 'source_id': content['source_id'],
            'publications': len(manifest['publications']), 'documents': len(records),
            'searchable_documents': sum(r['search_eligible'] for r in records),
            'unresolved_references': sum(ref['status'] != 'resolved' for r in records
                                         for ref in r['references']),
            'unavailable_figures': sum(f['status'] in {'missing', 'unsupported', 'blocked'}
                                       for r in records for f in r['figures']),
            'failures': failures, 'output': destination, 'content_path': CONTENT_NAME,
            'manifest_path': MANIFEST_NAME}
