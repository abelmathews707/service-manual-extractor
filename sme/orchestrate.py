"""Run recognized inputs from one outer folder into version-keyed packages."""

import hashlib
import json
import os

from fsd.disc import open_source

from .contract import load_manifest, source_id
from .discovery import discover_folder
from .ford_adapter import _archive_info, _selected, import_ford
from .normalize import CONTENT_NAME, _local_file, digest, normalize_source, validate_content
from .source import (
    INVENTORY_NAME,
    MANIFEST_NAME,
    SourceError,
    _sha_file,
    extract_source,
    inspect_source,
    validate_inventory,
)


def _transform_revision(ford=False):
    root = os.path.dirname(os.path.dirname(__file__))
    files = ['sme/normalize.py', 'sme/html_content.py', 'sme/pdf_content.py',
             'sme/contract.py']
    if ford:
        files += ['sme/ford_adapter.py', 'fsd/arc.py', 'fsd/disc.py',
                  'fsd/build.py', 'fsd/extract.py']
    sha = hashlib.sha256()
    for relative in files:
        sha.update(relative.encode() + b'\0')
        with open(os.path.join(root, relative), 'rb') as stream:
            while block := stream.read(1024 * 1024):
                sha.update(block)
    return sha.hexdigest()[:12]


def _verify_cached_package(path, expected_source_id):
    manifest = load_manifest(_local_file(path, MANIFEST_NAME))
    if manifest['source']['id'] != expected_source_id:
        raise SourceError(f'cached package has the wrong source ID: {path}')
    with open(_local_file(path, CONTENT_NAME), encoding='utf-8') as stream:
        validate_content(json.load(stream), manifest)
    with open(_local_file(path, INVENTORY_NAME), encoding='utf-8') as stream:
        inventory = validate_inventory(json.load(stream))
    if inventory['source_id'] != expected_source_id:
        raise SourceError(f'cached inventory has the wrong source ID: {path}')
    for member in inventory['members']:
        if _sha_file(_local_file(path, member['path'])) != member['sha256']:
            raise SourceError(f'cached original changed: {member["path"]}')
    return len(manifest['publications'])


def _ford_source_id(path, identities):
    with open_source(path) as source:
        refs, _ = _selected(source, identities)
        infos = [_archive_info(ref) for ref in refs]
        versions = {item['version'] for item in infos}
        if len(versions) != 1:
            raise SourceError('Ford orchestration mixed POD generations')
        source_hash = digest(json.dumps([(item['identity'], item['sha256'])
                                         for item in infos], sort_keys=True).encode())
        format_ = f'ford_tsp_disc_v{versions.pop()}'
        container = 'directory' if source.kind == 'directory' else 'disc_image'
        identity = source.label + ':' + ','.join(item['identity'] for item in infos)
        return source_id(format_, container, identity, source_hash)


def process_folder(outer, destination, include_names=None, ford_archives=None):
    """Build or verify each selected source package; never replace old output.

    ``include_names`` narrows the immediate child names. ``ford_archives`` maps
    a Ford child name to exact archive identities; omission selects all. Mixed
    POD v1/v2 archives become separate packages. Unsupported/partial sources
    stay in the report rather than disappearing from the library inventory.
    """
    found = discover_folder(outer)
    selected = set(include_names or [item['name'] for item in found['sources']])
    known = {item['name'] for item in found['sources']}
    if selected - known:
        raise SourceError('unknown outer-folder item(s): ' + ', '.join(sorted(selected - known)))
    if ford_archives and set(ford_archives) - selected:
        raise SourceError('Ford archive selection names an unselected child')
    if ford_archives and any(next(item for item in found['sources']
                                 if item['name'] == name)['route'] != 'ford-import'
                             for name in ford_archives):
        raise SourceError('Ford archive selection names a non-Ford child')
    target = os.path.abspath(destination)
    if os.path.islink(destination) or (os.path.lexists(target) and not os.path.isdir(target)):
        raise SourceError('package cache must be a regular directory')
    if os.path.commonpath((os.path.abspath(outer), target)) == os.path.abspath(outer):
        raise SourceError('package cache may not be inside the source folder')
    os.makedirs(target, exist_ok=True)
    verified_root = os.path.join(target, 'verified')
    packages_root = os.path.join(target, 'packages')
    if os.path.islink(verified_root) or os.path.islink(packages_root):
        raise SourceError('package cache subdirectories may not be symbolic links')
    os.makedirs(verified_root, exist_ok=True)
    os.makedirs(packages_root, exist_ok=True)
    results = []
    for item in found['sources']:
        if item['name'] not in selected:
            continue
        if item['status'] != 'recognized':
            results.append({'name': item['name'], 'status': item['status'],
                            'reason': item.get('reason') or item.get('failures'),
                            'packages': []})
            continue
        packages = []
        if item['route'] == 'ford-import':
            available = {archive['identity'].casefold(): archive['identity']
                         for archive in item['archives']}
            requested = ((ford_archives or {}).get(item['name']) or
                         [archive['identity'] for archive in item['archives']])
            allowed = {available.get(identity.casefold()) for identity in requested}
            if not allowed or None in allowed:
                raise SourceError(f'unknown or empty Ford archive selection: {item["name"]}')
            for version in sorted({archive['version'] for archive in item['archives']
                                   if archive['identity'] in allowed}):
                identities = [archive['identity'] for archive in item['archives']
                              if archive['identity'] in allowed and
                              archive['version'] == version]
                identifier = _ford_source_id(item['path'], identities)
                path = os.path.join(packages_root,
                                    identifier + '-' + _transform_revision(ford=True))
                if os.path.isdir(path):
                    count = _verify_cached_package(path, identifier)
                    packages.append({'path': path, 'source_id': identifier,
                                     'publications': count, 'cached': True})
                else:
                    built = import_ford(item['path'], path, identities)
                    packages.append({'path': path, 'source_id': identifier,
                                     'publications': built['publications'],
                                     'cached': False, 'failures': built['failures']})
        else:
            source = inspect_source(item['path'])
            if source.status != 'complete':
                results.append({'name': item['name'], 'status': source.status,
                                'reason': source.failures, 'packages': []})
                continue
            identifier = source.source_id
            extracted = os.path.join(verified_root, identifier)
            package = os.path.join(packages_root,
                                   identifier + '-' + _transform_revision())
            if os.path.isdir(package):
                count = _verify_cached_package(package, identifier)
                packages.append({'path': package, 'source_id': identifier,
                                 'publications': count, 'cached': True})
            else:
                if not os.path.isdir(extracted):
                    operation = extract_source(item['path'], extracted)
                    if not operation['ok']:
                        raise SourceError(f'extraction became partial: {item["name"]}')
                built = normalize_source(extracted, package)
                packages.append({'path': package, 'source_id': identifier,
                                 'publications': len(source.publications),
                                 'cached': False, 'failures': built['failures']})
        results.append({'name': item['name'], 'status': 'processed',
                        'reason': None, 'packages': packages})
    return {'contract': 'service-manual-processing/v1', 'root': found['root'],
            'destination': target, 'results': results,
            'unsupported': [item['name'] for item in found['sources']
                            if item['status'] != 'recognized']}
