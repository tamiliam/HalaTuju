"""Code health H8 — CHARACTERISATION of every api home of one question:

    "has this household shown what it earns?"

TD-235 says the income rule has four homes and only one of them is ever updated. This file is
the table that proves it, ONE SCENARIO AT A TIME, against the UNCHANGED tree. Nothing here
asserts what the code *should* do — every expected value was read off the code as it stands on
2026-09-19 and is pinned so a later unification cannot move it without saying so.

⚠ THIS IS AN ELIGIBILITY PATH. "Income evidenced?" decides whether a student may submit
(``services.income_doc_blockers``), whether an already-submitted student stays submitted
(``services.application_completeness`` → ``revert_if_profile_incomplete``), what the officer is
asked to chase (``income_engine.household_status_gaps``), and what the verdict paints
(``verdict_engine._verdict_income``). No expected value in this file may be EDITED to make a
refactor green. If a home's answer moves, that is a behaviour change in an eligibility path and
it stops the sprint.

THE HOMES CHARACTERISED HERE (see the sprint report for the full map with file:line)

  H-A  ``income_engine.member_income_evidenced``     — the SERVED answer (owner 2026-07-25:
       income is shown ANY ONE way — a usable payslip, a readable EPF, a declared amount + a
       supporting letter, or a non-breached household STR).
  H-B  ``services.income_doc_blockers``              — may a NOT-YET-SUBMITTED student submit?
       Reads H-A. (Also short-circuits on ``household_str_status`` / ``salary_income_satisfied``.)
  H-C  ``services.application_completeness``         — does an ALREADY-SUBMITTED student still
       read complete? The FROZEN GATE: a 5-June-2026 set of three DOCUMENT TYPES, OR-ed with
       ``any_member_income_evidenced`` since BrightPath #21.
  H-D  ``income_engine.income_requirements`` / ``salary_member_blocks`` — what shall we DRAW?
       A private list of doc-type literals; knows nothing of the fourth way.
  H-E  ``verdict_engine._verdict_income``            — what does the VERDICT say? Re-derives
       "financial evidence present" from ``salary_slip`` / ``epf`` document PRESENCE plus
       ``earner_monthly_income``'s source — it does NOT call H-A.
  H-F  ``income_engine._member_income_documented`` / ``member_income_status`` — what does the
       officer CHASE? Re-derives from ``salary_slip`` / ``epf`` presence. Its blindness to the
       STR is DELIBERATE and documented (owner 2026-07-16, the salary-picture asks).

Every ``# H8-FINDING:`` comment below marks a scenario where two homes disagree TODAY, in
production, on the same household. Those are reported, never silently reconciled.

Fixtures come from the H5 factory (``apps.scholarship.tests.factories``); personal data is
obviously fake.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship import income_engine, services, verdict_engine
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

# ── Document builders ───────────────────────────────────────────────────────────────────────
#: A salary slip whose OCR read a clean monthly gross. No authenticity signal → the
#: ``_salary_slip_not_wrongtype`` fail-open treats it as a real payslip (a legacy/unscored slip
#: must keep counting — that is the documented behaviour, not an oversight).
_SLIP_FIELDS = {'gross': 'RM 1,800.00', 'net': 'RM 1,650.00', 'period': '08/2026'}
#: An EPF statement from which ``_epf_monthly_salary`` CAN derive a figure (employee share ÷ 11%).
_EPF_READABLE = {'employee_contribution_total': 'RM 1,188.00', 'months_counted': '6',
                 'statement_date': '07/2026'}
#: An EPF statement nothing can be read off — present, but it documents nothing.
_EPF_BLANK = {'statement_date': ''}


def _doc(app, doc_type, member='', *, fields=None, authenticity=None, superseded=False,
         name='', nric=''):
    """One stored document. ``fields`` lands under ``vision_fields['fields']`` exactly as the
    extractor writes it; ``authenticity`` under ``vision_fields['authenticity']['status']``."""
    vf = {}
    if fields is not None:
        vf['fields'] = dict(fields)
    if authenticity is not None:
        vf['authenticity'] = {'status': authenticity}
    d = ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member=member,
        storage_path=f'fake/{doc_type}/{member or "household"}/{app.id}',
        vision_fields=vf, vision_name=name, vision_nric=nric,
        vision_run_at=timezone.now() if name or nric else None)
    if superseded:
        ApplicantDocument.objects.filter(id=d.id).update(superseded_at=timezone.now())
        d.refresh_from_db()
    return d


def _str_doc(app, *, status='Lulus', year='2026', source_type='semakan_status',
             recipient_name='', recipient_nric='', authenticity=None, member=''):
    return _doc(app, 'str', member, authenticity=authenticity, fields={
        'status': status, 'year': year, 'source_type': source_type,
        'recipient_name': recipient_name, 'recipient_nric': recipient_nric})


# ── The scenario table ──────────────────────────────────────────────────────────────────────
#: Obviously-fake household. The father's patronymic links him to the student so the
#: relationship arm of ``member_cluster_complete`` is not what any scenario is measuring.
STUDENT_NAME = 'Anbu A/L Devaraj'
FATHER_NAME = 'Devaraj A/L Munusamy'
FATHER_NRIC = '700707-14-5001'


class IncomeHomesBase(TestCase):
    """Builds a household at a named income state and asks EVERY home about it."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)

    def _app(self, *, route='salary', members=('father',), earner='',
             submitted=False, declared=None, father_occupation='private',
             mother_occupation='homemaker', other_family_members=None):
        """An application at the income state a scenario needs.

        ``submitted=True`` walks the factory to ``profile_complete`` — the state that makes
        ``application_completeness`` take its GRANDFATHERED branch (``profile_completed_at``
        is set). ``submitted=False`` leaves it on the live, strict branch.
        """
        student = make_student(name=STUDENT_NAME)
        app = make_application(
            'profile_complete' if submitted else 'submitted',
            cohort=self.cohort, student=student,
            income_route=route,
            income_earner=earner,
            income_working_members=list(members),
            income_declared=dict(declared or {}),
            father_name=FATHER_NAME, father_occupation=father_occupation,
            mother_name='Kamala A/P Suppiah', mother_occupation=mother_occupation,
            other_family_members=list(other_family_members or []),
            siblings_in_school=0, siblings_in_tertiary=0)
        if not submitted:
            # `submitted` stage sets profile_completed_at nowhere, but be explicit: the live
            # branch is keyed on it being NULL and that is what this fixture means.
            self.assertIsNone(app.profile_completed_at)
        return app

    def _ic(self, app, member='father'):
        """The earner's IC, read cleanly and carrying the patronymic that links him."""
        return _doc(app, 'parent_ic', member, name=FATHER_NAME, nric=FATHER_NRIC)

    # ── The six readings, taken the same way for every scenario ─────────────────────────
    def served(self, app, member='father'):
        """H-A — the served answer for one earner."""
        return income_engine.member_income_evidenced(app, member)

    def served_household(self, app):
        """H-A' — the household arm (the one the frozen gate already reads)."""
        return income_engine.any_member_income_evidenced(app)

    def live_gate(self, app, member='father'):
        """H-B — does the LIVE submission gate still want this earner's income evidence?"""
        return f'income_evidence_missing:{member}' in services.income_doc_blockers(app)

    def frozen_gate(self, app):
        """H-C — the already-submitted student's ``documents_done``, with every NON-income
        prerequisite of that branch satisfied, so the reading is about income and nothing else."""
        present = set(app.documents.filter(superseded_at__isnull=True)
                      .values_list('doc_type', flat=True))
        for needed in ('ic', 'results_slip'):
            if needed not in present:
                _doc(app, needed)
        if 'parent_ic' not in present:
            self._ic(app)
        return services.application_completeness(app)['documents_done']

    def drawn(self, app, member='father'):
        """H-D — the doc types the requirement engine tells the student to see for this earner,
        as ``(compulsory, optional)`` doc-type tuples."""
        reqs = income_engine.income_requirements(app)
        for block in reqs['members']:
            if block['member'] == member:
                return ([dt for dt, _tag in block['compulsory']],
                        [dt for dt, _tag in block['optional']])
        return (list(reqs['compulsory']), list(reqs['optional']))

    def verdict(self, app):
        """H-E — the income fact's band plus its unresolved codes."""
        fact = verdict_engine._verdict_income(app)
        return fact['status'], sorted(i['code'] for i in fact['unresolved'])

    def chased(self, app, member='father'):
        """H-F — what the officer-side completeness engine says about this member."""
        return (income_engine._member_income_documented(app, member),
                income_engine.member_income_status(app, member))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 1. THE FOUR WAYS, EACH ALONE  (owner 2026-07-25 — income may be shown ANY ONE way)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestEachWayAlone(IncomeHomesBase):

    def test_way1_usable_payslip(self):
        app = self._app()
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS)
        self.assertIs(self.served(app), True)
        self.assertIs(self.served_household(app), True)
        self.assertIs(self.live_gate(app), False)          # nothing more wanted
        self.assertEqual(self.chased(app), (True, 'satisfied'))
        self.assertEqual(self.drawn(app),
                         (['parent_ic'], ['salary_slip', 'epf']))

    def test_way2_readable_epf(self):
        app = self._app()
        self._ic(app)
        _doc(app, 'epf', 'father', fields=_EPF_READABLE)
        self.assertIs(self.served(app), True)
        self.assertIs(self.live_gate(app), False)
        self.assertEqual(self.chased(app), (True, 'satisfied'))

    def test_way3_declared_amount_plus_supporting_letter(self):
        app = self._app(declared={'father': 1200})
        self._ic(app)
        _doc(app, 'income_support_doc', 'father', fields={'employer': 'Kedai Runcit Aman'})
        # The letter must have READ — `has_income_support_doc` requires student_verdict == 'ok'.
        d = app.documents.get(doc_type='income_support_doc')
        d.vision_fields = {'fields': {'employer': 'Kedai Runcit Aman'}, 'student_verdict': 'ok'}
        d.save(update_fields=['vision_fields'])
        self.assertIs(self.served(app), True)
        self.assertIs(self.live_gate(app), False)
        # H8-FINDING (F1): the served answer says her income IS shown; the officer-side
        # completeness engine says it is NOT and keeps asking the father for a payslip. The
        # fourth way has no document type, and `_member_income_documented` reads document
        # types. Real student: Janani's household (TD-235 incident 2) — a ketua-kampung
        # letter clears the submission gate, then Check 2 chases a payslip she cannot get.
        self.assertEqual(self.chased(app), (False, 'need_proof'))
        # H8-FINDING (F2): the requirement engine still draws only a payslip and an EPF as
        # this earner's optional documents. There is no slot for the letter that actually
        # satisfied the gate — the api-side face of TD-235 incident 2.
        self.assertEqual(self.drawn(app), (['parent_ic'], ['salary_slip', 'epf']))

    def test_way4_non_breached_household_str(self):
        app = self._app()
        self._ic(app)
        _str_doc(app, recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC)
        self.assertIs(self.served(app), True)
        self.assertIs(self.live_gate(app), False)
        # H8-FINDING (F3): the served answer says her income IS shown and lets her submit;
        # the officer-side engine records `need_proof` and keeps chasing the father's payslip.
        # This one is DELIBERATE and documented (owner 2026-07-16) — an STR proves the
        # HOUSEHOLD's welfare status and quantifies nobody's pay, so the salary-picture asks
        # must survive it. Pinned here so a unification cannot erase a difference the owner
        # asked for. (Note the STR arm of `_parent_has_income_evidence` fires only on the STR
        # ROUTE for the DECLARED earner, so on the salary route it cannot apply at all.)
        self.assertEqual(self.chased(app), (False, 'need_proof'))
        self.assertIs(income_engine._member_income_documented(app, 'father'), False)


