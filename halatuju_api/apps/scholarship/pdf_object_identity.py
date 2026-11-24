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
Then each lookup pypdf makes, at open and after, is checked (`check`): its number has at most ONE candidate; a
row-based object sits exactly on that header (only white space or one comment before it, as pypdf reads it), of
the same generation; a packed object is in exactly one stream and has no raw header; and pypdf finding nothing
while a candidate exists (a generation pdfium ignores) is refused too. All work is charged to the reader's
lookup budget (`pdf_layer_guards`). Not checked: what pdfium does with the bytes of an object stream whose own
/Length it reads differently (stream extents in general), and filter decoding cost (TD-712).
"""
import bisect
import re

from pypdf.generic import NullObject

_WS = rb'\x00\t\n\x0c\r '
_BARE = rb'[^\x00\t\n\x0c\r ()<>\[\]{}/%]'
_OBJ_WORD = re.compile(rb'(?<!' + _BARE + rb')obj(?!' + _BARE + rb')')
_STRICT = re.compile(rb'(?<!' + _BARE + rb')(\d+)[' + _WS + rb']+(\d+)[' + _WS + rb']+obj(?!' + _BARE + rb')')
_CLEAN_NUM = re.compile(rb'0|[1-9]\d{0,8}')
_CLEAN_GEN = re.compile(rb'0|[1-9]\d{0,4}')
_LEAD = re.compile(rb'(?:[' + _WS + rb']|%[^\r\n]*)*')          # what pypdf skips before a header
_NAME = re.compile(rb'/' + _BARE + rb'*')
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
        self.headers = {}          # number -> {byte offset of a clean header: generation}
        self.starts = []           # sorted header offsets
        self.packed = None         # number -> [(stream, index)], built at the first check after open
        self.checked = set()

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
            seen = self.headers.setdefault(int(num), {})
            if len(seen) < MAX_CANDIDATES:
                seen[m.start()] = int(gen)
        for m in _OBJ_WORD.finditer(data):
            if m.end() not in ends:
                meter.charge(_WORD_WORK)
                if _odd_header(data, m.start(), meter):
                    self._refuse('an object header the gate cannot read')
        self.starts = sorted(p for seen in self.headers.values() for p in seen)

    def _objstm_names(self):
        """Offsets of every /ObjStm name in the raw file, a #-escaped spelling included."""
        data = self.data
        for m in _NAME.finditer(data):
            name = m.group()
            if b'#' in name:
                try:
                    name = re.sub(rb'#([0-9A-Fa-f]{2})', lambda e: bytes([int(e.group(1), 16)]), name)
                except ValueError:
                    continue
            if name == b'/ObjStm':
                yield m.start()

    def _build_packed(self) -> None:
        reader, meter = self.reader, self.reader._counted
        self.packed = {}
        streams = sorted({stm for stm, _ in reader.xref_objStm.values()})
        for at in self._objstm_names():
            meter.charge(_WORD_WORK)
            k = bisect.bisect_right(self.starts, at) - 1
            owner = [n for n, seen in self.headers.items() if k >= 0 and self.starts[k] in seen]
            if not owner or owner[0] not in streams:
                self._refuse('an object stream the cross-reference does not name')
        for stm in streams:
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

    def check(self, num: int, gen: int, found) -> None:
        """Refuse (OverBudget, via the reader's meter) unless pypdf's answer for (num, gen) is the ONE object
        any reader could find under ``num``."""
        if (num, gen) in self.checked:
            return
        self.checked.add((num, gen))
        reader = self.reader
        if self.packed is None:
            self._build_packed()
        raw = self.headers.get(num, {})
        packed = self.packed.get(num, [])
        if len(raw) + len(packed) > 1:
            self._refuse('object %d has more than one copy' % num)
        missing = found is None or isinstance(found, NullObject)
        if gen == 0 and num in reader.xref_objStm:       # a miss is fine only when no copy exists anywhere
            if raw or (packed and packed[0][0] != reader.xref_objStm[num][0]) or (not packed) != missing:
                self._refuse('object %d is not where the cross-reference packs it' % num)
            return
        row = reader.xref.get(gen, {}).get(num)
        if missing:
            if raw or packed:
                self._refuse('object %d exists but the gate did not read it' % num)
            return
        if packed or row is None or len(raw) != 1:
            self._refuse('object %d was read from bytes that are not its header' % num)
        (at, raw_gen), = raw.items()
        if raw_gen != gen or not (0 <= row <= at) or _LEAD.match(self.data, row).end() != at:
            self._refuse('object %d was read from bytes that are not its header' % num)


def _odd_header(data: bytes, at: int, meter) -> bool:
    """Could pdfium read the 'obj' word at ``at`` as an object header? True when, skipping white space and
    comments back from it, a number-like byte comes first. A '%' on a line may start a comment (or sit in a
    string), so both readings are tried: the line's end, and the bytes before its first '%'."""
    p = at
    for _ in range(64):
        q = p
        while q > 0 and data[q - 1] in _WHITE:
            q -= 1
        meter.charge(p - q + 1)
        if q == 0:
            return False
        if data[q - 1] in _NUMBERISH:
            return True
        line = max(data.rfind(b'\n', 0, q), data.rfind(b'\r', 0, q)) + 1
        meter.charge(q - line)
        pct = data.find(b'%', line, q)
        if pct < 0:
            return False
        p = pct
    return True
