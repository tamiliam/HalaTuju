"""Team tables T5c P5 S1 (2026-11-04): the Programmes LANDING read and the Overview's 404 rule.

`GET admin/scholarship/my-programmes/` (`views_admin/my_programmes.py`), driven per role through the real
endpoint: an admin sees every gift of their organisation with today's counts (finance without them); a
reviewer only the gifts holding a case assigned to them, open or done (an archived one included, flagged);
a mentor only the gifts of the students they mentor NOW; a reviewer who mentors, the union. A referral
partner and a source user are refused; another organisation's gift is never listed. A reviewer opening
the Overview of a gift where they have no case gets 404.
"""
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import Mentor, MentorAssignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
)

LANDING = '/api/v1/admin/scholarship/my-programmes/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'
NAMES = ('id', 'code', 'name_en', 'name_ms', 'name_ta', 'is_active', 'lifecycle', 'archived', 'opens')
COUNTS = ('intake_years', 'applications', 'awarded')


def _scholar(cohort):
    """A file in maintenance (the only files a mentor's desk reads)."""
    return make_application('maintenance', cohort=cohort, active_at=timezone.now() - datetime.timedelta(days=60))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class MyProgrammes(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other = make_org(), make_org()
        cls.g1 = make_programme(cls.org, code='mp-g1')
        cls.g2 = make_programme(cls.org, code='mp-g2')
        cls.g3 = make_programme(cls.org, code='mp-g3')                  # archived below, holds a done case
        cls.g4 = make_programme(cls.org, code='mp-g4')                  # nobody's work
        cls.gb = make_programme(cls.other, code='mp-gb')                # another organisation's
        c1, c2, c3, c4, cb = (make_cohort(programme=g) for g in (cls.g1, cls.g2, cls.g3, cls.g4, cls.gb))

        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        make_application('assigned', cohort=c1, reviewer=cls.reviewer)          # open
        make_application('closed', cohort=c3, reviewer=cls.reviewer)            # done
        make_application('assigned', cohort=cb, reviewer=cls.reviewer)          # another tenant's file
        make_application('submitted', cohort=c4)
        cls.g3.is_active = False
        cls.g3.save(update_fields=['is_active'])

        cls.mentor = make_admin('mentor', owning_org=cls.org)
        MentorAssignment.objects.create(application=_scholar(c2), mentor=cls.mentor.mentor)
        ended = MentorAssignment.objects.create(application=_scholar(c4), mentor=cls.mentor.mentor)
        ended.ended_at = timezone.now()
        ended.save(update_fields=['ended_at'])                                  # not current: g4 stays out

        cls.both = make_admin('reviewer', owning_org=cls.org, mentor=Mentor.objects.create(organisation=cls.org))
        make_application('assigned', cohort=c1, reviewer=cls.both)
        MentorAssignment.objects.create(application=_scholar(c2), mentor=cls.both.mentor)

        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.finance = make_admin('finance', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.other_admin = make_admin('org_admin', owning_org=cls.other)
        cls.super = make_admin('super', super_admin=True)

    def land(self, who):
        r = authed_client(who).get(LANDING)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def rows(self, who):
        return {row['code']: row for row in self.land(who)['programmes']}

    # ── admins ────────────────────────────────────────────────────────────────────────────────────────
    def test_an_org_admin_sees_every_gift_of_their_organisation_with_todays_counts(self):
        body = self.land(self.org_admin)
        self.assertTrue(body['every_gift'])
        rows = {r['code']: r for r in body['programmes']}
        self.assertEqual(list(rows), ['mp-g1', 'mp-g2', 'mp-g3', 'mp-g4'])
        self.assertEqual({k: rows['mp-g1'][k] for k in COUNTS}, {'intake_years': 1, 'applications': 2, 'awarded': 0})
        self.assertEqual(rows['mp-g2']['applications'], 2)
        self.assertEqual(rows['mp-g2']['awarded'], 2)                     # both in maintenance: ever awarded
        self.assertEqual((rows['mp-g3']['lifecycle'], rows['mp-g3']['archived']), ('archived', True))
        self.assertEqual({r['opens'] for r in rows.values()}, {'overview'})
        for row in rows.values():
            self.assertNotIn('cases', row)
            self.assertNotIn('scholars', row)

    def test_finance_sees_every_gift_but_no_application_counts(self):
        rows = self.rows(self.finance)
        self.assertEqual(list(rows), ['mp-g1', 'mp-g2', 'mp-g3', 'mp-g4'])
        for row in rows.values():
            self.assertEqual(set(row), set(NAMES))
        self.assertTrue(rows['mp-g3']['archived'])

    def test_qc_reads_every_gift_with_counts(self):
        rows = self.rows(self.qc)
        self.assertEqual(list(rows), ['mp-g1', 'mp-g2', 'mp-g3', 'mp-g4'])
        self.assertIn('applications', rows['mp-g1'])
        self.assertEqual(rows['mp-g1']['cases'], 0)                       # a Reviewer, nothing assigned

    def test_a_super_sees_every_tenant(self):
        rows = self.rows(self.super)
        self.assertTrue({'mp-g1', 'mp-g4', 'mp-gb'} <= set(rows))

    # ── reviewer ──────────────────────────────────────────────────────────────────────────────────────
    def test_a_reviewer_sees_only_the_gifts_with_a_case_assigned_open_or_done(self):
        body = self.land(self.reviewer)
        self.assertFalse(body['every_gift'])
        rows = {r['code']: r for r in body['programmes']}
        self.assertEqual(list(rows), ['mp-g1', 'mp-g3'])                  # not g2/g4, never the other tenant's
        self.assertEqual((rows['mp-g1']['cases'], rows['mp-g3']['cases']), (1, 1))
        self.assertEqual((rows['mp-g1']['archived'], rows['mp-g3']['archived']), (False, True))
        for row in rows.values():
            self.assertEqual(set(row), set(NAMES) | {'cases'})            # no counts, no scholars
            self.assertEqual(row['opens'], 'overview')

    def test_a_reviewer_with_nothing_assigned_gets_an_empty_list(self):
        body = self.land(make_admin('reviewer', owning_org=self.org))
        self.assertEqual(body, {'every_gift': False, 'programmes': []})

    # ── mentor ────────────────────────────────────────────────────────────────────────────────────────
    def test_a_mentor_sees_only_the_gifts_of_their_current_students(self):
        rows = self.rows(self.mentor)
        self.assertEqual(list(rows), ['mp-g2'])                           # the ended assignment's g4 is out
        self.assertEqual(rows['mp-g2']['scholars'], 1)
        self.assertEqual(rows['mp-g2']['opens'], 'my_students')
        self.assertEqual(set(rows['mp-g2']), set(NAMES) | {'scholars'})

    def test_a_reviewer_who_mentors_sees_the_union(self):
        rows = self.rows(self.both)
        self.assertEqual(list(rows), ['mp-g1', 'mp-g2'])
        self.assertEqual((rows['mp-g1']['cases'], rows['mp-g1']['scholars'], rows['mp-g1']['opens']),
                         (1, 0, 'overview'))
        self.assertEqual((rows['mp-g2']['cases'], rows['mp-g2']['scholars'], rows['mp-g2']['opens']),
                         (0, 1, 'my_students'))

    # ── outsiders and the fence ───────────────────────────────────────────────────────────────────────
    def test_a_referral_partner_and_a_source_user_are_refused(self):
        for who in (make_admin('partner', org=make_org()), make_admin('source_partner', owning_org=self.org)):
            with self.subTest(role=who.role):
                self.assertEqual(authed_client(who).get(LANDING).status_code, 403)

    def test_a_stopped_mentor_with_no_staff_seat_is_refused(self):
        stopped = make_admin('mentor', owning_org=self.org)
        stopped.mentor.deactivated_at = timezone.now()
        stopped.mentor.save(update_fields=['deactivated_at'])
        self.assertEqual(authed_client(stopped).get(LANDING).status_code, 403)

    def test_another_organisations_admin_sees_only_their_own_gift(self):
        self.assertEqual(list(self.rows(self.other_admin)), ['mp-gb'])

    def test_a_staff_member_with_no_organisation_sees_nothing(self):
        self.assertEqual(self.land(make_admin('admin'))['programmes'], [])

    # ── the Overview's 404 (lead ruling) ──────────────────────────────────────────────────────────────
    def overview(self, who, code=None):
        return authed_client(who).get(OVERVIEW + (f'?programme={code}' if code else '')).status_code

    def test_a_reviewer_opening_a_gift_with_no_case_of_theirs_gets_404(self):
        self.assertEqual(self.overview(self.reviewer, 'mp-g4'), 404)
        self.assertEqual(self.overview(self.reviewer, 'mp-g2'), 404)
        self.assertEqual(self.overview(self.both, 'mp-g2'), 404)           # mentoring-only: My students instead

    def test_a_reviewer_opens_a_gift_with_an_open_or_done_case_and_the_unnamed_overview(self):
        self.assertEqual(self.overview(self.reviewer, 'mp-g1'), 200)
        self.assertEqual(self.overview(self.reviewer, 'mp-g3'), 200)
        self.assertEqual(self.overview(self.reviewer), 200)

    def test_the_404_never_reaches_a_person_who_sees_every_gift(self):
        for who in (self.org_admin, self.finance, self.qc):
            with self.subTest(role=who.role):
                self.assertEqual(self.overview(who, 'mp-g4'), 200)
        self.assertEqual(self.overview(self.reviewer, 'mp-gb'), 404)      # another tenant's: 404 as before
