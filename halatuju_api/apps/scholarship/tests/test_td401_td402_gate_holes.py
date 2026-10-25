"""TD-401 and TD-402 — an identity hole and a money hole in the submission gate, both live until now.

**TD-401 (identity).** A student MyKad read with a NAME but no NRIC passed `ic_identity_blockers`: the
name matched, nothing checked the number. Owner's hard-gate ruling: identity rests on a verified NRIC,
so a card whose NRIC did not read is "re-upload a clearer photo" (`ic_unreadable`) — also when the
profile has no NRIC to compare, because the identity must rest on the CARD's number.

**TD-402 (money).** STR route: the student points `income_earner` at the mother and never uploads her
IC; the father's clean card links to the student; the STR names a stranger. The stranger rule cannot
judge (the earner is unread — F1), and the gate's "one complete cluster is enough" early return let
the father's cluster through on the household-STR arm alone, before `parent_ic_missing:mother` could
surface. Owner rule (with TD-394): a money gate never passes on a document nobody has matched.

Lead's production count (2026-10-25): ZERO live student ICs carry a name with no NRIC and no error, so
TD-401 newly blocks nobody already in flight.
"""
from django.test import TestCase

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student
from django.utils import timezone

STUDENT_NRIC = '060606-14-1234'
STUDENT = 'Anbu A/L Devaraj'
FATHER, FATHER_NRIC = 'Devaraj A/L Munusamy', '700707-14-5671'
MOTHER, MOTHER_NRIC = 'Kamala A/P Suppiah', '720808-14-5682'
STRANGER, STRANGER_NRIC = 'Lim Ah Kow', '650303-07-5123'


def _doc(app, doc_type, **kw):
    kw.setdefault('storage_path', f'test/{doc_type}/{ApplicantDocument.objects.count()}')
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type, **kw)


class TheStudentsIcMustReadItsNric(TestCase):
    def _app(self, nric=STUDENT_NRIC):
        return make_application('shortlisted', student=make_student(nric=nric, name=STUDENT))

    def _ic(self, app, nric):
        return _doc(app, 'ic', vision_run_at=timezone.now(), vision_name=STUDENT.upper(), vision_nric=nric)

    def test_a_name_without_an_nric_is_unreadable_and_blocks(self):
        from apps.scholarship.resolution import STUDENT_DOC_REQUEST_CODES, _ticketable_unresolved
        from apps.scholarship.services import consent_blockers, ic_identity_blockers
        from apps.scholarship.verdict_engine import build_verdict
        app = self._app()
        self._ic(app, nric='')
        self.assertEqual(ic_identity_blockers(app), ['ic_unreadable'])
        self.assertIn('ic_unreadable', consent_blockers(app))
        identity = next(f for f in build_verdict(app) if f['fact'] == 'identity')
        self.assertEqual(identity['status'], 'gap')                   # the verdict agrees with the gate
        self.assertIn('ic_unreadable', set(_ticketable_unresolved(app)) & STUDENT_DOC_REQUEST_CODES)

    def test_it_blocks_even_when_the_profile_has_no_nric_to_compare(self):
        from apps.scholarship.services import ic_identity_blockers
        app = self._app(nric='')
        self._ic(app, nric='')
        self.assertEqual(ic_identity_blockers(app), ['ic_unreadable'])

    def test_a_card_whose_nric_reads_and_matches_still_passes(self):
        from apps.scholarship.services import ic_identity_blockers
        app = self._app()
        self._ic(app, nric=STUDENT_NRIC)
        self.assertEqual(ic_identity_blockers(app), [])

    def test_the_other_readers_already_said_unreadable(self):
        """The gate was the odd one out: the coach, the request verdict and the student's chip all
        treated a card with no NRIC as unreadable already."""
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.resolution import doc_match_verdict
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        app = self._app()
        ic = self._ic(app, nric='')
        self.assertEqual(verdict_for_document(ic), 'unreadable')
        self.assertEqual(doc_match_verdict(ic), 'unreadable')
        self.assertEqual(ApplicantDocumentSerializer(ic).data['vision_nric_verdict'], 'unreadable')



