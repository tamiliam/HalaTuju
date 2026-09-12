"""Vircle Airtable integration (vircle_airtable.py) — we tell Vircle WHO, Vircle tells us the
WALLET.

The load-bearing behaviours, in the order they can hurt someone:

  * the OUTBOUND push can never fail the student's own confirmation (fault-injected);
  * the INBOUND write never overwrites a stored wallet id (the field decides where money goes —
    a mismatch is logged for a human, not auto-resolved);
  * an invalid wallet id (fails `valid_vircle_id`) is refused, exactly as a typed one would be;
  * matching is by NRIC DIGITS (dashes or not), restricted to the relay population, so a webhook
    row can never write onto a rejected/expired file;
  * the endpoint is inert without the shared secret.
"""
from unittest import mock

import jwt
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship import emails, vircle_airtable
from apps.scholarship.resolution import VIRCLE_CODE
from apps.scholarship.vircle import raise_setup_task

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      _TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _make(self, uid, status='awarded', nric='080214-08-1234', name='KAVITHA A/P SURESH',
              vircle_id=''):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name=name, nric=nric, contact_phone='0123456789',
            preferred_state='Perak', household_income=1500, household_size=4,
            receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status, vircle_id=vircle_id,
            profile_completed_at=timezone.now(), notify_email='k@example.com',
        )


# ── The outbound payload ─────────────────────────────────────────────────────
class TestRecipientPayload(_Base):
    def test_principal_for_a_student_who_can_hold_their_own_account(self):
        app = self._make('u1', nric='080214081234')   # born 2008 → can register
        p = vircle_airtable.recipient_payload(app)
        self.assertEqual(p, {'Name': 'KAVITHA A/P SURESH',
                             'NRIC': '080214-08-1234',   # digits → the dashed shape the guide shows
                             'Type': 'Principal'})

    def test_supplementary_for_a_child_registration(self):
        # Born after 2008 → registers under a parent = Supplementary (Gokula, 2026-09-08).
        # The SAME birth-year rule the setup email uses — not a second copy of it.
        app = self._make('u2', nric='090101-08-1234')
        self.assertEqual(vircle_airtable.recipient_payload(app)['Type'], 'Supplementary')

    def test_a_non_12_digit_nric_is_passed_through_untouched(self):
        app = self._make('u3', nric='A1234567')
        self.assertEqual(vircle_airtable.recipient_payload(app)['NRIC'], 'A1234567')


# ── The push rides the student's confirmation and can never break it ─────────
@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET, VIRCLE_SETUP_ENABLED=True,
                   VIRCLE_AIRTABLE_PUSH_URL='https://hooks.airtable.example/wh')
