"""The ink op's own-ink attribution and its point-to-pixel map, for the pdfium child (moved out of `pdfium_worker`
with no change at the OCR-9 rebase: the worker was over the line limit).

Pure Python plus numpy and Pillow (imported inside the function): no pdfium is imported here; `device_map` gets
pdfium's raw module from its caller. `pdfium_worker` loads this file by path when it runs as a script.
"""
import ctypes
import math

#: The grid (pixels per cell) that finds a character's neighbours; the most cells, and the most neighbours one
#: character may have (a genuine character: a handful; a pile of glyphs past it counts as no ink).
_CELL = 32
MAX_INK_CELLS = 200_000
MAX_INK_NEIGHBOURS = 64


def device_map(raw, page, width, height):
    """Page points -> picture pixels, NOT rounded (`FPDF_PageToDevice` rounds): the inverse of the exact map
    `FPDF_DeviceToPage` gives at three corners of the picture."""
    px, py = ctypes.c_double(), ctypes.c_double()

    def page_at(x, y):
        raw.FPDF_DeviceToPage(page, 0, 0, width, height, 0, x, y, px, py)
        return px.value, py.value
    (ox, oy), (ax, ay), (bx, by) = page_at(0, 0), page_at(width, 0), page_at(0, height)
    a, b, c, d = (ax - ox) / width, (bx - ox) / height, (ay - oy) / width, (by - oy) / height
    det = a * d - b * c
    if not det:
        raise ValueError('device map')

    def devf(x, y):
        x, y = x - ox, y - oy
        return (d * x - b * y) / det, (a * y - c * x) / det
    return devf


def own_ink(delta, seen, chars, width, height, threshold: int, turned: bool) -> bool:
    """Fill ``ink_px``, ``area_px``, ``cover_h`` and ``cover_w`` (``chars[i][6, 7, 9, 10]``) of every drawn
    non-space character from the diff picture ``delta``; False (nothing to trust) past `MAX_INK_CELLS`.

    Review round 2b (the ring attack): a black glyph TOUCHING a white character put its edge pixels in that
    character's box (+1 px). Now a pixel is a character's ink only when the OTHER drawn characters (a non-space,
    or a space with ink) cannot explain its change: each changes a pixel by at most 255 x the share of it that
    its box covers (exactly placed, widened by `OWN_PAD_X` / `OWN_PAD_Y`); what is left must still reach
    ``threshold``. A pixel two characters both reach is nobody's: a genuine letter keeps its inside, so this costs
    0 genuine letters; bars TOUCHING a black character can take it too (refused: the AI reads it)."""
    import numpy as np
    from PIL import Image
    big = np.asarray(delta, dtype=np.float32)
    others = [k for k, s in enumerate(seen) if s and (not s[2] or (s[3] and chars[k][6] > 0))]
    grid, entries = {}, 0
    for k in others:
        x0, y0, x1, y1 = seen[k][0]
        cx = range(max(0, math.floor(x0)) // _CELL, max(0, min(width, math.ceil(x1)) - 1) // _CELL + 1)
        cy = range(max(0, math.floor(y0)) // _CELL, max(0, min(height, math.ceil(y1)) - 1) // _CELL + 1)
        entries += len(cx) * len(cy)
        if entries > MAX_INK_CELLS:
            return False
        for gx in cx:
            for gy in cy:
                grid.setdefault((gx, gy), []).append(k)
    for i, s in enumerate(seen):
        if not s or s[2]:
            continue
        box = s[1]
        if not (box[2] > box[0] and box[3] > box[1]):
            continue
        part = big[box[1]:box[3], box[0]:box[2]]
        nb = {k for gx in range(box[0] // _CELL, (box[2] - 1) // _CELL + 1)
              for gy in range(box[1] // _CELL, (box[3] - 1) // _CELL + 1) for k in grid.get((gx, gy), ()) if k != i}
        if len(nb) > MAX_INK_NEIGHBOURS:
            part = np.zeros_like(part)            # a pile of glyphs: no ink of its own (refused)
            nb = ()
        if nb:
            cols = np.arange(box[0], box[2], dtype=np.float32)
            rows = np.arange(box[1], box[3], dtype=np.float32)
            share = np.zeros_like(part)
            for k in nb:
                x0, y0, x1, y1 = seen[k][0]
                ox = np.clip(np.minimum(cols + 1, x1) - np.maximum(cols, x0), 0, 1)
                oy = np.clip(np.minimum(rows + 1, y1) - np.maximum(rows, y0), 0, 1)
                share += np.outer(oy, ox)
            part = part - 255 * np.minimum(share, 1)
        own = part >= threshold
        crop = Image.fromarray((own * 255).astype(np.uint8), 'L')
        chars[i][6], chars[i][7] = int(own.sum()), (box[2] - box[0]) * (box[3] - box[1])
        bb = crop.getbbox()
        if bb:
            cover_h = round((bb[3] - bb[1]) / (box[3] - box[1]), 3)
            cover_w = round((bb[2] - bb[0]) / (box[2] - box[0]), 3)
            if turned:                          # /Rotate 90 or 270: the glyph's height runs across the picture
                cover_h, cover_w = cover_w, cover_h
            chars[i][9], chars[i][10] = cover_h, cover_w
    return True
