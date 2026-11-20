"""TD-692 (2026-11-20): the size a JPEG2000 (JPX) image costs pdfium to render, read from its own header.

`pdf_render_check` charges every image it meets by its decoded size before pdfium renders the page. For a JPX
image the PDF dictionary is not enough: OpenJPEG, inside pdfium, decodes the size the JPX data's own header
claims (the codestream's SIZ marker: Xsiz - XOsiz by Ysiz - YOsiz pixels of Csiz components). So a JPX image is
charged the LARGER of the two, and one whose header cannot be read is refused. Nothing is decoded here; only the
stream's headers are read.

Review 3 (2026-11-21): pixels alone did not bound the decode time. pdfium can skip resolution levels only when
the codestream has them; with ONE resolution level (the COD marker's decomposition levels NL = 0) OpenJPEG
decodes every pixel at full size. Three 4890 x 4890 16-bit grey NL = 0 images on each of 3 pages passed the
pixel caps and took 15-18 s of the child's 20 s. So every JPX image is also charged its DECODE WORK, the SIZ
size times its components: in full when NL = 0 or when NL cannot be proved (no COD read before the first tile,
a COD or COC in any tile-part header, a tile-part past the data read); at half when the main header proves
NL >= 1 for every component (measured on Windows, one 4890 x 4890 grey image: NL = 0 solid fill 1.31 s 8-bit
and 2.34 s 16-bit; NL >= 1 checkerboard 0.57-0.72 s). The work is capped per page (`MAX_PAGE_JPX_WORK`) and
over all the pages one gate call checks (`MAX_DOC_JPX_WORK`). The caps do not model OpenJPEG's memory
(measured peak 105 MiB for an 8484 x 8484 grey image); the child's memory cap (Linux) and time limit stay the
backstop.
"""
import zlib

from .pdf_layer_guards import OverBudget, _get

JPX = '/JPXDecode'
_JPX_WINDOW = 65_536
_JPX_MAX_BOXES = 64
_JPX_MAX_DEPTH = 38                                  # the deepest a JPEG2000 component may be, in bits
_J2K_START = b'\xff\x4f\xff\x51'                     # SOC then SIZ: a codestream's first two markers
_JP2_SIGNATURE = b'\x00\x00\x00\x0cjP  \r\n\x87\n'   # a JP2 file's first box
_JPX_MAX_MARKERS = 256                               # marker segments read in one header
_JPX_MAX_TILE_PARTS = 4_096                          # tile-parts walked; past them NL counts as 0
_SOT, _SOD, _EOC, _COD, _COC = b'\xff\x90', b'\xff\x93', b'\xff\xd9', b'\xff\x52', b'\xff\x53'
#: JPX decode work (SIZ pixels x components; half when every component has >= 1 decomposition level) on one
#: page, and summed over the pages one gate call checks. Real letters (870 fixture PDFs, 2026-11-21): one JPX
#: letter is measured, 352972e6, 0.83 million RGB pixels with 5 levels: work 1,238,040 (rendered in 0.51 s);
#: 10,000,000 is 8x it. A page at the cap renders in about 0.7 s (one 3162 x 3162 16-bit grey image, NL = 0).
#: The call cap is three such pages (the most any renderer asks for: `pdf_pages_png` and the offer reader stack
#: or read 3), so 3 pages of a 200 DPI A4 colour scan (NL >= 1: 5.8 million each) pass, and a census over 30
#: pages is bounded too.
MAX_PAGE_JPX_WORK = 10_000_000
MAX_DOC_JPX_WORK = 30_000_000


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
        data, whole = img._data, True
    elif before == ['/FlateDecode'] and not _predicted(img):
        try:
            data = zlib.decompressobj().decompress(img._data, _JPX_WINDOW)
        except zlib.error:
            return None
        whole = len(data) < _JPX_WINDOW              # a full window may have cut the stream short
    else:
        return None
    if data[:4] == _J2K_START:                       # a bare codestream
        siz = _siz(data, 0)
        return ([siz], _work(data, 0, whole)) if siz else None
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
            return ([siz] + found, _work(data, body, whole)) if siz else None
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


def _work(data, at, whole) -> int:
    """The decode work of the codestream at ``at`` (its SIZ marker already read): SIZ pixels x components, halved
    only when `_levels` proves every component has at least one decomposition level to skip."""
    x, y, x0, y0 = (int.from_bytes(data[at + o:at + o + 4], 'big') for o in (8, 12, 16, 20))
    full = (x - x0) * (y - y0) * int.from_bytes(data[at + 40:at + 42], 'big')
    return full if _levels(data, at, whole) == 0 else (full + 1) // 2


def _levels(data, at, whole) -> int:
    """The fewest decomposition levels (NL) any component of the codestream at ``at`` has: the main header's
    COD and COC markers. 0 (OpenJPEG decodes every pixel at full size) whenever it cannot be proved: no COD
    before the first tile-part, a marker that cannot be read, a COD or COC in ANY tile-part header (it may
    override the main header), a tile-part past the data read, or more than `_JPX_MAX_TILE_PARTS`."""
    comps = int.from_bytes(data[at + 40:at + 42], 'big')
    pos, nl = at + 4 + int.from_bytes(data[at + 4:at + 6], 'big'), None   # the marker after SIZ
    for _ in range(_JPX_MAX_MARKERS):
        if pos + 4 > len(data) or data[pos] != 0xFF:
            return 0
        marker, length = data[pos:pos + 2], int.from_bytes(data[pos + 2:pos + 4], 'big')
        if marker == _SOT:
            break
        if marker in (_COD, _COC):
            spot = pos + 9 if marker == _COD else pos + 5 + (2 if comps >= 257 else 1)
            if spot >= min(len(data), pos + 2 + length):
                return 0
            nl = data[spot] if nl is None else min(nl, data[spot])
        pos += 2 + length
    else:
        return 0
    if not nl:                                       # no COD in the main header, or NL = 0
        return 0
    for _ in range(_JPX_MAX_TILE_PARTS):             # tile-parts: Psot jumps, each header read to its SOD
        if pos + 12 > len(data) or data[pos:pos + 2] != _SOT:
            return 0
        psot, head = int.from_bytes(data[pos + 6:pos + 10], 'big'), pos + 12
        for _ in range(_JPX_MAX_MARKERS):
            if head + 4 > len(data) or data[head] != 0xFF:
                return 0
            marker = data[head:head + 2]
            if marker == _SOD:
                break
            if marker in (_COD, _COC):
                return 0
            head += 2 + int.from_bytes(data[head + 2:head + 4], 'big')
        else:
            return 0
        if psot == 0:                                # the last tile-part: it runs to the end of the data
            return nl
        pos += psot
        if data[pos:pos + 2] == _EOC or (whole and pos == len(data)):
            return nl
    return 0
