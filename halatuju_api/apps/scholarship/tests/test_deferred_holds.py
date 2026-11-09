"""Audit sprint A2.8a — Check 2's holds on documents our outage left unread end, and never block a
resolve a read letter already earned. Synthetic data only, no real applicant.

* TD-397: a deferred copy's hold stays only while the hourly sweep will still read it; an unchecked
  informal one past the sweep goes to the officer, never back to the family (lead ruling B).
* TD-398: one deferred letter does not delay resolving a member's request another live letter answered.
"""
import time
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.scholarship.income_declaration import APPROVAL_TRIED
from apps.scholarship.models import ApplicantDocument, ResolutionItem
from apps.scholarship.read_errors import SERVICE_RETRY_UNTIL, service_retry_open
from apps.scholarship.tests.factories import create_document, make_application, make_student

_SERVICE_READ = {'fields': {}, 'warnings': [], 'student_verdict': 'review_manually', 'capture': 'ai',
                 'error': 'All AI models failed: gemini-2.5-flash: 402 RESOURCE_EXHAUSTED', 'service_error': True}
_PAST = int(time.time()) - 60
_FUTURE = int(time.time()) + 3600
_LONG_AGO = int((timezone.now() - timedelta(hours=73)).timestamp())


def _doc(app, doc_type, vf, member=''):
    return create_document(application=app, doc_type=doc_type, household_member=member, vision_fields=vf,
                           storage_path=f'test/{doc_type}/{ApplicantDocument.objects.count()}',
                           content_type='image/jpeg', vision_run_at=timezone.now())


def _slip(seen, status='genuine', **fields):
    return {'fields': fields, 'student_verdict': 'ok', 'error': '',
            'authenticity': {'status': status, 'doc_seen': seen, 'probability': 0.5}}


class _Sync(TestCase):

    def _status(self, app, code):
        from apps.scholarship.check2_queries import sync_check2_queries
        sync_check2_queries(app)
        item = app.resolution_items.filter(source='check2', code=code).first()
        return item.status if item else None

    def _two_earners(self):
        app = make_application(
            'profile_complete', income_route='salary', income_working_members=['father', 'mother'],
            income_earner='', father_name='Ayah Contoh', father_occupation='fisherman', mother_name='Ibu Contoh',
            mother_occupation='private', other_family_members=[],
            student=make_student(name='PELAJAR CONTOH', nric='080115-05-0132'))
        create_document(application=app, doc_type='parent_ic', household_member='father',
                        vision_name='AYAH CONTOH', vision_nric='700707-05-5671',
                        storage_path=f'test/pic/{app.id}', vision_run_at=timezone.now())
        _doc(app, 'salary_slip', _slip('private', gross_income='1,450.00'), member='father')
        return app


class TheWindowRule(TestCase):

    def test_open_while_the_sweep_has_not_tried_or_its_window_runs(self):
        self.assertTrue(service_retry_open(dict(_SERVICE_READ)))
        self.assertTrue(service_retry_open({**_SERVICE_READ, SERVICE_RETRY_UNTIL: _FUTURE}))
        self.assertFalse(service_retry_open({**_SERVICE_READ, SERVICE_RETRY_UNTIL: _PAST}))
        self.assertFalse(service_retry_open({**_SERVICE_READ, SERVICE_RETRY_UNTIL: 'junk'}))

    def test_the_sweep_reads_the_same_key(self):
        from apps.scholarship.services.read_retry import RETRY_UNTIL
        self.assertEqual(RETRY_UNTIL, SERVICE_RETRY_UNTIL)


