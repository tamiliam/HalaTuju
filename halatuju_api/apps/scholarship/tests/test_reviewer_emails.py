"""Request #10 — the five reviewer emails become editable templates.

These five are LIVE mail. They were hard-coded prose; from this change the stored row is what
sends. Everything here exists because adopting a live email into a switchable template is the one
manoeuvre that can turn a feature into silence, and silence is invisible — nobody reports an email
they never knew was coming.

The three states are the spine of the file:

  row missing  → the built-in body still sends   (a seeding slip must not stop working mail)
  row OFF      → nothing sends                   (the switch has to mean stop, or it is a lie)
  row ON       → the row governs completely

and one property that has nothing to do with switches: whatever a QC typed reaches the reviewer
verbatim, because `qc_comments` is a structural block and not a scalar.
"""
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.scholarship import emails
from apps.scholarship.models import PartnerEmailTemplate

REVIEWER = 'anand@rv.test'


class _Base(TestCase):
    def seed(self):
        call_command('seed_partner_email_templates', verbosity=0)

    def send_assigned(self):
        return emails.send_reviewer_assigned_email(
            REVIEWER, 'Anand', ref='SC-0042', programme='BrightPath Bursary',
            review_by='12 August 2026')


class TestTheThreeStates(_Base):
    def test_with_NO_ROW_the_built_in_body_still_sends(self):
        # The dangerous direction. A missed seed must degrade to the old behaviour, never to none.
        self.assertFalse(PartnerEmailTemplate.objects.filter(kind='reviewer_assigned').exists())
        with mock.patch.object(emails, '_send_plain', return_value=True) as legacy, \
                mock.patch.object(emails, '_send_html') as templated:
            self.assertTrue(self.send_assigned())
        legacy.assert_called_once()
        templated.assert_not_called()

    def test_with_the_row_ON_the_row_governs(self):
        self.seed()
        with mock.patch.object(emails, '_send_plain') as legacy, \
                mock.patch.object(emails, '_send_html') as templated:
            self.assertTrue(self.send_assigned())
        templated.assert_called_once()
        legacy.assert_not_called()

    def test_with_the_row_OFF_NOTHING_sends(self):
        # ⚠ The switch must STOP it. Keying the fallback on `enabled` instead of on the row's
        # existence would leave the old sender mailing behind the owner's back — the screen would
        # say off while the system said on.
        self.seed()
        PartnerEmailTemplate.objects.filter(kind='reviewer_assigned').update(enabled=False)
        with mock.patch.object(emails, '_send_plain') as legacy, \
                mock.patch.object(emails, '_send_html') as templated:
            self.assertFalse(self.send_assigned())
        legacy.assert_not_called()
        templated.assert_not_called()

    def test_all_five_seed_switched_ON(self):
        self.seed()
        off = set(PartnerEmailTemplate.objects
                  .filter(kind__in=PartnerEmailTemplate.REVIEWER_KINDS, enabled=False)
                  .values_list('kind', flat=True))
        self.assertEqual(off, set())

    @override_settings(PARTNER_COMMS_ENABLED=False)
    def test_the_PARTNER_flag_does_not_silence_reviewer_mail(self):
        # That flag answers "what do ORGANISATIONS receive?". Taking partner comms dark for an
        # unrelated reason must not stop telling a volunteer they have been given a case.
        self.seed()
        with mock.patch.object(emails, '_send_html') as templated:
            self.assertTrue(self.send_assigned())
        templated.assert_called_once()

    def test_a_broken_template_falls_back_rather_than_losing_the_email(self):
        # Best-effort mail on the side of an assignment. A human editing a body into an
        # unrenderable state must not take the working sender down with it.
        self.seed()
        with mock.patch('apps.scholarship.partner_comms.render',
                        side_effect=ValueError('boom')), \
                mock.patch.object(emails, '_send_plain', return_value=True) as legacy:
            self.assertTrue(self.send_assigned())
        legacy.assert_called_once()

    def test_no_recipient_sends_nothing_by_either_route(self):
        self.seed()
        with mock.patch.object(emails, '_send_plain') as legacy, \
                mock.patch.object(emails, '_send_html') as templated:
            self.assertFalse(emails.send_reviewer_assigned_email('', 'Anand'))
        legacy.assert_not_called()
        templated.assert_not_called()


