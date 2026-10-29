"""Fill a BLANK `results_kind` on a live higher-results upload from the results the student holds
(Matric/Diploma exact-read M1, 2026-10-29; ruling D13).

WHAT THE COLUMN IS. `applicant_documents.results_kind` is the kind of results an upload is MEANT to
be — the results held at upload (`results_route.upload_kind`), never what the page says (that is
`vision_fields.fields.results_kind_detected`, `results_kind.py`). It is '' when the student held no
tertiary results at upload — the D1 legacy rows that read SPM until a document promoted them, or an
SPM holder whose upload the team moved here. So it is filled from the results held NOW
(`results_route.held_kind`), and ONLY when those are tertiary. It is NEVER filled from the detection:
`student_higher_check` compares the two, and a column copied from the detection would turn "cannot
tell" into a "kind matches" line that compares nothing.

VERDICT-NEUTRAL. `student_higher_check` already uses the results held whenever they are tertiary
and reads the column only when they are not, so a row this command fills reads exactly as before;
the column it changes is the reviewer drawer's label ("STPM results" instead of "Higher results").
Afterwards a filled row is like any other upload: if the student's held results later stop being
tertiary (a D1 row whose witness goes), its filled column then drives `kind_held`.
A row whose student holds no tertiary results is reported and left '' (that IS its value).

REPORT-ONLY BY DEFAULT; ``--apply`` writes. IDEMPOTENT: only a still-blank live row is written, by a
guarded update. Reads stored rows only: no document is read again, nothing is scored, no Gemini or
Vision call, and the verdict is not re-run.

    python manage.py backfill_higher_results_kind            # report
    python manage.py backfill_higher_results_kind --apply    # write
"""
import logging

from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument

logger = logging.getLogger(__name__)


def blank_rows():
    """``[(doc, kind or '', outcome)]`` for every LIVE higher-results upload whose kind is blank:
    outcome 'fill' (the results held are tertiary) or a reason it is left blank."""
    from apps.scholarship.results_route import held_kind
    docs = (ApplicantDocument.objects
            .filter(doc_type='higher_results', superseded_at__isnull=True, results_kind='')
            .select_related('application', 'application__profile').order_by('id'))
    out = []
    for doc in docs:
        kind = held_kind(doc.application)
        out.append((doc, kind, 'fill' if kind else 'leave: holds no tertiary results (D13)'))
    return out


def _detected(doc):
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    f = vf.get('fields') if isinstance(vf.get('fields'), dict) else {}
    return f.get('results_kind_detected') or '-'


class Command(BaseCommand):
    help = ("Fill a blank results_kind on live higher-results uploads from the results held "
            "(tertiary only; never from the detection). Report-only unless --apply.")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write (default: report only).')

    def handle(self, *args, **opts):
        apply = opts['apply']
        written = 0
        for doc, kind, outcome in blank_rows():
            self.stdout.write(f'doc {doc.id} app {doc.application_id}: held={kind or "-"} '
                              f'detected={_detected(doc)} -> {outcome}')
            if outcome != 'fill' or not apply:
                continue
            written += ApplicantDocument.objects.filter(pk=doc.pk, results_kind='').update(results_kind=kind)
            logger.info('AUDIT higher_results_kind_backfilled doc=%s app=%s kind=%s',
                        doc.id, doc.application_id, kind)
        mode = 'APPLIED' if apply else 'REPORT ONLY (nothing written; pass --apply)'
        self.stdout.write(f'{mode}: {written} row(s) written.')
