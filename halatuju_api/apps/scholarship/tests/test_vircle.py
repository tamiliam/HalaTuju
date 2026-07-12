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
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (ResolutionItem, ScholarshipApplication,
                                     ScholarshipCohort)
from apps.scholarship.resolution import VIRCLE_CODE, sync_vircle_item
from apps.scholarship.vircle import (birth_year_from_nric, can_register,
                                     confirmation, raise_setup_task, relay_rows)
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

    def _resolve(self, text):
        return self.client.post(f'/api/v1/scholarship/resolution-items/{self.item.id}/resolve/',
                                {'text': text}, format='json')

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
@override_settings(VIRCLE_SETUP_ENABLED=True)
class TestRelayRows(_Base):
    def test_confirmed_row_carries_the_mobile_the_student_gave(self):
        app = self._make('u1')
        raise_setup_task(app)
        item = app.resolution_items.get(code=VIRCLE_CODE)
        item.status, item.resolution_text = 'resolved', '+60123456789'
        item.resolved_at = timezone.now()
        item.save()
        row = relay_rows([app])[0]
        self.assertEqual(row[3], '+60123456789')
        self.assertEqual(row[5], STATUS_CONFIRMED)
        self.assertIsNotNone(confirmation(app))

    def test_pending_row_when_emailed_but_not_yet_confirmed(self):
        app = self._make('u2')
        raise_setup_task(app)   # the task exists only because the email actually sent
        row = relay_rows([app])[0]
        self.assertEqual(row[3], '')
        self.assertEqual(row[5], STATUS_PENDING)

    def test_a_student_we_never_emailed_is_not_reported_as_emailed(self):
        # The sheet must NOT say "emailed, awaiting confirmation" about someone we never wrote to.
        # That reads as "told, and ignoring us" when the truth is "we never asked" — and it is
        # exactly how a student gets quietly dropped off a chase list.
        app = self._make('u7')
        self.assertEqual(relay_rows([app])[0][5], STATUS_NOT_EMAILED)

    def test_student_born_after_2008_is_routed_to_a_parent_account(self):
        app = self._make('u3', nric='090101-08-1234')
        self.assertEqual(relay_rows([app])[0][5], STATUS_PARENT_ACCOUNT)

    def test_a_confirmed_under_18_reads_as_confirmed_not_as_a_problem(self):
        # If a parent registered and the student gave us the mobile, that IS the account we relay.
        app = self._make('u6', nric='090101-08-1234')
        raise_setup_task(app)
        item = app.resolution_items.get(code=VIRCLE_CODE)
        item.status, item.resolution_text = 'resolved', '+60123456789'
        item.resolved_at = timezone.now()
        item.save()
        row = relay_rows([app])[0]
        self.assertEqual(row[5], STATUS_CONFIRMED)
        self.assertEqual(row[3], '+60123456789')

    def test_confirmed_students_sort_first(self):
        pending = self._make('u4')
        confirmed = self._make('u5')
        raise_setup_task(confirmed)
        item = confirmed.resolution_items.get(code=VIRCLE_CODE)
        item.status, item.resolved_at = 'resolved', timezone.now()
        item.save()
        rows = relay_rows([pending, confirmed])
        self.assertEqual(rows[0][0], confirmed.id)


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
        from apps.scholarship.emails import SUPPORT_EMAIL, VIRCLE_INSTALL_BODIES
        for lang, body in VIRCLE_INSTALL_BODIES.items():
            text = body.format(name='X', support=SUPPORT_EMAIL)
            self.assertIn('2008', text)
            self.assertIn(SUPPORT_EMAIL, text, f'{lang}: no help@ route for an under-18')

    def test_body_never_calls_the_confirmation_verified(self):
        # Vircle tells us nothing back. The student's word is a claim, and the copy must not
        # imply we have checked it.
        from apps.scholarship.emails import VIRCLE_INSTALL_BODIES
        self.assertNotIn('verif', VIRCLE_INSTALL_BODIES['en'].lower())
