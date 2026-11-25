"""OCR-12 review round 1 (2026-11-24): EVERY cross-reference row of the file, in every section, for
`pdf_object_identity`.

pypdf keeps one row per (generation, number), the newest, and only rows of type 'n'; pdfium keys rows by number
alone (the newest wins, in any generation) and takes any type but 'f' as in use. So a row pypdf overrides or
ignores can be the one pdfium follows (a newer row of type 'x', or of another generation, pointing at the '3' of
'13 0 obj'). This walk reads the chain the way both start it (`pdfium_startxref`, which must be pypdf's own
start too, then each /Prev and /XRefStm, newest first) and keeps every row it meets. A classic table is read
both as pypdf reads it (a row realigned at a CR or LF) and as pdfium does (20 bytes a row from the subsection
start), and both readings are kept. Review round 2: the walk reads the WHOLE chain or refuses the file. A start
pdfium cannot find, a link to where no section starts, a loop, a link that is not a whole number: pdfium then
rebuilds from bytes this walk has not read (or follows a chain pypdf does not), so the file is refused. /Prev 0
ends the chain and /XRefStm 0 is no link (both readers). Round 3: a start pdfium cannot find (a long tail) is a
rebuild from the object headers, which the one-header rule covers: the walk then reads pypdf's chain. Offsets
pdfium follows count from its header (bytes before '%PDF'). All work is charged.
"""
import io
import re

from pypdf.generic import ArrayObject, StreamObject, read_object

#: The most rows one file may hold across its sections (memory bound). The corpus max is a few thousand.
MAX_ROWS = 200_000
MAX_SECTIONS = 1_000
_ROW_WORK = 300                # one row parsed and kept (pdf_layer_guards._ROW_WORK)
_SECTION_WORK = 3_000          # one section found and its dictionary parsed (about one counted read)
_WS = b'\x00\t\n\x0c\r '
_LEAD = re.compile(rb'(?:[\x00\t\n\x0c\r ]|%[^\r\n]*)*')
#: pdfium's byte classes (fpdf_parser_utility.cpp): white space (0x80 and 0xff too), number bytes, delimiters.
_P_WHITE = frozenset(b'\x00\t\n\x0c\r \x80\xff')
_P_NUMERIC = frozenset(b'0123456789+-.')
_P_DELIM = frozenset(b'%()/<>[]{}')
_KEYWORD = b'startxref'
_TAIL_LIMIT = 4096             # pdfium searches back this far from the end for 'startxref'
_HEADER_SIZE = 9               # pdfium rebuilds when the start is below this
_HEADER_LIMIT = 1024           # pdfium takes the first '%PDF' at offsets 0 to this (probe)
_SUBSECTION = re.compile(rb'(\d{1,10})[\x00\t\x0c ]+(\d{1,10})')
_STREAM_HEAD = re.compile(rb'(\d{1,10})[\x00\t\n\x0c\r ]+(\d{1,5})[\x00\t\n\x0c\r ]+obj')
#: A row: (section rank, kind, a, b). Kind 'n' in use (a offset, b generation), 'f' free, 'p' packed (a stream,
#: b index, generation 0), '?' a type neither reader agrees on. Rank 0 is the newest section; a hybrid file's
#: /XRefStm ranks just newer than its own table (both readers let its rows win there).


