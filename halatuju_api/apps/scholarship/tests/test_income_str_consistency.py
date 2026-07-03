"""Code-health S4 regressions (#13/#15/#17/#18): STR-route consistency in income_engine.

#13 — the red STR states are ONE shared tuple; the cluster coach must nudge on the two
worst states (wrong_type/unreadable) it used to be silent on.
#15 — a legacy BLANK-tagged income doc belongs to THE EARNER only (when one is named);
it must not satisfy the income-evidence check for the other parent.
#17 — the earner's IC is selected member-tagged, not "latest parent_ic of any member".
#18 — an earner IC whose OCR is still pending must not blame the (fine) relationship doc.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.income_engine import (
    STR_RED_STATES, STR_COACH_STATES, _member_ic_doc, _parent_has_income_evidence,
    income_cluster_advice,
)
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort


def _mk_app(*, route='str', earner='father', size=4, uid):
    cohort = ScholarshipCohort.objects.create(code=f'c{uid}'[:12], name='B40', year=2026,
                                              per_capita_ceiling=1584)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'sic-{uid}', name='DIVASHINI A/P MURUGAN',
        nric='080115-05-0132', household_size=size)
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='shortlisted',
        income_route=route, income_earner=earner)


def _doc(app, doc_type, *, member='', vision_name='', run=True, fields=None, ffields_run=False):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type,
        storage_path=f'{app.id}/{doc_type}/{member or "b"}-{ApplicantDocument.objects.count()}',
        household_member=member, vision_name=vision_name,
        vision_run_at=timezone.now() if run else None,
        vision_fields=({'fields': fields or {}, 'warnings': [], 'student_verdict': 'ok',
                        'error': ''} if fields is not None else {}),
        vision_fields_run_at=timezone.now() if (fields is not None or ffields_run) else None,
    )


class TestSharedRedStates(TestCase):
    def test_tuples_shape(self):
        # wrong_type IS red (the #13 gap); 'unreadable' is NOT (amber per the spec, and a
        # never-scanned legacy doc also reads unreadable — blocking on it would gate
        # consent on our own extraction backlog). The coach covers both fixable states.
        self.assertIn('wrong_type', STR_RED_STATES)
        self.assertNotIn('unreadable', STR_RED_STATES)
        self.assertIn('unreadable', STR_COACH_STATES)
        self.assertIn('unconfirmed', STR_COACH_STATES)

    def test_cluster_coach_nudges_on_wrong_type(self):
        # A SALINAN/SARA in the STR slot reads wrong_type — the coach used to go silent
        # on it (the officer saw red, the student heard nothing).
        app = _mk_app(uid='coach-wt')
        _doc(app, 'parent_ic', vision_name='MURUGAN A/L KESAVAN')
        _doc(app, 'str', fields={'status': '', 'source_type': 'unknown'})
        self.assertEqual(income_cluster_advice(app, 'father'), 'str_not_current')


class TestBlankTagBelongsToEarner(TestCase):
    def test_blank_slip_counts_for_earner_only(self):
        app = _mk_app(uid='blank-earner')
        _doc(app, 'salary_slip', member='', fields={'gross_income': 'RM1,200'})
        self.assertTrue(_parent_has_income_evidence(app, 'father'))    # the earner
        self.assertFalse(_parent_has_income_evidence(app, 'mother'))   # #15: no longer both

    def test_blank_wizard_keeps_tolerant_reading(self):
        # Legacy app: no earner recorded — the blank doc stays attributable (the
        # pre-slot-model tolerant reading the consent gate depends on).
        app = _mk_app(earner='', uid='blank-legacy')
        _doc(app, 'salary_slip', member='', fields={'gross_income': 'RM1,200'})
        self.assertTrue(_parent_has_income_evidence(app, 'father'))
        self.assertTrue(_parent_has_income_evidence(app, 'mother'))


class TestMemberIcSelection(TestCase):
    def test_member_ic_prefers_the_tagged_card(self):
        # #17: mother is the earner; the father's (newer) card must not be picked.
        app = _mk_app(earner='mother', uid='ic-member')
        mother = _doc(app, 'parent_ic', member='mother', vision_name='MEENA A/P RAJU')
        _doc(app, 'parent_ic', member='father', vision_name='MURUGAN A/L KESAVAN')
        self.assertEqual(_member_ic_doc(app, 'mother').id, mother.id)


class TestPendingIcDoesNotBlameRelDoc(TestCase):
    def test_pending_ic_is_silent_not_rel_doc_unreadable(self):
        # #18: mother's IC uploaded but OCR still pending (vision_run_at NULL — a known
        # transient the self-heal cron clears); the birth certificate HAS been processed.
        # The coach used to return 'income_rel_doc_unreadable' — telling the student to
        # re-upload a fine BC and turning it into a submission blocker.
        app = _mk_app(earner='mother', uid='ic-pending')
        _doc(app, 'parent_ic', member='mother', run=False)          # pending OCR
        _doc(app, 'str', fields={'status': 'Lulus', 'year': '2026', 'source_type': 'letter'})
        _doc(app, 'birth_certificate', fields={'bc_child_name': 'DIVASHINI A/P MURUGAN',
                                               'bc_mother_name': 'MEENA A/P RAJU'})
        self.assertNotEqual(income_cluster_advice(app, 'mother'), 'income_rel_doc_unreadable')
