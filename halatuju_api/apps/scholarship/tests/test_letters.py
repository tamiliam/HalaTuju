"""Student maintenance Sprint 6b — formal letters (`letters.py`, `views_admin/letters.py`, `views_bursary`).

Every door in the plan, each pinned (owner rulings 2026-10-30):
  * ISSUE — suspension/termination super or org_admin only; general/discipline/close-out the case
    writer; an unassigned reviewer, finance, another organisation and a student refused; a typed FULL
    NAME confirms discipline and termination, on the server; a closed file takes only general and
    close-out; a missing clause refuses wording that needs one.
  * DOCUMENTS ONLY — no status, sub-state or payment changes; termination makes the file PROMPT.
  * THE PDF — at `build_doc_key(app, 'letters', …)`, private; a failed upload issues nothing; the
    link is minted for THIS application's own path only.
  * THE EMAIL — always sent (even with the results flag off); `emailed_at` set ONLY when it went.
  * WITHDRAW — super / org_admin, a reason, once; the row stays.
  * THE STUDENT — her own letters only; acknowledge once ("does not mean you agree"), never a
    withdrawn one; the hub badge counts what waits for her.
  * NEVER A SPONSOR, PARTNER OR SOURCE READER.
"""
import datetime
import pathlib
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import letters as svc
from apps.scholarship.models import Disbursement, Letter, LetterTemplate, StudentActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)

UPLOAD = 'apps.scholarship.storage.upload_object'
SIGN = 'apps.scholarship.storage.create_signed_download_url'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
API = '/api/v1/admin/scholarship/scholars/{}/letters/'
HER = '/api/v1/scholarship/bursary/letters/'


def _scholar(**over):
    return make_application('maintenance', active_at=timezone.now() - datetime.timedelta(days=60),
                            notify_email='aisyah@example.test', locale='ta', **over)


@LOCMEM
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar()
        self.org = self.app.owning_organisation
        self.name = svc.student_name(self.app)
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.reviewer = make_admin('reviewer', owning_org=self.org)
        type(self.app).objects.filter(pk=self.app.pk).update(assigned_to=self.reviewer)
        self.app.refresh_from_db()
        patcher = patch(UPLOAD, return_value=True)
        self.upload = patcher.start()
        self.addCleanup(patcher.stop)

    def _issue(self, admin, **body):
        payload = {'kind': 'general', 'language': 'en', 'note': 'Your payment date moves to the 5th.'}
        payload.update(body)
        with self.captureOnCommitCallbacks(execute=True):
            return authed_client(admin).post(API.format(self.app.id), payload, format='json')


class TestWhoMayIssue(_Base):
    def test_org_admin_issues_every_kind_and_the_assigned_reviewer_only_the_ordinary_ones(self):
        for kind in ('general', 'discipline', 'suspension', 'termination', 'close_out'):
            with self.subTest(kind=kind):
                r = self._issue(self.org_admin, kind=kind, clause='9', confirm_name=self.name)
                self.assertEqual(r.status_code, 201, r.content)
        for kind, code in (('general', 201), ('discipline', 201), ('close_out', 201),
                           ('suspension', 403), ('termination', 403)):
            with self.subTest(reviewer=kind):
                r = self._issue(self.reviewer, kind=kind, clause='5', confirm_name=self.name)
                self.assertEqual(r.status_code, code, r.content)

    def test_others_are_refused(self):
        unassigned = make_admin('reviewer', owning_org=self.org)
        finance = make_admin('finance', owning_org=self.org)
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        self.assertEqual(self._issue(unassigned).status_code, 403)
        self.assertEqual(self._issue(finance).status_code, 403)
        self.assertEqual(self._issue(stranger).status_code, 404)
        student = authed_client(self.app.profile.supabase_user_id)
        self.assertIn(student.post(API.format(self.app.id), {'kind': 'general', 'language': 'en'},
                                   format='json').status_code, (401, 403))
        self.assertFalse(Letter.objects.exists())

    def test_the_tab_says_what_this_admin_may_issue(self):
        body = authed_client(self.reviewer).get(API.format(self.app.id)).json()
        self.assertEqual(body['can_issue'], ['general', 'discipline', 'close_out'])
        self.assertFalse(body['can_withdraw'])
        body = authed_client(self.org_admin).get(API.format(self.app.id)).json()
        self.assertEqual(body['can_issue'], list(svc.KINDS))
        self.assertEqual(body['response_days'], 14)


