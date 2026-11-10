"""Audit A3.5 - pinning tests for the split of ``apps/courses/views.py`` into a package.

Written BEFORE the split and green before and after it: the split moves code and changes none.

1. Every route of the courses URLconf that was served from ``views`` still resolves to the same view
   class (and URL name), and the package still exports that very object.
2. Every name other modules or tests import from ``apps.courses.views`` is still there.
3. ``CourseSearchView.get`` (the catalogue search): status, keys and values for filters, TVET pathways,
   PISMP aliran, qualification, state, Bumiputera, pagination and the pick-lists.
4. ``ProfileView.get`` (the student profile payload): the exact key order and values for a new profile,
   a populated one, an identity mismatch, a decided application and the two swallowed failures.

The course rows are made here; the seeded matric / STPM Form 6 rows from the migrations stay in place,
so the assertions look only at this file's own course ids (and at pick-list members).
"""
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import URLResolver
from rest_framework.test import APIClient

from apps.courses import urls as courses_urls
from apps.courses import views
from apps.courses.models import StudentProfile
from apps.courses.tests.test_a35_fixture import make_catalogue, pathway_patch
from apps.scholarship.tests.factories import create_document, make_application, make_student

PINNED_ROUTES = {
    'calculate/cgpa/|calculate-cgpa': 'CalculateCgpaView',
    'calculate/merit/|calculate-merit': 'CalculateMeritView',
    'calculate/pathways/|calculate-pathways': 'CalculatePathwaysView',
    'courses/<str:course_id>/|course-detail': 'CourseDetailView',
    'courses/search/|course-search': 'CourseSearchView',
    'courses/|course-list': 'CourseListView',
    'eligibility/check/|eligibility-check': 'EligibilityCheckView',
    'fields/|field-list': 'FieldListView',
    'institutions/<str:institution_id>/|institution-detail': 'InstitutionDetailView',
    'institutions/|institution-list': 'InstitutionListView',
    'outcomes/<int:outcome_id>/|outcome-detail': 'OutcomeDetailView',
    'outcomes/|outcome-list': 'OutcomeListView',
    'profile/claim-nric/confirm-code/|profile-claim-confirm-code': 'NricClaimConfirmCodeView',
    'profile/claim-nric/send-code/|profile-claim-send-code': 'NricClaimSendCodeView',
    'profile/claim-nric/|profile-claim-nric': 'NricClaimView',
    'profile/sync/|profile-sync': 'ProfileSyncView',
    'profile/verify-email/<uuid:token>/|verify-email': 'VerifyEmailView',
    'profile/verify-email/send/|verify-email-send': 'SendVerificationView',
    'profile/verify-phone/check/|verify-phone-check': 'PhoneVerifyCheckView',
    'profile/verify-phone/send/|verify-phone-send': 'PhoneVerifyStartView',
    'profile/|profile': 'ProfileView',
    'quiz/questions/|quiz-questions': 'QuizQuestionsView',
    'quiz/submit/|quiz-submit': 'QuizSubmitView',
    'ranking/|ranking': 'RankingView',
    'saved-courses/<str:course_id>/|saved-course-detail': 'SavedCourseDetailView',
    'saved-courses/|saved-courses': 'SavedCoursesView',
    'stpm/courses/<str:course_id>/|stpm-course-detail': 'StpmCourseDetailView',
    'stpm/eligibility/check/|stpm-eligibility-check': 'StpmEligibilityCheckView',
    'stpm/ranking/|stpm-ranking': 'StpmRankingView',
    'stpm/search/|stpm-search': 'StpmSearchView',
}