class AnStrNobodyMatchedCarriesNoClusterPastTheGate(TestCase):
    def _app(self, *, earner, route='str', members=()):
        return make_application(
            'profile_complete', income_route=route, income_earner=earner,
            income_working_members=list(members), father_name=FATHER, mother_name=MOTHER,
            father_occupation='private', mother_occupation='homemaker', other_family_members=[],
            student=make_student(nric=STUDENT_NRIC, name=STUDENT))

    def _card(self, app, member, name, nric):
        return _doc(app, 'parent_ic', household_member=member, vision_run_at=timezone.now(),
                    vision_name=name.upper(), vision_nric=nric)

    def _str(self, app, name, nric, member=''):
        return _doc(app, 'str', household_member=member, vision_fields={
            'fields': {'recipient_name': name.upper(), 'recipient_nric': nric, 'status': 'Lulus',
                       'year': '2026', 'source_type': 'semakan_status'},
            'student_verdict': 'ok', 'error': ''})

    def test_the_reviewers_scenario_blocks_on_the_earners_missing_ic(self):
        from apps.scholarship.services import consent_blockers, income_doc_blockers
        app = self._app(earner='mother')                       # re-pointed; her IC never uploaded
        self._card(app, 'father', FATHER, FATHER_NRIC)         # clean, patronymic-linked
        self._str(app, STRANGER, STRANGER_NRIC)
        out = income_doc_blockers(app)
        self.assertIn('parent_ic_missing:mother', out)
        self.assertIn('parent_ic_missing:mother', consent_blockers(app))    # the consent door
        from apps.scholarship.services import application_completeness, reconcile_income_route
        self.assertIs(application_completeness(app)['documents_done'], False)   # the submit door
        # The consent-time route reconcile reads the gate's rule too: an STR nobody matched never
        # "proves" a salary cluster that would move this household onto the salary route.
        self.assertEqual(reconcile_income_route(app, by='test'), 'str')

    def test_a_genuine_family_still_passes(self):
        from apps.scholarship.services import income_doc_blockers
        app = self._app(earner='mother')
        self._card(app, 'mother', MOTHER, MOTHER_NRIC)
        _doc(app, 'birth_certificate', vision_fields={
            'fields': {'bc_child_name': STUDENT, 'bc_mother_name': MOTHER, 'bc_mother_nric': MOTHER_NRIC},
            'student_verdict': 'ok', 'error': ''})
        self._str(app, MOTHER, MOTHER_NRIC)
        self.assertEqual(income_doc_blockers(app), [])

    def test_a_cluster_whose_income_shows_on_its_own_still_skips_the_str_triplet(self):
        """Owner 2026-07-22, unchanged: a fully documented earner settles income on its own."""
        from apps.scholarship.services import income_doc_blockers
        app = self._app(earner='mother')
        self._card(app, 'father', FATHER, FATHER_NRIC)
        _doc(app, 'salary_slip', household_member='father', vision_fields={
            'fields': {'name': FATHER.upper(), 'nric': FATHER_NRIC, 'gross_income': '2500',
                       'period': '09/2026'}, 'student_verdict': 'ok', 'error': ''})
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertEqual(income_doc_blockers(app), [])

    def test_the_verdict_reading_is_untouched(self):
        """F8 / TD-402 are GATE rulings: the predicate the verdict reads stays recipient-agnostic."""
        from apps.scholarship.income_engine import salary_income_satisfied
        app = self._app(earner='mother')
        self._card(app, 'father', FATHER, FATHER_NRIC)
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertIs(salary_income_satisfied(app), True)
        self.assertIs(salary_income_satisfied(app, str_must_match=True), False)

    def test_the_salary_route_early_return_uses_the_same_rule(self):
        """Salary route, father working, his clean card linked, no payslip, an STR no card matched:
        the early return no longer fires, and (owner ruling 2026-10-25, below) neither does the
        per-member reading let the unmatched STR stand in for his income."""
        from apps.scholarship.income_engine import salary_income_satisfied
        from apps.scholarship.services import income_doc_blockers
        app = self._app(earner='', route='salary', members=('father',))
        self._card(app, 'father', FATHER, FATHER_NRIC)
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertIs(salary_income_satisfied(app, str_must_match=True), False)
        # A second working member whose IC never arrived: the early return used to wave the whole
        # household through on the father's STR-carried cluster; now her missing IC is asked.
        app.income_working_members = ['father', 'mother']
        app.save(update_fields=['income_working_members'])
        self.assertIn('parent_ic_missing:mother', income_doc_blockers(app))


