"""Owner 2026-11-24 (#945): an officer's Re-run on a REPLACED copy judges again which copy is live.

Before this, Re-run re-read one document (a replaced one too) but never judged the slot again, so a
replaced copy a reader fix now reads BETTER than the live copy stayed in Old / Replaced. Now
``AdminRunVisionView`` asks ``upload_read.rejudge_after_rerun`` after a successful read: the upload's
own keep-better rule (``promotion.should_promote``), against the live copy of the copy's OWN exact slot
as it is now, promoted through ``slot_writes.promote_into_slot``. The stored ``read_plan`` stale ids
are never used (fix round: they can name another member's, request's or application's copy). Fake
people and fake reads only: the read is mocked, as the other Re-run view tests mock it; no paid or
network call.
"""
import re
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import promotion
from apps.scholarship.family import DECIDED_STATUSES
from apps.scholarship.income_engine import str_this_year
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, create_document, make_admin, make_application, make_cohort, make_student,
)
from apps.scholarship.tests.test_reslot_income_doc import _EPF_TEXT, _PAYSLIP_TEXT
from apps.scholarship.tests.test_reslot_income_doc import _Doc as _ReslotDoc
from apps.scholarship.upload_read import _RESLOT_FROM_TYPES, _str_names_a_stranger, _usable, rejudge_after_rerun
from apps.scholarship.views import _reslot_income_doc

APPS = '/api/v1/admin/scholarship/applications/'
LOGGER = 'apps.scholarship.upload_read'
DASHBOARD = {'source_type': 'dashboard', 'status': 'Lulus', 'year': ''}             # unconfirmed (3, 1)
SEMAKAN_UNREAD = {'source_type': 'semakan_status', 'status': '', 'year': ''}        # unreadable (2, 2)
PLAN = {'staged': True, 'stale_ids': [], 'existing_live': None}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   DOC_GENUINENESS_CHECK_ENABLED=False)
class _Slot(TestCase):
    """The #945 shape, invented: one STR slot, an older replaced Semakan, the live dashboard page,
    then three newer Semakan uploads the judging kept out with no ``superseded_by``."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)

    def setUp(self):
        self.app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer,
                                    income_route='str', income_earner='mother')
        year = str(str_this_year(self.app))
        self.current = {'source_type': 'semakan_status', 'status': 'Lulus', 'year': year}       # (4, 2)
        self.stale = {'source_type': 'semakan_status', 'status': 'Lulus', 'year': str(int(year) - 3)}
        self.old = self._str(SEMAKAN_UNREAD, superseded=True)
        self.live = self._str(DASHBOARD)
        ApplicantDocument.objects.filter(pk=self.old.pk).update(superseded_by=self.live)
        self.new1, self.new2, self.new3 = (self._str(SEMAKAN_UNREAD, superseded=True) for _ in range(3))

    def _str(self, fields, superseded=False, app=None, **kw):
        app = app or self.app
        return create_document(
            app, kw.pop('doc_type', 'str'), household_member=kw.pop('household_member', 'mother'),
            storage_path=f'test/str/{ApplicantDocument.objects.count()}', content_type='image/jpeg',
            superseded_at=timezone.now() if superseded else None, vision_run_at=timezone.now(),
            read_plan=kw.pop('read_plan', dict(PLAN)),
            vision_fields={'fields': dict(fields), 'authenticity': {'status': 'genuine'}}, **kw)

    def _rerun(self, doc, reads_as):
        """The officer's Re-run, with the read mocked to file ``reads_as`` (a reader fix)."""
        def _read(d):
            d.vision_fields = {'fields': dict(reads_as), 'authenticity': {'status': 'genuine'}}
            d.save(update_fields=['vision_fields'])
            return True
        with patch('apps.scholarship.reextract.reextract_document', side_effect=_read):
            return authed_client(self.reviewer).post(
                f'{APPS}{self.app.id}/documents/{doc.id}/re-run-vision/', {}, format='json')

    def reads(self, doc, fields):
        ApplicantDocument.objects.filter(pk=doc.pk).update(
            vision_fields={'fields': dict(fields), 'authenticity': {'status': 'genuine'}})

    def live_ids(self, app=None):
        return set(ApplicantDocument.objects.filter(
            application=app or self.app, superseded_at__isnull=True).values_list('id', flat=True))

    @staticmethod
    def outside_slot(doc):
        """Every row OUTSIDE ``doc``'s exact slot, with its live state: nothing here may move."""
        return {d.id: (d.superseded_at, d.superseded_by_id) for d in ApplicantDocument.objects.exclude(
            application_id=doc.application_id, doc_type=doc.doc_type, household_member=doc.household_member,
            request_code=doc.request_code)}

    @staticmethod
    def live_outside_slot(doc):
        return set(ApplicantDocument.objects.filter(superseded_at__isnull=True).exclude(
            application_id=doc.application_id, doc_type=doc.doc_type, household_member=doc.household_member,
            request_code=doc.request_code).values_list('id', flat=True))

    def assert_one_audit(self, logs, event, doc):
        """Exactly ONE line from the re-judge per call, and nothing in it but the event and two ids."""
        msgs = [r.getMessage() for r in logs.records]
        self.assertEqual(len(msgs), 1, msgs)
        self.assertRegex(msgs[0], re.compile(r'\AAUDIT rerun_rejudge_(promoted|skipped|failed) doc=\d+ app=\d+\Z'))
        self.assertEqual(msgs[0], f'AUDIT rerun_rejudge_{event} doc={doc.id} app={doc.application_id}')


def _payslip(name, gross):
    return {'fields': {'name': name, 'gross_income': gross, 'period': 'Jan 2026'}, 'warnings': [],
            'student_verdict': 'ok', 'capture': 'ai', 'error': ''}