EXPORTED_NAMES = [
    'CalculateCgpaView', 'CalculateMeritView', 'CalculatePathwaysView', 'CourseDetailView',
    'CourseListView', 'CourseSearchView', 'EligibilityCheckView', 'FieldListView',
    'InstitutionDetailView', 'InstitutionListView', 'NricClaimConfirmCodeView', 'NricClaimSendCodeView',
    'NricClaimView', 'OutcomeDetailView', 'OutcomeListView', 'PhoneVerifyCheckView',
    'PhoneVerifyStartView', 'ProfileSyncView', 'ProfileView', 'QuizQuestionsView', 'QuizSubmitView',
    'RankingView', 'SOURCE_TYPE_ORDER', 'SavedCourseDetailView', 'SavedCoursesView',
    'SendVerificationView', 'StpmCourseDetailView', 'StpmEligibilityCheckView', 'StpmRankingView',
    'StpmSearchView', 'VERIFICATION_EMAIL_BODIES', 'VERIFICATION_EMAIL_SUBJECTS', 'VerifyEmailView',
    '_persist_quiz_signals', '_tvet_pick_list', 'logger',
]


def _flatten(patterns):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _flatten(p.url_patterns)
        else:
            yield p


def _from_views_package(view):
    mod = view.__module__
    return mod == 'apps.courses.views' or mod.startswith('apps.courses.views.')


class EveryRouteStillResolves(SimpleTestCase):
    def test_every_route_served_from_views_points_at_the_same_class(self):
        seen = {}
        for p in _flatten(courses_urls.urlpatterns):
            view = getattr(p.callback, 'view_class', p.callback)
            if _from_views_package(view):
                seen[f'{p.pattern}|{p.name}'] = view.__qualname__
                self.assertIs(getattr(views, view.__qualname__), view)
        self.assertEqual(seen, PINNED_ROUTES)

    def test_the_names_other_modules_import_are_still_exported(self):
        for name in EXPORTED_NAMES:
            self.assertTrue(hasattr(views, name), name)

    def test_constants_unchanged(self):
        self.assertEqual(sorted(views.VERIFICATION_EMAIL_SUBJECTS), sorted(views.VERIFICATION_EMAIL_BODIES))
        self.assertEqual(views.SOURCE_TYPE_ORDER,
                         {'ua': 5, 'matric': 4, 'stpm': 4, 'pismp': 3, 'poly': 2, 'kkom': 1})

    def test_the_logger_keeps_its_name(self):
        self.assertEqual(views.logger.name, 'apps.courses.views')

    def test_unauthenticated_profile_is_401(self):
        self.assertEqual(APIClient().get('/api/v1/profile/').status_code, 401)


MINE = ['P-IT', 'P-ME', 'PI-1', 'T-IL', 'T-KB', 'U-BM', 'S-1', 'S-2']


