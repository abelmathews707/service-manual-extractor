"""Inventory one mixed outer folder without modifying its source files."""

import os

from fsd.arc import ArcError
from fsd.disc import DiscError
from fsd.iso import IsoError

from .ford_adapter import probe_ford
from .source import SourceError, inspect_source

DISCOVERY_CONTRACT = 'service-manual-discovery/v1'
_DISC_IMAGES = ('.iso', '.img', '.bin', '.mdf', '.nrg')


def discover_folder(root):
    """Route immediate children, leaving unsupported inputs visible by name.

    A Ford disc is recognized by its ``content`` archive tree before generic
    directory scanning. Ordinary HTML/PDF folders, ZIPs and standalone PDFs
    use the existing neutral source inspector; the Ford EPL parser is never
    invoked for those neutral inputs.
    """
    absolute = os.path.abspath(root)
    if os.path.islink(root) or not os.path.isdir(absolute):
        raise SourceError('discovery root must be a regular directory')
    sources = []
    for name in sorted(os.listdir(absolute), key=str.casefold):
        path = os.path.join(absolute, name)
        item = {'name': name, 'path': path, 'status': 'unsupported',
                'route': None, 'publications': 0, 'reason': None}
        if os.path.islink(path):
            item['reason'] = 'symbolic links are not followed'
        elif os.path.isdir(path) and _has_ford_content_tree(path):
            try:
                found = probe_ford(path)
                item.update(status='recognized', route='ford-import',
                            publications=len(found['archives']),
                            archives=found['archives'])
            except (OSError, ValueError, ArcError, DiscError, IsoError) as error:
                item.update(status='failed', reason=str(error))
        elif os.path.isfile(path) and name.casefold().endswith(_DISC_IMAGES):
            try:
                found = probe_ford(path)
                item.update(status='recognized', route='ford-import',
                            publications=len(found['archives']),
                            archives=found['archives'])
            except (OSError, ValueError, ArcError, DiscError, IsoError) as error:
                item.update(status='failed', reason=str(error))
        elif os.path.isdir(path) or name.casefold().endswith(('.zip', '.pdf')):
            try:
                found = inspect_source(path)
                item.update(status='recognized' if found.status == 'complete' else found.status,
                            route='extract', publications=len(found.publications),
                            format=found.format, source_id=found.source_id,
                            failures=found.failures)
            except (OSError, SourceError) as error:
                item['reason'] = str(error)
        else:
            item['reason'] = 'unsupported top-level file type'
        sources.append(item)
    return {'contract': DISCOVERY_CONTRACT, 'root': absolute, 'sources': sources,
            'counts': {state: sum(item['status'] == state for item in sources)
                       for state in ('recognized', 'partial', 'failed', 'unsupported')}}


def _has_ford_content_tree(path):
    content = os.path.join(path, 'content')
    if not os.path.isdir(content) or os.path.islink(content):
        return False
    for directory, dirs, files in os.walk(content):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(directory, name))]
        if any(name.casefold().endswith('.arc') and
               not os.path.islink(os.path.join(directory, name)) for name in files):
            return True
    return False