class AReplacedCopyThatNowReadsBetterTakesTheSlot(_Slot):

    def test_the_945_shape_the_newest_semakan_now_current_replaces_the_dashboard(self):
        with self.assertLogs(LOGGER, 'INFO') as logs, \
                patch('apps.scholarship.upload_read.judge') as judge:
            r = self._rerun(self.new3, self.current)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.live_ids(), {self.new3.id})
        self.live.refresh_from_db()
        self.assertEqual(self.live.superseded_by_id, self.new3.id)      # the dashboard is history now
        body = r.json()                                                 # requirement 9: as it is after
        self.assertEqual(body['id'], self.new3.id)
        self.assertIsNone(body['superseded_at'])
        self.assertEqual(body['vision_fields']['fields']['status'], 'Lulus')
        self.assert_one_audit(logs, 'promoted', self.new3)
        judge.assert_not_called()                                       # not the upload's whole judging
        for other in (self.old, self.new1, self.new2):                  # the rest of the slot's history
            self.assertIsNotNone(ApplicantDocument.objects.get(pk=other.pk).superseded_at)

    def test_the_945_shape_at_profile_complete_with_the_plan_as_stored(self):
        type(self.app).objects.filter(pk=self.app.pk).update(status='profile_complete')
        ApplicantDocument.objects.filter(pk__in=[self.new1.pk, self.new2.pk, self.new3.pk]).update(
            read_plan={'staged': True, 'stale_ids': []}, superseded_by=None)
        r = self._rerun(self.new3, self.current)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.live_ids(), {self.new3.id})
        self.assertEqual(ApplicantDocument.objects.get(pk=self.live.pk).superseded_by_id, self.new3.id)

    def test_a_keep_better_type_other_than_str_is_reached_too_an_epf(self):
        name = self.app.profile.name
        ok = _payslip(name, '2500')
        live = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/live',
                               content_type='image/jpeg', vision_run_at=timezone.now(), vision_fields=ok)
        kept = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/kept',
                               content_type='image/jpeg', superseded_at=timezone.now(), vision_run_at=timezone.now(),
                               vision_fields={'fields': {}, 'student_verdict': 'unreadable', 'error': ''})
        ApplicantDocument.objects.filter(pk=kept.pk).update(vision_fields=dict(ok, fields=dict(ok['fields'], gross_income='2700')))
        self.assertTrue(rejudge_after_rerun(kept))
        self.assertIsNone(ApplicantDocument.objects.get(pk=kept.pk).superseded_at)
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, kept.id)


class ATypeTheUploadMayReFileByContentIsLeftAlone(_Slot):
    """Fix round 3: the upload may move a copy of these types to ANOTHER slot by its OCR text
    (``views._reslot_income_doc``: a salary slip that is really an EPF statement is filed as an EPF).
    A Re-run reads without that text, so it cannot know the upload would judge the copy here: it skips,
    one logged line, every row as it was. The student uploads again, as before."""

    def test_a_better_reading_copy_of_each_re_filed_type_is_not_promoted(self):
        name = self.app.profile.name
        for doc_type in _RESLOT_FROM_TYPES:
            with self.subTest(doc_type=doc_type):
                live = create_document(self.app, doc_type, household_member='father', storage_path=f'test/{doc_type}/l',
                                       content_type='image/jpeg', vision_run_at=timezone.now(),
                                       vision_fields=_payslip(name, '2500'))
                kept = create_document(self.app, doc_type, household_member='father', storage_path=f'test/{doc_type}/k',
                                       content_type='image/jpeg', superseded_at=timezone.now(), read_plan=dict(PLAN),
                                       vision_run_at=timezone.now(), vision_fields=_payslip(name, '2700'))
                fresh = ApplicantDocument.objects.get(pk=kept.pk)
                self.assertTrue(promotion.should_promote(fresh, live, usable=_usable(fresh)))   # the claim: it would win
                before = {d.id: (d.doc_type, d.household_member, d.request_code, d.superseded_at, d.superseded_by_id,
                                 d.vision_fields) for d in ApplicantDocument.objects.all()}
                with self.assertLogs(LOGGER, 'INFO') as logs:
                    self.assertFalse(rejudge_after_rerun(kept))
                self.assert_one_audit(logs, 'skipped', kept)
                self.assertEqual({d.id: (d.doc_type, d.household_member, d.request_code, d.superseded_at,
                                         d.superseded_by_id, d.vision_fields) for d in ApplicantDocument.objects.all()},
                                 before)

    def test_the_re_run_view_leaves_a_payslip_copy_where_it_is(self):
        name = self.app.profile.name
        live = create_document(self.app, 'salary_slip', household_member='father', storage_path='test/slip/l',
                               content_type='image/jpeg', vision_run_at=timezone.now(), vision_fields=_payslip(name, '2500'))
        kept = create_document(self.app, 'salary_slip', household_member='father', storage_path='test/slip/k',
                               content_type='image/jpeg', superseded_at=timezone.now(), vision_run_at=timezone.now(),
                               vision_fields={'fields': {}, 'student_verdict': 'unreadable', 'error': ''})

        def _read(d):
            d.vision_fields = _payslip(name, '2700')
            d.save(update_fields=['vision_fields'])
            return True
        with self.assertLogs(LOGGER, 'INFO') as logs, \
                patch('apps.scholarship.reextract.reextract_document', side_effect=_read):
            r = authed_client(self.reviewer).post(
                f'{APPS}{self.app.id}/documents/{kept.id}/re-run-vision/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_one_audit(logs, 'skipped', kept)
        self.assertIsNone(ApplicantDocument.objects.get(pk=live.pk).superseded_at)
        self.assertEqual(ApplicantDocument.objects.get(pk=kept.pk).doc_type, 'salary_slip')


class TheSkippedTypesFollowTheUploadsReSlot(TestCase):
    """The drift guard: ``_RESLOT_FROM_TYPES`` must name every type ``_reslot_income_doc`` can move a
    copy OUT of. If the re-slot starts moving another type, this fails until the tuple names it."""

    TEXTS = (_EPF_TEXT, _PAYSLIP_TEXT, 'SEMAKAN STATUS STR LULUS 2026', '')

    def test_no_type_outside_the_tuple_is_ever_moved(self):
        for doc_type, _label in ApplicantDocument.DOC_TYPES:
            if doc_type in _RESLOT_FROM_TYPES:
                continue
            for text in self.TEXTS:
                with self.subTest(doc_type=doc_type, text=text[:20]):
                    doc = _ReslotDoc(doc_type)
                    self.assertFalse(_reslot_income_doc(doc, {'text': text}))
                    self.assertEqual((doc.doc_type, doc.saved), (doc_type, []))

    def test_every_type_in_the_tuple_can_be_moved(self):
        for doc_type in _RESLOT_FROM_TYPES:
            with self.subTest(doc_type=doc_type):
                self.assertTrue(_reslot_income_doc(_ReslotDoc(doc_type), {'text': _EPF_TEXT}))

    def test_str_is_still_re_judged(self):
        self.assertNotIn('str', _RESLOT_FROM_TYPES)


class AThinnerOrOlderCopyNeverReplacesTheLiveCopy(_Slot):
    """Requirement 1, with the requirement-5 guard: a newer decided upload's decision stands."""

    def test_a_newer_copy_that_still_reads_worse_changes_nothing(self):
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._rerun(self.new3, self.stale)                      # (1, 2) < the dashboard's (3, 1)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.live_ids(), {self.live.id})
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_one_audit(logs, 'skipped', self.new3)

    def test_a_thinner_copy_with_a_stored_plan_naming_the_live_copy_changes_nothing(self):
        ApplicantDocument.objects.filter(pk=self.new3.pk).update(
            read_plan={'staged': True, 'stale_ids': [self.live.id, self.old.id]})
        r = self._rerun(self.new3, self.stale)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.live_ids(), {self.live.id})
        self.assertIsNone(ApplicantDocument.objects.get(pk=self.live.pk).superseded_by_id)

    def test_an_older_copy_equal_or_better_never_displaces_the_newer_live_copy(self):
        for reads_as in (DASHBOARD, self.current):
            with self.subTest(reads_as=reads_as['source_type']):
                self._rerun(self.old, reads_as)
                self.assertEqual(self.live_ids(), {self.live.id})

    def test_a_copy_a_newer_decided_upload_follows_is_left_alone(self):
        self._rerun(self.new2, self.current)                            # new3 was read and judged after it
        self.assertEqual(self.live_ids(), {self.live.id})

    def test_a_copy_whose_upload_read_is_still_queued_is_left_alone(self):
        ApplicantDocument.objects.filter(pk=self.new3.pk).update(read_state='pending')
        self._rerun(self.new3, self.current)
        self.assertEqual(self.live_ids(), {self.live.id})

    def test_an_empty_slot_is_not_refilled_from_history(self):
        ApplicantDocument.objects.filter(pk=self.live.pk).update(superseded_at=timezone.now())
        self._rerun(self.new3, self.current)
        self.assertEqual(self.live_ids(), set())

    def test_a_type_the_upload_never_judges_is_left_alone(self):
        live = create_document(self.app, 'other', storage_path='test/other/live', content_type='image/jpeg')
        old = create_document(self.app, 'other', storage_path='test/other/new', content_type='image/jpeg',
                              superseded_at=timezone.now())
        self.assertFalse(rejudge_after_rerun(old))
        self.assertIn(live.id, self.live_ids())

    def test_a_clash_with_a_concurrent_live_copy_keeps_the_live_copy(self):
        with patch('apps.scholarship.slot_writes.promote_into_slot', return_value=False):
            r = self._rerun(self.new3, self.current)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assertEqual(self.live_ids(), {self.live.id})


