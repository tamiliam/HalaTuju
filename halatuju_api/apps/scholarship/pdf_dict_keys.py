"""OCR-20 review rounds 1-2 (2026-11-25): a dictionary, array or name the gate may read differently from pdfium
refuses the whole file.

Round 1: pypdf keeps the FIRST value of a repeated key (pypdf/generic/_data_structures.py, ``read_from_stream``);
pdfium keeps the LAST. A page naming /Contents and /Annots twice looked blank with one plain /Link to the gate while
pdfium drew GENUINE under a /Square sticker painting FORGED.

Round 2: pypdf's dictionary parser has more lenient paths, each a page pdfium reads differently (probe p1: the gate
read GENUINE, pdfium drew FORGED): a null key ENDS the dictionary silently; a key that is not a name (an array, a
string, a dictionary) is skipped whole; a value it cannot read returns the dictionary read so far; a lone '>' ends
it. pdfium skips one word and reads on. And pdfium cuts a name word at about 255 bytes, so a long font name named
no font to pdfium (fallback Helvetica) while pypdf applied the font's /Differences (probe p4).

So, while a `pdf_layer_guards.GateReader` parses a dictionary or an array from its file, an object stream (a
`_MeteredData` naming its meter) or a content stream its page walk parses (`content_meter`), the file is refused
when (all STRUCTURAL, checked as it is read; no warning text is matched):
  * a dictionary does not end on '>>' right after its last value, or pypdf did not read exactly one key and one
    value per entry it kept (a repeated key, a skipped non-name key, a null key, a partial read all break this);
  * an array does not end on its own ']' (pypdf stops silently at the end of the data);
  * a null or boolean is not exactly the word 'null', 'true' or 'false' standing alone (pypdf reads 'endobj' as
    null and 'falsy' as false);
  * a name is 128 bytes or more (the PDF limit is 127), raw or decoded;
  * pypdf's dictionary module logs ANY warning while the dictionary is read (a second line, e.g. a stream with no
    /Length).

Why the FILE, not the page: the object may be shared, pypdf parses each object once and caches it, and the refusal
is the meter's (`_CountedBytes._refuse`: an `OverBudget`, which pypdf's lenient parser always re-raises, and
``refused`` stays set even when a pypdf recovery path swallows the raise; `pdf_pages._layer_read` checks it).

Round 3 part 2 (H4, H5). STREAM BOUNDS: pypdf trusts a /Length only when 'endstream' follows it; otherwise it
looks one byte back, then searches on to the next 'endstream'. pdfium searches to the FIRST of 'endstream' and
'endobj' (probes p2d, p2e: a wrong /Length and an 'endobj' in the data; pypdf read GENUINE LULUS, pdfium drew
GENUINE). So a stream in the file is refused unless (`_stream_start`, `_stream_end`):
  * the 'stream' keyword is pypdf's: after the dictionary only pypdf's white space (NUL, TAB, LF, FF, CR, space),
    then 'stream', spaces, and LF, CR LF or CR (pdfium also skips comments and 0x80 / 0xFF before the keyword, and
    takes any rest of the line after it: pypdf then reads no stream or raises);
  * /Length (direct, or an indirect one pypdf resolves; any failure refuses) is a whole number >= 0, pypdf's data
    holds exactly that many bytes, and from start + /Length there is only pypdf's white space, then 'endstream'.
    Both readers skip that white space and then take /Length as it is (checked against pdfium: none, LF, CR LF,
    CR, LF LF, TAB, FF, NUL). A wrong /Length with no 'endobj' word refuses too: no search path is relied on;
  * for an indirect /Length, the data holds neither 'endstream' nor 'endobj' (should pdfium resolve it another
    way, its search then ends where pypdf's read does);
  * it is not inside a content stream or an object stream (pdfium reads 'stream' there as an operator or a word,
    and draws what follows);
  * pypdf's stream read raises nothing.
WORD ENDS IN ARRAYS (`_array_item`, probe p2l): pypdf reads 'null' in an array by a shortcut that skips the
round-2 word check, so '[5 0 R nulltrue 6 0 R]' was two content streams to pypdf and one to pdfium (the unknown
word 'nulltrue' ends its array). Each array element whose first byte is a regular one must follow white space or
a delimiter, and the shortcut's 'null' must be followed by one.

Round 3 part 3 (H5, the short check): pypdf's reference pattern (regex white space) and array loop
(bytes.isspace) take 0x0b as white space, pdfium as a regular byte: '[5 0 R 6<0b>0<0b>R]', '[5 0 R 6 0 R<0b>]'
and '/X1 6<0b>0<0b>R' were a second content stream or form to pypdf, nothing to pdfium. So (`_read_object`) a reference must hold no
`_DISAGREE` byte (0x00 0x0b 0x80 0xff: where any of pypdf's white-space tests and pdfium's differ) between its
parts, and its 'R' must be followed by white space or a delimiter both agree on; a number must not end on one.

pypdf with no `GateReader` (other readers, the pdfium child's layout op and `page_flags`) is unchanged.
"""
import io
import re
import threading
from contextlib import contextmanager

