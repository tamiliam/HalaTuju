"""OCR-12, new design (2026-11-24): every object number the PDF gate USES resolves to ONE object.

pypdf (the gate's reader) and pdfium (the renderer) find objects differently. pypdf follows the cross-reference
row and repairs a bad one by a regex search; pdfium, when the table looks wrong, rebuilds it by reading the whole
file word by word (skipping comments, strings and, by /Length, stream data), keeps the LAST copy of a number,
parses every object stream it finds, and follows a reference by number alone. A doctored file can hold two
objects under one number (a light page for pypdf, a heavy or different one for pdfium): round 4 hid the second
copy behind '3.' (pdfium reads 3) and a /Length the gate's walk read differently. The earlier design rebuilt the
table the way pdfium does and compared; any byte-level disagreement with pdfium's parser reopened the hole.

This design does not model pdfium's parser. It takes evidence that does not depend on /Length, strings or
comments, a SUPERSET of every place either reader could find an object:
1. Every ``N G obj`` header in the raw file (`_STRICT`), inside strings, streams and comments too, keyed by N
   alone (pdfium ignores the generation), and every member of every object stream the cross-reference names.
2. Any other ``obj`` word that a number word, a comment or odd white space could turn into a header for
   pdfium (`_odd_header`): '3.', '+3', '0003', a 256-byte number pdfium cuts short, '3 0 %x<EOL>obj'. One
   anywhere refuses the file: no one can say which number pdfium gives it.
3. An /ObjStm stream the cross-reference does not name (pdfium parses it; pypdf never looks) refuses the file.
4. Every cross-reference row in every section (`pdf_xref_rows`), the rows pypdf ignores or overrides too.
Then each lookup pypdf makes, at open and after, is checked (`check`): its number has at most ONE candidate; a
row-based object sits exactly on that header (only white space or comments before it, as both read it), of
the same generation; a packed object is in exactly one stream, at the row's own index, and has no raw header;
pypdf finding nothing while a candidate exists (a generation pdfium ignores) is refused too; and every row any
section holds for that number agrees (`_rows_check`, review round 1). All work is charged to the reader's
lookup budget (`pdf_layer_guards`). Not checked: what pdfium does with the bytes of an object stream whose own
/Length it reads differently (stream extents in general), and filter decoding cost (TD-712).
"""
import bisect
import re

from pypdf.generic import NullObject

from .pdf_xref_rows import Walk

_WS = rb'\x00\t\n\x0c\r '
_BARE = rb'[^\x00\t\n\x0c\r ()<>\[\]{}/%]'
_OBJ_WORD = re.compile(rb'(?<!' + _BARE + rb')obj(?!' + _BARE + rb')')
_STRICT = re.compile(rb'(?<!' + _BARE + rb')(\d+)[' + _WS + rb']+(\d+)[' + _WS + rb']+obj(?!' + _BARE + rb')')
_CLEAN_NUM = re.compile(rb'0|[1-9]\d{0,8}')
_CLEAN_GEN = re.compile(rb'0|[1-9]\d{0,4}')
_LEAD = re.compile(rb'(?:[' + _WS + rb']|%[^\r\n]*)*')          # what pypdf skips before a header
_NAME = re.compile(rb'/' + _BARE + rb'*')
_BREAK = re.compile(rb'[\r\n]')
_NUMBERISH = frozenset(b'0123456789+-.')
_WHITE = frozenset(b'\x00\t\n\x0c\r ')
#: A number keeps at most this many candidates (memory bound): two already refuse a lookup. 17, the bound the
#: round-5 review suggested, also caps the work one number's evidence costs to record.
MAX_CANDIDATES = 17
_WORD_WORK = 3_000          # an 'obj' word found and judged: about one counted read's parsing (pdf_layer_guards)
_PAIR_WORK = 300            # one object-stream index pair parsed