# ════════════════════════════════════════════════════════════════════════════════════════════
# 2. THE NEAR-MISSES  (each is one ingredient short of a way)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestNearMisses(IncomeHomesBase):

    def test_declared_amount_without_its_letter_is_not_evidence(self):
        app = self._app(declared={'father': 1200})
        self._ic(app)
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)
        self.assertEqual(self.chased(app), (False, 'need_proof'))

    def test_letter_without_a_declared_amount_is_not_evidence(self):
        app = self._app()
        self._ic(app)
        d = _doc(app, 'income_support_doc', 'father', fields={'employer': 'Kedai Runcit Aman'})
        d.vision_fields = {'fields': {'employer': 'Kedai Runcit Aman'}, 'student_verdict': 'ok'}
        d.save(update_fields=['vision_fields'])
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)

    def test_unreadable_epf_is_not_evidence(self):
        app = self._app()
        self._ic(app)
        _doc(app, 'epf', 'father', fields=_EPF_BLANK)
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)
        # H8-FINDING (F4): the officer-side engine counts a BLANK EPF as documented income
        # and stops asking; the gate does not. `_member_income_documented` tests PRESENCE
        # (`_cluster_docs(...).exists()`), the served answer tests READABILITY. Real student:
        # anyone who uploads a black/cropped KWSP page — she is still blocked from submitting
        # while the officer's chase list has gone quiet about her father.
        self.assertEqual(self.chased(app), (True, 'satisfied'))

    def test_not_salary_photo_in_the_payslip_slot_is_not_evidence(self):
        app = self._app()
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS, authenticity='not_salary')
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)
        # H8-FINDING (F5): same split as F4, and this is the one BrightPath #20 is about — a
        # `not_salary` photo. The served answer refuses it (`usable_salary_slip`, the #47 fix);
        # the officer-side engine counts it and marks the father satisfied.
        self.assertEqual(self.chased(app), (True, 'satisfied'))

    def test_superseded_payslip_is_not_evidence_anywhere(self):
        app = self._app()
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS, superseded=True)
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)
        self.assertEqual(self.chased(app), (False, 'need_proof'))

    def test_untagged_payslip_on_the_salary_route_is_not_this_earners_evidence(self):
        # The salary route reads the member TAG only — a blank tag is ambiguous, never
        # attributed (`_cluster_docs`). This is the legacy state BrightPath #20's sweep repairs.
        app = self._app()
        self._ic(app)
        _doc(app, 'salary_slip', '', fields=_SLIP_FIELDS)
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)
        # NOT a finding — the homes AGREE here, and it is worth saying why: the officer-side
        # engine reaches the document through the SAME `_cluster_docs` attribution, so a blank
        # tag is invisible to it too. Attribution has one home already; only READABILITY does
        # not (see F4 / F5).
        self.assertEqual(self.chased(app), (False, 'need_proof'))

    def test_nothing_at_all(self):
        app = self._app()
        self._ic(app)
        self.assertIs(self.served(app), False)
        self.assertIs(self.served_household(app), False)
        self.assertIs(self.live_gate(app), True)
        self.assertEqual(self.chased(app), (False, 'need_proof'))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 3. THE STR LADDER  (a non-breached STR is the fourth way; a breached one is not)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestStrLadder(IncomeHomesBase):

    def _with_str(self, **kw):
        app = self._app()
        self._ic(app)
        _str_doc(app, recipient_name=FATHER_NAME, recipient_nric=FATHER_NRIC, **kw)
        return app

    def test_current_str_evidences_income(self):
        app = self._with_str(status='Lulus', year='2026')
        self.assertIs(self.served(app), True)

    def test_unconfirmed_str_still_evidences_income(self):
        # Approved but dateless → 'unconfirmed'. NOT breached, so it is the fourth way.
        app = self._with_str(status='Lulus', year='')
        self.assertIs(self.served(app), True)
        self.assertIs(income_engine.str_not_breached(app), True)
        self.assertIs(income_engine.str_confirmed_current(app), False)

    def test_stale_str_still_evidences_income(self):
        # A prior-year approval is STALE, and stale is explicitly NOT breached
        # (`str_not_breached` is broader than `has_valid_str`).
        app = self._with_str(status='Lulus', year='2024')
        self.assertIs(self.served(app), True)
        self.assertIs(income_engine.has_valid_str(app), False)
        # H8-FINDING (F7): a STALE STR clears the submission gate but is NOT a dispositive
        # STR — `household_str_status` returns (None, None), so the verdict does not settle
        # on it. Two different STR bars live one function apart. Documented in
        # `str_not_breached`'s own docstring, so this is a pinned intention, not a defect —
        # but it means "the STR way" is not one thing, and a unification must keep both bars.
        self.assertEqual(income_engine.household_str_status(app), (None, None))

    def test_unreadable_str_still_evidences_income(self):
        app = self._with_str(status='', year='')
        self.assertIs(income_engine.str_not_breached(app), True)
        self.assertIs(self.served(app), True)

    def test_rejected_str_does_not_evidence_income(self):
        app = self._with_str(status='Permohonan Ditolak', year='2026')
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)

    def test_wrong_type_str_does_not_evidence_income(self):
        app = self._with_str(status='Lulus', year='2026', source_type='unknown')
        self.assertIs(self.served(app), False)
        self.assertIs(self.live_gate(app), True)

    def test_non_genuine_str_does_not_evidence_income(self):
        app = self._with_str(authenticity='not_str')
        self.assertIs(self.served(app), False)

    def test_str_matching_no_household_member_still_clears_the_gate(self):
        # `str_not_breached` never asks WHO the recipient is; `household_str_status` does.
        app = self._app()
        self._ic(app)
        _str_doc(app, recipient_name='Someone Else Bin Nobody', recipient_nric='999999-14-9999')
        # H8-FINDING (F8): a stranger's STR — a document that proves nothing about this
        # household — satisfies the served income answer, because `str_not_breached` is
        # recipient-agnostic by design (it asks "is the household's STR failed?", not "whose
        # STR is it?"). The verdict's `household_str_status` correctly refuses it. Real
        # student: anybody who uploads a relative's or neighbour's STR screenshot; she
        # submits, and the officer sees an income fact with no STR behind it.
        self.assertIs(self.served(app), True)
        self.assertEqual(income_engine.household_str_status(app), (None, None))