from pypdf.generic import (ArrayObject, BooleanObject, DictionaryObject, FloatObject, IndirectObject, NameObject,
                           NullObject, NumberObject)
from pypdf.generic import _data_structures as _pypdf_dicts

from .pdf_layer_guards import OverBudget, _CountedBytes

REFUSAL = 'a dictionary the gate and the renderer may read differently'
ARRAY_REFUSAL = 'an array the gate and the renderer may read differently'
WORD_REFUSAL = 'a null or boolean the gate and the renderer may read differently'
NAME_REFUSAL = 'a name past the 127-byte limit'
STREAM_REFUSAL = 'a stream the gate and the renderer may bound differently'
#: A name this long or longer (bytes, after the '/') refuses: the PDF limit is 127 (pdfium cuts at about 255).
NAME_MAX_BYTES = 128
#: Switched off only by tests that check another guard on its own.
CHECKS_ON = True
_DELIMITERS = frozenset(b'\x00\t\n\x0c\r ()<>[]{}/%')
_PYPDF_SPACE = frozenset(b'\x00\t\n\x0c\r ')            # pypdf's WHITESPACES (6.21.4); pdfium skips all of them
_PDFIUM_SPACE = _PYPDF_SPACE | frozenset(b'\x80\xff')    # pdfium's word-ending white space
_SPACE = frozenset(b' ')
#: Round 3 part 3: a byte one of pypdf's white-space tests (WHITESPACES; bytes.isspace in its array and reference
#: loops; regex white space in its reference pattern) and pdfium's disagree on: 0x00 (not \s), 0x0b (not pdfium's), 0x80,
#: 0xff (pdfium's only). Inside a reference or right after a number or a reference: refused.
_DISAGREE = frozenset().union(*(frozenset(b for b in range(256) if test(bytes([b]))) ^ _PDFIUM_SPACE for test in (
    lambda c: c[0] in _PYPDF_SPACE, bytes.isspace, re.compile(rb'\s').fullmatch)))
#: A reference's 'R' ends its word for pdfium only on white space or a delimiter both readers agree on.
_REF_ENDS = _DELIMITERS - _DISAGREE
_REF_TAIL = re.compile(rb'[+-]?\d+(\s+)\d+(\s+)R\Z')
_CHECKED = (IndirectObject, NumberObject, FloatObject, NullObject, BooleanObject)
#: How far past a dictionary or a stream's data the keyword checks look (uncharged; first 64 bytes): white
#: space or comments running past it refuse.
_PEEK = 4096
_HERE = threading.local()     # .frames: the dictionaries / arrays being read on this thread; .content: a meter
_pypdf_read_dict = DictionaryObject.read_from_stream
_pypdf_read_array = ArrayObject.read_from_stream
_pypdf_stream_data = DictionaryObject._read_stream_data
_pypdf_read_object = _pypdf_dicts.read_object
_pypdf_check_limits = ArrayObject._check_limits
_pypdf_warning = _pypdf_dicts.logger_warning


