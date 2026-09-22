"""Safe source inspection and staged extraction for neutral manual formats.

This module inventories original files.  It intentionally does not parse HTML
procedures or PDF page content; that is the next implementation step.
"""
import hashlib
import json
import mimetypes
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass, field

from . import __version__
from .contract import (
    MANIFEST_CONTRACT,
    OPERATION_CONTRACT,
    ContractError,
    canonical_path,
    publication_id,
    source_id,
    validate_manifest,
    validate_operation,
)

INVENTORY_CONTRACT = 'service-manual-source-inventory/v1'
MANIFEST_NAME = '.sme-manifest.json'
INVENTORY_NAME = '.sme-source-inventory.json'
RESERVED_PATHS = {MANIFEST_NAME.casefold(), INVENTORY_NAME.casefold()}
CHUNK = 1024 * 1024
_DRIVE = re.compile(r'^[A-Za-z]:')
_PAGE = re.compile(br'/Type\s*/Page(?!s)\b')
_PAGES_LINE = re.compile(r'^Pages:\s+(\d+)\s*$', re.MULTILINE)
_ALLOWED_ZIP_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class SourceError(Exception):
    """The input or destination cannot be used safely."""


@dataclass(frozen=True)
class Limits:
    max_files: int = 200_000
    max_file_bytes: int = 1024 * 1024 * 1024
    max_total_bytes: int = 20 * 1024 * 1024 * 1024
    max_compression_ratio: int = 1000


@dataclass(frozen=True)
class Member:
    path: str
    size: int
    sha256: str
    media_type: str
    page_count: int = None
    page_count_method: str = None

    def as_record(self):
        value = {
            'path': self.path,
            'size': self.size,
            'sha256': self.sha256,
            'media_type': self.media_type,
        }
        if self.page_count is not None:
            value['page_count'] = self.page_count
            value['page_count_method'] = self.page_count_method
        return value


@dataclass(frozen=True)
class Publication:
    id: str
    source_path: str
    title: str
    kind: str
    root: str
    member_paths: tuple

    def summary(self):
        return {
            'id': self.id,
            'source_path': self.source_path,
            'title': self.title,
            'kind': self.kind,
        }

    def manifest_record(self):
        return dict(self.summary(), applicability=[], documents=[])


@dataclass
class InspectedSource:
    input_path: str
    format: str
    container: str
    identity: str
    sha256: str
    content_sha256: str
    status: str
    failures: list
    ignored: list
    empty_directories: list
    members: list
    publications: list = field(default_factory=list)

    def source_record(self):
        value = {
            'id': source_id(self.format, self.container, self.identity, self.sha256),
            'format': self.format,
            'container': self.container,
            'identity': self.identity,
            'sha256': self.sha256,
            'status': self.status,
            'failures': self.failures,
            'extractor': {
                'name': 'service-manual-extractor',
                'version': __version__,
                'revision': 'source-reader-v1',
            },
        }
        return value

    @property
    def source_id(self):
        return self.source_record()['id']

    def operation(self, operation='probe', output=None):
        diagnostics = [
            {'level': 'error', 'code': item['code'], 'message': item['message']}
            for item in self.failures
        ]
        if self.ignored:
            diagnostics.append({
                'level': 'warning',
                'code': 'ignored_os_metadata',
                'message': f'Ignored {len(self.ignored)} operating-system metadata item(s).',
            })
        value = {
            'contract': OPERATION_CONTRACT,
            'operation': operation,
            'ok': self.status == 'complete',
            'source': self.source_record(),
            'publications': [item.summary() for item in self.publications],
            'output': output,
            'diagnostics': diagnostics,
        }
        return validate_operation(value)


@dataclass
class _Scan:
    container: str
    identity: str
    sha256: str
    names: set
    members: list
    directories: set
    ignored: list
    failures: list


def _failure(code, message, path=None):
    value = {'code': code, 'message': message}
    if path is not None:
        value['path'] = path
    return value


def _media_type(path):
    if path.casefold().endswith('.svg'):
        return 'image/svg+xml'
    return mimetypes.guess_type(path)[0] or 'application/octet-stream'


