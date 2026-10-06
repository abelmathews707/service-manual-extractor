"""Finding the archives on a Ford service disc, and reading what they say
about themselves.

A disc can reach us three ways — mounted (``/Volumes/20SLB``), copied to a
folder, or as an image file — and all three are handled here so nothing above
this module has to care.

Each archive carries a small ``<CODE>.epl`` manifest that names the book,
its type and the vehicles it covers. That manifest is what makes this tool
work on discs nobody has tested it against: we ask the disc what is on it
instead of hardcoding the codes from one title.
"""

import io
import os
import re
import xml.etree.ElementTree as ET

from .arc import ArcError, Archive
from .iso import SECTOR, Iso9660, SectorSource

IMAGE_EXT = ('.iso', '.img', '.bin', '.mdf', '.nrg')

#: Book types seen in the wild, mapped to the role the viewer gives them.
KNOWN_TYPES = {
    'SERVICE': 'wsm',  # workshop manual
    'EVTM': 'elb',  # electrical & vacuum troubleshooting (wiring)
    'PCED': 'pced',  # powertrain control / emissions diagnosis
}


class DiscError(Exception):
    pass


# --------------------------------------------------------------- book metadata
class Book:
    """What a ``.epl`` manifest says about one archive."""

    def __init__(self, code, type_, title='', vehicles=(), archive=None):
        self.code = code
        self.type = type_
        self.title = title
        self.vehicles = list(vehicles)
        self.archive = archive  # archive filename this came from
        self.dir = None  # set by books_in_dir()
        self.prefix = code  # filename prefix, usually == code

    @property
    def role(self):
        """'wsm' | 'elb' | 'pced', or None if we don't know this type."""
        return KNOWN_TYPES.get(self.type.upper())

    @property
    def years(self):
        return sorted({v['year'] for v in self.vehicles if v.get('year')})

    @property
    def models(self):
        out = []
        for v in self.vehicles:
            if v.get('name') and v['name'] not in out:
                out.append(v['name'])
        return out

    def describe(self):
        who = ', '.join(self.models[:3])
        if len(self.models) > 3:
            who += f' +{len(self.models) - 3} more'
        yr = '/'.join(self.years)
        bits = [b for b in (yr, who) if b]
        return f'{self.code} ({self.type}){" — " + " ".join(bits) if bits else ""}'

    def __repr__(self):
        return f'<Book {self.describe()}>'


def _epl_by_regex(data, archive):
    """Last resort for a manifest too malformed to parse as XML."""
    # <sections> has its own <title> per section; only look above it so a
    # section heading can't be mistaken for the book title.
    head = re.split(r'<sections\b', data, maxsplit=1, flags=re.I)[0]

    def one(tag, where=head):
        m = re.search(rf'<{tag}>(.*?)</{tag}>', where, re.S | re.I)
        return m.group(1).strip() if m else ''

    code, type_ = one('code'), one('type')
    if not code and not type_:
        return None
    vehicles = [
        {'year': y.strip(), 'name': n.strip(), 'engine': ''}
        for y, n in re.findall(r'<year>(.*?)</year>\s*<name>(.*?)</name>', data, re.S | re.I)
    ]
    return Book(code, type_, one('title'), vehicles, archive)


def parse_epl(data, archive=None):
    """Parse a ``.epl`` manifest. Returns a Book, or None if it isn't one."""
    if isinstance(data, bytes):
        data = data.decode('utf-8', 'replace')
    data = data.lstrip('﻿').strip()
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # Some manifests put a bare "&" inside a <dest> URL, which is not legal
        # XML. Escape any ampersand that isn't already an entity and retry.
        try:
            root = ET.fromstring(re.sub(r'&(?!#?\w+;)', '&amp;', data))
        except ET.ParseError:
            return _epl_by_regex(data, archive)

    def txt(node, tag):
        e = node.find(tag)
        return (e.text or '').strip() if e is not None and e.text else ''

    vehicles = [
        {'year': txt(v, 'year'), 'name': txt(v, 'name'), 'engine': txt(v, 'engine')}
        for v in root.iter('vehicle')
    ]
    code, type_ = txt(root, 'code'), txt(root, 'type')
    if not code and not type_:
        return None
    return Book(code, type_, txt(root, 'title'), vehicles, archive)


