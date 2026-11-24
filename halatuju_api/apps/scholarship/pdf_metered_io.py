"""Metered byte streams for `pdf_layer_guards.GateReader` (TD-710, moved out of it to keep that file under the size
limit; no logic change). `_MeteredData` is the BytesIO pypdf parses object-stream and open-time data from while a
`GateReader` is working: each read is charged to that reader's meter (its `_CountedBytes`). `_bytes_io` replaces
``pypdf._reader.BytesIO`` (installed once, at import) and hands out `_MeteredData` only while `_PARSING.meter` is
set on this thread. `pdf_layer_guards` imports these names back, so every existing import still works."""
import io
import threading

import pypdf._reader

_PARSE_CALL_WORK = 12_000
_PARSING = threading.local()                 # .meter: the `_CountedBytes` of the reader opening or parsing here


class _MeteredData(io.BytesIO):
    """Data pypdf parses for a `GateReader` (object streams; as it opens, xref stream entries and rebuilt object-
    stream indexes): each read is charged to that reader's budget as made (the call, its parsing, and each byte)."""

    def __init__(self, meter, *args):
        super().__init__(*args)
        self.meter = meter

    def read(self, size=-1):
        data = super().read(size)
        self.meter.charge(_PARSE_CALL_WORK + len(data))
        return data


def _bytes_io(*args):
    """``pypdf._reader.BytesIO``: `_MeteredData` while this thread's `GateReader` opens the file (_reader.py:1430,
    :1583) or parses an object stream (:407), else a plain BytesIO: pypdf with no `GateReader` is never charged."""
    meter = getattr(_PARSING, 'meter', None)
    return io.BytesIO(*args) if meter is None else _MeteredData(meter, *args)


pypdf._reader.BytesIO = _bytes_io
