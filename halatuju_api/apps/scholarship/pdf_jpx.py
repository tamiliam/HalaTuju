"""TD-692 (2026-11-20): the size a JPEG2000 (JPX) image costs pdfium to render, read from its own header.

`pdf_render_check` charges every image it meets by its decoded size before pdfium renders the page. For a JPX
image the PDF dictionary is not enough: OpenJPEG, inside pdfium, decodes the size the JPX data's own header
claims (the codestream's SIZ marker: Xsiz - XOsiz by Ysiz - YOsiz pixels of Csiz components). So a JPX image is
charged the LARGER of the two, and one whose header cannot be read is refused. Nothing is decoded here; only the
stream's headers are read.

Reviews 3 and 4 (2026-11-21): pixels alone did not bound the decode time, so every JPX image is also charged its
DECODE WORK (`_work`): SIZ pixels x components x bytes per sample, plus `_TILE_WORK` for each tile. The number of
resolution levels (NL) is not credited. pdfium asks OpenJPEG to skip levels only when the image is DRAWN at half
its SIZ size or less, which the page decides, not the header; drawn on its A4 page at the 200 DPI render, a scan up
to 400 DPI skips none (measured, Linux child, 3 pages: 300 DPI colour NL 0 / 1 / 5 rendered in 4.8 / 5.4 / 5.8 s).
Review 3 halved the work at NL >= 1 and so refused a 300 DPI colour scan at its 10,000,000 page cap while it let
three 4890 x 4890 16-bit images a page through at half. The work is capped per page (`MAX_PAGE_JPX_WORK`) and over
all the pages one gate call checks (`MAX_DOC_JPX_WORK`). The caps do not model OpenJPEG's memory: on Linux the
child's 256 MiB cap is the backstop (a 400 DPI A4 colour JPX scan passes the gate but its 200 DPI page render runs
out of it, about 8 s for 3 pages, while the smaller stacked render of the same pages draws in 3.3-3.8 s).
"""
import zlib

from .pdf_layer_guards import OverBudget, _get

JPX = '/JPXDecode'
_JPX_WINDOW = 65_536
_JPX_MAX_BOXES = 64
_JPX_MAX_DEPTH = 38                                  # the deepest a JPEG2000 component may be, in bits
_J2K_START = b'\xff\x4f\xff\x51'                     # SOC then SIZ: a codestream's first two markers
_JP2_SIGNATURE = b'\x00\x00\x00\x0cjP  \r\n\x87\n'   # a JP2 file's first box
#: JPX decode work on one page, and summed over the pages one gate call checks (at most 3 in production: the stack
#: and the offer reader read 3). Measured in the Linux child (256 MiB, 3 pages rendered at 200 DPI, 2026-11-21):
#: A4 scans, one per page, 8-bit, NL 0, 1 or 5: 200 DPI grey 1.7-2.6 s, colour 3.5-6.2 s; 300 DPI grey 2.2-3.0 s,
#: colour 4.8-5.8 s; 400 DPI grey 2.8-3.5 s, colour out of memory at 7.1-8.3 s; US letter 300 DPI colour 5.4 s.
#: The review 3 probe (work 430 million) 12.1 s. A 400 DPI A4 colour page, 3307 x 4677 x 3 = 46,400,517, is the
#: largest genuine page: the caps sit just above it and three of it. Near the caps: one 4890 x 4890 16-bit grey
#: image a page (47.8 million, refused) 4.4 s; one 4000 x 4000 16-bit (32 million, passes) 3.4 s.
MAX_PAGE_JPX_WORK = 47_000_000
MAX_DOC_JPX_WORK = 140_000_000
#: Work charged per tile: OpenJPEG pays a fixed cost for each. Measured, Linux child, 3 pages of 15,625 tiles each
#: (1000 x 1000 grey in 8 x 8 tiles; 2000 x 2000 in 16 x 16): 4.6-4.8 s, about 75 microseconds a tile above the
#: pixels; one unit of work measured 31-68 ns, so a tile costs 1,100-2,400 units. So 2,000 a tile: a page holds at
#: most 23,500 tiles.
_TILE_WORK = 2_000


