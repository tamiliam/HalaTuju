"""TD-114 — count (and, where it is free, score) the live anchor documents never scored for genuineness.

Since VERDICT_ENGINE_VERSION 2026-10-02.1 a never-scored IC, results slip or offer letter holds its
fact at Probable (`verdict_ladder._genuineness_unscored`), so every such document is a fact that can
no longer read Certain until it is scored. This command answers "how many?" and scores the ones it
can WITHOUT a paid call. DRY-RUN BY DEFAULT: nothing is written unless `--apply` is given.

    python manage.py rescore_unscored_documents            # count only
    python manage.py rescore_unscored_documents --apply    # also write what it can score free

⚠ WHAT "FREE" CAN REACH, read from the code on 2026-10-02:
  - **ic** — the IC scorer (`genuineness/ic.py`) is a Gemini MULTIMODAL read; there is no local
    model. Every unscored IC is counted as needing a paid read and never touched here.
  - **offer_letter** — scored on the live path by the LOCAL signature model over OCR text alone
    (`genuineness.assess('offer_letter')` ignores the image), so stored text re-scores it exactly.
  - **results_slip** — the live path adds two VISUAL signatures (QR + crest, weights 3 + 2) from a
    Gemini read. Text alone is therefore scored TWICE, with both visuals absent and both present,
    and a status is written only when the two agree — the visuals could not have changed it. When
    they disagree the document is counted `indeterminate` and left alone.
  - **The OCR text is not stored** for these three types today (only free-text documents keep
    `vision_fields['text']`), so on today's data every document lands in `no_stored_text`. Scoring
    those needs a fresh OCR read: `reextract_documents --doc-type <type> --pass-marker <new name>`
    (billable Vision + Gemini) — the owner's call, not this command's.

Two counts per type (review F4c): `unscored` is every live never-scored row; `unscored_latest` is
the never-scored rows that are the LATEST live document of their type on their application — the
one the verdict reads (`latest_doc`), so it is the number of facts that can no longer read Certain.

Never overwrites an existing genuineness verdict and never clears anything, so a run without
Storage or text access (a local checkout) cannot damage a row.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scholarship.genuineness import assess, signature_genuineness
from apps.scholarship.genuineness.bands import canonical_status, stored_status
from apps.scholarship.document_snapshot import SNAPSHOT_ORDER
from apps.scholarship.models import ApplicantDocument

ANCHOR_TYPES = ('ic', 'results_slip', 'offer_letter')
#: The doc types this command can score from text with no paid call (see the module docstring).
FREE_TYPES = ('results_slip', 'offer_letter')


def is_unscored(doc):
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    return not canonical_status(stored_status(vf), doc.doc_type)              # TD-293


def _record(sg, basis):
    return {'status': sg['status'], 'reason': sg.get('reason', ''),
            'doc_seen': sg.get('type') or sg.get('doc_seen', ''),
            'probability': sg.get('probability'), 'present': sg.get('present', []),
            'missing': sg.get('missing', []), 'model_version': sg.get('model_version'),
            'rescored': {'by': 'rescore_unscored_documents', 'basis': basis,
                         'at': timezone.now().isoformat()}}


def score_from_text(doc_type, text):
    """`(authenticity_dict, None)` or `(None, reason)` — the live scorer's answer from text alone."""
    if doc_type == 'offer_letter':
        sg = assess('offer_letter', ocr_text=text)
        if not sg.get('status'):
            return None, 'no_signal'
        # The live path folds a legacy 'unrecognised' to 'suspect' (vision.py offer branch).
        sg = dict(sg, status='suspect' if sg['status'] == 'unrecognised' else sg['status'])
        return _record(sg, 'text'), None
    if doc_type == 'results_slip':
        low = signature_genuineness(text, has_qr=False, has_crest=False)
        high = signature_genuineness(text, has_qr=True, has_crest=True)
        if low['status'] != high['status']:
            return None, 'indeterminate'
        return _record(low, 'text_only_visuals_unread'), None
    return None, 'paid_read'


class Command(BaseCommand):
    help = ('Count live IC / results-slip / offer documents never scored for genuineness, and '
            'score from stored text the ones that need no paid call (dry-run unless --apply).')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the scores. Without it nothing is saved.')

    def handle(self, *args, **opts):
        apply = opts['apply']
        tally = {t: {'unscored': 0, 'unscored_latest': 0, 'scored': 0, 'paid_read': 0,
                     'no_stored_text': 0, 'indeterminate': 0, 'no_signal': 0}
                 for t in ANCHOR_TYPES}
        docs = (ApplicantDocument.live(ApplicantDocument.objects.filter(doc_type__in=ANCHOR_TYPES))
                .order_by('application_id', 'doc_type', *SNAPSHOT_ORDER))
        seen = set()   # (application, type) whose LATEST row has been met — what the verdict reads
        for doc in docs.only('id', 'application_id', 'doc_type', 'vision_fields').iterator():
            key = (doc.application_id, doc.doc_type)
            latest = key not in seen
            seen.add(key)
            if not is_unscored(doc):
                continue
            row = tally[doc.doc_type]
            row['unscored'] += 1
            row['unscored_latest'] += latest
            if doc.doc_type not in FREE_TYPES:
                row['paid_read'] += 1
                continue
            vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
            text = (vf.get('text') or '').strip()
            if not text:
                row['no_stored_text'] += 1
                continue
            auth, why = score_from_text(doc.doc_type, text)
            if auth is None:
                row[why] += 1
                continue
            row['scored'] += 1
            if apply:
                doc.vision_fields = dict(vf, authenticity=auth)
                doc.save(update_fields=['vision_fields'])
        mode = 'APPLIED' if apply else 'DRY-RUN (nothing written; --apply to write)'
        self.stdout.write(f'rescore_unscored_documents: {mode}')
        for t in ANCHOR_TYPES:
            r = tally[t]
            self.stdout.write(
                f"  {t}: unscored={r['unscored']} unscored_latest={r['unscored_latest']} "
                f"scored={r['scored']} paid_read={r['paid_read']} "
                f"no_stored_text={r['no_stored_text']} indeterminate={r['indeterminate']} "
                f"no_signal={r['no_signal']}")
