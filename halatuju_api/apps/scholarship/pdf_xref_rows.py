"""OCR-12 review round 1 (2026-11-24): EVERY cross-reference row of the file, in every section, for
`pdf_object_identity`.

pypdf keeps one row per (generation, number), the newest, and only rows of type 'n'; pdfium keys rows by number
alone (the newest wins, in any generation) and takes any type but 'f' as in use. So a row pypdf overrides or
ignores can be the one pdfium follows (a newer row of type 'x', or of another generation, pointing at the '3' of
'13 0 obj'). This walk reads the chain the way both start it (the last 'startxref', then each /Prev and
/XRefStm, newest first) and keeps every row it meets. A classic table is read both as pypdf reads it (a row
realigned at a CR or LF) and as pdfium does (20 bytes a row from the subsection start), and both readings are
kept. An offset where no section starts ends the walk there (`Walk.complete` is then False; both readers then
rebuild from the object headers); a section that starts there but cannot be read is refused. All work is charged.
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
_STARTXREF =re.compile(rb'startxref[\x00\t\n\x0c\r ]*(\d{1,12})')
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
        self.complete = True
        self.heads = set()           # header offsets of the cross-reference streams read
        self._bio = io.BytesIO(data)

    def _row(self, rank, num, kind, a, b):
        self.count += 1
        self.meter.charge(_ROW_WORK)
        if self.count > MAX_ROWS:
            self.meter._refuse('cross-reference rows past the cap')
        self.rows.setdefault(num, []).append((rank, kind, a, b))

    def run(self) -> None:
        data = self.data
        at = data.rfind(b'startxref')
        self.meter.charge(len(data) - max(at, 0) + _SECTION_WORK)
        m = _STARTXREF.match(data, at) if at >= 0 else None
        todo, seen, rank = ([int(m.group(1))] if m else []), set(), 0
        if not m:
            self.complete = False
        while todo:
            pos = todo.pop(0)
            if pos in seen:
                continue
            seen.add(pos)
            if len(seen) > MAX_SECTIONS:
                self.meter._refuse('cross-reference sections past the cap')
            links = self._section(pos, rank)
            if links is None:
                self.complete = False
                return
            prev, xrefstm = links
            if xrefstm is not None and xrefstm not in seen:
                seen.add(xrefstm)
                if self._section(xrefstm, rank - 0.5) is None:
                    self.complete = False
                    return
            if prev is not None:
                todo.append(prev)
            rank += 1

    def _section(self, pos, rank):
        """Read one section's rows; return (/Prev, /XRefStm), or None when no section starts there (neither the
        'xref' keyword nor an object header: no reader can take rows from it, both rebuild from the object
        headers, which `pdf_object_identity` holds to one per number). A section that starts but that this walk
        cannot read is refused: pdfium may read rows from it that the gate never saw."""
        self.meter.charge(_SECTION_WORK)
        data = self.data
        if not 0 < pos < len(data):                  # /Prev 0 is the file header: the chain ends (both readers)
            return None
        q = self._skip(pos)
        if data.startswith(b'xref', q):
            read = self._table
            q += 4
        elif _STREAM_HEAD.match(data, q):
            read = self._stream
        elif data[q:q + 1] and data[q] not in b'0123456789+-.':
            return None                               # a word no reader takes as a section start
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
        return _trailer_int(trailer.get('/Prev')), _trailer_int(trailer.get('/XRefStm'))

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