class TestTheTypedConfirm(_Base):
    def test_a_wrong_name_issues_nothing_and_the_full_name_issues(self):
        for kind in ('discipline', 'termination'):
            with self.subTest(kind=kind):
                for typed in ('', self.name.split()[0], self.name + ' x'):
                    r = self._issue(self.org_admin, kind=kind, clause='5', confirm_name=typed)
                    self.assertEqual((r.status_code, r.json()['code']), (400, 'confirm_mismatch'))
                r = self._issue(self.org_admin, kind=kind, clause='5',
                                confirm_name='  ' + self.name.upper().replace(' ', '   ') + ' ')
                self.assertEqual(r.status_code, 201)
        self.assertEqual(Letter.objects.count(), 2)

    def test_general_needs_no_confirm(self):
        self.assertEqual(self._issue(self.org_admin, kind='general').status_code, 201)


class TestDocumentsOnly(_Base):
    def test_a_termination_changes_no_status_substate_or_money_and_prompts_close(self):
        before = (self.app.status, self.app.maintenance_substate, Disbursement.objects.count())
        r = self._issue(self.org_admin, kind='termination', clause='9', confirm_name=self.name)
        self.assertEqual(r.status_code, 201)
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.maintenance_substate, Disbursement.objects.count()), before)
        tab = authed_client(self.org_admin).get(API.format(self.app.id)).json()
        self.assertTrue(tab['prompt_close'])
        authed_client(self.org_admin).post(API.format(self.app.id) + f'{r.json()["id"]}/withdraw/',
                                           {'reason': 'wrong student'}, format='json')
        self.assertFalse(authed_client(self.org_admin).get(API.format(self.app.id)).json()['prompt_close'])

    def test_a_closed_file_takes_only_general_and_close_out(self):
        type(self.app).objects.filter(pk=self.app.pk).update(status='closed', closure_reason='graduated')
        self.app.refresh_from_db()
        r = self._issue(self.org_admin, kind='termination', clause='9', confirm_name=self.name)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'file_closed'))
        self.assertEqual(self._issue(self.org_admin, kind='close_out').status_code, 201)
        self.assertEqual(authed_client(self.org_admin).get(API.format(self.app.id)).json()['can_issue'],
                         ['general', 'close_out'])

    def test_wording_that_names_a_clause_refuses_without_one(self):
        r = self._issue(self.org_admin, kind='suspension', clause='')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'clause_required'))


class TestTheLetterItself(_Base):
    def test_text_is_frozen_the_due_date_stamped_and_the_pdf_stored_at_her_own_path(self):
        from apps.courses import org_config
        r = self._issue(self.org_admin, kind='discipline', clause='5', confirm_name=self.name,
                        note='Semester 3 results were not sent.')
        letter = Letter.objects.get(pk=r.json()['id'])
        self.assertIn('clause 5', letter.subject)
        self.assertIn('Semester 3 results were not sent.', letter.body)
        self.assertEqual(letter.response_due_on, timezone.localdate() + datetime.timedelta(days=14))
        self.assertEqual(letter.pdf_path, f'{self.org.id}/{self.app.id}/letters/{letter.id}.pdf')
        self.assertEqual(self.upload.call_args.args[0], letter.pdf_path)
        self.assertTrue(self.upload.call_args.args[1].startswith(b'%PDF'))   # a real render
        # A changed setting moves NEW letters only: the date she was given stays.
        with patch.object(org_config, 'value', return_value=30):
            r2 = self._issue(self.org_admin, kind='general')
        letter.refresh_from_db()
        self.assertEqual(letter.response_due_on, timezone.localdate() + datetime.timedelta(days=14))
        self.assertEqual(Letter.objects.get(pk=r2.json()['id']).response_due_on,
                         timezone.localdate() + datetime.timedelta(days=30))
        LetterTemplate.objects.create(organisation=self.org, kind='general', language='en',
                                      subject='CHANGED', body='Changed {name}')
        letter.refresh_from_db()
        self.assertIn('clause 5', letter.subject)                     # an edit never rewrites an issued letter

    def test_a_failed_upload_issues_nothing(self):
        self.upload.return_value = False
        r = self._issue(self.org_admin, kind='general')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'storage_failed'))
        self.assertFalse(Letter.objects.exists())
        self.assertFalse(StudentActivity.objects.filter(event='letter_issued').exists())
        self.assertEqual(mail.outbox, [])

    def test_the_malay_pdf_is_in_malay_and_tamil_is_refused(self):
        r = self._issue(self.org_admin, kind='general', language='ms')
        self.assertIn('Surat', Letter.objects.get(pk=r.json()['id']).subject)
        r = self._issue(self.org_admin, kind='general', language='ta')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'unknown_language'))

    def test_the_pdf_link_is_her_own_path_only(self):
        r = self._issue(self.org_admin, kind='general')
        lid = r.json()['id']
        with patch(SIGN, return_value='https://signed.example/x') as sign:
            body = authed_client(self.org_admin).get(API.format(self.app.id) + f'{lid}/pdf/').json()
        self.assertEqual(body['url'], 'https://signed.example/x')
        self.assertEqual(sign.call_args.kwargs['expires_in'], 300)
        Letter.objects.filter(pk=lid).update(pdf_path='99/1/letters/1.pdf')    # not this application's
        with patch(SIGN, return_value='https://signed.example/x'):
            self.assertEqual(authed_client(self.org_admin).get(
                API.format(self.app.id) + f'{lid}/pdf/').status_code, 404)

    def test_issuing_logs_activity(self):
        r = self._issue(self.org_admin, kind='general')
        row = StudentActivity.objects.get(application=self.app, event='letter_issued')
        self.assertEqual(row.meta['letter_id'], r.json()['id'])