class _Frame:
    """One dictionary or array being read: its gate meter (None: not a gate stream) and, for a dictionary, the
    objects pypdf read directly in it and whether it reached its normal end; the stream it is read from."""
    __slots__ = ('meter', 'is_dict', 'reads', 'ended', 'stream')

    def __init__(self, meter, is_dict: bool, stream=None):
        self.meter, self.is_dict, self.reads, self.ended, self.stream = meter, is_dict, 0, False, stream


def _frames() -> list:
    frames = getattr(_HERE, 'frames', None)
    if frames is None:
        frames = _HERE.frames = []
    return frames


def _meter(stream):
    """The gate meter of ``stream`` (the file, an object stream naming it, or a content stream the walk parses)."""
    if not CHECKS_ON:
        return None
    meter = stream if isinstance(stream, _CountedBytes) else getattr(stream, 'meter', None)
    if meter is None and type(stream) is io.BytesIO:
        meter = getattr(_HERE, 'content', None)
    return meter if isinstance(meter, _CountedBytes) else None


@contextmanager
def content_meter(reader):
    """While a `GateReader`'s page walk parses a content stream, its dictionaries, arrays and names are checked too
    (pypdf parses content from a plain BytesIO). Other readers: nothing changes."""
    outer = getattr(_HERE, 'content', None)
    _HERE.content = getattr(reader, '_counted', None)
    try:
        yield
    finally:
        _HERE.content = outer


def _around(stream, back: int, ahead: int) -> tuple:
    """The ``back`` bytes before the stream's position and the ``ahead`` after it, read uncharged; position kept."""
    at = io.BytesIO.tell(stream)
    io.BytesIO.seek(stream, max(at - back, 0))
    before = io.BytesIO.read(stream, min(back, at))
    after = io.BytesIO.read(stream, ahead)
    io.BytesIO.seek(stream, at)
    return before, after


def _read_dict(stream, pdf, forced_encoding=None, **kwargs):
    """pypdf's dictionary read; for a gate stream, refused unless it reached its normal end (`_stream_data`)."""
    frame = _Frame(_meter(stream), True)
    frames = _frames()
    frames.append(frame)
    try:
        result = _pypdf_read_dict(stream, pdf, forced_encoding, **kwargs)
    finally:
        frames.pop()
    if frame.meter is not None and not frame.ended:      # pypdf returned what it had read (a value it could not)
        frame.meter._refuse(REFUSAL)
    return result


def _stream_data(*, stream, pdf, data):
    """pypdf calls this once a dictionary's loop ends normally ('>' or a null key): it must have read two objects
    per entry kept, and the two bytes before here must be '>>'. Then the stream bounds (round 3 part 2, H4)."""
    frames = _frames()
    frame = frames[-1] if frames and frames[-1].is_dict else None
    meter = frame.meter if frame is not None else None
    if frame is not None:
        frame.ended = True
        if meter is not None and (frame.reads != 2 * len(data) or _around(stream, 2, 0)[0] != b'>>'):
            meter._refuse(REFUSAL)
    if meter is None:
        return _pypdf_stream_data(stream=stream, pdf=pdf, data=data)
    start = _stream_start(stream, meter)
    try:
        result = _pypdf_stream_data(stream=stream, pdf=pdf, data=data)
    except OverBudget:
        raise
    except Exception:                    # pypdf may recover from it further up: the file is refused first
        if start is not None:
            meter._refuse(STREAM_REFUSAL)
        raise
    if start is not None:
        _stream_end(stream, data, start, meter)
    return result


def _skip(ahead: bytes, space: frozenset, comments: bool = False) -> int:
    """The index of the first byte of ``ahead`` past ``space`` bytes (and, with ``comments``, '%' comments)."""
    k = 0
    while k < len(ahead) and (ahead[k] in space or (comments and ahead[k] == 0x25)):
        if ahead[k] == 0x25:                                 # a comment runs to its end of line
            while k < len(ahead) and ahead[k] not in (0x0A, 0x0D):
                k += 1
        k += 1
    return k


