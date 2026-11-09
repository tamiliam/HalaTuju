"""A2.6: no student is told by silence (TD-355/357/358/359), the partner count (TD-430), the
embargoed-decline upload door (TD-350), the dry-run reminder clock (TD-370)."""
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship.models import Programme, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import decline
from apps.scholarship.tests.factories import make_application
from apps.scholarship.services.decision_mail import (
    NO_ADDRESS, UNSENT, retry_unsent_decisions, untold_reason,
)

DECLINE_SEND = 'apps.scholarship.services.decline.send_decline_email'


def _cohort():
    org, _ = PartnerOrganisation.objects.get_or_create(code='a26-org', defaults={'name': 'Org'})
    prog, _ = Programme.objects.get_or_create(organisation=org, code='a26-g', defaults={'name_en': 'G'})
    return ScholarshipCohort.objects.get_or_create(
        code='a26', defaults={'name': 'B40', 'year': 2026, 'programme': prog})[0]


def _app(status='rejected', email='s@x.com', **kw):
    p = StudentProfile.objects.create(supabase_user_id=f'a26-{StudentProfile.objects.count()}')
    return make_application('submitted', cohort=_cohort(), student=p, status=status,
                            notify_email=email, **kw)


def _declined(hours_ago=2, minutes_ago=None, **kw):
    when = timezone.now() - (timedelta(minutes=minutes_ago) if minutes_ago else timedelta(hours=hours_ago))
    return _app(rejected_at=when, rejection_category='interview', **kw)


