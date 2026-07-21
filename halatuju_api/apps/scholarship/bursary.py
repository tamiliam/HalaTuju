"""Conditional Bursary Award Agreement — the binding bursary CONTRACT a student
signs (with a parent/guardian as surety/guarantor) when they accept a sponsor's
award.

Parties: the STUDENT (primary), the PARENT/GUARDIAN (surety/guarantor), the
FOUNDATION (counterparty — signatory from settings) and the PARTNER ORGANISATION
(non-blocking witness). The DONOR is NEVER a party and is never named — anonymity
is sacred. The contract names the FOUNDATION only.

This module is the deterministic core: the particulars builder, the immutable HTML
render, the shared guarantor-identity gate (extracted from the consent view), the
xhtml2pdf render, the ``sign_agreement`` / ``countersign_foundation`` /
``record_witness`` writers, and the executed-agreement distribution.

The agreement's TEXT (title, preamble, clauses, schedule, counterparty) now comes from
the org-owned, versioned ``ContractTemplate`` (apps.scholarship.contracts) — the
hard-coded constants that used to live here were removed in Sprint 5 after a render-diff
parity test. The whole feature ships behind ``BURSARY_AGREEMENT_ENABLED`` (default OFF).
"""
import hashlib
import io
import logging
import os
import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .vision import name_match, nric_match

logger = logging.getLogger(__name__)


class BursaryError(Exception):
    """Raised by the bursary writers with a machine-readable ``.code`` so the
    acceptance flow / the view can surface it as a 400 with that code."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


def _locale(locale):
    """Normalise to a template locale ('en' or 'ms'). 'ta'/unknown → 'en'."""
    return 'ms' if (locale or '').startswith('ms') else 'en'


def particulars_for(application, template, locale='en'):
    """Build the filled-in particulars dict for an application from the versioned
    ``template`` — the payment schedule, progress standard and counterparty (Foundation
    signatory) all come from it (Sprint 5: the hard-coded constants were removed after a
    render-diff parity test). ``template`` is REQUIRED — ``sign_agreement`` resolves it and
    raises ``no_active_template`` when absent. NEVER reads or exposes any donor identity."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    institution = (cp.get('institution') or '').strip()
    course = (cp.get('course_name') or '').strip()
    if not course:
        course = (getattr(application, 'field_of_study', '') or '').strip()

    from . import contracts
    lang = _locale(locale)
    row = contracts.schedule_row_for(template, application)
    return {
        'award_amount': application.award_amount,
        'payment_schedule': contracts.schedule_summary_text(row, lang) if row else '',
        'institution_name': institution,
        'course_name': course,
        'commencement_date': None,
        'progress_standard': getattr(template, f'progress_standard_{lang}', '') or template.progress_standard_en,
        'foundation_signatory_name': template.counterparty_name,
        'foundation_signatory_title': template.counterparty_title,
        'foundation_signatory_nric': template.counterparty_nric,
    }