# ════════════════════════════════════════════════════════════════════════════════════════════
# 4. THE FROZEN GATE  (grandfathering: a submitted student is held to the bar in force then)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestFrozenGate(IncomeHomesBase):
    """``application_completeness`` takes a DIFFERENT income bar once ``profile_completed_at``
    is set. Both arms are pinned here, because the whole of TD-235 incident 1 is that the
    frozen arm could not see a way the live rule had gained."""

    def test_legacy_three_types_still_pass_the_frozen_bar(self):
        # The 5-June set: any one of str / salary_slip / epf, by TYPE. A blank EPF is not
        # readable and so is NOT the served fourth way — but it IS in the legacy set, so the
        # frozen bar passes it. That is the grandfather working as designed: a student judged
        # complete in June must not be un-submitted now.
        app = self._app(submitted=True)
        self._ic(app)
        _doc(app, 'epf', 'father', fields=_EPF_BLANK)
        self.assertIs(self.served_household(app), False)     # the modern rule says no
        self.assertIs(self.frozen_gate(app), True)           # the frozen rule says yes
        # H8-FINDING (F9): THE GRANDFATHER CUTS BOTH WAYS, and this is the direction nobody
        # has written down. The frozen arm is STRICTLY MORE PERMISSIVE than the live rule for
        # a document set of {epf-that-reads-nothing}, {salary_slip scored not_salary},
        # {rejected str} and {wrong-type str} — each is in the legacy TYPE set and each fails
        # the modern reading. Replacing the frozen arm with the served answer would NEWLY FAIL
        # these households, and `revert_if_profile_incomplete` un-submits on a fail. The OR
        # in `application_completeness` is therefore load-bearing in BOTH directions and
        # must not be "tidied into one call".

    def test_not_salary_photo_passes_the_frozen_bar_but_not_the_modern_rule(self):
        app = self._app(submitted=True)
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS, authenticity='not_salary')
        self.assertIs(self.served_household(app), False)
        self.assertIs(self.frozen_gate(app), True)

    def test_rejected_str_passes_the_frozen_bar_but_not_the_modern_rule(self):
        app = self._app(submitted=True)
        self._ic(app)
        _str_doc(app, status='Permohonan Ditolak', year='2026')
        self.assertIs(self.served_household(app), False)
        self.assertIs(self.frozen_gate(app), True)

    def test_the_fourth_way_passes_only_through_the_served_arm(self):
        # TD-235 incident 1, application 144: a declared amount + a supporting letter. NO
        # document of a legacy type is on file, so the frozen set is empty and ONLY
        # `any_member_income_evidenced` can carry her.
        app = self._app(submitted=True, declared={'father': 1200})
        self._ic(app)
        d = _doc(app, 'income_support_doc', 'father')
        d.vision_fields = {'fields': {'employer': 'Kedai Runcit Aman'}, 'student_verdict': 'ok'}
        d.save(update_fields=['vision_fields'])
        present = set(app.documents.filter(superseded_at__isnull=True)
                      .values_list('doc_type', flat=True))
        self.assertFalse(present & {'str', 'salary_slip', 'epf'})    # the frozen set is blind
        self.assertIs(self.served_household(app), True)
        self.assertIs(self.frozen_gate(app), True)

    def test_a_submitted_student_with_nothing_fails_both_arms(self):
        app = self._app(submitted=True)
        self._ic(app)
        self.assertIs(self.served_household(app), False)
        self.assertIs(self.frozen_gate(app), False)


