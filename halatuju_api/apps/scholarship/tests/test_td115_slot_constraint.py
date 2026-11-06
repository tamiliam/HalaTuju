"""TD-115 (audit A1.8) — the DATABASE guard on the document slot.

One LIVE `applicant_documents` row per slot, the slot being the 4-column key (application,
doc_type, household_member, request_code); in-programme results slips (request_code
'in_programme') are left out by design. SQLite enforces partial unique indexes, so these run the
real index, not a stand-in.

What these pin:
  1. the constraint itself — a second live row in a slot is refused; history, another request and
     in-programme slips are not;
  2. every writer that used to put the new row live FIRST now supersedes first (upload door,
     refile to SPM / higher, the STR de-dup re-tag, the team's split, the untagged-doc backfill);
  3. two uploads at once meet the index as a clean answer — a retry, a 409, or the new copy kept
     in Old / Replaced — never a 500 and never two live rows.
"""
from io import StringIO
from unittest.mock import patch

import jwt
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import results_route
from apps.scholarship.income_engine import dedupe_income_proof
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.results_review import SLIP_REQUEST_CODE
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.test_split_combined_results import SplitCase

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER = 'td115-user'


def _app(**kw):
    return make_application('interviewing', student=make_student(name='Muthu Raman'), **kw)


def _doc(app, doc_type='ic', member='', request_code='', **kw):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member=member, request_code=request_code,
        storage_path=kw.pop('storage_path', f'blob-{ApplicantDocument.objects.count()}'), **kw)


def _live(app, doc_type, **kw):
    return ApplicantDocument.objects.filter(application=app, doc_type=doc_type,
                                            superseded_at__isnull=True, **kw)


