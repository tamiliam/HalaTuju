"""TD-262 chunks 2+3 — the ONE per-earner answer, over the whole scenario table.

``income_shown.income_shown(application, member)`` answers *has this earner's income been
SHOWN?* — the owner's three per-earner ways (a usable payslip · a readable EPF · a declared
amount + a supporting letter that READ), and **no STR arm**, because an STR is evidence about
the HOUSEHOLD (owner 2026-09-19, ``docs/decisions.md``).

What this file holds that the characterisation suite does not:
  * every ``unusable`` reason code, produced by the state the predicates actually test — so a
    code can never be invented on the officer's screen with nothing able to emit it;
  * the EQUIVALENCE that makes the refactor safe: ``member_income_evidenced`` is exactly
    ``income_shown(...).shown or str_not_breached(...)``, asserted scenario by scenario against
    the three predicates that used to be OR-ed inline;
  * the SHAPE of the served payload the officer cockpit reads
    (``halatuju-web/src/lib/incomeShown.ts``).

Fixtures come from the H5 factory; personal data is obviously fake.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship import income_engine, income_shown as isx
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

#: A payslip whose OCR read a clean monthly gross (the same shape the homes suite pins).
_SLIP_FIELDS = {'gross': 'RM 1,800.00', 'net': 'RM 1,650.00', 'period': '08/2026'}
#: An EPF statement a monthly figure CAN be derived from (employee share / 11%).
_EPF_READABLE = {'employee_contribution_total': 'RM 1,188.00', 'months_counted': '6',
                 'statement_date': '07/2026'}
#: An EPF statement nothing can be read off — present, but it documents nothing.
_EPF_BLANK = {'statement_date': ''}

STUDENT_NAME = 'Anbu A/L Devaraj'
FATHER_NAME = 'Devaraj A/L Munusamy'


class IncomeShownBase(TestCase):
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

    def answer(self, app, member='father'):
        return isx.income_shown(app, member)

    def reasons(self, app, member='father'):
        """``{doc_id: reason}`` — what the officer's screen will mark, and why."""
        return {u.doc_id: u.reason for u in self.answer(app, member).unusable}