# ════════════════════════════════════════════════════════════════════════════════════════════
# 5. HOUSEHOLD SHAPES  (single earner / two earners / guardian / non-salary routes)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestHouseholdShapes(IncomeHomesBase):

    def test_two_earners_one_evidenced(self):
        app = self._app(members=('father', 'mother'), mother_occupation='odd_jobs')
        self._ic(app)
        _doc(app, 'parent_ic', 'mother', name='Kamala A/P Suppiah', nric='750808-14-5002')
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS)
        self.assertIs(self.served(app, 'father'), True)
        self.assertIs(self.served(app, 'mother'), False)
        # The HOUSEHOLD arm is satisfied by one earner...
        self.assertIs(self.served_household(app), True)
        # ...but the LIVE gate is per-member until one cluster is COMPLETE. The father's
        # cluster is complete here (IC reads, name links, income shown), so the gate clears
        # and the mother's gap becomes a soft Check-2 follow-up (owner 2026-07-08).
        self.assertEqual(services.income_doc_blockers(app), [])

    def test_two_earners_neither_evidenced_names_both(self):
        app = self._app(members=('father', 'mother'), mother_occupation='odd_jobs')
        self._ic(app)
        _doc(app, 'parent_ic', 'mother', name='Kamala A/P Suppiah', nric='750808-14-5002')
        blockers = services.income_doc_blockers(app)
        self.assertIn('income_evidence_missing:father', blockers)
        self.assertIn('income_evidence_missing:mother', blockers)

    def test_guardian_route_adds_the_guardianship_letter(self):
        app = self._app(members=('guardian',),
                        other_family_members=[{'role': 'guardian', 'occupation': 'private'}])
        _doc(app, 'parent_ic', 'guardian', name='Rajan A/L Perumal', nric='650606-14-5003')
        _doc(app, 'salary_slip', 'guardian', fields=_SLIP_FIELDS)
        self.assertIs(self.served(app, 'guardian'), True)
        self.assertEqual(self.drawn(app, 'guardian'),
                         (['parent_ic', 'guardianship_letter'], ['salary_slip', 'epf']))
        # Income is shown, but the household relationship doc is still wanted.
        self.assertIn('guardianship_letter_missing', services.income_doc_blockers(app))

    def test_str_route_draws_the_str_triplet_and_never_the_letter(self):
        app = self._app(route='str', members=(), earner='father')
        reqs = income_engine.income_requirements(app)
        self.assertEqual(reqs['route'], 'str')
        self.assertEqual(reqs['compulsory'], ['parent_ic', 'str'])
        self.assertEqual(reqs['optional'],
                         ['water_bill', 'electricity_bill', 'salary_slip', 'epf'])
        self.assertEqual(reqs['members'], [])
        # H8-FINDING (F2, STR face): `income_support_doc` appears in NO branch of the
        # requirement engine, on either route. The one document that carries the owner's
        # fourth way is undrawable — a student can only ever reach it through an Action-Centre
        # request, never through the documents screen.
        self.assertNotIn('income_support_doc', reqs['compulsory'] + reqs['optional'])

    def test_blank_wizard_asks_for_the_earner_ic_only(self):
        app = self._app(route='', members=(), earner='')
        reqs = income_engine.income_requirements(app)
        self.assertEqual(reqs, {'route': '', 'members': [],
                                'compulsory': ['parent_ic'], 'optional': []})
        self.assertEqual(services.income_doc_blockers(app), ['income_incomplete'])

    def test_unemployed_member_is_satisfied_without_any_income_document(self):
        app = self._app(members=('father',), father_occupation='unemployed')
        self._ic(app)
        # The served answer is about EVIDENCE and knows nothing of occupation...
        self.assertIs(self.served(app), False)
        # ...while the officer-side engine reads the roster and is satisfied. Two questions
        # wearing one name: "has she shown what he earns" vs "do we know his economic status".
        self.assertEqual(income_engine.member_income_status(app, 'father'), 'satisfied')

    def test_pensioner_route_reuses_the_payslip_slot(self):
        # ⚠ THE CODE WROTE THIS CODE, NOT THE BRIEF: the occupation is `retired`
        # (`family.BENEFIT_OCC`), and there is no 'pensioner' code at all.
        app = self._app(members=('father',), father_occupation='retired')
        self._ic(app)
        self.assertIn('father', income_engine.pension_members(app))
        # No pension document TYPE exists — the pension statement reuses `salary_slip`
        # (check2_queries: father_pension_proof_missing → doc_type 'salary_slip'), so a
        # pension statement is income evidence through way 1 and no other.
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS)
        self.assertIs(self.served(app), True)

    def test_informal_earner_reaches_evidence_only_through_the_letter(self):
        app = self._app(members=('father',), father_occupation='odd_jobs',
                        declared={'father': 900})
        self._ic(app)
        self.assertIs(income_engine.member_is_informal(app, 'father'), True)
        self.assertIs(self.served(app), False)
        d = _doc(app, 'income_support_doc', 'father')
        d.vision_fields = {'fields': {'employer': 'Pasar Malam'}, 'student_verdict': 'ok'}
        d.save(update_fields=['vision_fields'])
        self.assertIs(self.served(app), True)


