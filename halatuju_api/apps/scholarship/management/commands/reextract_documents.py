"""Bulk re-extract documents in batches with the CURRENT parsers.

Most supporting docs were read by Gemini before the deterministic capture layer
(2026-06-11), so they carry weaker reads (e.g. an offer letter whose IC was never
captured). This re-reads them with the current deterministic + Gemini parsers.

Self-batching: each run processes the NEXT `--limit` (default 20) docs that this pass
hasn't touched yet — marked by a flag written into ``vision_fields`` — so it can be
called repeatedly (cron-driven) and observed batch by batch. FORCES billable reads, so
it's run deliberately. Scope = the supporting + text doc types (ic/parent_ic already
store their read in dedicated columns; photos aren't OCR'd).

⚠ THE CRON ENDPOINT PASSES NO ARGUMENTS. To run a targeted pass on the live service, set
``REEXTRACT_DOC_TYPE`` (one doc type) and ``REEXTRACT_PASS`` (a NEW pass name, so those docs
become eligible again without re-sweeping the whole corpus), run the ``reextract-documents``
job repeatedly until it reports nothing left, then UNSET both.

FORCED OVERWRITE (Matric/Diploma M5, review SF7 of M4b): `bands.keep_stored_authenticity` (TD-407)
carries a stored genuineness block forward when a re-read gives no signal. For the Matriculation /
Diploma higher-results pages re-scored under the M4b rulings that is wrong: a page stored "not final"
or "genuine" under the old rule must take the NEW answer, `{}` ("not checked") included.
``--fresh-higher-authenticity`` (env ``REEXTRACT_FRESH_HIGHER_AUTH=1``) drops the stored block of
each `higher_results` doc whose kind is matric / diploma, IN MEMORY, just before its re-read — so the
fresh result stands. Nothing is saved until the re-read succeeds: a failed re-read is clobber-guarded
(`run_field_extraction_for_document`, no save), so the stored block survives it. Every other doc
type, and the STPM higher pages, keep TD-407 exactly as before.
"""
import os

from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.reextract import add_preflight_argument, reextract_document, reread_preflight

# Bump this for a future re-extraction pass (e.g. after another parser change).
PASS_MARKER = 'reextract_2026_06'
#: The higher-results kinds whose stored authenticity a forced pass replaces (M4b review SF7).
FRESH_AUTH_KINDS = ('matric', 'diploma')


def drop_higher_authenticity(doc) -> bool:
    """SF7: forget a Matriculation / Diploma higher-results doc's stored authenticity IN MEMORY (never
    saved here), so the re-read's own answer — `{}` included — replaces it. True when it dropped one."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    fields = vf.get('fields') if isinstance(vf.get('fields'), dict) else {}
    kind = (doc.results_kind or fields.get('results_kind_detected') or '').strip().lower()
    if doc.doc_type != 'higher_results' or kind not in FRESH_AUTH_KINDS or 'authenticity' not in vf:
        return False
    doc.vision_fields = {k: v for k, v in vf.items() if k != 'authenticity'}
    return True


def _summary(doc) -> str:
    """A compact, human-readable digest of the key extracted field(s) per type, so each
    batch's outcome is visible in the (truncated) cron output."""
    vf = doc.vision_fields or {}
    f = vf.get('fields') or {}
    cap = vf.get('capture') or '—'
    dt = doc.doc_type
    if dt == 'offer_letter':
        return f"ic={f.get('candidate_nric','') or '∅'} name={(f.get('candidate_name') or '')[:16]}"
    if dt == 'birth_certificate':
        # The child IC + the date of birth that vouches for it: this pass exists to fill them,
        # so a batch's output must show whether it did.
        return (f"child={(f.get('bc_child_name') or '∅')[:16]} "
                f"ic={f.get('bc_child_nric') or '∅'} dob={f.get('bc_child_dob') or '∅'} "
                f"mother={(f.get('bc_mother_name') or '')[:12]}")
    if dt == 'results_slip':
        return f"name={(f.get('slip_name') or f.get('name') or '')[:16]} cap={cap}"
    if dt == 'school_leaving_cert':
        auth = (vf.get('authenticity') or {}).get('status', '—')
        mk = (vf.get('authenticity') or {}).get('markers') or {}
        return (f"name={(f.get('name') or '')[:14]} kel={(f.get('kelakuan') or '∅')[:8]} "
                f"auth={auth} labels={mk.get('labels', '?')}")
    if dt in ('salary_slip', 'epf', 'str', 'water_bill', 'electricity_bill'):
        return f"name={(f.get('name') or f.get('str_recipient') or '')[:16]} cap={cap}"
    return f"cap={cap}"