class OnlyTheReRunCopysOwnSlotChanges(_Slot):
    """Requirement 2: the same application, the same (doc type, member, request code) slot. The stored
    ``read_plan.stale_ids`` are the upload's and never reach the write (fix round, defect 1)."""

    def test_other_slots_and_other_applications_are_untouched(self):
        other_app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer,
                                     income_route='str', income_earner='mother')
        other_live = self._str(DASHBOARD, app=other_app)
        other_kept = self._str(SEMAKAN_UNREAD, superseded=True, app=other_app)
        officer_slot = self._str(DASHBOARD, request_code='officer_9')
        father_slip = create_document(self.app, 'salary_slip', household_member='father',
                                      storage_path='test/slip/f', content_type='image/jpeg')
        before = {d.id: (d.superseded_at, d.superseded_by_id)
                  for d in ApplicantDocument.objects.exclude(id__in=[self.live.id, self.new3.id])}
        self._rerun(self.new3, self.current)
        after = {d.id: (d.superseded_at, d.superseded_by_id)
                 for d in ApplicantDocument.objects.exclude(id__in=[self.live.id, self.new3.id])}
        self.assertEqual(before, after)
        self.assertEqual(self.live_ids(other_app), {other_live.id})
        self.assertIsNotNone(ApplicantDocument.objects.get(pk=other_kept.pk).superseded_at)
        self.assertIn(officer_slot.id, self.live_ids())
        self.assertIn(father_slip.id, self.live_ids())

    def _epfs(self):
        """The mother's live EPF M, then an EPF the tag guard re-tagged to the father and kept out, its
        stored plan still naming M (the upload's staged-against set). EPF, not payslip: a payslip is
        never re-judged by a Re-run (``_RESLOT_FROM_TYPES``)."""
        name = self.app.profile.name
        mother = create_document(self.app, 'epf', household_member='mother', storage_path='test/epf/m',
                                 content_type='image/jpeg', vision_run_at=timezone.now(),
                                 vision_fields=_payslip(name, '1900'))
        return mother, name

    def test_a_plan_naming_another_members_live_copy_never_reaches_it_when_the_slot_is_empty(self):
        mother, name = self._epfs()
        moved = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/x',
                                content_type='image/jpeg', superseded_at=timezone.now(), vision_run_at=timezone.now(),
                                read_plan={'staged': True, 'stale_ids': [mother.id]},
                                vision_fields=_payslip(name, '2700'))
        before, live_before = self.outside_slot(moved), self.live_outside_slot(moved)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(moved))               # the father's slot is empty: skip
        self.assert_one_audit(logs, 'skipped', moved)
        self.assertEqual(self.outside_slot(moved), before)
        self.assertEqual(self.live_outside_slot(moved), live_before)
        self.assertIn(mother.id, self.live_ids())

    def test_a_plan_naming_another_members_live_copy_never_reaches_it_when_the_slot_is_held(self):
        mother, name = self._epfs()
        father = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/f',
                                 content_type='image/jpeg', vision_run_at=timezone.now(),
                                 vision_fields=_payslip(name, '2500'))
        moved = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/x',
                                content_type='image/jpeg', superseded_at=timezone.now(), vision_run_at=timezone.now(),
                                read_plan={'staged': True, 'stale_ids': [mother.id]},
                                vision_fields=_payslip(name, '2700'))
        before, live_before = self.outside_slot(moved), self.live_outside_slot(moved)
        self.assertTrue(rejudge_after_rerun(moved))                    # wins its OWN slot only
        self.assertEqual(self.outside_slot(moved), before)
        self.assertEqual(self.live_outside_slot(moved), live_before)
        self.assertIn(mother.id, self.live_ids())
        self.assertEqual(ApplicantDocument.objects.get(pk=father.pk).superseded_by_id, moved.id)

    def test_a_plan_naming_the_apply_form_copy_never_reaches_it_from_a_request_slot(self):
        officer_live = self._str(DASHBOARD, request_code='officer_9')
        asked = self._str(SEMAKAN_UNREAD, superseded=True, request_code='officer_9',
                          read_plan={'staged': True, 'stale_ids': [self.live.id]})
        before, live_before = self.outside_slot(asked), self.live_outside_slot(asked)
        r = self._rerun(asked, self.current)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()['superseded_at'])                    # it won its request slot
        self.assertEqual(ApplicantDocument.objects.get(pk=officer_live.pk).superseded_by_id, asked.id)
        self.assertEqual(self.outside_slot(asked), before)
        self.assertEqual(self.live_outside_slot(asked), live_before)
        self.assertIn(self.live.id, self.live_ids())                    # the apply-form copy ('') stays

    def test_a_plan_naming_another_applications_live_copy_never_reaches_it(self):
        other_app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer,
                                     income_route='str', income_earner='mother')
        other_live = self._str(DASHBOARD, app=other_app)
        ApplicantDocument.objects.filter(pk=self.new3.pk).update(
            read_plan={'staged': True, 'stale_ids': [other_live.id]})
        before, live_before = self.outside_slot(self.new3), self.live_outside_slot(self.new3)
        self._rerun(self.new3, self.current)
        self.assertEqual(self.live_ids(), {self.new3.id})
        self.assertEqual(self.outside_slot(self.new3), before)
        self.assertEqual(self.live_outside_slot(self.new3), live_before)
        self.assertEqual(self.live_ids(other_app), {other_live.id})


