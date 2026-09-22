"""Versioned, manufacturer-neutral service-manual record contracts."""
import hashlib
import json
import re

MANIFEST_CONTRACT = 'service-manual-manifest/v1'
OPERATION_CONTRACT = 'service-manual-operation/v1'

FORMATS = (
    'ford_tsp_disc_v1',
    'ford_tsp_disc_v2',
    'workshop_manuals_html_v1',
    'pdf_collection_v1',
)
CONTAINERS = ('directory', 'zip', 'disc', 'disc_image', 'file_collection')
SOURCE_STATUSES = ('complete', 'partial', 'failed')
PUBLICATION_KINDS = (
    'workshop', 'wiring', 'diagnostics', 'owner', 'reference', 'unknown',
)
TEXT_PROVENANCE = ('native', 'ocr', 'none')
REFERENCE_STATUSES = ('resolved', 'missing', 'outside_selection', 'unavailable_by_source')
APPLICABILITY_LEVELS = ('publication', 'document', 'table', 'figure')
ID_PREFIXES = {
    'source': 'src',
    'publication': 'pub',
    'document': 'doc',
    'asset': 'asset',
}

_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_ID = re.compile(r'^(src|pub|doc|asset)_[0-9a-f]{32}$')
_DRIVE = re.compile(r'^[A-Za-z]:')


class ContractError(ValueError):
    """A record does not satisfy the versioned contract."""


def canonical_path(path):
    """Return the portable source-relative spelling used by IDs and records."""
    if not isinstance(path, str) or not path or '\x00' in path:
        raise ContractError('path must be a non-empty string without NUL bytes')
    path = path.replace('\\', '/')
    if path.startswith('/') or path.startswith('//') or _DRIVE.match(path):
        raise ContractError(f'path must be source-relative: {path!r}')
    parts = []
    for part in path.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            raise ContractError(f'path may not escape its source: {path!r}')
        if any(ord(char) < 32 for char in part):
            raise ContractError(f'path contains a control character: {path!r}')
        parts.append(part)
    if not parts:
        raise ContractError('path must identify an item below the source root')
    return '/'.join(parts)


def stable_id(kind, *parts):
    """Build the contract-v1 ID for an immutable source identity or path."""
    try:
        prefix = ID_PREFIXES[kind]
    except KeyError:
        raise ContractError(f'unknown ID kind: {kind!r}') from None
    if not parts or any(not isinstance(part, str) or not part for part in parts):
        raise ContractError('stable ID parts must be non-empty strings')
    material = ('service-manual-contract-v1', kind) + parts
    digest = hashlib.sha256('\x00'.join(material).encode('utf-8')).hexdigest()[:32]
    return f'{prefix}_{digest}'


def source_id(format_, container, identity, sha256):
    return stable_id('source', format_, container, identity, sha256)


def publication_id(source, source_path):
    return stable_id('publication', source, canonical_path(source_path))


def document_id(publication, path):
    return stable_id('document', publication, canonical_path(path))


def asset_id(document, path):
    return stable_id('asset', document, canonical_path(path))


def _fail(path, message):
    raise ContractError(f'{path}: {message}')


def _object(value, path, required, optional=()):
    if not isinstance(value, dict):
        _fail(path, 'must be an object')
    missing = set(required) - set(value)
    if missing:
        _fail(path, f'missing {", ".join(sorted(missing))}')
    extra = set(value) - set(required) - set(optional)
    if extra:
        _fail(path, f'unknown field(s): {", ".join(sorted(extra))}')


def _list(value, path):
    if not isinstance(value, list):
        _fail(path, 'must be an array')


def _string(value, path, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value):
        _fail(path, 'must be a string' if allow_empty else 'must be a non-empty string')


def _sha(value, path):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _fail(path, 'must be a lowercase SHA-256 hex digest')


def _identifier(value, path, prefix=None):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        _fail(path, 'must be a contract-v1 stable ID')
    if prefix and not value.startswith(prefix + '_'):
        _fail(path, f'must be a {prefix} ID')


def _path(value, path):
    try:
        normalized = canonical_path(value)
    except ContractError as ex:
        _fail(path, str(ex))
    if normalized != value:
        _fail(path, f'must use canonical spelling {normalized!r}')