class Command(BaseCommand):
    help = 'Re-extract supporting documents in batches (default 20) with the current parsers.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Docs to process this run.')
        parser.add_argument('--doc-type', default='',
                            help='Restrict the pass to ONE doc type (e.g. school_leaving_cert) — a '
                                 'targeted, cheap re-extraction (calibration / a single-type rollout) '
                                 'instead of the whole supporting-doc corpus.')
        parser.add_argument('--pass-marker', default='',
                            help='Name this pass (default: PASS_MARKER). A NEW name makes docs '
                                 'eligible again without disturbing the standing pass — which is '
                                 'how a single-type re-read after a parser change is run.')
        parser.add_argument('--retry-errors', action='store_true',
                            help="Also re-attempt docs whose last run FAILED (marked 'error'). "
                                 "Default runs skip them so one broken doc can't wedge the pass.")
        parser.add_argument('--fresh-higher-authenticity', action='store_true',
                            help='M5 (M4b review SF7): a Matriculation / Diploma higher-results re-read '
                                 'REPLACES its stored authenticity with the fresh result ({} included), '
                                 'instead of TD-407 keeping it. Env door: REEXTRACT_FRESH_HIGHER_AUTH=1.')
        add_preflight_argument(parser)

    def handle(self, *args, **opts):
        reread_preflight(self, opts)                     # TD-407: never re-read without the service's flags
        from apps.scholarship.views import SUPPORTING_NAME_CHECK_TYPES, TEXT_READ_DOC_TYPES
        # ``ic`` is deliberately OUTSIDE the default scope but reachable with an explicit
        # --doc-type. The original exclusion ("ic/parent_ic already store their read in
        # dedicated columns") was true when written and stopped being the whole truth once ICs
        # gained a GENUINENESS model, which lands in vision_fields like everything else — and
        # from 2026-07-29 that verdict decides whether an identity locks. Production carries 36
        # cards read before the model existed, which can never lock until they are scored.
        # Kept opt-in rather than folded into the default sweep because an IC read costs a
        # multimodal call per card and should be a deliberate act, not a side-effect of a
        # routine supporting-doc pass.
        types = sorted(SUPPORTING_NAME_CHECK_TYPES | TEXT_READ_DOC_TYPES)
        targeted_only = {'ic'}
        # ⚠ THE CRON ENDPOINT PASSES NO ARGUMENTS, so a flag alone can never be used in
        # production (TD-234). The env vars are the door: set them on the service, run the
        # job, then UNSET them — the same shape as PARTNER_EMAIL_RESET_KINDS.
        only = (opts.get('doc_type') or os.environ.get('REEXTRACT_DOC_TYPE') or '').strip()
        if only:
            if only not in set(types) | targeted_only:
                self.stderr.write(f"reextract: --doc-type '{only}' is not re-extractable "
                                  f"({', '.join(sorted(set(types) | targeted_only))}).")
                return
            types = [only]
        limit = max(1, opts['limit'])
        retry_errors = opts['retry_errors']
        marker = (opts.get('pass_marker') or os.environ.get('REEXTRACT_PASS') or PASS_MARKER).strip()
        fresh_auth = bool(opts.get('fresh_higher_authenticity')) or (
            os.environ.get('REEXTRACT_FRESH_HIGHER_AUTH', '').strip().lower() in ('1', 'true', 'yes'))
        from django.conf import settings
        if fresh_auth and not getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False):
            from django.core.management.base import CommandError     # nothing fresh would replace it
            raise CommandError('reextract: --fresh-higher-authenticity needs DOC_GENUINENESS_CHECK_ENABLED '
                               '(with it off the re-read scores nothing, so dropping a score would lose it).')

        # Filter "not yet processed this pass" in Python — a JSON-key `.exclude()` mishandles
        # rows where the key (or the whole vision_fields) is absent (SQL NULL semantics).
        # Code-health S2 #5b: an errored doc is marked 'error' (not True) — the pass advances
        # past it (no wedge), but it stays visibly failed and a --retry-errors run picks it
        # back up, instead of being silently stuck on the weak read forever.
        def unprocessed(doc):
            mark = (doc.vision_fields or {}).get(marker)
            return not mark or (retry_errors and mark == 'error')

        all_docs = ApplicantDocument.objects.filter(doc_type__in=types).order_by('id')
        batch = []
        for doc in all_docs.iterator():
            if unprocessed(doc):
                batch.append(doc)
            if len(batch) >= limit:
                break
        if not batch:
            self.stdout.write('reextract: nothing left — every supporting doc is on the current pass.')
            return

        done = errors = 0
        for doc in batch:
            before = _summary(doc)   # snapshot the prior read BEFORE we overwrite it
            stamps_before = (doc.vision_fields_run_at, doc.vision_run_at)
            ok = True
            try:
                if fresh_auth and drop_higher_authenticity(doc):
                    before += ' auth=dropped'
                reextract_document(doc)
                doc.refresh_from_db()
                after = _summary(doc)
                # The clobber guard keeps a stored read (and skips the save) when the
                # re-run itself failed — no timestamp advances. Treat that as an ERROR
                # of THIS run (old data safely kept), not a completed re-extraction.
                if (doc.vision_fields_run_at, doc.vision_run_at) == stamps_before:
                    ok = False
                    after = f'STALE-KEPT [{after}] (re-run failed; stored read preserved)'
            except Exception as e:  # noqa: BLE001 — mark + report so a broken doc never wedges the pass
                ok = False
                after = f'ERROR {str(e)[:55]}'
                doc.refresh_from_db()
            # Mark the doc so the next run advances: True = re-extracted on this pass;
            # 'error' = attempted + failed (skipped by default, re-attempted with
            # --retry-errors). Never stamp a failure as done (#5b).
            vf = doc.vision_fields or {}
            vf[marker] = True if ok else 'error'
            doc.vision_fields = vf
            doc.save(update_fields=['vision_fields'])
            done += 1
            if not ok:
                errors += 1
            self.stdout.write(f'app#{doc.application_id} doc{doc.id} {doc.doc_type}: [{before}] -> [{after}]')

        remaining = sum(
            1 for d in ApplicantDocument.objects.filter(doc_type__in=types).only('vision_fields', 'doc_type')
            if unprocessed(d))
        error_total = sum(
            1 for d in ApplicantDocument.objects.filter(doc_type__in=types).only('vision_fields', 'doc_type')
            if (d.vision_fields or {}).get(marker) == 'error')
        self.stdout.write(
            f'reextract: processed {done} ({errors} errors this run), {remaining} remaining, '
            f'{error_total} marked error total — re-attempt those with --retry-errors.')
