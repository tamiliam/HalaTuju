"""Tests for the Vircle eWallet setup arc (email → Action-Centre confirmation → relay sheet).

The load-bearing behaviours, in the order they can hurt someone:

  * the age gate — Vircle's rule is by birth YEAR, so a student born after 2008 cannot create an
    account at all and must NOT be emailed an impossible instruction;
  * the resolve carve-out — an awarded student is past `querying_locked`, so without an explicit
    exemption they could never confirm (the task would be un-resolvable);
  * the mobile is the ONLY join key to their Vircle account, so a bad one is rejected and a good
    one is stored normalised;
  * the task must stay ACTIONABLE for a funded student (not struck through as a leftover
    review-phase query) and must not be reopened once they've confirmed.

The confirmation is a CLAIM, never a verification — nothing here asserts otherwise.
"""
from unittest import mock

import jwt
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (ResolutionItem, ScholarshipApplication,
                                     ScholarshipCohort)
from apps.scholarship.resolution import VIRCLE_CODE, sync_vircle_item
from apps.scholarship.vircle import (birth_year_from_nric, can_register, confirmation,
                                     raise_setup_task, relay_bucket, relay_rows)
from apps.scholarship.sheets import (STATUS_CONFIRMED, STATUS_NOT_EMAILED,
                                     STATUS_PARENT_ACCOUNT, STATUS_PENDING)

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'
_STUDENT = 'KAVITHA A/P SURESH'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      _TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _make(self, uid, status='awarded', nric='080214-08-1234', phone='0123456789'):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name=_STUDENT, nric=nric, contact_phone=phone,
            preferred_state='Perak', household_income=1500, household_size=4,
            receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            profile_completed_at=timezone.now(), notify_email='k@example.com',
        )


# ── The age gate: Vircle counts by birth YEAR ────────────────────────────────
class TestAgeGate(_Base):
    def test_birth_year_read_from_nric(self):
        self.assertEqual(birth_year_from_nric('080214-08-1234'), 2008)
        self.assertEqual(birth_year_from_nric('091231-14-5678'), 2009)
        self.assertEqual(birth_year_from_nric('991231-14-5678'), 1999)

    def test_unreadable_nric_gives_no_year(self):
        self.assertIsNone(birth_year_from_nric(''))
        self.assertIsNone(birth_year_from_nric('abc'))

    def test_born_2008_can_register(self):
        self.assertTrue(can_register(self._make('u1', nric='081231-08-1234')))

    def test_born_2009_cannot_hold_their_own_account(self):
        # NOT excluded — a parent registers and they're added as a child. This flag only routes
        # them to help@ instead of the in-app confirmation.
        self.assertFalse(can_register(self._make('u2', nric='090101-08-1234')))

    def test_unreadable_nric_is_treated_as_able_to_register(self):
        # Conservative by design: never quietly reroute someone we merely can't read. The email
        # states the birth-year rule anyway, so they can self-select.
        self.assertTrue(can_register(self._make('u3', nric='')))