def _failure(value, path):
    _object(value, path, ('code', 'message'), ('path',))
    _string(value['code'], f'{path}.code')
    _string(value['message'], f'{path}.message')
    if 'path' in value:
        _path(value['path'], f'{path}.path')


def _extractor(value, path):
    _object(value, path, ('name', 'version', 'revision'))
    for key in ('name', 'version', 'revision'):
        _string(value[key], f'{path}.{key}')


def _source(value, path='source'):
    required = ('id', 'format', 'container', 'identity', 'sha256', 'status',
                'failures', 'extractor')
    _object(value, path, required)
    _identifier(value['id'], f'{path}.id', 'src')
    if value['format'] not in FORMATS:
        _fail(f'{path}.format', f'unsupported format {value["format"]!r}')
    if value['container'] not in CONTAINERS:
        _fail(f'{path}.container', f'unsupported container {value["container"]!r}')
    _string(value['identity'], f'{path}.identity')
    if '\x00' in value['identity']:
        _fail(f'{path}.identity', 'may not contain NUL bytes')
    _sha(value['sha256'], f'{path}.sha256')
    if value['status'] not in SOURCE_STATUSES:
        _fail(f'{path}.status', f'must be one of {", ".join(SOURCE_STATUSES)}')
    _list(value['failures'], f'{path}.failures')
    for index, failure in enumerate(value['failures']):
        _failure(failure, f'{path}.failures[{index}]')
    if value['status'] == 'complete' and value['failures']:
        _fail(path, 'a complete source may not contain failures')
    if value['status'] != 'complete' and not value['failures']:
        _fail(path, 'a partial or failed source must explain at least one failure')
    _extractor(value['extractor'], f'{path}.extractor')
    expected = source_id(value['format'], value['container'], value['identity'],
                         value['sha256'])
    if value['id'] != expected:
        _fail(f'{path}.id', f'does not match immutable source identity; expected {expected}')


def _applicability(value, path, expected_level=None):
    _object(value, path, ('level', 'statement', 'source_path'), ('selector',))
    if value['level'] not in APPLICABILITY_LEVELS:
        _fail(f'{path}.level', f'must be one of {", ".join(APPLICABILITY_LEVELS)}')
    if expected_level and value['level'] != expected_level:
        _fail(f'{path}.level', f'must be {expected_level!r} here')
    _string(value['statement'], f'{path}.statement')
    _path(value['source_path'], f'{path}.source_path')
    if 'selector' in value:
        _string(value['selector'], f'{path}.selector')


def _citation(value, path):
    _object(value, path, ('kind', 'path'), ('fragment', 'page'))
    if value['kind'] not in ('path', 'page'):
        _fail(f'{path}.kind', 'must be path or page')
    _path(value['path'], f'{path}.path')
    if 'fragment' in value:
        _string(value['fragment'], f'{path}.fragment')
    if value['kind'] == 'page':
        if not isinstance(value.get('page'), int) or value['page'] < 1:
            _fail(f'{path}.page', 'must be a positive integer for a page citation')
    elif 'page' in value:
        _fail(f'{path}.page', 'is only valid for a page citation')


def _text(value, path, document_sha):
    _object(value, path, ('provenance',),
            ('sha256', 'derived_from_sha256', 'tool'))
    provenance = value['provenance']
    if provenance not in TEXT_PROVENANCE:
        _fail(f'{path}.provenance', f'must be one of {", ".join(TEXT_PROVENANCE)}')
    if provenance == 'none':
        if set(value) != {'provenance'}:
            _fail(path, 'text with no provenance may not claim hashes or a tool')
        return
    if 'sha256' not in value:
        _fail(path, 'searchable text must include sha256')
    _sha(value['sha256'], f'{path}.sha256')
    if provenance == 'native':
        if 'derived_from_sha256' in value or 'tool' in value:
            _fail(path, 'native text may not claim OCR derivation')
        return
    if 'derived_from_sha256' not in value or 'tool' not in value:
        _fail(path, 'OCR text requires derived_from_sha256 and tool')
    _sha(value['derived_from_sha256'], f'{path}.derived_from_sha256')
    if value['derived_from_sha256'] != document_sha:
        _fail(f'{path}.derived_from_sha256', 'must identify the original document bytes')
    _object(value['tool'], f'{path}.tool', ('name', 'version'))
    _string(value['tool']['name'], f'{path}.tool.name')
    _string(value['tool']['version'], f'{path}.tool.version')


