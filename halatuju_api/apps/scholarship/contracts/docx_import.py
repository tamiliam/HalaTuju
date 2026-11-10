"""Contract module: reading an author's .docx. ``segment_docx`` itself stays in the package
``__init__``, where tests patch ``_docx_structure`` and ``_extract_docx_text``.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
import json
import re

from .errors import ContractsError
from .numbering import HEADING_TITLE_MAX, MAX_CLAUSE_LEVEL, normalise_levels


# ─────────────────────────────────────────────────────────────────────────────
# Word import (populate a draft's clauses from an author's .docx — Sprint 4)
#
# The uploaded file is a POPULATE CONVENIENCE, never retained as a legal artefact:
# segment_docx returns a proposed [{heading, body}] list the author reviews, and only
# the reviewed structured clauses (saved via replace_clauses) are the source of truth.
# ─────────────────────────────────────────────────────────────────────────────
def _extract_docx_text(data):
    """Plain text of a .docx (paragraphs joined by newlines). Raises on an
    unreadable or empty document (the FE degrades to hand-editing)."""
    try:
        import docx
    except ImportError:
        raise ContractsError('docx_unavailable')
    import io as _io
    try:
        document = docx.Document(_io.BytesIO(data))
    except Exception:
        raise ContractsError('docx_unreadable')
    paragraphs = [p.text.strip() for p in document.paragraphs]
    text = '\n'.join(p for p in paragraphs if p)
    if not text.strip():
        raise ContractsError('docx_empty')
    return text


def _para_numbering(para):
    """``(numId, ilvl)`` from a paragraph's direct list formatting, or ``(None, None)``.
    Word's visible numbers (``1.``, ``1.1``, ``i)``) come from this list definition, NOT
    from ``paragraph.text`` — so this is how the structure is actually read. A missing
    ``ilvl`` element means level 0."""
    try:
        numPr = para._p.pPr.numPr
    except AttributeError:
        return None, None
    if numPr is None:
        return None, None
    numId = numPr.numId.val if numPr.numId is not None else None
    ilvl = numPr.ilvl.val if numPr.ilvl is not None else None
    return numId, ilvl


def _docx_structure(data):
    """Deterministically parse a Word ``.docx`` into our clause hierarchy using the
    document's OWN heading styles + list levels — no AI guess. Returns
    ``{'title': str, 'preamble': str, 'clauses': [{heading, body, level}]}`` or ``None``
    when the document has no usable heading structure (an unstyled / hand-numbered doc),
    so the caller can fall back to Gemini segmentation.

    The old text-only path lost structure because Word GENERATES the ``1.`` / ``1.1`` /
    ``i)`` labels from the style + list definition — they are not in ``paragraph.text``.
    Here we read that definition directly:

    * ``Title`` style                     → the agreement title.
    * a plain paragraph before clause 1   → preamble / parties recital.
    * a ``Heading N`` paragraph           → a clause; its level is the paragraph's list
      level (``ilvl``) when present, else ``N-1`` (Heading 1→0, Heading 2→1, Heading 3→2).
    * a plain paragraph carrying a list    → an item nested one level UNDER the current
      heading (so a definition/obligation list renders ``i) ii) …``).
    * a plain un-numbered paragraph after a clause → continuation body of that clause.

    Levels pass through :func:`normalise_levels` (the no-skip guard)."""
    try:
        import docx
    except ImportError:
        raise ContractsError('docx_unavailable')
    import io as _io
    try:
        document = docx.Document(_io.BytesIO(data))
    except Exception:
        raise ContractsError('docx_unreadable')

    title = ''
    preamble = []
    clauses = []
    current_heading_level = 0
    saw_clause = False
    for para in document.paragraphs:
        text = (para.text or '').strip()
        if not text:
            continue
        style = (para.style.name if para.style else '') or ''
        numId, ilvl = _para_numbering(para)
        if style == 'Title':
            if not title:
                title = text
            continue
        if style.startswith('Heading'):
            if ilvl is not None:
                level = ilvl
            else:
                m = re.search(r'(\d+)', style)
                level = (int(m.group(1)) - 1) if m else 0
            level = max(0, min(MAX_CLAUSE_LEVEL, level))
            # A short Heading is a clause TITLE; a long one is a full sub-clause the author
            # styled as a Heading (common) — that text is clause BODY, not a 255-char title.
            if len(text) > HEADING_TITLE_MAX:
                clauses.append({'heading': '', 'body': text, 'level': level})
            else:
                clauses.append({'heading': text, 'body': '', 'level': level})
            current_heading_level = level
            saw_clause = True
        elif numId is not None:
            level = min(MAX_CLAUSE_LEVEL, current_heading_level + 1) if saw_clause else 0
            clauses.append({'heading': '', 'body': text, 'level': level})
            saw_clause = True
        elif not saw_clause:
            preamble.append(text)
        elif clauses:
            last = clauses[-1]
            last['body'] = (last['body'] + '\n\n' + text) if last['body'] else text

    # Only usable if the document actually carried headings; otherwise it is an unstyled
    # doc and the AI fallback will read it better than this structural walk would.
    if not clauses or not any(c['heading'] for c in clauses):
        return None
    levels = normalise_levels([c['level'] for c in clauses])
    for c, lv in zip(clauses, levels):
        c['level'] = lv
    return {'title': title, 'preamble': '\n\n'.join(preamble).strip(), 'clauses': clauses}


def _build_segment_prompt(text):
    return (
        'You segment the plain text of a bursary-agreement document into its numbered '
        'clauses. Return STRICT JSON only, no prose: a list '
        '[{"heading": str, "body": str, "level": 0|1|2}, ...] in document order. Each heading '
        "is the clause's short title; each body is its plain-text content (keep paragraphs as "
        'blank-line-separated text). "level" is the nesting depth read from the numbering: '
        '0 for a main clause (1., 2., 3.), 1 for a sub-clause (1.1, 2.3), 2 for a sub-sub-clause '
        '(i), (ii), (a), (b)). A sub-clause must follow its parent; never skip a level. '
        'Do NOT invent, summarise, or reword — copy the wording. Drop page headers/footers, '
        'signature blocks and the title.\n\nDOCUMENT:\n' + text
    )


def _parse_segments(raw):
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text).strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise ContractsError('segmentation_failed')
    if not isinstance(data, list) or not data:
        raise ContractsError('segmentation_failed')
    clauses = []
    for item in data:
        if not isinstance(item, dict):
            raise ContractsError('segmentation_failed')
        heading = (item.get('heading') or '').strip()
        body = (item.get('body') or '').strip()
        if not (heading or body):
            continue
        clauses.append({'heading': heading, 'body': body, 'level': item.get('level', 0)})
    if not clauses:
        raise ContractsError('segmentation_failed')
    # Enforce the no-skip rule on the proposed levels (the model can drift); the author still
    # reviews the result before it is saved.
    levels = normalise_levels([c['level'] for c in clauses])
    for c, lv in zip(clauses, levels):
        c['level'] = lv
    return clauses
