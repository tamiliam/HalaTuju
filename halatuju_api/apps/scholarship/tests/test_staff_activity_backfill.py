"""Common profile S4 (2026-10-31): `backfill_staff_activity` — rebuilding the list from old records.

  * `--dry-run` writes nothing and reports counts per verb and skips per reason;
  * `--apply` writes `backfilled=True` rows dated at the original moment, actor from a real FK or a
    UNIQUE email; an ambiguous or unknown email and a name-only stamp are skipped and counted;
  * idempotent — a second `--apply` writes nothing;
  * NO TWIN of a live row: an event stamped at or after the earliest live row is skipped;
  * a subject that has gone (a deleted staff row) still rebuilds, with no subject.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_activity, staff_activity_backfill as backfill
from apps.scholarship.models import (
    AssignmentEvent, BursaryAgreement, ScholarshipApplication, StaffActivity, StaffPermissionChange,
)
from apps.scholarship.services import assign_reviewer
from apps.scholarship.tests.factories import make_admin, make_application, make_cohort

V = staff_activity.V
LONG_AGO = timezone.now() - timedelta(days=90)


def _rebuilt():
    return StaffActivity.objects.filter(backfilled=True)


def _existed_long_ago(*admins):
    """Review M1: an email names a staff row only if it EXISTED when the act was stamped."""
    PartnerAdmin.objects.filter(pk__in=[a.pk for a in admins]).update(
        created_at=LONG_AGO - timedelta(days=30))


class _World(TestCase):

    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.oa = make_admin('org_admin', owning_org=self.org, email='oa@example.test')
        self.reviewer = make_admin('reviewer', owning_org=self.org, email='rev@example.test')
        self.app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)
        _existed_long_ago(self.oa, self.reviewer)

    def _event(self, by_email='oa@example.test', when=LONG_AGO, to=None):
        ev = AssignmentEvent.objects.create(application=self.app, to_admin=to or self.reviewer,
                                            by_email=by_email)
        AssignmentEvent.objects.filter(pk=ev.pk).update(created_at=when)
        return ev

    def report(self, apply=True, **kw):
        return backfill.run(apply=apply, **kw)


class TestDryRunAndApply(_World):

    def test_a_dry_run_writes_nothing_and_counts(self):
        self._event()
        out = StringIO()
        call_command('backfill_staff_activity', '--dry-run', stdout=out)
        self.assertEqual(StaffActivity.objects.count(), 0)
        self.assertIn('Would rebuild (dry run', out.getvalue())
        self.assertIn('assigned', out.getvalue())

    def test_apply_writes_rows_dated_at_the_original_moment(self):
        self._event()
        report = self.report()
        row = _rebuilt().get(verb=V.ASSIGNED)
        self.assertEqual((row.actor_id, row.subject_type, row.subject_id, row.organisation_id),
                         (self.oa.pk, 'application', self.app.pk, self.org.pk))
        self.assertEqual(row.created_at, LONG_AGO)
        self.assertEqual(row.meta, {'to_admin': self.reviewer.pk})
        self.assertEqual(report['written'][V.ASSIGNED], 1)

    def test_the_application_stamps(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            verified_at=LONG_AGO, verified_by='REV@example.test',      # case does not matter
            closed_at=LONG_AGO + timedelta(days=1), closed_by='oa@example.test',
            closure_reason='stalled')
        self.report()
        got = sorted((r.verb, r.actor_id) for r in _rebuilt().filter(subject_id=self.app.pk))
        self.assertIn((V.VERIFY_ACCEPT, self.reviewer.pk), got)
        self.assertIn((V.CASE_CLOSED, self.oa.pk), got)
        self.assertEqual(_rebuilt().get(verb=V.CASE_CLOSED).meta, {'reason': 'stalled'})

    def test_first_sign_in_from_the_real_row(self):
        PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(first_seen_at=LONG_AGO)
        self.report()
        row = _rebuilt().get(verb=V.FIRST_SIGN_IN, actor=self.reviewer)
        self.assertEqual((row.created_at, row.subject_type), (LONG_AGO, ''))


class TestIdempotent(_World):

    def test_a_second_apply_writes_nothing(self):
        self._event()
        PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(first_seen_at=LONG_AGO)
        first = self.report()
        count = StaffActivity.objects.count()
        second = self.report()
        self.assertEqual(StaffActivity.objects.count(), count)
        self.assertEqual(sum(second['written'].values()), 0)
        self.assertEqual(sum(n for (_, why), n in second['skipped'].items()
                             if why == backfill.ALREADY), sum(first['written'].values()))


class TestNoTwinOfALiveRow(_World):

    def test_the_first_live_action_gets_no_twin_and_an_older_one_is_rebuilt(self):
        """The live action STAMPS its event a moment BEFORE it writes its live row, so the cut-off
        alone would rebuild it (found by this test): the twin check is what stops that."""
        self._event()
        other = make_admin('reviewer', owning_org=self.org)
        assign_reviewer(self.app, reviewer=other, by_admin=self.oa)   # live: event + live row
        live = AssignmentEvent.objects.order_by('-id').first()
        self.assertLess(live.created_at, StaffActivity.objects.get(backfilled=False).created_at)
        report = self.report()
        self.assertEqual([r.created_at for r in _rebuilt().filter(verb=V.ASSIGNED)], [LONG_AGO])
        self.assertEqual(StaffActivity.objects.filter(verb=V.ASSIGNED).count(), 2)
        self.assertEqual(report['skipped'][(str(V.ASSIGNED), backfill.LIVE_TWIN)], 1)

    def test_a_later_live_action_is_after_the_cutoff(self):
        staff_activity.record(self.oa, V.FIRST_SIGN_IN)                # the live writers began
        self._event(when=timezone.now() + timedelta(seconds=5))
        report = self.report()
        self.assertFalse(_rebuilt().filter(verb=V.ASSIGNED).exists())
        self.assertEqual(report['skipped'][(str(V.ASSIGNED), backfill.AFTER_LIVE)], 1)

    def test_with_no_live_row_the_cutoff_is_the_moment_it_started(self):
        start = timezone.now()
        self._event(when=start + timedelta(seconds=30))     # "during the run"
        report = self.report(now=start)
        self.assertEqual(_rebuilt().count(), 0)
        self.assertEqual(report['cutoff'], start)

    def test_before_only_moves_the_cutoff_earlier(self):
        self._event(when=LONG_AGO)
        report = self.report(before=LONG_AGO - timedelta(days=1))
        self.assertEqual(_rebuilt().count(), 0)
        self.assertEqual(report['skipped'][(str(V.ASSIGNED), backfill.AFTER_LIVE)], 1)


class TestWhoTheActorIs(_World):

    def test_an_ambiguous_email_is_skipped_and_counted(self):
        _existed_long_ago(make_admin('admin', owning_org=self.org, email='Twin@example.test'),
                          make_admin('admin', owning_org=self.org, email='twin@example.test'))
        self._event(by_email='twin@example.test')
        report = self.report()
        self.assertFalse(_rebuilt().filter(verb=V.ASSIGNED).exists())
        self.assertEqual(report['skipped'][(str(V.ASSIGNED), backfill.AMBIGUOUS_EMAIL)], 1)

    def test_an_unknown_email_is_skipped_and_counted(self):
        self._event(by_email='gone@example.test')
        report = self.report()
        self.assertEqual(report['skipped'][(str(V.ASSIGNED), backfill.UNKNOWN_EMAIL)], 1)

    def test_a_name_only_countersign_is_skipped(self):
        BursaryAgreement.objects.create(application=self.app, version='v1',
                                        foundation_signed_by='Foundation Officer',
                                        foundation_signed_at=LONG_AGO)
        report = self.report()
        self.assertFalse(_rebuilt().filter(verb=V.CONTRACT_COUNTERSIGNED).exists())
        self.assertEqual(report['skipped'][(str(V.CONTRACT_COUNTERSIGNED), backfill.NAME_ONLY)], 1)

    def test_an_engine_rejection_has_no_actor_and_is_skipped(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(rejected_at=LONG_AGO,
                                                                     rejected_by='')
        report = self.report()
        self.assertEqual(report['skipped'][(str(V.DECLINED), backfill.NO_ACTOR)], 1)


class TestPurgedSubjects(_World):

    def test_a_deleted_staff_subject_still_rebuilds_with_no_subject(self):
        target = make_admin('reviewer', owning_org=self.org)
        change = StaffPermissionChange.objects.create(
            target=target, target_email=target.email, organisation=self.org, kind='edit',
            before=['review'], after=['review', 'spending'], changed_by_email='oa@example.test')
        StaffPermissionChange.objects.filter(pk=change.pk).update(created_at=LONG_AGO)
        target.delete()                                    # SET_NULL: the history row survives
        self.report()
        row = _rebuilt().get(verb=V.PERMISSIONS_CHANGED)
        self.assertEqual((row.actor_id, row.subject_type, row.subject_id), (self.oa.pk, '', None))
        self.assertEqual(row.meta, {'kind': 'edit', 'added': ['spending'], 'removed': []})

    def test_a_purged_application_leaves_nothing_to_rebuild(self):
        self._event()
        ScholarshipApplication.objects.filter(pk=self.app.pk).delete()   # events cascade with it
        self.report()
        self.assertFalse(_rebuilt().filter(verb=V.ASSIGNED).exists())
