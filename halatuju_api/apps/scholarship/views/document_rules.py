"""Which document types get which treatment on upload, and the upload-format rule."""
import logging

from ..models import ApplicantDocument

logger = logging.getLogger(__name__)


# Supporting docs that get a soft name-presence check on upload (the income docs,
# results slip, offer letter, and utility bills). Utility bills additionally get a
# soft home-address check. IC / parent_ic use the dedicated MyKad pipeline instead.
BILL_DOC_TYPES = frozenset({'water_bill', 'electricity_bill'})


# Reviewer / "other" documents that BYPASS the stage-judge-promote flow (owner 2026-07-09): the
# reviewer asked for them and will eyeball them, so we accept whatever is uploaded — no genuineness
# gate, no keep-better, no staging. They coexist in their own slots via ``request_code``. Every
# other (KEY NAMED) doc type goes through the staging path (see ``DocumentListCreateView.post``).
_BYPASS_JUDGE_TYPES = frozenset({'bank_statement', 'income_support_doc', 'other'})


# Income relationship-proof docs whose VERDICT depends on the Gemini-extracted structured
# fields (e.g. a birth certificate's child/mother names, or a guardianship letter's
# guardian/ward names), so they must ALWAYS field-extract — never gated by the "only when
# uncertain" cost knob, and never skipped at upload. (V1: guardianship_letter joined here —
# its schema + verdict + resolution branch already existed but were never fed because the
# upload never triggered its extraction; a genuine limb of the pipeline was dead.)
RELATIONSHIP_DOC_TYPES = frozenset({'birth_certificate', 'guardianship_letter'})


def _reslot_income_doc(doc, ocr) -> bool:
    """An EPF statement uploaded into the salary-slip slot is FILED AS AN EPF. Returns True if the
    document was moved. (Owner, 2026-07-14 — #126.)

    Why this exists: the income-proof request offers "salary slip OR EPF (KWSP) statement" but owns
    a single `salary_slip` slot, and the Action Centre uploads into the item's doc_type. An EPF put
    there scored `not_salary`, failed `usable_salary_slip()`, never cleared the request, and looped
    the student into the circuit-breaker — we invited a document and then refused it.

    The engine already treats EITHER document as income evidence for that member
    (`income_engine._parent_has_income_evidence`), so once the doc sits in the right slot the gap
    clears, the evidence counts, and the EPF request that would have followed a payslip is moot.
    Only the SLOT was wrong.

    Deliberately one-directional and deterministic: we move salary_slip → epf ONLY when the
    label-anchored KWSP parser (`doc_parse`) positively recognises the statement. A real payslip
    matches no EPF labels, so a genuine slip is never moved; an unreadable scan is never moved
    (parse returns None → left alone → the normal not_salary/coach path). We do NOT try the reverse
    (epf → salary_slip): nothing asks for an EPF and offers a payslip, so there is no trap there.
    """
    if doc.doc_type != 'salary_slip':
        return False
    text = (ocr or {}).get('text', '') if isinstance(ocr, dict) else ''
    if not (text or '').strip():
        return False
    from ..doc_parse import parse_by_labels
    if parse_by_labels('epf', text) is None:
        return False   # not recognisably a KWSP statement — leave it where the student put it
    doc.doc_type = 'epf'
    doc.save(update_fields=['doc_type'])
    logger.info('AUDIT reslot app=%s doc=%s salary_slip → epf (KWSP statement in the payslip slot)',
                doc.application_id, doc.id)
    return True


# Academic-completeness docs that are single-per-person: exactly ONE live copy per member should
# exist, so a duplicate across request-code slots is collapsed (see _collapse_duplicate_docs).
_ACADEMIC_SINGLE_TYPES = frozenset({'school_leaving_cert', 'semester_result', 'higher_results'})


def _collapse_duplicate_docs(app, doc_type, member) -> None:
    """Collapse duplicate LIVE copies of a single-per-person academic doc to ONE (owner 2026-07-15).

    A ``school_leaving_cert`` / ``semester_result`` is one document per person, but an officer can
    request it more than once — and each ResolutionItem opens its OWN ``request_code`` slot, so the
    stage-judge-promote supersede (scoped to the slot) leaves two live copies (app #66: the same cert
    live under ``officer_1`` AND ``officer_9``). Keep the best copy by the shared keep-better quality
    axis (``promotion.doc_quality`` — a genuine cert outranks a suspect / wrong-type one, newest
    breaks a tie) and supersede the rest into Old / Replaced (retained, never hard-deleted).
    Idempotent + best-effort; never raises into the upload path."""
    from django.utils import timezone as _tz
    from .. import promotion
    live = list(ApplicantDocument.objects.filter(
        application=app, doc_type=doc_type, household_member=member or '',
        superseded_at__isnull=True))
    if len(live) < 2:
        return
    keeper = max(live, key=lambda d: (promotion.doc_quality(d) or (), getattr(d, 'id', 0) or 0))
    losers = [d.id for d in live if d.id != keeper.id]
    if losers:
        ApplicantDocument.objects.filter(id__in=losers).update(
            superseded_at=_tz.now(), superseded_by=keeper)
        logger.info('AUDIT collapse_duplicate app=%s doc_type=%s member=%r kept=%s superseded=%s',
                    app.id, doc_type, member, keeper.id, losers)


SUPPORTING_NAME_CHECK_TYPES = frozenset({
    'results_slip', 'str', 'salary_slip', 'epf', 'offer_letter',
    # Post-award: the bank statement field-extracts (bank name / account no / holder) so
    # the student's confirm form pre-fills and Gopal can coach a weak read.
    'bank_statement',
    # V1: the declared-informal-income supporting doc (employer/wage letter, bank statements,
    # community/penghulu letter). It must be READ — mere presence used to clear the declared-
    # income gap, so a blank image "proved" a wage. Now it field-extracts on upload and the
    # gap only clears on a real read (see income_engine.has_income_support_doc).
    'income_support_doc',
    # V4: the promoted academic-completeness docs — field-extract the CGPA / school on upload so
    # the officer sees the read and a blank upload is held (see resolution.doc_match_verdict).
    'school_leaving_cert', 'semester_result', 'higher_results',   # + third route S3b
} | BILL_DOC_TYPES | RELATIONSHIP_DOC_TYPES)


# Free-text docs (the letter of intent) that get OCR'd into vision_fields['text'] so
# Check-2's submission review can read the student's motivation in her own words. No
# name/address check, no field extraction — just the plain text. Soft, never blocks.
TEXT_READ_DOC_TYPES = frozenset({'statement_of_intent'})


# Accepted upload formats: images (phone photos) + PDF (scan-to-PDF / digital docs
# like EPF & payslips). Everything else (video, etc.) is rejected. Before this
# there was NO format check — that's how a .mp4 IC got through (TD-080).
_ALLOWED_UPLOAD_EXTENSIONS = frozenset({
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.heic', '.heif',
})


def _is_allowed_upload(content_type, filename):
    """True iff the upload is an image or a PDF (by MIME type or file extension)."""
    ct = (content_type or '').lower().split(';')[0].strip()
    if ct.startswith('image/') or ct == 'application/pdf':
        return True
    import os
    return os.path.splitext(filename or '')[1].lower() in _ALLOWED_UPLOAD_EXTENSIONS