class TestUntoldReason(TestCase):
    def test_declined_without_email_is_unsent(self):
        self.assertEqual(untold_reason(_declined()), UNSENT)

    def test_no_address_is_flagged_for_the_officer(self):
        self.assertEqual(untold_reason(_declined(email='')), NO_ADDRESS)

    def test_told_is_clear(self):
        app = _declined()
        app.decline_email_sent_at = timezone.now()
        self.assertEqual(untold_reason(app), '')

    def test_embargoed_decline_is_not_here(self):
        app = _declined(pending_rejection_category='interview')
        self.assertEqual(untold_reason(app), '')

    def test_engine_reveal_without_email(self):
        app = _app(status='shortlisted', verdict='shortlisted',
                   decision_released_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(untold_reason(app), UNSENT)


class TestRetrySweep(TestCase):
    def test_failed_send_is_retried_then_stamped(self):
        app = _declined(minutes_ago=20)
        with mock.patch(DECLINE_SEND, return_value=False):
            self.assertEqual(retry_unsent_decisions(), {'sent': 0, 'failed': 1})
        with mock.patch(DECLINE_SEND, return_value=True):
            self.assertEqual(retry_unsent_decisions(), {'sent': 1, 'failed': 0})
        app.refresh_from_db()
        self.assertIsNotNone(app.decline_email_sent_at)
        with mock.patch(DECLINE_SEND, return_value=True) as send:
            retry_unsent_decisions()
        send.assert_not_called()

    def test_no_retry_past_the_cap(self):
        _declined(hours_ago=73)
        with mock.patch(DECLINE_SEND, return_value=True) as send:
            self.assertEqual(retry_unsent_decisions(), {'sent': 0, 'failed': 0})
        send.assert_not_called()

    def test_one_raise_does_not_stop_the_rest(self):
        _declined(minutes_ago=20)
        _declined(minutes_ago=20)
        with mock.patch(DECLINE_SEND, side_effect=[RuntimeError('x'), True]):
            self.assertEqual(retry_unsent_decisions(), {'sent': 1, 'failed': 1})


class TestReleaseCap(TestCase):
    def _embargoed(self, due_hours_ago):
        return _declined(hours_ago=due_hours_ago + 24, pending_rejection_category='interview',
                         pre_decline_status='interviewed',
                         decline_due_at=timezone.now() - timedelta(hours=due_hours_ago))

    def test_failed_send_within_cap_stays_masked(self):
        app = self._embargoed(1)
        with mock.patch(DECLINE_SEND, return_value=False):
            self.assertEqual(decline.release_pending_declines(), 0)
        app.refresh_from_db()
        self.assertEqual(app.pending_rejection_category, 'interview')

    def test_past_the_cap_it_is_never_released_without_its_email(self):
        # Lead ruling: a decline whose email keeps failing must NEVER become visible to her.
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        from apps.scholarship.student_status import student_facing_status
        app = self._embargoed(80)                       # due 80 h ago: past RETRY_CAP
        with mock.patch(DECLINE_SEND, return_value=False):
            for _ in range(3):
                decline.release_pending_declines()
            decline.release_pending_declines(now=timezone.now() + timedelta(days=9))
        app.refresh_from_db()
        self.assertEqual(app.pending_rejection_category, 'interview')       # still embargoed
        self.assertEqual(student_facing_status(app), 'interviewed')         # she sees no decline
        self.assertEqual(untold_reason(app), UNSENT)                        # the officer is told
        self.assertEqual(AdminApplicationDetailSerializer(app).data['decision_mail'], UNSENT)

    def test_the_officer_sees_it_from_the_moment_the_release_is_due(self):
        app = self._embargoed(1)
        self.assertEqual(untold_reason(app), UNSENT)
        app.decline_due_at = timezone.now() - timedelta(minutes=5)           # inside the grace
        self.assertEqual(untold_reason(app), '')
        app.decline_due_at = timezone.now() + timedelta(days=1)              # still cooling off
        self.assertEqual(untold_reason(app), '')

    def test_a_failing_release_is_tried_in_slots_not_on_every_run(self):
        self._embargoed(8)                                                    # between two slots
        with mock.patch(DECLINE_SEND, return_value=False) as send:
            decline.release_pending_declines()
        send.assert_not_called()

    def test_sent_stamp_can_be_kept_on_its_own(self):
        app = self._embargoed(1)
        stamp = timezone.now()
        decline._keep_sent_stamp(app.pk, stamp)
        app.refresh_from_db()
        self.assertEqual(app.decline_email_sent_at, stamp)
        self.assertEqual(app.decision_email_sent_at, stamp)


class TestRetrySchedule(TestCase):
    def test_a_failing_send_is_metered_about_six_times_in_the_window(self):
        t0 = timezone.now().replace(microsecond=0)
        _app(rejected_at=t0, rejection_category='interview')
        with mock.patch(DECLINE_SEND, return_value=False) as send:
            for k in range(0, 4 * 76):                                       # 15-minute cron, 76 hours
                retry_unsent_decisions(now=t0 + timedelta(minutes=15 * k))
        self.assertEqual(send.call_count, 6)    # 15 min, 1 h, 6 h, 24 h, 48 h, 72 h after the decision

    def test_slot_boundaries(self):
        h = timedelta(hours=1)
        self.assertTrue(decline.retry_slot(timedelta(minutes=16)))
        self.assertFalse(decline.retry_slot(timedelta(minutes=40)))
        self.assertTrue(decline.retry_slot(6 * h))
        self.assertFalse(decline.retry_slot(73 * h))                        # the sweep stops
        self.assertTrue(decline.retry_slot(96 * h + timedelta(minutes=5), forever=True))  # daily


class TestLockQueryIsSelfOnly(TestCase):
    def test_the_sweep_locks_its_own_row_only(self):
        # PostgreSQL refuses FOR UPDATE over a nullable outer join; SQLite cannot show the error.
        from django.db.models import QuerySet
        _declined(minutes_ago=20)
        real = QuerySet.select_for_update
        seen = {}

        def spy(qs, **kwargs):
            seen.update(kwargs)
            return real(qs, **kwargs)

        with mock.patch.object(QuerySet, 'select_for_update', spy), \
                mock.patch(DECLINE_SEND, return_value=True):
            retry_unsent_decisions()
        self.assertEqual(seen.get('of'), ('self',))
        self.assertTrue(seen.get('skip_locked'))


class TestCommandSurvivesOneFailure(TestCase):
    def test_raise_in_one_release_does_not_stop_the_run(self):
        past = timezone.now() - timedelta(hours=1)
        for _ in range(2):
            _app(status='submitted', verdict='shortlisted', decision_due_at=past)
        target = ('apps.scholarship.management.commands.send_pending_decision_emails.'
                  'release_decision')
        with mock.patch(target, side_effect=[RuntimeError('x'), True]) as rd:
            call_command('send_pending_decision_emails', stdout=mock.MagicMock())
        self.assertEqual(rd.call_count, 2)


class TestPartnerCount(TestCase):
    def test_cooloff_decline_counts_at_its_old_stage(self):
        from apps.scholarship import partner_comms
        org = PartnerOrganisation.objects.get_or_create(code='a26-org', defaults={'name': 'Org'})[0]
        _declined(pending_rejection_category='interview', pre_decline_status='interviewed',
                  decline_due_at=timezone.now() + timedelta(days=3))
        with mock.patch.object(partner_comms, 'partner_applications',
                               return_value=ScholarshipApplication.objects.all()):
            counts = partner_comms.stage_counts(org)
        lines = sum(counts[line] for line, _ in partner_comms.STAGE_LINES)
        self.assertEqual(lines, counts['total'])
        self.assertEqual(counts['total'], 1)
        rejected_line = [line for line, st in partner_comms.STAGE_LINES if 'rejected' in st][0]
        self.assertEqual(counts[rejected_line], 0)


class TestEmbargoedUploadDoor(TestCase):
    def test_embargoed_decline_still_resolves(self):
        from apps.scholarship.student_status import live_q
        app = _declined(pending_rejection_category='interview', pre_decline_status='shortlisted',
                        decline_due_at=timezone.now() + timedelta(days=3))
        qs = ScholarshipApplication.objects.filter(live_q(['shortlisted']), pk=app.pk)
        self.assertEqual(qs.count(), 1)
        app.pending_rejection_category = ''
        app.save()
        self.assertEqual(
            ScholarshipApplication.objects.filter(live_q(['shortlisted']), pk=app.pk).count(), 0)


class TestReminderClock(TestCase):
    def test_dry_run_and_live_share_one_rule(self):
        from apps.scholarship.services.queries_sla import query_reminder_is_due
        app = _app(status='shortlisted')
        self.assertFalse(query_reminder_is_due(app, {'days_left': None}))
        self.assertTrue(query_reminder_is_due(app, {'days_left': -1}))
        self.assertFalse(query_reminder_is_due(app, {'days_left': 10 ** 6}))


class TestDetailPayload(TestCase):
    def test_admin_detail_serializer_carries_decision_mail(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        self.assertEqual(
            AdminApplicationDetailSerializer(_declined(email='')).data['decision_mail'], NO_ADDRESS)
        self.assertEqual(AdminApplicationDetailSerializer(_app('submitted')).data['decision_mail'], '')


class TestCurrentApplicationTwoCohorts(TestCase):
    def _two(self):
        from apps.scholarship.tests.factories import make_cohort
        p = StudentProfile.objects.create(supabase_user_id=f'a26-two-{StudentProfile.objects.count()}')
        a = make_application('shortlisted', cohort=_cohort(), student=p)
        ScholarshipApplication.objects.filter(pk=a.pk).update(
            status='rejected', pending_rejection_category='interview',
            pre_decline_status='shortlisted', rejected_at=timezone.now(),
            decline_due_at=timezone.now() + timedelta(days=3))
        b = make_application('shortlisted', cohort=make_cohort(code='a26-b'), student=p)
        return p, b

    def test_an_embargoed_decline_does_not_block_the_other_cohort(self):
        from apps.scholarship.views import _current_application
        p, b = self._two()
        self.assertEqual(_current_application(p.pk).pk, b.pk)

    def test_two_live_ones_still_refuse(self):
        from apps.scholarship.tests.factories import make_cohort
        from apps.scholarship.views import AmbiguousApplication, _current_application
        p, _b = self._two()
        make_application('shortlisted', cohort=make_cohort(code='a26-c'), student=p)
        with self.assertRaises(AmbiguousApplication):
            _current_application(p.pk)


class TestCancelReopenFromAnUnmovedCase(TestCase):
    """TD-356: a reopen recorded from 'interviewing' (a decided case QC never saw) cancels in place."""

    def test_the_target_leaves_interviewing_alone(self):
        from apps.scholarship import reopen
        from apps.scholarship.models import DecisionReopen
        row = DecisionReopen(reopened_from='interviewing')
        self.assertIsNone(reopen._cancel_target(row, 'interviewing'))
        # ...while a QC reopen (recorded from 'interviewed') still returns to AWAITING QC.
        row.reopened_from = 'interviewed'
        self.assertEqual(reopen._cancel_target(row, 'interviewing'), 'interviewed')



class TestNotCheckedHold(TestCase):
    """TD-406: a later non-closing offer upload lifts the not-checked hold, and only that hold."""

    def _item(self, params, code):
        from apps.scholarship.models import ResolutionItem
        return ResolutionItem.objects.create(
            application=self.app, code=code, kind='doc', doc_type='offer_letter',
            source='officer', status='open', params=params)

    def setUp(self):
        from apps.scholarship.genuineness.offer_issuers import NOT_CHECKED_HOLD
        self.app = _app('shortlisted')
        self.hold = self._item({'needs_officer_eye': True, 'held_by': NOT_CHECKED_HOLD}, 'a')
        self.breaker = self._item({'needs_officer_eye': True}, 'b')

    def test_an_upload_lifts_only_the_request_it_answers(self):
        from apps.scholarship.genuineness.offer_issuers import (
            NOT_CHECKED_HOLD, release_not_checked_holds)
        other = self._item({'needs_officer_eye': True, 'held_by': NOT_CHECKED_HOLD}, 'c')
        release_not_checked_holds(
            self.app, mock.Mock(doc_type='offer_letter', vision_fields={}, request_code='a'))
        self.hold.refresh_from_db()
        other.refresh_from_db()
        self.assertNotIn('needs_officer_eye', self.hold.params)
        self.assertTrue(other.params.get('needs_officer_eye'))

    def test_later_unreadable_offer_lifts_only_the_not_checked_hold(self):
        from apps.scholarship.genuineness.offer_issuers import release_not_checked_holds
        doc = mock.Mock(doc_type='offer_letter', vision_fields={}, request_code='')
        release_not_checked_holds(self.app, doc)
        self.hold.refresh_from_db()
        self.breaker.refresh_from_db()
        self.assertNotIn('needs_officer_eye', self.hold.params)
        self.assertNotIn('held_by', self.hold.params)
        self.assertTrue(self.breaker.params.get('needs_officer_eye'))

    def test_another_doc_type_changes_nothing(self):
        from apps.scholarship.genuineness.offer_issuers import release_not_checked_holds
        release_not_checked_holds(self.app, mock.Mock(doc_type='ic', vision_fields={}))
        self.hold.refresh_from_db()
        self.assertTrue(self.hold.params.get('needs_officer_eye'))