def jpx_charge(img, before, px, bits):
    """(pixels, bits per pixel, decode work) to charge a JPEG2000 image whose dictionary says ``px`` and
    ``bits``: the LARGER of the dictionary and the JPX data's own header (the codestream's SIZ marker, and a JP2
    file's ihdr box), and the codestream's decode work (`_work`). None when no SIZ marker can be read: the caller
    refuses it (a dictionary may claim 10 x 10 over a 9000 x 9000 codestream, and an unread header has an
    unknown cost)."""
    head = _jpx_header(img, before)
    if not head:
        return None
    claims, work = head
    for head_px, head_bits in claims:
        px, bits = max(px, head_px), max(bits, head_bits)
    return px, bits, work


def charge_document(doc: dict, work: int, limits: bool) -> None:
    """Add one JPX image's decode work to the total of the gate call (``doc``, shared by the pages it checks)."""
    doc['jpx_work'] = doc.get('jpx_work', 0) + work
    if limits and doc['jpx_work'] > MAX_DOC_JPX_WORK:
        raise OverBudget('past the render JPEG2000 document cap')


def _predicted(img) -> bool:
    """A /DecodeParms with a /Predictor past 1: the inflated window is not the JPX data's start."""
    parms = _get(img, '/DecodeParms')
    for p in parms if isinstance(parms, list) else [parms]:
        p = p.get_object() if hasattr(p, 'get_object') else p
        pred = _get(p, '/Predictor') if p is not None else None
        if pred is not None and pred != 1:
            return True
    return False


def _jpx_header(img, before):
    """([(pixels, bits per pixel)] the JPX data's headers claim, the SIZ marker's first; decode work); None
    when no SIZ marker can be read. Read: the stream as stored when JPX is the only filter (its headers only);
    at most `_JPX_WINDOW` bytes inflated after one FlateDecode with no predictor (never the whole stream); after
    any other filter, two Flates or a predictor, not at all."""
    if not before:
        data = img._data
    elif before == ['/FlateDecode'] and not _predicted(img):
        try:
            data = zlib.decompressobj().decompress(img._data, _JPX_WINDOW)
        except zlib.error:
            return None
    else:
        return None
    if data[:4] == _J2K_START:                       # a bare codestream
        siz = _siz(data, 0)
        return ([siz], _work(data, 0)) if siz else None
    if data[:12] != _JP2_SIGNATURE:
        return None
    found, at = [], 0
    for _ in range(_JPX_MAX_BOXES):                  # a JP2 file: its boxes, read by their headers only
        box = _box(data, at)
        if box is None:
            return None
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
            return ([siz] + found, _work(data, body)) if siz else None
        at = end
    return None


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


def _work(data, at) -> int:
    """The decode work of the codestream at ``at`` (its SIZ marker already read by `_siz`): SIZ pixels x components
    x bytes per sample (the deepest component's bits, in whole bytes: 1 up to 8 bits, 2 up to 16), plus
    `_TILE_WORK` for each tile of the SIZ tile grid. The number of resolution levels is not read: pdfium skips levels
    only when the image is DRAWN at half its size or less, which the page (not the header) decides."""
    px, bits = _siz(data, at)
    x, y, x0, y0, xt, yt, xto, yto = (int.from_bytes(data[at + o:at + o + 4], 'big') for o in range(8, 40, 4))
    tiles = -(-(x - min(xto, x0)) // max(xt, 1)) * -(-(y - min(yto, y0)) // max(yt, 1))
    comps = int.from_bytes(data[at + 40:at + 42], 'big')
    return px * comps * -(-(bits // comps) // 8) + tiles * _TILE_WORK