class TestTheNoticeEmail(_Base):
    @override_settings(MAINTENANCE_REMINDERS_ENABLED=False)
    def test_always_sent_in_her_language_even_with_the_results_flag_off_and_stamped(self):
        r = self._issue(self.org_admin, kind='general')
        self.assertEqual([m.to for m in mail.outbox], [['aisyah@example.test']])
        self.assertIn('கடிதம்', mail.outbox[0].subject)                        # her language: Tamil
        letter = Letter.objects.get(pk=r.json()['id'])
        self.assertIsNotNone(letter.emailed_at)
        self.assertEqual(letter.emailed_to, 'aisyah@example.test')
        self.assertEqual(r.json()['emailed_to'], '')                          # serialised before commit
        tab = authed_client(self.org_admin).get(API.format(self.app.id)).json()
        self.assertEqual(tab['letters'][0]['emailed_to'], 'a…@example.test')

    def test_a_failed_send_leaves_emailed_at_null_and_resend_stamps_it(self):
        with patch('apps.scholarship.emails.sending._send_html', return_value=False):
            r = self._issue(self.org_admin, kind='general')
        letter = Letter.objects.get(pk=r.json()['id'])
        self.assertIsNone(letter.emailed_at)
        self.assertIsNone(letter.emailed_to)
        r = authed_client(self.org_admin).post(API.format(self.app.id) + f'{letter.id}/resend/', format='json')
        self.assertEqual(r.status_code, 200)
        letter.refresh_from_db()
        self.assertIsNotNone(letter.emailed_at)

    def test_no_switch_can_silence_it(self):
        from apps.scholarship import student_email_catalogue as cat
        with self.assertRaises(cat.NotSwitchable):
            cat.set_switch(self.org, 'letter_issued', False)


class TestWithdraw(_Base):
    def test_org_admin_withdraws_with_a_reason_once_and_the_row_stays(self):
        lid = self._issue(self.org_admin, kind='general').json()['id']
        url = API.format(self.app.id) + f'{lid}/withdraw/'
        self.assertEqual(authed_client(self.reviewer).post(url, {'reason': 'x'}, format='json').status_code, 403)
        r = authed_client(self.org_admin).post(url, {'reason': '  '}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'reason_required'))
        r = authed_client(self.org_admin).post(url, {'reason': 'Issued to the wrong student'}, format='json')
        self.assertEqual((r.status_code, r.json()['state']), (200, 'withdrawn'))
        r = authed_client(self.org_admin).post(url, {'reason': 'again'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'withdrawn'))
        self.assertEqual(Letter.objects.count(), 1)
        self.assertTrue(StudentActivity.objects.filter(event='letter_withdrawn').exists())
        r = authed_client(self.org_admin).post(API.format(self.app.id) + f'{lid}/resend/', format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'withdrawn'))

    def test_nothing_is_edited_or_deleted_after_issue(self):
        lid = self._issue(self.org_admin, kind='general').json()['id']
        client = authed_client(self.org_admin)
        self.assertEqual(client.delete(API.format(self.app.id) + f'{lid}/withdraw/').status_code, 405)
        self.assertEqual(client.put(API.format(self.app.id), {}, format='json').status_code, 405)
        self.assertEqual(client.post(API.format(self.app.id) + f'{lid}/edit/', {}, format='json').status_code, 404)


