"""Re-run a document's automatic read — the shared core of the cockpit's per-doc
'Re-run' (AdminRunVisionView) and the bulk `reextract_documents` command, so the two
can't drift. Mirrors the upload-time processing per doc type and FORCES the (billable)
read (no cost-knob / throttle gate — it's a deliberate action). Best-effort on the
offer-letter pathway autofill (never fails the read)."""
import logging

from . import vision as _vision

logger = logging.getLogger(__name__)


#: TD-407: the flag a re-read command needs to run without genuineness on purpose.
ALLOW_WITHOUT_GENUINENESS = '--allow-without-genuineness'


def add_preflight_argument(parser):
    parser.add_argument(ALLOW_WITHOUT_GENUINENESS, action='store_true',
                        help='Run although DOC_GENUINENESS_CHECK_ENABLED is off (TD-407). The re-read '
                             'keeps each stored genuineness score; it scores nothing new.')


def reread_preflight(command, opts, *, refuse=True):
    """TD-407 pre-flight for a command that re-reads documents in bulk. A Cloud Run JOB carries only
    core env, so the same command that is safe inside the service can run there without the service's
    flags (corpus C4). REFUSES to start (``CommandError`` → non-zero exit) when
    ``DOC_GENUINENESS_CHECK_ENABLED`` is off, unless ``--allow-without-genuineness`` says it is meant:
    the read would score nothing (the stored score is kept since TD-407, but nothing new is learnt).
    ``refuse=False`` (the HOURLY self-heal, `reprocess_unread_ic`, TD-407 review) only WARNS — log and
    stdout — and runs: the cron endpoint swallows a raised error as a warning and a 200, so a refusal
    would stop the AI-outage self-heal quietly, while a flag-off re-read is already safe (scores kept).
    Only WARNS when ``BILLING_USAGE_ENABLED`` is off: the reads are then correct but not attributed to
    an organisation's bill — a reconciliation gap the lead can see, not a data loss, and refusing would
    block every environment where billing is deliberately off."""
    from django.conf import settings
    from django.core.management.base import CommandError
    if not getattr(settings, 'BILLING_USAGE_ENABLED', False):
        command.stderr.write('reread: BILLING_USAGE_ENABLED is off — these paid reads will not be metered '
                             'to an organisation (set BILLING_USAGE_ENABLED=true on a job).')
    if getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False) or opts.get('allow_without_genuineness'):
        return
    if not refuse:
        msg = ('reread: DOC_GENUINENESS_CHECK_ENABLED is off — re-reading anyway (TD-407: stored scores are '
               "kept, nothing new is scored); set it to exactly '1' on the service.")
        logger.warning(msg)
        command.stdout.write(msg)
        return
    raise CommandError('reread: DOC_GENUINENESS_CHECK_ENABLED is off, so this re-read would score no '
                       "document's genuineness (TD-407). Set DOC_GENUINENESS_CHECK_ENABLED=1 (exactly '1') "
                       f'on the job, as on the halatuju-api service, or pass {ALLOW_WITHOUT_GENUINENESS}.')


def reextract_document(doc) -> bool:
    """Re-run the automatic read for one document, dispatched by type. Returns True when a
    known read ran, False for a type with no automatic check (caller decides what to do)."""
    from .views import BILL_DOC_TYPES, SUPPORTING_NAME_CHECK_TYPES, TEXT_READ_DOC_TYPES
    app = doc.application
    if doc.doc_type in ('ic', 'parent_ic'):
        _vision.run_vision_for_document(doc)               # MyKad OCR → vision_nric/name columns
    elif doc.doc_type in TEXT_READ_DOC_TYPES:
        _vision.read_text_document(doc)                    # letter of intent → vision_fields['text']
    elif doc.doc_type in SUPPORTING_NAME_CHECK_TYPES:
        profile = getattr(app, 'profile', None)
        names = _vision.reference_names(app)   # student + guardians + roster parents (#126)
        postcode = getattr(profile, 'postal_code', '') or ''
        city = getattr(profile, 'city', '') or ''
        # Code-health S2 #5c: the upload path passes the street line too — omitting it here
        # put the matcher in locality-only mode, so a re-run could flip a bill that matched
        # at upload (house number + street) to 'mismatch' on identical data.
        street = getattr(profile, 'address', '') or ''
        check_address = doc.doc_type in BILL_DOC_TYPES
        ocr = _vision.ocr_document_full(doc)               # ONE fetch + ONE Vision call, shared
        _vision.run_vision_match_for_document(
            doc, names=names, postcode=postcode, city=city, street=street,
            check_address=check_address, ocr=ocr)
        if doc.doc_type in _vision.GEMINI_EXTRACT_DOC_TYPES:
            _vision.run_field_extraction_for_document(
                doc, names=names, postcode=postcode, city=city, street=street,
                check_address=check_address, ocr=ocr)
        if doc.doc_type == 'offer_letter':
            try:
                from .services import autofill_pathway_from_offer
                autofill_pathway_from_offer(app)
            except Exception:
                logger.warning('autofill_pathway_from_offer failed for app %s', app.id, exc_info=True)
    else:
        return False
    return True
