"""#86 (27 Nov 2026): the "returned by QC" email links straight to the case.

The link rides in the shared `dashboard_link` value for `qc_returned` only, so a stored template
(which holds `{dashboard_link}`) carries it with no data change. Every other reviewer email, and a
`qc_returned` send without a case id (the golden fixture's call), keeps the dashboard login link.
"""
import types
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.scholarship import emails
from apps.scholarship.emails.shared import _P
from apps.scholarship.tests.test_reviewer_emails import REVIEWER, _patch_send

CASE = 513


def _case_url():
    return f'{_P.frontend_url}/admin/scholarship/{CASE}'


def _login_url():
    return f'{_P.frontend_url}/admin/login'


class TestTheReturnedEmailLinksTheCase(TestCase):
    def _templated_text(self, send, **kw):
        call_command('seed_partner_email_templates', verbosity=0)
        with _patch_send('_send_html') as templated:
            send(REVIEWER, 'Anand', ref='SC-7', applicant_name='the student', **kw)
        self.assertTrue(templated.called)
        return templated.call_args[0][3]   # (to, subject, html, text)

    def _built_in_text(self, send, **kw):   # no stored row: the hard-coded body sends
        with _patch_send('_send_plain') as plain:
            send(REVIEWER, 'Anand', ref='SC-7', applicant_name='the student', **kw)
        self.assertTrue(plain.called)
        return plain.call_args[0][2]   # (to, subject, body)

    def test_the_stored_template_carries_the_case_link(self):
        text = self._templated_text(emails.send_qc_returned_email, qc_comments='Recheck income.',
                                    case_id=CASE)
        self.assertIn(_case_url(), text)
        self.assertNotIn(_login_url(), text)

    def test_the_built_in_body_carries_the_case_link(self):
        text = self._built_in_text(emails.send_qc_returned_email, qc_comments='Recheck income.',
                                   case_id=CASE)
        self.assertIn(_case_url(), text)
        self.assertNotIn(_login_url(), text)

    def test_without_a_case_id_the_link_is_unchanged(self):
        for text in (self._built_in_text(emails.send_qc_returned_email, qc_comments='x'),
                     self._templated_text(emails.send_qc_returned_email, qc_comments='x')):
            self.assertIn(_login_url(), text)
            self.assertNotIn('/admin/scholarship/', text)

    def test_the_rejected_email_keeps_the_dashboard_link(self):
        for text in (self._built_in_text(emails.send_qc_rejected_email, qc_comments='x'),
                     self._templated_text(emails.send_qc_rejected_email, qc_comments='x')):
            self.assertIn(_login_url(), text)
            self.assertNotIn('/admin/scholarship/', text)

    def test_the_assigned_email_keeps_the_dashboard_link(self):
        call_command('seed_partner_email_templates', verbosity=0)
        with _patch_send('_send_html') as templated:
            emails.send_reviewer_assigned_email(REVIEWER, 'Anand', ref='SC-7', programme='P')
        text = templated.call_args[0][3]
        self.assertIn(_login_url(), text)
        self.assertNotIn('/admin/scholarship/', text)


class TestTheQcReopenPassesTheCase(TestCase):
    """`_email_reviewer` hands the case id to the returned send only."""

    def _app(self):
        reviewer = types.SimpleNamespace(email=REVIEWER, name='Anand')
        return types.SimpleNamespace(id=CASE, assigned_to=reviewer,
                                     profile=types.SimpleNamespace(name='the student'))

    def test_returned_carries_the_case_id(self):
        from apps.scholarship.views_admin.verdict import _email_reviewer
        with mock.patch('apps.scholarship.emails.send_qc_returned_email') as send:
            _email_reviewer(self._app(), 'returned', 'Recheck income.')
        self.assertEqual(send.call_args.kwargs['case_id'], CASE)

    def test_rejected_does_not(self):
        from apps.scholarship.views_admin.verdict import _email_reviewer
        with mock.patch('apps.scholarship.emails.send_qc_rejected_email') as send:
            _email_reviewer(self._app(), 'rejected', 'Declined.')
        self.assertNotIn('case_id', send.call_args.kwargs)
