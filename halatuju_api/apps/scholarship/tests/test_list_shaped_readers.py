"""TD-162 + TD-231 (2026-10-03): two list endpoints stopped asking one question per row — and the
list-shaped answer is the per-row answer, on every shape that decides it.

* TD-162 — `with_open_student_tasks` annotates the applicant list with ONE `EXISTS`;
  `is_ready_for_assignment` reads it when present and runs its own query when not. Both readings
  agree on: not submitted, submitted with no task, an open officer task, an open check2 task, a
  RESOLVED task, a system item (not the student's), and a lapsed SLA window.
* TD-231 — `programme_delete_blockers` answers the whole gift list in one query from the same
  holder table `programme_delete_blocker` reads. Pinned against an independent per-holder
  `.count()` walk (the pre-TD-231 shape) on: an empty gift, a held-by-applicant gift, a gift held
  only THROUGH A MOVED COHORT, and a gift held by money.

The query counts themselves are pinned in `test_query_budgets.py` (`LIST_BUDGETS`).
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import (Donation, Programme, ResolutionItem,
                                     ScholarshipApplication, ScholarshipCohort)
from apps.scholarship.services.queries_sla import (is_ready_for_assignment,
                                                   with_open_student_tasks)
from apps.scholarship.tests.factories import (make_application, make_cohort, make_org,
                                              make_programme)
from apps.scholarship.tests.test_sponsorship import _sponsor
from apps.scholarship.views_admin.gifts import (_delete_holders, programme_delete_blocker,
                                                programme_delete_blockers)


class TheAnnotatedReadinessIsThePerRowReadiness(TestCase):

    def _task(self, app, source, status='open'):
        ResolutionItem.objects.create(application=app, code=f't-{source}-{status}',
                                      source=source, status=status, kind='question')

    def test_every_shape_agrees(self):
        cohort = make_cohort()
        shapes = {}
        shapes['not submitted'] = make_application('shortlisted', cohort=cohort)
        shapes['no task'] = make_application('profile_complete', cohort=cohort)
        for name, source, status in (('open officer', 'officer', 'open'),
                                     ('open check2', 'check2', 'open'),
                                     ('resolved officer', 'officer', 'resolved'),
                                     ('system item', 'system', 'open')):
            shapes[name] = make_application('profile_complete', cohort=cohort)
            self._task(shapes[name], source, status)
        lapsed = make_application('profile_complete', cohort=cohort)
        self._task(lapsed, 'officer')
        ScholarshipApplication.objects.filter(pk=lapsed.pk).update(
            profile_completed_at=timezone.now() - timedelta(days=30))
        shapes['open but lapsed'] = lapsed

        annotated = {a.pk: a for a in with_open_student_tasks(
            ScholarshipApplication.objects.filter(pk__in=[a.pk for a in shapes.values()]))}
        answers = {}
        for name, app in shapes.items():
            plain = ScholarshipApplication.objects.get(pk=app.pk)
            with self.subTest(shape=name):
                self.assertEqual(is_ready_for_assignment(annotated[app.pk]),
                                 is_ready_for_assignment(plain))
                answers[name] = is_ready_for_assignment(plain)
        # The fixture really spans both answers — "agree" over one value would prove little.
        self.assertEqual(answers, {'not submitted': False, 'no task': True, 'open officer': False,
                                   'open check2': False, 'resolved officer': True,
                                   'system item': True, 'open but lapsed': True})


class TheListBlockersAreTheDeleteHandlersBlockers(TestCase):

    @staticmethod
    def _counted_one_by_one(p):
        """The pre-TD-231 shape, written out independently: each holder counted in order."""
        for code, qs in _delete_holders(p):
            n = qs.count()
            if n:
                return code, n
        return None, 0

    def test_every_shape_agrees(self):
        org = make_org()
        empty = make_programme(organisation=org)
        held = make_programme(organisation=org)
        for _ in range(2):
            make_application('submitted', cohort=make_cohort(programme=held))
        # A cohort MOVED to another gift after its applicant applied: the application's own
        # column still names the old gift, so only the reach through the cohort finds it.
        moved_from = make_programme(organisation=org)
        moved_to = make_programme(organisation=org)
        cohort = make_cohort(programme=moved_from)
        make_application('submitted', cohort=cohort)
        ScholarshipCohort.objects.filter(pk=cohort.pk).update(programme=moved_to)
        money = make_programme(organisation=org)
        Donation.objects.create(sponsor=_sponsor(uid='td231-sponsor'), amount=Decimal('100'),
                                programme=money)

        gifts = Programme.objects.filter(organisation=org)
        listed = programme_delete_blockers(gifts)
        expected = {empty.pk: (None, 0), held.pk: ('has_applications', 2),
                    moved_from.pk: ('has_applications', 1), moved_to.pk: ('has_applications', 1),
                    money.pk: ('has_money', 1)}
        self.assertEqual(listed, expected)
        for p in gifts:
            with self.subTest(gift=p.pk):
                self.assertEqual(programme_delete_blocker(p), self._counted_one_by_one(p))
                self.assertEqual(listed[p.pk], self._counted_one_by_one(p))