class TheReJudgeReadsTheDatabaseNotTheObjectItIsHanded(_Slot):
    """Fix round (5d): the view's object was loaded before the read; the slot may have moved since."""

    def test_a_copy_made_live_again_since_it_was_loaded_is_left_alone(self):
        stale_obj = ApplicantDocument.objects.get(pk=self.new3.pk)       # superseded when loaded
        ApplicantDocument.objects.filter(pk=self.live.pk).update(superseded_at=timezone.now(), superseded_by=self.new3)
        ApplicantDocument.objects.filter(pk=self.new3.pk).update(superseded_at=None, superseded_by=None)
        self.reads(self.new3, self.current)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(stale_obj))
        self.assert_one_audit(logs, 'skipped', self.new3)
        self.assertEqual(self.live_ids(), {self.new3.id})
        self.assertEqual(ApplicantDocument.objects.get(pk=self.live.pk).superseded_by_id, self.new3.id)

    def test_a_better_copy_that_took_the_slot_since_it_was_loaded_is_compared_with(self):
        stale_obj = ApplicantDocument.objects.get(pk=self.new3.pk)       # superseded, keeper = dashboard
        self.reads(self.new1, self.current)                              # (4, 2) took the slot since
        ApplicantDocument.objects.filter(pk=self.live.pk).update(superseded_at=timezone.now(), superseded_by=self.new1)
        ApplicantDocument.objects.filter(pk=self.new1.pk).update(superseded_at=None, superseded_by=None)
        self.reads(self.new3, DASHBOARD)                                 # would tie the OLD keeper, loses to new1
        self.assertFalse(rejudge_after_rerun(stale_obj))
        self.assertEqual(self.live_ids(), {self.new1.id})


class AFailureNeverFailsThePaidReRun(_Slot):
    """Fix round (defect 2): anything the re-judge raises is one AUDIT line; the slot stays as it was
    and the view answers 200 with the re-read document."""

    def test_the_judge_raising_answers_200_with_the_re_read_document_and_no_swap(self):
        with self.assertLogs(LOGGER, 'INFO') as logs, \
                patch('apps.scholarship.promotion.should_promote', side_effect=RuntimeError('boom')):
            r = self._rerun(self.new3, self.current)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['id'], self.new3.id)
        self.assertIsNotNone(body['superseded_at'])
        self.assertEqual(body['vision_fields']['fields'], self.current)     # the re-read, as read
        self.assertEqual(self.live_ids(), {self.live.id})
        self.assert_one_audit(logs, 'failed', self.new3)

    def test_a_write_that_fails_half_way_is_rolled_back_whole(self):
        def _half(app, doc, stale_ids):
            ApplicantDocument.objects.filter(pk=self.live.pk).update(superseded_at=timezone.now())
            raise RuntimeError('boom')
        self.reads(self.new3, self.current)
        with self.assertLogs(LOGGER, 'INFO') as logs, \
                patch('apps.scholarship.slot_writes.promote_into_slot', side_effect=_half):
            self.assertFalse(rejudge_after_rerun(self.new3))
        self.assert_one_audit(logs, 'failed', self.new3)
        self.assertEqual(self.live_ids(), {self.live.id})                    # and the transaction is usable

    def test_a_copy_deleted_under_the_re_judge_is_a_failure_line_not_a_500(self):
        gone = ApplicantDocument.objects.get(pk=self.new3.pk)
        ApplicantDocument.objects.filter(pk=self.new3.pk).delete()
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(gone))
        self.assert_one_audit(logs, 'failed', gone)


class OfferLettersAndStrangersAreNeverPromotedByAReRun(_Slot):
    """Fix round (defects 3 and 4). An offer letter is skipped: the read already ran the pathway
    autofill against the OLD live letter. An STR the match verdict says names a stranger is never
    promoted, though ``should_promote`` would promote a rejected one ('news') before any usable or
    TD-409 check; a matched rejected copy is promoted exactly as the upload promotes it."""

    FATHER, FATHER_NRIC = 'Ravindran A/L Kannappan', '700101-10-5111'
    MOTHER, MOTHER_NRIC = 'Malathi A/P Rajendran', '720202-10-5222'
    STRANGER, STRANGER_NRIC = 'Hasnul Bin Omarudin', '800303-10-5333'

    def test_an_offer_letter_is_skipped(self):
        live = create_document(self.app, 'offer_letter', storage_path='test/offer/live', content_type='image/jpeg')
        kept = create_document(self.app, 'offer_letter', storage_path='test/offer/kept', content_type='image/jpeg',
                               superseded_at=timezone.now())
        with self.assertLogs(LOGGER, 'INFO') as logs, \
                patch('apps.scholarship.promotion.should_promote', return_value=True):
            self.assertFalse(rejudge_after_rerun(kept))
        self.assert_one_audit(logs, 'skipped', kept)
        self.assertIn(live.id, self.live_ids())
        self.assertIsNotNone(ApplicantDocument.objects.get(pk=kept.pk).superseded_at)

    def _household(self):
        app = make_application(
            'assigned', cohort=self.cohort, reviewer=self.reviewer,
            student=make_student(name='Kavinesh A/L Ravindran'), income_route='str', income_earner='mother',
            father_name=self.FATHER, father_occupation='private', mother_name=self.MOTHER,
            mother_occupation='homemaker', other_family_members=[], siblings_in_school=0, siblings_in_tertiary=0)
        for member, name, nric in (('father', self.FATHER, self.FATHER_NRIC), ('mother', self.MOTHER, self.MOTHER_NRIC)):
            create_document(app, 'parent_ic', household_member=member, storage_path=f'test/ic/{member}',
                            content_type='image/jpeg', vision_fields={}, vision_name=name, vision_nric=nric,
                            vision_run_at=timezone.now())
        year = str(str_this_year(app))
        live = self._str(dict(self.current, year=year, recipient_name=self.MOTHER, recipient_nric=self.MOTHER_NRIC),
                         app=app)
        return app, year, live

    def test_a_strangers_rejected_str_never_replaces_the_familys_matched_current_one(self):
        app, year, live = self._household()
        rerun = self._str(SEMAKAN_UNREAD, superseded=True, app=app)
        self.reads(rerun, {'source_type': 'semakan_status', 'status': 'Ditolak', 'year': year,
                           'recipient_name': self.STRANGER, 'recipient_nric': self.STRANGER_NRIC})
        fresh = ApplicantDocument.objects.get(pk=rerun.pk)
        self.assertTrue(promotion.should_promote(fresh, live, usable=_usable(fresh)))   # the claim: upload would
        self.assertTrue(_str_names_a_stranger(fresh))
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(rerun))
        self.assert_one_audit(logs, 'skipped', rerun)
        self.assertEqual(set(ApplicantDocument.objects.filter(application=app, doc_type='str',
                                                              superseded_at__isnull=True).values_list('id', flat=True)),
                         {live.id})

    def test_the_familys_own_rejected_str_is_promoted_as_the_upload_promotes_it(self):
        app, year, live = self._household()
        rerun = self._str(SEMAKAN_UNREAD, superseded=True, app=app)
        self.reads(rerun, {'source_type': 'semakan_status', 'status': 'Ditolak', 'year': year,
                           'recipient_name': self.MOTHER, 'recipient_nric': self.MOTHER_NRIC})
        fresh = ApplicantDocument.objects.get(pk=rerun.pk)
        self.assertFalse(_str_names_a_stranger(fresh))
        self.assertTrue(promotion.should_promote(fresh, live, usable=_usable(fresh)))
        self.assertTrue(rejudge_after_rerun(rerun))
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, rerun.id)