class TestTheStudent(_Base):
    def _her(self, student=None):
        return authed_client(student or self.app.profile.supabase_user_id)

    def test_she_reads_and_acknowledges_her_own_letter_once(self):
        lid = self._issue(self.org_admin, kind='general').json()['id']
        body = self._her().get(HER).json()
        self.assertEqual([x['id'] for x in body['letters']], [lid])
        self.assertNotIn('issued_by_name', body['letters'][0])
        self.assertNotIn('emailed_to', body['letters'][0])
        self.assertFalse(body['letters'][0]['read'])
        self.assertEqual(self._her().post(HER + f'{lid}/read/').json()['read'], True)
        summary = self._her().get('/api/v1/scholarship/bursary/summary/').json()
        self.assertEqual((summary['has_letters'], summary['letters_to_acknowledge']), (True, 1))
        r = self._her().post(HER + f'{lid}/acknowledge/')
        self.assertEqual(r.json()['state'], 'acknowledged')
        first = Letter.objects.get(pk=lid).acknowledged_at
        self._her().post(HER + f'{lid}/acknowledge/')
        self.assertEqual(Letter.objects.get(pk=lid).acknowledged_at, first)     # once
        self.assertEqual(StudentActivity.objects.filter(event='letter_acknowledged').count(), 1)
        self.assertEqual(self._her().get('/api/v1/scholarship/bursary/summary/').json()['letters_to_acknowledge'], 0)

    def test_another_students_letter_is_not_found(self):
        lid = self._issue(self.org_admin, kind='general').json()['id']
        other = _scholar()
        client = self._her(other.profile.supabase_user_id)
        self.assertEqual(client.get(HER).json()['letters'], [])
        self.assertEqual(client.post(HER + f'{lid}/acknowledge/').status_code, 404)
        with patch(SIGN, return_value='https://signed.example/x'):
            self.assertEqual(client.get(HER + f'{lid}/pdf/').status_code, 404)
        self.assertIsNone(Letter.objects.get(pk=lid).acknowledged_at)
        nobody = make_student()
        self.assertEqual(self._her(nobody.supabase_user_id).get(HER).status_code, 404)

    def test_a_withdrawn_letter_cannot_be_acknowledged(self):
        lid = self._issue(self.org_admin, kind='general').json()['id']
        authed_client(self.org_admin).post(API.format(self.app.id) + f'{lid}/withdraw/', {'reason': 'x'},
                                           format='json')
        r = self._her().post(HER + f'{lid}/acknowledge/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'withdrawn'))
        self.assertEqual(self._her().get(HER).json()['letters'][0]['state'], 'withdrawn')

    def test_an_unacknowledged_letter_goes_overdue_after_its_date(self):
        lid = self._issue(self.org_admin, kind='general').json()['id']
        Letter.objects.filter(pk=lid).update(response_due_on=timezone.localdate() - datetime.timedelta(days=1))
        self.assertEqual(self._her().get(HER).json()['letters'][0]['state'], 'overdue')
        self.assertEqual(authed_client(self.org_admin).get(API.format(self.app.id)).json()['letters'][0]['state'],
                         'overdue')


class TestNeverASponsorPartnerOrSourceReader(TestCase):
    """No module that serves a sponsor, a referral partner or a source imports letters, and the only
    reader of the activity log (where letter events land) is the staff scholar file."""

    SERVES_OTHERS = ('views_sponsor.py', 'spend_sponsor.py', 'sponsor_feed.py', 'sponsor_notify.py',
                     'sponsor_comms.py', 'partner_comms.py', 'partner_notify.py', 'source_console.py',
                     'views_admin/source_console.py', 'views_admin/sponsors.py', 'views_admin/sources.py')

    def test_no_sponsor_partner_or_source_module_reads_letters(self):
        root = pathlib.Path(svc.__file__).parent
        for rel in self.SERVES_OTHERS:
            path = root / rel
            if not path.exists():
                continue
            with self.subTest(module=rel):
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('letters', text.replace('newsletters', ''))
                self.assertNotIn('Letter', text.replace('Newsletter', ''))

    def test_the_activity_log_is_read_only_by_the_staff_file(self):
        root = pathlib.Path(svc.__file__).parent
        readers = sorted(str(p.relative_to(root)).replace('\\', '/') for p in root.rglob('*.py')
                         if 'tests' not in p.parts and 'migrations' not in p.parts
                         and 'StudentActivity' in p.read_text(encoding='utf-8'))
        self.assertEqual(readers, ['activity.py', 'models/__init__.py', 'models/activity.py', 'scholars.py',
                                   'views_admin/scholars.py'])


class TestLetterWording(TestCase):
    def test_every_kind_has_wording_in_english_and_malay_using_only_its_tokens(self):
        from apps.scholarship import email_templates, letter_defaults
        for kind in svc.KINDS:
            for lang in svc.LANGUAGES:
                with self.subTest(kind=kind, lang=lang):
                    subject, body = letter_defaults.DEFAULTS[kind][lang]
                    self.assertEqual(email_templates.unknown_placeholders(
                        letter_defaults.PLACEHOLDERS, subject, body), ())
                    self.assertIn('{response_due}', body)

    def test_the_settings_page_saves_and_resets_and_refuses(self):
        app = _scholar()
        org = app.owning_organisation
        url = '/api/v1/admin/scholarship/organisation/letter-templates/'
        with self.settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET):
            client = authed_client(make_admin('org_admin', owning_org=org))
            self.assertEqual(len(client.get(url).json()['templates']), 10)            # 5 kinds x en/ms
            r = client.put(url, {'kind': 'general', 'language': 'ms', 'subject': 'Surat', 'body': '{name} {iban}'},
                           format='json')
            self.assertEqual((r.status_code, r.json()['code']), (400, 'unknown_placeholders'))
            r = client.put(url, {'kind': 'general', 'language': 'ta', 'subject': 'x', 'body': 'y'}, format='json')
            self.assertEqual(r.json()['code'], 'unknown_template')
            client.put(url, {'kind': 'general', 'language': 'ms', 'subject': 'Surat', 'body': 'Salam {name}'},
                       format='json')
            self.assertEqual(svc.letter_wording(org, 'general', 'ms')[:2], ('Surat', 'Salam {name}'))
            client.put(url, {'kind': 'general', 'language': 'ms', 'reset': True}, format='json')
            self.assertFalse(LetterTemplate.objects.exists())
            for role in ('reviewer', 'finance', 'admin'):
                with self.subTest(role=role):
                    self.assertEqual(authed_client(make_admin(role, owning_org=org)).get(url).status_code, 403)