class Walk:
    def __init__(self, data: bytes, meter):
        self.data, self.meter = data, meter
        self.rows = {}               # number -> [row]
        self.count = 0
        self.heads = set()           # header offsets of the cross-reference streams read
        self.base = 0                # pdfium's header position, added to the offsets of the chain it follows
        self.rebuilt = False         # pdfium finds no start: it rebuilds, the walk reads pypdf's chain
        self._bio = io.BytesIO(data)

    def _row(self, rank, num, kind, a, b):
        self.count += 1
        self.meter.charge(_ROW_WORK)
        if self.count > MAX_ROWS:
            self.meter._refuse('cross-reference rows past the cap')
        self.rows.setdefault(num, []).append((rank, kind, a + self.base if kind == 'n' else a, b))

    def run(self, pypdf_start) -> None:
        """Read every section from the start both readers take (``pypdf_start``: pypdf's own, `PdfReader._startxref`)
        to the end of the chain, or refuse (review round 2, finding 1: a walk that stopped early switched the row
        checks off while both readers still followed the chain). Round 3: where pdfium finds no start it rebuilds
        from the object headers and follows no row; pypdf's chain is then walked from pypdf's start, every check
        still applied (and `pdf_object_identity` holds every trailer's /Root to pypdf's). Bytes before the header:
        pdfium reads every offset from its header, pypdf from byte 0, so both must read the same startxref number
        and the walk adds the header position to pdfium's offsets (probe)."""
        self.meter.charge(_TAIL_LIMIT + _SECTION_WORK)
        base, value = pdfium_start(self.data)
        if base is None:
            self.meter._refuse('the renderer finds no file header')
        if value is None:                              # pdfium rebuilds; pypdf follows its own chain
            self.rebuilt, start = True, pypdf_start
        elif value != pypdf_start:
            self.meter._refuse('the gate and the renderer start the cross-reference in different places')
        else:
            self.base, start = base, value + base
        todo, seen, rank = [start], set(), 0
        while todo:
            pos = todo.pop(0)
            if pos in seen:                           # pdfium rebuilds on a loop; pypdf stops
                self.meter._refuse('a cross-reference chain that loops')
            seen.add(pos)
            if len(seen) > MAX_SECTIONS:
                self.meter._refuse('cross-reference sections past the cap')
            prev, xrefstm = self._section(pos, rank)
            if xrefstm is not None and xrefstm not in seen:
                seen.add(xrefstm)
                self._section(xrefstm, rank - 0.5)
            if prev is not None:
                todo.append(prev)
            rank += 1

    def _section(self, pos, rank):
        """Read one section's rows; return its (/Prev, /XRefStm), each None when it ends the chain or is no link.
        Refused: an offset where no section starts (neither the 'xref' keyword nor an object header: pdfium then
        rebuilds from the object headers, pypdf may search nearby), and a section that starts but that this walk
        cannot read (pdfium may read rows from it that the gate never saw)."""
        self.meter.charge(_SECTION_WORK)
        data = self.data
        if not 0 < pos < len(data):
            self.meter._refuse('a cross-reference link to where no section starts')
        q = self._skip(pos)
        if data.startswith(b'xref', q):
            read = self._table
            q += 4
        elif _STREAM_HEAD.match(data, q):
            read = self._stream
        elif data[q:q + 1] and data[q] not in b'0123456789+-.':
            self.meter._refuse('a cross-reference link to where no section starts')
        else:
            read = _unreadable                         # number-like: pdfium may read a header this walk cannot
        try:
            trailer = read(q, rank)
        except Exception as e:                       # an unreadable section is refused; OverBudget passes
            if type(e).__name__ == 'OverBudget':
                raise
            trailer = None
        if trailer is None:
            self.meter._refuse('a cross-reference section the gate cannot read')
        return self._link(trailer, '/Prev'), self._link(trailer, '/XRefStm')

    def _link(self, trailer, key):
        """A /Prev or /XRefStm value: None when absent or 0 (pdfium: a value not above 0 is no link; pypdf: /Prev 0
        ends the chain, an /XRefStm at 0 is unreadable and skipped). Refused: a link that is not a whole number
        above 0 (pdfium reads a real number's whole part, pypdf cannot seek to it) or is negative (pypdf seeks
        before the file)."""
        if key not in trailer:
            return None
        v = _trailer_int(trailer.get(key))
        if v is None or v < 0:
            self.meter._refuse('a cross-reference link the gate cannot read')
        return v + self.base if v else None

    def _skip(self, q):
        """Past white space and comments (both readers skip them between words)."""
        end = _LEAD.match(self.data, q).end()
        self.meter.charge(end - q)
        return end

    def _table(self, q, rank):
        data = self.data
        start_q = q
        while True:
            q = self._skip(q)
            if data.startswith(b'trailer', q):
                self.meter.charge(q - start_q)
                self._bio.seek(self._skip(q + 7))
                trailer = read_object(self._bio, _NO_LOOKUPS)
                self.meter.charge(self._bio.tell() - q)
                return trailer if isinstance(trailer, dict) else None
            m = _SUBSECTION.match(data, q)
            if not m:
                return None
            first, count = int(m.group(1)), int(m.group(2))
            q = self._skip(m.end())
            if q + 20 * count > len(data) + 20:
                return None
            for i in range(count):                    # pdfium: 20 bytes a row from the subsection start
                self._classic(rank, first + i, data[q + 20 * i:q + 20 * i + 20], pdfium=True)
            p = q
            for i in range(count):                    # pypdf: realigned at a CR or LF, 19 bytes after a digit
                line = data[p:p + 20]
                while line[:1] in (b'\r', b'\n'):
                    p += 1
                    line = data[p:p + 20]
                if len(line) < 20:
                    return None
                self._classic(rank, first + i, line, pdfium=False)
                p += 19 if line[-1:] in b'0123456789t' else 20
            q = p

    def _classic(self, rank, num, line, pdfium):
        kind = line[17:18]
        if pdfium:
            off = re.match(rb'[ \t]*\+?(\d{1,19})', line[:10])
            gen = re.match(rb'[ \t]*\+?(\d{1,10})', line[11:16])
            a, b = (int(off.group(1)) if off else -1), (int(gen.group(1)) if gen else -1)
        else:
            parts = line[:16].split(b' ')
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                return                              # pypdf finds this one by its own header search
            a, b = int(parts[0]), int(parts[1])
        if kind == b'f':
            self._row(rank, num, 'f', a, b)
        else:
            self._row(rank, num, 'n' if kind == b'n' else '?', a, b)

    def _stream(self, q, rank):
        m = _STREAM_HEAD.match(self.data, q)
        if not m:
            return None
        self.heads.add(q)
        self._bio.seek(self._skip(m.end()))
        xs = read_object(self._bio, _NO_LOOKUPS)             # an indirect /Length cannot be read here: not a section
        self.meter.charge(self._bio.tell() - q)
        if not isinstance(xs, StreamObject):
            return None
        w = xs.get('/W')
        size = _trailer_int(xs.get('/Size'))
        index = xs.get('/Index', ArrayObject([0, size if size is not None else 0]))
        if not (isinstance(w, list) and len(w) >= 3 and all(_trailer_int(x) is not None and 0 <= x <= 8 for x in w)):
            return None
        if not (isinstance(index, list) and len(index) % 2 == 0 and all(_trailer_int(x) is not None for x in index)):
            return None
        rows = xs.get_data()
        self.meter.charge(len(rows))
        width, p = sum(w), 0
        for j in range(0, len(index), 2):
            for num in range(index[j], index[j] + index[j + 1]):
                if width == 0 or p + width > len(rows):
                    return xs
                f = []
                for size_i in w[:3]:
                    f.append(int.from_bytes(rows[p:p + size_i], 'big') if size_i else None)
                    p += size_i
                p += width - sum(w[:3])
                t = 1 if f[0] is None else f[0]
                if t == 0:
                    self._row(rank, num, 'f', f[1] or 0, f[2] or 0)
                elif t == 1:
                    self._row(rank, num, 'n', f[1] or 0, f[2] or 0)
                elif t == 2:
                    self._row(rank, num, 'p', f[1] or 0, f[2] or 0)
                else:
                    self._row(rank, num, '?', f[1] or 0, f[2] or 0)
        return xs