class Identity:
    """The evidence for one file, built once (`build`), and the check of each lookup (`check`)."""

    def __init__(self, reader):
        self.reader = reader
        self.data = None
        self.headers = {}          # number -> {byte offset of a clean header: generation}, MAX_CANDIDATES at most
        self.owners = []           # (offset, number) of EVERY clean header, in file order (round 1, finding 4)
        self.breaks = None         # offsets of every CR and LF, found once at the first odd 'obj' word
        self.packed = None         # number -> [(stream, index)], built at the first check after open
        self.walk = None           # every cross-reference row (`pdf_xref_rows`), read at the first check
        self.checked = set()
        self.rows_checked = set()

    def _refuse(self, why: str):
        self.reader._counted._refuse(why)

    def build(self) -> None:
        """The raw scan: one copy of the file (charged as one read), every 'obj' word judged."""
        meter = self.reader._counted
        data = self.data = meter.getvalue()
        meter.charge(len(data) + _WORD_WORK)
        ends = {}
        for m in _STRICT.finditer(data):
            meter.charge(_WORD_WORK)
            num, gen = m.group(1), m.group(2)
            if not (_CLEAN_NUM.fullmatch(num) and _CLEAN_GEN.fullmatch(gen)):
                self._refuse('an object number the gate and the renderer may read differently')
            ends[m.end()] = None
            self.owners.append((m.start(), int(num)))
            seen = self.headers.setdefault(int(num), {})
            if len(seen) < MAX_CANDIDATES:
                seen[m.start()] = int(gen)
        for m in _OBJ_WORD.finditer(data):
            if m.end() not in ends:
                meter.charge(_WORD_WORK)
                if self.breaks is None:                  # finding 5: each line start is found once, by bisect
                    meter.charge(len(data))
                    self.breaks = [b.start() for b in _BREAK.finditer(data)]
                if _odd_header(data, m.start(), self.breaks, meter):
                    self._refuse('an object header the gate cannot read')

    def _objstm_names(self):
        """Offsets of every /ObjStm name in the raw file, a #-escaped spelling included."""
        data, meter = self.data, self.reader._counted
        meter.charge(len(data))
        for m in _NAME.finditer(data):
            name = m.group()
            if b'#' in name:
                meter.charge(len(name))
                try:
                    name = re.sub(rb'#([0-9A-Fa-f]{2})', lambda e: bytes([int(e.group(1), 16)]), name)
                except ValueError:
                    continue
            if name == b'/ObjStm':
                yield m.start()

    def _build_packed(self) -> None:
        reader, meter = self.reader, self.reader._counted
        self.packed = {}
        self.walk = Walk(self.data, meter)
        self.walk.run()
        streams = {stm for stm, _ in reader.xref_objStm.values()}
        starts = [at for at, _ in self.owners]
        for at in self._objstm_names():
            meter.charge(_WORD_WORK)               # finding 4: the owning header by bisect, not a scan of all
            k = bisect.bisect_right(starts, at) - 1
            if k < 0 or self.owners[k][1] not in streams:
                self._refuse('an object stream the cross-reference does not name')
        for stm in sorted(streams):
            obj = reader.get_object(stm)
            n, first = obj.get('/N'), obj.get('/First')
            if not isinstance(n, int) or not isinstance(first, int) or n < 0 or first < 0:
                self._refuse('an object stream index the gate cannot read')
            words = obj.get_data()[:first].split()
            meter.charge(_PAIR_WORK * (len(words) + 1))
            if len(words) != 2 * n or not all(w.isdigit() for w in words):
                self._refuse('an object stream index the gate cannot read')
            for i in range(n):
                self.packed.setdefault(int(words[2 * i]), []).append((stm, i))

    def _on_header(self, num: int, row: int, gen: int) -> bool:
        """Does a row (offset ``row``, generation ``gen``) sit on ``num``'s ONE clean header (only white space or
        comments before it, which both readers skip)?"""
        raw = self.headers.get(num, {})
        if len(raw) != 1:
            return False
        (at, raw_gen), = raw.items()
        return raw_gen == gen and 0 <= row <= at and _LEAD.match(self.data, row).end() == at

    def _rows_check(self, num: int, missing: bool) -> None:
        """Round 1, finding 1: EVERY row for ``num`` in every section and generation, the rows pdfium follows
        and pypdf ignores or overrides included (pdfium keys rows by number, newest wins, any type but 'f' in
        use). Refused: a row type other than n/f (0/1/2 in a stream); rows in use in two generations; a row in
        use not on the one header (or, packed, not the one place the object streams hold it); a free row as new
        as every row in use; an object pypdf read for a number with no row in use when the whole chain was read
        (a cross-reference stream's own header excepted)."""
        rows = self.walk.rows.get(num, [])
        self.reader._counted.charge(_PAIR_WORK * (len(rows) + 1))
        if any(kind == '?' for _, kind, _, _ in rows):
            self._refuse('object %d has a cross-reference row of an unknown type' % num)
        used = [r for r in rows if r[1] in 'np']
        if len({b if kind == 'n' else 0 for _, kind, _, b in used}) > 1:
            self._refuse('object %d is in use in more than one generation' % num)
        for _, kind, a, b in used:
            ok = (self._on_header(num, a, b) if kind == 'n'
                  else not self.headers.get(num) and self.packed.get(num) == [(a, b)])
            if not ok:
                self._refuse('object %d has a cross-reference row that is not its one copy' % num)
        frees = [rank for rank, kind, _, _ in rows if kind == 'f']
        if used and frees and min(frees) <= min(r[0] for r in used):
            self._refuse('object %d is free in a newer cross-reference row' % num)
        if not used and not missing and self.walk.complete and num not in self.reader.xref_objStm:
            raw = self.headers.get(num, {})
            if not (len(raw) == 1 and next(iter(raw)) in self.walk.heads):
                self._refuse('object %d has no cross-reference row' % num)

    def check(self, num: int, gen: int, found) -> None:
        """Refuse (OverBudget, via the reader's meter) unless pypdf's answer for (num, gen) is the ONE object
        any reader could find under ``num``."""
        if (num, gen) in self.checked:
            return
        self.checked.add((num, gen))
        reader = self.reader
        if self.packed is None:
            self._build_packed()
        missing = found is None or isinstance(found, NullObject)
        if num not in self.rows_checked:
            self.rows_checked.add(num)
            self._rows_check(num, missing)
        raw = self.headers.get(num, {})
        packed = self.packed.get(num, [])
        if len(raw) + len(packed) > 1:
            self._refuse('object %d has more than one copy' % num)
        if gen == 0 and num in reader.xref_objStm:       # a miss is fine only when no copy exists anywhere
            # finding 2: the stream AND the row's index. pypdf's rebuild (no chain read) stores a byte offset
            # there, which pypdf ignores; the walk's rows are then none, and pdfium's rebuild takes the index.
            stm, idx = reader.xref_objStm[num]
            if not self.walk.complete and packed:
                idx = packed[0][1]
            if raw or (packed and packed != [(stm, idx)]) or (not packed) != missing:
                self._refuse('object %d is not where the cross-reference packs it' % num)   # finding 2: index too
            return
        row = reader.xref.get(gen, {}).get(num)
        if missing:
            if raw or packed:
                self._refuse('object %d exists but the gate did not read it' % num)
            return
        if packed or row is None or not self._on_header(num, row, gen):
            self._refuse('object %d was read from bytes that are not its header' % num)


