"""Format tests.

Everything here is synthesised in memory. No Ford content is needed to run
the suite, which is the point: these tests double as an executable
specification of the two container formats.

    python3 -m unittest discover -s tests -v
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsd import idicomp  # noqa: E402
from fsd.arc import ArcError, Archive  # noqa: E402
from fsd.build import brand_parts, clean_fragment, site_title, tokens  # noqa: E402
from fsd.disc import Book, DirSource, book_of, parse_epl  # noqa: E402
from fsd.extract import extract, safe_name  # noqa: E402
from fsd.idicomp import LZError, unwrap  # noqa: E402
from fsd.iso import IsoError, SectorSource  # noqa: E402
from fsd.probe import report  # noqa: E402


# --------------------------------------------------------------- LZ helpers
def lit(b):
    return ('lit', b)


def tok(*bs):
    return ('tok',) + bs


def chunk(items):
    """One flag word plus up to 16 tokens."""
    assert len(items) <= 16
    flag = 0
    for i, t in enumerate(items):
        if t[0] == 'tok':
            flag |= 0x8000 >> i          # flags are consumed MSB first
    body = b''.join(bytes(t[1:]) for t in items)
    return struct.pack('<H', flag) + body


def payload(*chunks, stored=()):
    out = idicomp.MAGIC + b'\x01'
    for c in chunks:
        out += struct.pack('<h', len(c)) + c
    for s in stored:
        out += struct.pack('<h', -len(s)) + s
    return out + struct.pack('<h', 0)


class TestIdicomp(unittest.TestCase):
    def test_literals(self):
        data, _ = unwrap(payload(chunk([lit(b) for b in b'Ford'])))
        self.assertEqual(data, b'Ford')

    def test_stored_chunk(self):
        data, _ = unwrap(payload(stored=[b'raw bytes']))
        self.assertEqual(data, b'raw bytes')

    def test_short_run(self):
        # hi=0: b1 repeated lo+3 times
        data, _ = unwrap(payload(chunk([tok(0x00, 0x41)])))
        self.assertEqual(data, b'A' * 3)
        data, _ = unwrap(payload(chunk([tok(0x0F, 0x42)])))
        self.assertEqual(data, b'B' * 18)

    def test_long_run(self):
        # hi=1: third byte repeated ((b1 << 4) | lo) + 19 times
        data, _ = unwrap(payload(chunk([tok(0x10, 0x00, 0x43)])))
        self.assertEqual(data, b'C' * 19)
        data, _ = unwrap(payload(chunk([tok(0x11, 0x02, 0x44)])))
        self.assertEqual(data, b'D' * (((0x02 << 4) | 1) + 19))

    def test_short_match(self):
        # hi>=3: length = hi, distance = ((b1 << 4) | lo) + 3
        items = [lit(b) for b in b'abc'] + [tok(0x30, 0x00)]
        data, _ = unwrap(payload(chunk(items)))
        self.assertEqual(data, b'abcabc')

    def test_overlapping_match(self):
        """A match may read bytes it is itself writing — that is how the
        format encodes a repeating pattern longer than its period."""
        # history 'abc', then length 6 at distance 3
        items = [lit(b) for b in b'abc'] + [tok(0x60, 0x00)]
        data, _ = unwrap(payload(chunk(items)))
        self.assertEqual(data, b'abcabcabc')

    def test_extended_match_length(self):
        # hi=2: length = third byte + 16. lo=1 -> distance 4.
        items = [lit(b) for b in b'abcd'] + [tok(0x21, 0x00, 0x00)]
        data, _ = unwrap(payload(chunk(items)))
        self.assertEqual(len(data), 4 + 16)
        self.assertEqual(data, b'abcd' * 5)

    def test_prologue_is_zero_filled(self):
        """Matches at the very start legitimately reach back before byte 0."""
        data, _ = unwrap(payload(chunk([tok(0x30, 0x00)])))
        self.assertEqual(data, b'\0' * 3)

    def test_bad_magic(self):
        with self.assertRaises(LZError):
            unwrap(b'NOTIDICOMP\x00\x00')

    def test_prologue_covers_the_maximum_distance(self):
        """The zero prologue is exactly as long as the longest match distance
        (0xFFF + 3 = 4098), so a match can never outrun the history. The
        distance check in the decoder is defensive only."""
        self.assertEqual(idicomp.PROLOGUE, 0xFFF + 3)
        # the largest encodable distance, at the very start of a stream
        data, _ = unwrap(payload(chunk([tok(0x3F, 0xFF)])))
        self.assertEqual(data, b'\0' * 3)

    def test_strict_rejects_short_middle_chunk(self):
        """Every chunk but the last expands to exactly 16 KB."""
        two = payload(chunk([lit(0x41)]), chunk([lit(0x42)]))
        self.assertEqual(unwrap(two)[0], b'AB')          # lenient
        with self.assertRaises(LZError):
            unwrap(two, strict=True)

    def test_strict_allows_single_short_chunk(self):
        unwrap(payload(chunk([lit(0x41)])), strict=True)

    def test_consumed_offset_reported(self):
        blob = payload(chunk([lit(0x41)]))
        data, used = unwrap(blob)
        self.assertEqual(data, b'A')
        self.assertEqual(used, len(blob))


# ------------------------------------------------------------------ archive
def make_arc(files):
    names, table, blobs = b'', b'', b''
    head = 17 + len(files) * 16
    nsize = sum(len(n) + 1 for n in files)
    data_at = head + nsize
    for name, body in files.items():
        table += struct.pack('<IIII', len(names), len(name),
                             data_at + len(blobs), len(body))
        names += name.encode() + b'\0'
        blobs += body
    return (b'BAY POD' + bytes([2, 0]) + struct.pack('<II', len(files), nsize)
            + table + names + blobs)


def v1_symbols(stem, ext=(0, 0, 0)):
    """Pack raw v1 filename symbols, including deliberately invalid ones."""
    value = 0
    for symbol in stem:
        value = (value << 6) | symbol
    ext_value = ext[0] * 38 * 38 + ext[1] * 38 + ext[2]
    return value.to_bytes(6, 'big') + ext_value.to_bytes(2, 'big')


def v1_symbol(char):
    if '0' <= char <= '9':
        return ord(char) - ord('0') + 1
    if 'A' <= char <= 'Z':
        return ord(char) - ord('A') + 11
    if char == '_':
        return 37
    raise ValueError(f'unsupported v1 filename character {char!r}')


def v1_name(name):
    stem, dot, ext = name.upper().partition('.')
    if len(stem) > 8 or len(ext) > 3 or (dot and not ext):
        raise ValueError(f'not an 8.3 filename: {name!r}')
    stem_symbols = [v1_symbol(c) for c in stem]
    ext_symbols = [v1_symbol(c) for c in ext]
    return v1_symbols(stem_symbols + [0] * (8 - len(stem_symbols)),
                      tuple(ext_symbols + [0] * (3 - len(ext_symbols))))


def make_v1_arc(files, marker=b'POD BAY\x01\x00'):
    files = list(files)
    data_offset = 13 + len(files) * 15
    table, blobs = b'', b''
    for name, body in files:
        table += (v1_name(name) + struct.pack('<I', data_offset + len(blobs))
                  + len(body).to_bytes(3, 'little'))
        blobs += body
    return marker + struct.pack('<I', len(files)) + table + blobs


def patch_v1_record(archive, index, *, name=None, offset=None, length=None):
    archive = bytearray(archive)
    record = 13 + index * 15
    if name is not None:
        archive[record:record + 8] = name
    if offset is not None:
        struct.pack_into('<I', archive, record + 8, offset)
    if length is not None:
        archive[record + 12:record + 15] = length.to_bytes(3, 'little')
    return bytes(archive)


class TestArchive(unittest.TestCase):
    def setUp(self):
        import io
        self.files = {'ONE.HTM': payload(chunk([lit(b) for b in b'hello'])),
                      'TWO.epl': payload(stored=[b'<workunit/>'])}
        self.f = io.BytesIO(make_arc(self.files))

    def test_parses_entries(self):
        a = Archive(self.f)
        self.assertEqual(a.version, 2)
        self.assertEqual([e.name for e in a], ['ONE.HTM', 'TWO.epl'])

    def test_reads_and_decompresses(self):
        a = Archive(self.f)
        self.assertEqual(a.read(a.find('ONE.HTM')), b'hello')

    def test_ext_counts(self):
        self.assertEqual(Archive(self.f).ext_counts(), {'htm': 1, 'epl': 1})

    def test_rejects_foreign_file(self):
        import io
        with self.assertRaises(ArcError):
            Archive(io.BytesIO(b'PK\x03\x04' + b'\0' * 64))


class TestArchiveV1(unittest.TestCase):
    def _open(self, blob):
        import io
        return Archive(io.BytesIO(blob))

    def test_decodes_full_83_filename(self):
        a = self._open(make_v1_arc([
            ('A1_B2C3D.HTM', payload(stored=[b'page']))]))
        self.assertEqual(a.version, 1)
        self.assertEqual(a.entries[0].name, 'A1_B2C3D.HTM')

    def test_uses_stored_lengths(self):
        bodies = [payload(stored=[b'a' * 16384] * 4 + [b'end']),
                  payload(stored=[b'longer'])]
        a = self._open(make_v1_arc([
            ('ONE.HTM', bodies[0]), ('TWO.GIF', bodies[1])]))
        self.assertEqual([e.length for e in a], [len(b) for b in bodies])
        self.assertEqual([a.raw(e) for e in a], bodies)

    def test_reads_and_decompresses(self):
        body = payload(chunk([lit(b) for b in b'v1 works']))
        a = self._open(make_v1_arc([('PAGE.HTM', body)]))
        self.assertEqual(a.read(a.find('page.htm')), b'v1 works')

    def test_epl_manifest_is_discovered(self):
        manifest = (b'<workunit><type>SERVICE</type><code>S1O</code>'
                    b'<vehicles><vehicle><year>2001</year>'
                    b'<name>F-250</name></vehicle></vehicles></workunit>')
        a = self._open(make_v1_arc([
            ('S1O.EPL', payload(stored=[manifest])),
            ('INDEX.HTM', payload(stored=[b'<html/>']))]))
        book = book_of(a)
        self.assertEqual((book.code, book.role, book.years, book.models),
                         ('S1O', 'wsm', ['2001'], ['F-250']))

    def test_decodes_all_observed_extensions(self):
        extensions = ('EPL', 'GIF', 'HTM', 'MDB', 'PDF', 'WCF')
        files = [(f'FILE{i}.{ext}', payload(stored=[ext.encode()]))
                 for i, ext in enumerate(extensions)]
        a = self._open(make_v1_arc(files))
        self.assertEqual([e.ext for e in a], [e.lower() for e in extensions])
        self.assertEqual(a.ext_counts(), {e.lower(): 1 for e in extensions})

    def test_requires_exact_marker(self):
        markers = (b'POD BAY\x02\x00', b'POD BAY\x01\x01',
                   b'POD BAY\x00\x00', b'BAY POD\x01\x00')
        for marker in markers:
            with self.subTest(marker=marker), self.assertRaises(ArcError):
                self._open(make_v1_arc([], marker))

    def test_rejects_truncated_headers_and_table(self):
        cases = (b'POD BAY', b'POD BAY\x01\x00',
                 b'POD BAY\x01\x00\x01\x00',
                 b'POD BAY\x01\x00' + struct.pack('<I', 1) + b'\0' * 14)
        for blob in cases:
            with self.subTest(size=len(blob)), self.assertRaises(ArcError):
                self._open(blob)

    def test_rejects_invalid_empty_and_misplaced_padding_symbols(self):
        valid_stem = [11] + [0] * 7
        names = {
            'invalid stem': v1_symbols([38] + [0] * 7),
            'invalid extension': v1_symbols(valid_stem, (38, 0, 0)),
            'empty stem': v1_symbols([0] * 8),
            'stem after padding': v1_symbols([11, 0, 12] + [0] * 5),
            'extension after padding': v1_symbols(valid_stem, (11, 0, 12)),
        }
        base = make_v1_arc([('A.HTM', payload(stored=[b'x']))])
        for case, name in names.items():
            with self.subTest(case=case), self.assertRaises(ArcError):
                self._open(patch_v1_record(base, 0, name=name))

    def test_rejects_duplicate_names(self):
        body = payload(stored=[b'x'])
        with self.assertRaises(ArcError):
            self._open(make_v1_arc([('SAME.HTM', body), ('SAME.HTM', body)]))

    def test_rejects_invalid_payload_bounds(self):
        body = payload(stored=[b'payload'])
        base = make_v1_arc([('ONE.HTM', body)])
        cases = {
            'zero offset': patch_v1_record(base, 0, offset=0),
            'before table': patch_v1_record(base, 0, offset=27),
            'past eof': patch_v1_record(base, 0, offset=len(base) + 1),
            'zero length': patch_v1_record(base, 0, length=0),
            'length past eof': patch_v1_record(base, 0, length=len(body) + 1),
        }
        for case, blob in cases.items():
            with self.subTest(case=case), self.assertRaises(ArcError):
                self._open(blob)

    def test_rejects_payload_gaps_and_overlaps(self):
        bodies = [payload(stored=[b'first']), payload(stored=[b'second'])]
        base = make_v1_arc([('ONE.HTM', bodies[0]), ('TWO.HTM', bodies[1])])
        cases = {
            'gap': patch_v1_record(base, 0, length=len(bodies[0]) - 1),
            'overlap': patch_v1_record(base, 0, length=len(bodies[0]) + 1),
        }
        for case, blob in cases.items():
            with self.subTest(case=case), self.assertRaises(ArcError):
                self._open(blob)

    def test_rejects_trailing_data(self):
        blob = make_v1_arc([('ONE.HTM', payload(stored=[b'x']))])
        with self.assertRaises(ArcError):
            self._open(blob + b'unaccounted')


class TestDuplicateArchiveIdentity(unittest.TestCase):
    def _archive(self, language, page):
        manifest = (
            '<workunit><code>V22</code><type>PCED</type>'
            f'<title>{language}</title></workunit>'
        ).encode()
        return make_arc({
            'V22.EPL': payload(stored=[manifest]),
            page: payload(stored=[language.encode()]),
        })

    def test_exact_identity_keeps_same_code_archives_separate(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = os.path.join(temporary_directory, 'disc')
            english = os.path.join(root, 'content', 'useni4')
            french = os.path.join(root, 'content', 'cnfri4')
            os.makedirs(english)
            os.makedirs(french)
            with open(os.path.join(english, 'V22.arc'), 'wb') as file:
                file.write(self._archive('English', 'EN.HTM'))
            with open(os.path.join(french, 'V22.arc'), 'wb') as file:
                file.write(self._archive('French', 'FR.HTM'))

            source = DirSource(root)
            refs = source.archives()
            self.assertEqual(
                [ref.identity for ref in refs],
                ['content/cnfri4/v22.arc', 'content/useni4/v22.arc'],
            )
            self.assertEqual(
                [ref.output_dir for ref in refs], ['V22--CNFRI4', 'V22--USENI4']
            )

            output = os.path.join(temporary_directory, 'output')
            extract(source, output, archives=['content/useni4/v22.arc'], log=lambda _: None)
            self.assertTrue(os.path.exists(os.path.join(output, 'V22--USENI4', 'EN.HTM')))
            self.assertFalse(os.path.exists(os.path.join(output, 'V22--CNFRI4')))


class TestProbeReport(unittest.TestCase):
    def _report(self, deep):
        info = {
            'label': 'TEST', 'source': 'directory', 'deep': deep,
            'archives': [{
                'code': 'ABC', 'size': 1, 'version': 1, 'entries': 2,
                'extensions': {}, 'checked': 2, 'failed': 0,
                'stored_uncompressed': 0,
            }],
            'warnings': [], 'ok': True,
        }
        lines = []
        report(info, lines.append)
        return '\n'.join(lines)

    def test_distinguishes_sample_and_deep_results(self):
        self.assertIn('decoded 2 sampled', self._report(False))
        self.assertIn('decoded 2 entries (deep)', self._report(True))


# ---------------------------------------------------------------------- iso
def iso_image(stride=2048, data_off=0, label='TESTDISC'):
    """A volume descriptor is all SectorSource needs to identify the layout."""
    pvd = bytearray(2048)
    pvd[0:6] = b'\x01CD001'
    pvd[40:40 + len(label)] = label.encode().ljust(32)[:32]
    sectors = [bytes(2048)] * 16 + [bytes(pvd)]
    out = b''
    for s in sectors:
        raw = bytearray(stride)
        raw[data_off:data_off + 2048] = s
        out += bytes(raw)
    return out


class TestSectorSource(unittest.TestCase):
    def _open(self, blob):
        import io
        return SectorSource(io.BytesIO(blob))

    def test_plain_iso(self):
        s = self._open(iso_image(2048, 0))
        self.assertEqual((s.stride, s.data_off, s.raw), (2048, 0, False))

    def test_mode1_raw(self):
        s = self._open(iso_image(2352, 16))
        self.assertEqual((s.stride, s.data_off, s.raw), (2352, 16, True))

    def test_mode2_form1(self):
        s = self._open(iso_image(2352, 24))
        self.assertEqual((s.stride, s.data_off), (2352, 24))

    def test_with_subchannel(self):
        s = self._open(iso_image(2448, 16))
        self.assertEqual(s.stride, 2448)

    def test_reads_label(self):
        from fsd.iso import Iso9660
        # root record is zeroed here, so only check the label parse
        self.assertEqual(Iso9660(self._open(iso_image())).label, 'TESTDISC')

    def test_rejects_non_disc(self):
        with self.assertRaises(IsoError):
            self._open(b'\0' * 200000)


# ---------------------------------------------------------------- manifests
class TestEpl(unittest.TestCase):
    def test_basic(self):
        b = parse_epl('<workunit><type>SERVICE</type><code>SLB</code>'
                      '<vehicles><vehicle><year>2020</year><name>Mustang</name>'
                      '</vehicle></vehicles></workunit>')
        self.assertEqual((b.code, b.type, b.role), ('SLB', 'SERVICE', 'wsm'))
        self.assertEqual((b.years, b.models), (['2020'], ['Mustang']))

    def test_bare_ampersand_is_repaired(self):
        """Real manifests put an unescaped & inside a <dest> URL."""
        b = parse_epl('<workunit><type>EVTM</type><code>ELB</code><sections>'
                      '<section><title>Contents</title>'
                      '<dest>x.asp?a=1&b=2&legacy=N</dest></section>'
                      '</sections></workunit>')
        self.assertEqual((b.code, b.type), ('ELB', 'EVTM'))
        self.assertEqual(b.title, '', 'a section title must not become the book title')

    def test_unparseable_falls_back(self):
        b = parse_epl('<workunit><type>PCED</type><code>VL2</code>'
                      '<title>Gasoline Engines</title><unclosed>')
        self.assertEqual((b.code, b.type, b.title),
                         ('VL2', 'PCED', 'Gasoline Engines'))

    def test_not_a_manifest(self):
        self.assertIsNone(parse_epl('<other><thing>1</thing></other>'))

    def test_unknown_type_has_no_role(self):
        self.assertIsNone(parse_epl('<workunit><type>WIDGET</type>'
                                    '<code>ZZ</code></workunit>').role)


# -------------------------------------------------------------------- build
class TestBuildHelpers(unittest.TestCase):
    def _book(self, type_, models, years=('2020',), title=''):
        return Book(type_[:3], type_, title,
                    [{'year': y, 'name': m, 'engine': ''}
                     for y in years for m in models])

    def test_title_from_vehicle_book(self):
        self.assertEqual(
            site_title([self._book('SERVICE', ['Mustang'])]),
            '2020 Mustang Service Information')

    def test_shared_volume_does_not_name_the_disc(self):
        pced = self._book('PCED', ['Explorer', 'Escape', 'Edge'],
                          title='Gasoline Engines')
        wsm = self._book('SERVICE', ['Mustang'])
        self.assertEqual(site_title([pced, wsm]),
                         '2020 Mustang Service Information')

    def test_shared_volume_alone_uses_its_own_title(self):
        pced = self._book('PCED', ['Explorer', 'Escape', 'Edge'],
                          title='Gasoline Engines')
        self.assertEqual(site_title([pced]),
                         '2020 Gasoline Engines Service Information')

    def test_title_falls_back_to_label(self):
        self.assertEqual(site_title([], '20SLB'), '20SLB Service Information')

    def test_brand_parts(self):
        self.assertEqual(brand_parts('2020 Mustang Service Information'),
                         ('2020', 'Mustang', 'Service Information'))
        self.assertEqual(brand_parts('Ranger Service Information'),
                         ('FORD', 'Ranger', 'Service Information'))

    def test_engine_sizes_survive_tokenising(self):
        self.assertIn('5.0l', tokens('the 5.0L V8'))
        self.assertIn('2.3l', tokens('2.3L EcoBoost'))

    def test_frame_shells_are_dropped(self):
        out = clean_fragment(
            '<html><frameset cols="25%,*"><frame src="SLBLEFT.HTM">'
            '</frameset></html>', 'wsm')
        self.assertNotIn('src=', out)

    def test_images_are_rewritten_relative(self):
        out = clean_fragment('<body><img src="FOO.JPG"></body>', 'wsm')
        self.assertIn('src="content/wsm/foo.jpg"', out)
        self.assertNotIn('../', out)      # must work from a subdirectory
        self.assertIn('loading="lazy"', out)

    def test_links_become_hash_routes(self):
        out = clean_fragment('<body><a href="SLBG1234567.HTM">x</a></body>', 'wsm')
        self.assertIn('href="#/wsm/slbg1234567"', out)

    def test_dead_asp_links_are_redirected(self):
        out = clean_fragment(
            '<body><a href="/renderers/pced_2colframeset.asp?leftside=vl2s01l.htm'
            '&rightside=x">back</a></body>', 'pced')
        self.assertIn('href="#/pced/vl2s01l"', out)

    def test_external_links_cannot_navigate_from_manual_content(self):
        out = clean_fragment('<body><a href="http://example.com">x</a></body>', 'wsm')
        self.assertNotIn('href=', out)
        self.assertIn('>x</a>', out)


class TestSafeName(unittest.TestCase):
    def test_strips_path_traversal(self):
        for bad in ('../../etc/passwd', r'..\..\win.ini', '/abs/path'):
            self.assertNotIn('/', safe_name(bad))
            self.assertNotIn('\\', safe_name(bad))
            self.assertFalse(safe_name(bad).startswith('.'))

    def test_keeps_ordinary_names(self):
        self.assertEqual(safe_name('SLBG1234567.HTM'), 'SLBG1234567.HTM')


if __name__ == '__main__':
    unittest.main()