class TestSlotConstraint(TestCase):
    def test_second_live_row_in_the_same_slot_is_refused(self):
        app = _app()
        _doc(app, 'salary_slip', member='father', request_code='income_doc_stale')
        with self.assertRaises(IntegrityError), transaction.atomic():
            _doc(app, 'salary_slip', member='father', request_code='income_doc_stale')

    def test_blank_member_and_blank_request_is_a_slot_too(self):
        app = _app()
        _doc(app, 'ic')
        with self.assertRaises(IntegrityError), transaction.atomic():
            _doc(app, 'ic')

    def test_a_superseded_row_and_a_new_live_row_coexist(self):
        app = _app()
        new = _doc(app, 'ic')
        _doc(app, 'ic', superseded_at=timezone.now(), superseded_by=new)
        _doc(app, 'ic', superseded_at=timezone.now(), superseded_by=new)   # history has no cap
        self.assertEqual(_live(app, 'ic').count(), 1)

    def test_a_different_request_code_is_its_own_slot(self):
        """TD-134: each officer request is its own slot — why the key is 4 columns, not 3."""
        app = _app()
        _doc(app, 'other', request_code='')
        _doc(app, 'other', request_code='req-a')
        _doc(app, 'other', request_code='req-b')
        self.assertEqual(_live(app, 'other').count(), 3)

    def test_a_different_member_or_application_is_its_own_slot(self):
        app, other_app = _app(), _app()
        _doc(app, 'parent_ic', member='father')
        _doc(app, 'parent_ic', member='mother')
        _doc(other_app, 'parent_ic', member='father')
        self.assertEqual(ApplicantDocument.objects.filter(doc_type='parent_ic').count(), 3)

    def test_in_programme_slips_are_left_out_by_design(self):
        """`results_review.record_slip` keeps one live slip per semester — never replaced."""
        app = _app()
        self.assertEqual(SLIP_REQUEST_CODE, 'in_programme')     # the carve-out names this code
        for _ in range(3):
            _doc(app, 'semester_result', request_code=SLIP_REQUEST_CODE)
        self.assertEqual(_live(app, 'semester_result').count(), 3)

    def test_unstaging_into_an_occupied_slot_is_refused(self):
        app = _app()
        live = _doc(app, 'ic')
        staged = _doc(app, 'ic', superseded_at=timezone.now(), superseded_by=live)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ApplicantDocument.objects.filter(id=staged.id).update(superseded_at=None, superseded_by=None)


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestUploadDoor(TestCase):
    """The upload door (`DocumentListCreateView.post`): supersede first, and a clash is an answer."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='td115', name='B40', year=2026)
        cls.student = make_student(supabase_user_id=USER, nric='030101-14-1234')
        cls.app = make_application('shortlisted', cohort=cls.cohort, student=cls.student)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(USER)}')

    def _post(self, doc_type, name):
        return self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': doc_type, 'storage_path': _key(self.app, doc_type, name),
            'original_filename': f'{name}.pdf', 'size': 1000}, format='json')

    def _racing_create(self, clashes):
        """Wrap `create` so a rival upload lands in the same slot just before this one's row is
        written — the real index then refuses this one, as a concurrent request would meet it."""
        orig = ApplicantDocument.objects.create
        calls = {'n': 0}

        def racing(**kw):
            calls['n'] += 1
            if calls['n'] <= clashes and kw.get('superseded_at') is None:
                orig(application=kw['application'], doc_type=kw['doc_type'],
                     household_member=kw.get('household_member', ''),
                     request_code=kw.get('request_code', ''), storage_path=f'rival-{calls["n"]}')
            return orig(**kw)
        return patch.object(ApplicantDocument.objects, 'create', side_effect=racing)

    def test_replace_first_reupload_supersedes_before_it_inserts(self):
        """bank_statement is a bypass (replace-first) type: the old copy leaves the slot first."""
        old = _doc(self.app, 'bank_statement', storage_path=_key(self.app, 'bank_statement', 'old'))
        resp = self._post('bank_statement', 'new')
        self.assertEqual(resp.status_code, 201)
        live = _live(self.app, 'bank_statement')
        self.assertEqual(live.count(), 1)
        old.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)
        self.assertEqual(old.superseded_by_id, live.get().id)

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.promotion.should_promote', return_value=True)
    def test_staged_reupload_is_created_staged_then_promoted(self, _promote, _vision):
        old = _doc(self.app, 'ic', storage_path=_key(self.app, 'ic', 'old'))
        resp = self._post('ic', 'new')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.json()['kept_previous'])
        live = _live(self.app, 'ic').get()
        self.assertEqual(live.storage_path, _key(self.app, 'ic', 'new'))
        old.refresh_from_db()
        self.assertEqual(old.superseded_by_id, live.id)

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.promotion.should_promote', return_value=False)
    def test_staged_reupload_that_loses_never_goes_live(self, _promote, _vision):
        old = _doc(self.app, 'ic', storage_path=_key(self.app, 'ic', 'old'))
        resp = self._post('ic', 'worse')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['kept_previous'])
        self.assertEqual(_live(self.app, 'ic').get().id, old.id)

    def test_a_concurrent_upload_into_the_slot_is_retried_once(self):
        _doc(self.app, 'bank_statement', storage_path=_key(self.app, 'bank_statement', 'old'))
        with self._racing_create(clashes=1):
            resp = self._post('bank_statement', 'mine')
        self.assertEqual(resp.status_code, 201)
        live = _live(self.app, 'bank_statement')
        self.assertEqual(live.count(), 1)
        self.assertEqual(live.get().storage_path, _key(self.app, 'bank_statement', 'mine'))

    def test_a_second_clash_answers_409_not_500_and_keeps_the_old_copy(self):
        old = _doc(self.app, 'bank_statement', storage_path=_key(self.app, 'bank_statement', 'old'))
        with self._racing_create(clashes=2):
            resp = self._post('bank_statement', 'mine')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['code'], 'upload_conflict')
        live = _live(self.app, 'bank_statement')
        self.assertEqual(list(live.values_list('id', flat=True)), [old.id])   # untouched, still live
        self.assertFalse(ApplicantDocument.objects.filter(
            storage_path=_key(self.app, 'bank_statement', 'mine')).exists())

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.promotion.should_promote', return_value=True)
    def test_a_clash_at_promote_keeps_the_new_copy_in_replaced(self, _promote, _vision):
        """A rival goes live in the slot between this upload's supersede and its unstage: the
        index refuses the unstage, the transaction rolls back whole, the upload answers 201 with
        kept_previous — the slot's live copy is untouched and the new copy waits in Old / Replaced."""
        old = _doc(self.app, 'ic', storage_path=_key(self.app, 'ic', 'old'))
        orig_update = QuerySet.update

        def racing_update(qs, **kw):
            if kw == {'superseded_at': None, 'superseded_by': None} and qs.model is ApplicantDocument:
                d = qs.get()
                ApplicantDocument.objects.create(
                    application=d.application, doc_type=d.doc_type, household_member=d.household_member,
                    request_code=d.request_code, storage_path='rival')
            return orig_update(qs, **kw)

        with patch.object(QuerySet, 'update', racing_update):
            resp = self._post('ic', 'new')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['kept_previous'])
        self.assertEqual(list(_live(self.app, 'ic').values_list('id', flat=True)), [old.id])
        new = ApplicantDocument.objects.get(storage_path=_key(self.app, 'ic', 'new'))
        self.assertIsNotNone(new.superseded_at)


