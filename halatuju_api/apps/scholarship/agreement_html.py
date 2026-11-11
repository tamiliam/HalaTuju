"""The signed bursary agreement's HTML pieces: the value formatters and the particulars,
Schedule 1 and signature sections that ``bursary.render_agreement_html`` assembles.

Moved unchanged out of ``bursary.py`` by audit A3.8 (2026-11-10), so that function fits the
150-line limit. Each section builder returns the list of HTML strings the render used to append
inline, in the same order; ``bursary`` re-imports every name, so ``bursary._esc`` and the rest
still resolve.
"""
from decimal import Decimal


def _esc(s):
    """Minimal HTML escaping for interpolated values."""
    return (str(s or '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _fmt_amount(amount):
    if amount is None:
        return '—'
    try:
        return f'RM{Decimal(amount):,.2f}'
    except Exception:  # noqa: BLE001 — any unparseable amount falls back to the raw text
        return f'RM{amount}'


def _fmt_dt(dt):
    return dt.strftime('%d %b %Y, %H:%M') if dt else '—'


def _signature_block(role, *, name, nric='', extra='', signed_at):
    """One self-contained signature block (inline CSS only)."""
    lines = [f'<div style="font-weight:bold;">{_esc(role)}</div>']
    lines.append(f'<div>Name: {_esc(name) or "&mdash;"}</div>')
    if nric:
        lines.append(f'<div>NRIC: {_esc(nric)}</div>')
    if extra:
        lines.append(f'<div>{_esc(extra)}</div>')
    lines.append(f'<div>Signed: {_esc(_fmt_dt(signed_at))}</div>')
    inner = ''.join(lines)
    return (
        '<td style="width:50%; vertical-align:top; padding:8px; '
        'border:1px solid #999;">' + inner + '</td>'
    )


def _guarantor_role_label(parent_role):
    """The signature-block label for the parent/guardian party, driven by the
    template's ``parent_role`` so the config and the wording agree by construction.
    ``co_signer_all`` (the v1 default): the parent co-signs the whole agreement;
    ``minor_only`` (fenced in v1) keeps the legacy surety wording."""
    if parent_role == 'co_signer_all':
        return 'Parent/Guardian — Co-signer / Ibu bapa atau Penjaga (Penandatangan bersama)'
    return 'Guarantor / Penjamin (surety)'


def _bold(escaped):
    """Markdown-``**bold**`` → ``<b>…</b>`` on an already-escaped string. Delegates to the
    canonical ``contracts._bold`` so the signed agreement, the preview and the preview PDF
    share ONE bold transform (no drift)."""
    from . import contracts
    return contracts._bold(escaped)


def particulars_html(particulars, student, guarantor):
    """The Particulars / Butiran table."""
    parts = []
    p = particulars
    parts.append('<h2 style="font-size:13px; margin:14px 0 6px 0;">Particulars / Butiran</h2>')
    parts.append('<table style="width:100%; border-collapse:collapse; font-size:11px;">')
    rows = [
        ('Student', _esc(student.get('name', ''))),
        ('Student NRIC', _esc(student.get('nric', ''))),
        ('Bursary amount', _esc(_fmt_amount(p.get('award_amount')))),
        ('Payment schedule', _esc(p.get('payment_schedule', ''))),
        ('Institution', _esc(p.get('institution_name', '')) or '&mdash;'),
        ('Course', _esc(p.get('course_name', '')) or '&mdash;'),
        ('Academic progress standard', _esc(p.get('progress_standard', ''))),
        ('Guarantor', _esc(guarantor.get('name', ''))),
        ('Guarantor relationship', _esc(guarantor.get('relationship', '')) or '&mdash;'),
    ]
    for k, v in rows:
        parts.append(
            '<tr>'
            f'<td style="border:1px solid #ccc; padding:4px; width:40%; '
            f'background:#f3f4f6; font-weight:bold;">{k}</td>'
            f'<td style="border:1px solid #ccc; padding:4px;">{v}</td>'
            '</tr>')
    parts.append('</table>')
    return parts


def schedule_html(calendar):
    """Schedule 1, the month-by-month payment table (template only; gap months shown).
    Nothing when the template has no calendar for this case."""
    parts = []
    if calendar:
        parts.append('<h2 style="font-size:13px; margin:14px 0 6px 0;">'
                     'Schedule 1 / Jadual 1 — Payment schedule</h2>')
        parts.append('<table style="width:100%; border-collapse:collapse; font-size:11px;">')
        parts.append('<tr>'
                     '<td style="border:1px solid #ccc; padding:4px; background:#f3f4f6; '
                     'font-weight:bold; width:50%;">Month / Bulan</td>'
                     '<td style="border:1px solid #ccc; padding:4px; background:#f3f4f6; '
                     'font-weight:bold;">Amount / Amaun</td></tr>')
        for m in calendar:
            cell = (_fmt_amount(m['amount']) if m['paid']
                    else 'Exam month — no payment / Bulan peperiksaan — tiada bayaran')
            style = '' if m['paid'] else ' color:#92400e; background:#fffbeb;'
            parts.append(
                '<tr>'
                f'<td style="border:1px solid #ccc; padding:4px;{style}">{_esc(m["label"])}</td>'
                f'<td style="border:1px solid #ccc; padding:4px;{style}">{_esc(cell)}</td>'
                '</tr>')
        parts.append('</table>')
    return parts


def signatures_html(student, guarantor, foundation, witness, guarantor_role):
    """The four signature blocks: student, guarantor, Foundation and witness."""
    parts = []
    parts.append('<h2 style="font-size:13px; margin:16px 0 6px 0;">Signatures / Tandatangan</h2>')
    parts.append('<table style="width:100%; border-collapse:collapse;">')
    parts.append('<tr>')
    parts.append(_signature_block(
        'Student / Pelajar', name=student.get('name', ''), nric=student.get('nric', ''),
        signed_at=student.get('signed_at')))
    parts.append(_signature_block(
        guarantor_role, name=guarantor.get('name', ''),
        nric=guarantor.get('nric', ''),
        extra=(f"Relationship: {guarantor.get('relationship', '')}"
               if guarantor.get('relationship') else ''),
        signed_at=guarantor.get('signed_at')))
    parts.append('</tr><tr>')
    parts.append(_signature_block(
        'For the Foundation / Bagi pihak Yayasan',
        name=foundation.get('name', ''), nric=foundation.get('nric', ''),
        extra=foundation.get('title', ''), signed_at=foundation.get('signed_at')))
    # The witness's own name (typed when recorded), else its organisation — NEVER `by`, the officer
    # who recorded it (the Contract tab's rule, `scholar_money.contract_payload`; source sign-in S4).
    parts.append(_signature_block(
        'Witness — Partner Organisation / Saksi',
        name=witness.get('name') or witness.get('org', ''),
        extra=(f"Organisation: {witness.get('org', '')}" if witness.get('org') else ''),
        signed_at=witness.get('signed_at')))
    parts.append('</tr></table>')
    return parts
