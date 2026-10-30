"""A letter's PDF (student maintenance Sprint 6b, 2026-10-31) — xhtml2pdf, the contract's engine and font.

English or Malay only (owner ruling, 2026-10-30): reportlab cannot shape Tamil, so a Tamil PDF
would print its vowel signs in the wrong order. The body arrives as the shared renderer's escaped
HTML paragraphs (`email_templates.render`), so nothing here formats text itself.

Its own module, not `bursary.py` (on the oversize ledger): it borrows only the font registration.
"""
from html import escape
from io import BytesIO

_LABELS = {
    'en': {'date': 'Date', 'to': 'To', 'reply': 'Please confirm you have received this letter by',
           'ref': 'Reference'},
    'ms': {'date': 'Tarikh', 'to': 'Kepada', 'reply': 'Sila sahkan anda telah menerima surat ini sebelum',
           'ref': 'Rujukan'},
}


def html_for(letter, *, html_body):
    from .letters import format_day, student_name
    lang = letter.language if letter.language in _LABELS else 'en'
    labels = _LABELS[lang]
    app = letter.application
    org = getattr(getattr(app, 'owning_organisation', None), 'name', '') or ''
    issued = letter.issued_at.date() if letter.issued_at else None
    return (
        '<html><head><meta charset="utf-8"><style>'
        '@page { size: A4; margin: 2.2cm 2.2cm 2.4cm 2.2cm; }'
        "body { font-family: 'IBM Plex Serif', Georgia, serif; font-size: 11pt; color: #111827; }"
        'h1 { font-size: 14pt; margin: 0 0 4pt 0; } .muted { color: #4b5563; font-size: 9.5pt; }'
        'h2 { font-size: 12pt; margin: 18pt 0 10pt 0; } p { margin: 0 0 9pt 0; line-height: 1.45; }'
        '</style></head><body>'
        f'<h1>{escape(org)}</h1>'
        f'<p class="muted">{labels["ref"]}: L-{letter.id} &nbsp;·&nbsp; {labels["date"]}: '
        f'{escape(format_day(issued, lang)) if issued else ""}</p>'
        f'<p class="muted">{labels["to"]}: {escape(student_name(app) or "")}</p>'
        f'<h2>{escape(letter.subject)}</h2>'
        f'{html_body}'
        f'<p class="muted">{labels["reply"]} {escape(format_day(letter.response_due_on, lang))}.</p>'
        '</body></html>'
    )


def render_pdf(letter, *, html_body):
    """The PDF bytes. Raises on failure — `letters.issue` refuses the letter rather than store none."""
    from xhtml2pdf import pisa
    from .bursary import _register_contract_fonts
    _register_contract_fonts()
    out = BytesIO()
    result = pisa.CreatePDF(html_for(letter, html_body=html_body), dest=out, encoding='utf-8')
    if result.err:
        raise RuntimeError(f'xhtml2pdf reported {result.err} error(s)')
    return out.getvalue()
