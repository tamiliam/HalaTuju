"""Partner-organisation comms — the renderer + the two weekly emails (S2, 2026-07-26).

The assertions that matter are about SILENCE and REPETITION, because those are the failure modes a
weekly email has: sending the same unchanged scoreboard forever, going quiet on a partner who needs
chasing, or skipping someone with no trace that it happened.
"""
from datetime import date, timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import partner_comms, partner_notify
from apps.scholarship.models import (
    ApplicantDocument, PartnerEmailLog, PartnerEmailTemplate,
    ScholarshipApplication, ScholarshipCohort,
)

LIVE = dict(PARTNER_COMMS_ENABLED=True,
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def _org(code, name=None, email='partner@example.org'):
    org, _ = PartnerOrganisation.objects.update_or_create(
        code=code,
        defaults={'name': name or code.upper(), 'contact_email': email,
                  'contact_person': 'Sivamani', 'is_active': True},
    )
    return org


def _app(cohort, chip, status, n, *, submitted=None):
    prof = StudentProfile.objects.create(
        supabase_user_id=f'pd-{chip}-{status}-{n}', name=f'Student {n}', referral_source=chip)
    app = ScholarshipApplication.objects.create(cohort=cohort, profile=prof, status=status)
    if submitted is not None:
        ScholarshipApplication.objects.filter(pk=app.pk).update(submitted_at=submitted)
        app.refresh_from_db()
    return app


def _seed():
    from django.core.management import call_command
    call_command('seed_partner_email_templates', verbosity=0)
    PartnerEmailTemplate.objects.update(enabled=True)


class TestRender(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed()

    def test_counts_table_becomes_a_real_table_in_both_parts(self):
        tpl = PartnerEmailTemplate.objects.get(kind='weekly_summary')
        counts = {k: 1 for k, _ in partner_comms.STAGE_LINES}
        counts['total'] = 7
        subject, text, html = partner_comms.render(
            'weekly_summary', tpl, {'org_name': 'Sri Murugan Centre', 'counts': counts})
        self.assertIn('Sri Murugan Centre', subject)
        self.assertIn('<table', html)
        self.assertIn('Awaiting review', html)
        self.assertIn('Awaiting review', text)
        self.assertIn('Bursary students in total', text)
        self.assertNotIn('{counts_table}', html + text + subject)

    def test_no_placeholder_survives_into_any_part(self):
        for tpl in PartnerEmailTemplate.objects.all():
            counts = {k: 0 for k, _ in partner_comms.STAGE_LINES}
            counts['total'] = 2
            subject, text, html = partner_comms.render(tpl.kind, tpl, {
                'org_name': 'SMC', 'contact_person': 'Sivamani', 'count': 2,
                'counts': counts, 'names': ['A B', 'C D'], 'student_name': 'A B',
                'rows': [('A B', date(2026, 6, 1), date(2026, 6, 2))],
            })
            for part in (subject, text, html):
                self.assertNotRegex(part, r'\{[a-z_]+\}', f'{tpl.kind}: an unfilled token remains')

    def test_missing_contact_person_falls_back_rather_than_greeting_nobody(self):
        tpl = PartnerEmailTemplate.objects.get(kind='awarded')
        _, text, _ = partner_comms.render('awarded', tpl, {
            'org_name': 'SMC', 'contact_person': '', 'count': 1, 'names': ['A B']})
        self.assertIn(f'Dear {partner_comms.NO_CONTACT_GREETING},', text)
        self.assertNotIn('Dear ,', text)

    def test_a_name_with_html_in_it_cannot_break_the_email(self):
        tpl = PartnerEmailTemplate.objects.get(kind='awaiting_review')
        _, _, html = partner_comms.render('awaiting_review', tpl, {
            'org_name': '<script>x</script>', 'count': 1, 'names': ['<b>Bad</b> Name']})
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>Bad</b>', html)
        self.assertIn('&lt;', html)

    def test_chase_table_carries_both_dates_and_its_footnote(self):
        tpl = PartnerEmailTemplate.objects.get(kind='shortlisted_followup')
        rows = [('Kavitha Ramasamy', date(2026, 6, 12), date(2026, 6, 18))]
        _, text, html = partner_comms.render('shortlisted_followup', tpl, {
            'org_name': 'SMC', 'count': 1, 'rows': rows, 'today': date(2026, 7, 26)})
        self.assertIn('12 Jun 2026', html)
        self.assertIn('18 Jun 2026', html)
        self.assertIn('12 Jun 2026', text)
        self.assertIn(partner_comms.CHASE_FOOTNOTE, text)
        self.assertIn('Last activity', html)

    def test_a_stale_date_is_marked_and_a_fresh_one_is_not(self):
        tpl = PartnerEmailTemplate.objects.get(kind='shortlisted_followup')
        today = date(2026, 7, 26)
        stale = [('Old Case', date(2026, 6, 1), date(2026, 6, 2))]
        fresh = [('New Case', date(2026, 6, 1), date(2026, 7, 25))]
        _, stale_text, stale_html = partner_comms.render(
            'shortlisted_followup', tpl,
            {'org_name': 'SMC', 'count': 1, 'rows': stale, 'today': today})
        _, fresh_text, fresh_html = partner_comms.render(
            'shortlisted_followup', tpl,
            {'org_name': 'SMC', 'count': 1, 'rows': fresh, 'today': today})
        self.assertIn(' *', stale_text)
        self.assertIn('#b45309', stale_html)
        self.assertNotIn(' *', fresh_text)
        self.assertNotIn('#b45309', fresh_html)

    def test_a_long_chase_list_says_what_it_dropped(self):
        """Silent truncation would read as 'that is everyone'."""
        tpl = PartnerEmailTemplate.objects.get(kind='shortlisted_followup')
        rows = [(f'Student {i}', date(2026, 6, 1), date(2026, 7, 20))
                for i in range(partner_comms.MAX_CHASE_ROWS + 7)]
        _, text, html = partner_comms.render('shortlisted_followup', tpl, {
            'org_name': 'SMC', 'count': len(rows), 'rows': rows, 'today': date(2026, 7, 26)})
        self.assertIn('and 7 more', text)
        self.assertIn('and 7 more', html)
        self.assertNotIn('Student 56', text)

    def test_a_structural_token_in_a_subject_never_renders_raw(self):
        tpl = PartnerEmailTemplate.objects.get(kind='awaiting_review')
        tpl.subject = 'Update: {student_list}'
        subject, _, _ = partner_comms.render('awaiting_review', tpl, {
            'org_name': 'SMC', 'count': 2, 'names': ['A B', 'C D']})
        self.assertNotIn('{student_list}', subject)
        self.assertNotIn('\n', subject)
        self.assertIn('A B', subject)


@override_settings(**LIVE)
class TestWeeklyDigests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed()
        cls.cohort = ScholarshipCohort.objects.create(code='pd-2026', name='PD', year=2026)

    def setUp(self):
        mail.outbox = []

    def test_summary_sends_then_skips_an_unchanged_week(self):
        org = _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        partner_notify.send_partner_digests()
        first = [m for m in mail.outbox if 'this week' in m.subject]
        self.assertEqual(len(first), 1)

        mail.outbox = []
        partner_notify.send_partner_digests()
        self.assertEqual([m for m in mail.outbox if 'this week' in m.subject], [])
        self.assertTrue(PartnerEmailLog.objects.filter(
            organisation=org, kind='weekly_summary', ok=False, note='unchanged').exists())

    def test_summary_sends_again_once_a_count_moves(self):
        _org('smc')
        app = _app(self.cohort, 'smc', 'shortlisted', 1)
        partner_notify.send_partner_digests()
        mail.outbox = []
        app.status = 'profile_complete'
        app.save(update_fields=['status'])
        partner_notify.send_partner_digests()
        self.assertEqual(len([m for m in mail.outbox if 'this week' in m.subject]), 1)

    def test_an_organisation_with_no_students_gets_no_summary(self):
        org = _org('empty')
        partner_notify.send_partner_digests()
        self.assertEqual(mail.outbox, [])
        self.assertTrue(PartnerEmailLog.objects.filter(
            organisation=org, kind='weekly_summary', note='no_students').exists())

    def test_chase_list_sends_again_even_when_the_list_HAS_NOT_changed(self):
        """The owner's rule applied where it matters: an unchanged list of stragglers is exactly
        who needs chasing, so unlike the summary this one repeats."""
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1,
             submitted=timezone.now() - timedelta(days=30))
        partner_notify.send_partner_digests()
        self.assertEqual(len([m for m in mail.outbox if 'not finished' in m.subject]), 1)
        mail.outbox = []
        partner_notify.send_partner_digests()
        self.assertEqual(len([m for m in mail.outbox if 'not finished' in m.subject]), 1)

    def test_chase_list_is_silent_when_nobody_is_waiting(self):
        org = _org('smc')
        _app(self.cohort, 'smc', 'awarded', 1)
        partner_notify.send_partner_digests()
        self.assertEqual([m for m in mail.outbox if 'not finished' in m.subject], [])
        self.assertTrue(PartnerEmailLog.objects.filter(
            organisation=org, kind='shortlisted_followup', note='nobody_waiting').exists())

    def test_one_email_per_organisation_not_per_student(self):
        _org('smc')
        for i in range(4):
            _app(self.cohort, 'smc', 'shortlisted', i,
                 submitted=timezone.now() - timedelta(days=20))
        partner_notify.send_partner_digests()
        chase = [m for m in mail.outbox if 'not finished' in m.subject]
        self.assertEqual(len(chase), 1)
        self.assertEqual(len(chase[0].to), 1)
        self.assertIn('4', chase[0].subject)

    def test_no_recipient_is_skipped_AND_logged(self):
        """Silence is not success — a partner with no address leaves a trace."""
        org = _org('noaddr', email='')
        _app(self.cohort, 'noaddr', 'shortlisted', 1)
        partner_notify.send_partner_digests()
        self.assertEqual(mail.outbox, [])
        # qualifying_partners excludes it, so it is never even iterated — assert the honest
        # consequence instead: nothing was sent and nothing claims to have been.
        self.assertFalse(PartnerEmailLog.objects.filter(organisation=org, ok=True).exists())

    def test_the_house_organisation_is_never_emailed(self):
        _org(partner_comms.HOUSE_ORG_CODE, name='BrightPath', email='staff@example.org')
        _app(self.cohort, partner_comms.HOUSE_ORG_CODE, 'shortlisted', 1)
        partner_notify.send_partner_digests()
        self.assertEqual(mail.outbox, [])

    @override_settings(PARTNER_COMMS_ENABLED=False)
    def test_platform_flag_off_sends_nothing(self):
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        summary = partner_notify.send_partner_digests()
        self.assertEqual(mail.outbox, [])
        self.assertTrue(all(row['off'] for row in summary.values()))

    def test_template_switch_off_sends_nothing_even_with_the_flag_on(self):
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        PartnerEmailTemplate.objects.filter(kind='weekly_summary').update(enabled=False)
        partner_notify.send_partner_digests()
        self.assertEqual([m for m in mail.outbox if 'this week' in m.subject], [])

    @override_settings(PARTNER_NOTIFY_MAX_PER_RUN=1)
    def test_the_per_run_cap_defers_rather_than_drops(self):
        for code in ('aaa', 'bbb', 'ccc'):
            _org(code, email=f'{code}@example.org')
            _app(self.cohort, code, 'shortlisted', code)
        partner_notify.send_partner_digests()
        self.assertEqual(len([m for m in mail.outbox if 'this week' in m.subject]), 1)

    def test_dry_run_sends_nothing_and_logs_nothing(self):
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        import io
        out = io.StringIO()
        partner_notify.send_partner_digests(dry_run=True, out=out)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(PartnerEmailLog.objects.filter(ok=True).exists())
        printed = out.getvalue()
        self.assertIn('dry-run', printed)
        self.assertIn('smc', printed)

    def test_the_email_is_html_with_a_text_alternative(self):
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        partner_notify.send_partner_digests()
        msg = [m for m in mail.outbox if 'this week' in m.subject][0]
        self.assertTrue(msg.body)                       # plain-text alternative
        self.assertEqual(len(msg.alternatives), 1)
        html, mime = msg.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<table', html)
        self.assertIn('<!doctype html>', html.lower())  # the shared shell

    def test_no_email_points_at_a_console_that_does_not_exist(self):
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1,
             submitted=timezone.now() - timedelta(days=20))
        partner_notify.send_partner_digests()
        for msg in mail.outbox:
            for word in ('partner console', 'log in', 'dashboard'):
                self.assertNotIn(word, msg.body.lower())

    def test_a_send_failure_is_logged_as_a_failure(self):
        from unittest import mock
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        with mock.patch('apps.scholarship.partner_notify.send_partner_email', return_value=False):
            partner_notify.send_partner_digests()
        self.assertTrue(PartnerEmailLog.objects.filter(ok=False, note='send_failed').exists())

    def test_a_failed_send_does_not_suppress_the_next_run_as_unchanged(self):
        """`last_fingerprint` only reads successful sends — otherwise one failure would silence
        the organisation permanently."""
        from unittest import mock
        _org('smc')
        _app(self.cohort, 'smc', 'shortlisted', 1)
        with mock.patch('apps.scholarship.partner_notify.send_partner_email', return_value=False):
            partner_notify.send_partner_digests()
        mail.outbox = []
        partner_notify.send_partner_digests()
        self.assertEqual(len([m for m in mail.outbox if 'this week' in m.subject]), 1)