class AHoldEndsWhenTheSweepGivesUp(_Sync):
    """TD-397: before A2.8a a deferred copy held its request for ever once the sweep's 72 hours ran out."""

    def test_a_bill_request_held_inside_the_window_is_asked_after_it(self):
        app = make_application('profile_complete')
        bill = _doc(app, 'water_bill', {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _FUTURE})
        self.assertIsNone(self._status(app, 'water_bill_recheck'))           # held: the sweep still reads it
        bill.vision_fields = {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _PAST}
        bill.save(update_fields=['vision_fields'])
        self.assertEqual(self._status(app, 'water_bill_recheck'), 'open')    # given up: the ordinary ask

    def test_an_open_certificate_request_resolves_no_more_after_the_window(self):
        """The hold never lets an unread copy pass: after the window the gap reader decides (it is unread,
        so the request stays open)."""
        app = make_application('profile_complete')
        ResolutionItem.objects.create(application=app, source='check2', code='school_leaving_cert_missing',
                                      fact='academic', kind='doc', doc_type='school_leaving_cert', status='open')
        _doc(app, 'school_leaving_cert', {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _PAST})
        from apps.scholarship.check2_deferred import held_doc_requests
        from apps.scholarship.check2_queries import DOC_SPECS
        existing = {r.code: r for r in app.resolution_items.filter(source='check2')}
        self.assertEqual(held_doc_requests(app, DOC_SPECS, existing, set()), set())

    def test_a_deferred_support_letter_is_judged_by_its_window_not_by_its_missing_approval(self):
        """A deferred letter has no fields, so it is also "approval unchecked"; that must not keep holding
        once the sweep's window has passed."""
        app = self._two_earners()
        letter = _doc(app, 'income_support_doc', {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _FUTURE}, member='mother')
        self.assertIsNone(self._status(app, 'mother_income_proof_missing'))
        letter.vision_fields = {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _PAST}
        letter.save(update_fields=['vision_fields'])
        self.assertEqual(self._status(app, 'mother_income_proof_missing'), 'open')

    def test_an_unchecked_slip_past_its_approval_re_read_goes_to_the_officer_not_the_family(self):
        """Lead ruling B (A2.8a review): when the one approval re-read is past its 72 hours the family is
        NOT asked again for what she sent; the officer's drawer reason says to check it by eye."""
        from apps.scholarship.income_declaration import member_approval_state, missing_reason
        app = self._two_earners()
        slip = _doc(app, 'salary_slip', _slip('informal', status='suspect', gross_income='RM400'), member='mother')
        self.assertIsNone(self._status(app, 'mother_income_proof_missing'))  # never re-read yet: held
        self.assertEqual(missing_reason(slip), 'approval_unchecked')
        slip.vision_fields = {**slip.vision_fields, APPROVAL_TRIED: int(time.time())}
        slip.save(update_fields=['vision_fields'])
        self.assertIsNone(self._status(app, 'mother_income_proof_missing'))  # just tried: still held
        self.assertEqual(missing_reason(slip), 'approval_unchecked')
        slip.vision_fields = {**slip.vision_fields, APPROVAL_TRIED: _LONG_AGO}
        slip.save(update_fields=['vision_fields'])
        # The family side: no ordinary income ask; her gate still says "we are still checking" (the
        # blocker's 'unchecked' state), never "show their income".
        self.assertIsNone(self._status(app, 'mother_income_proof_missing'))
        self.assertEqual(member_approval_state(app, 'mother'), 'unchecked')
        # The officer side: check it by eye.
        self.assertEqual(missing_reason(ApplicantDocument.objects.get(pk=slip.pk)), 'approval_unreadable')

    def test_an_open_approval_image_window_keeps_the_hold(self):
        from apps.scholarship.income_declaration import APPROVAL_ERROR, APPROVAL_UNTIL
        app = self._two_earners()
        _doc(app, 'salary_slip', {**_slip('informal', status='suspect', gross_income='RM400'),
                                  APPROVAL_TRIED: _LONG_AGO, APPROVAL_ERROR: 'All AI models failed: x',
                                  APPROVAL_UNTIL: _FUTURE}, member='mother')
        self.assertIsNone(self._status(app, 'mother_income_proof_missing'))


class ADeferredLetterOnlyAdds(_Sync):
    """TD-398: before A2.8a the mother's open request waited for her deferred letter although her other
    live letter had already read and answered it."""

    def _open(self, app, code):
        ResolutionItem.objects.create(application=app, source='check2', code=code, fact='income', kind='doc',
                                      doc_type='salary_slip', params={'household_member': 'mother'}, status='open')

    def test_her_read_payslip_resolves_the_request_beside_a_deferred_letter(self):
        app = self._two_earners()
        self._open(app, 'mother_income_proof_missing')
        _doc(app, 'salary_slip', _slip('private', gross_income='1,200.00'), member='mother')
        _doc(app, 'income_support_doc', {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _FUTURE}, member='mother')
        self.assertEqual(self._status(app, 'mother_income_proof_missing'), 'resolved')

    def test_another_members_read_letter_does_not_release_her_hold(self):
        from apps.scholarship.check2_deferred import held_doc_requests
        from apps.scholarship.check2_queries import DOC_SPECS
        app = self._two_earners()                                          # the father's payslip read fine
        self._open(app, 'mother_income_proof_missing')
        _doc(app, 'income_support_doc', {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _FUTURE}, member='mother')
        existing = {r.code: r for r in app.resolution_items.filter(source='check2')}
        self.assertIn('mother_income_proof_missing', held_doc_requests(app, DOC_SPECS, existing, set()))

    def test_a_raise_is_still_held_beside_a_read_letter(self):
        from apps.scholarship.check2_deferred import held_doc_requests
        from apps.scholarship.check2_queries import DOC_SPECS
        app = self._two_earners()
        _doc(app, 'salary_slip', _slip('private', gross_income='1,200.00'), member='mother')
        _doc(app, 'income_support_doc', {**_SERVICE_READ, SERVICE_RETRY_UNTIL: _FUTURE}, member='mother')
        held = held_doc_requests(app, DOC_SPECS, {}, {'mother_income_proof_missing'})
        self.assertIn('mother_income_proof_missing', held)