def _peek(stream, at: int, space: frozenset, meter, comments: bool = False) -> tuple:
    """(bytes of ``stream`` from ``at``, read uncharged with its position kept; the index `_skip` stops at, with
    at least 16 bytes after it): 64 bytes, or `_PEEK` when the white space runs on. Past that: refused."""
    here = io.BytesIO.tell(stream)
    try:
        for size in (64, _PEEK):
            io.BytesIO.seek(stream, at)
            ahead = io.BytesIO.read(stream, size)
            k = _skip(ahead, space, comments)
            if k + 16 <= len(ahead) or len(ahead) < size:
                return ahead, k
    finally:
        io.BytesIO.seek(stream, here)
    meter._refuse(STREAM_REFUSAL)


def _stream_start(stream, meter):
    """Where the stream data after this dictionary starts, as pypdf reads it; None when pypdf reads no stream here.
    Refused: a 'stream' keyword pdfium finds and pypdf does not, one pypdf reads in a content or object stream,
    or one not followed by spaces and an end of line."""
    at = io.BytesIO.tell(stream)
    ahead, k = _peek(stream, at, _PYPDF_SPACE, meter)
    if ahead[k:k + 6] != b'stream':
        ahead, k = _peek(stream, at, _PDFIUM_SPACE, meter, comments=True)
        if ahead[k:k + 6] == b'stream':
            meter._refuse(STREAM_REFUSAL)
        return None
    if not isinstance(stream, _CountedBytes):
        meter._refuse(STREAM_REFUSAL)
    at += k + 6
    ahead, k = _peek(stream, at, _SPACE, meter)
    if ahead[k:k + 1] not in (b'\n', b'\r'):
        meter._refuse(STREAM_REFUSAL)
    return at + k + (2 if ahead[k:k + 2] == b'\r\n' else 1)


def _stream_end(stream, data, start: int, meter) -> None:
    """The data pypdf read must be exactly /Length bytes from ``start``, then white space and 'endstream'."""
    length = data.get('/Length')
    indirect = isinstance(length, IndirectObject)
    try:
        length = length.get_object() if indirect else length      # pypdf resolved it already: cached
    except OverBudget:
        raise
    except Exception:
        meter._refuse(STREAM_REFUSAL)
    got = data.get('__streamdata__')
    if (not isinstance(length, int) or isinstance(length, bool) or length < 0 or not isinstance(got, bytes)
            or len(got) != length or (indirect and (b'endstream' in got or b'endobj' in got))):
        meter._refuse(STREAM_REFUSAL)
    after, k = _peek(stream, start + length, _PYPDF_SPACE, meter)
    if after[k:k + 9] != b'endstream':
        meter._refuse(STREAM_REFUSAL)


def _read_array(stream, pdf, forced_encoding=None, **kwargs):
    """pypdf's array read; for a gate stream, refused unless its last byte is its OWN ']' (an inner array that
    ended at the same place means the outer one ran off the end of the data)."""
    frame = _Frame(_meter(stream), False, stream)
    frames = _frames()
    frames.append(frame)
    _HERE.array_end = None
    try:
        result = _pypdf_read_array(stream, pdf, forced_encoding, **kwargs)
    finally:
        frames.pop()
    if frame.meter is not None:
        end = (id(stream), io.BytesIO.tell(stream))
        if _around(stream, 1, 0)[0] != b']' or getattr(_HERE, 'array_end', None) == end:
            frame.meter._refuse(ARRAY_REFUSAL)
        _HERE.array_end = end
    return result


def _array_item(*, remaining_elements, parsing_budget):
    """pypdf calls this for each array element, its first byte just read (round 3 part 2, H5): a regular first
    byte must follow white space or a delimiter, and a 'null' (read by pypdf's shortcut, past `_read_object`)
    must be followed by one."""
    frames = _frames()
    frame = frames[-1] if frames and not frames[-1].is_dict else None
    if frame is not None and frame.meter is not None:
        before, after = _around(frame.stream, 2, 4)
        if before[-1:] and before[-1] not in _DELIMITERS and (len(before) < 2 or before[0] not in _DELIMITERS):
            frame.meter._refuse(WORD_REFUSAL)
        if before[-1:] == b'n' and after[:3] == b'ull' and (len(after) < 4 or after[3] not in _DELIMITERS):
            frame.meter._refuse(WORD_REFUSAL)
    return _pypdf_check_limits(remaining_elements=remaining_elements, parsing_budget=parsing_budget)