# ════════════════════════════════════════════════════════════════════════════════════════════
# 1. THE THREE WAYS, EACH ALONE — and which documents carry them
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheThreeWays(IncomeShownBase):

    def test_a_usable_payslip(self):
        app = self._app()
        slip = self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        a = self.answer(app)
        self.assertIs(a.shown, True)
        self.assertEqual(a.way, isx.WAY_SALARY_SLIP)
        self.assertEqual(a.documents, (slip.id,))
        self.assertEqual(a.unusable, ())

    def test_a_readable_epf(self):
        app = self._app()
        epf = self._doc(app, 'epf', fields=_EPF_READABLE)
        a = self.answer(app)
        self.assertIs(a.shown, True)
        self.assertEqual((a.way, a.documents), (isx.WAY_EPF, (epf.id,)))

    def test_a_declared_amount_and_a_letter_that_read(self):
        app = self._app(declared={'father': 1200})
        letter = self._doc(app, 'income_support_doc', fields={'employer': 'Kedai Runcit Aman'},
                           student_verdict='ok')
        a = self.answer(app)
        self.assertIs(a.shown, True)
        self.assertEqual((a.way, a.documents), (isx.WAY_DECLARED_LETTER, (letter.id,)))

    def test_nothing_at_all_is_not_shown_and_names_nothing(self):
        app = self._app()
        self.assertEqual(self.answer(app), isx.IncomeShown(False, None, (), ()))

    def test_the_payslip_wins_the_way_when_several_documents_could(self):
        # The arm ORDER is ``member_income_evidenced``'s own, so the two can never name
        # different winners for one household.
        app = self._app(declared={'father': 1200})
        slip = self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        self._doc(app, 'epf', fields=_EPF_READABLE)
        self._doc(app, 'income_support_doc', fields={'employer': 'X'}, student_verdict='ok')
        a = self.answer(app)
        self.assertEqual((a.way, a.documents), (isx.WAY_SALARY_SLIP, (slip.id,)))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 2. EVERY REASON CODE — each produced by the state its own predicate tests
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheUnusableVocabulary(IncomeShownBase):

    def test_not_salary_a_mykad_in_the_payslip_slot(self):
        app = self._app()
        slip = self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
        self.assertIs(self.answer(app).shown, False)
        self.assertEqual(self.reasons(app), {slip.id: isx.REASON_NOT_SALARY})

    def test_no_value_an_epf_nothing_can_be_read_off(self):
        app = self._app()
        epf = self._doc(app, 'epf', fields=_EPF_BLANK)
        self.assertIs(self.answer(app).shown, False)
        self.assertEqual(self.reasons(app), {epf.id: isx.REASON_NO_VALUE})

    def test_letter_unread_a_blank_image_cannot_prove_a_wage(self):
        app = self._app(declared={'father': 1200})
        letter = self._doc(app, 'income_support_doc', fields={'employer': 'X'})
        self.assertIs(self.answer(app).shown, False)
        self.assertEqual(self.reasons(app), {letter.id: isx.REASON_LETTER_UNREAD})

    def test_no_declared_amount_a_letter_with_nothing_to_back(self):
        app = self._app()           # no declared amount
        letter = self._doc(app, 'income_support_doc', fields={'employer': 'X'},
                           student_verdict='ok')
        self.assertIs(self.answer(app).shown, False)
        self.assertEqual(self.reasons(app), {letter.id: isx.REASON_NO_DECLARED_AMOUNT})

    def test_an_unusable_document_is_still_named_when_another_way_carries_the_income(self):
        # The officer must see that the blank EPF is not doing anything, even though the
        # payslip is — a document that reads as evidence and is not is the whole defect.
        app = self._app()
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        epf = self._doc(app, 'epf', fields=_EPF_BLANK)
        self.assertIs(self.answer(app).shown, True)
        self.assertEqual(self.reasons(app), {epf.id: isx.REASON_NO_VALUE})

    def test_every_reason_a_document_can_carry_is_in_the_served_vocabulary(self):
        # A code the web has no label for renders a raw dotted path on an officer's screen.
        app = self._app()
        self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
        self._doc(app, 'epf', fields=_EPF_BLANK)
        self._doc(app, 'income_support_doc', fields={'employer': 'X'}, student_verdict='ok')
        self.assertTrue(set(self.reasons(app).values()) <= set(isx.REASONS))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 3. NO STR ARM — the owner's ruling, and the gate's OR that keeps the answer unchanged
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestNoStrArm(IncomeShownBase):

    def test_a_household_str_never_shows_an_earners_income(self):
        # ⚠ owner 2026-09-19: an STR is evidence about the HOUSEHOLD; a working adult's income
        # proof is ADDITIONAL to it. Adding a fourth arm here silences the salary-picture asks
        # (F3) and turns a per-earner cue green on a fact about somebody else.
        app = self._app()
        self._str(app)
        self.assertIs(income_engine.str_not_breached(app), True)
        self.assertIs(self.answer(app).shown, False)
        # …and the GATE is unmoved, because it ORs the household arm on itself.
        self.assertIs(income_engine.member_income_evidenced(app, 'father'), True)

    def test_the_gate_answer_is_exactly_shown_or_str_not_breached(self):
        """The equivalence that makes the extraction safe — over the whole table."""
        def build(case):
            app = self._app(declared={'father': 1200} if 'declared' in case else None)
            if 'slip' in case:
                self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
            if 'bad_slip' in case:
                self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
            if 'epf' in case:
                self._doc(app, 'epf', fields=_EPF_READABLE)
            if 'blank_epf' in case:
                self._doc(app, 'epf', fields=_EPF_BLANK)
            if 'letter' in case:
                self._doc(app, 'income_support_doc', fields={'employer': 'X'},
                          student_verdict='ok')
            if 'str' in case:
                self._str(app)
            return app

        for case in (frozenset(), {'slip'}, {'bad_slip'}, {'epf'}, {'blank_epf'},
                     {'declared'}, {'letter'}, {'declared', 'letter'},
                     {'declared', 'letter', 'str'}, {'bad_slip', 'str'}, {'str'},
                     {'bad_slip', 'declared', 'letter'}):
            with self.subTest(case=sorted(case)):
                app = build(case)
                shown = isx.income_shown(app, 'father').shown
                # The three arms as they were written inline before the extraction.
                inline = (income_engine.usable_salary_slip(app, 'father')
                          or income_engine._member_has_epf_value(app, 'father')
                          or (income_engine.declared_amount(app, 'father') is not None
                              and income_engine.has_income_support_doc(app, 'father')))
                self.assertIs(shown, inline)
                self.assertIs(income_engine.member_income_evidenced(app, 'father'),
                              shown or income_engine.str_not_breached(app))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 4. THE SERVED PAYLOAD — the shape the officer cockpit reads
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestServedPerEarnerAnswer(IncomeShownBase):
    """Pins the JSON the cockpit's `@/lib/incomeShown` types against. The web suite
    (`src/lib/__tests__/incomeEvidenceHomes.test.ts`) builds its served fixtures by hand, so
    this is what stops the two drifting."""

    def test_the_map_carries_one_entry_per_roster_member_code(self):
        app = self._app()
        served = isx.income_shown_map(app, income_engine._MEMBER_ORDER)
        self.assertEqual(sorted(served), sorted(income_engine._MEMBER_ORDER))

    def test_an_entry_names_the_keys_the_web_reads(self):
        app = self._app()
        slip = self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
        entry = isx.income_shown_map(app, ('father',))['father']
        self.assertEqual(entry, {
            'shown': False, 'way': None, 'documents': [],
            'unusable': [{'doc_id': slip.id, 'doc_type': 'salary_slip', 'reason': 'not_salary'}],
        })

    def test_a_shown_entry_names_the_way_and_the_documents_that_carry_it(self):
        app = self._app()
        slip = self._doc(app, 'salary_slip', fields=_SLIP_FIELDS)
        self.assertEqual(isx.income_shown_map(app, ('father',))['father'], {
            'shown': True, 'way': 'salary_slip', 'documents': [slip.id], 'unusable': []})