@LOCMEM
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestEveryLetterRouteOverHttp(TestCase):
    """Each letters route driven by a literal path (the route walk in `test_endpoint_exercise` reads
    them), and the dialog's preview: the letter and her email, nothing written."""

    def setUp(self):
        self.app = _scholar()
        self.admin = make_admin('org_admin', owning_org=self.app.owning_organisation)
        patcher = patch(UPLOAD, return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_preview_tab_issue_pdf_and_withdraw(self):
        client = authed_client(self.admin)
        pk = self.app.id
        r = client.post(f'/api/v1/admin/scholarship/scholars/{pk}/letters/preview/',
                        {'kind': 'discipline', 'language': 'ms', 'clause': '5', 'note': 'Keputusan.'}, format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn('fasal 5', body['subject'])
        self.assertEqual((body['email']['language'], body['needs_confirm']), ('ta', True))
        self.assertIn('கடிதம்', body['email']['subject'])
        self.assertFalse(Letter.objects.exists())                          # a preview writes nothing
        self.assertEqual(mail.outbox, [])
        self.assertEqual(client.get(f'/api/v1/admin/scholarship/scholars/{pk}/letters/').status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            lid = client.post(f'/api/v1/admin/scholarship/scholars/{pk}/letters/',
                              {'kind': 'general', 'language': 'en'}, format='json').json()['id']
        with patch(SIGN, return_value='https://signed.example/x'):
            self.assertEqual(client.get(f'/api/v1/admin/scholarship/scholars/{pk}/letters/{lid}/pdf/').status_code, 200)
        r = client.post(f'/api/v1/admin/scholarship/scholars/{pk}/letters/{lid}/withdraw/', {'reason': 'x'},
                        format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(client.post(f'/api/v1/admin/scholarship/scholars/{pk}/letters/{lid}/archive/', {},
                                     format='json').status_code, 404)