def pdfium_start(data: bytes):
    """(pdfium's header position, the startxref number it reads), the number None where pdfium rebuilds; (None,
    None) where it finds no header. Round 3 probe (pypdfium2 4.30): the header is the first '%PDF' at offsets 0
    to 1024 (none further: pdfium cannot open the file), and every offset, the startxref number's too, counts
    from it; pypdf reads the same number from byte 0."""
    base = data.find(b'%PDF', 0, _HEADER_LIMIT + 4)
    if base < 0:
        return None, None
    return base, _startxref_value(data[base:] if base else data)


def pdfium_startxref(data: bytes):
    """The byte offset where pdfium starts the cross-reference, or None where it rebuilds (`pdfium_start`)."""
    base, value = pdfium_start(data)
    return None if value is None else base + value


def _startxref_value(data: bytes):
    """The startxref number pdfium reads (CPDF_Parser::ParseStartXRef) from the bytes after its header, or None
    where it finds none and rebuilds the table. Review round 2, finding 1, checked against pypdfium2 4.30 by probe
    (OCR-12 docs): pdfium searches BACK from 9 bytes before the end, at most 4096 bytes, for 'startxref' as a
    whole word (no number or regular byte just before it; just after it only while it starts within the first
    4087 bytes), then reads the word after it, past white space and comments: every byte a number byte (digits,
    + - .), its first 256 read as C's atoi64 (a sign, then digits). A start at or past the end, or below 9, is
    none."""
    size, top = len(data), len(data) - len(_KEYWORD)
    pos, k = top, len(_KEYWORD) - 1
    while True:                                   # BackwardsSearchToWord, byte for byte
        if pos <= top - _TAIL_LIMIT or pos < 0:
            return None
        byte = data[pos]
        if byte == _KEYWORD[k]:
            k -= 1
            if k >= 0:
                pos -= 1
                continue
            if _whole_word(data, pos):
                break
        k = len(_KEYWORD) - 2 if byte == _KEYWORD[-1] else len(_KEYWORD) - 1
        pos -= 1
        if pos < 0:
            return None
    q = pos
    while q < size and data[q] not in _P_DELIM and data[q] not in _P_WHITE:
        q += 1                                    # the keyword word itself (it may run on: 'startxrefs')
    while q < size:                               # ToNextWord: white space, then comments to a line end
        if data[q] in _P_WHITE:
            q += 1
        elif data[q] == 0x25:
            while q < size and data[q] not in b'\r\n':
                q += 1
        else:
            break
    if q >= size or data[q] in _P_DELIM:
        return None
    end = q
    while end < size and data[end] not in _P_DELIM and data[end] not in _P_WHITE:
        end += 1
    word = data[q:end]
    if not all(c in _P_NUMERIC for c in word):
        return None
    m = re.match(rb'([+-]?)(\d*)', word[:256])
    value = int(m.group(2) or b'0') * (-1 if m.group(1) == b'-' else 1)
    return value if _HEADER_SIZE <= value < size else None


def _whole_word(data, start):
    """pdfium's IsWholeWord for 'startxref' (limit 4096): the byte after is checked only while the word ends
    within the first 4096 bytes (pdfium compares a file offset with the limit)."""
    end = start + len(_KEYWORD)
    if end <= _TAIL_LIMIT and end < len(data) and data[end] not in _P_WHITE and data[end] not in _P_DELIM:
        return False
    return not (start > 0 and data[start - 1] not in _P_WHITE and data[start - 1] not in _P_DELIM)


def _unreadable(q, rank):
    return None


def _trailer_int(v):
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else None


class _Unreadable(Exception):
    pass


class _NoLookups:
    """The 'reader' pypdf's parser is handed here: a reference is kept as written, a /Length that is one ends the
    read (the section is then unreadable). The walk never looks an object up (no lookup to check, no recursion)."""
    strict = False

    def get_object(self, ref):
        raise _Unreadable('an indirect value in a cross-reference section')


_NO_LOOKUPS = _NoLookups()
