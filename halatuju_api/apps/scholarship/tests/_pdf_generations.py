"""Synthetic PDFs for the OCR-12 render-gate tests: one object NUMBER that could mean two objects (OCR-12).

Pure bytes, no personal data: every page draws filled rectangles only. ``HEAVY`` is 20,000 full-page fills
(past the paint cap if the gate walks it); ``LIGHT`` one small fill. Each builder is a hostile file an adversarial
review used (2026-11-21, rounds 4 and 5 of the gate-generation work): the gate must refuse it.
"""
import zlib

HEAVY = b'0 g 0 0 595 842 re f\n' * 20_000
LIGHT = b'0 g 72 700 300 1 re f'
FORM = b'<< /Type /XObject /Subtype /Form /BBox [0 0 595 842]'
PAGE = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << %s >> /Contents %s%s >>'


def gen_stream(data, head=b'<<'):
    return head + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


class GenDoc:
    """Objects written in order, then cross-reference sections (oldest first): a table or a stream, each with
    explicit entries [(number, kind, generation, key)]: kind 'n' (key: the (number, generation) written), 'f' or
    'c' (packed: key unused, `packed` says where)."""

    def __init__(self):
        self.out, self.off, self.packed, self.prev, self.size = bytearray(b'%PDF-1.5\n'), {}, {}, None, 0

    def obj(self, num, gen, body):
        self.off[(num, gen)] = len(self.out)
        self.out += b'%d %d obj\n' % (num, gen) + body + b'\nendobj\n'
        self.size = max(self.size, num + 1)
        return self

    def table(self, entries, root=1):
        at = len(self.out)
        body = b'xref\n0 1\n0000000000 65535 f \n'
        for num, kind, gen, key in sorted(entries):
            body += b'%d 1\n%010d %05d %s \n' % (num, self.off[key] if kind == 'n' else 0, gen, kind.encode())
        prev = b'' if self.prev is None else b' /Prev %d' % self.prev
        self.out += body + b'trailer\n<< /Size %d /Root %d 0 R%s >>\nstartxref\n%d\n%%%%EOF\n' % (
            self.size + 10, root, prev, at)
        self.prev = at
        return self

    def xstm(self, num, entries, root=1):
        at, rows, idx = len(self.out), bytearray(), []
        for n, kind, gen, key in sorted(entries + [(num, 'self', 0, None)]):
            idx += [n, 1]
            if kind == 'n':
                rows += bytes([1]) + self.off[key].to_bytes(4, 'big') + gen.to_bytes(2, 'big')
            elif kind == 'self':
                rows += bytes([1]) + at.to_bytes(4, 'big') + bytes(2)
            elif kind == 'f':
                rows += bytes([0]) + bytes(4) + gen.to_bytes(2, 'big')
            else:
                stm, i = self.packed[n]
                rows += bytes([2]) + stm.to_bytes(4, 'big') + i.to_bytes(2, 'big')
        self.size = max(self.size, num + 1)
        prev = b'' if self.prev is None else b' /Prev %d' % self.prev
        head = b'<< /Type /XRef /Size %d /W [1 4 2] /Index [%s] /Root %d 0 R%s' % (
            self.size + 10, b' '.join(b'%d' % x for x in idx), root, prev)
        self.out += b'%d 0 obj\n' % num + gen_stream(bytes(rows), head) + b'\nendobj\n'
        self.out += b'startxref\n%d\n%%%%EOF\n' % at
        self.prev = at
        return self

    def bytes(self):
        return bytes(self.out)


def ents(*nums):
    return [(n, 'n', 0, (n, 0)) for n in nums]


