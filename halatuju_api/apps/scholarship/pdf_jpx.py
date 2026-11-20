"""TD-692 (2026-11-20): the size a JPEG2000 (JPX) image costs pdfium to render, read from its own header.

`pdf_render_check` charges every image it meets by its decoded size before pdfium renders the page. For a JPX
image the PDF dictionary is not enough: OpenJPEG, inside pdfium, decodes the size the JPX data's own header
claims (the codestream's SIZ marker: Xsiz - XOsiz by Ysiz - YOsiz pixels of Csiz components). So a JPX image is
charged the LARGER of the two, and one whose header cannot be read is refused. Nothing is decoded here; only the
stream's first bytes are read. The caps do not model OpenJPEG's memory: pdfium decodes a large JPX at reduced
resolution (measured peak 105 MiB for an 8484 x 8484 grey image), and the child's memory cap (Linux) and time
limit stay the backstop.
"""
import zlib

from .pdf_layer_guards import _get

JPX = '/JPXDecode'
_JPX_WINDOW = 65_536
_JPX_MAX_BOXES = 64
_JPX_MAX_DEPTH = 38                                  # the deepest a JPEG2000 component may be, in bits
_J2K_START = b'\xff\x4f\xff\x51'                     # SOC then SIZ: a codestream's first two markers
_JP2_SIGNATURE = b'\x00\x00\x00\x0cjP  \r\n\x87\n'   # a JP2 file's first box


def jpx_charge(img, before, px, bits):
    """(pixels, bits per pixel) to charge a JPEG2000 image whose dictionary says ``px`` and ``bits``: the
    LARGER of the dictionary and the JPX data's own header (the codestream's SIZ marker, and a JP2 file's
    ihdr box). None when no SIZ marker can be read: the caller refuses it (a dictionary may claim 10 x 10 over
    a 9000 x 9000 codestream, and an unread header has an unknown cost)."""
    claims = _jpx_header(img, before)
    if not claims:
        return None
    for head_px, head_bits in claims:
        px, bits = max(px, head_px), max(bits, head_bits)
    return px, bits


def _predicted(img) -> bool:
    """A /DecodeParms with a /Predictor past 1: the inflated window is not the JPX data's start."""
    parms = _get(img, '/DecodeParms')
    for p in parms if isinstance(parms, list) else [parms]:
        p = p.get_object() if hasattr(p, 'get_object') else p
        pred = _get(p, '/Predictor') if p is not None else None
        if pred is not None and pred != 1:
            return True
    return False


def _jpx_header(img, before) -> list:
    """The (pixels, bits per pixel) the JPX data's headers claim, the SIZ marker's first; empty when no SIZ
    marker can be read. Only the stream's start is read: as stored when JPX is the only filter; at most
    `_JPX_WINDOW` bytes inflated after one FlateDecode with no predictor (never the whole stream); after any
    other filter, two Flates or a predictor, not at all."""
    if not before:
        data = img._data
    elif before == ['/FlateDecode'] and not _predicted(img):
        try:
            data = zlib.decompressobj().decompress(img._data, _JPX_WINDOW)
        except zlib.error:
            return []
    else:
        return []
    if data[:4] == _J2K_START:                       # a bare codestream
        siz = _siz(data, 0)
        return [siz] if siz else []
    if data[:12] != _JP2_SIGNATURE:
        return []
    found, at = [], 0
    for _ in range(_JPX_MAX_BOXES):                  # a JP2 file: its boxes, read by their headers only
        box = _box(data, at)
        if box is None:
            return []
        kind, body, end = box
        if kind == b'jp2h':                          # the header box holds ihdr: height, width, components, depth
            sub = body
            for _ in range(_JPX_MAX_BOXES):
                inner = _box(data, sub) if sub < min(end, len(data)) else None
                if inner is None:
                    break
                if inner[0] == b'ihdr' and inner[1] + 11 <= len(data):
                    o = inner[1]
                    height, width = int.from_bytes(data[o:o + 4], 'big'), int.from_bytes(data[o + 4:o + 8], 'big')
                    depth = data[o + 10]
                    depth = _JPX_MAX_DEPTH if depth == 255 else (depth & 0x7F) + 1
                    found.append((height * width, int.from_bytes(data[o + 8:o + 10], 'big') * depth))
                sub = inner[2]
        elif kind == b'jp2c':                        # the codestream OpenJPEG decodes (the first one)
            siz = _siz(data, body)
            return [siz] + found if siz else []
        at = end
    return []


def _box(data, at):
    """(type, content offset, end offset) of the JP2 box at ``at``; None when its header cannot be read."""
    if at + 8 > len(data):
        return None
    size, kind, body = int.from_bytes(data[at:at + 4], 'big'), data[at + 4:at + 8], at + 8
    if size == 1:                                    # a 64-bit length follows the type
        if at + 16 > len(data):
            return None
        size, body = int.from_bytes(data[at + 8:at + 16], 'big'), at + 16
    elif size == 0:                                  # the last box: it runs to the end of the data
        size = len(data) - at
    if size < body - at:
        return None
    return kind, body, at + size


def _siz(data, at):
    """(pixels, bits per pixel) the codestream at ``at`` claims in its SIZ marker, which must follow its SOC
    marker at once: (Xsiz - XOsiz) x (Ysiz - YOsiz) pixels, Csiz components of the deepest component's bits.
    None when it cannot be read or is not valid (OpenJPEG refuses such a codestream)."""
    if data[at:at + 4] != _J2K_START or at + 42 > len(data):
        return None
    x, y, x0, y0 = (int.from_bytes(data[at + o:at + o + 4], 'big') for o in (8, 12, 16, 20))
    comps = int.from_bytes(data[at + 40:at + 42], 'big')
    if x <= x0 or y <= y0 or comps == 0:
        return None
    depths = [(data[at + 42 + 3 * i] & 0x7F) + 1 for i in range(comps) if at + 42 + 3 * i < len(data)]
    if len(depths) < comps:                          # components past the data read: the deepest possible
        depths.append(_JPX_MAX_DEPTH)
    return (x - x0) * (y - y0), comps * max(depths)