def _reference(value, path):
    _object(value, path, ('path', 'status'), ('target_id', 'reason'))
    _path(value['path'], f'{path}.path')
    if value['status'] not in REFERENCE_STATUSES:
        _fail(f'{path}.status', f'must be one of {", ".join(REFERENCE_STATUSES)}')
    target = value.get('target_id')
    if value['status'] == 'resolved':
        _identifier(target, f'{path}.target_id', 'doc')
        if 'reason' in value:
            _fail(f'{path}.reason', 'is only valid for an unresolved reference')
    else:
        if target is not None:
            _fail(f'{path}.target_id', 'must be absent when the target is unresolved')
        _string(value.get('reason'), f'{path}.reason')


def _asset(value, path, document):
    _object(value, path, ('id', 'path', 'sha256', 'media_type'), ('caption',))
    _identifier(value['id'], f'{path}.id', 'asset')
    _path(value['path'], f'{path}.path')
    _sha(value['sha256'], f'{path}.sha256')
    _string(value['media_type'], f'{path}.media_type')
    if 'caption' in value:
        _string(value['caption'], f'{path}.caption', allow_empty=True)
    expected = asset_id(document, value['path'])
    if value['id'] != expected:
        _fail(f'{path}.id', f'does not match document/path; expected {expected}')


def _document(value, path, publication):
    required = ('id', 'path', 'title', 'content_sha256', 'text', 'citations',
                'applicability', 'references', 'assets')
    _object(value, path, required, ('breadcrumbs',))
    _identifier(value['id'], f'{path}.id', 'doc')
    _path(value['path'], f'{path}.path')
    _string(value['title'], f'{path}.title')
    _sha(value['content_sha256'], f'{path}.content_sha256')
    expected = document_id(publication, value['path'])
    if value['id'] != expected:
        _fail(f'{path}.id', f'does not match publication/path; expected {expected}')
    if 'breadcrumbs' in value:
        _list(value['breadcrumbs'], f'{path}.breadcrumbs')
        for index, crumb in enumerate(value['breadcrumbs']):
            _string(crumb, f'{path}.breadcrumbs[{index}]')
    _text(value['text'], f'{path}.text', value['content_sha256'])
    for field in ('citations', 'applicability', 'references', 'assets'):
        _list(value[field], f'{path}.{field}')
    if not value['citations']:
        _fail(f'{path}.citations', 'must retain at least one source citation')
    for index, citation in enumerate(value['citations']):
        _citation(citation, f'{path}.citations[{index}]')
    for index, item in enumerate(value['applicability']):
        _applicability(item, f'{path}.applicability[{index}]')
    for index, reference in enumerate(value['references']):
        _reference(reference, f'{path}.references[{index}]')
    for index, asset in enumerate(value['assets']):
        _asset(asset, f'{path}.assets[{index}]', value['id'])


def _publication(value, path, source):
    required = ('id', 'source_path', 'title', 'kind', 'applicability', 'documents')
    _object(value, path, required)
    _identifier(value['id'], f'{path}.id', 'pub')
    _path(value['source_path'], f'{path}.source_path')
    _string(value['title'], f'{path}.title')
    if value['kind'] not in PUBLICATION_KINDS:
        _fail(f'{path}.kind', f'must be one of {", ".join(PUBLICATION_KINDS)}')
    expected = publication_id(source, value['source_path'])
    if value['id'] != expected:
        _fail(f'{path}.id', f'does not match source/path; expected {expected}')
    _list(value['applicability'], f'{path}.applicability')
    for index, item in enumerate(value['applicability']):
        _applicability(item, f'{path}.applicability[{index}]', 'publication')
    _list(value['documents'], f'{path}.documents')
    for index, document in enumerate(value['documents']):
        _document(document, f'{path}.documents[{index}]', value['id'])