class TestRefileIntoAnOccupiedSlot(TestCase):
    """refile_to_spm / refile_to_higher used to save the moved doc into its new slot while it was
    still live, and only then supersede — with the index, a collision with the slot's live copy."""

    def test_refile_to_spm_beside_a_live_slip(self):
        app = _app()
        slip = _doc(app, 'results_slip')
        moved = _doc(app, 'higher_results', results_kind='stpm')
        results_route.refile_to_spm(app, moved)
        self.assertEqual(_live(app, 'results_slip').count(), 1)
        self.assertEqual(_live(app, 'higher_results').count(), 0)
        slip.refresh_from_db()
        moved.refresh_from_db()
        self.assertEqual(moved.doc_type, 'results_slip')
        loser = moved if moved.superseded_at else slip
        self.assertIsNotNone(loser.superseded_by_id)

    def test_refile_to_spm_promote_supersedes_the_live_slip(self):
        app = _app()
        slip = _doc(app, 'results_slip')
        moved = _doc(app, 'higher_results', results_kind='stpm')
        with patch('apps.scholarship.promotion.should_promote', return_value=True):
            results_route.refile_to_spm(app, moved)
        slip.refresh_from_db()
        self.assertEqual(_live(app, 'results_slip').get().id, moved.id)
        self.assertEqual(slip.superseded_by_id, moved.id)

    def test_refile_to_spm_keep_saves_the_moved_doc_already_superseded(self):
        app = _app()
        slip = _doc(app, 'results_slip')
        moved = _doc(app, 'higher_results', results_kind='stpm')
        with patch('apps.scholarship.promotion.should_promote', return_value=False):
            results_route.refile_to_spm(app, moved)
        moved.refresh_from_db()
        self.assertEqual(_live(app, 'results_slip').get().id, slip.id)
        self.assertEqual((moved.doc_type, moved.superseded_by_id), ('results_slip', slip.id))

    def _refile_to_higher(self, promote):
        app = _app()
        higher = _doc(app, 'higher_results', results_kind='stpm')
        moved = _doc(app, 'results_slip')
        with patch('apps.scholarship.promotion.should_promote', return_value=promote):
            results_route.refile_to_higher(app, moved, 'stpm')
        self.assertEqual(_live(app, 'results_slip').count(), 0)
        return _live(app, 'higher_results'), higher, moved

    def test_refile_to_higher_promote_beside_a_live_higher_upload(self):
        live, higher, moved = self._refile_to_higher(promote=True)
        self.assertEqual(live.get().id, moved.id)
        higher.refresh_from_db()
        self.assertEqual(higher.superseded_by_id, moved.id)

    def test_refile_to_higher_keep_beside_a_live_higher_upload(self):
        live, higher, moved = self._refile_to_higher(promote=False)
        self.assertEqual(live.get().id, higher.id)
        moved.refresh_from_db()
        self.assertEqual((moved.doc_type, moved.superseded_by_id), ('higher_results', higher.id))