# ════════════════════════════════════════════════════════════════════════════════════════════
# 5. THE STUDENT'S OWN PAYLOAD — the same answer, on her side of the fence (TD-262 F2)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestTheStudentPayloadServesIt(IncomeShownBase):
    """Her income wizard decides whether to offer the cash/informal door. It used to decide from
    document PRESENCE, so a payslip nothing could be read off closed the door on the very family
    that needed it (F2, the lockout). It reads this instead — one shape, both screens."""

    def _payload(self, app):
        from apps.scholarship.serializers import ApplicationReadSerializer
        return ApplicationReadSerializer(app).data

    def test_her_payload_carries_one_entry_per_roster_member_code(self):
        served = self._payload(self._app())['income_shown']
        self.assertEqual(sorted(served), sorted(income_engine._MEMBER_ORDER))

    def test_an_unusable_payslip_reads_as_not_shown_and_names_its_reason(self):
        # ⚠ THE LOCKOUT ROW. Before F2 her screen saw a file and closed the cash door; the
        # server saw nothing it could read. This is the disagreement, ended.
        app = self._app()
        slip = self._doc(app, 'salary_slip', fields=_SLIP_FIELDS, authenticity='not_salary')
        self.assertEqual(self._payload(app)['income_shown']['father'], {
            'shown': False, 'way': None, 'documents': [],
            'unusable': [{'doc_id': slip.id, 'doc_type': 'salary_slip', 'reason': 'not_salary'}],
        })

    def test_both_payloads_answer_identically(self):
        # One rule, one home: the officer's and the student's screens can never be told
        # different things about the same earner.
        from apps.scholarship.serializers import ApplicationReadSerializer
        app = self._app(declared={'father': 1200})
        self._doc(app, 'epf', fields=_EPF_BLANK)
        self._doc(app, 'income_support_doc', fields={'employer': 'X'}, student_verdict='ok')
        self.assertEqual(ApplicationReadSerializer(app).data['income_shown'],
                         isx.income_shown_map(app, income_engine._MEMBER_ORDER))