class ACopyTheUploadWouldFileUnderAnotherMemberStaysWhereItIs(_Slot):
    """Fix round 2: the upload's tag guard (``judge`` → ``_tag_guard_member``) runs BEFORE its
    keep-better decision and files a copy whose read names another member under THAT member, so the
    upload never judges it in this slot. A Re-run never re-tags: it skips, one logged line, every row
    as it was. Each case has a control where the read names the slot's own member (or no one)."""

    FATHER, FATHER_NRIC = 'Ravindran A/L Kannappan', '700101-10-5111'
    MOTHER, MOTHER_NRIC = 'Malathi A/P Rajendran', '720202-10-5222'

    def _household(self, route, *, ics=('father', 'mother'), earner=''):
        app = make_application(
            'assigned', cohort=self.cohort, reviewer=self.reviewer,
            student=make_student(name='Kavinesh A/L Ravindran'), income_route=route, income_earner=earner,
            father_name=self.FATHER, father_occupation='private', mother_name=self.MOTHER,
            mother_occupation='private', other_family_members=[], siblings_in_school=0, siblings_in_tertiary=0)
        for member in ics:
            name, nric = (self.FATHER, self.FATHER_NRIC) if member == 'father' else (self.MOTHER, self.MOTHER_NRIC)
            create_document(app, 'parent_ic', household_member=member, storage_path=f'test/ic/{member}',
                            content_type='image/jpeg', vision_fields={}, vision_name=name, vision_nric=nric,
                            vision_run_at=timezone.now())
        return app

    def _slip(self, app, member, vf, superseded=False, doc_type='salary_slip'):
        return create_document(app, doc_type, household_member=member, content_type='image/jpeg',
                               storage_path=f'test/slip/{ApplicantDocument.objects.count()}', read_plan=dict(PLAN),
                               superseded_at=timezone.now() if superseded else None, vision_run_at=timezone.now(),
                               vision_fields=vf)

    def _unreadable(self, app, member, doc_type='salary_slip'):
        return self._slip(app, member, {'fields': {}, 'student_verdict': 'unreadable', 'error': ''}, superseded=True,
                          doc_type=doc_type)

    def _rerun_view(self, app, doc, vision_fields):
        def _read(d):
            d.vision_fields = vision_fields
            d.save(update_fields=['vision_fields'])
            return True
        with patch('apps.scholarship.reextract.reextract_document', side_effect=_read):
            return authed_client(self.reviewer).post(
                f'{APPS}{app.id}/documents/{doc.id}/re-run-vision/', {}, format='json')

    def rows(self, app):
        return {d.id: (d.doc_type, d.household_member, d.request_code, d.superseded_at, d.superseded_by_id)
                for d in ApplicantDocument.objects.filter(application=app)}

    def would_promote_but_for_the_tag_guard(self, doc, live):
        fresh = ApplicantDocument.objects.get(pk=doc.pk)
        self.assertTrue(promotion.should_promote(fresh, live, usable=_usable(fresh)))   # the claim: it would win
        self.assertFalse(_str_names_a_stranger(fresh))

    def assert_skipped_and_untouched(self, app, doc, before, logs):
        self.assert_one_audit(logs, 'skipped', doc)
        self.assertEqual(self.rows(app), before)                    # no row moved, re-tagged or re-slotted

    def test_the_defect_a_payslip_filed_under_the_father_that_reads_the_mother_is_left_alone(self):
        app = self._household('salary', ics=('mother',))                     # the father has no IC on file
        father = self._slip(app, 'father', _payslip(self.FATHER, '2500'))
        kept = self._unreadable(app, 'father')
        mother_vf = _payslip(self.MOTHER, '2700')
        ApplicantDocument.objects.filter(pk=kept.pk).update(vision_fields=mother_vf)
        self.would_promote_but_for_the_tag_guard(kept, father)
        ApplicantDocument.objects.filter(pk=kept.pk).update(vision_fields={'fields': {}, 'student_verdict': 'unreadable'})
        before = self.rows(app)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._rerun_view(app, kept, mother_vf)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_skipped_and_untouched(app, kept, before, logs)            # the read is the only change
        self.assertEqual(ApplicantDocument.objects.get(pk=kept.pk).household_member, 'father')
        self.assertIsNone(ApplicantDocument.objects.get(pk=father.pk).superseded_at)

    def test_an_epf_filed_under_the_father_that_reads_the_mother_is_left_alone(self):
        app = self._household('salary', ics=('mother',))
        father = self._slip(app, 'father', _payslip(self.FATHER, '2500'), doc_type='epf')
        kept = self._unreadable(app, 'father', doc_type='epf')
        mother_vf = _payslip(self.MOTHER, '2700')
        ApplicantDocument.objects.filter(pk=kept.pk).update(vision_fields=mother_vf)
        self.would_promote_but_for_the_tag_guard(kept, father)
        ApplicantDocument.objects.filter(pk=kept.pk).update(vision_fields={'fields': {}, 'student_verdict': 'unreadable'})
        before = self.rows(app)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._rerun_view(app, kept, mother_vf)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_skipped_and_untouched(app, kept, before, logs)
        self.assertIsNone(ApplicantDocument.objects.get(pk=father.pk).superseded_at)

    def test_control_the_same_epf_reading_the_father_is_promoted(self):
        app = self._household('salary', ics=('mother',))
        father = self._slip(app, 'father', _payslip(self.FATHER, '2500'), doc_type='epf')
        kept = self._unreadable(app, 'father', doc_type='epf')
        r = self._rerun_view(app, kept, _payslip(self.FATHER, '2700'))
        self.assertIsNone(r.json()['superseded_at'])
        self.assertEqual(ApplicantDocument.objects.get(pk=father.pk).superseded_by_id, kept.id)

    def _strs(self, app, member, live_reads, kept_reads):
        live = self._str(live_reads, app=app, household_member=member)
        kept = self._str(SEMAKAN_UNREAD, superseded=True, app=app, household_member=member)
        self.reads(kept, kept_reads)
        return live, kept

    def test_an_str_filed_under_the_mother_that_reads_the_fathers_nric_is_left_alone(self):
        app = self._household('salary')
        year = str(str_this_year(app))
        live, kept = self._strs(app, 'mother', dict(DASHBOARD, recipient_name=self.MOTHER, recipient_nric=self.MOTHER_NRIC),
                                dict(self.current, year=year, recipient_name=self.FATHER, recipient_nric=self.FATHER_NRIC))
        self.would_promote_but_for_the_tag_guard(kept, live)
        before = self.rows(app)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(kept))
        self.assert_skipped_and_untouched(app, kept, before, logs)

    def test_control_the_same_str_reading_the_mothers_nric_is_promoted(self):
        app = self._household('salary')
        year = str(str_this_year(app))
        live, kept = self._strs(app, 'mother', dict(DASHBOARD, recipient_name=self.MOTHER, recipient_nric=self.MOTHER_NRIC),
                                dict(self.current, year=year, recipient_name=self.MOTHER, recipient_nric=self.MOTHER_NRIC))
        self.assertTrue(rejudge_after_rerun(kept))
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, kept.id)

    def test_a_blank_tagged_epf_the_name_files_under_the_mother_is_left_alone(self):
        app = self._household('salary', ics=())
        blank = self._slip(app, '', _payslip('', '2500'), doc_type='epf')
        kept = self._unreadable(app, '', doc_type='epf')
        self.reads_vf(kept, _payslip(self.MOTHER, '2700'))
        self.would_promote_but_for_the_tag_guard(kept, blank)
        before = self.rows(app)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(kept))
        self.assert_skipped_and_untouched(app, kept, before, logs)

    def test_control_a_blank_tagged_epf_with_no_name_on_the_salary_route_is_promoted(self):
        app = self._household('salary', ics=())
        blank = self._slip(app, '', _payslip('', '2500'), doc_type='epf')
        kept = self._unreadable(app, '', doc_type='epf')
        self.reads_vf(kept, _payslip('', '2700'))
        self.assertTrue(rejudge_after_rerun(kept))
        self.assertEqual(ApplicantDocument.objects.get(pk=blank.pk).superseded_by_id, kept.id)

    def test_a_blank_tagged_str_the_str_route_files_under_its_earner_is_left_alone(self):
        app = self._household('str', ics=(), earner='mother')
        live, kept = self._strs(app, '', DASHBOARD, self.current_for(app))
        self.would_promote_but_for_the_tag_guard(kept, live)
        before = self.rows(app)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(kept))
        self.assert_skipped_and_untouched(app, kept, before, logs)

    def test_control_a_blank_tagged_str_on_the_salary_route_is_promoted(self):
        app = self._household('salary', ics=())
        live, kept = self._strs(app, '', DASHBOARD, self.current_for(app))
        self.assertTrue(rejudge_after_rerun(kept))
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, kept.id)

    def test_the_945_shape_reading_the_mothers_own_name_and_nric_still_takes_the_slot(self):
        app = self._household('str', earner='mother')
        type(app).objects.filter(pk=app.pk).update(status='profile_complete')
        live = self._str(DASHBOARD, app=app)
        kept = [self._str(SEMAKAN_UNREAD, superseded=True, app=app, read_plan={'staged': True, 'stale_ids': []})
                for _ in range(3)]
        newest = kept[-1]
        r = self._rerun_view(app, newest, {'fields': dict(self.current_for(app), recipient_name=self.MOTHER,
                                                          recipient_nric=self.MOTHER_NRIC),
                                           'authenticity': {'status': 'genuine'}})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()['superseded_at'])
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, newest.id)
        self.assertEqual(ApplicantDocument.objects.get(pk=newest.pk).household_member, 'mother')

    def current_for(self, app):
        return dict(self.current, year=str(str_this_year(app)))

    @staticmethod
    def reads_vf(doc, vision_fields):
        ApplicantDocument.objects.filter(pk=doc.pk).update(vision_fields=vision_fields)