class AnUnmatchedStrIsNoWorkingMembersIncomeProofEither(TestCase):
    """Owner ruling 2026-10-25 (option A), ONE rule on BOTH routes, superseding F1 FOR THE GATE: an
    STR is income proof only when a card MATCHED its recipient. Unmatched, the gate asks for the IC of
    the roster member who could settle it (the Documents page offers that card, TD-309); with every
    card on file, the stranger rule's answer, or a clearer document. The verdict keeps F1's reading."""

    def _app(self, *, route='salary', earner='', working=('mother',), mother_occ='private'):
        return make_application(
            'profile_complete', income_route=route, income_earner=earner,
            income_working_members=list(working), father_name=FATHER, mother_name=MOTHER,
            father_occupation='private', mother_occupation=mother_occ, other_family_members=[],
            student=make_student(nric=STUDENT_NRIC, name=STUDENT))

    def _father_ic(self, app):
        _doc(app, 'parent_ic', household_member='father', vision_run_at=timezone.now(),
             vision_name=FATHER.upper(), vision_nric=FATHER_NRIC)

    def _mother_cluster(self, app):
        """The mother's clean, linked cluster with NO payslip: her IC + the birth certificate."""
        _doc(app, 'parent_ic', household_member='mother', vision_run_at=timezone.now(),
             vision_name=MOTHER.upper(), vision_nric=MOTHER_NRIC)
        _doc(app, 'birth_certificate', vision_fields={
            'fields': {'bc_child_name': STUDENT, 'bc_mother_name': MOTHER, 'bc_mother_nric': MOTHER_NRIC},
            'student_verdict': 'ok', 'error': ''})

    def _str(self, app, name, nric):
        return _doc(app, 'str', vision_fields={
            'fields': {'recipient_name': name.upper(), 'recipient_nric': nric, 'status': 'Lulus',
                       'year': '2026', 'source_type': 'semakan_status'},
            'student_verdict': 'ok', 'error': ''})

    def test_probe_1_a_strangers_str_nobody_could_judge_now_blocks(self):
        """Father on the form with no IC (so F1 cannot judge), mother working with no payslip. Only
        the father's card could settle whose STR it is, so the gate asks for it — the card the
        Documents page offers (`ic_slots`); once it lands and mismatches, it is 1b."""
        from apps.scholarship.income_shown import income_shown
        from apps.scholarship.income_str_ownership import str_owner_ic_asks
        from apps.scholarship.services import consent_blockers, income_doc_blockers
        app = self._app()
        self._mother_cluster(app)
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertEqual(income_doc_blockers(app), ['parent_ic_missing:father'])
        self.assertIn('parent_ic_missing:father', consent_blockers(app))
        self.assertEqual(str_owner_ic_asks(app)['missing'], ['father'])   # the page's slot, same rule
        # The student's own income cue already said "not shown" — the surfaces now agree.
        self.assertFalse(income_shown(app, 'mother').shown)

    def test_probe_1b_a_judged_strangers_str_still_reads_str_not_household(self):
        from apps.scholarship.income_str_ownership import STR_NOT_HOUSEHOLD
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        self._mother_cluster(app)
        self._father_ic(app)
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertEqual(sorted(income_doc_blockers(app)),
                         ['income_evidence_missing:mother', STR_NOT_HOUSEHOLD])

    def test_probe_1c_the_str_route_dodge_is_closed(self):
        """The probe-1 family on the STR route (earner = the mother, the father's IC never uploaded,
        a stranger's STR): used to read []. The STR route asks the same question now."""
        from apps.scholarship.services import income_doc_blockers
        app = self._app(route='str', earner='mother', working=())
        self._mother_cluster(app)
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertEqual(income_doc_blockers(app), ['parent_ic_missing:father'])
        self._father_ic(app)                       # every card on file, still no match → stranger
        self.assertEqual(income_doc_blockers(app), ['str_not_household'])

    def test_family_3_the_working_fathers_household_str_names_the_mother(self):
        """Father works with no payslip, the STR names the (non-working) mother, her IC not on file:
        ask for HER IC — the Documents page offers her a card (TD-309) — not his income. Her card
        landing and matching clears the gate."""
        from apps.scholarship.income_str_ownership import str_owner_ic_asks
        from apps.scholarship.services import income_doc_blockers
        app = self._app(working=('father',), mother_occ='homemaker')
        self._father_ic(app)
        self._str(app, MOTHER, MOTHER_NRIC)
        self.assertEqual(income_doc_blockers(app), ['parent_ic_missing:mother'])
        self.assertEqual(str_owner_ic_asks(app)['missing'], ['mother'])
        _doc(app, 'parent_ic', household_member='mother', vision_run_at=timezone.now(),
             vision_name=MOTHER.upper(), vision_nric=MOTHER_NRIC)
        self.assertEqual(income_doc_blockers(app), [])

    def test_genuine_5_the_str_route_with_a_matched_str_passes(self):
        from apps.scholarship.services import income_doc_blockers
        app = self._app(route='str', earner='mother', working=())
        self._mother_cluster(app)
        self._str(app, MOTHER, MOTHER_NRIC)
        self.assertEqual(income_doc_blockers(app), [])

    def test_an_str_whose_recipient_did_not_read_asks_for_a_clearer_one(self):
        """Every card on file, the STR read but its recipient blank: no match, not a stranger."""
        from apps.scholarship.services import income_doc_blockers
        app = self._app(route='str', earner='mother', working=())
        self._mother_cluster(app)
        self._father_ic(app)
        self._str(app, '', '')
        self.assertEqual(income_doc_blockers(app), ['income_document_unreadable'])

    def test_an_str_our_outage_never_read_is_try_later_not_the_students_fault(self):
        from apps.scholarship.services import income_doc_blockers
        app = self._app(route='str', earner='mother', working=())
        self._mother_cluster(app)
        self._father_ic(app)
        _doc(app, 'str', vision_fields={'student_verdict': 'review_manually', 'service_error': True})
        self.assertEqual(income_doc_blockers(app), ['ic_service_down'])

    def test_genuine_2_a_payslip_carries_her_income(self):
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        self._mother_cluster(app)
        _doc(app, 'salary_slip', household_member='mother', vision_fields={
            'fields': {'name': MOTHER.upper(), 'nric': MOTHER_NRIC, 'gross_income': '2200',
                       'period': '09/2026'}, 'student_verdict': 'ok', 'error': ''})
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertEqual(income_doc_blockers(app), [])

    def test_genuine_3_the_mothers_own_str_with_her_ic_missing_asks_for_her_ic(self):
        """Expected under the ruling: until a card matches the STR, her IC is what is asked for."""
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        _doc(app, 'birth_certificate', vision_fields={
            'fields': {'bc_child_name': STUDENT, 'bc_mother_name': MOTHER, 'bc_mother_nric': MOTHER_NRIC},
            'student_verdict': 'ok', 'error': ''})
        self._str(app, MOTHER, MOTHER_NRIC)
        out = income_doc_blockers(app)
        self.assertIn('parent_ic_missing:mother', out)
        # The IC ask alone: her card may match the STR, so she is not sent hunting for a payslip.
        self.assertNotIn('income_evidence_missing:mother', out)

    def test_genuine_4_the_mothers_own_str_matched_by_her_card_passes(self):
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        self._mother_cluster(app)
        self._str(app, MOTHER, MOTHER_NRIC)
        self.assertEqual(income_doc_blockers(app), [])

    def test_the_verdict_keeps_its_lenient_reading(self):
        """The ruling is a GATE ruling: the predicate the band reads still accepts the STR."""
        from apps.scholarship.income_engine import member_income_evidenced
        app = self._app()
        self._mother_cluster(app)
        self._str(app, STRANGER, STRANGER_NRIC)
        self.assertIs(member_income_evidenced(app, 'mother'), True)
