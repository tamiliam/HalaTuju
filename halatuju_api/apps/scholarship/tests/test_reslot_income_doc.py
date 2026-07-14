"""An EPF uploaded into the salary-slip slot is filed as an EPF (owner, 2026-07-14 — #126).

The income-proof request SAYS "his latest salary slip or EPF (KWSP) statement" but owns ONE slot
(`salary_slip`), and the Action Centre uploads into the item's doc_type. So an EPF landed in the
payslip slot, scored `not_salary` ("no recognisable payslip fields"), failed usable_salary_slip(),
never cleared the request, and looped the student into the circuit-breaker.

We were inviting a document and then refusing it — the #126 trap, written into our own copy.

The engine already accepts EITHER document as that member's income evidence. Only the SLOT was
wrong. Fix the slot and the copy becomes true; narrowing the copy instead would have left the same
trap armed for the formal earner whose only proof IS the EPF.
"""
from django.test import TestCase

from apps.scholarship.views import _reslot_income_doc

# A real KWSP "Penyata Ahli" — the same shape the deterministic parser is calibrated on
# (test_doc_parse._KWSP). Shaped as #126's mother's: No. Majikan all-zeros, no contributions.
_EPF_TEXT = """SULIT DAN PERSENDIRIAN

VIMALA A/P MUNIANDY
KAMPUNG BESAR
13300 TASEK GELUGOR
Pulau Pinang
PENYATA AHLI TAHUN 2026
RINGKASAN AKAUN
No. Ahli KWSP : 12345678 Tarikh Penyata : 08/07/2026
No. Kad Pengenalan : 830402025562
No. Majikan : 000000000
JUMLAH SIMPANAN: RM27,044.84
CARUMAN SEMASA
Tiada Transaksi
"""

_PAYSLIP_TEXT = """
PENYATA GAJI  /  SALARY SLIP
Nama: R KANNAN A/L RAMU
Gaji Pokok: RM2,400.00   Elaun: RM300.00
KWSP: RM264.00   PERKESO: RM12.00   PCB: RM0.00
Gaji Bersih: RM2,424.00
"""


class _Doc:
    """The two fields _reslot_income_doc touches — no DB, no storage."""
    def __init__(self, doc_type):
        self.doc_type = doc_type
        self.id = 1
        self.application_id = 126
        self.saved = []

    def save(self, update_fields=None):
        self.saved.append(tuple(update_fields or ()))


class TestReslotIncomeDoc(TestCase):
    def test_an_epf_in_the_payslip_slot_is_refiled_as_an_epf(self):
        doc = _Doc('salary_slip')
        self.assertTrue(_reslot_income_doc(doc, {'text': _EPF_TEXT}))
        self.assertEqual(doc.doc_type, 'epf')
        self.assertEqual(doc.saved, [('doc_type',)])

    def test_a_real_payslip_is_never_moved(self):
        # The whole point: a genuine salary slip must stay exactly where the student put it.
        doc = _Doc('salary_slip')
        self.assertFalse(_reslot_income_doc(doc, {'text': _PAYSLIP_TEXT}))
        self.assertEqual(doc.doc_type, 'salary_slip')
        self.assertEqual(doc.saved, [])

    def test_an_unreadable_scan_is_never_moved(self):
        # No text → no confident read → leave it alone and let the normal coach path run.
        for ocr in ({'text': ''}, {}, None):
            with self.subTest(ocr=ocr):
                doc = _Doc('salary_slip')
                self.assertFalse(_reslot_income_doc(doc, ocr))
                self.assertEqual(doc.doc_type, 'salary_slip')

    def test_other_doc_types_are_untouched(self):
        # One-directional: only salary_slip is ever re-slotted. An EPF stays an EPF; nothing else
        # is second-guessed.
        for t in ('epf', 'str', 'ic', 'offer_letter', 'results_slip'):
            with self.subTest(doc_type=t):
                doc = _Doc(t)
                self.assertFalse(_reslot_income_doc(doc, {'text': _EPF_TEXT}))
                self.assertEqual(doc.doc_type, t)