def _read_object(stream, pdf, forced_encoding=None, **kwargs):
    """pypdf's object read inside a dictionary, array or content stream: counted for the dictionary it is read in;
    a null or boolean must be its whole word; a number or a reference must not hold or end on a `_DISAGREE` byte,
    and a reference's 'R' must end its word for pdfium too (round 3 part 3)."""
    frames = _frames()
    if frames and frames[-1].is_dict:
        frames[-1].reads += 1
    result = _pypdf_read_object(stream, pdf, forced_encoding, **kwargs)
    meter = _meter(stream) if isinstance(result, _CHECKED) else None
    if meter is None:
        return result
    if isinstance(result, IndirectObject):
        before, after = _around(stream, 20, 1)     # pypdf matched the reference in 20 bytes, one after its 'R'
        ref = _REF_TAIL.search(before)
        if ref is None or _DISAGREE.intersection(ref[1] + ref[2]) or (after and after[0] not in _REF_ENDS):
            meter._refuse(WORD_REFUSAL)
    elif isinstance(result, (NumberObject, FloatObject)):
        after = _around(stream, 0, 1)[1]
        if after and after[0] in _DISAGREE:
            meter._refuse(WORD_REFUSAL)
    else:
        word = b'null' if isinstance(result, NullObject) else b'true' if result.value else b'false'
        before, after = _around(stream, len(word), 1)
        if before != word or (after and after[0] not in _DELIMITERS):
            meter._refuse(WORD_REFUSAL)
    return result


def _name_check(read_name):
    """The name reader in place (`pdf_layer_guards._read_name`, OCR-12), with the length rule on top."""
    def _read_name(stream, pdf):
        meter = _meter(stream)
        start = io.BytesIO.tell(stream) if meter is not None else 0
        name = read_name(stream, pdf)
        if meter is not None:
            raw = io.BytesIO.tell(stream) - start - 1
            if raw >= NAME_MAX_BYTES or len(name.encode('utf-8', 'surrogatepass')) - 1 >= NAME_MAX_BYTES:
                meter._refuse(NAME_REFUSAL)
        return name
    _read_name.gate_length_check = True
    return _read_name


def _warning(message, **values):
    """pypdf's warning in its dictionary module: while a gate dictionary is read, ANY warning refuses the file
    (raised from outside pypdf's try block, so it leaves the parse at once). Then the warning installed before."""
    frames = _frames()
    if frames and frames[-1].is_dict and frames[-1].meter is not None:
        frames[-1].meter._refuse(REFUSAL)
    _pypdf_warning(message, **values)


def install() -> None:
    """Put the hooks in place, process-wide, once: a hook already there is never replaced (idempotent), and the
    warning hook goes in only over pypdf's own function (an outer patch is left as it is)."""
    if DictionaryObject.read_from_stream is not _read_dict:
        DictionaryObject.read_from_stream = staticmethod(_read_dict)
    if DictionaryObject._read_stream_data is not _stream_data:
        DictionaryObject._read_stream_data = staticmethod(_stream_data)
    if ArrayObject.read_from_stream is not _read_array:
        ArrayObject.read_from_stream = staticmethod(_read_array)
    if ArrayObject._check_limits is not _array_item:
        ArrayObject._check_limits = staticmethod(_array_item)
    if _pypdf_dicts.read_object is _pypdf_read_object:
        _pypdf_dicts.read_object = _read_object
    if not getattr(NameObject.read_from_stream, 'gate_length_check', False):
        NameObject.read_from_stream = staticmethod(_name_check(NameObject.read_from_stream))
    if _pypdf_dicts.logger_warning is _pypdf_warning:
        _pypdf_dicts.logger_warning = _warning


install()
