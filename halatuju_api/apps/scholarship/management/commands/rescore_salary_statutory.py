"""#85 — re-score, from their STORED markers, the live payslips the old cascade wrongly called not_salary.

Before salary_doc 1.3.0 the "no recognisable payslip fields" reject ran before the statutory branch, so a
slip whose text showed two or more statutory deductions (KWSP / SOCSO / EIS / PCB) but none of the wage
labels was stored as `not_salary`, and the family was asked again for the earner's income. 1.3.0 puts the
statutory branch first (the 2026-07-09 rule); the MyKad reject still runs before it.

The stored `authenticity.markers` (`statutory`, `wage`, `kwsp`) are everything the new cascade reads for
such a row: a stored not_salary has 0 wage labels, and with ≥2 statutory markers and no MyKad (its reason
is not the MyKad one) `salary_doc.decide` answers genuine/private whatever the issuer flags say. So this
command re-writes the result exactly as a fresh read would — NO read, NO AI call, NO OCR text.

Selected: live (not superseded) `salary_slip` rows stored `not_salary` by a model older than 1.3.0, with
markers `statutory >= 2`, `wage == 0`, a recorded `kwsp`, and a reason that is not the MyKad reason.
DRY-RUN BY DEFAULT: prints document id + case number + old -> new and the counts (no personal data);
`--apply` writes.

    python manage.py rescore_salary_statutory            # dry run
    python manage.py rescore_salary_statutory --apply    # write
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scholarship.genuineness.salary_doc import MODEL_VERSION, decide
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.vision.authenticity import _family_auth

#: The first model version whose cascade puts the statutory branch before the "no payslip fields" reject.
FIXED_IN = (1, 3)
_MYKAD_REASON = 'MyKad'


def _version(raw) -> tuple:
    try:
        return tuple(int(p) for p in str(raw or '').split('.')[:2])
    except ValueError:
        return ()


def _marker_count(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def eligible(doc) -> bool:
    """Is this row one the old order called not_salary although its stored markers make it a payslip?"""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    auth = vf.get('authenticity')
    if not isinstance(auth, dict) or auth.get('status') != 'not_salary':
        return False
    if _version(auth.get('model_version')) >= FIXED_IN or not _version(auth.get('model_version')):
        return False
    if str(auth.get('reason') or '').startswith(_MYKAD_REASON):
        return False
    m = auth.get('markers')
    if not isinstance(m, dict) or not isinstance(m.get('kwsp'), bool):
        return False
    stat, wage = _marker_count(m.get('statutory')), _marker_count(m.get('wage'))
    return stat is not None and stat >= 2 and wage == 0


def rescored_authenticity(doc) -> dict:
    """The stored result the 1.3.0 scorer gives this row, from its stored markers alone."""
    m = doc.vision_fields['authenticity']['markers']
    sg = decide({'statutory': m['statutory'], 'wage': m['wage'], 'kwsp': m['kwsp'],
                 'mykad': False, 'govt': False, 'singapore': False, 'gig': False})
    auth = _family_auth(sg)
    auth['rescored'] = {'by': 'rescore_salary_statutory', 'basis': 'stored_markers',
                        'from_model_version': doc.vision_fields['authenticity'].get('model_version'),
                        'at': timezone.now().isoformat()}
    return auth


def rescore_candidates():
    qs = ApplicantDocument.live(ApplicantDocument.objects.filter(
        doc_type='salary_slip', vision_fields__authenticity__status='not_salary'))
    return [d for d in qs.only('id', 'application_id', 'vision_fields').order_by('id') if eligible(d)]


class Command(BaseCommand):
    help = ('#85: re-score from stored markers the live payslips with >=2 statutory deductions that an '
            'older salary model called not_salary (dry-run unless --apply; no read, no AI call).')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the results. Without it nothing is saved.')

    def handle(self, *args, **opts):
        apply = opts['apply']
        written = 0
        docs = rescore_candidates()
        for doc in docs:
            auth = rescored_authenticity(doc)
            self.stdout.write(f"  document {doc.id} case {doc.application_id}: not_salary -> "
                              f"{auth['status']}/{auth['doc_seen']}")
            if apply:
                doc.vision_fields = dict(doc.vision_fields, authenticity=auth)
                doc.save(update_fields=['vision_fields'])
                written += 1
        mode = 'APPLIED' if apply else 'DRY-RUN (nothing written; --apply to write)'
        self.stdout.write(f'rescore_salary_statutory: {mode}; model {MODEL_VERSION}; '
                          f'selected={len(docs)} written={written}')