class TestPushOnConfirm(_Base):
    def setUp(self):
        self.client = APIClient()
        self.app = self._make('u1')
        raise_setup_task(self.app)
        self.item = self.app.resolution_items.get(code=VIRCLE_CODE)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("u1")}')

    def _resolve(self):
        return self.client.post(
            f'/api/v1/scholarship/resolution-items/{self.item.id}/resolve/',
            {'text': '012-345 6789', 'vircle_id': '8000400175123'}, format='json')

    @mock.patch('requests.post')
    def test_confirming_pushes_name_nric_type_to_vircle(self, post):
        post.return_value = mock.Mock(status_code=200)
        r = self._resolve()
        self.assertEqual(r.status_code, 200)
        (url,), kwargs = post.call_args
        self.assertEqual(url, 'https://hooks.airtable.example/wh')
        self.assertEqual(kwargs['json'], {'Name': 'KAVITHA A/P SURESH',
                                         'NRIC': '080214-08-1234', 'Type': 'Principal'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.params.get('airtable_push'), 'sent')

    @mock.patch('requests.post', side_effect=OSError('network down'))
    def test_a_dead_webhook_never_fails_the_confirmation(self, post):
        # Fault injection — the usage-meter contract. The student's confirm succeeds, the
        # wallet id is stored, and the failure is recorded on the item for the cockpit.
        r = self._resolve()
        self.assertEqual(r.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'resolved')
        self.app.refresh_from_db()
        self.assertEqual(self.app.vircle_id, '8000400175123')
        self.assertEqual(self.item.params.get('airtable_push'), 'failed')

    @override_settings(VIRCLE_AIRTABLE_PUSH_URL='')
    @mock.patch('requests.post')
    def test_no_url_configured_means_no_call_at_all(self, post):
        self._resolve()
        post.assert_not_called()


# ── The inbound update ───────────────────────────────────────────────────────
class TestApplyUpdate(_Base):
    def test_sets_wallet_and_activation_matched_on_nric_digits(self):
        app = self._make('u1', nric='080214-08-1234')
        # Vircle sends bare digits; we store dashed — digits-matching bridges them.
        out = vircle_airtable.apply_update({'NRIC': '080214081234',
                                            'Wallet ID': '8000400181509',
                                            'Activated On': '08/09/2026'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'set')
        self.assertEqual(out['activated'], 'set')
        self.assertEqual(app.vircle_id, '8000400181509')
        self.assertIsNotNone(app.vircle_activated_at)

    def test_a_stored_wallet_is_NEVER_overwritten(self):
        # The field decides where money goes. A disagreement between Vircle's row and our
        # stored id is a human's question — auto-resolving it is how a wrong id becomes a
        # wrong payment with no witness.
        app = self._make('u1', vircle_id='8000400175123')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400179999'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'mismatch')
        self.assertEqual(app.vircle_id, '8000400175123')

    def test_an_identical_wallet_reads_kept(self):
        self._make('u1', vircle_id='8000400175123')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '="8000400175123"'})
        self.assertEqual(out['wallet'], 'kept')

    def test_an_invalid_wallet_is_refused_like_a_typed_one(self):
        # Same gate as the Action Centre: valid_vircle_id. A DuitNow-shaped or out-of-band
        # value from the webhook is held for a human, never stored.
        app = self._make('u1')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400101003'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'invalid')
        self.assertEqual(app.vircle_id, '')

    def test_activation_is_set_if_null_only(self):
        app = self._make('u1')
        when = timezone.now()
        app.vircle_activated_at = when
        app.save(update_fields=['vircle_activated_at'])
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Activated On': '01/01/2020'})
        app.refresh_from_db()
        self.assertEqual(out['activated'], 'kept')
        self.assertEqual(app.vircle_activated_at, when)

    def test_their_own_QR_Activated_Date_column_is_read(self):
        # Their Recipients table spells it "QR Activated Date" (owner's screenshots, 2026-09-11).
        # It was missing from the alias list, so a date they sent was silently discarded.
        app = self._make('u1')
        out = vircle_airtable.apply_update({'MYKAD': '080214081234',
                                            'QR Activated Date': '11/09/2026'})
        app.refresh_from_db()
        self.assertEqual(out['activated'], 'set')
        self.assertIsNotNone(app.vircle_activated_at)

    def test_status_Done_activates_even_with_no_date(self):
        # Owner ruling: "Done is when the account is activated… treat the date we receive the
        # notification with status Done as the activation date." Every row they have sent so far
        # carries a blank QR Activated Date, so the status is the only signal there is.
        app = self._make('u1')
        out = vircle_airtable.apply_update({'MYKAD': '080214081234',
                                            'Principal Wallet ID': '8000400184238',
                                            'Status': 'Done'})
        app.refresh_from_db()
        self.assertEqual(out['activated'], 'set')
        self.assertIsNotNone(app.vircle_activated_at)

    def test_status_Pending_Vircle_Activation_activates_NOTHING(self):
        # The dangerous direction. "Pending Vircle Activation" is a present, non-empty value — a
        # bare presence check would read it as an activation and mark an unusable wallet live.
        app = self._make('u1')
        out = vircle_airtable.apply_update({'MYKAD': '080214081234',
                                            'Principal Wallet ID': '8000400184238',
                                            'Status': 'Pending Vircle Activation'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'set')       # the id still lands
        self.assertEqual(out['activated'], 'none')   # the activation does not
        self.assertIsNone(app.vircle_activated_at)

    def test_a_dated_row_keeps_its_own_date_rather_than_today(self):
        # When Vircle DO fill the column, that date wins over the arrival time.
        app = self._make('u1')
        vircle_airtable.apply_update({'MYKAD': '080214081234',
                                      'QR Activated Date': '01/03/2026',
                                      'Status': 'Done'})
        app.refresh_from_db()
        # ⚠ localtime, not .date() — the stored value is UTC and midnight in Malaysia is the
        # PREVIOUS day there. That is TD-209, and it bit this very test on the first run.
        self.assertEqual(timezone.localtime(app.vircle_activated_at).date().isoformat(),
                         '2026-03-01')

    def test_the_supplementary_wallet_is_NEVER_read(self):
        # Owner ruling 2026-09-11: money is only ever paid into the PRINCIPAL wallet; the parent
        # passes it to the child, and spending is tracked on the principal. A row carrying only a
        # supplementary id must store nothing — paying it would pay a wallet nobody reconciles.
        app = self._make('u1')
        out = vircle_airtable.apply_update({'MYKAD': '080214081234',
                                            'Supp Wallet ID': '8000400184299'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'none')
        self.assertEqual(app.vircle_id, '')

    def test_unknown_nric_reports_no_match(self):
        self._make('u1', nric='080214-08-1234')
        out = vircle_airtable.apply_update({'NRIC': '990101-14-5678',
                                            'Wallet ID': '8000400175123'})
        self.assertEqual(out, {'ok': False, 'reason': 'no_match'})

    def test_a_rejected_file_is_outside_the_population(self):
        # Restricted to VIRCLE_SETUP_STATES — a webhook row can never write onto a closed-out
        # application, even with a matching NRIC.
        app = self._make('u1', status='rejected')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400175123'})
        app.refresh_from_db()
        self.assertEqual(out['reason'], 'no_match')
        self.assertEqual(app.vircle_id, '')


# ── The alert on the money-routing write ─────────────────────────────────────
@override_settings(ADMIN_NOTIFY_EMAIL='contact@halatuju.xyz')
class TestTheWalletDoorShouts(_Base):
    """⚠⚠ THE DOOR THAT CAN REDIRECT MONEY MUST NOT ONLY WHISPER (owner, 2026-09-11).

    `VircleAirtableUpdateView` is a PUBLIC route held shut by one shared secret. Anybody holding
    that secret and a student's NRIC can set `vircle_id` on a student who has none yet — the field
    that decides where that student's bursary is paid. Until this, the only record was a line in
    an application log, which nobody reads. These tests are written from that harm.
    """

    def test_setting_a_wallet_emails_a_person(self):
        app = self._make('u1', nric='080214-08-1234')
        vircle_airtable.apply_update({'NRIC': '080214081234', 'Wallet ID': '8000400181509'})
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('8000400181509', body)
        self.assertIn(str(app.id), body)

    def test_a_REFUSED_overwrite_also_emails_and_says_both_numbers(self):
        """⚠ THE ONE THAT MATTERS MOST. A refused change is the door being PUSHED AT, and it is
        exactly what an attempt on an already-funded student looks like. It writes nothing, so
        without an email it leaves no trace a person will ever see."""
        app = self._make('u1', vircle_id='8000400175123')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400179999'})
        self.assertEqual(out['wallet'], 'mismatch')
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('8000400175123', body)   # what we hold
        self.assertIn('8000400179999', body)   # what they sent
        self.assertIn(str(app.id), body)
        app.refresh_from_db()
        self.assertEqual(app.vircle_id, '8000400175123')   # still refused

    def test_it_NEVER_names_the_student(self):
        """⚠ Wallet + application id are what a person needs to check the row. A name is not, and
        internal alerts get forwarded. Same rule as `send_spending_alert_email`."""
        self._make('u1', nric='080214-08-1234', name='KAVITHA A/P SURESH')
        vircle_airtable.apply_update({'NRIC': '080214081234', 'Wallet ID': '8000400181509'})
        self.assertEqual(len(mail.outbox), 1)
        whole = mail.outbox[0].body + mail.outbox[0].subject
        self.assertNotIn('KAVITHA', whole.upper())
        self.assertNotIn('080214', whole)          # nor the NRIC they were matched on

    def test_a_FAILED_SAVE_sends_NOTHING(self):
        """⚠⚠ FOUND BY A BITE-CHECK THAT NOTHING ELSE CAUGHT. Moving the alert to before the
        save passed all seven tests above.

        The harm is specific: the email is a claim ABOUT STORED STATE — *"wallet now
        8000400181509"* — so sending it before the write means that on any save failure a person
        is handed a fact that is not true, about the field that decides where money goes, with
        nothing to tell them otherwise. Ordering is invisible to a test that only counts emails on
        the happy path; it takes a failing save to see it at all.
        """
        self._make('u1', nric='080214-08-1234')
        with mock.patch.object(ScholarshipApplication, 'save',
                               side_effect=RuntimeError('database went away')):
            with self.assertRaises(RuntimeError):
                vircle_airtable.apply_update({'NRIC': '080214081234',
                                              'Wallet ID': '8000400181509'})
        self.assertEqual(mail.outbox, [])

    def test_the_email_itself_refuses_an_outcome_where_nothing_happened(self):
        """⚠ DRIVEN DIRECTLY, BECAUSE THROUGH `apply_update` THIS GUARD IS UNREACHABLE.

        A bite-check deleting the `outcome not in ('set', 'mismatch')` check changed nothing —
        `_alert` is only ever called from the two branches that DO something, so the guard could
        never fire and was, on the evidence, decorative. It is kept because it defends the email
        boundary against the next caller, and a guard that is kept has to be provable: this drives
        the function itself. (The 2026-09-10 lesson: dead code that looks like a safeguard is
        worse than none, because it invites trust.)
        """
        for outcome in ('kept', 'none', 'invalid', '', 'set '):
            self.assertFalse(
                emails.send_vircle_wallet_alert_email(7, outcome, '8000400181509'), outcome)
        self.assertEqual(mail.outbox, [])
        # …and the two that DO mean something still send.
        self.assertTrue(emails.send_vircle_wallet_alert_email(7, 'set', '8000400181509'))
        self.assertTrue(emails.send_vircle_wallet_alert_email(
            7, 'mismatch', '8000400179999', stored='8000400175123'))
        self.assertEqual(len(mail.outbox), 2)

    def test_nothing_changing_sends_nothing(self):
        """No email for `kept`, `invalid`, `no_match` or an activation-only row. An alert that
        arrives when nothing happened is an alert that gets filtered, and then the one that
        matters is filtered with it."""
        self._make('u1', nric='080214-08-1234', vircle_id='8000400175123')
        vircle_airtable.apply_update({'NRIC': '080214081234',
                                      'Wallet ID': '8000400175123'})          # kept
        vircle_airtable.apply_update({'NRIC': '080214081234',
                                      'Activated On': '08/09/2026'})          # activation only
        vircle_airtable.apply_update({'NRIC': '999999999999',
                                      'Wallet ID': '8000400188888'})          # no_match
        self.assertEqual(mail.outbox, [])

    def test_an_invalid_wallet_is_refused_AND_silent(self):
        self._make('u1', nric='080214-08-1234')
        out = vircle_airtable.apply_update({'NRIC': '080214081234', 'Wallet ID': '123'})
        self.assertEqual(out['wallet'], 'invalid')
        self.assertEqual(mail.outbox, [])

    def test_a_BROKEN_MAIL_SERVER_STILL_LEAVES_VIRCLE_WITH_A_200(self):
        """⚠⚠ THE CONTRACT. This endpoint answers somebody else's automation. An exception
        escaping the alert would turn our mail server's bad afternoon into Vircle's retry storm,
        about our data question — and, worse here, would abort the wallet write that had already
        been saved. The alert fails ALONE."""
        app = self._make('u1', nric='080214-08-1234')
        with mock.patch('apps.scholarship.emails.send_vircle_wallet_alert_email',
                        side_effect=RuntimeError('smtp is down')):
            out = vircle_airtable.apply_update({'NRIC': '080214081234',
                                                'Wallet ID': '8000400181509'})
        self.assertEqual(out['wallet'], 'set')
        app.refresh_from_db()
        self.assertEqual(app.vircle_id, '8000400181509')   # the write survived the alert

    @override_settings(ADMIN_NOTIFY_EMAIL='')
    def test_with_no_recipient_configured_it_is_simply_quiet(self):
        self._make('u1', nric='080214-08-1234')
        out = vircle_airtable.apply_update({'NRIC': '080214081234',
                                            'Wallet ID': '8000400181509'})
        self.assertEqual(out['wallet'], 'set')
        self.assertEqual(mail.outbox, [])


# ── The endpoint: inert without the secret ───────────────────────────────────
@override_settings(VIRCLE_AIRTABLE_SECRET='s3cret')
class TestInboundEndpoint(_Base):
    URL = '/api/v1/internal/vircle/airtable/'

    def setUp(self):
        self.client = APIClient()
        self.app = self._make('u1', nric='080214-08-1234')

    def test_no_secret_is_403(self):
        r = self.client.post(self.URL, {'NRIC': '080214-08-1234'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_wrong_secret_is_403(self):
        r = self.client.post(self.URL, {'NRIC': '080214-08-1234'}, format='json',
                             HTTP_X_VIRCLE_SECRET='wrong')
        self.assertEqual(r.status_code, 403)

    @override_settings(VIRCLE_AIRTABLE_SECRET='')
    def test_unset_secret_refuses_everything(self):
        # Dark by default: with no secret configured, even an empty header must not pass —
        # ''=='' would otherwise open the endpoint to the world.
        r = self.client.post(self.URL, {'NRIC': '080214-08-1234'}, format='json',
                             HTTP_X_VIRCLE_SECRET='')
        self.assertEqual(r.status_code, 403)

    def test_good_secret_applies_the_update_through_the_url(self):
        # Through the URL, not the service — the view/service seam lesson (2026-08-18).
        r = self.client.post(self.URL,
                             {'NRIC': '080214081234', 'Wallet ID': '8000400181509'},
                             format='json', HTTP_X_VIRCLE_SECRET='s3cret')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['wallet'], 'set')
        self.app.refresh_from_db()
        self.assertEqual(self.app.vircle_id, '8000400181509')