def _base(d, page=None):
    d.obj(1, 0, b'<< /Type /Catalog /Pages 2 0 R >>').obj(2, 0, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    return d.obj(3, 0, page) if page is not None else d


def page(res=b'', contents=b'5 0 R', extra=b''):
    return PAGE % (res, contents, extra)


def _two(d, num, light, heavy, others):
    """``num`` gen 1 = light (the OLDER cross-reference stream), gen 0 = heavy (the newer)."""
    d.obj(num, 1, light).obj(num, 0, heavy)
    return d.xstm(20, others + [(num, 'n', 1, (num, 1))]).xstm(21, others + [(num, 'n', 0, (num, 0))]).bytes()


def wrong_generation(site):
    """The TD row's hole: a reference naming generation 1 of an object written as generation 0 (heavy)."""
    pages = {
        'contents': (page(contents=b'5 1 R'), {5: gen_stream(HEAVY)}),
        'annots': (page(contents=b'4 0 R', extra=b' /Annots [7 1 R]'),
                   {4: gen_stream(LIGHT), 7: b'<< /Type /Annot /Subtype /Square /Rect [0 0 595 842]'
                                             b' /AP << /N 6 0 R >> >>', 6: gen_stream(HEAVY, FORM)}),
        'ap': (page(contents=b'4 0 R', extra=b' /Annots [7 0 R]'),
               {4: gen_stream(LIGHT), 7: b'<< /Type /Annot /Subtype /Square /Rect [0 0 595 842]'
                                         b' /AP << /N 6 1 R >> >>', 6: gen_stream(HEAVY, FORM)}),
        'xobject': (page(b'/XObject << /X 6 1 R >>', b'4 0 R'),
                    {4: gen_stream(b'/X Do'), 6: gen_stream(HEAVY, FORM)}),
    }
    pg, objs = pages[site]
    d = _base(GenDoc(), pg)
    for num, body in objs.items():
        d.obj(num, 0, body)
    return d.table(ents(1, 2, 3, *objs)).bytes()


def page_node():
    """The PAGE object (a /Kids entry) has two versions."""
    d = _base(GenDoc()).obj(5, 0, gen_stream(LIGHT)).obj(6, 0, gen_stream(HEAVY))
    return _two(d, 3, page(contents=b'5 0 R'), page(contents=b'6 0 R'), ents(1, 2, 5, 6))


XPAGE = page(b'/XObject << /X 8 0 R >>')


def matrix():
    """A form's indirect /Matrix has two versions: tiny (gen 1) and identity (gen 0)."""
    d = _base(GenDoc(), XPAGE).obj(5, 0, gen_stream(b'/X Do')).obj(8, 0, gen_stream(HEAVY, FORM + b' /Matrix 9 0 R'))
    return _two(d, 9, b'[0.0001 0 0 0.0001 0 0]', b'[1 0 0 1 0 0]', ents(1, 2, 3, 5, 8))


def bbox():
    d = _base(GenDoc(), XPAGE).obj(5, 0, gen_stream(b'/X Do'))
    d.obj(8, 0, gen_stream(HEAVY, b'<< /Type /XObject /Subtype /Form /BBox 9 0 R'))
    return _two(d, 9, b'[0 0 0.01 0.01]', b'[0 0 595 842]', ents(1, 2, 3, 5, 8))


def rect():
    """An annotation's indirect /Rect has two versions."""
    d = _base(GenDoc(), page(extra=b' /Annots [7 0 R]')).obj(5, 0, gen_stream(LIGHT))
    d.obj(7, 0, b'<< /Type /Annot /Subtype /Square /Rect 9 0 R /AP << /N 8 0 R >> >>').obj(8, 0, gen_stream(HEAVY, FORM))
    return _two(d, 9, b'[0 0 0.01 0.01]', b'[0 0 595 842]', ents(1, 2, 3, 5, 7, 8))


def parent():
    """Inherited /Resources: the page's /Parent node (2) has two versions, one naming a heavy form."""
    d = GenDoc().obj(1, 0, b'<< /Type /Catalog /Pages 2 0 R >>')
    d.obj(3, 0, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 5 0 R >>')
    d.obj(5, 0, gen_stream(b'/X Do')).obj(6, 0, gen_stream(LIGHT, FORM)).obj(8, 0, gen_stream(HEAVY, FORM))
    node = b'<< /Type /Pages /Kids [3 0 R] /Count 1 /Resources << /XObject << /X %d 0 R >> >> >>'
    return _two(d, 2, node % 6, node % 8, ents(1, 3, 5, 6, 8))


def object_stream():
    """The page's /Resources (11) is packed in object stream 10, which has two versions (light, heavy form)."""
    d = _base(GenDoc(), page(contents=b'5 0 R').replace(b'/Resources <<  >>', b'/Resources 11 0 R'))
    d.obj(5, 0, gen_stream(b'/X Do')).obj(6, 0, gen_stream(LIGHT, FORM)).obj(8, 0, gen_stream(HEAVY, FORM))
    for gen, x in ((1, 6), (0, 8)):
        d.obj(10, gen, gen_stream(b'11 0 << /XObject << /X %d 0 R >> >>' % x, b'<< /Type /ObjStm /N 1 /First 5'))
    d.packed[11] = (10, 0)
    d.xstm(20, ents(1, 2, 3, 5, 6, 8) + [(10, 'n', 1, (10, 1)), (11, 'c', 0, None)])
    return d.xstm(21, ents(1, 2, 3, 5, 6, 8) + [(10, 'n', 0, (10, 0)), (11, 'c', 0, None)]).bytes()


def length():
    """The content stream's indirect /Length has two versions: short (gen 1) and the whole heavy stream (gen 0)."""
    d = _base(GenDoc(), page())
    data = LIGHT + b'\n' + HEAVY
    d.obj(5, 0, b'<< /Length 9 0 R >>\nstream\n' + data + b'\nendstream')
    return _two(d, 9, b'%d' % len(LIGHT), b'%d' % len(data), ents(1, 2, 3, 5))


def filters():
    """The content stream's indirect /Filter has two versions: one Flate pass and two, over twice-compressed data."""
    d = _base(GenDoc(), page()).obj(5, 0, gen_stream(zlib.compress(zlib.compress(HEAVY)), b'<< /Filter 9 0 R'))
    return _two(d, 9, b'/FlateDecode', b'[/FlateDecode /FlateDecode]', ents(1, 2, 3, 5))


def font_file():
    """A TrueType font's /FontFile2 has two versions: 16 bytes (gen 1) and a Flate stream inflating to 5 MB."""
    d = _base(GenDoc(), page(b'/Font << /F1 7 0 R >>')).obj(5, 0, gen_stream(b'BT /F1 12 Tf 72 700 Td (Hi) Tj ET'))
    d.obj(7, 0, b'<< /Type /Font /Subtype /TrueType /BaseFont /Arial /FirstChar 32 /LastChar 126'
                b' /FontDescriptor 8 0 R >>')
    d.obj(8, 0, b'<< /Type /FontDescriptor /FontName /Arial /Flags 32 /FontBBox [0 0 1000 1000] /ItalicAngle 0'
                b' /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 /FontFile2 9 0 R >>')
    d.obj(9, 1, gen_stream(bytes(16))).obj(9, 0, gen_stream(zlib.compress(bytes(5_000_000), 9), b'<< /Filter /FlateDecode'))
    return d.xstm(20, ents(1, 2, 3, 5, 7, 8) + [(9, 'n', 1, (9, 1))]).xstm(
        21, ents(1, 2, 3, 5, 7, 8) + [(9, 'n', 0, (9, 0))]).bytes()


def newer_section(ref=b'5 0 R'):
    """Round 4: two cross-reference streams, the older lists 5 gen 1 (light), the newer 5 gen 0 (heavy)."""
    d = _base(GenDoc(), page(contents=ref)).obj(5, 1, gen_stream(LIGHT)).obj(5, 0, gen_stream(HEAVY))
    return d.xstm(20, ents(1, 2, 3) + [(5, 'n', 1, (5, 1))]).xstm(21, ents(1, 2, 3) + [(5, 'n', 0, (5, 0))]).bytes()


def incremental(newest_names_last=True, bump=False, ref=b'5 0 R', first=LIGHT):
    """An incremental update rewriting object 5 (``first``, then light), each save with its own table. With
    ``newest_names_last=False`` the update's table names the OLD copy and the last header is heavy instead.
    ``bump`` gives the rewrite generation 1 (the page then references ``ref``)."""
    d = _base(GenDoc(), page(contents=ref)).obj(5, 0, gen_stream(first)).table(ents(1, 2, 3, 5))
    d.off[('old', 5)] = d.off[(5, 0)]
    gen = 1 if bump else 0
    d.obj(5, gen, gen_stream(LIGHT if newest_names_last else HEAVY))
    key = (5, gen) if newest_names_last else ('old', 5)
    return d.table([(5, 'n', gen if newest_names_last else 0, key)]).bytes()


def shifted_table():
    """A table whose entry for object 5 lands on object 3's header (a sloppy writer); pypdf repairs it."""
    d = _base(GenDoc(), page()).obj(5, 0, gen_stream(LIGHT))
    return d.table(ents(1, 2, 3) + [(5, 'n', 0, (3, 0))]).bytes()


#: A heavy copy of object 5 whose header a comment splits, in a file whose startxref points nowhere (rebuilt).
COMMENT_SPLIT = {'r1': b'5 1 %c\nobj', 'r2': b'5 1\n%c\nobj', 'r3': b'5\n%x\n1 obj'}


def comment_split(head):
    out = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
    out += b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
    out += b'3 0 obj\n' + page() + b'\nendobj\n5 0 obj\n' + gen_stream(LIGHT) + b'\nendobj\n'
    out += head + b'\n' + gen_stream(HEAVY) + b'\nendobj\n'
    return out + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n999999999\n%%EOF\n'


def many_headers(n):
    """A light, valid page plus an unreferenced stream holding ``n`` copies of '7 0 obj' (timing)."""
    d = _base(GenDoc(), page()).obj(5, 0, gen_stream(LIGHT)).obj(6, 0, gen_stream(b'7 0 obj\n' * n))
    return d.table(ents(1, 2, 3, 5, 6)).bytes()


def retail(pdf, tail):
    """``pdf`` with its last line ('startxref', offset, '%%EOF') rewritten as ``tail % offset`` (review 1: a tail
    that is not a clean word sends pdfium's backwards search to the OLDER startxref)."""
    at = pdf.rindex(b'startxref\n')
    return pdf[:at] + tail % int(pdf[at + 10:].split()[0])


def _one_table(chunks, listed, tail=b'startxref\n%d\n%%%%EOF\n'):
    """``chunks`` [(key, bytes)] written in order after the catalogue and page tree; ONE table listing ``listed``
    [(number, key)]."""
    d = _base(GenDoc())
    for key, raw in chunks:
        d.off[key] = len(d.out)
        d.out += raw
    at = len(d.out)
    d.out += b'xref\n0 1\n0000000000 65535 f \n' + b''.join(
        b'%d 1\n%010d 00000 n \n' % (n, d.off[k]) for n, k in [(1, (1, 0)), (2, (2, 0))] + listed)
    return bytes(d.out + b'trailer\n<< /Size 10 /Root 1 0 R >>\n' + tail % at)


def _o(num, body, head=None):
    return (head or b'%d 0 obj' % num) + b'\n' + body + b'\nendobj\n'


def orphan_object_stream(type_name=b'/ObjStm', decoy=b''):
    """Page 3 draws light object 6; an object stream NO entry names (written after it) packs a second copy of the
    page drawing heavy object 7. pdfium's rebuild reads it. ``decoy`` goes in its dictionary before /Type (review
    2: a header in a comment or a string there)."""
    packed = b'3 0 ' + page(contents=b'7 0 R')
    stm = gen_stream(packed, b'<< %s/Type %s /N 1 /First 4' % (decoy, type_name))
    return _one_table([('p', _o(3, page(contents=b'6 0 R'))), ('l', _o(6, gen_stream(LIGHT))),
                       ('h', _o(7, gen_stream(HEAVY))), ('s', _o(9, stm))], [(3, 'p'), (6, 'l')])


def dotted_number():
    """The table names light 5; a later header '5.0 0 obj' (heavy) is object 5 to pdfium's number word."""
    return _one_table([('p', _o(3, page())), ('l', _o(5, gen_stream(LIGHT))),
                       ('h', _o(5, gen_stream(HEAVY), b'5.0 0 obj'))], [(3, 'p'), (5, 'l')])


def last_copy_in_string():
    """Heavy 5, then object 8: a string whose text is a complete light '5 0 obj ... endobj', which the table names.
    pdfium's rebuild skips the string and keeps the heavy copy; the tail is clean."""
    return _one_table([('p', _o(3, page())), ('h', _o(5, gen_stream(HEAVY))), ('s', b'8 0 obj\n(\n'),
                       ('l', _o(5, gen_stream(LIGHT))), ('e', b')\nendobj\n')], [(3, 'p'), (5, 'l'), (8, 's')])


#: Review 2 decoys in an orphan object stream's dictionary: a comment, a string, and a string holding a whole
#: readable object stream (the nearest header then reads; only the top-level walk finds the real one).
DECOYS = {'comment': b'%99 0 obj\n', 'string': b'/X (99 0 obj) ',
          'readable': b'/X (99 0 obj\n<< /Type /ObjStm /N 1 /First 4 /Length 8 >>\nstream\n4 0 null\nendstream\n) '}


def leading_zeros(zeros, digits=b'6'):
    """The table names light 6; a later heavy header is ``zeros`` zeros then ``digits``, ' 0 obj' (review 2)."""
    return _one_table([('p', _o(3, page(contents=b'6 0 R'))), ('l', _o(6, gen_stream(LIGHT))),
                       ('h', _o(6, gen_stream(HEAVY), b'0' * zeros + digits + b' 0 obj'))], [(3, 'p'), (6, 'l')])


def packed_page(pairs, sep=b' ', idx=1):
    """Page 3 packed in object stream 9, whose header lists ``pairs`` [(number word, body)], every word split by
    ``sep``; the entry for 3 names member ``idx`` (review 2: pdfium and pypdf read such a header differently)."""
    head, data = [], b''
    for word, body in pairs:
        head += [word, b'%d' % len(data)]
        data += body + b'\n'
    head = sep.join(head) + b' '
    d = _base(GenDoc()).obj(6, 0, gen_stream(LIGHT)).obj(7, 0, gen_stream(HEAVY))
    d.obj(9, 0, gen_stream(head + data, b'<< /Type /ObjStm /N %d /First %d' % (len(pairs), len(head))))
    d.packed[3] = (9, idx)
    return d.xstm(10, ents(1, 2, 6, 7, 9) + [(3, 'c', 0, None)]).bytes()


LIGHT_PAGE, HEAVY_PAGE = page(contents=b'6 0 R'), page(contents=b'7 0 R')


def comment_digits(size):
    """A light, valid page after one comment line '%1%1%1...' of ``size`` bytes (the old header scan: quadratic)."""
    d = GenDoc()
    d.out += b'%' + b'1%' * (size // 2) + b'\n'
    return _base(d, page()).obj(5, 0, gen_stream(LIGHT)).table(ents(1, 2, 3, 5)).bytes()


def many_objects(n, forms=0):
    """A page of ``n`` tiny fills (within every gate cap), or ``forms`` form XObjects drawing ``n`` fills each."""
    fills = b'0 g 0 0 1 1 re f\n' * n
    if not forms:
        return _base(GenDoc(), page()).obj(5, 0, gen_stream(fills)).table(ents(1, 2, 3, 5)).bytes()
    names = b' '.join(b'/F%d 6 0 R' % k for k in range(forms))
    draw = b''.join(b'/F%d Do\n' % k for k in range(forms))
    d = _base(GenDoc(), page(b'/XObject << %s >>' % names)).obj(5, 0, gen_stream(draw))
    return d.obj(6, 0, gen_stream(fills, FORM)).table(ents(1, 2, 3, 5, 6)).bytes()


def junk_in_stream(junk):
    """A light, valid page; ``junk`` inside an unreferenced stream (the regex scans read it, the walk skips it)."""
    d = _base(GenDoc(), page()).obj(5, 0, gen_stream(LIGHT)).obj(6, 0, gen_stream(junk))
    return d.table(ents(1, 2, 3, 5, 6)).bytes()


def junk_in_update(junk):
    """An incremental update (object 5 twice, the exception's case: the rebuild walk runs) with ``junk`` at the
    top level before it."""
    d = _base(GenDoc(), page())
    d.out += junk
    d.obj(5, 0, gen_stream(LIGHT)).table(ents(1, 2, 3, 5))
    return d.obj(5, 0, gen_stream(LIGHT)).table([(5, 'n', 0, (5, 0))]).bytes()
