"""Document chip standard — what a chip change WOULD do, as COUNTS, inside ONE read-only transaction.

⛔ HAND-RUN ONLY, and only on the owner's word. Never run it against a live database from a checkout:
the unit tests (``tests/test_chip_dry_run.py``) run it on the TEST database only.

Safety: everything runs inside ``offer_s4_dry_run.read_only_rollback`` — ONE transaction, ``BEGIN READ
ONLY`` on PostgreSQL, every write refused, Storage / Gemini / the usage meter shut, and always rolled
back. Signed download URLs are not made (``get_download_url`` is stubbed to None).

What it counts, per document type (live documents only, superseded rows skipped), for BOTH audiences
(Sprint 1: the officer's payload serves ``doc_chips``, the student's ``doc_chips_student``):
  docs                   documents seen
  chips                  chips on the OFFICER payload (``AdminApplicantDocumentSerializer``)
  state_changed          officer chips whose state differs between ``old`` and ``new`` (compared key
                         by key, in order; a chip present on one side only counts too)
  pill_changed           documents whose officer pill differs between ``old`` and ``new``
  student_chips          chips on the STUDENT payload (``ApplicantDocumentSerializer``)
  student_state_changed  the same, between ``student_old`` and ``student_new``, on the student payload
  student_pill_changed   the same for the student pill (the student draws no pill today)

and, over the whole run, ``chip_fallbacks``: how far the serializer's loud-fallback counter
(``serializers.documents.CHIP_FALLBACKS``, N6) moved while the documents were served. Every fallback is
a document that served no chips because a chip function raised, so a clean run must show 0.

``old`` / ``new`` (officer) and ``student_old`` / ``student_new`` (student) are chip functions on a
serialized document. They default to the audience's own ``chips_for``, which reproduces today's screen
exactly, so every ``*state_changed`` is 0 by construction; a later sprint passes its frozen "today" as
the old one and its target rules as the new one. (Sprint 0's ``student_differs`` is gone: the two
audiences now have different rules on purpose, so comparing them says nothing.)

Verdict bands: every application's four fact bands (``build_verdict`` → ``_fact_band``) are taken BEFORE
the documents are serialized, then AFTER, with EVERY public function of BOTH chip modules (``doc_chips``
and ``doc_chips_student``: ``chips_for``, ``pill_for``, ``fact_chips``, ``year_chip`` and the rest) rigged
to raise ``ChipsRefused``. The serializer calls the chips through the MODULE (``module.chips_for``), so
the rig bites there too, and ``ChipsRefused`` is a ``BaseException`` so the serializer's display-only
fallback (which catches ``Exception``) cannot swallow it. What a clean run proves, for the data it
read and no more: (1) serializing the documents left every band as it was, and (2) ``build_verdict``
on that data never reached the chip functions, directly or through the document serializer. Code paths
that data does not exercise are the import fence's job (``tests/test_doc_chips_import_fence.py``).
``bands_identical`` is True only when every band of every application is the same. Output is counts
only — never a name, an IC, an id or a value read off a document.

Cost: one documents query per application, the two serializers' own reads per document, and
``build_verdict`` twice per application, over EVERY application. Hand-run only, never at peak time.

Usage (operator, owner's word only):  python manage.py shell -c "from apps.scholarship.eval.chip_dry_run
import main; main()"
"""
import contextlib
import inspect
from collections import Counter, defaultdict
from unittest import mock


def _bands(application):
    from apps.scholarship.verdict_engine import build_verdict
    from apps.scholarship.verdict_narrative import _fact_band
    return tuple((f.get('fact'), _fact_band(f)) for f in build_verdict(application))


class ChipsRefused(BaseException):
    """A verdict path called the chip module. A BaseException on purpose: the document serializer's
    display-only fallback catches ``Exception`` and must not swallow this."""


def public_chip_functions(module):
    """The names of every public function DEFINED in ``module`` (not one it imported)."""
    return sorted(name for name, v in vars(module).items()
                  if not name.startswith('_') and inspect.isfunction(v) and v.__module__ == module.__name__)


