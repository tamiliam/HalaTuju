"""OCR-20 review round 3 part 1 (25 Nov 2026): content-stream BYTES that pypdf (the exact read) and pdfium (what is
drawn) tokenise differently. `content_bytes_check` runs on every content stream the page walk parses
(`pdf_pages._parsed_ops`), before the parse; anything below makes the page hidden (the AI / Vision route).

1. WHITE SPACE. pdfium counts 0x80 and 0xFF as white space, pypdf does not: ``(TIDAK) Tj\\x80`` is a Tj to pdfium and
   one unknown word 'Tj\\x80' to pypdf (so the text is drawn and never extracted; a ``cm``, ``Tr`` or ``BI`` hidden
   the same way changes what is drawn). 0x0B is white space to pypdf's operator reader and a regular byte to pdfium.
   Any of the three outside a string or a comment hides the page.
2. UNKNOWN OPERATORS (`unknown_operator`). The operator names are a fixed set (ISO 32000 Annex A). A word pypdf reads
   as any other operator is the mark of a tokeniser disagreement (``Tj\\x00``: pypdf ends a word only on regex white
   space, pdfium on 0x00 too), so it hides the page. Decision: also inside a BX/EX compatibility section, which a
   reader must ignore unknown operators in: not one of the corpus PDFs has one, and no document we read needs one.
3. STRING ESCAPES. An octal escape over 255 (``\\777``: pypdf keeps the four characters, pdfium the low byte); a
   backslash before a byte outside pypdf's escape table (``\\9``, ``\\q``: pypdf keeps the backslash, pdfium drops
   it); a backslash before LF LF, LF CR or CR CR (pypdf drops both line ends, pdfium keeps the second). A single
   CR, LF or CR LF after a backslash reads alike (checked against pdfium) and stays.
4. /CONTENTS ARRAYS (`content_bytes_check`). pypdf joins a page's streams with '\\n' (none when one already ends in
   '\\n'), pdfium with ' '. The rule, the narrowest that is provably safe: at every join, no comment, literal string
   or hex string may be open, and the next stream may not open with '>' (the second half of a split '>>'). Outside
   those, one white-space byte for another (or one extra) reads the same in both tokenisers; inside a comment '\\n'
   ends it and ' ' does not (a comment at the end of stream 1 swallowed stream 2's first line in pdfium), and inside
   a string the two bytes are different characters. Any inline image already hides the page, so its data never
   needs to be understood here (bytes in it may raise: the page is hidden either way).

The scan's work is linear in the stream's bytes and in the parens, '%', '<' and backslashes it holds: all charged to
the walk's document budget (bytes and token boundaries, `pdf_pages._charge`) before it runs.
"""
import re

from .pdf_layer_guards import _ARITY

#: Every operator name; the colour operators take a variable operand count, and pypdf reports an inline image as
#: 'INLINE IMAGE' (which hides the page on its own).
KNOWN_OPERATORS = frozenset(_ARITY) | frozenset((b'sc', b'scn', b'SC', b'SCN', b'INLINE IMAGE'))
#: An inline image's BI, ended by pdfium's white space (0x80 and 0xFF too: H3, 'BI\\x80' was missed) or '/'. Not by
#: the other delimiters: a genuine string holding ' BI)' (a subject) would hide the page, and a BI pypdf reads as an
#: operator hides it after the parse anyway (`pdf_pages`, 'INLINE IMAGE').
INLINE_IMAGE = re.compile(rb'(?<![^\s\x00\x80\xff)\]>}])BI(?![^\s\x00\x80\xff/])')
_TOP = re.compile(rb'[(%<\x80\xff\x0b]')
_IN_STRING = re.compile(rb'[()\\]')
_EOL = re.compile(rb'[\r\n]')
_HEX_BODY = re.compile(rb'[0-9A-Fa-f\x00\t\n\x0c\r ]*')
_OPENS_GT = re.compile(rb'[\x00\t\n\x0c\r ]*>')
#: Escaped bytes pypdf (its escape table, 6.21.4) and pdfium read alike: pdfium drops the backslash before any byte.
_SAME_ESCAPE = frozenset(b'nrtbf()\\/ %<>[]#_&$')
_OCTAL = frozenset(b'01234567')
_LF, _CR = 0x0A, 0x0D