def _ignored_metadata(path):
    parts = path.replace('\\', '/').split('/')
    return ('__MACOSX' in parts or '.DS_Store' in parts or 'Thumbs.db' in parts or
            any(part.startswith('._') for part in parts))


def _safe_path(path, directory=False):
    if not isinstance(path, str) or not path or '\x00' in path:
        raise SourceError('member path is empty or contains a NUL byte')
    if '\\' in path:
        raise SourceError(f'member path uses a backslash: {path!r}')
    candidate = path[:-1] if directory and path.endswith('/') else path
    if not candidate:
        raise SourceError('member path identifies only the source root')
    if candidate.startswith('/') or candidate.startswith('//') or _DRIVE.match(candidate):
        raise SourceError(f'member path is absolute: {path!r}')
    parts = candidate.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise SourceError(f'member path is not canonical: {path!r}')
    if any(any(ord(char) < 32 for char in part) for part in parts):
        raise SourceError(f'member path contains a control character: {path!r}')
    normalized = '/'.join(parts)
    if normalized.casefold() in RESERVED_PATHS:
        raise SourceError(f'member path is reserved for extractor metadata: {path!r}')
    return normalized


def _collision_key(path):
    return unicodedata.normalize('NFC', path).casefold()


def _sha_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as file:
        while True:
            block = file.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _pdf_pages_fallback(path):
    count = 0
    encrypted = object_stream = False
    carry = b''
    with open(path, 'rb') as file:
        first = file.read(1024)
        if not first.startswith(b'%PDF-'):
            raise SourceError('file does not begin with a PDF header')
        file.seek(0)
        while True:
            block = file.read(CHUNK)
            if not block:
                break
            data = carry + block
            encrypted = encrypted or b'/Encrypt' in data
            object_stream = object_stream or b'/ObjStm' in data
            count += sum(match.end() > len(carry) for match in _PAGE.finditer(data))
            carry = data[-64:]
    if encrypted:
        raise SourceError('encrypted PDF is unsupported')
    if object_stream and not count:
        raise SourceError('PDF page objects require a full PDF reader')
    if count < 1:
        raise SourceError('PDF has no countable pages')
    return count, 'structure-scan'


def _pdf_page_count(path):
    pdfinfo = shutil.which('pdfinfo')
    if pdfinfo:
        result = subprocess.run(
            [pdfinfo, path], capture_output=True, text=True, timeout=60, check=False,
        )
        match = _PAGES_LINE.search(result.stdout)
        if result.returncode == 0 and match:
            return int(match.group(1)), 'pdfinfo'
        combined = (result.stderr + result.stdout).casefold()
        if 'encrypted' in combined or 'password' in combined:
            raise SourceError('encrypted PDF is unsupported')
    return _pdf_pages_fallback(path)