def book_of(archive):
    """Read the .epl manifest out of an open Archive."""
    for e in archive:
        if e.ext == 'epl':
            try:
                return parse_epl(archive.read(e), archive.name)
            except Exception:
                return None
    return None


# ------------------------------------------------------------------- sources
class _ExtentFile(io.RawIOBase):
    """A seekable read-only window onto a contiguous run of ISO sectors.

    ISO9660 files are stored contiguously, so an archive inside an image can be
    read in place. That matters: these archives run to hundreds of megabytes
    and there is no reason to copy one into memory to list it.
    """

    def __init__(self, src, lba, size):
        self.src, self.lba, self.size, self.pos = src, lba, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, off, whence=os.SEEK_SET):
        base = {os.SEEK_SET: 0, os.SEEK_CUR: self.pos, os.SEEK_END: self.size}[whence]
        self.pos = max(0, base + off)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if not n:
            return b''
        start = self.pos
        first = start // SECTOR
        skip = start % SECTOR
        need = skip + n
        nsec = (need + SECTOR - 1) // SECTOR
        buf = self.src.read(self.lba + first, nsec * SECTOR)
        self.pos += n
        return buf[skip : skip + n]

    def readall(self):
        return self.read(-1)


class ArchiveRef:
    __slots__ = ('code', 'identity', 'output_dir', 'path', 'size', '_open')

    def __init__(self, code, identity, path, size, opener):
        self.code = code
        self.identity = _archive_identity(identity)
        self.output_dir = code
        self.path, self.size, self._open = path, size, opener

    def open(self):
        return Archive(self._open(), self.identity)

    def __repr__(self):
        return f'<ArchiveRef {self.code} {self.identity} {self.size}B>'


def _archive_identity(path):
    return path.replace('\\', '/').lstrip('/').casefold()


def _with_output_dirs(refs):
    """Assign stable output directories without merging same-code archives."""
    by_code = {}
    for ref in refs:
        by_code.setdefault(ref.code.casefold(), []).append(ref)
    for group in by_code.values():
        if len(group) == 1:
            continue
        used = set()
        for ref in group:
            parent = ref.identity.rsplit('/', 1)[0].rsplit('/', 1)[-1].upper()
            candidate = f'{ref.code}--{parent or "ARCHIVE"}'
            if candidate.casefold() in used:
                token = re.sub(r'[^A-Z0-9]+', '-', ref.identity.upper()).strip('-')
                candidate = f'{ref.code}--{token}'
            used.add(candidate.casefold())
            ref.output_dir = candidate
    return sorted(refs, key=lambda ref: (ref.code.casefold(), ref.identity))


class Source:
    """Common interface over a mounted disc, a folder, or an image."""

    label = ''
    kind = ''
    origin = ''

    def archives(self):
        raise NotImplementedError

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def books(self):
        """[(ArchiveRef, Book|None)] for everything on the disc."""
        out = []
        for ref in self.archives():
            try:
                with ref.open() as a:
                    out.append((ref, book_of(a)))
            except ArcError:
                out.append((ref, None))
        return out


class DirSource(Source):
    """A mounted disc or a folder holding a copy of one."""

    kind = 'directory'

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.origin = self.root
        self.label = os.path.basename(self.root.rstrip(os.sep))

    def archives(self):
        found = []
        for dirpath, _, files in os.walk(self.root):
            for fn in files:
                if fn.lower().endswith('.arc'):
                    p = os.path.join(dirpath, fn)
                    found.append(
                        ArchiveRef(
                            os.path.splitext(fn)[0].upper(),
                            os.path.relpath(p, self.root),
                            p,
                            os.path.getsize(p),
                            lambda p=p: open(p, 'rb'),
                        )
                    )
        return _with_output_dirs(found)