def content_bytes_check(content, data: bytes) -> None:
    """Raise ValueError (the page is then hidden) on content-stream bytes pypdf and pdfium read differently. ``data``:
    pypdf's (joined) data; when ``content`` is a /Contents array its streams are scanned one by one, each but the last
    ending with no comment, string or hex string open, and each after the first not opening with '>'."""
    from pypdf.generic import ArrayObject, StreamObject
    if not isinstance(content, ArrayObject):
        _scan(data)
        return
    parts = [s for s in (x.get_object() for x in content) if isinstance(s, StreamObject)]
    for k, part in enumerate(parts):
        part = part.get_data()                 # pypdf keeps the decoded data: no second decode
        if k and _OPENS_GT.match(part):
            raise ValueError("a /Contents stream that opens with '>'")
        if not _scan(part) and k < len(parts) - 1:
            raise ValueError('a comment, string or hex string open where one /Contents stream ends')


def unknown_operator(ops) -> bool:
    """True when the parsed operations hold a word that is no PDF operator (`KNOWN_OPERATORS`)."""
    return any(op not in KNOWN_OPERATORS for _, op in ops)


def _scan(data: bytes) -> bool:
    """Raise on a byte or escape the two read differently; True when ``data`` ends with nothing open."""
    pos = 0
    while True:
        m = _TOP.search(data, pos)
        if m is None:
            return True
        at, c = m.start() + 1, data[m.start()]
        if c == 0x28:                                    # '(' a literal string
            pos = _string_end(data, at)
        elif c == 0x25:                                  # '%' a comment, to the next CR or LF
            e = _EOL.search(data, at)
            pos = e.start() if e else -1
        elif c == 0x3C and data[at:at + 1] == b'<':      # '<<' a dictionary
            pos = at + 1
        elif c == 0x3C:                                  # '<' a hex string
            end = data.find(b'>', at)
            if end >= 0 and _HEX_BODY.fullmatch(data, at, end) is None:
                raise ValueError('a byte in a hex string that is not a hex digit or white space')
            pos = end + 1 if end >= 0 else -1
        else:
            raise ValueError('a byte (0x80, 0xFF or 0x0B) one reader counts as white space and the other does not')
        if pos < 0:
            return False


def _string_end(data: bytes, i: int) -> int:
    """The index after the ')' closing the string whose body starts at ``i``; -1 when the data ends first."""
    depth = 1
    while True:
        m = _IN_STRING.search(data, i)
        if m is None:
            return -1
        j, c = m.start(), data[m.start()]
        if c == 0x5C:                                    # backslash
            i = _escape_end(data, j + 1)
            continue
        depth += 1 if c == 0x28 else -1
        i = j + 1
        if depth == 0:
            return i


def _escape_end(data: bytes, i: int) -> int:
    """The index after the escape whose byte is at ``i`` (raising on one the two read differently)."""
    if i >= len(data) or data[i] in _SAME_ESCAPE:
        return i + 1
    c, nxt = data[i], data[i + 1] if i + 1 < len(data) else -1
    if c in _OCTAL:
        end = i + 1
        while end < len(data) and end - i < 3 and data[end] in _OCTAL:
            end += 1
        if int(data[i:end], 8) > 255:
            raise ValueError('an octal escape past 255')
        return end
    if c == _LF and nxt not in (_LF, _CR):
        return i + 1
    if c == _CR and nxt != _CR:
        return i + 2 if nxt == _LF else i + 1
    if c in (_LF, _CR):
        raise ValueError('a backslash before two line ends')
    raise ValueError('an escape pypdf and pdfium read differently')
