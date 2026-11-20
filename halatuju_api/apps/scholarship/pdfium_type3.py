"""The Type3 glyph rules for the pdfium child (moved out of `pdfium_worker`, which was over the line limit).

Pure Python plus pypdf (imported inside the function): no pdfium. `pdfium_worker` re-exports `T3_TOLERANCE`,
`T3_MAX_BYTES` and `_type3_ok`, and loads this file by path when it runs as a script.
"""

#: Type3 glyph procedures (review round 2, B2): a glyph whose procedure paints outside its own ``d1`` box draws
#: ink where pdfium's char box is not (a tiny /space glyph placed far away painting boxes over a white word), so
#: the overlap and stray rules miss it. Every Type3 font page 1 can reach must keep each path coordinate inside its
#: glyph's ``d1`` box (`T3_TOLERANCE` of the box's longer side), use only the operators below, and a ``d0`` glyph
#: (coloured: anything goes) may not paint at all. Genuine cost: the 6 UiTM letters with Type3 fonts pass; 0 of
#: the 58 UMS use one. Fix round 3 (review round 3's BLOCKER): the tolerance is a share of the box's LONGER side,
#: so a flat 1000 x 1 glyph may paint 20 units (20x its height) above and below its box, onto a white value. While
#: the rules lane is UMS-only, ANY Type3 font page 1 can reach refuses (`pdf_ink.TYPE3_LANES` is empty); this
#: check only matters once a lane allows Type3, and before that the tolerance must change (decisions.md).
T3_TOLERANCE = 0.02
#: Path construction: the operator and its operand count (each pair an x, y to check).
_T3_PATH = {'m': 2, 'l': 2, 'c': 6, 'v': 4, 'y': 4}
#: Operators that paint nothing outside the path: filling, closing, ending or clipping a path, graphics state with
#: no matrix, colour (ignored under d1), marked content. Not here, so refused: cm, gs, Do, an inline image, sh,
#: any text operator, a stroke (it paints past the path by the line width; no genuine glyph strokes), anything else.
_T3_FILL_OPS = frozenset(('f', 'F', 'f*'))
_T3_STATE_OPS = frozenset('h n W W* q Q w J j M d ri i g G rg RG k K cs CS sc SC scn SCN BMC BDC EMC MP DP BX EX'
                          .split())
#: The most bytes of glyph procedures read for one page (a genuine letter's Type3 fonts: well under 1 MB).
T3_MAX_BYTES = 4_000_000


def type3_ok(font, budget: list) -> bool:
    """True when every glyph procedure of the Type3 ``font`` keeps to the rules above (`T3_TOLERANCE`)."""
    from pypdf.generic import ContentStream
    procs = font.get('/CharProcs')
    procs = procs.get_object() if procs is not None else None
    if not hasattr(procs, 'values'):
        return False
    for ref in procs.values():
        proc = ref.get_object()
        budget[0] -= len(proc.get_data())
        if budget[0] < 0:
            return False
        try:
            ops = [(args, _op_name(op)) for args, op in ContentStream(proc, None).operations]
        except Exception:                         # a glyph pypdf cannot parse is not one it can vouch for
            return False
        if not ops:
            continue
        head_args, head = ops[0]
        if head == 'd0':                          # a coloured glyph: it may set state, never paint
            if any(name not in _T3_STATE_OPS for _a, name in ops[1:]):
                return False
            continue
        if head != 'd1' or len(head_args) != 6:
            return False
        llx, lly, urx, ury = (float(v) for v in head_args[2:])
        llx, urx, lly, ury = min(llx, urx), max(llx, urx), min(lly, ury), max(lly, ury)
        tol = T3_TOLERANCE * max(urx - llx, ury - lly)
        for args, name in ops[1:]:
            if name in _T3_PATH or name == 're':
                nums = [float(v) for v in args]
                if name == 're':
                    if len(nums) != 4:
                        return False
                    x, y, w, h = nums
                    pts = [(x, y), (x + w, y + h)]
                else:
                    if len(nums) != _T3_PATH[name]:
                        return False
                    pts = list(zip(nums[0::2], nums[1::2]))
                if any(not (llx - tol <= px <= urx + tol and lly - tol <= py <= ury + tol) for px, py in pts):
                    return False
            elif name not in _T3_FILL_OPS and name not in _T3_STATE_OPS:
                return False
    return True


def _op_name(op) -> str:
    return op.decode('latin-1') if isinstance(op, bytes) else str(op)