def validate_manifest(value):
    """Validate and return a version-1 manifest without mutating it."""
    _object(value, 'manifest', ('contract', 'source', 'publications'))
    if value['contract'] != MANIFEST_CONTRACT:
        _fail('manifest.contract', f'must be {MANIFEST_CONTRACT!r}')
    _source(value['source'])
    _list(value['publications'], 'manifest.publications')
    seen = set()
    for index, publication in enumerate(value['publications']):
        _publication(publication, f'manifest.publications[{index}]', value['source']['id'])
        for item in (publication,) + tuple(publication['documents']):
            if item['id'] in seen:
                _fail('manifest', f'duplicate stable ID {item["id"]}')
            seen.add(item['id'])
        for document in publication['documents']:
            for asset in document['assets']:
                if asset['id'] in seen:
                    _fail('manifest', f'duplicate stable ID {asset["id"]}')
                seen.add(asset['id'])
    if value['source']['status'] == 'failed' and value['publications']:
        _fail('manifest.publications', 'must be empty for a failed source')
    document_ids = {
        document['id']
        for publication in value['publications']
        for document in publication['documents']
    }
    for publication in value['publications']:
        for document in publication['documents']:
            for reference in document['references']:
                target = reference.get('target_id')
                if target and target not in document_ids:
                    _fail(
                        f'document {document["id"]}.references',
                        f'resolved target {target} is not present in this manifest',
                    )
    return value


def validate_operation(value):
    """Validate the JSON envelope used by neutral probe/extract commands."""
    required = ('contract', 'operation', 'ok', 'source', 'publications', 'output',
                'diagnostics')
    _object(value, 'result', required)
    if value['contract'] != OPERATION_CONTRACT:
        _fail('result.contract', f'must be {OPERATION_CONTRACT!r}')
    if value['operation'] not in ('probe', 'extract'):
        _fail('result.operation', 'must be probe or extract')
    if not isinstance(value['ok'], bool):
        _fail('result.ok', 'must be a boolean')
    _source(value['source'])
    _list(value['publications'], 'result.publications')
    for index, publication in enumerate(value['publications']):
        _object(publication, f'result.publications[{index}]',
                ('id', 'source_path', 'title', 'kind'))
        _identifier(publication['id'], f'result.publications[{index}].id', 'pub')
        _path(publication['source_path'], f'result.publications[{index}].source_path')
        _string(publication['title'], f'result.publications[{index}].title')
        if publication['kind'] not in PUBLICATION_KINDS:
            _fail(f'result.publications[{index}].kind', 'has an unsupported kind')
        expected = publication_id(value['source']['id'], publication['source_path'])
        if publication['id'] != expected:
            _fail(f'result.publications[{index}].id',
                  f'does not match source/path; expected {expected}')
    output = value['output']
    if value['operation'] == 'probe':
        if output is not None:
            _fail('result.output', 'must be null for probe')
    else:
        _object(output, 'result.output', ('manifest_path', 'files_written', 'bytes_written'))
        _path(output['manifest_path'], 'result.output.manifest_path')
        for key in ('files_written', 'bytes_written'):
            if not isinstance(output[key], int) or output[key] < 0:
                _fail(f'result.output.{key}', 'must be a non-negative integer')
    _list(value['diagnostics'], 'result.diagnostics')
    for index, diagnostic in enumerate(value['diagnostics']):
        _object(diagnostic, f'result.diagnostics[{index}]', ('level', 'code', 'message'))
        if diagnostic['level'] not in ('warning', 'error'):
            _fail(f'result.diagnostics[{index}].level', 'must be warning or error')
        _string(diagnostic['code'], f'result.diagnostics[{index}].code')
        _string(diagnostic['message'], f'result.diagnostics[{index}].message')
    if value['ok'] and (value['source']['status'] == 'failed' or
                        any(item['level'] == 'error' for item in value['diagnostics'])):
        _fail('result.ok', 'cannot be true for a failed source or error diagnostic')
    return value


def contract_summary():
    """Machine-readable discovery data for the neutral CLI."""
    return {
        'manifest_contract': MANIFEST_CONTRACT,
        'operation_contract': OPERATION_CONTRACT,
        'formats': list(FORMATS),
        'containers': list(CONTAINERS),
        'source_statuses': list(SOURCE_STATUSES),
        'text_provenance': list(TEXT_PROVENANCE),
        'neutral_readers': ['workshop_manuals_html_v1', 'pdf_collection_v1'],
        'legacy_entry_points': ['python3 -m fsd'],
    }


def load_manifest(path):
    with open(path, encoding='utf-8') as file:
        value = json.load(file)
    return validate_manifest(value)
