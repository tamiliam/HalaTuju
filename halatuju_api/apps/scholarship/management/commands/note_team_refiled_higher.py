"""Write the reviewer note for the six STPM slips the HalaTuju team moved from the SPM card to the
higher-results card on 2026-10-26 (third results route S4; roadmap §7a D15, "Done 2026-10-26").

The move itself was one guarded SQL update (doc_type results_slip -> higher_results, results_kind
'stpm', the read cleared exactly as `results_route.refile_to_spm` does). Its reviewer note could not
be written then: the cockpit rendered only the 'only_spm' / 'refiled_spm' kinds. S4 adds the
'refiled_higher' kind; this command appends it, with ``by: 'team'``, to each of the six applications'
`results_change_notes` — the cockpit's Academic card then reads "Moved from the SPM card to the STPM
results card by the HalaTuju team on 2026-10-26."

REPORT-ONLY BY DEFAULT: it prints what it would write and writes nothing. ``--apply`` writes.
IDEMPOTENT: an application that already carries a 'refiled_higher' note for that document is left
alone, so a second ``--apply`` writes nothing. A pair whose document is no longer that application's
LIVE higher-results upload is reported and skipped (never guessed). Reads stored rows only: no
document is read again, nothing is scored, no email is sent, and the verdict is not re-run.

    python manage.py note_team_refiled_higher            # report
    python manage.py note_team_refiled_higher --apply    # write the notes
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument, ScholarshipApplication

#: (application id, document id) — the exact list the owner said "go" on (roadmap §7a D15).
MOVED = ((189, 2680), (257, 3109), (258, 3709), (275, 3053), (325, 3490), (333, 3661))
#: The day of the team's move — the note's date (not the day this command runs).
MOVED_AT = '2026-10-26T00:00:00+08:00'


def _note_for(doc_id):
    # `submitted` is AS OF THE MOVE (2026-10-26), like every other note's: the team moved only
    # shortlisted, UNSUBMITTED applications (roadmap §7a D15), so all six were unsubmitted then —
    # whatever they are on the day this command runs (review finding 5).
    return {'at': MOVED_AT, 'kind': 'refiled_higher', 'submitted': False, 'document_id': doc_id,
            'results_kind': 'stpm', 'by': 'team'}


def plan(pairs=MOVED):
    """``[(app_id, doc_id, outcome)]`` — outcome 'write', 'already_noted' or a skip reason."""
    out = []
    for app_id, doc_id in pairs:
        app = ScholarshipApplication.objects.filter(pk=app_id).first()
        if app is None:
            out.append((app_id, doc_id, 'skip: no such application'))
            continue
        live = ApplicantDocument.objects.filter(
            pk=doc_id, application=app, doc_type='higher_results', superseded_at__isnull=True,
        ).exists()
        if not live:
            out.append((app_id, doc_id, 'skip: not this application\'s live higher-results upload'))
            continue
        notes = app.results_change_notes if isinstance(app.results_change_notes, list) else []
        done = any(isinstance(n, dict) and n.get('kind') == 'refiled_higher'
                   and n.get('document_id') == doc_id for n in notes)
        out.append((app_id, doc_id, 'already_noted' if done else 'write'))
    return out


class Command(BaseCommand):
    help = ("Add the 'refiled_higher' reviewer note (by the team) to the six applications whose "
            "STPM slip the team moved on 2026-10-26. Report-only unless --apply.")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the notes (default: report only).')

    def handle(self, *args, **opts):
        apply = opts['apply']
        written = 0
        for app_id, doc_id, outcome in plan():
            self.stdout.write(f'app {app_id} doc {doc_id}: {outcome}')
            if outcome != 'write' or not apply:
                continue
            app = ScholarshipApplication.objects.get(pk=app_id)
            notes = list(app.results_change_notes or [])
            notes.append(_note_for(doc_id))
            app.results_change_notes = notes
            app.save(update_fields=['results_change_notes'])
            written += 1
        mode = 'APPLIED' if apply else 'REPORT ONLY (nothing written; pass --apply)'
        self.stdout.write(f'{mode}: {written} note(s) written.')