class ImageSource(Source):
    """A disc image, read in place — no mounting, no conversion, no root."""

    kind = 'image'

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.origin = self.path
        self.f = open(self.path, 'rb')
        try:
            self.src = SectorSource(self.f)
            self.iso = Iso9660(self.src)
        except Exception:
            self.f.close()
            raise
        self.label = self.iso.label
        self._entries = None

    @property
    def raw(self):
        return self.src.raw

    @property
    def sector_size(self):
        return self.src.stride

    def _scan(self):
        if self._entries is None:
            self._entries = list(self.iso.walk())
        return self._entries

    def archives(self):
        out = []
        for e in self._scan():
            if not e.is_dir and e.path.lower().endswith('.arc'):
                code = os.path.basename(e.path).rsplit('.', 1)[0].upper()
                out.append(
                    ArchiveRef(
                        code,
                        e.path,
                        e.path,
                        e.size,
                        lambda e=e: _ExtentFile(self.src, e.lba, e.size),
                    )
                )
        return _with_output_dirs(out)

    def close(self):
        self.f.close()


# --------------------------------------------------- reading an extracted tree
def detect_prefix(d, code):
    """The prefix that structural filenames carry, e.g. 'SLB' in SLBLEFT.HTM.

    Normally this is just the book code, but the code comes from the manifest
    and the filenames come from the archive, so don't assume they agree —
    fall back to whatever prefix the files actually share.
    """
    try:
        files = os.listdir(d)
    except OSError:
        return code
    if code and any(f.upper().startswith(code.upper()) for f in files):
        return code.upper()
    counts = {}
    for f in files:
        if not f.upper().endswith(('.HTM', '.XML')):
            continue
        m = re.match(r'([A-Za-z]{2,4})', f)
        if m:
            p = m.group(1).upper()
            counts[p] = counts.get(p, 0) + 1
    return max(counts, key=counts.get) if counts else (code or '').upper()


def guess_type(d, prefix):
    """Work out a book's type from its files, for discs with no .epl."""
    try:
        files = os.listdir(d)
    except OSError:
        return ''
    up = [f.upper() for f in files]
    P = prefix.upper()
    if any(f.startswith(f'{P}CEL_') and f.endswith('.XML') for f in up):
        return 'EVTM'
    if f'{P}LEFT.HTM' in up and any(re.fullmatch(rf'{re.escape(P)}G\d+L\.HTM', f) for f in up):
        return 'SERVICE'
    for f in files:
        if f.upper().endswith('.HTM'):
            try:
                head = open(os.path.join(d, f), 'rb').read(4096)
            except OSError:
                continue
            if b'tps_section' in head:
                return 'PCED'
    return ''


def books_in_dir(root):
    """Discover the books in an extracted tree (one subdirectory per archive)."""
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError as ex:
        raise DiscError(f'{root}: {ex}') from None
    for name in names:
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name.startswith('.'):
            continue
        book = None
        for f in sorted(os.listdir(d)):
            if f.lower().endswith('.epl'):
                try:
                    with open(os.path.join(d, f), 'rb') as stream:
                        book = parse_epl(stream.read(), name)
                except OSError:
                    book = None
                if book:
                    break
        if book is None:
            book = Book(name.upper(), '', archive=name)
        book.dir = d
        book.prefix = detect_prefix(d, book.code or name)
        if not book.type:
            book.type = guess_type(d, book.prefix)
        if not book.code:
            book.code = book.prefix or name.upper()
        out.append(book)
    return out


def open_source(path):
    """Open a disc by mount point, folder, or image file."""
    if not os.path.exists(path):
        raise DiscError(f'{path}: no such file or directory')
    if os.path.isdir(path):
        return DirSource(path)
    return ImageSource(path)