def _odd_header(data: bytes, at: int, breaks, meter) -> bool:
    """Could pdfium read the 'obj' word at ``at`` as an object header? True when, skipping white space and
    comments back from it, a number-like byte comes first. Any '%' on a line may start a comment (or sit in a
    string), so EVERY one is tried (round 1, finding 3): the line's end, and the bytes before each '%'. Each line
    is searched once (its start by bisect in ``breaks``, finding 5); past 64 candidates, True."""
    todo, lines, steps = [at], set(), 0
    while todo:
        p = todo.pop()
        steps += 1
        if steps > 64:
            return True
        q = p
        while q > 0 and data[q - 1] in _WHITE:
            q -= 1
        meter.charge(p - q + 1)
        if q == 0:
            continue
        if data[q - 1] in _NUMBERISH:
            return True
        k = bisect.bisect_left(breaks, q - 1) - 1
        line = breaks[k] + 1 if k >= 0 else 0
        if line in lines:          # first reached at its furthest point: every '%' before q is already queued
            continue
        lines.add(line)
        end, pct = q, data.find(b'%', line, q)
        while pct >= 0:
            todo.append(pct)
            if len(todo) > 64:
                end = pct
                break
            pct = data.find(b'%', pct + 1, q)
        meter.charge(end - line + 1)
    return False
