"""Tests for post-award bank-details capture (Action Centre).

Covers the deterministic holder verdict, the upload-then-confirm flow (the upload
never auto-resolves the task), the awarded/active Action-Centre trigger + always-on
visibility, and the confirm endpoint's HARD holder==student gate.
"""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, BankAccount, ResolutionItem, ScholarshipApplication,
    ScholarshipCohort,
)
from apps.scholarship.resolution import (
    doc_match_verdict, resolve_doc_items_for_upload, sync_bank_details_item,
    BANK_DETAILS_CODE,
)
from apps.scholarship.vision import doc_student_verdict

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'
_STUDENT = 'KAVITHA A/P SURESH'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      _TEST_JWT_SECRET, algorithm='HS256')


def _bank_fields(bank='Maybank', acct='1234567890', holder=_STUDENT):
    return {k: v for k, v in
            (('bank_name', bank), ('account_number', acct), ('account_holder', holder))}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _make(self, uid, status='awarded'):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name=_STUDENT, nric='080214-08-1234',
            preferred_state='Perak', household_income=1500, household_size=4,
            receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            profile_completed_at=timezone.now(),
        )

    def _add_bank_doc(self, app, *, verdict='ok', fields=None):
        return ApplicantDocument.objects.create(
            application=app, doc_type='bank_statement', storage_path=f'{app.id}/bank/x',
            vision_run_at=timezone.now(),
            vision_fields={'fields': fields if fields is not None else _bank_fields(),
                           'warnings': [], 'student_verdict': verdict, 'error': ''},
        )


# ── The deterministic holder verdict (never an AI hallucination) ──────────────
class TestHolderVerdict(_Base):
    def test_ok_when_all_present_and_holder_is_student(self):
        self.assertEqual(doc_student_verdict('bank_statement', _bank_fields(), names=[_STUDENT]), 'ok')

    def test_name_mismatch_when_holder_is_someone_else(self):
        f = _bank_fields(holder='AHMAD BIN ALI')
        self.assertEqual(doc_student_verdict('bank_statement', f, names=[_STUDENT]), 'name_mismatch')

    def test_incomplete_when_a_field_is_missing(self):
        f = _bank_fields(acct='')
        self.assertEqual(doc_student_verdict('bank_statement', f, names=[_STUDENT]), 'incomplete')

    def test_wrong_doc_when_nothing_bank_shaped(self):
        self.assertEqual(doc_student_verdict('bank_statement', {}, names=[_STUDENT]), 'wrong_doc')

    def test_holder_matched_only_against_student_not_guardian(self):
        # A guardian name in `names` must NOT satisfy the hard "holder is the student" rule.
        f = _bank_fields(holder='RAJA A/P GANESAN')
        v = doc_student_verdict('bank_statement', f, names=[_STUDENT, 'RAJA A/P GANESAN'])
        self.assertEqual(v, 'name_mismatch')


# ── Upload verdict + no auto-resolve (upload-then-confirm) ────────────────────
class TestUploadVerdict(_Base):
    def test_doc_match_verdict_maps_states(self):
        app = self._make('bank-up')
        self.assertEqual(doc_match_verdict(self._add_bank_doc(app, verdict='ok')), 'ok')
        self.assertEqual(doc_match_verdict(self._add_bank_doc(app, verdict='name_mismatch')), 'mismatch')
        self.assertEqual(doc_match_verdict(self._add_bank_doc(app, verdict='incomplete')), 'unreadable')

    def test_unscanned_bank_doc_is_pending(self):
        app = self._make('bank-pend')
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='bank_statement', storage_path='x', vision_fields={})
        self.assertEqual(doc_match_verdict(doc), 'pending')

    def test_clean_upload_does_not_auto_resolve_the_task(self):
        app = self._make('bank-noauto')
        sync_bank_details_item(app)
        doc = self._add_bank_doc(app, verdict='ok')
        # A clean upload returns 'ok' but the task stays OPEN — it resolves on confirm.
        self.assertEqual(resolve_doc_items_for_upload(app, doc), 'ok')
        item = app.resolution_items.get(code=BANK_DETAILS_CODE)
        self.assertEqual(item.status, 'open')


# ── The Action-Centre trigger ────────────────────────────────────────────────
class TestSyncBankItem(_Base):
    def test_creates_for_awarded_without_account(self):
        app = self._make('bank-sync1', status='awarded')
        sync_bank_details_item(app)
        self.assertTrue(app.resolution_items.filter(code=BANK_DETAILS_CODE, status='open').exists())

    def test_creates_for_active_too(self):
        app = self._make('bank-sync2', status='active')
        sync_bank_details_item(app)
        self.assertTrue(app.resolution_items.filter(code=BANK_DETAILS_CODE, status='open').exists())

    def test_not_created_before_award(self):
        app = self._make('bank-sync3', status='profile_complete')
        sync_bank_details_item(app)
        self.assertFalse(app.resolution_items.filter(code=BANK_DETAILS_CODE).exists())

    def test_idempotent(self):
        app = self._make('bank-sync4')
        sync_bank_details_item(app)
        sync_bank_details_item(app)
        self.assertEqual(app.resolution_items.filter(code=BANK_DETAILS_CODE).count(), 1)

    def test_resolves_once_account_confirmed(self):
        app = self._make('bank-sync5')
        sync_bank_details_item(app)
        BankAccount.objects.create(
            application=app, bank_name='Maybank', account_number='1234567890',
            account_holder=_STUDENT, confirmed_at=timezone.now())
        sync_bank_details_item(app)
        self.assertEqual(app.resolution_items.get(code=BANK_DETAILS_CODE).status, 'resolved')