def _esc(s):
    """Minimal HTML escaping for interpolated values."""
    return (str(s or '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _fmt_amount(amount):
    if amount is None:
        return '—'
    try:
        return f'RM{Decimal(amount):,.2f}'
    except Exception:  # noqa: BLE001
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
    """Convert markdown-style ``**bold**`` in an ALREADY-ESCAPED string to ``<b>…</b>``.
    Runs on escaped text so the emphasis markup can never inject HTML; non-greedy and
    single-line, so an unmatched ``**`` is left literal."""
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped)


def _clause_body_html(body):
    """Plain-text clause body → HTML: a blank line becomes a paragraph break, and the
    author's ``**bold**`` inline emphasis is honoured (escaped first, so it is safe)."""
    paras = [_bold(_esc(p)) for p in (body or '').split('\n\n') if p.strip()]
    return '<br/><br/>'.join(paras)


def render_agreement_html(application, particulars, *, student, guarantor,
                          foundation, witness, locale='en', template):
    """Render the full, self-contained agreement HTML (inline CSS only — xhtml2pdf
    has limited CSS support). This is the immutable snapshot stored on the record.

    The title/preamble/clauses, the party-block wording and the Schedule 1 payment table
    all come from the versioned ``template`` (REQUIRED — Sprint 5 removed the hard-coded
    constants fallback after a render-diff parity test). A deployed template is
    lawyer-vetted, so the document carries an "English is authoritative" notice (no DRAFT
    banner) + a "Vetted by {name}, {date}" footer.

    ``student`` / ``guarantor`` / ``foundation`` / ``witness`` are dicts with the party's
    name (+ nric/role/timestamp where applicable). The donor is NEVER rendered."""
    from . import contracts
    lang = _locale(locale)

    # {{variable}} merge context — resolved into this signed snapshot only (the template
    # keeps the generic tokens). A commencement date renders British-style; unknown tokens
    # are left visible (see contracts.substitute_vars).
    commencement = particulars.get('commencement_date')
    ctx = {
        'student_name': student.get('name', ''),
        'student_nric': student.get('nric', ''),
        'guarantor_name': guarantor.get('name', ''),
        'guarantor_relationship': guarantor.get('relationship', ''),
        'donor_name': getattr(template, 'counterparty_name', '') or '',
        'amount': _fmt_amount(particulars.get('award_amount')),
        'institution': particulars.get('institution_name', ''),
        'course': particulars.get('course_name', ''),
        'commencement_date': (commencement.strftime('%d %B %Y')
                              if hasattr(commencement, 'strftime') else (commencement or '')),
        'progress_standard': particulars.get('progress_standard', ''),
    }
    sub = lambda s: contracts.substitute_vars(s, ctx)

    title = sub(getattr(template, f'title_{lang}', '') or template.title_en)
    preamble = sub(getattr(template, f'preamble_{lang}', '') or template.preamble_en)
    clauses = [
        (sub(getattr(c, f'heading_{lang}', '') or c.heading_en),
         sub(getattr(c, f'body_{lang}', '') or c.body_en),
         c.level)
        for c in template.clauses.all().order_by('order')
    ]
    clause_numbers = contracts.clause_numbers([lv for _, _, lv in clauses])
    guarantor_role = _guarantor_role_label(template.parent_role)
    version = template.version
    vetted_line = (f'Vetted by {template.vetted_by_name}, {template.vetted_on}'
                   if template.vetted_by_name and template.vetted_on else '')
    cohort_year = getattr(getattr(application, 'cohort', None), 'year', None)
    row = contracts.schedule_row_for(template, application)
    calendar = contracts.schedule_calendar(row, cohort_year, lang)

    parts = [
        # IBM Plex Serif for the contract document (2026-07-19). The face is registered with
        # reportlab (xhtml2pdf's engine) in generate_pdf, so xhtml2pdf EMBEDS it in the PDF.
        # The browser preview (a sandboxed srcDoc iframe with no font loaded) falls back to the
        # serif stack below — a close visual match to the embedded PDF font.
        '<html><head><meta charset="utf-8"/></head>',
        '<body style="font-family: \'IBM Plex Serif\', Georgia, \'Times New Roman\', serif; '
        'font-size: 11px; color: #222; line-height: 1.4;">',
        '<div style="background:#eff6ff; border:1px solid #bfdbfe; color:#1e40af; '
        'padding:6px 10px; text-align:center; font-size:9px; margin-bottom:12px;">'
        'The English version of this Agreement is authoritative; any other language '
        'is a courtesy translation.</div>',
        f'<h1 style="font-size:18px; text-align:center; margin:0 0 4px 0;">{_esc(title)}</h1>',
        f'<p>{_bold(_esc(preamble))}</p>',
    ]

    # Particulars table.
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

    # Schedule 1 — the month-by-month payment table (template only; gap months shown).
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

    # Clauses.
    parts.append('<h2 style="font-size:13px; margin:16px 0 6px 0;">Terms / Terma</h2>')
    # Computed hierarchical numbering (1. / 1.1 / i)) + per-level indent — NOT an <ol> (mixed
    # decimal/roman numbering + depth is handled here, which xhtml2pdf renders reliably).
    for (heading, body, level), number in zip(clauses, clause_numbers):
        indent = 4 + level * 18
        head = f'<b>{_esc(heading)}.</b> ' if heading else ''
        parts.append(
            f'<div style="margin:0 0 7px 0; padding-left:{indent}px;">'
            f'<b>{_esc(number)}</b> {head}{_clause_body_html(body)}</div>')

    # Signature blocks.
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
    parts.append(_signature_block(
        'Witness — Partner Organisation / Saksi',
        name=witness.get('by', ''),
        extra=(f"Organisation: {witness.get('org', '')}" if witness.get('org') else ''),
        signed_at=witness.get('signed_at')))
    parts.append('</tr></table>')

    footer = f'Version {_esc(version)}.'
    if vetted_line:
        footer += f' {_esc(vetted_line)}.'
    parts.append(f'<p style="margin-top:14px; font-size:9px; color:#666;">{footer}</p>')
    parts.append('</body></html>')
    return ''.join(parts)


def guarantor_identity_check(application, name, nric):
    """The shared parent/guardian identity gate, extracted from the consent POST so
    it can be reused for BOTH the consent flow and the bursary agreement.

    A ``parent_ic`` document is compulsory for ALL students (adults included), so
    this works regardless of age. Returns one of:
      'ok'                         — name + NRIC match the OCR'd parent_ic
      'parent_ic_missing'          — no usable parent_ic (none uploaded, or OCR
                                     hasn't run / errored)
      'parent_ic_nric_mismatch'    — typed NRIC doesn't match the IC
      'parent_ic_name_mismatch'    — typed name doesn't match the IC
    """
    present_qs = application.documents.filter(superseded_at__isnull=True)
    parent_ic = next(
        (d for d in present_qs
         if d.doc_type == 'parent_ic' and d.vision_run_at and not d.vision_error),
        None,
    )
    if parent_ic is None:
        return 'parent_ic_missing'
    if parent_ic.vision_nric and not nric_match(nric, parent_ic.vision_nric):
        return 'parent_ic_nric_mismatch'
    if parent_ic.vision_name and name_match(parent_ic.vision_name, name) != 'match':
        return 'parent_ic_name_mismatch'
    return 'ok'


def guarantor_phone_for(application):
    """The parent/guardian SURETY's pre-declared phone — read (locked) from the student's
    ``profile.guardians`` list captured at apply. Returns the first non-blank phone, or ''.

    This is the ONLY number a PIN is ever sent to: the student cannot edit it at signing,
    which is what makes the same-session parent check meaningful. An editable phone would
    let a dishonest student self-verify in the parent's place, defeating the gate."""
    profile = getattr(application, 'profile', None)
    for g in (getattr(profile, 'guardians', None) or []):
        phone = ((g or {}).get('phone') or '').strip()
        if phone:
            return phone
    return ''


def guarantor_phone_verification_fresh(application):
    """True when the guarantor's phone-PIN check was stamped within the freshness TTL.
    The window stops a signature riding a days-old verification."""
    ts = application.guarantor_phone_verified_at
    if ts is None:
        return False
    ttl = getattr(settings, 'GUARANTOR_PHONE_VERIFY_TTL_SECONDS', 1800)
    return (timezone.now() - ts).total_seconds() <= ttl


_FONT_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
_FONTS_REGISTERED = False


def _register_contract_fonts():
    """Register the bundled IBM Plex Serif faces with reportlab (xhtml2pdf's engine) so the
    contract document font is EMBEDDED in the PDF. Idempotent; best-effort — if the font files
    are missing, xhtml2pdf simply falls back to the serif stack in the HTML (Georgia/Times).
    Registering with reportlab directly avoids xhtml2pdf's @font-face temp-file handling (which
    is flaky on Windows) and is the standard custom-font pattern for xhtml2pdf."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.fonts import addMapping
        from xhtml2pdf.default import DEFAULT_FONT
        regular = os.path.join(_FONT_DIR, 'IBMPlexSerif-Regular.ttf')
        bold = os.path.join(_FONT_DIR, 'IBMPlexSerif-Bold.ttf')
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont('IBM Plex Serif', regular))
            pdfmetrics.registerFont(TTFont('IBM Plex Serif Bold', bold))
            addMapping('IBM Plex Serif', 0, 0, 'IBM Plex Serif')       # normal
            addMapping('IBM Plex Serif', 1, 0, 'IBM Plex Serif Bold')  # bold
            # Tell xhtml2pdf's font resolver (getFontName looks up the lowercased CSS family in
            # fontList, seeded from DEFAULT_FONT) to map the family to the reportlab base font.
            DEFAULT_FONT['ibm plex serif'] = 'IBM Plex Serif'
    except Exception:
        logger.warning('bursary: could not register contract fonts; PDF will use the serif '
                       'fallback', exc_info=True)
    _FONTS_REGISTERED = True   # don't retry every render; the fallback stack is acceptable


def generate_pdf(html):
    """Render the agreement HTML to PDF bytes via xhtml2pdf (pure-Python, no system
    libs). Raises ``BursaryError('pdf_failed')`` on any failure. This is a mockable
    seam — tests patch it so no real PDF engine runs. The IBM Plex Serif document font is
    registered with reportlab (once) so xhtml2pdf embeds it in the output."""
    try:
        from xhtml2pdf import pisa
        _register_contract_fonts()
        buf = io.BytesIO()
        result = pisa.CreatePDF(io.StringIO(html), dest=buf)
        if result.err:
            raise BursaryError('pdf_failed', 'xhtml2pdf reported errors')
        return buf.getvalue()
    except BursaryError:
        raise
    except Exception as e:  # noqa: BLE001
        raise BursaryError('pdf_failed', str(e))


@transaction.atomic
def sign_agreement(application, *, sponsorship=None, student_signed_name,
                   student_signed_nric='', guarantor_name, guarantor_nric,
                   guarantor_relationship, guarantor_method='in_session',
                   locale='en', ip=None):
    """Create (or update) the binding bursary agreement for an application:

      (a) run the shared guarantor identity gate → BursaryError(code) on mismatch;
      (b) build the particulars from the application + settings;
      (c) render the immutable agreement HTML;
      (d) compute its sha256;
      (e) generate the PDF;
      (f) upload the PDF to the private bucket;
      (g) update_or_create the BursaryAgreement with particulars + student +
          guarantor signatures stamped now.

    Wrapped in a transaction so a failure (e.g. a bad guarantor) rolls everything
    back. The caller (respond_to_award) runs this BEFORE the consent + 'active' flip
    so a BursaryError aborts the whole acceptance. Returns the BursaryAgreement.
    """
    from . import contracts, storage
    from .models import BursaryAgreement

    check = guarantor_identity_check(application, guarantor_name, guarantor_nric)
    if check != 'ok':
        raise BursaryError(check)

    # Same-session parent gate: the guarantor's phone PIN must have been verified, FRESH,
    # in this signing session. No phone on file → block (an admin must capture it) rather
    # than silently skip the gate — "no number" is never a bypass.
    if not guarantor_phone_for(application):
        raise BursaryError('guarantor_phone_missing')
    if not guarantor_phone_verification_fresh(application):
        raise BursaryError('guarantor_phone_unverified')

    # Contract-module cutover: the agreement is rendered from the org's ACTIVE template
    # (or the one already pinned to a prior agreement). Flag-on with no active template is
    # a hard error — never fall back to the hard-coded constants once the org is live.
    # And the student must have passed the comprehension quiz for THIS exact version
    # (comprehension_stale otherwise — the runtime quiz↔contract guard against a redeploy
    # between "Understand" and "Sign").
    template = contracts.template_for_application(application)
    if template is None:
        if getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False):
            raise BursaryError('no_active_template')
    else:
        if application.comprehension_template_id != template.id:
            raise BursaryError('comprehension_stale')
        locale = contracts.resolve_locale(locale, template)

    now = timezone.now()
    version = template.version if template is not None else getattr(
        settings, 'BURSARY_AGREEMENT_VERSION', '2026-v1')
    p = particulars_for(application, template, locale)

    student = {
        'name': student_signed_name,
        'nric': student_signed_nric,
        'signed_at': now,
    }
    guarantor = {
        'name': guarantor_name,
        'nric': guarantor_nric,
        'relationship': guarantor_relationship,
        'signed_at': now,
    }
    foundation = {
        'name': p['foundation_signatory_name'],
        'title': p['foundation_signatory_title'],
        'nric': p['foundation_signatory_nric'],
        'signed_at': None,
    }
    witness = {'by': '', 'org': '', 'signed_at': None}

    html = render_agreement_html(
        application, p, student=student, guarantor=guarantor,
        foundation=foundation, witness=witness, locale=locale, template=template)
    sha = hashlib.sha256(html.encode('utf-8')).hexdigest()

    pdf_bytes = generate_pdf(html)
    # Org-prefixed key (Sprint 4): <org_id>/<app_id>/bursary_agreement_....pdf.
    pdf_path = storage.build_doc_key(
        application, application.id, f'bursary_agreement_{version}_{int(now.timestamp())}.pdf')
    storage.upload_object(pdf_path, pdf_bytes, 'application/pdf')

    agreement, _ = BursaryAgreement.objects.update_or_create(
        application=application,
        defaults={
            'sponsorship': sponsorship,
            'template': template,
            'version': version,
            'locale': _locale(locale),
            'award_amount': p['award_amount'],
            'payment_schedule': p['payment_schedule'],
            'institution_name': p['institution_name'],
            'course_name': p['course_name'],
            'commencement_date': p['commencement_date'],
            'progress_standard': p['progress_standard'],
            'foundation_signatory_name': p['foundation_signatory_name'],
            'foundation_signatory_title': p['foundation_signatory_title'],
            'foundation_signatory_nric': p['foundation_signatory_nric'],
            'student_signed_name': student_signed_name,
            'student_signed_nric': student_signed_nric,
            'student_signed_at': now,
            'student_ip': ip,
            'guarantor_name': guarantor_name,
            'guarantor_nric': guarantor_nric,
            'guarantor_relationship': guarantor_relationship,
            'guarantor_method': guarantor_method,
            'guarantor_signed_at': now,
            'guarantor_ip': ip,
            'rendered_html': html,
            'agreement_sha256': sha,
            'pdf_storage_path': pdf_path,
        },
    )
    return agreement


def _maybe_activate(agreement):
    """Post-award lifecycle: once the agreement is EXECUTED — the three parties (student + guarantor
    + Foundation) have signed — the application moves 'awarded' → 'active' (executed; awaiting first
    payout — S4 flips it to 'maintenance' on the first disbursement). The partner-org witness is
    NON-BLOCKING (an attestation, not a party), so it is not required here. Idempotent; only advances
    from 'awarded', so it never disturbs another state."""
    if not (agreement.student_signed_at and agreement.guarantor_signed_at
            and agreement.foundation_signed_at):
        return
    app = agreement.application
    if app.status == 'awarded':
        app.status = 'active'
        fields = ['status']
        if app.stamp_first('active_at'):
            fields.append('active_at')
        app.save(update_fields=fields)


def countersign_foundation(agreement, *, by_name):
    """Stamp the Foundation's countersignature and re-render/regenerate the PDF so the
    countersignature appears in the artefact. Best-effort on the PDF: a render failure still stamps
    the fields (the signature record is what binds). The Foundation signs LAST, so this normally
    fully executes the agreement → the application moves 'awarded' → 'active' (see _maybe_activate)."""
    now = timezone.now()
    agreement.foundation_signed_by = by_name or agreement.foundation_signatory_name
    agreement.foundation_signed_at = now
    fields = ['foundation_signed_by', 'foundation_signed_at', 'updated_at']
    _regenerate_artefact(agreement, fields)
    agreement.save(update_fields=fields)
    _maybe_activate(agreement)
    # The Foundation signs last → if this executed the agreement (app now 'active'),
    # distribute the signed PDF (student notice + witness/org copies + Drive).
    if agreement.application.status == 'active':
        distribute_executed_agreement(agreement)
    return agreement


def record_witness(agreement, *, org, by_name, witness_name=''):
    """Record the partner organisation's (non-blocking) witness attestation, and
    re-render/regenerate the PDF so the witness block appears. Best-effort PDF."""
    now = timezone.now()
    agreement.witness_org = org
    agreement.witness_signed_by = by_name or ''
    agreement.witness_name = witness_name or ''
    agreement.witness_signed_at = now
    fields = ['witness_org', 'witness_signed_by', 'witness_name', 'witness_signed_at',
              'updated_at']
    _regenerate_artefact(agreement, fields)
    agreement.save(update_fields=fields)
    _maybe_activate(agreement)   # in case the witness is the last of the four to sign
    # Witness done → the Foundation is next in the chain (unless it already signed).
    if agreement.foundation_signed_at is None:
        _notify_foundation_countersign_pending(agreement.application)
    elif agreement.application.status == 'active':
        distribute_executed_agreement(agreement)
    return agreement


def _regenerate_artefact(agreement, fields):
    """Re-render the HTML snapshot (now carrying the latest Foundation/witness
    signatures) + regenerate the PDF. Best-effort: a PDF failure leaves the prior
    artefact in place and never blocks the signature stamp. Mutates ``agreement`` +
    extends ``fields`` in place."""
    application = agreement.application
    p = {
        'award_amount': agreement.award_amount,
        'payment_schedule': agreement.payment_schedule,
        'institution_name': agreement.institution_name,
        'course_name': agreement.course_name,
        'commencement_date': agreement.commencement_date,
        'progress_standard': agreement.progress_standard,
        'foundation_signatory_name': agreement.foundation_signatory_name,
        'foundation_signatory_title': agreement.foundation_signatory_title,
        'foundation_signatory_nric': agreement.foundation_signatory_nric,
    }
    student = {'name': agreement.student_signed_name, 'nric': agreement.student_signed_nric,
               'signed_at': agreement.student_signed_at}
    guarantor = {'name': agreement.guarantor_name, 'nric': agreement.guarantor_nric,
                 'relationship': agreement.guarantor_relationship,
                 'signed_at': agreement.guarantor_signed_at}
    foundation = {'name': agreement.foundation_signed_by or agreement.foundation_signatory_name,
                  'title': agreement.foundation_signatory_title,
                  'nric': agreement.foundation_signatory_nric,
                  'signed_at': agreement.foundation_signed_at}
    witness = {'by': agreement.witness_signed_by,
               'org': agreement.witness_org.name if agreement.witness_org else '',
               'signed_at': agreement.witness_signed_at}
    html = render_agreement_html(
        application, p, student=student, guarantor=guarantor,
        foundation=foundation, witness=witness, locale=agreement.locale,
        template=agreement.template)  # safe: a non-draft template is immutable
    agreement.rendered_html = html
    agreement.agreement_sha256 = hashlib.sha256(html.encode('utf-8')).hexdigest()
    fields.extend(['rendered_html', 'agreement_sha256'])
    try:
        from . import storage
        pdf_bytes = generate_pdf(html)
        storage.upload_object(agreement.pdf_storage_path, pdf_bytes, 'application/pdf')
    except BursaryError:
        pass  # keep the prior PDF; the signature fields still stamp


# ── Signing-chain notifications (best-effort; a mail failure never breaks signing) ──

def _cockpit_link(application):
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    return f'{frontend}/admin/scholarship/{application.id}'


def foundation_notify_emails(application=None):
    """Recipients for a "please countersign" nudge: the governing template's
    ``counterparty_notify_emails`` (when an ``application`` with an active/pinned
    template is given) take precedence; else the ``FOUNDATION_NOTIFY_EMAIL`` override
    (comma-separated) if set, else every active super admin (the people who can
    countersign), else ``ADMIN_NOTIFY_EMAIL``. Returns a de-duplicated list."""
    if application is not None:
        from . import contracts
        template = contracts.template_for_application(application)
        emails = list((template.counterparty_notify_emails or []) if template else [])
        emails = [e for e in (str(x).strip() for x in emails) if e]
        if emails:
            return list(dict.fromkeys(emails))
    env = getattr(settings, 'FOUNDATION_NOTIFY_EMAIL', '') or ''
    explicit = [e.strip() for e in env.split(',') if e.strip()]
    if explicit:
        return list(dict.fromkeys(explicit))
    from django.db.models import Q
    from apps.courses.models import PartnerAdmin
    supers = list(
        PartnerAdmin.objects.filter(is_active=True)
        .filter(Q(role='super') | Q(is_super_admin=True))
        .exclude(email='').values_list('email', flat=True)
    )
    if supers:
        return sorted(set(supers))
    fallback = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    return [fallback] if fallback else []


def _applicant_name(application):
    return getattr(getattr(application, 'profile', None), 'name', '') or ''


def _resolve_witness_org(application):
    """Witness-organisation resolution (go-live transition, 2026-07-19): the admin OVERRIDE on the
    application (``witness_org``) wins, else the student's referring organisation
    (``profile.referred_by_org``), else None — straight to the Foundation countersignature, no
    witness step. Lets an org_admin assign a witness to a SOURCELESS student without inventing a
    referral, and lets one be overridden when the private arrangement differs from the referrer."""
    override = getattr(application, 'witness_org', None)
    if override is not None:
        return override
    profile = getattr(application, 'profile', None)
    return getattr(profile, 'referred_by_org', None)


def notify_after_guarantor_signed(application):
    """Student + guarantor have signed → email the NEXT party in the chain. If a referring
    partner organisation with a contact email exists, ask them to witness (sequenced first);
    otherwise email the Foundation directly to countersign (graceful — no org / no contact
    must never stall the student). Best-effort: any failure is logged, never raised."""
    try:
        from . import emails
        org = _resolve_witness_org(application)
        name = _applicant_name(application)
        link = _cockpit_link(application)
        if org and getattr(org, 'contact_email', ''):
            emails.send_witness_pending_email(
                org.contact_email, contact_person=getattr(org, 'contact_person', ''),
                applicant_name=name, org_name=getattr(org, 'name', ''), link=link)
        else:
            for to in foundation_notify_emails(application):
                emails.send_countersign_pending_email(to, applicant_name=name, link=link)
    except Exception:
        logger.exception('bursary: notify_after_guarantor_signed failed (app %s)',
                         getattr(application, 'id', '?'))


def _notify_foundation_countersign_pending(application):
    """Ask the Foundation to countersign (used after a partner witnesses). Best-effort."""
    try:
        from . import emails
        name = _applicant_name(application)
        link = _cockpit_link(application)
        for to in foundation_notify_emails(application):
            emails.send_countersign_pending_email(to, applicant_name=name, link=link)
    except Exception:
        logger.exception('bursary: countersign-pending notify failed (app %s)',
                         getattr(application, 'id', '?'))


def _student_app_link(application):
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    return f'{frontend}/scholarship/application'


def send_vircle_setup_at_execution(application):
    """Contract-era Vircle bootstrap (go-live transition, 2026-07-19). Once the agreement is fully
    executed, the student needs the Vircle eWallet the bursary is paid through — so send the Vircle
    install email + raise the Action-Centre setup task. In contract mode the award email no longer
    carries Vircle (it's the sign-flavoured variant), so this is where a NEW student is first told.

    GRANDFATHER SKIP + idempotency in one guard: send NOTHING and raise NOTHING when the student
    already has a Vircle setup task (any status — the pre-contract cohort was emailed the merged
    award email, so they already carry one; and a task raised by a prior run of THIS function means
    we already invited them) OR a non-blank ``vircle_id`` (they are already paying through Vircle).
    A student who confirmed has BOTH. Best-effort: a failure never blocks execution, and — because
    the task is raised ONLY on a successful send — a failed send simply retries on the next
    execution-hook pass (the signing-reminder cron re-runs distribution)."""
    from . import vircle
    if vircle.setup_task(application) is not None:
        return   # already invited (grandfather with a task, or a prior run) — idempotent no-op
    if (getattr(application, 'vircle_id', '') or '').strip():
        return   # already paying through Vircle (grandfather, confirmed) — nothing to set up
    try:
        from . import emails
        name = _applicant_name(application)
        lang = getattr(application, 'locale', 'en') or 'en'
        to = (getattr(application, 'notify_email', '') or ''
              or getattr(getattr(application, 'profile', None), 'contact_email', '') or '')
        if emails.send_vircle_install_email(to, name, lang=lang):
            vircle.raise_setup_task(application)
    except Exception:
        logger.exception('bursary: execution-time Vircle setup failed (app %s)',
                         getattr(application, 'id', '?'))


def distribute_executed_agreement(agreement):
    """Execution distribution (Sprint 5): once the agreement is fully executed (→ 'active'),
    email the signed PDF to the STUDENT (their "in effect" notice), the witnessing partner
    contact and the org admins, file the PDF in Google Drive, and (go-live transition) bootstrap
    the student's Vircle eWallet. Best-effort and idempotent via two stamps:
    ``executed_pdf_emailed_at`` (all the emails) and ``drive_file_url`` (Drive), plus the Vircle
    setup-task guard. A re-run (the signing-reminder cron) only fills the missing half. A
    Drive/email/storage failure NEVER blocks execution — the agreement is already executed when
    this runs. The donor is never named. All external seams (storage/email/Drive) are mocked in
    tests."""
    application = agreement.application
    # Fetch the signed PDF once (best-effort). Without it we still send the plain student notice.
    pdf_bytes = None
    if agreement.pdf_storage_path:
        try:
            from . import storage
            pdf_bytes = storage.download_object(agreement.pdf_storage_path)
        except Exception:
            logger.exception('bursary: could not fetch executed PDF (app %s)',
                             getattr(application, 'id', '?'))

    # (A) Emails — one stamp covers the student notice + all copies.
    if agreement.executed_pdf_emailed_at is None:
        student_ok = False
        try:
            from . import emails
            profile = getattr(application, 'profile', None)
            name = _applicant_name(application)
            cp = getattr(application, 'chosen_programme', None) or {}
            programme = cp.get('course_name', '') if isinstance(cp, dict) else ''
            lang = getattr(application, 'locale', 'en') or 'en'
            student_to = (getattr(application, 'notify_email', '') or ''
                          or getattr(profile, 'contact_email', '') or '')
            student_ok = emails.send_agreement_executed_email(
                student_to, name, programme, lang=lang,
                link=_student_app_link(application), pdf=pdf_bytes)
            # Witnessing partner contact: the recorded witness org (who actually attested), else
            # the resolved witness (override -> referral -> none) for the copy.
            org = agreement.witness_org or _resolve_witness_org(application)
            witness_email = getattr(org, 'contact_email', '') if org else ''
            cockpit = _cockpit_link(application)
            if witness_email:
                emails.send_executed_copy_email(
                    witness_email, applicant_name=name, programme_name=programme,
                    pdf=pdf_bytes, link=cockpit)
            # Org admins (template counterparty_notify_emails → supers → ADMIN_NOTIFY_EMAIL).
            for to in foundation_notify_emails(application):
                emails.send_executed_copy_email(
                    to, applicant_name=name, programme_name=programme, pdf=pdf_bytes, link=cockpit)
        except Exception:
            logger.exception('bursary: executed distribution emails failed (app %s)',
                             getattr(application, 'id', '?'))
        if student_ok:
            agreement.executed_pdf_emailed_at = timezone.now()
            agreement.save(update_fields=['executed_pdf_emailed_at', 'updated_at'])

    # (B) Drive — idempotent on drive_file_url.
    if not agreement.drive_file_url and pdf_bytes:
        try:
            from . import sheets
            url = sheets.write_contract_pdf(agreement, pdf_bytes)
            if url:
                agreement.drive_file_url = url
                agreement.save(update_fields=['drive_file_url', 'updated_at'])
        except Exception:
            logger.exception('bursary: executed Drive upload failed (app %s)',
                             getattr(application, 'id', '?'))

    # (C) Vircle eWallet bootstrap (go-live transition) — idempotent + grandfather-skipping.
    # Rides the same execution seam so the signing-reminder cron's distribution retry re-attempts
    # a failed Vircle send too.
    send_vircle_setup_at_execution(application)


def send_signing_reminders(now=None):
    """SLA cron: nudge the party whose signature is still pending on a binding-but-not-yet-
    executed agreement — the partner (witness) first if a referring org with a contact email
    exists, else the Foundation (countersign). Re-nudges no more often than
    ``BURSARY_SIGN_REMINDER_DAYS``. Best-effort; returns a summary. No-op when the feature is
    off. Idempotent within the interval via the ``*_reminded_at`` stamps."""
    summary = {'witness': 0, 'countersign': 0}
    if not getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False):
        return summary
    from datetime import timedelta
    from . import emails
    from .models import BursaryAgreement
    now = now or timezone.now()
    interval = timedelta(days=getattr(settings, 'BURSARY_SIGN_REMINDER_DAYS', 3))
    qs = (BursaryAgreement.objects
          .filter(guarantor_signed_at__isnull=False, foundation_signed_at__isnull=True)
          .select_related('application', 'application__profile', 'application__witness_org',
                          'witness_org'))
    for ag in qs:
        app = ag.application
        if getattr(app, 'status', '') != 'awarded':
            continue   # only a still-pending (not declined/active) agreement is nudged
        org = _resolve_witness_org(app)
        name = _applicant_name(app)
        link = _cockpit_link(app)
        witness_pending = bool(org and getattr(org, 'contact_email', '')
                               and ag.witness_signed_at is None)
        if witness_pending:
            since = max(ag.guarantor_signed_at, ag.witness_reminded_at or ag.guarantor_signed_at)
            if now - since < interval:
                continue
            if emails.send_witness_pending_email(
                    org.contact_email, contact_person=getattr(org, 'contact_person', ''),
                    applicant_name=name, org_name=getattr(org, 'name', ''), link=link):
                ag.witness_reminded_at = now
                ag.save(update_fields=['witness_reminded_at', 'updated_at'])
                summary['witness'] += 1
        else:
            since = max(ag.guarantor_signed_at,
                        ag.countersign_reminded_at or ag.guarantor_signed_at)
            if now - since < interval:
                continue
            any_sent = False
            for to in foundation_notify_emails(app):
                any_sent = emails.send_countersign_pending_email(
                    to, applicant_name=name, link=link) or any_sent
            if any_sent:
                ag.countersign_reminded_at = now
                ag.save(update_fields=['countersign_reminded_at', 'updated_at'])
                summary['countersign'] += 1

    # Distribution retry pass (Sprint 5): an EXECUTED agreement whose best-effort distribution
    # didn't fully complete (a Drive/email/storage hiccup at execution) is retried here.
    # distribute_executed_agreement is idempotent — it only fills the missing stamp.
    from django.db.models import Q
    summary['distributed'] = 0
    executed = (BursaryAgreement.objects
                .filter(foundation_signed_at__isnull=False)
                .filter(Q(executed_pdf_emailed_at__isnull=True) | Q(drive_file_url=''))
                .select_related('application', 'application__profile', 'witness_org'))
    for ag in executed:
        if getattr(ag.application, 'status', '') != 'active':
            continue   # only a fully-executed (active) agreement is distributed
        before = (ag.executed_pdf_emailed_at, ag.drive_file_url)
        distribute_executed_agreement(ag)
        if (ag.executed_pdf_emailed_at, ag.drive_file_url) != before:
            summary['distributed'] += 1
    return summary