class TestStrDedupeInheritsMemberAfterSupersede(TestCase):
    def test_blank_keep_inherits_a_losers_member_without_a_collision(self):
        """The kept STR is blank-tagged; the loser names the recipient ('mother') in the slot the
        keep inherits. The loser must leave the slot BEFORE the keep is re-tagged into it."""
        app = _app()
        loser = _doc(app, 'str', member='mother')
        keep = _doc(app, 'str')                    # ties on rank -> the later id keeps the slot
        ids = dedupe_income_proof(app, '', 'str')
        self.assertEqual(ids, [loser.id])
        keep.refresh_from_db()
        loser.refresh_from_db()
        self.assertEqual(keep.household_member, 'mother')
        self.assertIsNone(keep.superseded_at)
        self.assertEqual(loser.superseded_by_id, keep.id)
        self.assertEqual(_live(app, 'str').count(), 1)


class TestSplitPartInTheOriginalsOwnCard(SplitCase):
    def test_the_part_in_the_originals_slot_goes_live_and_the_original_is_history(self):
        app = self._app()
        doc = self._combined(app)
        self._run([self._split(app, doc, [{'pages': [1], 'slot': 'results_slip'},
                                          {'pages': [2, 3], 'slot': 'higher_results', 'kind': 'stpm'}])],
                  '--apply')
        doc.refresh_from_db()
        part = _live(app, 'results_slip').get()
        self.assertNotEqual(part.id, doc.id)
        self.assertIsNotNone(doc.superseded_at)
        self.assertEqual(doc.superseded_by_id, part.id)


class TestBackfillTagIntoAnOccupiedSlot(TestCase):
    """backfill_untagged_income_docs tagged the blank doc into the member's slot while the member's
    live copy was still there, and only then settled the pair."""

    def _app(self):
        return _app(income_route='str', income_earner='father', profile_completed_at=timezone.now())

    def _run(self):
        out = StringIO()
        call_command('backfill_untagged_income_docs', '--apply', stdout=out)
        return out.getvalue()

    def test_blank_doc_that_wins_supersedes_the_members_copy_first(self):
        app = self._app()
        tagged = _doc(app, 'salary_slip', member='father')
        blank = _doc(app, 'salary_slip')           # ties on rank -> the later id wins
        self._run()
        blank.refresh_from_db()
        tagged.refresh_from_db()
        self.assertEqual(blank.household_member, 'father')
        self.assertIsNone(blank.superseded_at)
        self.assertEqual(tagged.superseded_by_id, blank.id)

    def test_blank_doc_that_loses_is_superseded_before_it_is_tagged(self):
        app = self._app()
        genuine = _doc(app, 'salary_slip', member='father',
                       vision_fields={'authenticity': {'status': 'genuine'}, 'fields': {}})
        blank = _doc(app, 'salary_slip',               # a later id, but NOT genuine -> it loses
                     vision_fields={'authenticity': {'status': 'not_salary'}, 'fields': {}})
        self._run()
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, 'father')
        self.assertEqual(blank.superseded_by_id, genuine.id)
        self.assertEqual(_live(app, 'salary_slip').get().id, genuine.id)

    def test_parent_ic_pair_is_settled_without_a_collision(self):
        app = self._app()
        _doc(app, 'parent_ic', member='father')
        blank = _doc(app, 'parent_ic')
        self._run()
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, 'father')
        self.assertEqual(_live(app, 'parent_ic').count(), 1)

    def test_a_slot_clash_mid_run_skips_that_doc_instead_of_crashing(self):
        app = self._app()
        blank = _doc(app, 'salary_slip')
        with patch('apps.scholarship.management.commands.backfill_untagged_income_docs.'
                   'dedupe_income_proof', side_effect=IntegrityError('slot taken')):
            out = self._run()
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, '')                 # rolled back, untouched
        self.assertIn('slot changed while this ran', out)
