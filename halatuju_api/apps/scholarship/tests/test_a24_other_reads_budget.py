"""A2.4 / SP-13, TD-449, TD-500, TD-505 - query budgets for the smaller slow reads.

* TD-500: the mentor's My students list reads every mentee's alias in ONE query, so five mentees
  cost what two do.
* TD-505: the Overview's pending cards for a mentor and for a super (the pooled paths) are budgeted,
  and `review_sla.in_band` is a range filter, not an id list.
* TD-449: the cockpit detail for an applicant WITH an offer letter (programme, institution, issuer).

Numbers are pinned here (SQLite, the test client, one warm-up request first). They may only go DOWN.
"""
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_shortlistable_student,
)

MENTOR_ROUTE = '/api/v1/admin/mentor/students/'
PENDING_ROUTE = '/api/v1/admin/scholarship/my-pending/'
#: reading -> budget (queries). Measured 2026-11-08.
#: The mentor list still pays ~5 queries a mentee for the card's own reads (course, institution, latest
#: result, standing, help flag) - recorded here, not part of TD-500 (the alias read), see technical-debt.
BUDGETS = {'mentor-students-2': 17, 'mentor-students-5': 32, 'pending-mentor-2': 7,
           'pending-mentor-5': 7, 'pending-super-1-org': 9, 'pending-super-3-orgs': 9,
           'detail-with-offer-letter': 52}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheOtherSlowReadsQueryBudget(TestCase):

    def _mentees(self, n):
        from apps.scholarship.models import MentorAssignment
        org = make_org()
        gift = make_programme(organisation=org)
        mentor = make_admin('mentor', owning_org=org)
        cohort = make_cohort(programme=gift)
        for _ in range(n):
            app = make_application('maintenance', cohort=cohort)
            MentorAssignment.objects.create(application=app, mentor=mentor.mentor)
        return mentor

    def _count(self, who, url):
        client = authed_client(who)
        self.assertEqual(client.get(url).status_code, 200)            # warm-up
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, response.content[:200])
        return len(captured.captured_queries)

    def _offer_letter_detail(self):
        """TD-449: the cockpit detail of a case whose offer letter carries a programme, an institution
        and an issuer, so `student_offer_check` runs its catalogue lookups (letter_place, campus rows,
        the STPM scan, the second institutions scan)."""
        from django.utils import timezone
        from apps.scholarship.models import ApplicantDocument
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org), owning_organisation=org)
        app = make_application('interviewing', cohort=cohort, student=make_shortlistable_student())
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {
                'candidate_name': app.profile.name, 'candidate_nric': app.profile.nric,
                'programme': 'Diploma Teknologi Maklumat', 'programme_code': 'DIT',
                'institution': 'Politeknik Ungku Omar', 'campus': 'Ipoh',
                'issuer': 'Jabatan Pendidikan Politeknik', 'stream': ''},
                'student_verdict': 'ok', 'authenticity': {'status': 'genuine', 'reason': 'x'}},
            vision_run_at=timezone.now())
        return self._count(make_admin('org_admin', owning_org=org),
                           f'/api/v1/admin/scholarship/applications/{app.id}/')

    def _reading(self, name):
        if name == 'detail-with-offer-letter':
            return self._offer_letter_detail()
        n = int(name.split('-')[-1] if name[-1].isdigit() else name.split('-')[-2])
        if name.startswith('mentor-students'):
            return self._count(self._mentees(n), MENTOR_ROUTE)
        if name.startswith('pending-mentor'):
            return self._count(self._mentees(n), PENDING_ROUTE)
        for _ in range(n):
            cohort = make_cohort()
            make_application('submitted', cohort=cohort)
        return self._count(make_admin('super', super_admin=True), PENDING_ROUTE)

    def test_each_reading_stays_inside_its_budget(self):
        for name, limit in BUDGETS.items():
            with self.subTest(name=name):
                now = self._reading(name)
                self.assertLessEqual(now, limit, f'{name} now costs {now}; budget {limit}. DO NOT RAISE IT.')

    def test_the_alias_guard_reads_once_whatever_the_number_of_mentees(self):
        # TD-500: `mentoring.is_the_student` over the whole list is one alias query, not one a mentee.
        def alias_reads(n):
            mentor = self._mentees(n)
            client = authed_client(mentor)
            client.get(MENTOR_ROUTE)                                   # warm-up
            with CaptureQueriesContext(connection) as captured:
                client.get(MENTOR_ROUTE)
            # the login's own one-row lookup is not the list's: count the `profile_id IN (...)` read
            return sum('profile_login_alias' in q['sql'] and 'profile_id" IN' in q['sql']
                       for q in captured.captured_queries)
        two, five = alias_reads(2), alias_reads(5)
        self.assertEqual(two, five)                        # flat in the number of mentees
        self.assertEqual(five, 1)                          # and really ONE read: 0 == 0 must not pass

    def test_the_pending_cards_cost_the_same_for_more_mentees_or_organisations(self):
        self.assertEqual(self._reading('pending-mentor-2'), self._reading('pending-mentor-5'))
        self.assertEqual(self._reading('pending-super-1-org'), self._reading('pending-super-3-orgs'))

    def test_a_budget_that_now_sits_above_the_code_is_lowered(self):
        loose = [f'BUDGETS["{k}"]: budget {limit}, code {m} - LOWER it to {m}'
                 for k, limit in BUDGETS.items() for m in (self._reading(k),) if limit - 2 > m]
        self.assertEqual(loose, [], 'A budget may only go down:\n' + '\n'.join(loose))


class TestTheSlaRangeFilterKeepsReviewBandsEdges(TestCase):
    """`review_sla.in_band` (a range filter) and `review_band` (the sweep's own rule) must agree at
    every edge: now == due is overdue; the due-soon window opens exactly `soon` days before due."""

    CLOCKS = (10, 2, 1)

    def test_each_edge_lands_in_the_band_review_band_names(self):
        import datetime
        from apps.scholarship.models import ScholarshipApplication
        reviewer = make_admin('org_admin', owning_org=make_org())
        sec = datetime.timedelta(seconds=1)
        day = datetime.timedelta(days=1)
        sla, soon = self.CLOCKS[0], self.CLOCKS[1]
        cases = {                                  # age -> expected band
            sla * day + sec: 'overdue',
            sla * day: 'overdue',                  # now == due: the later band
            sla * day - sec: 'due_soon',
            (sla - soon) * day: 'due_soon',        # the window's first instant
            (sla - soon) * day - sec: 'open',
        }
        from django.utils import timezone
        from apps.scholarship import review_sla
        now = timezone.now()
        for age, expected in cases.items():
            app = make_application('interviewing', cohort=make_cohort())
            ScholarshipApplication.objects.filter(pk=app.pk).update(
                assigned_to=reviewer, assigned_at=now - age)
            qs = ScholarshipApplication.objects.filter(pk=app.pk)
            by_rule = review_sla.review_band(now - age, now=now, clocks=self.CLOCKS)
            self.assertEqual(by_rule, expected, f'review_band at age {age}')
            for band in ('overdue', 'due_soon'):
                held = review_sla.in_band(qs, band, now=now, clocks=self.CLOCKS).exists()
                self.assertEqual(held, band == expected, f'in_band({band}) at age {age}')