# ════════════════════════════════════════════════════════════════════════════════════════════
# 6. THE VERDICT  (H-E re-derives, and this is where it lands differently)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestVerdictHome(IncomeHomesBase):

    def test_not_salary_photo_counts_as_financial_evidence_for_the_verdict(self):
        app = self._app()
        self._ic(app)
        _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS, authenticity='not_salary')
        self.assertIs(self.served(app), False)
        status, codes = self.verdict(app)
        # H8-FINDING (F10): the verdict's `any_financial` is document PRESENCE
        # (`_latest_doc_for_member(application, 'salary_slip', m)`), with no `usable_salary_slip`
        # filter — so a MyKad photographed into the payslip slot reads as financial evidence to
        # the verdict while the gate refuses it. The two disagree about the same document, in
        # the direction that matters least (it cannot block a student) but that still paints an
        # officer's screen with an income fact nothing supports. Real student: application 73.
        self.assertNotIn('income_declared_needs_evidence', codes)
        self.assertIn(status, ('recommend', 'review', 'verified'))

    def test_declared_without_a_letter_reaches_the_verdict_as_amber(self):
        app = self._app(declared={'father': 1200})
        self._ic(app)
        status, codes = self.verdict(app)
        self.assertEqual(status, 'recommend')
        self.assertIn('income_declared_needs_evidence', codes)

    def test_declared_with_a_letter_is_accepted_by_the_verdict(self):
        app = self._app(declared={'father': 1200})
        self._ic(app)
        d = _doc(app, 'income_support_doc', 'father')
        d.vision_fields = {'fields': {'employer': 'Kedai Runcit Aman'}, 'student_verdict': 'ok'}
        d.save(update_fields=['vision_fields'])
        status, codes = self.verdict(app)
        self.assertNotIn('income_declared_needs_evidence', codes)


