"""Tests for the document vault + referee endpoints (Sprint 5a)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'doc-user-a'
USER_B = 'doc-user-b'
USER_C = 'doc-user-c'  # has only a rejected application


def _token(uid, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDocumentApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.cohort2 = ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2025)
        cls.profile_a = StudentProfile.objects.create(supabase_user_id=USER_A, nric='030101-14-1234')
        cls.profile_b = StudentProfile.objects.create(supabase_user_id=USER_B, nric='040101-14-5678')
        cls.profile_c = StudentProfile.objects.create(supabase_user_id=USER_C, nric='050101-14-9999')
        cls.app_a = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile_a, status='shortlisted')
        cls.app_b = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile_b, status='shortlisted')
        cls.rejected_c = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile_c, status='rejected')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/upload')
    def test_sign_upload(self, _mock):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['upload_url'], 'https://signed.example/upload')
        self.assertTrue(resp.json()['storage_path'].startswith(f'{self.app_a.id}/ic/'))

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value=None)
    def test_sign_upload_unavailable_503(self, _mock):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'}, format='json')
        self.assertEqual(resp.status_code, 503)

    def test_sign_upload_no_shortlisted_403(self):
        self._auth(USER_C)
        resp = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'}, format='json')
        self.assertEqual(resp.status_code, 403)

    @patch('apps.scholarship.storage.object_exists', return_value=False)
    def test_create_rejects_when_blob_confirmed_missing(self, _mock):
        """If the file never landed in Storage (confirmed missing), the row is NOT created —
        no orphan record with a dead view link (app #80 EPF, 2026-06-27)."""
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'epf',
            'storage_path': f'{self.app_a.id}/epf/ghost',
            'original_filename': 'SUMATHY.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get('code'), 'upload_incomplete')
        self.assertEqual(
            ApplicantDocument.objects.filter(application=self.app_a, doc_type='epf').count(), 0)

    @patch('apps.scholarship.storage.delete_objects')
    @patch('apps.scholarship.storage.object_exists', return_value=False)
    def test_rejected_upload_keeps_existing_doc(self, _exists, mock_del):
        """A confirmed-missing re-upload must NOT sweep the student's existing good copy."""
        self._auth(USER_A)
        ApplicantDocument.objects.create(application=self.app_a, doc_type='ic',
                                         storage_path=f'{self.app_a.id}/ic/good')
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/ghost',
            'original_filename': 'ic.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        rows = ApplicantDocument.objects.filter(application=self.app_a, doc_type='ic')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().storage_path, f'{self.app_a.id}/ic/good')
        mock_del.assert_not_called()

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    def test_create_and_list_document(self, _mock):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'results_slip',
            'storage_path': f'{self.app_a.id}/results_slip/abc',
            'original_filename': 'results.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp2 = self.client.get('/api/v1/scholarship/documents/')
        self.assertEqual(resp2.status_code, 200)
        docs = resp2.json()['documents']
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['doc_type'], 'results_slip')
        self.assertEqual(docs[0]['download_url'], 'https://signed.example/dl')

    def test_delete_own_document(self):
        doc = ApplicantDocument.objects.create(application=self.app_a, doc_type='ic', storage_path='x')
        self._auth(USER_A)
        resp = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_single_instance_doctype_replaces_on_reupload(self, mock_storage_delete, _mock_vision):
        """Post-S14 + Phase 2 (version history): uploading a new IC SUPERSEDES the old ones
        (rows + blobs RETAINED as history) — a live read sees only the new one."""
        # Existing IC + an unrelated income-proof doc (multi-instance, must NOT be touched).
        old_ic = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='ic',
            storage_path=f'{self.app_a.id}/ic/old-1',
        )
        old_ic_2 = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='ic',
            storage_path=f'{self.app_a.id}/ic/old-2',
        )
        income = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip',
            storage_path=f'{self.app_a.id}/salary_slip/keep-1',
        )

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/new',
            'original_filename': 'NRICF.jpeg', 'size': 200_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        # Only the new IC is LIVE; the old ICs are retained but superseded; income untouched.
        live_ic = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='ic', superseded_at__isnull=True)
        self.assertEqual(live_ic.count(), 1)
        self.assertEqual(live_ic.first().storage_path, f'{self.app_a.id}/ic/new')
        new_id = live_ic.first().id
        for old in (old_ic, old_ic_2):
            old.refresh_from_db()
            self.assertIsNotNone(old.superseded_at)       # retained, not deleted
            self.assertEqual(old.superseded_by_id, new_id)
        self.assertTrue(ApplicantDocument.objects.filter(id=income.id).exists())

        # Phase 2: the stale blobs are RETAINED as version history — no Storage sweep.
        mock_storage_delete.assert_not_called()

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_student_get_excludes_superseded_after_replace(self, _del, _dl, _vis):
        """Phase 2: the student's documents listing shows only the LIVE copy after a re-upload —
        a superseded (replaced) doc is version history for the officer view, never shown back."""
        ApplicantDocument.objects.create(
            application=self.app_a, doc_type='ic', storage_path=f'{self.app_a.id}/ic/old')
        self._auth(USER_A)
        self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic', 'storage_path': f'{self.app_a.id}/ic/new',
            'original_filename': 'ic.jpg', 'size': 1000,
        }, format='json')
        docs = self.client.get('/api/v1/scholarship/documents/').json()['documents']
        ic_docs = [d for d in docs if d['doc_type'] == 'ic']
        self.assertEqual(len(ic_docs), 1)                                       # only the live one
        self.assertTrue(ic_docs[0]['download_url'])
        # DB still holds both rows (the old one retained as history).
        self.assertEqual(
            ApplicantDocument.objects.filter(application=self.app_a, doc_type='ic').count(), 2)

    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_failed_create_does_not_destroy_existing_document(self, mock_storage_delete):
        """TD audit 2026-06-14 — data-loss guard. If creating the replacement row fails, the
        student's existing document (DB row + Storage blob) must survive untouched. The fix is
        create-first inside a transaction, sweep the stale blob only AFTER it commits — the old
        delete-then-create order could wipe an income slip / IC / STR with no recovery."""
        old_ic = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='ic',
            storage_path=f'{self.app_a.id}/ic/old-keep',
        )
        self._auth(USER_A)
        with patch.object(ApplicantDocument.objects, 'create', side_effect=RuntimeError('db boom')):
            try:
                self.client.post('/api/v1/scholarship/documents/', {
                    'doc_type': 'ic',
                    'storage_path': f'{self.app_a.id}/ic/new',
                    'original_filename': 'NRICF.jpeg', 'size': 200_000,
                }, format='json')
            except RuntimeError:
                pass  # the simulated DB failure may surface as a raised error or a 500
        # The existing IC row survives, no duplicate was made, and NO storage blob was swept.
        self.assertTrue(ApplicantDocument.objects.filter(id=old_ic.id).exists())
        self.assertEqual(
            ApplicantDocument.objects.filter(application=self.app_a, doc_type='ic').count(), 1)
        mock_storage_delete.assert_not_called()

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_every_doctype_replaces_on_reupload(self, mock_storage_delete, _mock_vision):
        """Every document is single-instance now (user's call, 2026-06-05) — a re-upload
        of an UNTAGGED salary slip replaces the prior copy in the same slot."""
        first = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip',
            storage_path=f'{self.app_a.id}/salary_slip/jan',
        )
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'salary_slip',
            'storage_path': f'{self.app_a.id}/salary_slip/feb',
            'original_filename': 'feb.pdf', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        rows = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='salary_slip', household_member='',
            superseded_at__isnull=True,
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().storage_path, f'{self.app_a.id}/salary_slip/feb')
        first.refresh_from_db()
        self.assertIsNotNone(first.superseded_at)      # Phase 2: retained as history
        # Phase 2: the stale blob is RETAINED — no Storage sweep.
        mock_storage_delete.assert_not_called()

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_member_tagged_income_doc_is_single_instance_per_member(self, mock_del, _mv):
        """Salary route: a member-tagged salary slip replaces THAT member's prior copy
        (single-instance per (doc_type, member)) — never another member's."""
        fathers = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip', household_member='father',
            storage_path=f'{self.app_a.id}/salary_slip/father-old')
        mothers = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip', household_member='mother',
            storage_path=f'{self.app_a.id}/salary_slip/mother-keep')
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'salary_slip', 'household_member': 'father',
            'storage_path': f'{self.app_a.id}/salary_slip/father-new',
            'original_filename': 'f.pdf', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        father_rows = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='salary_slip', household_member='father',
            superseded_at__isnull=True)
        self.assertEqual(father_rows.count(), 1)
        self.assertEqual(father_rows.first().storage_path, f'{self.app_a.id}/salary_slip/father-new')
        fathers.refresh_from_db()
        self.assertIsNotNone(fathers.superseded_at)     # father's old slip retained (superseded)
        mothers.refresh_from_db()
        self.assertIsNone(mothers.superseded_at)        # mother's untouched (still live)

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_blank_member_parent_ic_does_not_sweep_member_tagged(self, mock_del, _mv):
        """An untagged parent_ic (STR route / minor consent) must NOT sweep the
        salary-route member-tagged parent_ics — the sweep is (doc_type, member)-scoped."""
        father_ic = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='parent_ic', household_member='father',
            storage_path=f'{self.app_a.id}/parent_ic/father')
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic',  # no household_member → blank
            'storage_path': f'{self.app_a.id}/parent_ic/str-earner',
            'original_filename': 'ic.jpg', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(ApplicantDocument.objects.filter(id=father_ic.id).exists())
        self.assertEqual(ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='parent_ic').count(), 2)

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_str_route_income_doc_auto_tagged_to_earner_and_supersedes_legacy_blank(self, mock_del, _mv):
        """Slot model (TD-115) + Phase 2: on the STR route the backend authoritatively tags the
        earner's income docs, and a re-upload SUPERSEDES the legacy UNTAGGED copy (retained as
        history, no live duplicate) — even when the client sends no household_member."""
        self.app_a.income_route = 'str'
        self.app_a.income_earner = 'mother'
        self.app_a.save(update_fields=['income_route', 'income_earner'])
        ApplicantDocument.objects.create(
            application=self.app_a, doc_type='parent_ic', household_member='',
            storage_path=f'{self.app_a.id}/parent_ic/legacy-blank')
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic',  # client sends NO member
            'storage_path': f'{self.app_a.id}/parent_ic/new',
            'original_filename': 'ic.png', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ics = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='parent_ic', superseded_at__isnull=True)
        self.assertEqual(ics.count(), 1)                          # legacy blank superseded, no live dup
        self.assertEqual(ics.first().household_member, 'mother')  # auto-tagged to the earner

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_blank_income_doc_auto_tagged_by_name_on_upload(self, mock_vision, _dl):
        """Backend tag guard (airtight last line): a salary-route income doc uploaded with NO member
        is attributed to the household member by the NAME Vision reads off it — a blank-tagged income
        doc is never persisted where the person is determinable."""
        self.app_a.income_route = 'salary'
        self.app_a.father_name = 'RAVI A/L PERIAKARUPPAN'
        self.app_a.save(update_fields=['income_route', 'father_name'])

        def _read(doc):
            from django.utils import timezone as _tz
            doc.vision_name = 'RAVI A/L PERIAKARUPPAN'
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_name', 'vision_run_at'])
        mock_vision.side_effect = _read

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic',                       # NO household_member sent
            'storage_path': f'{self.app_a.id}/parent_ic/blank',
            'original_filename': 'ic.jpg', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = ApplicantDocument.objects.get(id=resp.json()['id'])
        self.assertEqual(doc.household_member, 'father')   # auto-tagged from the name on the card

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_name_derived_upload_supersedes_prior_slot(self, mock_vision, _dl):
        """The guard also REPLACES: a name-derived income doc supersedes the prior live copy in that
        person's slot, so a memberless re-upload (e.g. answering income_doc_stale) doesn't duplicate."""
        self.app_a.income_route = 'salary'
        self.app_a.father_name = 'RAVI A/L PERIAKARUPPAN'
        self.app_a.save(update_fields=['income_route', 'father_name'])
        old = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='parent_ic', household_member='father',
            storage_path=f'{self.app_a.id}/parent_ic/old')

        def _read(doc):
            from django.utils import timezone as _tz
            doc.vision_name = 'RAVI A/L PERIAKARUPPAN'
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_name', 'vision_run_at'])
        mock_vision.side_effect = _read

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic',                       # blank member → derived to father
            'storage_path': f'{self.app_a.id}/parent_ic/new',
            'original_filename': 'ic.jpg', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        old.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)            # prior father IC replaced (retained)
        live = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='parent_ic', household_member='father',
            superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)
        self.assertEqual(live.first().id, resp.json()['id'])

    @patch('apps.scholarship.vision.run_field_extraction_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_str_route_force_tag_only_pre_consent(self, _del, _ext):
        """The STR-route force-tag-to-earner applies ONLY pre-consent. Post-consent (profile
        completed) we collect every working member, so a father's payslip on a mother-STR household
        keeps its 'father' tag instead of being force-tagged to the mother (#80's root cause)."""
        from django.utils import timezone
        self.app_a.income_route = 'str'
        self.app_a.income_earner = 'mother'
        self.app_a.profile_completed_at = timezone.now()          # consent given → post-consent
        self.app_a.save(update_fields=['income_route', 'income_earner', 'profile_completed_at'])
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'salary_slip', 'household_member': 'father',
            'storage_path': f'{self.app_a.id}/salary_slip/father',
            'original_filename': 'f.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = ApplicantDocument.objects.get(id=resp.json()['id'])
        self.assertEqual(doc.household_member, 'father')          # NOT force-tagged to the STR earner

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_post_consent_tag_corrected_when_name_contradicts(self, mock_vision, _dl):
        """(3a) The tag guard CORRECTS, not just fills: a post-consent income doc whose read name
        contradicts its tag (the #80/#112 class — a father's doc stamped onto the mother) is
        re-attributed to the person the name points to, and supersedes the prior copy in that slot."""
        from django.utils import timezone
        self.app_a.income_route = 'str'
        self.app_a.income_earner = 'mother'
        self.app_a.father_name = 'RAVI A/L PERIAKARUPPAN'
        self.app_a.mother_name = 'SELVI A/P VELLAYAN'
        self.app_a.profile_completed_at = timezone.now()          # post-consent → no force-tag
        self.app_a.save(update_fields=['income_route', 'income_earner', 'father_name',
                                       'mother_name', 'profile_completed_at'])
        old_father = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='parent_ic', household_member='father',
            storage_path=f'{self.app_a.id}/parent_ic/old_f')

        def _read(doc):
            from django.utils import timezone as _tz
            doc.vision_name = 'RAVI A/L PERIAKARUPPAN'             # the FATHER, though tagged mother
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_name', 'vision_run_at'])
        mock_vision.side_effect = _read

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic', 'household_member': 'mother',   # WRONG tag
            'storage_path': f'{self.app_a.id}/parent_ic/mis',
            'original_filename': 'ic.jpg', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = ApplicantDocument.objects.get(id=resp.json()['id'])
        self.assertEqual(doc.household_member, 'father')            # corrected to the name on the doc
        old_father.refresh_from_db()
        self.assertIsNotNone(old_father.superseded_at)             # prior father slot replaced (retained)

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_tag_not_corrected_when_name_matches_tag(self, mock_vision, _dl):
        """Guard is a no-op when the name agrees with the tag — the correct tag is never disturbed."""
        from django.utils import timezone
        self.app_a.father_name = 'RAVI A/L PERIAKARUPPAN'
        self.app_a.mother_name = 'SELVI A/P VELLAYAN'
        self.app_a.profile_completed_at = timezone.now()
        self.app_a.save(update_fields=['father_name', 'mother_name', 'profile_completed_at'])

        def _read(doc):
            from django.utils import timezone as _tz
            doc.vision_name = 'SELVI A/P VELLAYAN'                  # matches the 'mother' tag
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_name', 'vision_run_at'])
        mock_vision.side_effect = _read

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic', 'household_member': 'mother',
            'storage_path': f'{self.app_a.id}/parent_ic/ok',
            'original_filename': 'ic.jpg', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = ApplicantDocument.objects.get(id=resp.json()['id'])
        self.assertEqual(doc.household_member, 'mother')           # unchanged

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_tag_not_corrected_when_name_matches_nobody(self, mock_vision, _dl):
        """Strictness guard (app 66 class: roster fields hold NRICs, not names): a name that matches
        NO roster member never overrides an existing tag — the request/earner-set tag stands."""
        from django.utils import timezone
        self.app_a.father_name = '750819145383'                    # NRIC in the name field
        self.app_a.mother_name = '810122105834'
        self.app_a.profile_completed_at = timezone.now()
        self.app_a.save(update_fields=['father_name', 'mother_name', 'profile_completed_at'])

        def _read(doc):
            from django.utils import timezone as _tz
            doc.vision_name = 'JAYAKUMAR A/L ANNAMARI'             # matches neither NRIC 'name'
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_name', 'vision_run_at'])
        mock_vision.side_effect = _read

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic', 'household_member': 'father',
            'storage_path': f'{self.app_a.id}/parent_ic/nric',
            'original_filename': 'ic.jpg', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = ApplicantDocument.objects.get(id=resp.json()['id'])
        self.assertEqual(doc.household_member, 'father')           # tag stands (no unambiguous match)

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    def test_dedupe_keeps_newest_salary_slip_supersedes_older(self, _dl):
        """One-live-copy dedup: a person's salary slips collapse to the newest pay month; older /
        undated copies drop to Old/Replaced (retained). Runs across request_codes."""
        from apps.scholarship.income_engine import dedupe_income_proof

        def slip(rc, period):
            d = ApplicantDocument.objects.create(
                application=self.app_a, doc_type='salary_slip', household_member='father',
                request_code=rc, storage_path=f'{self.app_a.id}/salary_slip/{rc or "a"}{period}')
            d.vision_fields = {'fields': {'period': period}}
            d.save(update_fields=['vision_fields'])
            return d
        may1 = slip('', 'May 2026')
        may2 = slip('officer_10', 'MAY 2026')          # same month, different request → parallel slot
        apr = slip('officer_11', 'Apr 2026')           # older month
        blank = slip('officer_9', '')                  # unread period

        superseded = dedupe_income_proof(self.app_a, 'father', 'salary_slip')
        live = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='salary_slip', superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)              # only one live copy remains
        self.assertEqual(live.first().id, may2.id)     # newest month, latest upload (highest id)
        self.assertCountEqual(superseded, [may1.id, apr.id, blank.id])
        for d in (may1, apr, blank):
            d.refresh_from_db()
            self.assertEqual(d.superseded_by_id, may2.id)   # retained, pointed at the keeper

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    def test_dedupe_str_prefers_the_dated_screenshot(self, _dl):
        """STR dedup: the dated screenshot (a shown year) is kept; older undated copies → Old/Replaced."""
        from apps.scholarship.income_engine import dedupe_income_proof

        def str_doc(rc, year):
            d = ApplicantDocument.objects.create(
                application=self.app_a, doc_type='str', household_member='mother',
                request_code=rc, storage_path=f'{self.app_a.id}/str/{rc or "a"}{year or "x"}')
            d.vision_fields = {'fields': {'year': year, 'status': 'Lulus'}}
            d.save(update_fields=['vision_fields'])
            return d
        undated1 = str_doc('', '')
        dated = str_doc('officer_2', '2026')
        undated2 = str_doc('officer_3', '')

        superseded = dedupe_income_proof(self.app_a, 'mother', 'str')
        live = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='str', superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)
        self.assertEqual(live.first().id, dated.id)    # the dated one is kept
        self.assertCountEqual(superseded, [undated1.id, undated2.id])

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    def test_dedupe_keeps_genuine_over_a_newer_non_genuine_copy(self, _dl):
        """Genuineness ranks first: a genuine STR is NEVER superseded by a newer non-genuine copy
        (a SARA letter / wrong-type in the STR slot) — we keep the real document."""
        from apps.scholarship.income_engine import dedupe_income_proof
        genuine = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='str', household_member='mother',
            storage_path=f'{self.app_a.id}/str/genuine')
        genuine.vision_fields = {'fields': {'year': '2025'}, 'authenticity': {'status': 'genuine'}}
        genuine.save(update_fields=['vision_fields'])
        sara = ApplicantDocument.objects.create(                 # newer id, but not genuine
            application=self.app_a, doc_type='str', household_member='mother', request_code='officer_4',
            storage_path=f'{self.app_a.id}/str/sara')
        sara.vision_fields = {'fields': {'year': '2026'}, 'authenticity': {'status': 'suspect'}}
        sara.save(update_fields=['vision_fields'])

        superseded = dedupe_income_proof(self.app_a, 'mother', 'str')
        self.assertEqual(superseded, [sara.id])                  # the SARA drops, the genuine STR stays
        live = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='str', superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)
        self.assertEqual(live.first().id, genuine.id)

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    def test_dedupe_epf_keeps_genuine_over_wrong_type(self, _dl):
        """EPF dedups too (#80): a genuine EPF statement is kept; a payslip-misfiled-as-EPF
        (not_epf) drops to Old/Replaced, regardless of upload order."""
        from apps.scholarship.income_engine import dedupe_income_proof
        wrong = ApplicantDocument.objects.create(              # newer id, but wrong type
            application=self.app_a, doc_type='epf', household_member='mother',
            storage_path=f'{self.app_a.id}/epf/wrong')
        wrong.vision_fields = {'fields': {'statement_date': 'Jun 2026'},
                               'authenticity': {'status': 'not_epf'}}
        wrong.save(update_fields=['vision_fields'])
        genuine = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='epf', household_member='mother', request_code='officer_2',
            storage_path=f'{self.app_a.id}/epf/genuine')
        genuine.vision_fields = {'fields': {'statement_date': 'Jan 2026'},
                                 'authenticity': {'status': 'genuine'}}
        genuine.save(update_fields=['vision_fields'])

        superseded = dedupe_income_proof(self.app_a, 'mother', 'epf')
        self.assertEqual(superseded, [wrong.id])               # the wrong-type EPF drops
        live = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='epf', superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)
        self.assertEqual(live.first().id, genuine.id)          # genuine kept despite older date/id

    def test_dedupe_noop_for_single_or_non_dedup_type(self):
        from apps.scholarship.income_engine import dedupe_income_proof
        one = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip', household_member='father', storage_path='x')
        one.vision_fields = {'fields': {'period': 'May 2026'}}
        one.save(update_fields=['vision_fields'])
        self.assertEqual(dedupe_income_proof(self.app_a, 'father', 'salary_slip'), [])   # single → no-op
        # a non-dedupable type is never touched even with duplicates
        ApplicantDocument.objects.create(application=self.app_a, doc_type='parent_ic',
                                         household_member='father', storage_path='y')
        ApplicantDocument.objects.create(application=self.app_a, doc_type='parent_ic',
                                         household_member='father', storage_path='z')
        self.assertEqual(dedupe_income_proof(self.app_a, 'father', 'parent_ic'), [])

    def test_semester_check_name_nric_cgpa(self):
        """A semester-result slip reads Name + NRIC (matched vs the student) + CGPA."""
        from apps.scholarship.academic_engine import semester_check
        self.profile_a.name = 'PRIYA A/P KUMAR'
        self.profile_a.save(update_fields=['name'])
        doc = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='semester_result', storage_path='sem-x')
        doc.vision_fields = {'student_verdict': 'ok', 'fields': {
            'name': 'PRIYA A/P KUMAR', 'nric': '030101-14-1234', 'cgpa': '3.50'}}
        doc.save(update_fields=['vision_fields'])
        c = semester_check(doc)
        self.assertEqual(c['name_status'], 'match')
        self.assertEqual(c['nric_status'], 'match')
        self.assertEqual(c['cgpa'], '3.50')

        # a semester-only slip: different name, no NRIC, no cumulative CGPA
        doc2 = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='semester_result', storage_path='sem-y')
        doc2.vision_fields = {'student_verdict': 'ok', 'fields': {
            'name': 'SOMEONE ELSE BINTI OTHER', 'nric': '', 'cgpa': ''}}
        doc2.save(update_fields=['vision_fields'])
        c2 = semester_check(doc2)
        self.assertEqual(c2['name_status'], 'mismatch')
        self.assertEqual(c2['nric_status'], 'no_ref')     # no NRIC on the slip → grey/red in FE
        self.assertEqual(c2['cgpa'], '')

        # unread slip → None (the row shows "Unread", not all-red)
        doc3 = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='semester_result', storage_path='sem-z')
        self.assertIsNone(semester_check(doc3))

    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_delete_sweeps_storage(self, mock_storage_delete):
        """Explicit DELETE on a doc also sweeps its Storage blob."""
        doc = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='water_bill',
            storage_path=f'{self.app_a.id}/water_bill/abc',
        )
        self._auth(USER_A)
        resp = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())
        mock_storage_delete.assert_called_once_with([f'{self.app_a.id}/water_bill/abc'])

    def test_delete_cross_user_404(self):
        doc = ApplicantDocument.objects.create(application=self.app_b, doc_type='ic', storage_path='x')
        self._auth(USER_A)
        resp = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_referee_create_and_list(self):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/referees/', {
            'name': 'Mr Teacher', 'role': 'teacher', 'phone': '012-3456789',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp2 = self.client.get('/api/v1/scholarship/referees/')
        self.assertEqual(len(resp2.json()['referees']), 1)
        self.assertEqual(resp2.json()['referees'][0]['name'], 'Mr Teacher')

    @override_settings(SUPABASE_URL='', SUPABASE_SERVICE_ROLE_KEY='')
    def test_storage_returns_none_when_unconfigured(self):
        from apps.scholarship.storage import create_signed_download_url, create_signed_upload_url
        self.assertIsNone(create_signed_upload_url('x/y/z'))
        self.assertIsNone(create_signed_download_url('x/y/z'))

    def test_documents_require_auth(self):
        resp = self.client.get('/api/v1/scholarship/documents/')
        self.assertEqual(resp.status_code, 401)

    # ── S4: new doc types ────────────────────────────────────────────────
    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/upload')
    def test_sign_upload_accepts_salary_slip(self, _mock):
        """salary_slip (new in S4) is a valid doc_type for sign-upload."""
        self._auth(USER_A)
        resp = self.client.post(
            '/api/v1/scholarship/documents/sign-upload/',
            {'doc_type': 'salary_slip'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['doc_type'], 'salary_slip')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    def test_record_document_accepts_new_types(self, _mock):
        """All four S4 doc types can be recorded via the document API."""
        self._auth(USER_A)
        for doc_type in ('salary_slip', 'water_bill', 'electricity_bill', 'offer_letter'):
            resp = self.client.post('/api/v1/scholarship/documents/', {
                'doc_type': doc_type,
                'storage_path': f'{self.app_a.id}/{doc_type}/abc',
                'original_filename': f'{doc_type}.pdf',
                'size': 512,
            }, format='json')
            self.assertEqual(resp.status_code, 201, f'Expected 201 for doc_type={doc_type}, got {resp.status_code}')

    # ── S13: Vision OCR auto-trigger on IC upload ───────────────────────────
    @staticmethod
    def _mock_vision_call(doc):
        """Mimic vision.run_vision_for_document side effect (writes to the row)."""
        from django.utils import timezone as _tz
        doc.vision_nric = '030101-14-1234'
        doc.vision_name = 'PRIYA A/P KRISHNAN'
        doc.vision_run_at = _tz.now()
        doc.vision_error = ''
        doc.save(update_fields=['vision_nric', 'vision_name', 'vision_run_at', 'vision_error'])
        return {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN', 'error': None}

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_ic_upload_auto_runs_vision(self, mock_vision, _dl):
        """Recording an IC document triggers run_vision_for_document; response carries the fields."""
        mock_vision.side_effect = self._mock_vision_call
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/abc',
            'original_filename': 'mykad.jpg', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(mock_vision.called)
        body = resp.json()
        self.assertEqual(body['vision_nric'], '030101-14-1234')
        self.assertEqual(body['vision_name'], 'PRIYA A/P KRISHNAN')
        self.assertEqual(body['vision_error'], '')
        self.assertIsNotNone(body['vision_run_at'])

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_non_ic_upload_does_not_run_vision(self, mock_vision, _dl):
        """Vision is gated on doc_type='ic' — other types must not trigger a call."""
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'results_slip',
            'storage_path': f'{self.app_a.id}/results_slip/abc',
            'original_filename': 'results.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(mock_vision.called)
        self.assertEqual(resp.json()['vision_nric'], '')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.ocr_document')
    def test_statement_of_intent_upload_reads_text(self, mock_ocr, _dl):
        """P1 (Check 2): uploading the letter of intent OCRs its plain text into
        vision_fields['text'] so the submission review can read motivation."""
        mock_ocr.return_value = {'text': 'I have taught my younger cousins for years.', 'error': ''}
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'statement_of_intent',
            'storage_path': f'{self.app_a.id}/statement_of_intent/abc',
            'original_filename': 'letter.pdf', 'size': 2000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(mock_ocr.called)
        from apps.scholarship.models import ApplicantDocument
        doc = ApplicantDocument.objects.get(id=resp.json()['id'])
        self.assertEqual(doc.vision_fields.get('text'), 'I have taught my younger cousins for years.')
        self.assertEqual(doc.vision_fields.get('student_verdict'), 'read')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_ic_upload_survives_vision_failure(self, mock_vision, _dl):
        """If Vision errors, the upload still succeeds; the error is recorded on the row."""
        from django.utils import timezone as _tz

        def boom(doc):
            doc.vision_error = 'AI module not installed'
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_error', 'vision_run_at'])
            return {'nric': '', 'name': '', 'error': 'AI module not installed'}
        mock_vision.side_effect = boom
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/zzz',
            'original_filename': 'mykad.jpg', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)   # upload not blocked
        body = resp.json()
        self.assertEqual(body['vision_nric'], '')
        self.assertEqual(body['vision_error'], 'AI module not installed')


class TestIcGeminiFallbackIntegration(TestCase):
    """#5 — run_vision_for_document escalates a low-confidence MyKad read to the Gemini
    second opinion (cost-gated) and merges it in. Vision + Gemini seams both mocked."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='gx', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id='gemini-ic-user',
                                                    nric='030101-14-1234', name='Priya Krishnan')
        cls.app = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile,
                                                        status='shortlisted')

    def _ic_doc(self):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='ic',
            storage_path=f'{self.app.id}/ic/x', original_filename='mykad.jpg',
            content_type='image/jpeg', size=50_000)

    # A misread last digit (…1239) — OCR disagrees with the typed profile (…1234).
    _MISREAD_OCR = {'text': 'MYKAD\nMALAYSIA\n030101-14-1239\nPRIYA A/P KRISHNAN\nNO 1 JALAN\n50000 KL',
                    'error': None}
    _CLEAN_OCR = {'text': 'MYKAD\nMALAYSIA\n030101-14-1234\nPRIYA A/P KRISHNAN\nNO 1 JALAN\n50000 KL',
                  'error': None}

    @patch('apps.scholarship.vision._call_gemini_json')
    @patch('apps.scholarship.vision._vision_document_text')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_low_confidence_escalates_and_merges(self, _img, mock_ocr, mock_gemini):
        from apps.scholarship.vision import run_vision_for_document
        mock_ocr.return_value = self._MISREAD_OCR
        mock_gemini.return_value = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN',
                                    'address': 'NO 1, JALAN BERSIH, 50000 KL'}
        doc = self._ic_doc()
        result = run_vision_for_document(doc)
        self.assertTrue(mock_gemini.called)                 # escalated
        self.assertEqual(result['nric'], '030101-14-1234')  # gemini recovered the digit
        doc.refresh_from_db()
        self.assertEqual(doc.vision_nric, '030101-14-1234')
        self.assertEqual(doc.vision_address, 'NO 1, JALAN BERSIH, 50000 KL')

    @patch('apps.scholarship.vision._call_gemini_json')
    @patch('apps.scholarship.vision._vision_document_text')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_clean_read_does_not_call_gemini(self, _img, mock_ocr, mock_gemini):
        from apps.scholarship.vision import run_vision_for_document
        mock_ocr.return_value = self._CLEAN_OCR
        run_vision_for_document(self._ic_doc())
        mock_gemini.assert_not_called()                     # stayed free

    @override_settings(IC_GEMINI_FALLBACK_ENABLED=False)
    @patch('apps.scholarship.vision._call_gemini_json')
    @patch('apps.scholarship.vision._vision_document_text')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_knob_off_never_calls_gemini(self, _img, mock_ocr, mock_gemini):
        from apps.scholarship.vision import run_vision_for_document
        mock_ocr.return_value = self._MISREAD_OCR
        run_vision_for_document(self._ic_doc())
        mock_gemini.assert_not_called()


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRequestOwnedSlots(TestCase):
    """A reviewer-requested document lands in its OWN slot, keyed by the officer request
    code (doc_type, household_member, request_code). So multiple 'Other' docs — and a
    cross-person income doc — coexist instead of overwriting each other. Plus the 'other'
    per-application cap. Regression for the live data loss (Theepicaa: 5 requests, 1 stored)."""
    USER = 'ros-user'

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='ros', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=cls.USER, nric='030101-14-2468')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted',
            income_route='str', income_earner='mother')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(self.USER)}')

    def _upload(self, doc_type, suffix, request_code='', household_member=''):
        return self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': doc_type, 'storage_path': f'{self.app.id}/{doc_type}/{suffix}',
            'request_code': request_code, 'household_member': household_member,
            'original_filename': f'{suffix}.jpg', 'size': 1000,
        }, format='json')

    def test_multiple_other_requests_coexist(self):
        self.assertEqual(self._upload('other', 'a', request_code='officer_1').status_code, 201)
        self.assertEqual(self._upload('other', 'b', request_code='officer_2').status_code, 201)
        self.assertEqual(
            ApplicantDocument.objects.filter(application=self.app, doc_type='other').count(), 2)

    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_same_request_replaces(self, _del):
        self._upload('other', 'a', request_code='officer_1')
        self._upload('other', 'b', request_code='officer_1')   # same request → replace, not a 2nd live doc
        rows = ApplicantDocument.objects.filter(
            application=self.app, doc_type='other', superseded_at__isnull=True)
        self.assertEqual(rows.count(), 1)
        self.assertTrue(rows.first().storage_path.endswith('/b'))

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_request_income_doc_does_not_overwrite_str_earner(self, _del, _vis):
        # the student's own STR-route mother IC (no request_code)
        mother_ic = ApplicantDocument.objects.create(
            application=self.app, doc_type='parent_ic', household_member='mother',
            storage_path=f'{self.app.id}/parent_ic/mother')
        # a reviewer asks for the FATHER's IC — must NOT be force-tagged to mother / overwrite hers
        r = self._upload('parent_ic', 'father', request_code='officer_3', household_member='father')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(ApplicantDocument.objects.filter(id=mother_ic.id).exists())   # mother's survives
        self.assertEqual(
            ApplicantDocument.objects.filter(application=self.app, doc_type='parent_ic').count(), 2)
        father = ApplicantDocument.objects.get(
            application=self.app, doc_type='parent_ic', request_code='officer_3')
        self.assertEqual(father.household_member, 'father')   # honoured, NOT forced to 'mother'

    @patch('apps.scholarship.vision.run_field_extraction_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_officer_request_supersedes_apply_form_same_person(self, _del, _ext):
        """An officer-requested re-upload of the same (doc_type, member) SUPERSEDES the student's
        apply-form copy (→ OTHER Old/Replaced), rather than sitting beside it as a parallel slot.
        STR route earner=mother: the apply-form STR is force-tagged to mother; the officer copy
        (request_code) replaces it."""
        self._upload('str', 'apply')                                   # apply-form STR (→ mother)
        apply_form = ApplicantDocument.objects.get(
            application=self.app, doc_type='str', request_code='')
        self._upload('str', 'officer', request_code='officer_2', household_member='mother')
        apply_form.refresh_from_db()
        self.assertIsNotNone(apply_form.superseded_at)                 # replaced, retained as history
        live = ApplicantDocument.objects.filter(
            application=self.app, doc_type='str', superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)                             # only the officer copy is live
        self.assertEqual(live.first().request_code, 'officer_2')

    @override_settings(MAX_OTHER_DOCS=2)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_other_cap(self, _del):
        self.assertEqual(self._upload('other', '1', request_code='officer_1').status_code, 201)
        self.assertEqual(self._upload('other', '2', request_code='officer_2').status_code, 201)
        r = self._upload('other', '3', request_code='officer_3')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'other_doc_limit_reached')
        # re-uploading an EXISTING 'other' slot is a replace, not a new doc → allowed past the cap
        self.assertEqual(self._upload('other', '1b', request_code='officer_1').status_code, 201)

    def test_resolve_targets_one_request_by_code(self):
        from apps.scholarship.resolution import add_officer_item, resolve_doc_items_for_upload
        i1 = add_officer_item(self.app, kind='doc', prompt='Upload A', admin_email='o@x', doc_type='other')
        i2 = add_officer_item(self.app, kind='doc', prompt='Upload B', admin_email='o@x', doc_type='other')
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='other', request_code=i1.code,
            storage_path=f'{self.app.id}/other/a')
        resolve_doc_items_for_upload(self.app, doc)
        i1.refresh_from_db(); i2.refresh_from_db()
        self.assertEqual(i1.status, 'resolved')   # the matching request closes
        self.assertEqual(i2.status, 'open')       # the OTHER request stays open
