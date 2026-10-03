"""TD-251 (2026-10-03): Vircle's "Activate DNQR" payload IS an activation.

Their Airtable has two buttons. "Get Details" posts the whole row with `Status`; "Activate DNQR" —
the one pressed AT activation — posts Name, NRIC, Wallet id and the activated phone: no Status, no
date. Until this fix the reader saved the wallet and dropped the activation (#144, 14 Sep, repaired
by hand). A present, non-blank activated phone now stamps `vircle_activated_at` with the row's
arrival time. `Pending Vircle Activation` still activates nothing (pinned in
test_vircle_airtable.py and again here, beside the new signal).
"""
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.scholarship import vircle_airtable
from apps.scholarship.tests.factories import make_application, make_student

NRIC = '080214-08-1234'
WALLET = '8000400184348'


class ActivateDnqrPayloadTest(TestCase):
    def setUp(self):
        self.app = make_application('awarded', student=make_student(nric=NRIC.replace('-', '')))
        patcher = mock.patch('apps.scholarship.vircle.sync_relay_sheet')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _short_payload(self, **extra):
        # The shape #144's row arrived in on 2026-09-14 (key spellings per the owner's reading
        # of their table: "Activated phone", "Wallet id" is read by the existing wallet aliases).
        return {'Name': 'LINDA', 'NRIC': NRIC, 'Activated phone': '0123456789',
                'Wallet ID': WALLET, **extra}

    def test_activate_dnqr_stamps_activation_at_arrival(self):
        before = timezone.now()
        out = vircle_airtable.apply_update(self._short_payload())
        self.app.refresh_from_db()
        self.assertEqual(out['wallet'], 'set')
        self.assertEqual(out['activated'], 'set')
        self.assertIsNotNone(self.app.vircle_activated_at)
        # The phone number is never read as a date: the stamp is the arrival.
        self.assertGreaterEqual(self.app.vircle_activated_at, before)
        self.assertLessEqual(self.app.vircle_activated_at, timezone.now())

    def test_every_alias_spelling_is_a_signal(self):
        for key in vircle_airtable._ACTIVATED_PHONE_KEYS:
            with self.subTest(key=key):
                self.app.vircle_activated_at = None
                self.app.save(update_fields=['vircle_activated_at'])
                out = vircle_airtable.apply_update({'NRIC': NRIC, key: '0123456789'})
                self.assertEqual(out['activated'], 'set')

    def test_a_blank_activated_phone_is_not_a_signal(self):
        for blank in ('', None):
            with self.subTest(blank=blank):
                out = vircle_airtable.apply_update(self._short_payload(**{'Activated phone': blank}))
                self.assertEqual(out['activated'], 'none')
        self.app.refresh_from_db()
        self.assertIsNone(self.app.vircle_activated_at)

    def test_an_existing_activation_date_is_never_overwritten(self):
        when = timezone.now() - timezone.timedelta(days=20)
        self.app.vircle_activated_at = when
        self.app.save(update_fields=['vircle_activated_at'])
        out = vircle_airtable.apply_update(self._short_payload())
        self.app.refresh_from_db()
        self.assertEqual(out['activated'], 'kept')
        self.assertEqual(self.app.vircle_activated_at, when)

    def test_pending_status_beside_no_phone_still_activates_nothing(self):
        out = vircle_airtable.apply_update({'NRIC': NRIC, 'Wallet ID': WALLET,
                                            'Status': 'Pending Vircle Activation'})
        self.assertEqual(out['activated'], 'none')

    def test_a_pending_status_silences_a_present_phone(self):
        # Review F2: a "Get Details" row carries Status; Pending beside a pre-filled phone is NOT
        # an activation. Only a row with NO Status lets the phone decide.
        out = vircle_airtable.apply_update(
            self._short_payload(Status='Pending Vircle Activation'))
        self.app.refresh_from_db()
        self.assertEqual(out['wallet'], 'set')
        self.assertEqual(out['activated'], 'none')
        self.assertIsNone(self.app.vircle_activated_at)

    def test_done_beside_a_phone_still_activates(self):
        out = vircle_airtable.apply_update(self._short_payload(Status='Done'))
        self.assertEqual(out['activated'], 'set')

    def test_a_wallet_without_activation_warns_with_field_names_only(self):
        with self.assertLogs('apps.scholarship.vircle_airtable', 'WARNING') as logs:
            vircle_airtable.apply_update({'NRIC': NRIC, 'Wallet ID': WALLET,
                                          'Status': 'Pending Vircle Activation'})
        line = '\n'.join(logs.output)
        self.assertIn('NO activation', line)
        self.assertIn('keys=NRIC,Status,Wallet ID', line)
        for value in ('080214', WALLET, 'Pending'):
            self.assertNotIn(value, line)   # names only — never a student's NRIC or wallet
