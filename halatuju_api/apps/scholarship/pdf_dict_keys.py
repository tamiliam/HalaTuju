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

pypdf with no `GateReader` (other readers, the pdfium child's layout op and `page_flags`) is unchanged.
"""
import io
import threading
from contextlib import contextmanager

from pypdf.generic import ArrayObject, BooleanObject, DictionaryObject, NameObject, NullObject
from pypdf.generic import _data_structures as _pypdf_dicts

from .pdf_layer_guards import _CountedBytes

REFUSAL = 'a dictionary the gate and the renderer may read differently'
ARRAY_REFUSAL = 'an array the gate and the renderer may read differently'
WORD_REFUSAL = 'a null or boolean the gate and the renderer may read differently'
NAME_REFUSAL = 'a name past the 127-byte limit'
#: A name this long or longer (bytes, after the '/') refuses: the PDF limit is 127 (pdfium cuts at about 255).
NAME_MAX_BYTES = 128
#: Switched off only by tests that check another guard on its own.
CHECKS_ON = True
_DELIMITERS = frozenset(b'\x00\t\n\x0c\r ()<>[]{}/%')
_HERE = threading.local()     # .frames: the dictionaries / arrays being read on this thread; .content: a meter
_pypdf_read_dict = DictionaryObject.read_from_stream
_pypdf_read_array = ArrayObject.read_from_stream
_pypdf_stream_data = DictionaryObject._read_stream_data
_pypdf_read_object = _pypdf_dicts.read_object
_pypdf_warning = _pypdf_dicts.logger_warning


class _Frame:
    """One dictionary or array being read: its gate meter (None: not a gate stream) and, for a dictionary, the
    objects pypdf read directly in it and whether it reached its normal end."""
    __slots__ = ('meter', 'is_dict', 'reads', 'ended')

    def __init__(self, meter, is_dict: bool):
        self.meter, self.is_dict, self.reads, self.ended = meter, is_dict, 0, False


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
    per entry kept, and the two bytes before here must be '>>'."""
    frames = _frames()
    frame = frames[-1] if frames and frames[-1].is_dict else None
    if frame is not None:
        frame.ended = True
        if frame.meter is not None and (frame.reads != 2 * len(data) or _around(stream, 2, 0)[0] != b'>>'):
            frame.meter._refuse(REFUSAL)
    return _pypdf_stream_data(stream=stream, pdf=pdf, data=data)


def _read_array(stream, pdf, forced_encoding=None, **kwargs):
    """pypdf's array read; for a gate stream, refused unless its last byte is its OWN ']' (an inner array that
    ended at the same place means the outer one ran off the end of the data)."""
    frame = _Frame(_meter(stream), False)
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


def _read_object(stream, pdf, forced_encoding=None, **kwargs):
    """pypdf's object read inside a dictionary, array or content stream: counted for the dictionary it is read in;
    a null or boolean must be its whole word."""
    frames = _frames()
    if frames and frames[-1].is_dict:
        frames[-1].reads += 1
    result = _pypdf_read_object(stream, pdf, forced_encoding, **kwargs)
    if isinstance(result, (NullObject, BooleanObject)):
        meter = _meter(stream)
        if meter is not None:
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
    if _pypdf_dicts.read_object is _pypdf_read_object:
        _pypdf_dicts.read_object = _read_object
    if not getattr(NameObject.read_from_stream, 'gate_length_check', False):
        NameObject.read_from_stream = staticmethod(_name_check(NameObject.read_from_stream))
    if _pypdf_dicts.logger_warning is _pypdf_warning:
        _pypdf_dicts.logger_warning = _warning


install()
