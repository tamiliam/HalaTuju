"""The Overview's Unassigned / Overdue / Due-soon cards and the Applications lists they open
(owner ruling 2026-11-05, option A: "Unassigned" = cases that can be assigned NOW).

* `queries_sla.ready_to_assign` (queryset) == `is_ready_for_assignment` (per row), over mixed cases and
  two organisations with different `query_answer_days`;
* each card's count == the length of the list its link opens (`?ready=1`, `?band=overdue|due_soon`),
  for the Overview's attention strip AND the pending cards, for an org admin, a super and a reviewer;
* the fence holds and a reviewer cannot widen visibility through these parameters.
"""
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import OrganisationConfiguration
from apps.scholarship.models import ResolutionItem, ScholarshipApplication
from apps.scholarship.review_sla import clocks as review_clocks
from apps.scholarship.services.queries_sla import (
    assignable_now, is_ready_for_assignment, ready_to_assign, with_open_student_tasks,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_programme,
)

LIST = '/api/v1/admin/scholarship/applications/'
PENDING = '/api/v1/admin/scholarship/my-pending/'
OVERVIEW = '/api/v1/admin/scholarship/programme-overview/'


def _ago(**kw):
    return timezone.now() - datetime.timedelta(**kw)


def _task(app):
    ResolutionItem.objects.create(application=app, source='officer', code='officer_1', kind='clarify',
                                  fact='other', status='open')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class OverviewCardLists(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.org_b = make_org(), make_org()
        OrganisationConfiguration.objects.create(organisation=cls.org_a, values={'query_answer_days': 4})
        # org_b follows the platform default (5 days).
        cls.ca = make_cohort(programme=make_programme(cls.org_a, code='cl-a'))
        cls.cb = make_cohort(programme=make_programme(cls.org_b, code='cl-b'))
        cls.rev = make_admin('reviewer', owning_org=cls.org_a)
        cls.rev_b = make_admin('reviewer', owning_org=cls.org_b)

        def pc(cohort, age, task=False):
            app = make_application('profile_complete', cohort=cohort)
            ScholarshipApplication.objects.filter(pk=app.pk).update(profile_completed_at=_ago(hours=age))
            if task:
                _task(app)
            return app

        # org A (grace 4 days = 96 h)
        cls.a_clear = pc(cls.ca, 24)                   # no task: ready
        cls.a_wait = pc(cls.ca, 48, task=True)         # task, inside grace: NOT ready
        cls.a_lapsed = pc(cls.ca, 120, task=True)      # task, past 4 days: ready
        cls.a_taken = pc(cls.ca, 216)
        ScholarshipApplication.objects.filter(pk=cls.a_taken.pk).update(assigned_to=cls.rev)
        cls.a_never = make_application('submitted', cohort=cls.ca)   # no profile_completed_at
        # org B (grace 5 days = 120 h): 108 h with a task is READY on A's clock but NOT on B's
        cls.b_wait = pc(cls.cb, 108, task=True)
        cls.b_lapsed = pc(cls.cb, 144, task=True)
        cls.b_clear = pc(cls.cb, 2)
        cls.b_decided = pc(cls.cb, 192)
        ScholarshipApplication.objects.filter(pk=cls.b_decided.pk).update(verdict_decided_at=timezone.now())

        sla, _soon, _grace = review_clocks(cls.org_a)

        def assigned(offset, reviewer, cohort):
            app = make_application('assigned', cohort=cohort, reviewer=reviewer)
            ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_at=timezone.now() - offset)
            return app

        cls.over = assigned(datetime.timedelta(days=sla + 2), cls.rev, cls.ca)
        cls.soon = assigned(datetime.timedelta(days=sla) - datetime.timedelta(hours=2), cls.rev, cls.ca)
        cls.open_ = assigned(datetime.timedelta(hours=1), cls.rev, cls.ca)
        cls.b_over = assigned(datetime.timedelta(days=sla + 3), cls.rev_b, cls.cb)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org_a)
        cls.org_admin_b = make_admin('org_admin', owning_org=cls.org_b)
        cls.super = make_admin('super', super_admin=True)

    # ── the rule: queryset == per row ─────────────────────────────────────────────────────────────────
    def test_ready_to_assign_equals_the_per_row_rule(self):
        now = timezone.now()
        by_query = set(ready_to_assign(ScholarshipApplication.objects.all(), now).values_list('pk', flat=True))
        by_row = {a.pk for a in ScholarshipApplication.objects.select_related('owning_organisation')
                  if is_ready_for_assignment(a, now)}
        self.assertEqual(by_query, by_row)
        # the mixed cases really are mixed
        self.assertIn(self.a_clear.pk, by_query)
        self.assertNotIn(self.a_wait.pk, by_query)
        self.assertIn(self.a_lapsed.pk, by_query)
        self.assertNotIn(self.a_never.pk, by_query)
        self.assertNotIn(self.b_wait.pk, by_query)     # 108 h: past A's 96, inside B's 120
        self.assertIn(self.b_lapsed.pk, by_query)
        self.assertIn(self.b_clear.pk, by_query)

    def test_ready_to_assign_is_the_same_on_an_already_annotated_queryset(self):
        now = timezone.now()
        plain = set(ready_to_assign(ScholarshipApplication.objects.all(), now).values_list('pk', flat=True))
        again = set(ready_to_assign(with_open_student_tasks(ScholarshipApplication.objects.all()), now)
                    .values_list('pk', flat=True))
        self.assertEqual(plain, again)

    def test_the_organisation_hint_reads_the_same_as_the_map_inside_a_fence(self):
        now = timezone.now()
        for org in (self.org_a, self.org_b):
            fenced = ScholarshipApplication.objects.filter(owning_organisation=org)
            self.assertEqual(
                set(ready_to_assign(fenced, now, org).values_list('pk', flat=True)),
                set(ready_to_assign(fenced, now).values_list('pk', flat=True)))

    def test_assignable_now_is_awaiting_review_unassigned_undecided_and_ready(self):
        got = set(assignable_now(ScholarshipApplication.objects.all()).values_list('pk', flat=True))
        self.assertEqual(got, {self.a_clear.pk, self.a_lapsed.pk, self.b_lapsed.pk, self.b_clear.pk})

    # ── card == list ──────────────────────────────────────────────────────────────────────────────────
    def _list(self, who, qs):
        r = authed_client(who).get(LIST + qs)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        return body['count'], {a['id'] for a in body['applications']}

    def _cards(self, who):
        r = authed_client(who).get(PENDING)
        self.assertEqual(r.status_code, 200, r.content)
        return {c['key']: c for c in r.json()['cards']}

    def test_the_unassigned_card_equals_the_ready_list(self):
        for who, ids in ((self.org_admin, {self.a_clear.pk, self.a_lapsed.pk}),
                         (self.org_admin_b, {self.b_lapsed.pk, self.b_clear.pk}),
                         (self.super, {self.a_clear.pk, self.a_lapsed.pk, self.b_lapsed.pk, self.b_clear.pk})):
            with self.subTest(who=who.role, n=len(ids)):
                count, got = self._list(who, '?ready=1')
                self.assertEqual(got, ids)
                self.assertEqual(count, self._cards(who)['unassigned']['count'])
                att = authed_client(who).get(OVERVIEW).json()['attention']['unassigned']
                self.assertEqual(att, count)

    def test_the_overdue_and_due_soon_cards_equal_their_lists(self):
        for who, over, soon in ((self.org_admin, {self.over.pk}, {self.soon.pk}),
                                (self.org_admin_b, {self.b_over.pk}, set()),
                                (self.super, {self.over.pk, self.b_over.pk}, {self.soon.pk})):
            with self.subTest(who=who.role):
                card = self._cards(who)
                c_over, ids_over = self._list(who, '?band=overdue')
                c_soon, ids_soon = self._list(who, '?band=due_soon')
                self.assertEqual((ids_over, ids_soon), (over, soon))
                self.assertEqual((c_over, c_soon), (card['overdue']['count'], card['overdue']['due_soon']))

    def test_a_reviewers_band_lists_equal_their_own_cards(self):
        card = self._cards(self.rev)
        c_over, ids_over = self._list(self.rev, '?band=overdue&assigned=me')
        c_soon, ids_soon = self._list(self.rev, '?band=due_soon&assigned=me')
        self.assertEqual((c_over, c_soon), (card['my_overdue']['count'], card['my_due_soon']['count']))
        self.assertEqual((ids_over, ids_soon), ({self.over.pk}, {self.soon.pk}))

    # ── the fence ─────────────────────────────────────────────────────────────────────────────────────
    def test_a_reviewer_cannot_widen_visibility_through_the_new_parameters(self):
        mine = {a.pk for a in ScholarshipApplication.objects.filter(assigned_to=self.rev)}
        for qs in ('', '?ready=1', '?band=overdue', '?band=due_soon', '?ready=1&assigned=none',
                   '?band=overdue&assigned=all'):
            with self.subTest(qs=qs):
                self.assertLessEqual(self._list(self.rev, qs)[1], mine)
        self.assertEqual(self._list(self.rev, '?ready=1')[1], set())

    def test_an_org_admin_never_reads_another_organisations_cases(self):
        other = {self.b_lapsed.pk, self.b_clear.pk, self.b_over.pk, self.b_wait.pk}
        for qs in ('?ready=1', '?band=overdue', '?band=due_soon'):
            with self.subTest(qs=qs):
                self.assertFalse(self._list(self.org_admin, qs)[1] & other)

    def test_other_values_are_ignored(self):
        plain = self._list(self.org_admin, '')[1]
        for qs in ('?ready=0', '?ready=yes', '?band=open', '?band=zzz'):
            with self.subTest(qs=qs):
                self.assertEqual(self._list(self.org_admin, qs)[1], plain)