# ════════════════════════════════════════════════════════════════════════════════════════════
# 7. THE SWEEP  (H-G: "which copy is live" — a different question, pinned so it stays different)
# ════════════════════════════════════════════════════════════════════════════════════════════
class TestOneLiveCopy(IncomeHomesBase):
    """``dedupe_income_proof`` answers WHICH COPY IS LIVE, never whether income is evidenced.
    It legitimately knows document types (they carry different date fields). Pinned because
    the fifth-home guard must not be written in a way that catches it."""

    def test_a_genuine_payslip_is_never_superseded_by_a_not_salary_photo(self):
        app = self._app()
        good = _doc(app, 'salary_slip', 'father', fields=_SLIP_FIELDS)
        bad = _doc(app, 'salary_slip', 'father', fields={'period': '09/2026'},
                   authenticity='not_salary')
        income_engine.dedupe_income_proof(app, 'father', 'salary_slip')
        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertIsNone(good.superseded_at)
        self.assertIsNotNone(bad.superseded_at)

    def test_the_str_dedup_is_household_wide_not_per_member(self):
        app = self._app()
        old = _str_doc(app, year='2024', member='father')
        new = _str_doc(app, year='2026', member='')
        income_engine.dedupe_income_proof(app, 'mother', 'str')     # note: a DIFFERENT member
        old.refresh_from_db()
        new.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)
        self.assertIsNone(new.superseded_at)
        # The kept blank-tagged copy inherits the superseded sibling's recipient attribution.
        self.assertEqual(new.household_member, 'father')