def _content_digest(members, directories, failures=()):
    value = {
        'members': [{
            'path': item.path,
            'size': item.size,
            'sha256': item.sha256,
        } for item in sorted(members, key=lambda item: item.path)],
        'empty_directories': sorted(directories),
        'failures': failures,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _empty_directories(directories, names):
    files = tuple(names)
    return {
        directory for directory in directories
        if not any(path.startswith(directory + '/') for path in files)
    }


def _check_collision(path, seen, failures):
    parts = path.split('/')
    for length in range(1, len(parts) + 1):
        prefix = '/'.join(parts[:length])
        key = _collision_key(prefix)
        previous = seen.get(key)
        if previous is not None and previous != prefix:
            failures.append(_failure(
                'path_collision',
                f'Paths collide by case or Unicode normalization: {previous!r} and '
                f'{prefix!r}.',
            ))
            return False
        if length == len(parts) and previous == path:
            failures.append(_failure(
                'duplicate_member', f'Duplicate member path: {path!r}.',
            ))
            return False
        seen.setdefault(key, prefix)
    return True


def _scan_directory(root, limits):
    members = []
    names = set()
    directories = set()
    ignored = []
    failures = []
    seen = {}
    total = 0
    count = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        relative_dir = os.path.relpath(dirpath, root)
        relative_dir = '' if relative_dir == '.' else relative_dir.replace(os.sep, '/')
        kept = []
        for name in sorted(dirnames):
            full = os.path.join(dirpath, name)
            relative = '/'.join(item for item in (relative_dir, name) if item)
            if _ignored_metadata(relative):
                ignored.append(relative + '/')
                continue
            if os.path.islink(full):
                failures.append(_failure(
                    'symlink', f'Symbolic-link directory is unsupported: {relative!r}.',
                    relative,
                ))
                continue
            try:
                safe = _safe_path(relative, directory=True)
            except SourceError as ex:
                failures.append(_failure('unsafe_path', str(ex)))
                continue
            if _check_collision(safe, seen, failures):
                directories.add(safe)
                kept.append(name)
        dirnames[:] = kept

        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            relative = '/'.join(item for item in (relative_dir, name) if item)
            if _ignored_metadata(relative):
                ignored.append(relative)
                continue
            if os.path.islink(full):
                failures.append(_failure(
                    'symlink', f'Symbolic-link file is unsupported: {relative!r}.', relative,
                ))
                continue
            try:
                safe = _safe_path(relative)
            except SourceError as ex:
                failures.append(_failure('unsafe_path', str(ex)))
                continue
            if not _check_collision(safe, seen, failures):
                continue
            names.add(safe)
            count += 1
            if count > limits.max_files:
                failures.append(_failure(
                    'file_limit', f'Source exceeds the {limits.max_files} file limit.',
                ))
                continue
            try:
                before = os.stat(full, follow_symlinks=False)
            except OSError as ex:
                failures.append(_failure('unreadable_member', str(ex), safe))
                continue
            if not stat.S_ISREG(before.st_mode):
                failures.append(_failure(
                    'unsupported_member', f'Not a regular file: {safe!r}.', safe,
                ))
                continue
            if before.st_size > limits.max_file_bytes:
                failures.append(_failure(
                    'file_size_limit', f'File exceeds the size limit: {safe!r}.', safe,
                ))
                continue
            total += before.st_size
            if total > limits.max_total_bytes:
                failures.append(_failure(
                    'total_size_limit', 'Source exceeds the total uncompressed size limit.',
                ))
                continue
            try:
                digest = _sha_file(full)
                after = os.stat(full, follow_symlinks=False)
            except OSError as ex:
                failures.append(_failure('unreadable_member', str(ex), safe))
                continue
            identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            if identity_before != identity_after:
                failures.append(_failure(
                    'source_changed', f'File changed while it was being read: {safe!r}.', safe,
                ))
                continue
            page_count = page_method = None
            if safe.casefold().endswith('.pdf'):
                try:
                    page_count, page_method = _pdf_page_count(full)
                except (OSError, SourceError, subprocess.SubprocessError) as ex:
                    failures.append(_failure('unreadable_pdf', f'{safe}: {ex}', safe))
            members.append(Member(
                safe, before.st_size, digest, _media_type(safe), page_count, page_method,
            ))

    empty = _empty_directories(directories, names)
    content = _content_digest(members, empty, failures)
    return _Scan(
        'directory', os.path.basename(root.rstrip(os.sep)), content, names, members,
        empty, sorted(ignored), failures,
    )


def _zip_is_symlink(info):
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _scan_zip(path, limits):
    before = os.stat(path, follow_symlinks=False)
    raw_sha256 = _sha_file(path)
    members = []
    names = set()
    directories = set()
    ignored = []
    failures = []
    seen = {}
    accepted = []
    total = 0
    count = 0
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as ex:
        raise SourceError(f'cannot open ZIP: {ex}') from None
    with archive:
        for info in archive.infolist():
            raw_name = info.filename
            try:
                safe = _safe_path(raw_name, directory=info.is_dir())
            except SourceError as ex:
                failures.append(_failure('unsafe_path', str(ex)))
                continue
            if _ignored_metadata(safe):
                ignored.append(safe + ('/' if info.is_dir() else ''))
                continue
            if not _check_collision(safe, seen, failures):
                continue
            if _zip_is_symlink(info):
                failures.append(_failure(
                    'symlink', f'Symbolic-link member is unsupported: {safe!r}.', safe,
                ))
                continue
            if info.is_dir():
                directories.add(safe)
                continue
            names.add(safe)
            count += 1
            if count > limits.max_files:
                failures.append(_failure(
                    'file_limit', f'Source exceeds the {limits.max_files} file limit.',
                ))
                continue
            if info.flag_bits & 0x1:
                failures.append(_failure(
                    'encrypted_member', f'Encrypted ZIP member is unsupported: {safe!r}.', safe,
                ))
                continue
            if info.compress_type not in _ALLOWED_ZIP_COMPRESSION:
                failures.append(_failure(
                    'unsupported_compression',
                    f'ZIP member uses unsupported compression: {safe!r}.', safe,
                ))
                continue
            if info.file_size > limits.max_file_bytes:
                failures.append(_failure(
                    'file_size_limit', f'File exceeds the size limit: {safe!r}.', safe,
                ))
                continue
            total += info.file_size
            if total > limits.max_total_bytes:
                failures.append(_failure(
                    'total_size_limit', 'Source exceeds the total uncompressed size limit.',
                ))
                continue
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > limits.max_compression_ratio:
                failures.append(_failure(
                    'compression_ratio_limit',
                    f'ZIP member exceeds the compression-ratio limit: {safe!r}.', safe,
                ))
                continue
            accepted.append((info, safe))

        for info, safe in accepted:
            digest = hashlib.sha256()
            actual = 0
            temporary = temp_path = None
            try:
                if safe.casefold().endswith('.pdf'):
                    temporary = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                    temp_path = temporary.name
                with archive.open(info, 'r') as source:
                    while True:
                        block = source.read(CHUNK)
                        if not block:
                            break
                        actual += len(block)
                        digest.update(block)
                        if temporary:
                            temporary.write(block)
                if actual != info.file_size:
                    raise SourceError(
                        f'declared {info.file_size} bytes but read {actual} bytes'
                    )
                page_count = page_method = None
                if temporary:
                    temporary.flush()
                    temporary.close()
                    temporary = None
                    page_count, page_method = _pdf_page_count(temp_path)
                members.append(Member(
                    safe, actual, digest.hexdigest(), _media_type(safe),
                    page_count, page_method,
                ))
            except Exception as ex:
                code = 'unreadable_pdf' if safe.casefold().endswith('.pdf') \
                    else 'unreadable_member'
                failures.append(_failure(code, f'{safe}: {ex}', safe))
            finally:
                if temporary:
                    temporary.close()
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

    after = os.stat(path, follow_symlinks=False)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        failures.append(_failure('source_changed', 'ZIP changed while it was being read.'))
    empty = _empty_directories(directories, names)
    return _Scan(
        'zip', os.path.basename(path), raw_sha256, names, members, empty,
        sorted(ignored), failures,
    )


def _scan_single_pdf(path, limits):
    before = os.stat(path, follow_symlinks=False)
    size = before.st_size
    if size > limits.max_file_bytes or size > limits.max_total_bytes:
        raise SourceError('PDF exceeds the configured size limit')
    name = os.path.basename(path)
    safe = _safe_path(name)
    digest = _sha_file(path)
    failures = []
    page_count = method = None
    try:
        page_count, method = _pdf_page_count(path)
    except (OSError, SourceError, subprocess.SubprocessError) as ex:
        failures.append(_failure('unreadable_pdf', f'{safe}: {ex}', safe))
    after = os.stat(path, follow_symlinks=False)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        failures.append(_failure('source_changed', 'PDF changed while it was being read.'))
    member = Member(safe, size, digest, 'application/pdf', page_count, method)
    return _Scan(
        'file_collection', name, digest, {safe}, [member], set(), [], failures,
    )


def _html_roots(names):
    roots = []
    lower = {path.casefold(): path for path in names}
    for folded, original in lower.items():
        if folded.rsplit('/', 1)[-1] != 'index.html':
            continue
        root = original.rsplit('/', 1)[0] if '/' in original else ''
        pages = (root + '/' if root else '') + 'pages/'
        if any(path.casefold().startswith(pages.casefold()) and
               path.casefold().endswith(('.htm', '.html')) for path in names):
            roots.append((root, original))
    return sorted(roots)


def _detect(scan):
    html = _html_roots(scan.names)
    pdfs = sorted(path for path in scan.names if path.casefold().endswith('.pdf'))
    readable = {item.path for item in scan.members}
    if html:
        source_format = 'workshop_manuals_html_v1'
        publications = []
        assigned = set()
        roots = [root for root, _index in html]
        for index, root in enumerate(roots):
            for other in roots[index + 1:]:
                if not root or other.startswith(root + '/'):
                    scan.failures.append(_failure(
                        'overlapping_publications',
                        f'Detected HTML manual roots overlap: {root or "."!r} and '
                        f'{other!r}.',
                    ))
        for root, index in html:
            prefix = root + '/' if root else ''
            paths = tuple(sorted(path for path in readable if path.startswith(prefix)))
            assigned.update(path for path in scan.names if path.startswith(prefix))
            title = 'HTML workshop manual'
            publications.append((index, title, 'workshop', root, paths))
        unassigned = sorted(scan.names - assigned)
        for path in unassigned:
            scan.failures.append(_failure(
                'unassigned_member', f'File is outside every detected manual: {path!r}.', path,
            ))
        return source_format, publications
    if pdfs:
        source_format = 'pdf_collection_v1'
        publications = []
        for path in sorted(scan.names):
            if not path.casefold().endswith('.pdf'):
                scan.failures.append(_failure(
                    'unsupported_member',
                    f'Non-PDF file is unsupported in a PDF collection: {path!r}.', path,
                ))
                continue
            title = os.path.basename(path).rsplit('.', 1)[0]
            paths = (path,) if path in readable else ()
            publications.append((path, title, 'unknown', '', paths))
        return source_format, publications
    raise SourceError(
        'unsupported source: expected an HTML export with index.html and pages/, '
        'or a PDF collection'
    )


def inspect_source(path, limits=None):
    """Fully inspect a ZIP, directory or PDF without writing beside the source."""
    limits = limits or Limits()
    absolute = os.path.abspath(path)
    if not os.path.exists(absolute):
        raise SourceError(f'{path}: no such file or directory')
    if os.path.islink(absolute):
        raise SourceError(f'{path}: source may not be a symbolic link')
    if os.path.isdir(absolute):
        scan = _scan_directory(absolute, limits)
    elif zipfile.is_zipfile(absolute):
        scan = _scan_zip(absolute, limits)
    elif absolute.casefold().endswith('.zip'):
        raise SourceError(f'{path}: invalid or truncated ZIP')
    elif absolute.casefold().endswith('.pdf'):
        scan = _scan_single_pdf(absolute, limits)
    else:
        raise SourceError(f'{path}: unsupported file type')

    source_format, candidates = _detect(scan)
    content_sha256 = _content_digest(scan.members, scan.directories, scan.failures)
    status = 'complete' if not scan.failures else ('partial' if candidates else 'failed')
    result = InspectedSource(
        absolute, source_format, scan.container, scan.identity, scan.sha256,
        content_sha256, status, scan.failures, scan.ignored,
        sorted(scan.directories), sorted(scan.members, key=lambda item: item.path),
    )
    result.publications = [
        Publication(
            publication_id(result.source_id, source_path), source_path, title,
            kind, root, member_paths,
        )
        for source_path, title, kind, root, member_paths in candidates
    ]
    return result


def _selected_publications(source, publication_ids):
    if not publication_ids:
        return list(source.publications)
    requested = set(publication_ids)
    selected = [item for item in source.publications if item.id in requested]
    missing = requested - {item.id for item in selected}
    if missing:
        raise SourceError('unknown publication ID(s): ' + ', '.join(sorted(missing)))
    return selected


def _destination_guard(source, destination):
    destination = os.path.abspath(destination)
    if os.path.lexists(destination):
        raise SourceError(f'destination already exists: {destination}')
    parent = os.path.dirname(destination)
    if not os.path.isdir(parent):
        raise SourceError(f'destination parent is not a directory: {parent}')
    if os.path.islink(parent):
        raise SourceError(f'destination parent may not be a symbolic link: {parent}')
    if os.path.isdir(source.input_path):
        try:
            inside = os.path.commonpath((source.input_path, destination)) == source.input_path
        except ValueError:
            inside = False
        if inside:
            raise SourceError('destination may not be inside the source directory')
    return destination, parent


def _copy_member(source, member, target):
    digest = hashlib.sha256()
    total = 0
    if source.container == 'zip':
        archive = zipfile.ZipFile(source.input_path)
        opened = archive.open(member.path, 'r')
        before = None
    else:
        archive = None
        path = source.input_path if source.container == 'file_collection' \
            else os.path.join(source.input_path, *member.path.split('/'))
        current = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode):
            raise SourceError(f'source member is no longer a regular file: {member.path}')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(path, flags)
        opened = os.fdopen(descriptor, 'rb')
        before = os.fstat(opened.fileno())
    try:
        with opened, open(target, 'wb') as output:
            while True:
                block = opened.read(CHUNK)
                if not block:
                    break
                output.write(block)
                digest.update(block)
                total += len(block)
            after = os.fstat(opened.fileno()) if before is not None else None
    finally:
        if archive:
            archive.close()
    if total != member.size or digest.hexdigest() != member.sha256:
        raise SourceError(f'copied bytes do not match the inspected source: {member.path}')
    if before is not None:
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after:
            raise SourceError(f'source changed while it was copied: {member.path}')