class TestWhatActuallyRenders(_Base):
    def _rendered(self, fn):
        with mock.patch.object(emails, '_send_html') as templated:
            fn()
        self.assertTrue(templated.called, 'the template path did not run')
        _to, subject, html, text = templated.call_args[0][:4]
        return subject, html, text

    def test_no_placeholder_survives_rendering(self):
        # The failure this catches is silent: a `{token}` nobody supplies renders literally into a
        # volunteer's inbox and only a human reading the email would ever notice.
        self.seed()
        subject, html, text = self._rendered(self.send_assigned)
        for part in (subject, html, text):
            self.assertNotRegex(part, r'\{[a-z_]+\}')

    def test_the_subject_carries_the_scholar_code_reviewers_triage_by(self):
        self.seed()
        subject, _html, _text = self._rendered(self.send_assigned)
        self.assertIn('SC-0042', subject)

    def test_the_reviewer_gets_a_greeting_even_with_no_name_on_file(self):
        self.seed()
        _s, _h, text = self._rendered(
            lambda: emails.send_reviewer_assigned_email(REVIEWER, '', ref='SC-1'))
        self.assertIn('Dear there,', text)

    def test_due_soon_and_overdue_are_DIFFERENT_emails(self):
        # One stored body cannot say both; the split is why there are five kinds and not four.
        self.seed()
        soon, _h, soon_text = self._rendered(lambda: emails.send_reviewer_verdict_due_email(
            REVIEWER, reviewer_name='Anand', applicant_name='Siti', ref='SC-9',
            due_by='10 August', overdue=False))
        late, _h2, late_text = self._rendered(lambda: emails.send_reviewer_verdict_due_email(
            REVIEWER, reviewer_name='Anand', applicant_name='Siti', ref='SC-9',
            due_by='10 August', overdue=True))
        self.assertNotEqual(soon, late)
        self.assertIn('due soon', soon_text)
        self.assertIn('overdue', late_text)


class TestTheQcsOwnWords(_Base):
    def _qc_text(self, comments):
        with mock.patch.object(emails, '_send_html') as templated:
            emails.send_qc_returned_email(
                REVIEWER, 'Anand', ref='SC-7', applicant_name='Siti', qc_comments=comments)
        return templated.call_args[0][3]

    def test_the_comments_reach_the_reviewer_verbatim(self):
        self.seed()
        self.assertIn('The income band was misread.',
                      self._qc_text('The income band was misread.'))

    def test_a_TOKEN_typed_by_the_QC_is_NOT_substituted(self):
        # ⚠ THE REASON `qc_comments` IS A BLOCK AND NOT A SCALAR. A scalar is filled in before the
        # next pass, so a QC who happened to type `{ref}` would have it resolved as though the
        # template had asked for it. A block lands after substitution finishes.
        self.seed()
        text = self._qc_text('Check {ref} and {applicant_name} again.')
        self.assertIn('{ref}', text)
        self.assertIn('{applicant_name}', text)

    def test_it_keeps_the_QCs_paragraphs(self):
        self.seed()
        text = self._qc_text('First point.\n\nSecond point.')
        self.assertIn('First point.', text)
        self.assertIn('Second point.', text)

    def test_a_CALLER_that_forgets_the_comments_leaks_no_token(self):
        # ⚠ The structural token has to be filled even when nobody supplied it. Otherwise a call
        # site that omits `qc_comments` puts the literal string "{qc_comments}" in a volunteer's
        # inbox — no exception, no log line, and only a human reading the email would notice.
        from apps.scholarship import partner_comms
        from apps.scholarship.models import PartnerEmailTemplate as _T
        self.seed()
        tpl = _T.objects.get(kind='qc_returned')
        subject, text, html = partner_comms.render('qc_returned', tpl, {'reviewer_name': 'Anand'})
        for part in (subject, text, html):
            self.assertNotRegex(part, r'\{[a-z_]+\}')

    def test_an_empty_reason_does_not_crash_the_email(self):
        self.seed()
        with mock.patch.object(emails, '_send_html') as templated:
            emails.send_qc_returned_email(REVIEWER, 'Anand', ref='SC-7', qc_comments='')
        self.assertTrue(templated.called)
