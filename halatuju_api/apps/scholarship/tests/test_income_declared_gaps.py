"""TD-262 F2 — the declared-income chase, over the whole scenario table.

``declared_income_gaps(application)`` decides whether Check 2 asks a working member for an
``income_support_doc`` because they DECLARED a wage the household has not yet backed. It is the
only reader of that gap (``check2_queries._gap_sets`` →
``declared_income_evidence_missing``).

**The defect this file was written for (F2, the dead-end chase).** The gap fired on a declared
amount alone — a member who had typed a figure and then uploaded a perfectly good payslip was
still chased for a letter they do not need. Paired with the student screen's presence-only
lockout (which hid the cash panel the moment any salary/EPF file existed, usable or not), the
family could neither clear the chase nor retract the figure.

**What decides it now.** No gap is raised for a member whose income is ALREADY SHOWN another
way — the owner's per-earner answer (``income_shown``: a usable payslip · a readable EPF · a
declared amount + a letter that READ), the same answer the submission gate, the chase list and
the AI verdict read. It is deliberately the SHOWN answer and not document presence: a
``not_salary`` photo or a blank EPF shows nothing, so that household is still asked — which is
the F4 / F5 silence this arc has been closing everywhere else.

⚠ NOTHING ABOUT ELIGIBILITY MOVES HERE. This is a Check-2 ASK, not a gate and not a verdict: a
member's ability to submit and every fact on the AI card are untouched, and the rows below that
pin the STR short-circuit and the route guard are byte-identical to the behaviour before F2.

Fixtures come from the H5 factory; personal data is obviously fake.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship import income_engine
from apps.scholarship.income_declared_gaps import declared_income_gaps
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

#: A payslip whose OCR read a clean monthly gross.
_SLIP_FIELDS = {'gross': 'RM 1,800.00', 'net': 'RM 1,650.00', 'period': '08/2026'}
#: An EPF statement a monthly figure CAN be derived from (employee share / 11%).
_EPF_READABLE = {'employee_contribution_total': 'RM 1,188.00', 'months_counted': '6',
                 'statement_date': '07/2026'}
#: An EPF statement nothing can be read off — present, but it documents nothing.
_EPF_BLANK = {'statement_date': ''}

STUDENT_NAME = 'Anbu A/L Devaraj'
FATHER_NAME = 'Devaraj A/L Munusamy'


class DeclaredGapsBase(TestCase):
    """One salary-route household with a working father, at whatever income state a test needs."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)

    def _app(self, *, declared=None, route='salary', members=('father',)):
        return make_application(
            'submitted', cohort=self.cohort, student=make_student(name=STUDENT_NAME),
            income_route=route, income_earner='', income_working_members=list(members),
            income_declared=dict(declared or {}),
            father_name=FATHER_NAME, father_occupation='private',
            mother_name='Kamala A/P Suppiah', mother_occupation='homemaker',
            other_family_members=[], siblings_in_school=0, siblings_in_tertiary=0)

    def _doc(self, app, doc_type, member='father', *, fields=None, authenticity=None,
             student_verdict=None):
        vf = {}
        if fields is not None:
            vf['fields'] = dict(fields)
        if authenticity is not None:
            vf['authenticity'] = {'status': authenticity}
        if student_verdict is not None:
            vf['student_verdict'] = student_verdict
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, household_member=member,
            storage_path=f'fake/{doc_type}/{member or "household"}/{app.id}', vision_fields=vf)

    def _str(self, app):
        return ApplicantDocument.objects.create(
            application=app, doc_type='str', household_member='',
            storage_path=f'fake/str/household/{app.id}',
            vision_fields={'fields': {'status': 'Lulus', 'year': '2026',
                                      'source_type': 'semakan_status',
                                      'recipient_name': FATHER_NAME, 'recipient_nric': ''}},
            vision_run_at=timezone.now())

    def gaps(self, app):
        return declared_income_gaps(app)