# ── The Action-Centre task ───────────────────────────────────────────────────
@override_settings(VIRCLE_SETUP_ENABLED=True)
class TestTaskSync(_Base):
    def test_sync_never_creates_the_task(self):
        # THE load-bearing rule: the task is raised by whatever SENT the email, never by a sync.
        # If sync created it, flipping the feature on would drop a "set up your eWallet" card on
        # every awarded student — including the ones who were never emailed about it.
        app = self._make('u1')
        sync_vircle_item(app)
        self.assertFalse(app.resolution_items.filter(code=VIRCLE_CODE).exists())

    def test_raised_by_the_send_then_left_alone_by_sync(self):
        app = self._make('u2')
        raise_setup_task(app)
        sync_vircle_item(app)
        self.assertEqual(app.resolution_items.filter(code=VIRCLE_CODE, status='open').count(), 1)

    def test_raise_is_idempotent(self):
        app = self._make('u3')
        raise_setup_task(app)
        raise_setup_task(app)
        self.assertEqual(app.resolution_items.filter(code=VIRCLE_CODE).count(), 1)

    def test_confirmed_task_is_never_reopened(self):
        # The student said their account is active. That claim doesn't expire — re-opening it
        # would nag someone who has already done the work.
        app = self._make('u5')
        raise_setup_task(app)
        item = app.resolution_items.get(code=VIRCLE_CODE)
        item.status = 'resolved'
        item.save(update_fields=['status'])
        sync_vircle_item(app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_swept_when_the_award_ends(self):
        app = self._make('u6')
        raise_setup_task(app)
        app.status = 'closed'
        app.save(update_fields=['status'])
        sync_vircle_item(app)
        self.assertEqual(app.resolution_items.get(code=VIRCLE_CODE).status, 'resolved')


class TestTaskDark(_Base):
    @override_settings(VIRCLE_SETUP_ENABLED=False)
    def test_open_task_is_swept_when_the_feature_goes_off(self):
        app = self._make('u2')
        raise_setup_task(app)
        sync_vircle_item(app)
        self.assertEqual(app.resolution_items.get(code=VIRCLE_CODE).status, 'resolved')


# ── The student confirms (the carve-out past querying_locked) ────────────────
@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET, VIRCLE_SETUP_ENABLED=True)
class TestConfirm(_Base):
    def setUp(self):
        self.client = APIClient()
        self.app = self._make('u1')
        raise_setup_task(self.app)
        self.item = self.app.resolution_items.get(code=VIRCLE_CODE)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("u1")}')

    # Payments D9: the confirmation now also carries the 13-digit Vircle Wallet ID.
    _VALID_VIRCLE = '8000400175123'

    def _resolve(self, text, vircle_id=_VALID_VIRCLE):
        payload = {'text': text}
        if vircle_id is not None:
            payload['vircle_id'] = vircle_id
        return self.client.post(f'/api/v1/scholarship/resolution-items/{self.item.id}/resolve/',
                                payload, format='json')

    def test_awarded_student_can_confirm_despite_querying_being_locked(self):
        # An awarded student is well past the interview, so querying_locked() is true. Without
        # the carve-out this returns 400 querying_closed and the task is IMPOSSIBLE to resolve.
        r = self._resolve('012-345 6789')
        self.assertEqual(r.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'resolved')

    def test_mobile_is_stored_normalised(self):
        self._resolve('012-345 6789')
        self.item.refresh_from_db()
        self.assertEqual(self.item.resolution_text, '+60123456789')

    def test_vircle_id_is_stored_on_the_application(self):
        self._resolve('012-345 6789', vircle_id='8000400175777')
        self.app.refresh_from_db()
        self.assertEqual(self.app.vircle_id, '8000400175777')

    def test_missing_vircle_id_is_rejected(self):
        r = self._resolve('012-345 6789', vircle_id=None)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'bad_vircle_id')
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'open')       # not resolved

    def test_bad_vircle_id_is_rejected(self):
        for bad in ('8000400175', '9000400175123', '800040017512x'):
            r = self._resolve('012-345 6789', vircle_id=bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertEqual(r.json()['error'], 'bad_vircle_id', bad)

    def test_a_bad_mobile_is_rejected(self):
        # The mobile is the only join key to their Vircle account — a typo silently relays the
        # wrong account, or none at all.
        r = self._resolve('not a phone')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'bad_mobile')
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'open')

    def test_an_empty_mobile_is_rejected(self):
        self.assertEqual(self._resolve('').status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'open')

    def test_the_task_is_actionable_not_set_aside_for_a_funded_student(self):
        # Funded students have their leftover review-phase queries struck through. This task must
        # NOT be swept up in that — it is the one thing we're actually asking them to do.
        r = self.client.get('/api/v1/scholarship/resolution-items/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn(VIRCLE_CODE, [i['code'] for i in body['open']])
        self.assertNotIn(VIRCLE_CODE, [i['code'] for i in body.get('set_aside', [])])

    @override_settings(VIRCLE_SETUP_ENABLED=False)
    def test_task_is_hidden_while_the_feature_is_off(self):
        r = self.client.get('/api/v1/scholarship/resolution-items/')
        self.assertNotIn(VIRCLE_CODE, [i['code'] for i in r.json()['open']])


# ── The relay sheet (what we hand Vircle) ────────────────────────────────────
# Columns: 0 Application · 1 Name · 2 NRIC · 3 Email · 4 Emailed on · 5 Confirmed on · 6 Mobile ·
#          7 eWallet ID (the owner keeps their own columns, e.g. "Activated On", to the RIGHT)
@override_settings(VIRCLE_SETUP_ENABLED=True)
class TestRelayRows(_Base):
    def test_confirmed_row_carries_the_mobile_and_both_dates(self):
        app = self._make('u1')
        raise_setup_task(app)
        item = app.resolution_items.get(code=VIRCLE_CODE)
        item.status, item.resolution_text = 'resolved', '+60123456789'
        item.resolved_at = timezone.now()
        item.save()
        row = relay_rows([app])[0]
        self.assertEqual(row[2], '080214-08-1234')      # NRIC
        self.assertEqual(row[6], '+60123456789')        # the account we relay
        self.assertTrue(row[4])                         # emailed on
        self.assertTrue(row[5])                         # confirmed on
        self.assertEqual(relay_bucket(app), STATUS_CONFIRMED)
        self.assertIsNotNone(confirmation(app))

    def test_emailed_but_not_confirmed_has_an_emailed_date_and_no_confirmed_date(self):
        app = self._make('u2')
        raise_setup_task(app)   # the task exists only because the email actually sent
        row = relay_rows([app])[0]
        self.assertTrue(row[4])         # we asked
        self.assertEqual(row[5], '')    # they haven't answered
        self.assertEqual(row[6], '')
        self.assertEqual(relay_bucket(app), STATUS_PENDING)

    def test_a_student_we_never_emailed_has_a_BLANK_emailed_date(self):
        # The two blanks mean different things. Blank "Emailed on" = we never asked. If that read
        # the same as "asked and ignoring us", a student we never contacted drops off the list.
        app = self._make('u7')
        row = relay_rows([app])[0]
        self.assertEqual(row[4], '')
        self.assertEqual(row[5], '')
        self.assertEqual(relay_bucket(app), STATUS_NOT_EMAILED)

    def test_row_carries_the_principal_ewallet_id(self):
        app = self._make('u8')
        app.vircle_id = '8000400175153'
        app.save(update_fields=['vircle_id'])
        row = relay_rows([app])[0]
        self.assertEqual(row[7], '8000400175153')   # eWallet ID (principal), column H

    def test_ewallet_id_is_blank_when_unset(self):
        app = self._make('u9')
        row = relay_rows([app])[0]
        self.assertEqual(row[7], '')

    def test_header_width_matches_row_width(self):
        # The clear range in write_relay_sheet is computed from len(_HEADER); if the header and the
        # row ever drift, the sheet would clip a column or wipe one of the owner's. Guard it.
        from apps.scholarship.sheets import _HEADER
        app = self._make('u10')
        self.assertEqual(len(relay_rows([app])[0]), len(_HEADER))

    def test_student_born_after_2008_is_routed_to_a_parent_account(self):
        app = self._make('u3', nric='090101-08-1234')
        self.assertEqual(relay_bucket(app), STATUS_PARENT_ACCOUNT)

    def test_a_confirmed_under_18_reads_as_confirmed_not_as_a_problem(self):
        # If a parent registered and the student gave us the mobile, that IS the account we relay.
        app = self._make('u6', nric='090101-08-1234')
        raise_setup_task(app)
        item = app.resolution_items.get(code=VIRCLE_CODE)
        item.status, item.resolution_text = 'resolved', '+60123456789'
        item.resolved_at = timezone.now()
        item.save()
        self.assertEqual(relay_bucket(app), STATUS_CONFIRMED)
        self.assertEqual(relay_rows([app])[0][6], '+60123456789')

    def test_rows_are_ordered_by_awarded_date_first_come_first_served(self):
        # Awarded order, NOT status order. A status sort would re-shuffle the sheet every time a
        # student confirms, dragging the owner's own notes (kept in the columns to the right) out
        # of line with the student they belong to.
        first = self._make('u4')
        second = self._make('u5')
        third = self._make('u8')
        for app, days in ((first, 10), (second, 5), (third, 1)):
            app.awarded_at = timezone.now() - timezone.timedelta(days=days)
            app.save(update_fields=['awarded_at'])
        # The LAST-awarded student confirms; the order must not budge.
        raise_setup_task(third)
        item = third.resolution_items.get(code=VIRCLE_CODE)
        item.status, item.resolved_at = 'resolved', timezone.now()
        item.save()
        ids = [r[0] for r in relay_rows([third, second, first])]
        self.assertEqual(ids, [first.id, second.id, third.id])

    def test_an_application_with_no_awarded_date_sorts_last_rather_than_crashing(self):
        dated = self._make('u9')
        dated.awarded_at = timezone.now() - timezone.timedelta(days=3)
        dated.save(update_fields=['awarded_at'])
        undated = self._make('u10')   # awarded_at is None
        ids = [r[0] for r in relay_rows([undated, dated])]
        self.assertEqual(ids, [dated.id, undated.id])


# ── The merged award email raises the task (and only on a real send) ─────────
class TestAwardEmailRaisesTask(_Base):
    """The award email now CARRIES the Vircle instructions, so the task it points at must exist by
    the time the student reads it — and must NOT exist for a student whose email never went."""

    def _award(self, app):
        from apps.scholarship.models import Sponsor, Sponsorship
        sponsor = Sponsor.objects.create(supabase_user_id=f's{app.id}', name='S',
                                         email=f's{app.id}@e.com', status='approved')
        sp = Sponsorship.objects.create(
            application=app, sponsor=sponsor, amount=3000, status='offered',
        )
        # offered_at is auto_now_add, so it must be back-dated AFTER creation to clear the
        # cool-off window the release cron waits out.
        Sponsorship.objects.filter(pk=sp.pk).update(
            offered_at=timezone.now() - timezone.timedelta(days=2))
        sp.refresh_from_db()
        return sp

    def test_task_raised_when_the_award_email_sends(self):
        from apps.scholarship.sponsorship import release_award_offer_emails
        app = self._make('u1')
        self._award(app)
        self.assertEqual(release_award_offer_emails(), 1)
        self.assertTrue(app.resolution_items.filter(code=VIRCLE_CODE).exists())

    def test_no_task_and_no_stamp_when_the_email_fails(self):
        # A failed send must leave offer_emailed_at unstamped (so the next run retries — otherwise
        # the student NEVER hears they won) and must not leave a mystery task behind.
        from unittest.mock import patch
        from apps.scholarship.sponsorship import release_award_offer_emails
        app = self._make('u2')
        sp = self._award(app)
        with patch('apps.scholarship.sponsorship.send_award_offer_email', return_value=False):
            self.assertEqual(release_award_offer_emails(), 0)
        sp.refresh_from_db()
        self.assertIsNone(sp.offer_emailed_at)
        self.assertFalse(app.resolution_items.filter(code=VIRCLE_CODE).exists())


# ── The email ────────────────────────────────────────────────────────────────
class TestInstallEmail(TestCase):
    def test_guide_pdf_is_attached(self):
        from apps.scholarship.emails import vircle_guide_attachment
        att = vircle_guide_attachment()
        self.assertIsNotNone(att, 'the installation guide asset is missing from the repo')
        filename, content, mimetype = att
        self.assertTrue(filename.endswith('.pdf'))
        self.assertEqual(mimetype, 'application/pdf')
        self.assertTrue(content.startswith(b'%PDF'))

    @mock.patch('apps.scholarship.sheets.fetch_drive_pdf')
    @override_settings(VIRCLE_GUIDE_CACHE_SECONDS=0)
    def test_guide_prefers_the_live_drive_copy(self, fetch):
        # When Drive returns the guide, the email attaches THOSE bytes (the owner's live copy),
        # under the configured filename — not the bundled repo asset.
        from apps.scholarship.emails import vircle_guide_attachment
        fetch.return_value = b'%PDF-1.7 drive-live-copy'
        filename, content, mimetype = vircle_guide_attachment()
        self.assertEqual(content, b'%PDF-1.7 drive-live-copy')
        self.assertEqual(mimetype, 'application/pdf')
        self.assertEqual(filename, settings.VIRCLE_GUIDE_FILENAME)
        fetch.assert_called_once_with(
            settings.VIRCLE_GUIDE_FOLDER, settings.VIRCLE_GUIDE_FILENAME)

    @mock.patch('apps.scholarship.sheets.fetch_drive_pdf', return_value=None)
    @override_settings(VIRCLE_GUIDE_CACHE_SECONDS=0)
    def test_guide_falls_back_to_bundled_asset_when_drive_unavailable(self, fetch):
        # Drive down / disabled → the bundled repo PDF still goes out (an email with the guide
        # beats no email). A real %PDF, and not the drive sentinel.
        from apps.scholarship.emails import vircle_guide_attachment
        att = vircle_guide_attachment()
        self.assertIsNotNone(att)
        _filename, content, _mimetype = att
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertNotIn(b'drive-live-copy', content)

    @mock.patch('apps.scholarship.sheets.fetch_drive_pdf')
    @override_settings(VIRCLE_GUIDE_CACHE_SECONDS=600)
    def test_live_guide_bytes_are_cached_between_sends(self, fetch):
        # A batch send must not re-download 1.5 MB per email: the fetched bytes are cached.
        from django.core.cache import cache

        from apps.scholarship.emails import vircle_guide_attachment
        cache.clear()
        try:
            fetch.return_value = b'%PDF-1.7 cached-once'
            first = vircle_guide_attachment()
            second = vircle_guide_attachment()
            self.assertEqual(first, second)
            fetch.assert_called_once()
        finally:
            cache.clear()

    def test_sends_in_each_language_with_the_guide_attached(self):
        from django.core import mail
        from apps.scholarship.emails import send_vircle_install_email
        for lang in ('en', 'ms', 'ta'):
            mail.outbox = []
            self.assertTrue(send_vircle_install_email('k@example.com', _STUDENT, lang=lang))
            msg = mail.outbox[0]
            self.assertEqual(len(msg.attachments), 1)
            self.assertIn('/scholarship/application', msg.alternatives[0][0])

    def test_every_language_tells_an_under_18_to_use_a_parent_account(self):
        # A student born after 2008 can't hold their own account. The email must say so and point
        # them at help@ — otherwise they hit a wall in the app and go quiet.
        from apps.scholarship import branding as _branding
        from apps.scholarship.emails import SUPPORT_EMAIL, VIRCLE_INSTALL_BODIES
        _P = _branding.platform()
        for lang, body in VIRCLE_INSTALL_BODIES.items():
            # The body now carries {programme}/{signoff} placeholders (per-org branding seam),
            # filled from the platform seam here exactly as send_vircle_install_email does.
            text = body.format(name='X', support=SUPPORT_EMAIL,
                               programme=_P.programme_name(lang), signoff=_P.team_signoff(lang))
            self.assertIn('2008', text)
            self.assertIn(SUPPORT_EMAIL, text, f'{lang}: no help@ route for an under-18')

    def test_body_never_calls_the_confirmation_verified(self):
        # Vircle tells us nothing back. The student's word is a claim, and the copy must not
        # imply we have checked it.
        from apps.scholarship.emails import VIRCLE_INSTALL_BODIES
        self.assertNotIn('verif', VIRCLE_INSTALL_BODIES['en'].lower())


# ── 48h activation request (installed but not activated → email Vircle) ───────
_ACT_HEADER = ['Application', 'Name', 'NRIC', 'Email', 'Emailed on', 'Confirmed on',
               'Mobile registered with Vircle', 'eWallet ID', 'Activated On']


class TestPendingActivation(TestCase):
    def _sheet(self):
        return [
            _ACT_HEADER,
            ['1', 'ALICE', 'a', 'e', '28/06/2026', '29/06/2026', '+60123', '8000400175001', '30/06/2026'],  # activated
            ['2', 'BOB', 'b', 'e', '28/06/2026', '29/06/2026', '+60124', '8000400175002', ''],              # pending
            ['3', 'CARA', 'c', 'e', '', '', '', '', ''],                                                     # not installed
            ['4', 'DEE', 'd', 'e', '28/06/2026', '29/06/2026', '+60125', '8000400175003'],                  # pending (col I trimmed off)
        ]

    @mock.patch('apps.scholarship.sheets.read_sheet_values')
    def test_only_installed_and_not_activated_rows_are_returned(self, read):
        from apps.scholarship import vircle
        read.return_value = self._sheet()
        rows = vircle.pending_activation_rows()
        self.assertEqual([r['name'] for r in rows], ['BOB', 'DEE'])   # ALICE activated, CARA not installed
        bob = rows[0]
        self.assertEqual(bob['ewallet'], '8000400175002')
        self.assertEqual(bob['phone'], '+60124')
        self.assertEqual(bob['installed_on'], '29/06/2026')          # Installed Date <- Confirmed on

    @mock.patch('apps.scholarship.sheets.read_sheet_values', return_value=[])
    def test_unreadable_sheet_returns_empty(self, _read):
        from apps.scholarship import vircle
        self.assertEqual(vircle.pending_activation_rows(), [])

    def test_csv_has_owner_headers_and_excel_safe_ewallet(self):
        from apps.scholarship import vircle
        text = vircle.activation_csv_text([
            {'name': 'BOB', 'nric': 'b', 'installed_on': '29/06/2026', 'phone': '+60124',
             'ewallet': '8000400175002'}])
        self.assertIn('Name,NRIC,Installed Date,Phone number,eWallet ID', text)
        self.assertIn('8000400175002', text)          # the id survives
        # csv quotes the ="…" field and doubles the inner quotes → Excel keeps it as text
        self.assertIn('=""8000400175002""', text)


class TestActivationEmail(TestCase):
    ROWS = [{'name': 'BOB', 'nric': 'b', 'installed_on': '29/06/2026', 'phone': '+60124',
             'ewallet': '8000400175002'}]

    @override_settings(VIRCLE_ACTIVATION_EMAIL='vircle@example.com',
                       VIRCLE_ACTIVATION_BCC='ref@example.com')
    def test_sends_with_csv_and_bcc(self):
        from django.core import mail
        from apps.scholarship.emails import send_vircle_activation_email
        mail.outbox = []
        self.assertTrue(send_vircle_activation_email(self.ROWS))
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['vircle@example.com'])
        self.assertEqual(msg.bcc, ['ref@example.com'])
        self.assertIn('activation request', msg.subject.lower())
        self.assertEqual(len(msg.attachments), 1)                    # the CSV
        self.assertIn('8000400175002', msg.attachments[0][1])

    @override_settings(VIRCLE_ACTIVATION_EMAIL='', VIRCLE_PAYMENTS_EMAIL='gokula@vircle.com')
    def test_recipient_falls_back_to_payments_contact(self):
        from django.core import mail
        from apps.scholarship.emails import send_vircle_activation_email
        mail.outbox = []
        self.assertTrue(send_vircle_activation_email(self.ROWS))
        self.assertEqual(mail.outbox[0].to, ['gokula@vircle.com'])

    @override_settings(VIRCLE_ACTIVATION_EMAIL='vircle@example.com')
    def test_empty_rows_send_nothing(self):
        from django.core import mail
        from apps.scholarship.emails import send_vircle_activation_email
        mail.outbox = []
        self.assertFalse(send_vircle_activation_email([]))
        self.assertEqual(len(mail.outbox), 0)