def _sample_mark(doc_type):
    """What the upload's sample check (H9, ``sample_stamp.check_uploaded_sample``) stores on a copy."""
    return {'status': 'not_' + doc_type, 'doc_seen': 'sample_document', 'reason': 'Looks like a sample.',
            'sample': True, 'sample_check_version': '1.0.0', 'scored_status': 'genuine'}


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class ACopyTheUploadMarkedAsASampleIsNeverPromoted(_Slot):
    """Fix round 4 (the read side): the upload's read ends with the sample check (``_check_sample``),
    which marks a stamped SAMPLE / CONTOH copy not genuine, so the upload never accepts it. A Re-run
    never runs that check, and with the genuineness check on its fresh read REPLACES the stored mark
    (``add_read_authenticity`` → ``_store_field_read``). So the view asks for the mark BEFORE the re-read
    and the re-judge skips a marked copy (and one still marked after). Each defect test runs the REAL
    read path (``reextract_document`` → ``run_field_extraction_for_document`` → ``_store_field_read``):
    only the network seams are faked (OCR, name match, label read, the genuineness scorer)."""

    @staticmethod
    def _seams(fields):
        """Only the network seams of the real read path: OCR, name match, label read, genuineness scorer."""
        from contextlib import ExitStack

        def _ex(*_a, **_k):
            return {'fields': dict(fields), 'warnings': [], 'error': '', 'capture': 'deterministic'}
        stack = ExitStack()
        for target, kw in (
                ('apps.scholarship.vision.ocr_document_full', {'return_value': {'text': 'x', 'error': None, 'image': b'i'}}),
                ('apps.scholarship.vision.run_vision_match_for_document', {'return_value': {}}),
                ('apps.scholarship.vision.field_extraction._read_labelled_doc', {'side_effect': _ex}),
                ('apps.scholarship.vision.authenticity._auth_str', {'return_value': {'status': 'genuine'}}),
                ('apps.scholarship.vision.authenticity._auth_signature_doc', {'return_value': {'status': 'genuine'}})):
            stack.enter_context(patch(target, **kw))
        return stack

    def _real_rerun(self, app, doc, fields):
        with self._seams(fields):
            return authed_client(self.reviewer).post(
                f'{APPS}{app.id}/documents/{doc.id}/re-run-vision/', {}, format='json')

    def _press_and_expect_a_skip(self, kept, fields, before):
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._real_rerun(self.app, kept, fields)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_one_audit(logs, 'skipped', kept)
        self.assertEqual(self.slot_rows(kept), before)

    def slot_rows(self, doc):
        return {d.id: (d.superseded_at, d.superseded_by_id) for d in ApplicantDocument.objects.filter(
            application_id=doc.application_id, doc_type=doc.doc_type, household_member=doc.household_member,
            request_code=doc.request_code)}

    def _945_slot(self, *, sample):
        """The motivating shape: profile_complete, the three newest copies kept out with no keeper and
        the plan as stored; the newest one marked a sample at upload (or not, for the control)."""
        type(self.app).objects.filter(pk=self.app.pk).update(status='profile_complete')
        ApplicantDocument.objects.filter(pk__in=[self.new1.pk, self.new2.pk, self.new3.pk]).update(
            read_plan={'staged': True, 'stale_ids': []}, superseded_by=None)
        if sample:
            ApplicantDocument.objects.filter(pk=self.new3.pk).update(
                vision_fields={'fields': dict(self.current), 'authenticity': _sample_mark('str')})
        return self.new3

    def _epf_slot(self, *, sample):
        name = self.app.profile.name
        live = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/live',
                               content_type='image/jpeg', vision_run_at=timezone.now(), vision_fields=_payslip(name, '2500'))
        kept = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/kept',
                               content_type='image/jpeg', superseded_at=timezone.now(), vision_run_at=timezone.now(),
                               read_plan=dict(PLAN), vision_fields=dict(
                                   _payslip(name, '2700'), authenticity=_sample_mark('epf') if sample else {'status': 'genuine'}))
        return live, kept, dict(_payslip(name, '2700')['fields'])

    def assert_cleared_and_would_win(self, doc, live):
        """The point of the defect: the re-read really dropped the mark, and the copy would win."""
        from apps.scholarship.genuineness.sample_stamp import is_sample_flagged
        fresh = ApplicantDocument.objects.get(pk=doc.pk)
        self.assertFalse(is_sample_flagged(fresh))
        self.assertEqual(fresh.vision_fields['authenticity'], {'status': 'genuine'})
        self.assertTrue(promotion.should_promote(fresh, live, usable=_usable(fresh)))

    def test_the_defect_a_sample_str_whose_re_read_comes_back_clean_is_not_promoted(self):
        kept = self._945_slot(sample=True)
        before = self.slot_rows(kept)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._real_rerun(self.app, kept, self.current)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_one_audit(logs, 'skipped', kept)
        self.assertEqual(self.slot_rows(kept), before)
        self.assertEqual(self.live_ids(), {self.live.id})
        self.assert_cleared_and_would_win(kept, self.live)

    def test_control_the_945_shape_without_the_mark_is_promoted_on_the_real_read_path(self):
        kept = self._945_slot(sample=False)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._real_rerun(self.app, kept, self.current)
        self.assertIsNone(r.json()['superseded_at'])
        self.assert_one_audit(logs, 'promoted', kept)
        self.assertEqual(self.live_ids(), {kept.id})
        self.assertEqual(ApplicantDocument.objects.get(pk=self.live.pk).superseded_by_id, kept.id)

    def test_the_defect_a_sample_epf_whose_re_read_comes_back_clean_is_not_promoted(self):
        live, kept, fields = self._epf_slot(sample=True)
        before = self.slot_rows(kept)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            r = self._real_rerun(self.app, kept, fields)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()['superseded_at'])
        self.assert_one_audit(logs, 'skipped', kept)
        self.assertEqual(self.slot_rows(kept), before)
        self.assertIsNone(ApplicantDocument.objects.get(pk=live.pk).superseded_at)
        self.assert_cleared_and_would_win(kept, live)

    def test_control_the_same_epf_without_the_mark_is_promoted(self):
        live, kept, fields = self._epf_slot(sample=False)
        r = self._real_rerun(self.app, kept, fields)
        self.assertIsNone(r.json()['superseded_at'])
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, kept.id)

    def test_a_copy_still_marked_after_the_re_read_is_not_promoted(self):
        """(b): the mark survived the re-read (the genuineness check off keeps the stored score, TD-407)
        and the caller did not ask before it: the re-judge reads the mark off the row itself. A rejected
        STR shows why ``_usable`` alone is not enough: ``should_promote`` takes it as news first."""
        kept = self._945_slot(sample=False)
        ApplicantDocument.objects.filter(pk=kept.pk).update(vision_fields={
            'fields': dict(self.current, status='Ditolak'), 'authenticity': _sample_mark('str')})
        fresh = ApplicantDocument.objects.get(pk=kept.pk)
        self.assertFalse(_usable(fresh))
        self.assertFalse(_str_names_a_stranger(fresh))
        self.assertTrue(promotion.should_promote(fresh, self.live, usable=_usable(fresh)))   # the claim
        before = self.slot_rows(kept)
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.assertFalse(rejudge_after_rerun(kept))
        self.assert_one_audit(logs, 'skipped', kept)
        self.assertEqual(self.slot_rows(kept), before)
        self.assertEqual(self.live_ids(), {self.live.id})

    # Round 4, second item: the first Re-run's fresh read drops the mark, so the view keeps a lasting
    # record on the row (``read_plan['was_sample']``) BEFORE the re-read; every later Re-run skips too.

    def test_a_sample_str_pressed_twice_is_skipped_both_times(self):
        kept = self._945_slot(sample=True)
        before = self.slot_rows(kept)
        self._press_and_expect_a_skip(kept, self.current, before)
        self.assert_cleared_and_would_win(kept, self.live)           # the mark is gone after press one
        self.assertEqual(ApplicantDocument.objects.get(pk=kept.pk).read_plan,
                         {'staged': True, 'stale_ids': [], 'was_sample': True})
        self._press_and_expect_a_skip(kept, self.current, before)
        self.assertEqual(self.live_ids(), {self.live.id})

    def test_a_sample_epf_with_no_read_plan_pressed_twice_is_skipped_both_times(self):
        live, kept, fields = self._epf_slot(sample=True)
        ApplicantDocument.objects.filter(pk=kept.pk).update(read_plan=None)    # an older row: no plan
        before = self.slot_rows(kept)
        self._press_and_expect_a_skip(kept, fields, before)
        self.assertEqual(ApplicantDocument.objects.get(pk=kept.pk).read_plan, {'was_sample': True})
        self._press_and_expect_a_skip(kept, fields, before)
        self.assertIsNone(ApplicantDocument.objects.get(pk=live.pk).superseded_at)

    def test_three_presses_with_a_plain_re_read_in_between_are_all_skipped(self):
        from apps.scholarship.reextract import reextract_document
        kept = self._945_slot(sample=True)
        before = self.slot_rows(kept)
        for press in range(3):
            self._press_and_expect_a_skip(kept, self.current, before)
            if press < 2:
                with self._seams(self.current):                       # the bulk command's read
                    self.assertTrue(reextract_document(ApplicantDocument.objects.get(pk=kept.pk)))
        self.assertEqual(self.live_ids(), {self.live.id})
        self.assertTrue(ApplicantDocument.objects.get(pk=kept.pk).read_plan['was_sample'])

    def test_the_record_survives_every_other_reader_and_writer_and_changes_none_of_them(self):
        from apps.scholarship.reextract import reextract_document
        from apps.scholarship.upload_read import judge_reread_copy, kept_out_by_outage, run_read
        kept = self._945_slot(sample=True)
        plain = ApplicantDocument.objects.get(pk=kept.pk)
        answers = (kept_out_by_outage(plain), run_read(kept.pk))
        self._press_and_expect_a_skip(kept, self.current, self.slot_rows(kept))
        with self._seams(self.current):
            reextract_document(ApplicantDocument.objects.get(pk=kept.pk), reslot=True, fresh=False)  # the sweep's read
        marked = ApplicantDocument.objects.get(pk=kept.pk)
        self.assertEqual((kept_out_by_outage(marked), run_read(kept.pk)), answers)
        judge_reread_copy(marked)                                     # the sweep's judge: skipped, writes no plan
        self.assertTrue(ApplicantDocument.objects.filter(pk=kept.pk, read_plan__staged=True).exists())  # the sweep's filter
        self.assertEqual(ApplicantDocument.objects.get(pk=kept.pk).read_plan,
                         {'staged': True, 'stale_ids': [], 'was_sample': True})

    def test_a_live_sample_copy_re_run_writes_no_record_and_answers_as_before(self):
        ApplicantDocument.objects.filter(pk=self.live.pk).update(
            vision_fields={'fields': dict(DASHBOARD), 'authenticity': _sample_mark('str')})
        with self.assertNoLogs(LOGGER, 'INFO'):
            r = self._real_rerun(self.app, self.live, DASHBOARD)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()['superseded_at'])
        self.assertEqual(ApplicantDocument.objects.get(pk=self.live.pk).read_plan, PLAN)
        self.assertEqual(self.live_ids(), {self.live.id})