# ════════════════════════════════════════════════════════════════════════════════════════════
# 1. THE SCENARIO TABLE — one row per state a real family can be in
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheDeclaredIncomeChase(DeclaredGapsBase):

    def test_an_amount_and_a_good_payslip_is_not_chased(self):
        # ⚠ THE F2 DEFECT, IN ONE ROW. The family typed a figure, then uploaded a payslip that
        # read. Their income is SHOWN; asking them for a letter as well is a chase with no
        # question behind it — and, with the screen's old lockout, one they could not answer.
        app = self._app(declared={'father': 1200})
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        self.assertEqual(self.gaps(app), [])

    def test_an_amount_and_a_readable_epf_is_not_chased(self):
        app = self._app(declared={'father': 1200})
        self._doc(app, 'epf', fields=_EPF_READABLE)
        self.assertEqual(self.gaps(app), [])

    def test_an_amount_with_nothing_behind_it_is_chased(self):
        # The gap's whole reason for existing: a declared wage and no evidence at all.
        app = self._app(declared={'father': 1200})
        self.assertEqual(self.gaps(app), [{'member': 'father'}])

    def test_a_letter_with_no_amount_is_not_chased(self):
        # Nothing was declared, so there is nothing to back — the letter sits on file unasked-for.
        app = self._app()
        self._doc(app, 'income_support_doc', fields={'employer': 'Kedai Runcit Aman'},
                  student_verdict='ok')
        self.assertEqual(self.gaps(app), [])

    def test_an_amount_and_a_letter_that_read_is_not_chased(self):
        app = self._app(declared={'father': 1200})
        self._doc(app, 'income_support_doc', fields={'employer': 'Kedai Runcit Aman'},
                  student_verdict='ok')
        self.assertEqual(self.gaps(app), [])

    def test_all_three_ways_at_once_is_not_chased(self):
        app = self._app(declared={'father': 1200})
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        self._doc(app, 'epf', fields=_EPF_READABLE)
        self._doc(app, 'income_support_doc', fields={'employer': 'Kedai Runcit Aman'},
                  student_verdict='ok')
        self.assertEqual(self.gaps(app), [])

    def test_a_member_with_nothing_at_all_is_not_chased(self):
        # No declared amount → no gap. The household's income asks come from elsewhere
        # (``household_status_gaps`` / the per-member proof codes), never from here.
        app = self._app()
        self.assertEqual(self.gaps(app), [])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 2. SHOWN, NOT PRESENT — a document that cannot carry the income does not stop the ask
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestAnUnusableDocumentIsNotEvidence(DeclaredGapsBase):
    """⚠ The F4 / F5 rule, applied here too. Silencing the ask on document PRESENCE would let a
    MyKad photographed into the payslip slot end the conversation about what the family earns."""

    def test_a_not_salary_photo_does_not_stop_the_ask(self):
        app = self._app(declared={'father': 1200})
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
        self.assertEqual(self.gaps(app), [{'member': 'father'}])

    def test_a_blank_epf_does_not_stop_the_ask(self):
        app = self._app(declared={'father': 1200})
        self._doc(app, 'epf', fields=_EPF_BLANK)
        self.assertEqual(self.gaps(app), [{'member': 'father'}])

    def test_a_letter_that_never_read_does_not_stop_the_ask(self):
        # V1 finding #2, pinned again from this side: a blank image must not clear the gap.
        app = self._app(declared={'father': 1200})
        self._doc(app, 'income_support_doc', fields={'employer': 'X'})
        self.assertEqual(self.gaps(app), [{'member': 'father'}])

    def test_an_unusable_payslip_beside_a_good_letter_is_still_not_chased(self):
        # The dud slip is noise; the letter answers the question.
        app = self._app(declared={'father': 1200})
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
        self._doc(app, 'income_support_doc', fields={'employer': 'Kedai Runcit Aman'},
                  student_verdict='ok')
        self.assertEqual(self.gaps(app), [])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 3. THE TWO SHORT-CIRCUITS — byte-unchanged by F2, and RULED, not merely inherited
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheShortCircuits(DeclaredGapsBase):
    """⛔ THESE ARE DECISIONS. Owner, 2026-09-20: *"If STR has been fulfilled, there is no need
    for the student to complete the cash door. It is there primarily for those without STR or
    salary slip."* So the cash door is never added to the STR route, and a household holding a
    valid STR is never chased for a letter. The fourth way is for households with NEITHER a
    current STR NOR a payslip. Do not "complete" either early return (`docs/decisions.md`)."""

    def test_a_valid_str_accepts_every_declared_amount_at_once(self):
        app = self._app(declared={'father': 1200, 'mother': 800}, members=('father', 'mother'))
        self._str(app)
        self.assertIs(income_engine.has_valid_str(app), True)
        self.assertEqual(self.gaps(app), [])

    def test_off_the_salary_route_there_is_no_declared_chase(self):
        app = self._app(declared={'father': 1200}, route='str')
        self.assertEqual(self.gaps(app), [])

    def test_a_blank_route_raises_nothing(self):
        app = self._app(declared={'father': 1200}, route='')
        self.assertEqual(self.gaps(app), [])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 4. TWO EARNERS — the answer is per member, and one member's payslip never covers the other
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestPerMember(DeclaredGapsBase):

    def test_the_fathers_payslip_does_not_answer_for_the_mother(self):
        app = self._app(declared={'father': 1200, 'mother': 700},
                        members=('father', 'mother'))
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)          # father's
        self.assertEqual(self.gaps(app), [{'member': 'mother'}])

    def test_one_untagged_letter_answers_for_both(self):
        # ⚠ Looks like a bug and is not: ``has_income_support_doc`` counts an UNTAGGED
        # household letter for every earner, and the owner's line on the student's screen says
        # so out loud — "One letter is enough for the whole family."
        app = self._app(declared={'father': 1200, 'mother': 700},
                        members=('father', 'mother'))
        self._doc(app, 'income_support_doc', member='',
                  fields={'employer': 'Kedai Runcit Aman'}, student_verdict='ok')
        self.assertEqual(self.gaps(app), [])


# ════════════════════════════════════════════════════════════════════════════════════════════
# 5. WHAT CHECK 2 ACTUALLY ASKS — the gap's only reader
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheCheck2Request(DeclaredGapsBase):
    """The chase is invisible until it becomes a code in ``proof_wanted``; this is the wire."""

    def _proof_wanted(self, app):
        from apps.scholarship.check2_queries import _gap_sets
        return _gap_sets(app)[1]

    def test_a_declared_amount_with_nothing_behind_it_asks_for_a_letter(self):
        app = self._app(declared={'father': 1200})
        self.assertIn('declared_income_evidence_missing', self._proof_wanted(app))

    def test_a_good_payslip_means_check_2_never_asks(self):
        # ⚠ THE F2 DEFECT AS THE OFFICER AND THE STUDENT SEE IT — the request that used to
        # appear in the Action Centre for a family who had already answered.
        app = self._app(declared={'father': 1200})
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        self.assertNotIn('declared_income_evidence_missing', self._proof_wanted(app))
