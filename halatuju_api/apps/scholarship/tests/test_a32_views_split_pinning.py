"""Audit A3.2 - pinning tests for the split of ``apps/scholarship/views.py`` into a package.

Written BEFORE the split and green before and after it: the split moves code and changes none, so
these say what the student-facing views did and must keep doing.

1. Every route of the scholarship URLconf that was served from ``views`` still resolves to the same
   view class, and the package still exports that very object.
2. The document-record POST (``DocumentListCreateView.post``, the identity / document path): its
   refusals and their ORDER, the STR earner force-tag, the slot sweep, the staged / replace-first
   split, the queue-or-judge hand-off, the higher_results kind, and the 409 on a contested slot.
3. Every name another module imports from ``apps.scholarship.views`` is still importable from it.

No paid call is made: ``upload_read`` (the only thing that reads a document) and storage are mocked.
The personal data is obviously fake.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, URLResolver

from apps.scholarship import urls as scholarship_urls
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.doc_keys import issued_key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'

# route pattern -> view class name, for every route served from the old views.py (8e8c77b19).
PINNED_ROUTES = {
    'internal/cron/<str:job>/': 'CronRunView',
    'internal/vircle/airtable/': 'VircleAirtableUpdateView',
    'scholarship/applications/<int:pk>/confirm/': 'ApplicationConfirmView',
    'scholarship/applications/<int:pk>/graduation-message/': 'GraduationMessageView',
    'scholarship/applications/<int:pk>/income-route/': 'IncomeRouteSwitchView',
    'scholarship/applications/<int:pk>/interview/book/': 'StudentInterviewBookView',
    'scholarship/applications/<int:pk>/interview/cancel/': 'StudentInterviewCancelView',
    'scholarship/applications/<int:pk>/interview/message/': 'StudentInterviewMessageView',
    'scholarship/applications/<int:pk>/interview/request-alternatives/': 'StudentInterviewRequestAlternativesView',
    'scholarship/applications/<int:pk>/interview/': 'StudentInterviewView',
    'scholarship/applications/<int:pk>/onboarding-complete/': 'ApplicationOnboardingCompleteView',
    'scholarship/applications/<int:pk>/promotional-consent/': 'PromotionalConsentView',
    'scholarship/applications/<int:pk>/semester-results/': 'SemesterResultView',
    'scholarship/applications/<int:pk>/': 'ApplicationDetailView',
    'scholarship/applications/': 'ApplicationListCreateView',
    'scholarship/award/comprehension-quiz/': 'StudentComprehensionQuizView',
    'scholarship/award/comprehension/': 'StudentComprehensionView',
    'scholarship/award/guarantor/verify-phone/check/': 'GuarantorPhoneVerifyCheckView',
    'scholarship/award/guarantor/verify-phone/send/': 'GuarantorPhoneVerifyStartView',
    'scholarship/award/': 'StudentAwardView',
    'scholarship/bank-account/': 'BankAccountView',
    'scholarship/bursary-agreement/': 'BursaryAgreementView',
    'scholarship/consent/': 'ConsentView',
    'scholarship/documents/<int:pk>/help/': 'DocumentHelpView',
    'scholarship/documents/<int:pk>/read/': 'DocumentReadView',
    'scholarship/documents/<int:pk>/': 'DocumentDetailView',
    'scholarship/documents/sign-upload/': 'DocumentSignUploadView',
    'scholarship/documents/': 'DocumentListCreateView',
    'scholarship/income/<str:member>/help/': 'IncomeClusterHelpView',
    'scholarship/intake/': 'ScholarshipIntakeView',
    'scholarship/referees/': 'RefereeListCreateView',
    'scholarship/resolution-items/<int:pk>/resolve/': 'ResolutionItemResolveView',
    'scholarship/resolution-items/': 'ResolutionItemListView',
    'scholarship/whatsapp/inbound/': 'WhatsAppInboundView',
}

# Names other modules (urls.py, upload_read, reextract, results_review, tests) import from the package.
EXPORTED_NAMES = [
    'AmbiguousApplication', 'BILL_DOC_TYPES', 'RELATIONSHIP_DOC_TYPES', 'SET_ASIDE_STATES',
    'SUPPORTING_NAME_CHECK_TYPES', 'TEXT_READ_DOC_TYPES', '_ACADEMIC_SINGLE_TYPES',
    '_BYPASS_JUDGE_TYPES', '_FUNDED_STATES', '_collapse_duplicate_docs', '_current_application',
    '_flag_needs_officer_eye', '_is_allowed_upload', '_note_unresolved_attempts',
    '_open_doc_request_items', '_reslot_income_doc', '_stage_attempts_exhausted',
    'consent_blockers', 'is_minor', 'logger',
]


def _flatten(patterns):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _flatten(p.url_patterns)
        elif isinstance(p, URLPattern):
            yield p


class EveryRouteStillResolves(SimpleTestCase):
    def test_every_route_served_from_views_points_at_the_same_class(self):
        import apps.scholarship.views as views
        seen = {}
        for p in _flatten(scholarship_urls.urlpatterns):
            target = getattr(p.callback, 'view_class', p.callback)
            mod = getattr(target, '__module__', '')
            if mod == 'apps.scholarship.views' or mod.startswith('apps.scholarship.views.'):
                seen[str(p.pattern)] = target.__qualname__
                self.assertIs(getattr(views, target.__name__), target, str(p.pattern))
        self.assertEqual(seen, PINNED_ROUTES)

    def test_the_names_other_modules_import_are_still_exported(self):
        import apps.scholarship.views as views
        for name in EXPORTED_NAMES:
            with self.subTest(name=name):
                self.assertTrue(hasattr(views, name), name)

    def test_the_document_record_view_keeps_its_hooks(self):
        """Tests patch ``DocumentListCreateView._maybe_extract_fields`` by this dotted path."""
        from apps.scholarship.views import DocumentListCreateView
        self.assertTrue(callable(DocumentListCreateView._maybe_extract_fields))
        self.assertTrue(DocumentListCreateView()._is_single_instance('ic', ''))

    def test_upload_type_sets_are_unchanged(self):
        from apps.scholarship import views
        self.assertEqual(views.BILL_DOC_TYPES, {'water_bill', 'electricity_bill'})
        self.assertEqual(views._BYPASS_JUDGE_TYPES, {'bank_statement', 'income_support_doc', 'other'})
        self.assertEqual(views.RELATIONSHIP_DOC_TYPES, {'birth_certificate', 'guardianship_letter'})
        self.assertEqual(views.TEXT_READ_DOC_TYPES, {'statement_of_intent'})
        self.assertEqual(views._FUNDED_STATES, ('awarded', 'active', 'maintenance'))
        self.assertEqual(views.SET_ASIDE_STATES, ('recommended', 'awarded', 'active', 'maintenance'))
        self.assertEqual(views._ACADEMIC_SINGLE_TYPES,
                         {'school_leaving_cert', 'semester_result', 'higher_results'})
        self.assertEqual(views.SUPPORTING_NAME_CHECK_TYPES, {
            'results_slip', 'str', 'salary_slip', 'epf', 'offer_letter', 'bank_statement',
            'income_support_doc', 'school_leaving_cert', 'semester_result', 'higher_results',
            'water_bill', 'electricity_bill', 'birth_certificate', 'guardianship_letter'})

    def test_allowed_upload_formats(self):
        from apps.scholarship.views import _is_allowed_upload
        self.assertTrue(_is_allowed_upload('image/jpeg', ''))
        self.assertTrue(_is_allowed_upload('Application/PDF; charset=x', 'a'))
        self.assertTrue(_is_allowed_upload('', 'scan.HEIC'))
        self.assertFalse(_is_allowed_upload('video/mp4', 'clip.mp4'))
        self.assertFalse(_is_allowed_upload('', ''))
        self.assertFalse(_is_allowed_upload(None, None))


def _cfg(max_other=8, max_docs=40, max_mb=8):
    """An ``org_config.value`` stand-in carrying just the three upload limits."""
    table = {'max_other_docs': max_other, 'max_docs_per_application': max_docs, 'max_doc_size_mb': max_mb}
    return lambda org, key: table[key]


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class DocumentRecordPost(TestCase):
    """``POST /scholarship/documents/`` branch by branch. ``upload_read`` is mocked in ``setUp``."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.me = make_student(name='Siti Test')
        cls.app = make_application('shortlisted', cohort=cls.cohort, student=cls.me)

    def setUp(self):
        self.client = authed_client(self.me.supabase_user_id)
        patch('apps.scholarship.storage.object_exists', return_value=True).start()
        self.read = patch('apps.scholarship.upload_read.read_and_judge',
                          return_value={'match_verdict': 'ok'}).start()
        self.needs = patch('apps.scholarship.upload_read.needs_read', return_value=False).start()
        self.addCleanup(patch.stopall)

    def _body(self, doc_type='ic', tag='t', **extra):
        body = {'doc_type': doc_type, 'storage_path': issued_key(self.app, doc_type, tag),
                'original_filename': 'f.jpg', 'content_type': 'image/jpeg', 'size': 1000}
        body.update(extra)
        return body

    def _post(self, body):
        return self.client.post(DOCS, body, format='json')

    def _count(self):
        return ApplicantDocument.objects.filter(application=self.app).count()

    # -- refusals, and the order they are checked in --------------------------------------------
    def test_no_application_is_403(self):
        stranger = make_student(name='No App')
        r = authed_client(stranger.supabase_user_id).post(DOCS, self._body(), format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json(), {'error': 'No shortlisted application.'})

    def test_an_invalid_body_is_400_and_saves_nothing(self):
        r = self._post({'doc_type': 'not_a_type', 'storage_path': 'x'})
        self.assertEqual(r.status_code, 400)
        r = self._post({'doc_type': 'ic'})   # no storage_path
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self._count(), 0)

    def test_a_video_is_refused_as_unsupported_format(self):
        r = self._post(self._body(content_type='video/mp4', original_filename='ic.mp4'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'error': 'unsupported_format', 'code': 'unsupported_format'})
        self.assertEqual(self._count(), 0)

    def test_a_too_big_file_reports_the_organisations_cap(self):
        with patch('apps.courses.org_config.value', side_effect=_cfg(max_mb=3)), \
                patch('apps.courses.org_config.max_doc_size_bytes', return_value=3 * 1024 * 1024):
            r = self._post(self._body(size=3 * 1024 * 1024 + 1))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'error': 'file_too_large', 'max_mb': 3})
        self.assertEqual(self._count(), 0)

    def test_a_file_exactly_at_the_cap_is_accepted(self):
        with patch('apps.courses.org_config.value', side_effect=_cfg(max_mb=3)), \
                patch('apps.courses.org_config.max_doc_size_bytes', return_value=3 * 1024 * 1024):
            r = self._post(self._body(size=3 * 1024 * 1024))
        self.assertEqual(r.status_code, 201, r.content)

    def test_the_in_programme_slip_slot_is_never_replaced_here(self):
        r = self._post(self._body('results_slip', request_code='in_programme'))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {'error': 'slip_locked', 'code': 'slip_locked'})
        self.assertEqual(self._count(), 0)

    def test_the_checks_run_in_this_order(self):
        """format -> size -> slip lock -> caps -> storage key. A body failing several is refused by
        the earliest, so a change in order shows here."""
        with patch('apps.courses.org_config.value', side_effect=_cfg(max_other=0, max_docs=0, max_mb=1)), \
                patch('apps.courses.org_config.max_doc_size_bytes', return_value=1024 * 1024):
            bad = self._body('other', request_code='in_programme', size=10 ** 9)
            bad['storage_path'] = 'not/an/issued/key'
            bad['content_type'] = 'video/mp4'
            bad['original_filename'] = 'x.mp4'
            self.assertEqual(self._post(bad).json()['error'], 'unsupported_format')
            bad['content_type'] = 'image/png'
            bad['original_filename'] = 'x.png'
            self.assertEqual(self._post(bad).json()['error'], 'file_too_large')
            bad['size'] = 10
            self.assertEqual(self._post(bad).json()['error'], 'slip_locked')
            bad['request_code'] = 'officer_1'
            self.assertEqual(self._post(bad).json()['error'], 'other_doc_limit_reached')
            bad['doc_type'] = 'ic'
            self.assertEqual(self._post(bad).json()['error'], 'doc_limit_reached')
        with patch('apps.courses.org_config.value', side_effect=_cfg()):
            self.assertEqual(self._post(bad).json()['error'], 'bad_storage_path')
        self.assertEqual(self._count(), 0)

    def test_the_other_doc_cap_refuses_a_new_slot_but_not_a_replacement(self):
        ApplicantDocument.objects.create(application=self.app, doc_type='other', request_code='officer_1',
                                         storage_path=issued_key(self.app, 'other', 'o1'))
        with patch('apps.courses.org_config.value', side_effect=_cfg(max_other=1)):
            r = self._post(self._body('other', 'o2', request_code='officer_2'))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json(), {'error': 'other_doc_limit_reached', 'max': 1})
            replace = self._post(self._body('other', 'o3', request_code='officer_1'))
            self.assertEqual(replace.status_code, 201, replace.content)

    def test_the_per_application_cap_refuses_a_new_slot_but_not_a_replacement(self):
        ApplicantDocument.objects.create(application=self.app, doc_type='ic',
                                         storage_path=issued_key(self.app, 'ic', 'a'))
        with patch('apps.courses.org_config.value', side_effect=_cfg(max_docs=1)):
            r = self._post(self._body('epf', 'b'))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json(), {'error': 'doc_limit_reached', 'max': 1})
            replace = self._post(self._body('ic', 'c'))
            self.assertEqual(replace.status_code, 201, replace.content)

    def test_a_superseded_copy_does_not_count_toward_the_cap(self):
        from django.utils import timezone
        ApplicantDocument.objects.create(application=self.app, doc_type='epf', superseded_at=timezone.now(),
                                         storage_path=issued_key(self.app, 'epf', 'old'))
        with patch('apps.courses.org_config.value', side_effect=_cfg(max_docs=1)):
            r = self._post(self._body('ic', 'n'))
        self.assertEqual(r.status_code, 201, r.content)

    def test_a_foreign_key_is_refused_before_anything_is_written(self):
        r = self._post(self._body(storage_path='9/9/ic/' + 'a' * 32))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'error': 'bad_storage_path', 'code': 'bad_storage_path'})
        self.assertEqual(self._count(), 0)

    def test_a_confirmed_missing_blob_is_refused(self):
        with patch('apps.scholarship.storage.object_exists', return_value=False):
            r = self._post(self._body())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'error': 'upload_incomplete', 'code': 'upload_incomplete'})

    def test_a_storage_hiccup_does_not_block_a_legitimate_upload(self):
        with patch('apps.scholarship.storage.object_exists', return_value=None):
            r = self._post(self._body())
        self.assertEqual(r.status_code, 201, r.content)

    # -- the write ------------------------------------------------------------------------------
    def test_a_first_upload_is_staged_judged_and_answered_201(self):
        r = self._post(self._body('ic', 'first'))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json(), {'match_verdict': 'ok'})
        doc = ApplicantDocument.objects.get(application=self.app, doc_type='ic')
        self.assertEqual(doc.storage_path, issued_key(self.app, 'ic', 'first'))
        kw = self.read.call_args.kwargs
        self.assertEqual(self.read.call_args.args[0].id, self.app.id)
        self.assertEqual(self.read.call_args.args[1].id, doc.id)
        self.assertEqual((kw['staged'], kw['stale_ids'], kw['existing_live']), (True, [], None))

    def test_a_reupload_stages_against_the_live_copy_and_hands_it_over(self):
        old = ApplicantDocument.objects.create(application=self.app, doc_type='ic',
                                               storage_path=issued_key(self.app, 'ic', 'old'))
        r = self._post(self._body('ic', 'new'))
        self.assertEqual(r.status_code, 201, r.content)
        kw = self.read.call_args.kwargs
        self.assertTrue(kw['staged'])
        self.assertEqual(kw['stale_ids'], [old.id])
        self.assertEqual(kw['existing_live'].id, old.id)

    def test_a_reviewer_type_replaces_first_and_is_never_staged(self):
        old = ApplicantDocument.objects.create(application=self.app, doc_type='bank_statement',
                                               storage_path=issued_key(self.app, 'bank_statement', 'old'))
        r = self._post(self._body('bank_statement', 'new'))
        self.assertEqual(r.status_code, 201, r.content)
        kw = self.read.call_args.kwargs
        self.assertFalse(kw['staged'])
        self.assertEqual(kw['stale_ids'], [old.id])
        self.assertIsNone(kw['existing_live'])
        old.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)   # replaced in the same write, not hard-deleted

    def test_a_reupload_is_scoped_to_its_own_household_member(self):
        father = ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='father',
            storage_path=issued_key(self.app, 'salary_slip', 'f'))
        mother = ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='mother',
            storage_path=issued_key(self.app, 'salary_slip', 'm'))
        self._post(self._body('salary_slip', 'm2', household_member='mother'))
        self.assertEqual(self.read.call_args.kwargs['stale_ids'], [mother.id])
        father.refresh_from_db()
        self.assertIsNone(father.superseded_at)

    def test_an_officer_requested_upload_also_replaces_the_apply_form_copy(self):
        apply_form = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', request_code='',
            storage_path=issued_key(self.app, 'ic', 'form'))
        asked = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', request_code='officer_4',
            storage_path=issued_key(self.app, 'ic', 'asked'))
        self._post(self._body('ic', 'again', request_code='officer_4'))
        self.assertEqual(sorted(self.read.call_args.kwargs['stale_ids']), sorted([asked.id, apply_form.id]))

    def test_a_blank_upload_does_not_touch_an_officer_requested_slot(self):
        asked = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', request_code='officer_4',
            storage_path=issued_key(self.app, 'ic', 'asked'))
        self._post(self._body('ic', 'plain'))
        self.assertEqual(self.read.call_args.kwargs['stale_ids'], [])
        asked.refresh_from_db()
        self.assertIsNone(asked.superseded_at)

    # -- STR earner force-tag -------------------------------------------------------------------
    def _str_app(self):
        return make_application('shortlisted', cohort=self.cohort, student=make_student(name='Str Test'),
                                income_route='str', income_earner='mother')

    def _post_for(self, app, doc_type, member='', **extra):
        body = {'doc_type': doc_type, 'storage_path': issued_key(app, doc_type, 'x'),
                'original_filename': 'f.jpg', 'content_type': 'image/jpeg', 'size': 10,
                'household_member': member}
        body.update(extra)
        return authed_client(app.profile.supabase_user_id).post(DOCS, body, format='json')

    def _member_of(self, app, doc_type):
        return ApplicantDocument.objects.get(application=app, doc_type=doc_type).household_member

    def test_pre_consent_str_income_docs_are_tagged_to_the_earner(self):
        app = self._str_app()
        for doc_type in ('str', 'salary_slip', 'epf', 'parent_ic'):
            with self.subTest(doc_type=doc_type):
                r = self._post_for(app, doc_type)
                self.assertEqual(r.status_code, 201, r.content)
                self.assertEqual(self._member_of(app, doc_type), 'mother')

    def test_an_str_doc_replaces_the_legacy_untagged_copy(self):
        app = self._str_app()
        legacy = ApplicantDocument.objects.create(
            application=app, doc_type='str', household_member='',
            storage_path=issued_key(app, 'str', 'legacy'))
        self._post_for(app, 'str')
        self.assertEqual(self.read.call_args.kwargs['stale_ids'], [legacy.id])

    def test_a_parent_ic_tagged_to_someone_else_keeps_its_tag(self):
        app = self._str_app()
        self._post_for(app, 'parent_ic', member='father')
        self.assertEqual(self._member_of(app, 'parent_ic'), 'father')

    def test_an_str_slip_tagged_to_someone_else_is_still_forced_to_the_earner(self):
        app = self._str_app()
        self._post_for(app, 'salary_slip', member='father')
        self.assertEqual(self._member_of(app, 'salary_slip'), 'mother')

    def test_an_officer_requested_upload_is_never_force_tagged(self):
        app = self._str_app()
        self._post_for(app, 'salary_slip', member='father', request_code='officer_2')
        self.assertEqual(self._member_of(app, 'salary_slip'), 'father')

    def test_after_consent_nothing_is_force_tagged(self):
        from django.utils import timezone
        app = self._str_app()
        type(app).objects.filter(pk=app.pk).update(profile_completed_at=timezone.now())
        self._post_for(app, 'salary_slip', member='father')
        self.assertEqual(self._member_of(app, 'salary_slip'), 'father')

    def test_a_non_str_route_is_never_force_tagged(self):
        app = make_application('shortlisted', cohort=self.cohort, student=make_student(name='Sal Test'),
                               income_route='salary', income_earner='mother')
        self._post_for(app, 'salary_slip', member='')
        self.assertEqual(self._member_of(app, 'salary_slip'), '')

    # -- queue or judge, kind, conflict ---------------------------------------------------------
    def test_a_type_with_a_paid_read_is_queued_and_answered_at_once(self):
        self.needs.return_value = True
        r = self._post(self._body('ic', 'q'))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['reading'], True)
        self.assertEqual(r.json()['match_verdict'], 'pending')
        self.read.assert_not_called()
        doc = ApplicantDocument.objects.get(application=self.app, doc_type='ic')
        self.assertEqual(doc.read_state, 'pending')
        self.assertTrue(doc.read_plan['staged'])

    def test_higher_results_carries_the_kind_from_results_route(self):
        with patch('apps.scholarship.results_route.upload_kind', return_value='stpm') as kind, \
                patch('apps.scholarship.slot_writes.create_in_slot', return_value=MagicMock()) as create:
            self._post(self._body('higher_results', 'h', request_code='officer_5'))
        kind.assert_called_once()
        self.assertEqual(kind.call_args.args[1], 'officer_5')
        self.assertEqual(create.call_args.args[1]['results_kind'], 'stpm')

    def test_other_types_carry_no_results_kind(self):
        with patch('apps.scholarship.slot_writes.create_in_slot', return_value=MagicMock()) as create:
            self._post(self._body('ic', 'k'))
        self.assertNotIn('results_kind', create.call_args.args[1])

    def test_the_slot_write_gets_the_slot_filter_and_flags(self):
        old = ApplicantDocument.objects.create(application=self.app, doc_type='ic',
                                               storage_path=issued_key(self.app, 'ic', 'old'))
        with patch('apps.scholarship.slot_writes.create_in_slot', return_value=MagicMock()) as create:
            self._post(self._body('ic', 'n'))
        kw = create.call_args.kwargs
        self.assertTrue(kw['staged'])
        self.assertEqual(kw['stale_ids'], [old.id])
        self.assertEqual(kw['existing_live'].id, old.id)
        self.assertEqual(kw['slot_filter'], dict(application=self.app, doc_type='ic',
                                                  household_member__in=[''], request_code='',
                                                  superseded_at__isnull=True))

    def test_a_contested_slot_is_409_upload_conflict(self):
        with patch('apps.scholarship.slot_writes.create_in_slot', return_value=None):
            r = self._post(self._body())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {'error': 'upload_conflict', 'code': 'upload_conflict'})
        self.read.assert_not_called()

    def test_the_list_serves_the_limits_and_the_pending_count(self):
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', read_state='pending',
                                         storage_path=issued_key(self.app, 'ic', 'p'))
        with patch('apps.courses.org_config.value', side_effect=_cfg(3, 9, 2)):
            r = self.client.get(DOCS)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['limits'], {'max_doc_size_mb': 2, 'max_docs_per_application': 9,
                                          'max_other_docs': 3})
        self.assertEqual(body['reading'], 1)
        self.assertEqual(len(body['documents']), 1)
