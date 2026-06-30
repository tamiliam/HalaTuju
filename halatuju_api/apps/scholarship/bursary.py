"""Conditional Bursary Award Agreement — the binding bursary CONTRACT a student
signs (with a parent/guardian as surety/guarantor) when they accept a sponsor's
award.

Parties: the STUDENT (primary), the PARENT/GUARDIAN (surety/guarantor), the
FOUNDATION (counterparty — signatory from settings) and the PARTNER ORGANISATION
(non-blocking witness). The DONOR is NEVER a party and is never named — anonymity
is sacred. The contract names the FOUNDATION only.

This module is the deterministic core: the agreement TEMPLATE (EN + BM), the
particulars builder, the immutable HTML render, the shared guarantor-identity
gate (extracted from the consent view), the xhtml2pdf render, and the
``sign_agreement`` / ``countersign_foundation`` / ``record_witness`` writers.

DRAFT: the clause wording below is pending legal review — the rendered document
carries a "DRAFT — pending legal review" banner and the whole feature ships
behind ``BURSARY_AGREEMENT_ENABLED`` (default OFF).
"""
import hashlib
import io
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .vision import name_match, nric_match


class BursaryError(Exception):
    """Raised by the bursary writers with a machine-readable ``.code`` so the
    acceptance flow / the view can surface it as a 400 with that code."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


# ── The agreement clauses (EN + BM). DRAFT — lawyer to finalise. ──────────────
# Each clause is framed as SUPPORT, not a punitive contract: the bursary is a gift
# (not repayable except on fraud/misuse), academic progress is a REVIEW (not auto-
# suspension), and seminars are reframed to "Foundation/programme activities". We
# DROP any criminal-record / "good standing in public" clause and any "the
# Foundation may change your obligations at any time" clause. The FOUNDATION is the
# named counterparty — the donor is never mentioned.
AGREEMENT_TITLE = {
    'en': 'Conditional Bursary Award Agreement',
    'ms': 'Perjanjian Pemberian Biasiswa Bersyarat',
}

# Recitals / preamble, interpolated with party + particulars at render time.
AGREEMENT_PREAMBLE = {
    'en': (
        'This Agreement records the terms on which the Foundation awards a bursary to '
        'the Student named below, with the Student’s parent or guardian signing as '
        'surety/guarantor. It is made between the Foundation (the counterparty), the '
        'Student, and the Guarantor, and witnessed by the Student’s referring '
        'partner organisation.'
    ),
    'ms': (
        'Perjanjian ini merekodkan terma-terma pemberian biasiswa oleh Yayasan kepada '
        'Pelajar yang dinamakan di bawah, dengan ibu bapa atau penjaga Pelajar '
        'menandatangani sebagai penjamin. Ia dibuat antara Yayasan (pihak rakan kontrak), '
        'Pelajar, dan Penjamin, serta disaksikan oleh organisasi rakan kongsi yang merujuk '
        'Pelajar.'
    ),
}

# The numbered clauses. List of (heading, body) tuples.
AGREEMENT_CLAUSES = {
    'en': [
        ('The Bursary Award',
         'The Foundation agrees to award the Student a bursary of the amount stated in the '
         'Particulars, to be applied in good faith towards the approved expenses of the '
         'Student’s studies (such as fees, learning materials and reasonable living '
         'costs). The bursary is to be used for its stated purpose; it is not subject to '
         'clawback for ordinary, good-faith use.'),
        ('Payment Schedule',
         'The bursary will be paid according to the payment schedule stated in the '
         'Particulars. The Foundation may make reasonable administrative adjustments to '
         'timing, communicated to the Student in advance.'),
        ('Evidence of Results, Income and Eligibility',
         'The Student agrees to provide, when reasonably requested, evidence of academic '
         'results, household income, and continued eligibility (for example STR or other '
         'supporting documents), so the Foundation can administer the bursary responsibly.'),
        ('Enrolment at a Government Institution',
         'The Student confirms they are, or will be, enrolled at a recognised government '
         'institution of higher learning for the course stated in the Particulars.'),
        ('Remaining Enrolled',
         'The Student agrees to remain enrolled in their course of study for the duration '
         'of the bursary, and to inform the Foundation promptly if they intend to defer, '
         'change or withdraw from the course.'),
        ('Academic Progress (Review, not Automatic Suspension)',
         'The Student agrees to work towards satisfactory academic progress, as described '
         'in the Particulars. Where progress falls short, the Foundation will REVIEW the '
         'situation with the Student supportively; the bursary is not automatically '
         'suspended.'),
        ('Notifying the Foundation of Changes',
         'The Student agrees to notify the Foundation of any material change in their '
         'circumstances — institution, course, contact details, or household '
         'situation — within a reasonable time.'),
        ('Good Standing in School',
         'The Student agrees to maintain good standing at their institution and to conduct '
         'themselves honestly and responsibly as a member of its community.'),
        ('Communication with the Assigned Mentor',
         'The Student agrees to maintain reasonable communication with the mentor assigned '
         'to them, and to take part in Foundation or programme activities where invited.'),
        ('Suspension or Withholding of Future Support',
         'The Foundation may suspend or withhold future support where the Student fails to '
         'comply with this Agreement, provides false information, or misuses the bursary. '
         'The Foundation will give the Student a fair opportunity to respond first.'),
        ('The Bursary is a Gift',
         'The bursary is a gift and is NOT repayable, except where it was obtained by fraud '
         'or has been misused, in which case the Foundation may require repayment of the '
         'affected amount.'),
        ('Confidentiality',
         'The parties will keep each other’s personal and programme information '
         'confidential, and use it only to administer the bursary.'),
        ('No Employment Relationship',
         'Nothing in this Agreement creates an employment, agency or partnership '
         'relationship between the Student, the Guarantor and the Foundation.'),
        ('Governing Law and Dispute Resolution',
         'This Agreement is governed by the laws of Malaysia. The parties will first seek '
         'to resolve any dispute through good-faith discussion, and then through mediation, '
         'before any other step.'),
        ('Term and Termination',
         'This Agreement takes effect on signing and continues for the duration of the '
         'bursary. It may be ended by agreement of the parties, or by the Foundation in '
         'accordance with the clauses above.'),
        ('Entire Agreement and Amendment',
         'This Agreement is the entire agreement between the parties on its subject matter. '
         'Any amendment must be in writing and agreed by the parties.'),
    ],
    'ms': [
        ('Pemberian Biasiswa',
         'Yayasan bersetuju memberi Pelajar biasiswa sebanyak amaun yang dinyatakan dalam '
         'Butiran, untuk digunakan dengan suci hati bagi perbelanjaan yang diluluskan untuk '
         'pengajian Pelajar (seperti yuran, bahan pembelajaran dan kos sara hidup yang '
         'munasabah). Biasiswa hendaklah digunakan untuk tujuan yang dinyatakan; ia tidak '
         'tertakluk kepada tuntutan balik bagi penggunaan biasa dengan suci hati.'),
        ('Jadual Pembayaran',
         'Biasiswa akan dibayar mengikut jadual pembayaran yang dinyatakan dalam Butiran. '
         'Yayasan boleh membuat pelarasan pentadbiran yang munasabah terhadap masa '
         'pembayaran, dengan memaklumkan Pelajar terlebih dahulu.'),
        ('Bukti Keputusan, Pendapatan dan Kelayakan',
         'Pelajar bersetuju memberikan, apabila diminta dengan munasabah, bukti keputusan '
         'akademik, pendapatan isi rumah, dan kelayakan berterusan (contohnya STR atau '
         'dokumen sokongan lain), supaya Yayasan dapat mentadbir biasiswa dengan '
         'bertanggungjawab.'),
        ('Pendaftaran di Institusi Kerajaan',
         'Pelajar mengesahkan bahawa mereka sedang, atau akan, mendaftar di institusi '
         'pengajian tinggi kerajaan yang diiktiraf untuk kursus yang dinyatakan dalam '
         'Butiran.'),
        ('Kekal Mendaftar',
         'Pelajar bersetuju untuk kekal mendaftar dalam kursus pengajian mereka sepanjang '
         'tempoh biasiswa, dan memberitahu Yayasan dengan segera jika mereka berhasrat '
         'untuk menangguh, menukar atau menarik diri daripada kursus.'),
        ('Kemajuan Akademik (Semakan, Bukan Penggantungan Automatik)',
         'Pelajar bersetuju berusaha ke arah kemajuan akademik yang memuaskan, seperti yang '
         'diterangkan dalam Butiran. Jika kemajuan kurang memuaskan, Yayasan akan MENYEMAK '
         'keadaan bersama Pelajar secara menyokong; biasiswa tidak digantung secara '
         'automatik.'),
        ('Memaklumkan Yayasan tentang Perubahan',
         'Pelajar bersetuju memaklumkan Yayasan tentang sebarang perubahan penting dalam '
         'keadaan mereka — institusi, kursus, butiran perhubungan, atau keadaan isi '
         'rumah — dalam masa yang munasabah.'),
        ('Tatakelakuan Baik di Sekolah',
         'Pelajar bersetuju mengekalkan tatakelakuan baik di institusi mereka dan bertindak '
         'dengan jujur dan bertanggungjawab sebagai ahli komunitinya.'),
        ('Komunikasi dengan Mentor yang Ditugaskan',
         'Pelajar bersetuju mengekalkan komunikasi yang munasabah dengan mentor yang '
         'ditugaskan kepada mereka, dan menyertai aktiviti Yayasan atau program apabila '
         'dijemput.'),
        ('Penggantungan atau Penahanan Sokongan Masa Hadapan',
         'Yayasan boleh menggantung atau menahan sokongan masa hadapan jika Pelajar gagal '
         'mematuhi Perjanjian ini, memberikan maklumat palsu, atau menyalahgunakan '
         'biasiswa. Yayasan akan memberi Pelajar peluang yang adil untuk menjawab '
         'terlebih dahulu.'),
        ('Biasiswa adalah Pemberian',
         'Biasiswa adalah pemberian dan TIDAK perlu dibayar balik, kecuali jika ia '
         'diperoleh melalui penipuan atau disalahgunakan, di mana Yayasan boleh menuntut '
         'pembayaran balik amaun yang terjejas.'),
        ('Kerahsiaan',
         'Pihak-pihak akan merahsiakan maklumat peribadi dan program antara satu sama lain, '
         'dan menggunakannya hanya untuk mentadbir biasiswa.'),
        ('Tiada Hubungan Pekerjaan',
         'Tiada apa-apa dalam Perjanjian ini mewujudkan hubungan pekerjaan, agensi atau '
         'perkongsian antara Pelajar, Penjamin dan Yayasan.'),
        ('Undang-undang dan Penyelesaian Pertikaian',
         'Perjanjian ini ditadbir oleh undang-undang Malaysia. Pihak-pihak akan terlebih '
         'dahulu cuba menyelesaikan sebarang pertikaian melalui perbincangan dengan suci '
         'hati, dan kemudian melalui pengantaraan, sebelum sebarang langkah lain.'),
        ('Tempoh dan Penamatan',
         'Perjanjian ini berkuat kuasa apabila ditandatangani dan berterusan sepanjang '
         'tempoh biasiswa. Ia boleh ditamatkan melalui persetujuan pihak-pihak, atau oleh '
         'Yayasan menurut klausa di atas.'),
        ('Keseluruhan Perjanjian dan Pindaan',
         'Perjanjian ini adalah keseluruhan perjanjian antara pihak-pihak mengenai '
         'perkaranya. Sebarang pindaan mestilah secara bertulis dan dipersetujui oleh '
         'pihak-pihak.'),
    ],
}

DRAFT_BANNER = {
    'en': 'DRAFT — pending legal review',
    'ms': 'DERAF — menunggu semakan undang-undang',
}

DEFAULT_PAYMENT_SCHEDULE = 'RM500 one-time then RM250/month for 10 months'
DEFAULT_PROGRESS_STANDARD = 'Maintain satisfactory academic progress as reviewed each semester'


def _locale(locale):
    """Normalise to a template locale ('en' or 'ms'). 'ta'/unknown → 'en'."""
    return 'ms' if (locale or '').startswith('ms') else 'en'


def particulars_for(application):
    """Build the filled-in particulars dict for an application. Reads the award
    amount + chosen programme off the application and the Foundation signatory off
    settings. NEVER reads or exposes any donor identity."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    institution = (cp.get('institution') or '').strip()
    course = (cp.get('course_name') or '').strip()
    if not course:
        course = (getattr(application, 'field_of_study', '') or '').strip()
    return {
        'award_amount': application.award_amount,
        'payment_schedule': DEFAULT_PAYMENT_SCHEDULE,
        'institution_name': institution,
        'course_name': course,
        'commencement_date': None,
        'progress_standard': DEFAULT_PROGRESS_STANDARD,
        'foundation_signatory_name': getattr(settings, 'FOUNDATION_SIGNATORY_NAME', 'Suresh'),
        'foundation_signatory_title': getattr(
            settings, 'FOUNDATION_SIGNATORY_TITLE',
            'For and on behalf of the Foundation (interim signatory)'),
        'foundation_signatory_nric': getattr(settings, 'FOUNDATION_SIGNATORY_NRIC', '') or '',
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


def render_agreement_html(application, particulars, *, student, guarantor,
                          foundation, witness, locale='en'):
    """Render the full, self-contained agreement HTML (inline CSS only — xhtml2pdf
    has limited CSS support). This is the immutable snapshot stored on the record.

    ``student`` / ``guarantor`` / ``foundation`` / ``witness`` are dicts with the
    party's name (+ nric/role/timestamp where applicable). The donor is NEVER
    rendered — there is no donor field anywhere in this document."""
    lang = _locale(locale)
    title = AGREEMENT_TITLE[lang]
    banner = DRAFT_BANNER[lang]
    preamble = AGREEMENT_PREAMBLE[lang]
    clauses = AGREEMENT_CLAUSES[lang]

    parts = [
        '<html><head><meta charset="utf-8"/></head>',
        '<body style="font-family: Helvetica, Arial, sans-serif; font-size: 11px; '
        'color: #222; line-height: 1.4;">',
        # DRAFT banner
        '<div style="background:#fde68a; border:1px solid #d97706; color:#92400e; '
        'padding:6px 10px; text-align:center; font-weight:bold; margin-bottom:12px;">'
        f'{_esc(banner)}</div>',
        f'<h1 style="font-size:18px; text-align:center; margin:0 0 4px 0;">{_esc(title)}</h1>',
    ]
    if lang == 'en':
        parts.append('<p style="text-align:center; font-size:9px; color:#666; margin:0 0 12px 0;">'
                     'Perjanjian Pemberian Biasiswa Bersyarat</p>')
    parts.append(f'<p>{_esc(preamble)}</p>')

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

    # Clauses.
    parts.append('<h2 style="font-size:13px; margin:16px 0 6px 0;">Terms / Terma</h2>')
    parts.append('<ol style="padding-left:18px;">')
    for heading, body in clauses:
        parts.append(
            f'<li style="margin-bottom:8px;"><b>{_esc(heading)}.</b> {_esc(body)}</li>')
    parts.append('</ol>')

    # Signature blocks.
    parts.append('<h2 style="font-size:13px; margin:16px 0 6px 0;">Signatures / Tandatangan</h2>')
    parts.append('<table style="width:100%; border-collapse:collapse;">')
    parts.append('<tr>')
    parts.append(_signature_block(
        'Student / Pelajar', name=student.get('name', ''), nric=student.get('nric', ''),
        signed_at=student.get('signed_at')))
    parts.append(_signature_block(
        'Guarantor / Penjamin (surety)', name=guarantor.get('name', ''),
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

    parts.append(f'<p style="margin-top:14px; font-size:9px; color:#666;">{_esc(banner)} '
                 f'— version {_esc(getattr(settings, "BURSARY_AGREEMENT_VERSION", ""))}.</p>')
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
    present_qs = application.documents.all()
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


def generate_pdf(html):
    """Render the agreement HTML to PDF bytes via xhtml2pdf (pure-Python, no system
    libs). Raises ``BursaryError('pdf_failed')`` on any failure. This is a mockable
    seam — tests patch it so no real PDF engine runs."""
    try:
        from xhtml2pdf import pisa
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
    from . import storage
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

    now = timezone.now()
    version = getattr(settings, 'BURSARY_AGREEMENT_VERSION', '2026-v1')
    p = particulars_for(application)

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
        foundation=foundation, witness=witness, locale=locale)
    sha = hashlib.sha256(html.encode('utf-8')).hexdigest()

    pdf_bytes = generate_pdf(html)
    pdf_path = f'{application.id}/bursary_agreement_{version}_{int(now.timestamp())}.pdf'
    storage.upload_object(pdf_path, pdf_bytes, 'application/pdf')

    agreement, _ = BursaryAgreement.objects.update_or_create(
        application=application,
        defaults={
            'sponsorship': sponsorship,
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
        app.save(update_fields=['status'])


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
        foundation=foundation, witness=witness, locale=agreement.locale)
    agreement.rendered_html = html
    agreement.agreement_sha256 = hashlib.sha256(html.encode('utf-8')).hexdigest()
    fields.extend(['rendered_html', 'agreement_sha256'])
    try:
        from . import storage
        pdf_bytes = generate_pdf(html)
        storage.upload_object(agreement.pdf_storage_path, pdf_bytes, 'application/pdf')
    except BursaryError:
        pass  # keep the prior PDF; the signature fields still stamp