@contextlib.contextmanager
def _chips_refused():
    """Any call to a public function of either chip module while this is open raises ``ChipsRefused``
    (they are display only). The calls are also counted, so a caller that swallowed even a
    BaseException is caught on the way out."""
    from apps.scholarship import doc_chips, doc_chips_student
    calls = []

    def refuse(*_a, **_k):
        calls.append(1)
        raise ChipsRefused('chip_dry_run: a verdict path called doc_chips / doc_chips_student')
    with contextlib.ExitStack() as stack:
        for module in (doc_chips, doc_chips_student):
            for name in public_chip_functions(module):
                stack.enter_context(mock.patch.object(module, name, refuse))
        yield
    if calls:
        raise ChipsRefused(f'chip_dry_run: a verdict path called doc_chips / doc_chips_student '
                           f'{len(calls)} time(s)')


def _payloads(doc):
    from apps.scholarship.serializers import ApplicantDocumentSerializer
    from apps.scholarship.sgd_conversion import AdminApplicantDocumentSerializer
    with mock.patch.object(ApplicantDocumentSerializer, 'get_download_url', lambda self, obj: None):
        return ApplicantDocumentSerializer(doc).data, AdminApplicantDocumentSerializer(doc).data


def _changed(a, b):
    """Chips whose state differs, key by key in order; a chip on one side only counts as changed."""
    n = max(len(a), len(b))
    return sum(1 for i in range(n)
               if i >= len(a) or i >= len(b) or (a[i]['key'], a[i]['state']) != (b[i]['key'], b[i]['state']))


def count_changes(applications, old=None, new=None, student_old=None, student_new=None):
    """The counts (see the module docstring) over ``applications``. Pure reads; call it inside
    ``read_only_rollback``."""
    from apps.scholarship import doc_chips, doc_chips_student
    from apps.scholarship.serializers.documents import CHIP_FALLBACKS
    fallbacks_before = CHIP_FALLBACKS['count']
    old = old or doc_chips.chips_for
    new = new or doc_chips.chips_for
    student_old = student_old or doc_chips_student.chips_for
    student_new = student_new or doc_chips_student.chips_for
    per_type = defaultdict(Counter)
    apps_seen = bands_same = 0
    for application in applications:
        apps_seen += 1
        before = _bands(application)
        for doc in application.documents.filter(superseded_at__isnull=True):
            student, officer = _payloads(doc)
            row = per_type[doc.doc_type]
            o, n = old(officer), new(officer)
            row['docs'] += 1
            row['chips'] += len(officer['chips'])
            row['state_changed'] += _changed(o, n)
            row['pill_changed'] += int(doc_chips.pill_for(o) != doc_chips.pill_for(n))
            so, sn = student_old(student), student_new(student)
            row['student_chips'] += len(student['chips'])
            row['student_state_changed'] += _changed(so, sn)
            row['student_pill_changed'] += int(doc_chips_student.pill_for(so) != doc_chips_student.pill_for(sn))
        with _chips_refused():
            after = _bands(application)
        bands_same += int(before == after)
    return {
        'applications': apps_seen,
        'bands_identical': bands_same == apps_seen,
        'bands_same': bands_same,
        'chip_fallbacks': CHIP_FALLBACKS['count'] - fallbacks_before,
        'per_type': {k: dict(v) for k, v in sorted(per_type.items())},
    }


def run_dry(old=None, new=None, student_old=None, student_new=None, *, allow_sqlite=False):
    """Every application, inside ONE read-only transaction that is always rolled back."""
    from apps.scholarship.eval.offer_s4_dry_run import read_only_rollback
    from apps.scholarship.models import ScholarshipApplication
    with read_only_rollback(allow_sqlite=allow_sqlite):
        return count_changes(ScholarshipApplication.objects.order_by('pk').iterator(), old=old, new=new,
                             student_old=student_old, student_new=student_new)


def render_counts(result):
    lines = [f"applications {result['applications']}  bands_identical {result['bands_identical']}  "
             f"chip_fallbacks {result['chip_fallbacks']}"]
    for doc_type, row in result['per_type'].items():
        lines.append(f"{doc_type:22} docs {row.get('docs', 0):5}  chips {row.get('chips', 0):6}  "
                     f"state_changed {row.get('state_changed', 0):5}  pill_changed {row.get('pill_changed', 0):5}  "
                     f"student_chips {row.get('student_chips', 0):6}  "
                     f"student_state_changed {row.get('student_state_changed', 0):5}  "
                     f"student_pill_changed {row.get('student_pill_changed', 0):5}")
    return '\n'.join(lines)


def main():                                   # pragma: no cover — the operator's printer
    print(render_counts(run_dry()))