class CourseSearchGetPins(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_catalogue()

    def setUp(self):
        self.client = APIClient()
        p = pathway_patch()
        p.start()
        self.addCleanup(p.stop)

    def _get(self, **params):
        r = self.client.get('/api/v1/courses/search/', params)
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _mine(self, **params):
        return [c['course_id'] for c in self._get(**params)['courses'] if c['course_id'] in MINE]

    def test_default_order_is_credential_then_source_then_merit(self):
        d = self._get()
        self.assertEqual(set(d), {'courses', 'total_count', 'filters'})
        self.assertEqual(self._mine(), ['P-IT', 'P-ME', 'PI-1', 'T-KB', 'T-IL', 'S-1'])
        self.assertEqual(d['total_count'], len(d['courses']))

    def test_row_shapes(self):
        rows = {c['course_id']: c for c in self._get()['courses']}
        self.assertEqual(rows['P-IT'], {
            'course_id': 'P-IT', 'course_name': 'Diploma Teknologi Maklumat', 'level': 'Diploma',
            'field': 'Teknologi Maklumat', 'field_key': 'it-perisian', 'source_type': 'poly',
            'pathway_type': 'poly', 'merit_cutoff': 70.0, 'institution_count': 2,
            'institution_name': 'Kolej Alpha', 'institution_state': 'Kedah', 'qualification': 'SPM',
            'aliran': None, 'is_elektif': False})
        self.assertEqual(rows['T-IL']['pathway_type'], 'iljtm')
        self.assertEqual(rows['T-IL']['source_type'], 'tvet')
        self.assertEqual(rows['T-IL']['merit_cutoff'], None)
        self.assertEqual(rows['PI-1']['aliran'], 'sk')
        self.assertEqual(rows['PI-1']['is_elektif'], False)
        self.assertEqual(rows['S-1'], {
            'course_id': 'S-1', 'course_name': 'Ijazah Sains Komputer', 'level': 'Ijazah Sarjana Muda',
            'field': 'Teknologi Maklumat', 'field_key': 'it-perisian', 'source_type': 'ua',
            'merit_cutoff': 88.0, 'institution_count': 1, 'institution_name': 'UM',
            'institution_state': 'Selangor', 'qualification': 'STPM'})

    def test_filters(self):
        self.assertEqual(self._mine(q='kimpalan'), ['T-IL'])
        self.assertEqual(self._get(q='kimpalan')['total_count'], 1)
        self.assertEqual(self._mine(level='Diploma'), ['P-IT', 'P-ME'])
        self.assertEqual(self._get(level='Diploma')['total_count'], 2)
        self.assertEqual(self._mine(field_key='it-perisian'), ['P-IT', 'S-1'])
        self.assertEqual(self._mine(field='kejuruteraan'), ['P-ME', 'T-KB', 'T-IL'])
        self.assertEqual(self._mine(source_type='poly'), ['P-IT', 'P-ME'])
        self.assertEqual(self._mine(state='kedah'), ['P-IT', 'P-ME', 'PI-1'])
        self.assertEqual(self._mine(level='Ijazah Sarjana Muda'), ['PI-1', 'S-1'])

    def test_tvet_pathway_filters_post_filter_and_fix_the_count(self):
        for pathway, cid in (('iljtm', 'T-IL'), ('ilkbs', 'T-KB')):
            d = self._get(source_type=pathway)
            self.assertEqual([c['course_id'] for c in d['courses']], [cid])
            self.assertEqual(d['total_count'], 1)
        self.assertEqual(self._get(source_type='mara')['courses'], [])

    def test_pismp_and_aliran(self):
        d = self._get(source_type='pismp')
        self.assertEqual([c['course_id'] for c in d['courses']], ['PI-1'])
        self.assertEqual(d['total_count'], 1)
        self.assertEqual(self._get(aliran='rendah')['courses'], [])
        self.assertEqual(self._get(aliran='rendah')['total_count'], 0)
        d = self._get(aliran='sk')
        self.assertEqual([c['course_id'] for c in d['courses']], ['PI-1'])   # STPM excluded by aliran

    def test_qualification_and_ua(self):
        self.assertEqual([c['course_id'] for c in self._get(qualification='stpm')['courses']], ['S-1'])
        self.assertNotIn('S-1', self._mine(qualification='SPM'))
        self.assertEqual([c['course_id'] for c in self._get(source_type='ua')['courses']], ['S-1'])

    def test_bumiputera_unlocks_the_bumi_only_rows(self):
        self.assertNotIn('U-BM', self._mine())
        self.assertNotIn('S-2', self._mine())
        self.assertEqual(self._mine(bumiputera='1'),
                         ['U-BM', 'P-IT', 'P-ME', 'PI-1', 'T-KB', 'T-IL', 'S-1', 'S-2'])
        self.assertNotIn('U-BM', self._mine(bumiputera='1', nationality='non_malaysian'))

    def test_pagination(self):
        full = self._get()
        d = self._get(limit=2, offset=1)
        self.assertEqual([c['course_id'] for c in d['courses']],
                         [c['course_id'] for c in full['courses'][1:3]])
        self.assertEqual(d['total_count'], full['total_count'])
        for bad in ({'limit': 'x'}, {'offset': '-3'}, {'offset': 'z'}):
            self.assertEqual(self._get(**bad)['courses'][:3], full['courses'][:3])
        # a non-numeric limit falls back to 24, a missing one to "everything"
        self.assertEqual(len(self._get(limit='x')['courses']), min(24, full['total_count']))

    def test_pick_lists(self):
        f = self._get()['filters']
        self.assertEqual(list(f), ['levels', 'fields', 'field_keys', 'source_types', 'alirans', 'states',
                                   'qualifications'])
        self.assertEqual(f['qualifications'], ['SPM', 'STPM'])
        self.assertEqual(f['alirans'], [{'value': 'sk', 'label': 'Sekolah Kebangsaan (SK)'}])
        self.assertIn('Diploma', f['levels'])
        self.assertNotIn('Asasi', f['levels'])                   # the Bumi-only row's level
        self.assertEqual(f['levels'], sorted(f['levels']))
        for st in ('iljtm', 'ilkbs', 'poly', 'pismp', 'matric'):
            self.assertIn(st, f['source_types'])
        self.assertNotIn('tvet', f['source_types'])
        self.assertNotIn('ua', f['source_types'])
        self.assertNotIn('mara', f['source_types'])
        self.assertIn('it-perisian', f['field_keys'])
        self.assertIn('Kejuruteraan', f['fields'])
        self.assertNotIn('Sains', f['fields'])                   # only Bumi-only rows carry it
        self.assertEqual(f['states'], sorted(f['states']))
        self.assertIn('Kedah', f['states'])
        fb = self._get(bumiputera='1')['filters']
        self.assertIn('Asasi', fb['levels'])
        self.assertIn('Sains', fb['fields'])


def _req(uid, email='kid@example.test'):
    r = RequestFactory().get('/api/v1/profile/')
    r.user_id = uid
    r.supabase_user = {'email': email}
    return r


NEW_PROFILE = {
    'grades': {}, 'gender': '', 'nationality': 'Warganegara', 'bumiputera': None, 'colorblind': False,
    'disability': False, 'student_signals': {}, 'preferred_state': '', 'preferred_call_language': '',
    'referral_source': None, 'guardians': [], 'name': '', 'school': '', 'nric': '',
    'nric_verified': False, 'identity_verified': False, 'nric_locked': False, 'ic_flags': [],
    'ic_card_nric': '', 'ic_card_name': '', 'angka_giliran': '', 'address': '', 'postal_code': '',
    'city': '', 'email': 'kid@example.test', 'contact_email': 'kid@example.test',
    'contact_email_verified': True, 'contact_phone': '', 'contact_phone_verified': False,
    'phone_verify_enabled': False, 'whatsapp_opt_in': True, 'household_income': None,
    'household_size': None, 'father_name': '', 'father_occupation': '', 'father_occupation_other': '',
    'mother_name': '', 'mother_occupation': '', 'mother_occupation_other': '',
    'other_family_members': [], 'siblings_in_school': None, 'siblings_in_tertiary': None,
    'pathway_certainty': '', 'chosen_pathway': '', 'pre_u_track': '', 'pre_u_institution': '',
    'chosen_programme': {}, 'pathways_considered': [], 'uncertainty_reasons': [], 'uncertainty_note': '',
    'merit_score': None, 'pathway': '', 'application_open': False, 'exam_type': 'spm',
    'results_exam_type': '', 'results_held': 'spm', 'stpm_grades': {}, 'stpm_cgpa': None,
    'stpm_cgpa_calculated': False, 'stpm_koko': None, 'muet_band': None, 'coq_score': None,
    'spm_prereq_grades': {}, 'stream_subjects': [], 'elective_subjects': [], 'spm_elective_subjects': [],
    'spm_stream': '', 'higher_cgpa': None, 'higher_koko': None, 'higher_institution_type': '',
    'completed_qualifications': [], 'overall_cgpa': None,
}


class ProfileGetPins(TestCase):
    def _get(self, uid, **kw):
        resp = views.ProfileView().get(_req(uid, **kw))
        self.assertEqual(resp.status_code, 200)
        return resp.data

    def test_a_new_profile_is_created_and_served_exactly(self):
        d = self._get('new-uid')
        self.assertEqual(list(d), list(NEW_PROFILE))
        self.assertEqual(dict(d), NEW_PROFILE)
        self.assertTrue(StudentProfile.objects.filter(supabase_user_id='new-uid').exists())

    def test_no_supabase_user_gives_a_blank_email(self):
        r = RequestFactory().get('/api/v1/profile/')
        r.user_id = 'no-email'
        d = views.ProfileView().get(r).data
        self.assertEqual((d['email'], d['contact_email'], d['contact_email_verified']), ('', '', False))

    def test_a_populated_profile_with_a_matching_card_and_an_open_application(self):
        s = make_student(grades={'bm': 'A', 'eng': 'B+', 'math': 'A-', 'sci': 'B', 'hist': 'C'},
                         name='ARUN A/L RAJU', nric='070101-14-1234', contact_email='other@example.test',
                         coq_score=7.5, stream_subjects=['phy', 'chem'], gender='Lelaki')
        app = make_application('submitted', student=s)
        create_document(app, 'ic', vision_name='ARUN A/L RAJU', vision_nric='070101-14-1234')
        d = self._get(s.supabase_user_id)
        want = dict(NEW_PROFILE, grades=s.grades, gender='Lelaki', name='ARUN A/L RAJU',
                    nric='070101-14-1234', identity_verified=True, ic_card_nric='070101-14-1234',
                    ic_card_name='ARUN A/L RAJU', contact_email='other@example.test',
                    contact_email_verified=False, merit_score=40.6, application_open=True,
                    coq_score=7.5, stream_subjects=['phy', 'chem'])
        self.assertEqual(dict(d), want)

    def test_a_card_that_disagrees_is_flagged_and_not_verified(self):
        s = make_student(name='BALA A/L SAMY', nric='070101-14-1234', contact_email='kid@example.test')
        app = make_application('submitted', student=s)
        create_document(app, 'ic', vision_name='SOMEONE ELSE', vision_nric='070101-14-9999')
        d = self._get(s.supabase_user_id)
        self.assertEqual(d['ic_flags'], ['nric_differs', 'name_differs'])
        self.assertEqual((d['ic_card_nric'], d['ic_card_name']), ('070101-14-9999', 'SOMEONE ELSE'))
        self.assertFalse(d['identity_verified'])
        self.assertFalse(d['nric_locked'])
        self.assertTrue(d['application_open'])
        self.assertTrue(d['contact_email_verified'])

    def test_a_superseded_card_decides_nothing(self):
        from django.utils import timezone
        s = make_student(name='BALA A/L SAMY', nric='070101-14-1234')
        app = make_application('submitted', student=s)
        create_document(app, 'ic', vision_name='SOMEONE ELSE', vision_nric='070101-14-9999',
                        superseded_at=timezone.now())
        d = self._get(s.supabase_user_id)
        self.assertEqual((d['ic_flags'], d['ic_card_nric'], d['ic_card_name']), ([], '', ''))

    def test_a_locked_nric_is_served_locked_and_verified(self):
        s = make_student(name='BALA A/L SAMY', nric='070101-14-1234', nric_verified=True)
        d = self._get(s.supabase_user_id)
        self.assertTrue(d['nric_verified'])
        self.assertTrue(d['identity_verified'])
        self.assertTrue(d['nric_locked'])

    def test_a_decided_application_is_not_open(self):
        s = make_student()
        app = make_application('submitted', student=s)
        app.status = 'rejected'
        app.save(update_fields=['status'])
        self.assertFalse(self._get(s.supabase_user_id)['application_open'])

    def test_a_failing_merit_calculation_is_swallowed(self):
        s = make_student(grades={'bm': 'A'})
        with patch('apps.courses.eligibility_service.compute_student_merit', side_effect=RuntimeError('x')):
            self.assertIsNone(self._get(s.supabase_user_id)['merit_score'])

    def test_a_failing_identity_read_is_swallowed(self):
        s = make_student(name='BALA A/L SAMY', nric='070101-14-1234')
        app = make_application('submitted', student=s)
        create_document(app, 'ic', vision_name='BALA A/L SAMY', vision_nric='070101-14-1234')
        with patch('apps.scholarship.identity.compare', side_effect=RuntimeError('x')):
            d = self._get(s.supabase_user_id)
        self.assertEqual((d['identity_verified'], d['ic_flags'], d['ic_card_nric']), (False, [], ''))

    def test_phone_verify_flag_follows_the_setting(self):
        with self.settings(PHONE_VERIFY_ENABLED=True):
            self.assertTrue(self._get('pv-uid')['phone_verify_enabled'])