def _inventory_record(source, publications, members, empty_directories):
    selected_digest = _content_digest(members, empty_directories)
    return {
        'contract': INVENTORY_CONTRACT,
        'source_id': source.source_id,
        'source_content_sha256': source.content_sha256,
        'selected_content_sha256': selected_digest,
        'members': [item.as_record() for item in members],
        'empty_directories': sorted(empty_directories),
        'ignored': source.ignored,
        'publications': [{
            'id': item.id,
            'source_path': item.source_path,
            'member_paths': list(item.member_paths),
        } for item in publications],
    }


def validate_inventory(value):
    """Validate the raw-file inventory consumed by later normalization."""
    required = {
        'contract', 'source_id', 'source_content_sha256', 'selected_content_sha256',
        'members', 'empty_directories', 'ignored', 'publications',
    }
    if not isinstance(value, dict) or set(value) != required:
        raise SourceError('source inventory has missing or unknown top-level fields')
    if value['contract'] != INVENTORY_CONTRACT:
        raise SourceError(f'unsupported source inventory contract: {value["contract"]!r}')
    if not isinstance(value['source_id'], str) or not re.fullmatch(
            r'src_[0-9a-f]{32}', value['source_id']):
        raise SourceError('source inventory has an invalid source ID')
    for field_name in ('source_content_sha256', 'selected_content_sha256'):
        if not isinstance(value[field_name], str) or not re.fullmatch(
                r'[0-9a-f]{64}', value[field_name]):
            raise SourceError(f'source inventory has an invalid {field_name}')
    for field_name in ('members', 'empty_directories', 'ignored', 'publications'):
        if not isinstance(value[field_name], list):
            raise SourceError(f'source inventory {field_name} must be an array')

    members = []
    paths = set()
    for record in value['members']:
        base = {'path', 'size', 'sha256', 'media_type'}
        page = {'page_count', 'page_count_method'}
        fields = set(record) if isinstance(record, dict) else set()
        if not base.issubset(fields) or fields - base - page or bool(fields & page) != \
                page.issubset(fields):
            raise SourceError('source inventory member has invalid fields')
        try:
            path = canonical_path(record['path'])
        except ContractError as ex:
            raise SourceError(f'invalid inventory member path: {ex}') from None
        if path != record['path'] or path in paths:
            raise SourceError(f'duplicate or non-canonical inventory path: {path!r}')
        paths.add(path)
        if not isinstance(record['size'], int) or record['size'] < 0:
            raise SourceError(f'invalid inventory size for {path!r}')
        if not isinstance(record['sha256'], str) or not re.fullmatch(
                r'[0-9a-f]{64}', record['sha256']):
            raise SourceError(f'invalid inventory hash for {path!r}')
        if not isinstance(record['media_type'], str) or not record['media_type']:
            raise SourceError(f'invalid inventory media type for {path!r}')
        if 'page_count' in record and (
                not isinstance(record['page_count'], int) or record['page_count'] < 1):
            raise SourceError(f'invalid page count for {path!r}')
        if 'page_count_method' in record and (
                not isinstance(record['page_count_method'], str) or
                not record['page_count_method']):
            raise SourceError(f'invalid page-count method for {path!r}')
        members.append(Member(
            path, record['size'], record['sha256'], record['media_type'],
            record.get('page_count'), record.get('page_count_method'),
        ))

    directories = []
    for path in value['empty_directories']:
        try:
            normalized = canonical_path(path)
        except ContractError as ex:
            raise SourceError(f'invalid empty-directory path: {ex}') from None
        if normalized != path or path in directories:
            raise SourceError(f'duplicate or non-canonical directory path: {path!r}')
        directories.append(path)
    for path in value['ignored']:
        if not isinstance(path, str) or not path:
            raise SourceError('ignored metadata paths must be non-empty strings')
    publication_ids = set()
    for publication in value['publications']:
        if not isinstance(publication, dict) or set(publication) != {
                'id', 'source_path', 'member_paths'}:
            raise SourceError('source inventory publication has invalid fields')
        if not isinstance(publication['id'], str) or not re.fullmatch(
                r'pub_[0-9a-f]{32}', publication['id']):
            raise SourceError('source inventory publication has an invalid ID')
        try:
            source_path = canonical_path(publication['source_path'])
        except ContractError as ex:
            raise SourceError(f'invalid publication path: {ex}') from None
        if source_path != publication['source_path']:
            raise SourceError('source inventory publication path is not canonical')
        expected_id = publication_id(value['source_id'], source_path)
        if publication['id'] != expected_id or publication['id'] in publication_ids:
            raise SourceError('source inventory publication ID does not match source/path')
        publication_ids.add(publication['id'])
        member_paths = publication['member_paths']
        if (not isinstance(member_paths, list) or
                any(not isinstance(path, str) for path in member_paths) or
                len(set(member_paths)) != len(member_paths) or
                not set(member_paths).issubset(paths)):
            raise SourceError('publication includes a member absent from the inventory')
    expected = _content_digest(members, directories)
    if value['selected_content_sha256'] != expected:
        raise SourceError('selected-content hash does not match the inventory')
    return value


