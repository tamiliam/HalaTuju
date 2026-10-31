"""Common profile S4 — the adversarial review's findings, one regression test each (2026-10-31).

Every finding's test FAILED before its fix (two are positive controls — "a row that existed at the
time is credited", "a reopen on its own is still rebuilt" — that pass on both sides of it). H1 / M1 /
M2 / L1 / L2 / L6 are the back-fill, M3 / L5 the reader, L4 the live writers' no-op clicks.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_activity, staff_activity_backfill as backfill
from apps.scholarship.models import (
    AssignmentEvent, ContractTemplate, DecisionReopen, InterviewSession, Invitation, Invoice,
    OrgRequest, ScholarshipApplication, Sponsor, SponsorProgrammeMembership, StaffActivity,
    StaffProfile,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

V = staff_activity.V
NOW = timezone.now()
LONG_AGO = NOW - timedelta(days=90)
EARLIER = LONG_AGO - timedelta(days=30)


def _rebuilt(verb=None):
    qs = StaffActivity.objects.filter(backfilled=True)
    return qs.filter(verb=verb) if verb else qs


def _created(admin, when):
    PartnerAdmin.objects.filter(pk=admin.pk).update(created_at=when)


class _Backfill(TestCase):

    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.qc = make_admin('qc', owning_org=self.org, email='qc@example.test')
        self.oa = make_admin('org_admin', owning_org=self.org, email='oa@example.test')
        for who in (self.qc, self.oa):
            _created(who, EARLIER)          # they existed when the old events happened
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)


class TestH1QcAcceptIsNotRebuiltFromStampsThatDisagree(_Backfill):

    def test_recommended_stamps_rebuild_nothing_and_are_counted(self):
        # QC1 accepted at LONG_AGO (first-only stamp); after a reopen QC2 re-accepted and
        # overwrote `recommended_by` — the two stamps no longer describe one act.
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            recommended_at=LONG_AGO, recommended_by='qc@example.test')
        report = backfill.run(apply=True)
        self.assertFalse(_rebuilt(V.QC_DECISION).exists())
        self.assertEqual(report['skipped'][(str(V.QC_DECISION), backfill.UNPAIRED_STAMPS)], 1)


class TestM1AnEmailMapsOnlyToARowThatExistedAtTheTime(_Backfill):

    def test_a_deleted_ops_mailbox_is_not_credited_to_its_successor(self):
        old = make_admin('admin', owning_org=self.org, email='ops@example.test')
        _created(old, EARLIER)
        AssignmentEvent.objects.create(application=self.app, to_admin=self.qc,
                                       by_email='ops@example.test')
        AssignmentEvent.objects.update(created_at=LONG_AGO)
        old.delete()                                            # it had no recorded work
        new = make_admin('admin', owning_org=self.org, email='ops@example.test')   # today
        report = backfill.run(apply=True)
        self.assertFalse(_rebuilt(V.ASSIGNED).filter(actor=new).exists())
        self.assertEqual(report['skipped'][(str(V.ASSIGNED), backfill.EMAIL_HOLDER_LATER)], 1)

    def test_a_row_that_existed_at_the_time_is_credited(self):
        AssignmentEvent.objects.create(application=self.app, to_admin=self.qc,
                                       by_email='oa@example.test')
        AssignmentEvent.objects.update(created_at=LONG_AGO)
        backfill.run(apply=True)
        self.assertTrue(_rebuilt(V.ASSIGNED).filter(actor=self.oa).exists())


class TestM2InterviewSubmitterIsUnknown(_Backfill):

    def test_a_submitted_interview_is_counted_not_rebuilt(self):
        InterviewSession.objects.create(application=self.app, interviewer=self.qc,
                                        status='submitted', submitted_at=LONG_AGO)
        report = backfill.run(apply=True)
        self.assertFalse(_rebuilt(V.INTERVIEW_SUBMITTED).exists())
        self.assertEqual(
            report['skipped'][(str(V.INTERVIEW_SUBMITTED), backfill.SUBMITTER_UNKNOWN)], 1)


class TestL1OneAccountVettingIsOneRow(_Backfill):

    def test_the_membership_stamp_of_the_same_click_is_dropped(self):
        sponsor = Sponsor.objects.create(supabase_user_id='l1', name='Ben', email='b@x.test',
                                         status='approved', reviewed_by='oa@example.test',
                                         reviewed_at=LONG_AGO)
        SponsorProgrammeMembership.objects.create(
            sponsor=sponsor, programme=self.cohort.programme, status='approved',
            vetted_by='oa@example.test', vetted_at=LONG_AGO + timedelta(milliseconds=300))
        backfill.run(apply=True)
        self.assertEqual(_rebuilt(V.BENEFACTOR_VETTED).count(), 1)


class TestL2AQcRejectIsOneRow(_Backfill):

    def test_the_reopen_inside_a_qc_reject_is_dropped(self):
        reopen = DecisionReopen.objects.create(application=self.app, reopened_by='qc@example.test',
                                               reason='x')
        DecisionReopen.objects.filter(pk=reopen.pk).update(created_at=LONG_AGO)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            rejected_at=LONG_AGO + timedelta(seconds=1), rejected_by='qc@example.test',
            rejection_category='interview')
        backfill.run(apply=True)
        self.assertEqual(list(_rebuilt().values_list('verb', flat=True)), [V.DECLINED])

    def test_a_reopen_on_its_own_is_still_rebuilt(self):
        reopen = DecisionReopen.objects.create(application=self.app, reopened_by='qc@example.test',
                                               reason='x')
        DecisionReopen.objects.filter(pk=reopen.pk).update(created_at=LONG_AGO)
        backfill.run(apply=True)
        self.assertTrue(_rebuilt(V.DECISION_REOPENED).exists())


class TestL6SourcesStreamInStampOrder(_Backfill):

    def test_events_come_oldest_first_whatever_their_ids(self):
        late = AssignmentEvent.objects.create(application=self.app, to_admin=self.qc,
                                              by_email='oa@example.test')
        early = AssignmentEvent.objects.create(application=self.app, to_admin=self.qc,
                                               by_email='oa@example.test')
        AssignmentEvent.objects.filter(pk=late.pk).update(created_at=LONG_AGO + timedelta(days=1))
        AssignmentEvent.objects.filter(pk=early.pk).update(created_at=LONG_AGO)
        stamps = [c.at for c in backfill._assignments()]
        self.assertEqual(stamps, sorted(stamps))


# ── the reader ─────────────────────────────────────────────────────────────────────────────────
URL = '/api/v1/admin/me/activity/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True, BILLING_USAGE_ENABLED=True)
class TestM3ADemotedViewerLosesTheNames(TestCase):

    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.me = make_admin('org_admin', owning_org=self.org)
        sponsor = Sponsor.objects.create(supabase_user_id='m3', name='Benefactor Name',
                                         email='b@x.test', status='approved')
        SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=self.cohort.programme,
                                                  status='approved')
        invitation = Invitation.objects.create(audience='staff', email='i@x.test', code='m3c',
                                               name='Invitee Name', organisation=self.org)
        invoice = Invoice.objects.create(number='INV-2026-0099', organisation=self.org,
                                         period_month='2026-08', issued_on='2026-09-01',
                                         due_on='2026-09-30', sent_at=timezone.now(),
                                         subtotal_myr='10.00', total_myr='10.00')
        template = ContractTemplate.objects.create(organisation=self.org,
                                                   programme=self.cohort.programme,
                                                   version='2026-vX', status='draft')
        request = OrgRequest.objects.create(organisation=self.org, submitted_by=self.me, kind='bug',
                                            title='t', description='d')
        self.subjects = {'sponsor': sponsor, 'invitation': invitation, 'invoice': invoice,
                         'contract_template': template, 'org_request': request}
        for kind, subject in self.subjects.items():
            StaffActivity.objects.create(actor=self.me, verb=V.INVITATION_SENT, subject_type=kind,
                                         subject_id=subject.pk)

    def _states(self):
        body = authed_client(self.me).get(URL).json()
        return {i['subject']['type']: i['subject']['state'] for i in body['results']}

    def test_names_while_org_admin_and_neutral_words_once_demoted(self):
        self.assertEqual(set(self._states().values()), {'visible'})
        PartnerAdmin.objects.filter(pk=self.me.pk).update(role='reviewer')
        self.assertEqual(self._states(), {kind: 'hidden' for kind in self.subjects})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestL5TheReaderNeverAnswers500(TestCase):

    def test_odd_digits_and_huge_ids_are_400(self):
        import base64
        me = make_admin('reviewer', owning_org=make_org())
        huge = base64.urlsafe_b64encode(f'{NOW.isoformat()}|{10 ** 30}'.encode()).decode()
        naive = base64.urlsafe_b64encode(b'2026-01-01T00:00:00|5').decode()
        for params, code in (({'limit': '²'}, 'bad_limit'), ({'limit': '٣'}, 'bad_limit'),
                             ({'cursor': huge}, 'bad_cursor'), ({'cursor': naive}, 'bad_cursor')):
            with self.subTest(params):
                resp = authed_client(me).get(URL, params)
                self.assertEqual((resp.status_code, resp.json().get('code')), (400, code))


# ── L4: a click that changes nothing writes nothing ────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestL4NoOpClicks(TestCase):

    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.oa = make_admin('org_admin', owning_org=self.org)

    def test_a_membership_set_to_what_it_already_is_writes_nothing(self):
        sponsor = Sponsor.objects.create(supabase_user_id='l4', name='Ben', email='b@x.test',
                                         status='approved')
        body = {'programme_id': self.cohort.programme_id, 'status': 'approved'}
        url = f'/api/v1/admin/sponsors/{sponsor.pk}/membership/'
        self.assertEqual(authed_client(self.oa).post(url, body, format='json').status_code, 200)
        self.assertEqual(authed_client(self.oa).post(url, body, format='json').status_code, 200)
        self.assertEqual(StaffActivity.objects.filter(verb=V.BENEFACTOR_VETTED).count(), 1)

    def test_a_profile_patch_names_only_the_fields_that_changed(self):
        StaffProfile.objects.create(partner_admin=self.oa, job_title='Lead')
        c = authed_client(self.oa)
        self.assertEqual(c.patch('/api/v1/admin/me/', {'job_title': 'Lead', 'name': self.oa.name},
                                 format='json').status_code, 200)
        self.assertFalse(StaffActivity.objects.exists())
        c.patch('/api/v1/admin/me/', {'job_title': 'Lead', 'about': 'New words'}, format='json')
        self.assertEqual(list(StaffActivity.objects.values_list('meta', flat=True)),
                         [{'fields': ['about']}])
