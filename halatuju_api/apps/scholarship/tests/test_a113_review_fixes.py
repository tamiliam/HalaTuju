"""A1.13 adversarial review (BLOCK on the award withdrawal) — one regression per finding.

  F1  the withdrawal voids the bursary agreement; countersign / witness refuse a withdrawn or
      superseded agreement (service + doors); a re-signing never inherits an old Foundation /
      witness stamp; so the payments check D4-7 cannot pass on the old countersignature.
  F2  an accept is locked and re-read: it never writes 'active' over a withdrawal.
  F3  the hold-release job locks and re-reads each case before either write.
  F4  the award-email job re-reads each sponsorship under its lock: a cancel mid-run stops the email.
  F5  a sponsor's cancel locks the application BEFORE the sponsorship (the withdrawal's order).
  F6  withdrawing an ACCEPTED sponsorship, one in its hold period, and a payment run completed
      after a withdrawal (``not_payable_in_run``).

SQLite ignores ``select_for_update``, so (as `test_status_lock.py` explains) each race is staged
as a stale copy that must be refused on the re-read, plus a call-order spy where the ORDER is
the point. All on dummy data; the PDF / storage seams are mocked.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import (
    agreement_guard, bursary, payments, source_console, source_witness, status_lock,
)
from apps.scholarship.tests.withdrawal_helpers import withdraw_now
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    BursaryAgreement, Donation, ScholarshipApplication, ScholarshipCohort, Sponsor, Sponsorship,
    StudentActivity,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, unique_suffix,
)
from apps.scholarship.tests.test_bursary_agreement import (
    GUARANTOR_NAME, GUARANTOR_NRIC, _add_parent_ic, _cumig, _fund, _fundable_app, _mock_seams,
    _twin, _verify_guarantor_phone,
)
from apps.scholarship.tests import test_source_witness as _source_witness_tests
from apps.scholarship.tests import test_status_lock as _status_lock_tests   # module, not the class:
#                              a class imported by name would be collected (and run) twice here

REASON = 'Zxq internal reason for the review tests.'
API = '/api/v1/admin/scholarship/applications/'


def _sponsor(programme, amount=Decimal('3000')):
    s = Sponsor.objects.create(
        supabase_user_id=unique_suffix('a113r-'), name='Test Sponsor',
        email=f'{unique_suffix("a113r-")}@sponsor.example', phone='0123', source='friend',
        consent_at=timezone.now(), status='approved')
    Donation.objects.create(sponsor=s, amount=amount, programme=programme)
    return s


def _accept(app):
    _verify_guarantor_phone(app)
    return svc.respond_to_award(
        app, action='accept', student_signed_name='Zxq Student',
        guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
        guarantor_relationship='mother')


def _order_spy():
    """Record lock_application_for calls and every select_for_update, in order."""
    order = []
    real_lock, real_sfu = status_lock.lock_application_for, QuerySet.select_for_update

    def lock(app, allowed):
        order.append('lock_application')
        return real_lock(app, allowed)

    def sfu(qs, *a, **k):
        order.append(f'sfu:{qs.model.__name__}')
        return real_sfu(qs, *a, **k)
    return order, (patch.object(status_lock, 'lock_application_for', lock),
                   patch.object(QuerySet, 'select_for_update', sfu))


# ── F1 + F6: the agreement dies with the award ─────────────────────────────────────────────────

@override_settings(BURSARY_AGREEMENT_ENABLED=True)
class TestTheAgreementIsVoided(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        for p in _mock_seams():
            p.start()
            self.addCleanup(p.stop)
        self.super = make_admin(super_admin=True)
        self.org = _cumig()
        self.app = _fundable_app(self.cohort, suffix='a113', org=self.org, source=_twin(self.org))
        _add_parent_ic(self.app)
        self.sp_a = _fund(self.app)
        _accept(self.app)                       # student + guarantor sign; sponsorship 'active'
        self.ag = self.app.bursary_agreement

    def _withdraw(self):
        with self.captureOnCommitCallbacks(execute=True):
            withdraw_now(self.app)
        self.ag.refresh_from_db()

    def test_an_accepted_sponsorship_is_withdrawn_and_its_agreement_voided(self):   # F6 + F1
        self.sp_a.refresh_from_db()
        self.assertEqual((self.sp_a.status, self.ag.binds, self.ag.sponsorship_id),
                         ('active', True, self.sp_a.pk))
        self._withdraw()
        self.sp_a.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual((self.sp_a.status, self.app.status), ('cancelled', 'recommended'))
        self.assertFalse(self.ag.binds)
        self.assertIsNone(self.ag.sponsorship_id)
        for f in ('student_signed_at', 'guarantor_signed_at', 'foundation_signed_at',
                  'witness_signed_at'):
            self.assertIsNone(getattr(self.ag, f), f)
        row = StudentActivity.objects.get(application=self.app, event='award_withdrawn')
        was = row.meta['agreement_voided']                  # the audit keeps the old stamps
        self.assertIsNotNone(was['student_signed_at'])
        self.assertEqual(was['sponsorship_id'], self.sp_a.pk)

    def test_countersign_and_witness_are_refused_after_the_withdrawal(self):
        self._withdraw()
        with self.assertRaises(agreement_guard.AgreementNotCurrent) as cm:
            bursary.countersign_foundation(self.ag, by_name='The Super')
        self.assertEqual(cm.exception.reason, 'case_status')
        with self.assertRaises(agreement_guard.AgreementNotCurrent):
            bursary.record_witness(self.ag, org=_twin(self.org), by_name='Officer')
        with self.assertRaises(agreement_guard.AgreementNotCurrent):
            source_witness.record_once(self.ag, org=_twin(self.org), by_name='Officer')
        self.ag.refresh_from_db()
        self.assertIsNone(self.ag.foundation_signed_at)
        self.assertIsNone(self.ag.witness_signed_at)

    def test_after_a_re_award_the_old_agreement_cannot_be_countersigned_or_paid_on(self):
        self._withdraw()
        sponsor_b = _sponsor(self.app.programme)
        sp_b = svc.fund_student(sponsor_b, self.app)        # re-awarded: 'awarded' again
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')
        with self.assertRaises(agreement_guard.AgreementNotCurrent) as cm:
            bursary.countersign_foundation(self.ag, by_name='The Super')
        self.assertEqual(cm.exception.reason, 'agreement_void')
        self.assertIn('agreement_unsigned',                  # D4-7 is not met on A's contract
                      payments.eligibility(self.app, timezone.localdate())['reasons'])
        # B's acceptance re-signs the SAME row; even a stale counterparty stamp is reset (F1c).
        BursaryAgreement.objects.filter(pk=self.ag.pk).update(
            foundation_signed_at=timezone.now(), foundation_signed_by='Old',
            witness_signed_at=timezone.now(), witness_name='Old')
        _accept(self.app)
        self.ag.refresh_from_db()
        self.assertEqual(self.ag.sponsorship_id, sp_b.pk)
        self.assertTrue(self.ag.binds)
        self.assertEqual((self.ag.foundation_signed_at, self.ag.foundation_signed_by),
                         (None, ''))
        self.assertEqual((self.ag.witness_signed_at, self.ag.witness_name), (None, ''))
        bursary.countersign_foundation(self.ag, by_name='The Super')     # now it may
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'active')

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_the_super_doors_answer_409(self):
        self._withdraw()
        client = authed_client(self.super)
        for door in ('countersign', 'witness'):
            with self.subTest(door=door):
                r = client.post(f'{API}{self.app.id}/bursary-agreement/{door}/')
                self.assertEqual(r.status_code, 409, r.content)
                self.assertEqual(r.json()['code'], 'agreement_not_current')
        self.ag.refresh_from_db()
        self.assertIsNone(self.ag.foundation_signed_at)
        self.assertIsNone(self.ag.witness_signed_at)

    def test_a_real_held_decline_keeps_the_witness_open_and_a_told_one_closes_it(self):  # re-review 2
        from apps.scholarship.services.decline import admin_reject
        bursary.countersign_foundation(self.ag, by_name='The Super')     # executed: 'active'
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'active')
        admin_reject(self.app, self.super, 'contractual', comments=REASON)   # held: email embargoed
        self.app.refresh_from_db()
        self.sp_a.refresh_from_db()
        self.assertEqual((self.app.status, self.sp_a.status), ('rejected', 'lapsed'))
        self.assertTrue(self.app.pending_rejection_category)
        self.assertTrue(source_console.contract_live(self.app))          # the console offers it
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(pending_rejection_category='')
        with self.assertRaises(agreement_guard.AgreementNotCurrent) as cm:     # told: closed
            bursary.record_witness(self.ag, org=_twin(self.org), by_name='Officer')
        self.assertEqual(cm.exception.reason, 'case_status')
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            pending_rejection_category='contractual')
        bursary.record_witness(self.ag, org=_twin(self.org), by_name='Officer')   # held: it may
        self.ag.refresh_from_db()
        self.assertIsNotNone(self.ag.witness_signed_at)

    def test_the_audit_keeps_what_the_void_clears_and_the_old_pdf_is_hidden(self):  # re-review 3+4
        from apps.scholarship.serializers import BursaryAgreementSerializer
        bursary.record_witness(self.ag, org=_twin(self.org), by_name='Officer')
        BursaryAgreement.objects.filter(pk=self.ag.pk).update(foundation_signed_by='Old Super')
        self.ag.refresh_from_db()
        old = {f: getattr(self.ag, f) for f in ('witness_org_id', 'witness_name', 'witness_signed_by',
                                                 'agreement_sha256', 'pdf_storage_path')}
        self.assertTrue(old['pdf_storage_path'] and old['agreement_sha256'] and old['witness_org_id'])
        signed = patch('apps.scholarship.storage.create_signed_download_url',
                       return_value='https://storage.example/signed')
        anyorg = patch('apps.scholarship.storage.resolve_org_for_path', return_value=None)
        with signed, anyorg:
            self.assertEqual(BursaryAgreementSerializer(self.ag).data['pdf_url'],
                             'https://storage.example/signed')
            self._withdraw()
            self.assertIsNone(BursaryAgreementSerializer(self.ag).data['pdf_url'])
        self.assertEqual(self.ag.pdf_storage_path, old['pdf_storage_path'])  # kept: the sweep keeps it
        was = StudentActivity.objects.get(application=self.app, event='award_withdrawn').meta[
            'agreement_voided']
        for f, v in old.items():
            self.assertEqual(was[f], v, f)
        self.assertEqual(was['foundation_signed_by'], 'Old Super')
        for f in ('witness_ip', 'witness_admin_id'):
            self.assertIn(f, was)

    def test_an_unwithdrawn_agreement_still_signs_as_before(self):
        bursary.record_witness(self.ag, org=_twin(self.org), by_name='Officer')
        bursary.countersign_foundation(self.ag, by_name='The Super')
        self.ag.refresh_from_db()
        self.assertTrue(self.ag.is_executed)
        # The witness may still come after the Foundation on a funded case (designed path).
        BursaryAgreement.objects.filter(pk=self.ag.pk).update(witness_signed_at=None)
        bursary.record_witness(self.ag, org=_twin(self.org), by_name='Officer')


class TestASupersededAgreementIsRefused(TestCase):
    """A row that still points at a cancelled sponsorship (written before this fix) is refused
    even though it binds and the case is awarded again."""

    def test_countersign_names_the_superseded_sponsorship(self):
        app = make_application('awarded')
        old_sp = Sponsorship.objects.create(sponsor=_sponsor(app.programme), application=app,
                                            amount=Decimal('3000'), status='cancelled')
        Sponsorship.objects.create(sponsor=_sponsor(app.programme), application=app,
                                   amount=Decimal('3000'), status='offered')
        ag = BursaryAgreement.objects.create(
            application=app, version='2026-v1', sponsorship=old_sp,
            student_signed_at=timezone.now(), guarantor_signed_at=timezone.now())
        with self.assertRaises(agreement_guard.AgreementNotCurrent) as cm:
            bursary.countersign_foundation(ag, by_name='The Super')
        self.assertEqual(cm.exception.reason, 'agreement_superseded')
        ag.refresh_from_db()
        self.assertIsNone(ag.foundation_signed_at)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheSourceConsoleDoorAnswers409(_source_witness_tests._Fixture):
    """Re-review 5: the source's own witness door, through the view. The console's checks pass (an
    awarded case, a signed agreement, no witness yet); the guard refuses a superseded contract."""

    def test_a_superseded_agreement_is_refused_and_nothing_is_written(self):
        app = self.ready
        old_sp = Sponsorship.objects.create(sponsor=_sponsor(app.programme), application=app,
                                            amount=Decimal('3000'), status='cancelled')
        BursaryAgreement.objects.filter(application=app).update(sponsorship=old_sp)
        resp = self.client.post(_source_witness_tests.witness_url(app), _source_witness_tests.GOOD,
                                format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'agreement_not_current'))
        self.assertIsNone(self.agreement(app).witness_signed_at)


# ── F2: an accept is locked and re-read ────────────────────────────────────────────────────────

@override_settings(BURSARY_AGREEMENT_ENABLED=False, AWARD_COOLOFF_DAYS=2)
class TestAcceptIsLocked(TestCase):
    def setUp(self):
        self.app = make_application('recommended', award_amount=Decimal('3000'))
        self.sponsor = _sponsor(self.app.programme)
        self.sp = svc.fund_student(self.sponsor, self.app)
        self.super = make_admin(super_admin=True)

    def test_an_accept_from_a_copy_read_before_a_withdrawal_is_refused(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)     # the student's page
        with self.captureOnCommitCallbacks(execute=True):
            withdraw_now(self.app)
        with self.assertRaises(svc.SponsorshipError) as cm:
            svc.respond_to_award(stale, action='accept')
        self.assertEqual(cm.exception.code, 'no_offer')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'cancelled')                   # never 'active'
        self.assertFalse(Sponsorship.objects.filter(application=self.app, status='active').exists())

    def test_a_case_no_longer_awarded_is_refused_even_with_an_offer_row(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(status='recommended')
        with self.assertRaises(svc.SponsorshipError) as cm:
            svc.respond_to_award(stale, action='accept')
        self.assertEqual(cm.exception.code, 'no_offer')
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'offered')

    def test_the_case_is_locked_before_the_offer(self):
        order, (p1, p2) = _order_spy()
        with p1, p2:
            svc.respond_to_award(self.app, action='accept')
        self.assertEqual(order[:3], ['lock_application', 'sfu:ScholarshipApplication',
                                     'sfu:Sponsorship'])


# ── F3 + F6: the hold-release job ──────────────────────────────────────────────────────────────

@override_settings(BURSARY_AGREEMENT_ENABLED=False, AWARD_COOLOFF_DAYS=2)
class TestReleasePendingAwardsIsLocked(TestCase):
    def setUp(self):
        self.super = make_admin(super_admin=True)

    def _held(self):
        """An accepted award in its hold period, due now."""
        app = make_application('recommended', award_amount=Decimal('3000'))
        sp = svc.fund_student(_sponsor(app.programme), app)
        svc.respond_to_award(app, action='accept')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            award_due_at=timezone.now() - timedelta(minutes=1))
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, sp.status), ('awarded', 'active'))
        return app, sp

    def test_a_withdrawal_in_the_hold_period_is_never_released(self):             # F6
        app, sp = self._held()
        with self.captureOnCommitCallbacks(execute=True):
            withdraw_now(app)
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, sp.status, app.award_due_at), ('recommended', 'cancelled', None))
        self.assertEqual(svc.release_pending_awards(), 0)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    def test_a_case_moved_on_after_the_list_was_read_is_skipped(self):
        first, second = self._held(), self._held()
        apps = {first[0].pk: second[0].pk, second[0].pk: first[0].pk}
        real = svc._finalise_award

        def finalise_then_close_the_other(app, locale='en'):
            # Lands between the job's list read and the next case's write.
            ScholarshipApplication.objects.filter(pk=apps[app.pk]).update(status='closed')
            return real(app, locale)
        with patch.object(svc, '_finalise_award', finalise_then_close_the_other):
            self.assertEqual(svc.release_pending_awards(), 1)
        statuses = sorted(ScholarshipApplication.objects.filter(pk__in=apps)
                          .values_list('status', flat=True))
        self.assertEqual(statuses, ['active', 'closed'])                 # never active over closed

    def test_a_closed_case_with_a_marker_is_not_flipped(self):
        app, _sp = self._held()
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='closed')
        self.assertEqual(svc.release_pending_awards(), 0)
        app.refresh_from_db()
        self.assertEqual(app.status, 'closed')

    def test_a_held_case_still_releases(self):
        app, _sp = self._held()
        self.assertEqual(svc.release_pending_awards(), 1)
        app.refresh_from_db()
        self.assertEqual((app.status, app.award_due_at), ('active', None))


# ── F4: the award-email job re-reads each row ──────────────────────────────────────────────────

@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestAwardEmailsReRead(TestCase):
    def test_a_cancel_after_the_list_was_read_stops_its_email(self):
        sps = []
        for n in range(2):
            app = make_application('recommended', award_amount=Decimal('3000'),
                                   notify_email=f'stu{n}@a113.example')
            sps.append(svc.fund_student(_sponsor(app.programme), app))
        sent_to = []

        def send(**kw):
            sent_to.append(kw['to_email'])
            # The sponsor cancels the OTHER award while this email is going out.
            Sponsorship.objects.exclude(application__notify_email=kw['to_email']).filter(
                status='offered', offer_emailed_at__isnull=True).update(status='cancelled')
            return True
        later = timezone.now() + timedelta(days=30)
        with patch.object(svc, 'send_award_offer_email', side_effect=send), \
                patch.object(svc, 'raise_setup_task'), \
                patch('apps.scholarship.parent_call.held_for_parent_call', return_value=False):
            self.assertEqual(svc.release_award_offer_emails(now=later), 1)
        self.assertEqual(len(sent_to), 1)
        stamped = [sp for sp in Sponsorship.objects.filter(pk__in=[s.pk for s in sps])
                   if sp.offer_emailed_at is not None]
        self.assertEqual(len(stamped), 1)
        self.assertEqual(stamped[0].status, 'offered')

    def test_the_case_is_locked_before_the_sponsorship(self):                     # re-review 1
        app = make_application('recommended', award_amount=Decimal('3000'),
                               notify_email='stu@a113.example')
        sp = svc.fund_student(_sponsor(app.programme), app)
        order, (p1, p2) = _order_spy()
        with p1, p2, patch.object(svc, 'send_award_offer_email', return_value=True), \
                patch.object(svc, 'raise_setup_task'), \
                patch('apps.scholarship.parent_call.held_for_parent_call', return_value=False):
            self.assertEqual(svc.release_award_offer_emails(now=timezone.now() + timedelta(days=30)), 1)
        self.assertEqual(order[:3], ['lock_application', 'sfu:ScholarshipApplication',
                                     'sfu:Sponsorship'])
        sp.refresh_from_db()
        self.assertIsNotNone(sp.offer_emailed_at)


# ── F5: cancel_offer's lock order ──────────────────────────────────────────────────────────────

class TestCancelOfferLockOrder(TestCase):
    def test_the_application_is_locked_before_the_sponsorship(self):
        app = make_application('recommended', award_amount=Decimal('3000'))
        sponsor = _sponsor(app.programme)
        sp = svc.fund_student(sponsor, app)
        order, (p1, p2) = _order_spy()
        with p1, p2:
            svc.cancel_offer(sponsor, sp.pk)
        self.assertEqual(order[:3], ['lock_application', 'sfu:ScholarshipApplication',
                                     'sfu:Sponsorship'])
        sp.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual((sp.status, app.status), ('cancelled', 'recommended'))

    def test_an_unknown_offer_is_still_not_found(self):
        app = make_application('recommended', award_amount=Decimal('3000'))
        sponsor = _sponsor(app.programme)
        with self.assertRaises(svc.SponsorshipError) as cm:
            svc.cancel_offer(sponsor, 987654321)
        self.assertEqual(cm.exception.code, 'not_found')


# ── F6: a payment run completed after a withdrawal ─────────────────────────────────────────────

class TestARunDoesNotPayAWithdrawnStudent(_status_lock_tests.TestARunDoesNotPayAClosedStudent):
    """Every case of the TD-367 suite, with the award WITHDRAWN (A1.13) in place of the close: the
    run's completion re-reads the case under its lock and refuses it (``not_payable_in_run``)."""

    def _close(self):
        with self.captureOnCommitCallbacks(execute=True):
            withdraw_now(self.closing)
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.closing.pk).status,
                         'recommended')
        mail.outbox.clear()