def extract_source(path, destination, publication_ids=None, limits=None, on_member=None):
    """Inspect, copy to a fresh staging tree, verify, then publish atomically."""
    source = inspect_source(path, limits=limits)
    if source.status != 'complete':
        return source.operation('extract', {
            'manifest_path': MANIFEST_NAME,
            'files_written': 0,
            'bytes_written': 0,
        })
    publications = _selected_publications(source, publication_ids)
    if not publications:
        raise SourceError('source contains no selectable publications')
    selected_paths = {
        path for publication in publications for path in publication.member_paths
    }
    members = [item for item in source.members if item.path in selected_paths]
    if len(publications) == len(source.publications):
        empty_directories = list(source.empty_directories)
    else:
        roots = [item.root for item in publications if item.kind == 'workshop']
        empty_directories = [
            directory for directory in source.empty_directories
            if any(not root or directory == root or directory.startswith(root + '/')
                   for root in roots)
        ]
    destination, parent = _destination_guard(source, destination)
    staging = tempfile.mkdtemp(prefix=f'.{os.path.basename(destination)}.sme-', dir=parent)
    try:
        for directory in empty_directories:
            os.makedirs(os.path.join(staging, *directory.split('/')), exist_ok=True)
        for member in members:
            target = os.path.join(staging, *member.path.split('/'))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            _copy_member(source, member, target)
            if on_member:
                on_member(member)
        manifest = {
            'contract': MANIFEST_CONTRACT,
            'source': source.source_record(),
            'publications': [item.manifest_record() for item in publications],
        }
        validate_manifest(manifest)
        inventory = _inventory_record(source, publications, members, empty_directories)
        validate_inventory(inventory)
        with open(os.path.join(staging, MANIFEST_NAME), 'w', encoding='utf-8') as file:
            json.dump(manifest, file, indent=2, ensure_ascii=False)
            file.write('\n')
        with open(os.path.join(staging, INVENTORY_NAME), 'w', encoding='utf-8') as file:
            json.dump(inventory, file, indent=2, ensure_ascii=False)
            file.write('\n')
        if os.path.lexists(destination):
            raise SourceError(f'destination appeared during extraction: {destination}')
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    output = {
        'manifest_path': MANIFEST_NAME,
        'files_written': len(members),
        'bytes_written': sum(item.size for item in members),
    }
    return source.operation('extract', output)