class TestTheRequestClearsOnEitherDocument(TestCase):
    """The point of the re-slot: once the EPF sits in the EPF slot, the income-proof request
    clears on its own. The engine always accepted either document — only the slot was wrong."""

    @classmethod
    def setUpTestData(cls):
        from apps.scholarship.models import ScholarshipCohort
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, uid):
        from django.utils import timezone
        from apps.courses.models import StudentProfile
        from apps.scholarship.models import ResolutionItem, ScholarshipApplication
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name='HAVINESH A/L R KANNAN', nric='081211-07-0605',
            preferred_state='Pulau Pinang', household_income=3900, household_size=5,
            receives_str=True, receives_jkm=False,
        )
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='profile_complete',
            profile_completed_at=timezone.now(), income_route='str', income_earner='mother',
            father_name='R KANNAN A/L RAMU', father_occupation='driver',
            mother_name='VIMALA A/P MUNIANDY', mother_occupation='unemployed',
        )
        # He told us his father has a payslip → the request is open.
        ResolutionItem.objects.create(
            application=app, source='check2', code='informal_income_detail', fact='income',
            kind='clarify', status='resolved', resolution_text='he has payslip',
            resolved_at=timezone.now(), resolved_by='student',
            params={'payslip_claim': 'yes'},
        )
        return app

    def _add(self, app, doc_type):
        from django.utils import timezone
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, household_member='father',
            storage_path=f'{app.id}/{doc_type}/x', vision_run_at=timezone.now(),
            vision_fields={'fields': {'name': 'R KANNAN A/L RAMU'}, 'warnings': [],
                           'student_verdict': 'ok', 'error': ''},
        )

    def test_the_request_is_open_with_no_income_document(self):
        from apps.scholarship.check2_queries import _gap_sets
        _, wanted = _gap_sets(self._app('r1'))
        self.assertIn('father_income_proof_missing', wanted)

    def test_an_epf_in_the_epf_slot_clears_it(self):
        # This is what the re-slot buys: the EPF the student uploaded now COUNTS.
        from apps.scholarship.check2_queries import _gap_sets
        app = self._app('r2')
        self._add(app, 'epf')
        _, wanted = _gap_sets(app)
        self.assertNotIn('father_income_proof_missing', wanted)

    def test_a_payslip_clears_it_and_the_epf_request_follows(self):
        # The other branch: a payslip satisfies the request, and the EPF ask follows on its own.
        from apps.scholarship.check2_queries import _gap_sets
        app = self._app('r3')
        self._add(app, 'salary_slip')
        _, wanted = _gap_sets(app)
        self.assertNotIn('father_income_proof_missing', wanted)
        self.assertIn('father_epf_missing', wanted)


class TestTheSlipDecidesWhetherToAskForEpf(TestCase):
    """The payslip answers the question we were guessing at (owner, 2026-07-14).

    KWSP deduction on the slip → he contributes → ask for the statement.
    Slip READ, no KWSP line     → he doesn't → asking would be another dead end.
    No slip scored              → we cannot tell → keep today's behaviour, never silently drop a
                                  legitimate ask.

    This replaces the occupation-keyed guess that trapped #126 twice. The document knows; the job
    title doesn't.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.scholarship.models import ScholarshipCohort
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, uid, *, occupation='driver'):
        from django.utils import timezone
        from apps.courses.models import StudentProfile
        from apps.scholarship.models import ScholarshipApplication
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name='HAVINESH A/L R KANNAN', nric='081211-07-0605',
            preferred_state='Pulau Pinang', household_income=3900, household_size=5,
            receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='profile_complete',
            profile_completed_at=timezone.now(), income_route='salary',
            father_name='R KANNAN A/L RAMU', father_occupation=occupation,
        )

    def _slip(self, app, *, markers):
        from django.utils import timezone
        from apps.scholarship.models import ApplicantDocument
        vf = {'fields': {'name': 'R KANNAN A/L RAMU', 'gross_income': 'RM2400'},
              'warnings': [], 'student_verdict': 'ok', 'error': ''}
        if markers is not None:
            vf['authenticity'] = {'status': 'genuine', 'family': 'private', 'markers': markers}
        return ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', household_member='father',
            storage_path=f'{app.id}/slip/x', vision_run_at=timezone.now(), vision_fields=vf)

    def test_a_slip_with_a_kwsp_line_asks_for_the_epf(self):
        from apps.scholarship.income_engine import (employed_epf_members,
                                                    slip_epf_evidence)
        app = self._app('e1')
        self._slip(app, markers={'statutory': 3, 'wage': 4, 'kwsp': True})
        self.assertEqual(slip_epf_evidence(app, 'father'), 'yes')
        self.assertEqual(employed_epf_members(app), ['father'])

    def test_a_slip_with_no_kwsp_line_does_NOT_ask(self):
        # He doesn't contribute. Demanding a statement he cannot produce is the dead end the
        # ask-first rule exists to prevent.
        from apps.scholarship.income_engine import (employed_epf_members,
                                                    slip_epf_evidence)
        app = self._app('e2')
        self._slip(app, markers={'statutory': 0, 'wage': 3, 'kwsp': False})
        self.assertEqual(slip_epf_evidence(app, 'father'), 'no')
        self.assertEqual(employed_epf_members(app), [])

    def test_an_unscored_slip_falls_back_to_the_occupation_heuristic(self):
        # Legacy slips carry no marker → 'unknown'. The document can't tell us, so the old
        # ask-first caution stands: an informal earner is not chased for an EPF...
        from apps.scholarship.income_engine import (employed_epf_members,
                                                    slip_epf_evidence)
        app = self._app('e3', occupation='driver')      # informal
        self._slip(app, markers=None)
        self.assertEqual(slip_epf_evidence(app, 'father'), 'unknown')
        self.assertEqual(employed_epf_members(app), [])

    def test_an_unscored_slip_still_asks_a_formal_earner(self):
        # ...but a factory operator, whose EPF is standard, still is.
        from apps.scholarship.income_engine import employed_epf_members
        app = self._app('e5', occupation='factory')
        self._slip(app, markers=None)
        self.assertEqual(employed_epf_members(app), ['father'])

    def test_the_job_title_no_longer_decides(self):
        # #126's father is a 'driver' (informal). Once his payslip shows KWSP, his EPF is asked
        # for — the old occupation gate would have stopped the chain dead here.
        from apps.scholarship.income_engine import employed_epf_members
        app = self._app('e4', occupation='driver')
        self._slip(app, markers={'statutory': 2, 'wage': 4, 'kwsp': True})
        self.assertEqual(employed_epf_members(app), ['father'])
