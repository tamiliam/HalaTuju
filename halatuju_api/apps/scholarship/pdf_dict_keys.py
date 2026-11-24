"""OCR-20 review round 1 (2026-11-25): a dictionary that names one key twice refuses the whole file.

pypdf keeps the FIRST value of a repeated key (pypdf/generic/_data_structures.py, ``read_from_stream``: "Multiple
definitions in dictionary"); pdfium keeps the LAST. A page naming /Contents and /Annots twice looked blank with one
plain /Link to the gate (pypdf) while pdfium drew GENUINE under a /Square sticker painting FORGED, and the SPM
certificate reader then read pdfium's words of it. So any dictionary a `pdf_layer_guards.GateReader` parses from its
file or from an object stream (its `_CountedBytes`, or a `_MeteredData` that names it) refuses the file on a repeated
key, as it is read: "a dictionary the gate and the renderer may read differently".

Why the FILE, not the page: the dictionary may be shared (the trailer, the catalogue, a page-tree node, a font, a
resource or annotation dictionary used by several pages), pypdf parses each object once and caches it (a later page
using it would never ask again), and the refusal is the meter's (`_CountedBytes._refuse`: an `OverBudget`, which
pypdf's lenient dictionary parser always re-raises, and ``refused`` stays set even when a pypdf recovery path
swallows the raise; `pdf_pages._layer_read` checks it). The OCR-12 name hook refuses the file the same way.

pypdf with no `GateReader` (other readers, the pdfium child's layout op) is unchanged: its warning is only logged.
"""
import threading

from pypdf.generic import DictionaryObject
from pypdf.generic import _data_structures as _pypdf_dicts

from .pdf_layer_guards import _CountedBytes

#: pypdf's warning for a repeated key (6.21.4; a test pins that it still fires, `test_ocr20_dup_keys`).
DUPLICATE_KEY_WARNING = 'Multiple definitions in dictionary'
REFUSAL = 'a dictionary the gate and the renderer may read differently (a key named twice)'
_HERE = threading.local()            # .meter: the gate meter of the dictionary being parsed on this thread, or None
_pypdf_read_dict = DictionaryObject.read_from_stream
_pypdf_warning = _pypdf_dicts.logger_warning


def _meter(stream):
    meter = stream if isinstance(stream, _CountedBytes) else getattr(stream, 'meter', None)
    return meter if isinstance(meter, _CountedBytes) else None


def _read_dict(stream, pdf, forced_encoding=None, **kwargs):
    """pypdf's dictionary read, with this thread's current meter set to the stream's (None for a non-gate stream)
    for its own keys; a nested dictionary sets its own and puts the outer one back."""
    outer = getattr(_HERE, 'meter', None)
    _HERE.meter = _meter(stream)
    try:
        return _pypdf_read_dict(stream, pdf, forced_encoding, **kwargs)
    finally:
        _HERE.meter = outer


def _warning(message, **values):
    """pypdf's warning in its dictionary module: a repeated key in a gate dictionary refuses the file (raised from
    outside pypdf's try block, so it leaves the parse at once)."""
    meter = getattr(_HERE, 'meter', None)
    if meter is not None and str(message).startswith(DUPLICATE_KEY_WARNING):
        meter._refuse(REFUSAL)
    _pypdf_warning(message, **values)


def install() -> None:
    """Put the two hooks in place, process-wide (idempotent; `GateReader` calls it before it opens a file)."""
    if DictionaryObject.read_from_stream is not _read_dict:
        DictionaryObject.read_from_stream = staticmethod(_read_dict)
    _pypdf_dicts.logger_warning = _warning


install()