# ── Visibility: always shown for an awarded student, even with Check-2 OFF ────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=_TEST_JWT_SECRET,
                   CHECK2_STUDENT_QUERIES_ENABLED=False)
class TestVisibility(_Base):
    URL = '/api/v1/scholarship/resolution-items/'

    def test_bank_item_shows_with_queries_flag_off(self):
        self._make('bank-vis')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("bank-vis")}')
        codes = [i['code'] for i in client.get(self.URL).json()['open']]
        self.assertIn(BANK_DETAILS_CODE, codes)


# ── The confirm endpoint + the HARD holder gate ──────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestConfirmEndpoint(_Base):
    URL = '/api/v1/scholarship/bank-account/'

    def _client(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    def test_get_null_then_confirmed(self):
        app = self._make('bank-c1')
        sync_bank_details_item(app)
        c = self._client('bank-c1')
        self.assertIsNone(c.get(self.URL).json()['bank_account'])
        r = c.post(self.URL, _bank_fields(), format='json')
        self.assertEqual(r.status_code, 200)
        # The account is saved and the task resolves.
        acct = BankAccount.objects.get(application=app)
        self.assertEqual(acct.account_number, '1234567890')
        self.assertEqual(app.resolution_items.get(code=BANK_DETAILS_CODE).status, 'resolved')
        self.assertEqual(c.get(self.URL).json()['bank_account']['bank_name'], 'Maybank')

    def test_holder_mismatch_is_refused(self):
        app = self._make('bank-c2')
        r = self._client('bank-c2').post(self.URL, _bank_fields(holder='AHMAD BIN ALI'), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bank_holder_mismatch')
        self.assertFalse(BankAccount.objects.filter(application=app).exists())

    def test_not_awarded_is_refused(self):
        self._make('bank-c3', status='profile_complete')
        r = self._client('bank-c3').post(self.URL, _bank_fields(), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'not_awarded')

    def test_short_account_number_rejected(self):
        self._make('bank-c4')
        r = self._client('bank-c4').post(self.URL, _bank_fields(acct='12'), format='json')
        self.assertEqual(r.status_code, 400)

    def test_reconfirm_updates_in_place(self):
        app = self._make('bank-c5')
        c = self._client('bank-c5')
        c.post(self.URL, _bank_fields(), format='json')
        c.post(self.URL, _bank_fields(bank='CIMB', acct='9988776655'), format='json')
        self.assertEqual(BankAccount.objects.filter(application=app).count(), 1)
        self.assertEqual(BankAccount.objects.get(application=app).bank_name, 'CIMB')

    def test_links_source_bank_statement(self):
        app = self._make('bank-c6')
        doc = self._add_bank_doc(app, verdict='ok')
        self._client('bank-c6').post(self.URL, _bank_fields(), format='json')
        self.assertEqual(BankAccount.objects.get(application=app).source_doc_id, doc.id)


# ── Funded students: the auto review-phase queries are suppressed ─────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=_TEST_JWT_SECRET,
                   CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestFundedSetsAsideReviewQueries(_Base):
    """Owner decision 2026-06-29: the moment recommended → awarded, the auto review-phase
    items (system verdict gaps + Check-2 clarify queries) are SET ASIDE in the student's
    Action Centre — peeled out of the actionable queue into a `set_aside` bucket the FE shows
    struck-through (amber): not deleted, not green/done. The bank-details task + anything an
    officer/super-admin RAISES stays actionable. (The officer cockpit — a separate serializer —
    still shows the queries as unanswered.)"""
    URL = '/api/v1/scholarship/resolution-items/'

    def test_funded_sets_aside_review_keeps_officer_and_bank_open(self):
        from apps.scholarship.resolution import add_officer_item
        # An awarded no-docs app → the verdict raises system review gaps (offer/ic/results…).
        app = self._make('fund-aside', status='awarded')
        add_officer_item(app, kind='explanation', prompt='Officer asks', admin_email='r@x')
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("fund-aside")}')
        body = c.get(self.URL).json()
        open_codes = {i['code'] for i in body['open']}
        # Actionable open = the bank task + the officer item ONLY.
        self.assertIn('bank_details_missing', open_codes)
        self.assertIn('officer_1', open_codes)
        # NO review-phase auto item (system/check2) leaks into the actionable queue.
        for i in body['open']:
            self.assertFalse(i['source'] in ('system', 'check2') and i['code'] != 'bank_details_missing',
                             f'review item leaked into open: {i}')
        # The review-phase auto items are SET ASIDE (struck amber) — present, not deleted.
        self.assertTrue(body['set_aside'], 'expected review items in set_aside')
        for i in body['set_aside']:
            self.assertIn(i['source'], ('system', 'check2'))
            self.assertNotEqual(i['code'], 'bank_details_missing')

    def test_pre_award_keeps_review_items_actionable(self):
        # Contrast: an interviewed (pre-award) no-docs student with the flag on sees the
        # review gaps as normal open to-dos — nothing is set aside before funding.
        app = self._make('preaward-aside', status='interviewed')  # noqa: F841 (used via token)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("preaward-aside")}')
        body = c.get(self.URL).json()
        self.assertTrue(any(i['source'] in ('system', 'check2') for i in body['open']))
        self.assertEqual(body['set_aside'], [])
