"""Contract module: the clause HTML shared by the signed agreement and the preview.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
import re

from .numbering import clause_numbers
from .readers import resolve_locale


def _bold(escaped):
    """Canonical markdown-``**bold**`` → ``<b>…</b>`` transform, run on an ALREADY-ESCAPED
    string so the emphasis can never inject markup. Non-greedy, single-line: an unmatched
    ``**`` is left literal. The single source of truth for bold — ``bursary._bold`` (the
    signed-agreement render) delegates here so the preview and the PDF stay in step."""
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped or '')


def render_clauses_html(clauses, *, base_indent=4):
    """Shared clause-list → HTML for BOTH the signed agreement and the preview, so the two
    always look identical. ``clauses`` is an iterable of ``(heading, body, level)`` whose text
    is already localised / variable-substituted by the caller (RAW of markup — escaping and
    ``**bold**`` happen here). Rendering rules (2026-07-21, owner review):
      • the number, heading and body render INLINE — the number is never on its own line;
      • only a TOP-LEVEL (level 0) clause's number + heading are BOLD (sub-clauses / sub-sub
        are normal weight, numbers included);
      • depth adds a left indent.
    Body paragraphs (blank-line separated) render under the first line with a break."""
    from django.utils.html import escape
    # Number-column width per level (px). A clause is indented by the SUM of its ancestors'
    # gutters, so a child's number lines up with where its parent's TEXT begins (the classic
    # legal outline: '1.1.' aligns under 'Definitions', 'I.' under 'In this Agreement').
    gutters = (22, 34, 30)
    clauses = list(clauses)
    numbers = clause_numbers([lv for _, _, lv in clauses])
    out = []
    for (heading, body, level), number in zip(clauses, numbers):
        top = level == 0
        prefix = base_indent + sum(gutters[:level])
        gutter = gutters[min(level, len(gutters) - 1)]
        num = f'<b>{escape(number)}</b>' if top else escape(number)
        head = ''
        if heading:
            h = _bold(escape(heading))
            head = f'<b>{h}</b> ' if top else f'{h} '
        paras = [_bold(escape(p)) for p in (body or '').split('\n\n') if p.strip()]
        body_html = '<br/><br/>'.join(paras)
        # A per-clause 2-cell table gives the HANGING INDENT (a wrapped line aligns in the text
        # column, not under the number); the table's left MARGIN does the per-depth nest.
        # (xhtml2pdf reduces the available width by the margin, so width:100% never overflows —
        # a wrapping div + width:100% table instead computes a NEGATIVE width and crashes.)
        out.append(
            f'<table style="width:100%; border-collapse:collapse; margin:0 0 6px {prefix}px;">'
            f'<tr><td style="width:{gutter}px; vertical-align:top; white-space:nowrap;">{num}</td>'
            f'<td style="vertical-align:top;">{head}{body_html}</td></tr></table>')
    return ''.join(out)


def render_preview_html(template, locale='en'):
    """A minimal standalone HTML preview (PREVIEW banner + English-authoritative notice).
    Sample particulars only — never a real signed artefact. Uses the SHARED clause renderer
    (render_clauses_html), so numbering (1. / 1.1 / i)), inline layout, bold rules and
    ``**bold**`` match the signed agreement exactly; ``{{variable}}`` tokens are left visible
    (no student context in a preview). Served as inline HTML and, via ``?output=pdf``, as PDF."""
    from django.utils.html import escape as _esc
    if template is None:
        return '<html><body><p>No template.</p></body></html>'
    loc = resolve_locale(locale, template)

    def rich(text):
        return _bold(_esc(text or ''))

    title = getattr(template, f'title_{loc}', '') or template.title_en
    preamble = getattr(template, f'preamble_{loc}', '') or template.preamble_en
    clauses = [
        (getattr(c, f'heading_{loc}', '') or c.heading_en,
         getattr(c, f'body_{loc}', '') or c.body_en, getattr(c, 'level', 0) or 0)
        for c in template.clauses.all().order_by('order')
    ]
    parts = [
        '<div style="background:#fde68a;padding:8px;text-align:center;">PREVIEW — not a signed agreement</div>',
        '<div style="background:#eff6ff;padding:6px;font-size:12px;">'
        'The English version is authoritative; other languages are courtesy translations.</div>',
        f'<h1>{rich(title)}</h1>',
        f'<p>{rich(preamble)}</p>',
        render_clauses_html(clauses),
    ]
    footer = f'Version {_esc(template.version)}'
    if template.vetted_by_name and template.vetted_on:
        footer += f' — Vetted by {_esc(template.vetted_by_name)}, {_esc(str(template.vetted_on))}'
    parts.append(f'<hr><p style="font-size:12px;color:#666;">{footer}</p>')
    return '<html><body>' + ''.join(parts) + '</body></html>'