class ACopyTheUploadsHeicFixWouldReadIsLeftAlone(_Slot):
    """Fix round 4: the upload's read starts with the HEIC fix (``imaging.convert_heic_to_jpeg``), which
    a Re-run never runs. A copy converted at upload is a JPEG now; one still HEIC (the fix failed) may
    read differently once converted, so the Re-run cannot know the upload's answer: it skips."""

    def test_a_heic_copy_that_would_win_is_left_alone_and_its_jpeg_twin_is_promoted(self):
        name = self.app.profile.name
        live = create_document(self.app, 'epf', household_member='father', storage_path='test/epf/live',
                               content_type='image/jpeg', vision_run_at=timezone.now(), vision_fields=_payslip(name, '2500'))
        for content_type, filename, promoted in (('image/heic', 'k.heic', False), ('image/jpeg', 'k.HEIF', False),
                                                 ('image/jpeg', 'k.jpg', True)):
            with self.subTest(content_type=content_type, filename=filename):
                kept = create_document(self.app, 'epf', household_member='father', storage_path=f'test/epf/{filename}',
                                       content_type=content_type, original_filename=filename,
                                       superseded_at=timezone.now(), vision_run_at=timezone.now(),
                                       vision_fields=_payslip(name, '2700'))
                fresh = ApplicantDocument.objects.get(pk=kept.pk)
                self.assertTrue(promotion.should_promote(fresh, live, usable=_usable(fresh)))
                with self.assertLogs(LOGGER, 'INFO') as logs:
                    self.assertEqual(rejudge_after_rerun(kept), promoted)
                self.assert_one_audit(logs, 'promoted' if promoted else 'skipped', kept)
                self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_at is None, not promoted)


