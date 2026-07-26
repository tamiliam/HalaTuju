"""Partner-organisation comms — S1 (2026-07-26).

Every test here pins a way this feature could fail QUIETLY rather than loudly:

* the recipient rule reads `contact_email` and **never** a `PartnerAdmin` row — the correction that
  matters most, because the only `partner`-role logins belong to the HalaTuju course selector, and
  emailing them bursary progress would put applicant data in front of the wrong audience;
* the counts RECONCILE (every status lands in exactly one line, the lines sum to the total) — a
  partner must never receive figures that do not add up;
* `recommended` is never its own line — it is masked from the student, so it must not reach a
  partner as a near-certainty either;
* the digest and the Sources screen agree, because they share one predicate;
* "last activity" does not move when a SYSTEM save touches the application;
* the seeded copy passes the owner's voice rules.
"""
from datetime import timedelta

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import partner_comms
from apps.scholarship.models import (
    ApplicantDocument, PartnerEmailLog, PartnerEmailTemplate,
    ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.views_admin import _source_application_counts

TEST_JWT_SECRET = 'test-secret-partner-comms'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _org(code, name=None, email=''):
    """update_or_create, not create: a migration seeds the house organisation (BrightPath as
    org #1, platform Sprint 1), so a test that needs it must adopt the existing row."""
    org, _ = PartnerOrganisation.objects.update_or_create(
        code=code,
        defaults={'name': name or code.upper(), 'contact_email': email, 'is_active': True},
    )
    return org


def _app(cohort, chip, status, n, *, submitted=None):
    prof = StudentProfile.objects.create(
        supabase_user_id=f'pc-{chip}-{status}-{n}', name=f'Student {n}', referral_source=chip)
    app = ScholarshipApplication.objects.create(cohort=cohort, profile=prof, status=status)
    if submitted is not None:
        # submitted_at is auto_now_add, so it needs an explicit UPDATE to be back-dated.
        ScholarshipApplication.objects.filter(pk=app.pk).update(submitted_at=submitted)
        app.refresh_from_db()
    return app


class TestQualifyingPartners(TestCase):
    """Who can actually receive a partner email — and who must never be consulted."""

    def test_needs_a_contact_email(self):
        with_email = _org('withmail', email='partner@example.org')
        _org('nomail')
        self.assertEqual([o.id for o in partner_comms.qualifying_partners()], [with_email.id])

    def test_house_org_never_qualifies_even_with_an_address(self):
        """BrightPath is US — the residual bucket in the Sources count. Sending ourselves a
        partner digest when we have the officer cockpit is noise, so the exclusion is by RULE,
        not by whether someone happens to have filled the field in."""
        _org(partner_comms.HOUSE_ORG_CODE, name='BrightPath', email='staff@example.org')
        self.assertEqual(partner_comms.qualifying_partners(), [])

    def test_inactive_org_never_qualifies(self):
        org = _org('dormant', email='x@example.org')
        PartnerOrganisation.objects.filter(pk=org.pk).update(is_active=False)
        self.assertEqual(partner_comms.qualifying_partners(), [])

    def test_partner_logins_are_NOT_recipients(self):
        """THE correction of 2026-07-26. Two active `partner`-role logins exist on prod (both at
        CUMIG, created 2026-03-17, `owning_organisation` NULL — no B40 scope at all): they belong
        to the HalaTuju course-selector relationship. Emailing them bursary progress would send
        applicant data to an audience attached for a different product."""
        org = _org('cumig')
        PartnerAdmin.objects.create(
            supabase_user_id='pc-partner-1', role='partner', is_active=True, org=org,
            name='Course-selector rep', email='rep@example.org')
        self.assertEqual(partner_comms.recipient_for(org), [])
        self.assertEqual(partner_comms.qualifying_partners(), [])

    def test_recipient_is_lower_cased_and_trimmed(self):
        org = _org('smc', email='  SMC@Example.ORG ')
        self.assertEqual(partner_comms.recipient_for(org), ['smc@example.org'])


class TestStageCounts(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _org('smc', email='smc@example.org')
        cls.cohort = ScholarshipCohort.objects.create(code='pc-2026', name='PC', year=2026)

    def test_every_status_lands_in_exactly_one_line(self):
        """If a new status is added and nobody classifies it, the partner's figures stop adding
        up. This fails the day that happens, naming the status."""
        claimed = [s for _, statuses in partner_comms.STAGE_LINES for s in statuses]
        self.assertEqual(len(claimed), len(set(claimed)), 'a status appears in two lines')
        all_statuses = {s for s, _ in ScholarshipApplication.STATUS_CHOICES}
        self.assertEqual(all_statuses - set(claimed), set(), 'unclassified status(es)')

    def test_lines_sum_to_total(self):
        for i, status in enumerate(s for s, _ in ScholarshipApplication.STATUS_CHOICES):
            _app(self.cohort, 'smc', status, i)
        counts = partner_comms.stage_counts(self.org)
        lines = sum(counts[line] for line, _ in partner_comms.STAGE_LINES)
        self.assertEqual(lines, counts['total'])
        self.assertEqual(counts['total'], len(ScholarshipApplication.STATUS_CHOICES))

    def test_recommended_is_not_its_own_line(self):
        """`recommended` is masked from the student (models.py STATUS_CHOICES). Surfacing it to a
        partner as its own figure would leak a near-certainty by the back door — it belongs inside
        'Under review'."""
        self.assertNotIn('recommended', [line for line, _ in partner_comms.STAGE_LINES])
        under = dict(partner_comms.STAGE_LINES)['under_review']
        self.assertIn('recommended', under)

    def test_awarded_counts_the_funded_states(self):
        _app(self.cohort, 'smc', 'awarded', 1)
        _app(self.cohort, 'smc', 'active', 2)
        _app(self.cohort, 'smc', 'maintenance', 3)
        self.assertEqual(partner_comms.stage_counts(self.org)['awarded'], 3)

    def test_another_orgs_students_are_not_counted(self):
        other = _org('pptm', email='pptm@example.org')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        _app(self.cohort, 'pptm', 'shortlisted', 2)
        self.assertEqual(partner_comms.stage_counts(self.org)['total'], 1)
        self.assertEqual(partner_comms.stage_counts(other)['total'], 1)

    def test_fingerprint_changes_only_when_a_count_changes(self):
        first = partner_comms.fingerprint(partner_comms.stage_counts(self.org))
        self.assertEqual(first, partner_comms.fingerprint(partner_comms.stage_counts(self.org)))
        _app(self.cohort, 'smc', 'shortlisted', 9)
        self.assertNotEqual(first, partner_comms.fingerprint(partner_comms.stage_counts(self.org)))


class TestOnePredicate(TestCase):
    """The digest and the Sources screen must never report different numbers."""

    def test_agrees_with_source_application_counts(self):
        cohort = ScholarshipCohort.objects.create(code='pc-agree', name='PC', year=2026)
        smc = _org('smc', email='smc@example.org')
        pptm = _org('pptm')
        house = _org(partner_comms.HOUSE_ORG_CODE, name='BrightPath')
        for i in range(3):
            _app(cohort, 'smc', 'shortlisted', i)
        _app(cohort, 'pptm', 'awarded', 10)
        _app(cohort, 'halatuju', 'shortlisted', 20)   # self-referral → house residual
        _app(cohort, '', 'shortlisted', 21)           # blank chip → house residual

        counts = _source_application_counts()
        for org in (smc, pptm):
            self.assertEqual(
                counts[org.id], partner_comms.partner_applications(org).count(),
                f'{org.code}: the Sources screen and the digest disagree')
        self.assertEqual(counts[house.id], 2, 'the house org takes the unclaimed residual')


class TestChaseRows(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _org('smc', email='smc@example.org')
        cls.cohort = ScholarshipCohort.objects.create(code='pc-chase', name='PC', year=2026)

    def test_only_shortlisted_students_appear(self):
        _app(self.cohort, 'smc', 'shortlisted', 1)
        _app(self.cohort, 'smc', 'profile_complete', 2)
        _app(self.cohort, 'smc', 'awarded', 3)
        self.assertEqual(len(partner_comms.chase_rows(self.org)), 1)

    def test_applied_is_the_submission_date_and_activity_falls_back_to_it(self):
        when = timezone.now() - timedelta(days=40)
        _app(self.cohort, 'smc', 'shortlisted', 1, submitted=when)
        (name, applied, activity), = partner_comms.chase_rows(self.org)
        # StudentProfile.save() upper-cases the name (2026-07-16) — the partner sees it as stored.
        self.assertEqual(name, 'STUDENT 1')
        self.assertEqual(applied, when.date())
        self.assertEqual(activity, when.date(), 'no upload yet → activity is the application date')

    def test_last_activity_is_the_newest_live_upload(self):
        app = _app(self.cohort, 'smc', 'shortlisted', 1,
                   submitted=timezone.now() - timedelta(days=40))
        older = ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='a')
        newer = ApplicantDocument.objects.create(application=app, doc_type='results_slip',
                                                storage_path='b')
        ApplicantDocument.objects.filter(pk=older.pk).update(
            uploaded_at=timezone.now() - timedelta(days=30))
        ApplicantDocument.objects.filter(pk=newer.pk).update(
            uploaded_at=timezone.now() - timedelta(days=5))
        (_, _, activity), = partner_comms.chase_rows(self.org)
        self.assertEqual(activity, (timezone.now() - timedelta(days=5)).date())

    def test_a_superseded_upload_does_not_count_as_activity(self):
        app = _app(self.cohort, 'smc', 'shortlisted', 1,
                   submitted=timezone.now() - timedelta(days=40))
        doc = ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='a')
        ApplicantDocument.objects.filter(pk=doc.pk).update(
            uploaded_at=timezone.now() - timedelta(days=2), superseded_at=timezone.now())
        (_, applied, activity), = partner_comms.chase_rows(self.org)
        self.assertEqual(activity, applied, 'a replaced copy is history, not activity')

    def test_a_SYSTEM_save_does_not_move_last_activity(self):
        """The whole reason `updated_at` is not used. It is `auto_now`, so verdict scoring,
        re-extraction, the institution sync — even a partner-notification stamp — bump it. A
        student untouched for a month would read as active this morning, and the partner would
        stop chasing precisely the person who needs it."""
        app = _app(self.cohort, 'smc', 'shortlisted', 1,
                   submitted=timezone.now() - timedelta(days=40))
        before = partner_comms.chase_rows(self.org)[0][2]
        app.partner_awaiting_notified_at = timezone.now()
        app.save()                       # a system-side write, exactly like a sweep would do
        after = partner_comms.chase_rows(self.org)[0][2]
        self.assertEqual(before, after)


class TestMilestoneQueryset(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='pc-ms', name='PC', year=2026)
        _org('smc', email='smc@example.org')

    def test_awaiting_review_picks_unstamped_profile_complete(self):
        wanted = _app(self.cohort, 'smc', 'profile_complete', 1)
        _app(self.cohort, 'smc', 'shortlisted', 2)
        stamped = _app(self.cohort, 'smc', 'profile_complete', 3)
        stamped.partner_awaiting_notified_at = timezone.now()
        stamped.save(update_fields=['partner_awaiting_notified_at'])
        self.assertEqual(
            list(partner_comms.milestone_queryset('awaiting_review').values_list('pk', flat=True)),
            [wanted.pk])

    def test_a_reverted_transition_drops_out(self):
        """The state is re-checked at SEND time, not trusted from when it changed — which is what
        stops `revert_if_profile_incomplete` (and `awarded → recommended`) producing an email for
        something that is no longer true."""
        app = _app(self.cohort, 'smc', 'profile_complete', 1)
        self.assertIn(app.pk, partner_comms.milestone_queryset('awaiting_review')
                      .values_list('pk', flat=True))
        app.status = 'shortlisted'
        app.save(update_fields=['status'])
        self.assertNotIn(app.pk, partner_comms.milestone_queryset('awaiting_review')
                         .values_list('pk', flat=True))

    def test_awarded_covers_the_funded_states(self):
        for i, status in enumerate(('awarded', 'active', 'maintenance')):
            _app(self.cohort, 'smc', status, i)
        self.assertEqual(partner_comms.milestone_queryset('awarded').count(), 3)


class TestEnabledGates(TestCase):
    """Two independent switches: the platform flag AND the template's own."""

    def setUp(self):
        PartnerEmailTemplate.objects.create(
            kind='weekly_summary', enabled=True, subject='s', body='b')

    @override_settings(PARTNER_COMMS_ENABLED=False)
    def test_flag_off_means_nothing_sends(self):
        self.assertFalse(partner_comms.is_enabled('weekly_summary'))

    @override_settings(PARTNER_COMMS_ENABLED=True)
    def test_template_off_means_nothing_sends(self):
        PartnerEmailTemplate.objects.filter(kind='weekly_summary').update(enabled=False)
        self.assertFalse(partner_comms.is_enabled('weekly_summary'))

    @override_settings(PARTNER_COMMS_ENABLED=True)
    def test_both_on(self):
        self.assertTrue(partner_comms.is_enabled('weekly_summary'))


class TestSeededTemplates(TestCase):
    """The seeds must satisfy the same rules the API enforces on a save."""

    def setUp(self):
        from django.core.management import call_command
        call_command('seed_partner_email_templates', verbosity=0)

    def test_seeds_all_five_kinds_disabled(self):
        self.assertEqual(PartnerEmailTemplate.objects.count(), 5)
        self.assertEqual(PartnerEmailTemplate.objects.filter(enabled=True).count(), 0)

    def test_idempotent(self):
        from django.core.management import call_command
        call_command('seed_partner_email_templates', verbosity=0)
        self.assertEqual(PartnerEmailTemplate.objects.count(), 5)

    def test_every_placeholder_is_one_the_kind_supplies(self):
        for tpl in PartnerEmailTemplate.objects.all():
            self.assertEqual(
                partner_comms.unknown_placeholders(tpl.kind, tpl.subject, tpl.body), (),
                f'{tpl.kind} uses a placeholder nothing will fill')

    def test_no_conduit_or_reader_owned_phrasing(self):
        """Owner ruling, 2026-07-26: a partner organisation co-owns this bursary and may market it
        as its own, and the students belong to the ORGANISATION, not to whoever reads the email."""
        for tpl in PartnerEmailTemplate.objects.all():
            self.assertEqual(
                partner_comms.banned_phrases(tpl.subject, tpl.body), (),
                f'{tpl.kind} casts the partner as a conduit or hands them the students')

    def test_the_award_email_licenses_them_to_share_it_as_their_own(self):
        tpl = PartnerEmailTemplate.objects.get(kind='awarded')
        self.assertIn('as your own', tpl.body)
        self.assertIn('{org_name}’s achievement', tpl.body)

    def test_no_email_points_at_a_partner_console(self):
        """None exists for the bursary, so every email must stand alone."""
        for tpl in PartnerEmailTemplate.objects.all():
            for word in ('partner console', 'log in', 'dashboard'):
                self.assertNotIn(word, tpl.body.lower(), f'{tpl.kind} links somewhere that is not built')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPartnerEmailEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        cls.org = _org('smc', email='smc@example.org')
        call_command('seed_partner_email_templates', verbosity=0)
        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='pc-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OrgAdmin', email='oa@example.org')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='pc-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Reviewer', email='rev@example.org')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='pc-qc', role='qc', is_active=True,
            owning_organisation=cls.org, name='QC', email='qc@example.org')
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='pc-par', role='partner', is_active=True, org=cls.org,
            name='Course rep', email='rep@example.org')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_org_admin_sees_the_five_templates(self):
        self._auth('pc-oa')
        body = self.client.get('/api/v1/admin/scholarship/partner-emails/').json()
        self.assertEqual([t['kind'] for t in body['templates']], list(partner_comms.KINDS))
        self.assertTrue(all(t['enabled'] is False for t in body['templates']))

    def test_payload_states_who_qualifies(self):
        _org('noaddress')
        self._auth('pc-oa')
        body = self.client.get('/api/v1/admin/scholarship/partner-emails/').json()
        self.assertEqual(body['qualifying_count'], 1)
        self.assertEqual(body['partner_count'], 2)
        by_code = {o['code']: o for o in body['organisations']}
        self.assertTrue(by_code['smc']['qualifies'])
        self.assertFalse(by_code['noaddress']['qualifies'])
        self.assertFalse(by_code['noaddress']['has_email'])

    def test_house_org_is_marked_and_never_qualifies(self):
        _org(partner_comms.HOUSE_ORG_CODE, name='BrightPath', email='staff@example.org')
        self._auth('pc-oa')
        body = self.client.get('/api/v1/admin/scholarship/partner-emails/').json()
        house = next(o for o in body['organisations'] if o['code'] == partner_comms.HOUSE_ORG_CODE)
        self.assertTrue(house['is_house_org'])
        self.assertFalse(house['qualifies'])
        self.assertEqual(body['partner_count'], 1, 'the house org is not counted as a partner')

    def test_reviewer_qc_and_partner_are_refused(self):
        for uid in ('pc-rev', 'pc-qc', 'pc-par'):
            self._auth(uid)
            self.assertEqual(
                self.client.get('/api/v1/admin/scholarship/partner-emails/').status_code, 403,
                f'{uid} must not manage partner emails')
            self.assertEqual(
                self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                                  {'enabled': True}, format='json').status_code, 403)

    def test_switching_one_on_persists(self):
        self._auth('pc-oa')
        r = self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                              {'enabled': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['enabled'])
        tpl = PartnerEmailTemplate.objects.get(kind='weekly_summary')
        self.assertTrue(tpl.enabled)
        self.assertEqual(tpl.updated_by_email, 'oa@example.org')

    def test_unknown_placeholder_is_refused(self):
        self._auth('pc-oa')
        r = self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                              {'body': 'Dear {contact_person}, {student_table} {nonsense}'},
                              format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'unknown_placeholder')
        self.assertIn('nonsense', r.json()['placeholders'])
        self.assertIn('student_table', r.json()['placeholders'],
                      'a table placeholder belongs to the chase list, not the summary')

    def test_conduit_phrasing_is_refused(self):
        self._auth('pc-oa')
        r = self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                              {'body': 'Dear {contact_person}, thank you for the students you '
                                       'send us. {counts_table} {team_signoff}'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'conduit_phrasing')

    def test_your_students_is_refused(self):
        self._auth('pc-oa')
        r = self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                              {'body': 'Dear {contact_person}, here are your students. '
                                       '{counts_table} {team_signoff}'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'conduit_phrasing')

    def test_a_valid_edit_is_accepted(self):
        self._auth('pc-oa')
        good = ('Dear {contact_person},\n\n{org_name}’s students this week:\n\n'
                '{counts_table}\n\n{team_signoff}')
        r = self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                              {'subject': '{org_name} — this week', 'body': good}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PartnerEmailTemplate.objects.get(kind='weekly_summary').body, good)

    def test_blank_body_is_refused(self):
        self._auth('pc-oa')
        r = self.client.patch('/api/v1/admin/scholarship/partner-emails/weekly_summary/',
                              {'body': '   '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'subject_and_body_required')

    def test_unknown_kind_is_404(self):
        self._auth('pc-oa')
        self.assertEqual(
            self.client.patch('/api/v1/admin/scholarship/partner-emails/not_a_kind/',
                              {'enabled': True}, format='json').status_code, 404)

    def test_last_sent_comes_from_the_log(self):
        PartnerEmailLog.objects.create(
            organisation=self.org, kind='weekly_summary', recipients=['smc@example.org'],
            subject='x', ok=True, students=3, fingerprint='abc')
        self._auth('pc-oa')
        body = self.client.get('/api/v1/admin/scholarship/partner-emails/').json()
        weekly = next(t for t in body['templates'] if t['kind'] == 'weekly_summary')
        self.assertIsNotNone(weekly['last_sent_at'])
        self.assertEqual(weekly['last_sent_orgs'], 1)

    def test_a_failed_send_is_not_reported_as_last_sent(self):
        PartnerEmailLog.objects.create(
            organisation=self.org, kind='awarded', recipients=[], subject='x',
            ok=False, note='no_recipient')
        self._auth('pc-oa')
        body = self.client.get('/api/v1/admin/scholarship/partner-emails/').json()
        awarded = next(t for t in body['templates'] if t['kind'] == 'awarded')
        self.assertIsNone(awarded['last_sent_at'],
                          'silence must not read as a successful send')


class TestLastFingerprint(TestCase):
    def test_reads_the_newest_successful_send(self):
        org = _org('smc', email='smc@example.org')
        PartnerEmailLog.objects.create(organisation=org, kind='weekly_summary', ok=True,
                                       fingerprint='old', recipients=['a@b.c'])
        newest = PartnerEmailLog.objects.create(organisation=org, kind='weekly_summary', ok=True,
                                                fingerprint='new', recipients=['a@b.c'])
        PartnerEmailLog.objects.filter(pk=newest.pk).update(sent_at=timezone.now())
        self.assertEqual(partner_comms.last_fingerprint(org, 'weekly_summary'), 'new')

    def test_never_sent_is_blank(self):
        org = _org('smc', email='smc@example.org')
        self.assertEqual(partner_comms.last_fingerprint(org, 'weekly_summary'), '')

    def test_a_failed_send_does_not_count_as_the_last_fingerprint(self):
        """Otherwise a failed run would suppress the next real one as 'unchanged'."""
        org = _org('smc', email='smc@example.org')
        PartnerEmailLog.objects.create(organisation=org, kind='weekly_summary', ok=False,
                                       fingerprint='failed', recipients=[])
        self.assertEqual(partner_comms.last_fingerprint(org, 'weekly_summary'), '')