class ALiveCopyAndADecidedCaseAreAnsweredAsBefore(_Slot):

    def test_re_run_on_the_live_copy_never_re_judges(self):
        with patch('apps.scholarship.upload_read.rejudge_after_rerun') as rejudge:
            r = self._rerun(self.live, DASHBOARD)
        self.assertEqual(r.status_code, 200)
        rejudge.assert_not_called()
        self.assertEqual(r.json()['id'], self.live.id)
        self.assertEqual(self.live_ids(), {self.live.id})

    def test_a_decided_case_re_reads_but_never_re_judges(self):
        self.reads(self.new3, self.current)                             # would win on an open case
        for status in sorted(DECIDED_STATUSES):
            with self.subTest(status=status):
                type(self.app).objects.filter(pk=self.app.pk).update(status=status)
                with self.assertLogs(LOGGER, 'INFO') as logs:
                    self.assertFalse(rejudge_after_rerun(self.new3))
                self.assertEqual(self.live_ids(), {self.live.id})
                self.assert_one_audit(logs, 'skipped', self.new3)
        type(self.app).objects.filter(pk=self.app.pk).update(status='assigned')   # the control
        self.assertTrue(rejudge_after_rerun(self.new3))


class NothingStudentFacingBeyondTheSwap(_Slot):
    """Requirement 7: no request closing, no attempt note, no ticket, no notify, no email."""

    def test_the_swap_alone(self):
        items = list(self.app.resolution_items.values_list('id', 'status'))
        notified = type(self.app).objects.get(pk=self.app.pk).query_raised_notified_at
        with patch('apps.scholarship.resolution.resolve_doc_items_for_upload') as resolve, \
                patch('apps.scholarship.resolution.sync_resolution_items') as sync, \
                patch('apps.scholarship.views._note_unresolved_attempts') as note, \
                patch('apps.scholarship.income_engine.dedupe_income_proof') as dedupe:
            self._rerun(self.new3, self.current)
        self.assertEqual(self.live_ids(), {self.new3.id})
        for called in (resolve, sync, note, dedupe):
            called.assert_not_called()
        self.assertEqual(list(self.app.resolution_items.values_list('id', 'status')), items)
        self.assertEqual(type(self.app).objects.get(pk=self.app.pk).query_raised_notified_at, notified)
        self.assertEqual(mail.outbox, [])

    def test_an_ic_promoted_by_re_run_is_aligned_as_an_upload_promotion_is(self):
        live = create_document(self.app, 'ic', storage_path='test/ic/live', content_type='image/jpeg')
        kept = create_document(self.app, 'ic', storage_path='test/ic/kept', content_type='image/jpeg',
                               superseded_at=timezone.now())
        with patch('apps.scholarship.promotion.should_promote', return_value=True), \
                patch('apps.scholarship.upload_read._align_name_after_promotion') as align:
            self.assertTrue(rejudge_after_rerun(kept))
        align.assert_called_once()
        self.assertEqual(ApplicantDocument.objects.get(pk=live.pk).superseded_by_id, kept.id)
