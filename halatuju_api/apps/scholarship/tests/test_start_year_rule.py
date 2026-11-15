"""H3 (#597, owner 2026-11-15): the per-intake course-start-year rule (`start_year`).

Per gift setting: a 2024 starter in a 2025/2026 intake is caught (red Pathway, a confident
disqualifier, QC's floor); a 2025 starter in an intake with no limit (Sabah) is not; an intake with
no setting is unchanged; an unreadable year is a reviewer line for a person, never a fail.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import award, start_year
from apps.scholarship import pathway_engine as pe
from apps.scholarship.models import ApplicantDocument, ScholarshipCohort
from apps.scholarship.resolution import CODE_TO_TICKET
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)
from apps.scholarship.verdict_engine import build_verdict


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.degree = ScholarshipCohort.objects.create(code='deg', name='Degree', year=2026,
                                                      allowed_start_years=[2025, 2026])
        cls.sabah = ScholarshipCohort.objects.create(code='sabah', name='Sabah', year=2026)
        cls.plain = ScholarshipCohort.objects.create(code='plain', name='B40', year=2026)

    def _app(self, cohort, suffix):
        student = make_student(supabase_user_id=f'sy-{suffix}', name='Anbu A/L Raj',
                               household_income=1500, household_size=5)
        return make_application(
            'profile_complete', cohort=cohort, student=student,
            chosen_pathway='matric', father_occupation='gov', mother_occupation='homemaker')

    def _offer(self, app, intake='', reporting_date='', read=True):
        fields = {'reporting_date': reporting_date, 'intake': intake, 'candidate_name': 'Anbu A/L Raj',
                  'programme': 'Program Matrikulasi', 'institution': 'Kolej Matrikulasi Test'}
        vf = {'fields': fields, 'student_verdict': 'ok'} if read else {}
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer', vision_fields=vf)

    def _pathway(self, app):
        return next(f for f in build_verdict(app) if f['fact'] == 'pathway')

    def _codes(self, app):
        return {i['code'] for i in self._pathway(app)['unresolved']}


class PerGiftSetting(_Base):
    def test_a_2024_starter_in_a_2025_2026_intake_is_caught(self):
        app = self._app(self.degree, 'a')
        self._offer(app, intake='2024', reporting_date='10 JUN 2024')
        fact = self._pathway(app)
        self.assertEqual(fact['status'], 'gap')
        item = next(i for i in fact['unresolved'] if i['code'] == start_year.OUTSIDE)
        self.assertEqual(item['params'], {'start_year': '2024', 'years': '2025, 2026'})
        self.assertEqual(award.verdict_disqualifier(build_verdict(app)), start_year.OUTSIDE)

    def test_the_amount_does_not_move(self):
        app = self._app(self.degree, 'amt')
        self._offer(app, intake='2024')
        self.assertEqual(str(award.proposed_award_amount(app)), '2000')

    def test_a_2025_or_2026_starter_in_that_intake_is_not_caught(self):
        for y in ('2025', '2026'):
            with self.subTest(y):
                app = self._app(self.degree, f'in-{y}')
                self._offer(app, intake=y)
                self.assertFalse(self._codes(app) & {start_year.OUTSIDE, start_year.UNKNOWN})

    def test_a_2025_starter_in_an_unlimited_intake_is_not_caught(self):
        app = self._app(self.sabah, 'sabah')
        self._offer(app, intake='2025')
        self.assertFalse(self._codes(app) & {start_year.OUTSIDE, start_year.UNKNOWN})
        self.assertIsNone(start_year.reading(app))

    def test_an_intake_with_no_setting_is_unchanged(self):
        # The same verdict as with the rule module switched out entirely.
        app = self._app(self.plain, 'plain')
        self._offer(app, intake='2019')
        before = build_verdict(app)
        from unittest import mock
        with mock.patch('apps.scholarship.start_year.apply_to_pathway_fact', lambda a, f: f):
            self.assertEqual(build_verdict(app), before)

    def test_an_unreadable_year_is_flagged_for_a_person_not_failed(self):
        app = self._app(self.degree, 'unk')
        self._offer(app, intake='', reporting_date='')
        fact = self._pathway(app)
        self.assertIn(start_year.UNKNOWN, {i['code'] for i in fact['unresolved']})
        self.assertNotIn(start_year.OUTSIDE, {i['code'] for i in fact['unresolved']})
        self.assertEqual(award.verdict_disqualifier(build_verdict(app)), '')
        # No band move: the same status as the identical case in an intake with no setting.
        twin = self._app(self.plain, 'unk-twin')
        self._offer(twin, intake='', reporting_date='')
        self.assertEqual(fact['status'], self._pathway(twin)['status'])

    def test_no_line_while_the_letter_is_not_read_or_absent(self):
        app = self._app(self.degree, 'unread')
        self._offer(app, read=False)
        self.assertFalse(self._codes(app) & {start_year.OUTSIDE, start_year.UNKNOWN})
        none = self._app(self.degree, 'none')
        self.assertFalse(self._codes(none) & {start_year.OUTSIDE, start_year.UNKNOWN})

    def test_neither_code_is_a_student_ticket(self):
        self.assertNotIn(start_year.OUTSIDE, CODE_TO_TICKET)
        self.assertNotIn(start_year.UNKNOWN, CODE_TO_TICKET)


class QcFloor(_Base):
    def test_a_caught_case_joins_the_red_fact_floor(self):
        app = self._app(self.degree, 'qc')
        self._offer(app, intake='2024')
        self.assertIn('pathway', [f['fact'] for f in build_verdict(app) if f['status'] == 'gap'])


class SessionReading(SimpleTestCase):
    """H3a review (LM): a session "S/S+1" spans two calendar years. Semester II starts in S+1, so
    reading the FIRST year would wrongly fail a 2025 starter on a 2025/2026 gift. Unsure → ''
    (a person checks), never a guessed year. None = no session in the line (the old reading)."""

    def test_second_semester_forms_read_the_second_year(self):
        for intake in ('Sesi 2024/2025 Semester II', 'Semester 2 Sesi 2024/2025', 'SEM 2 2024/2025',
                       'Sem. 2, Sesi 2024/2025', 'Semester Kedua Sesi 2024/2025',
                       'Sesi 2024/2025 Ambilan Februari', 'Sesi Akademik 2024/2025 (Mac)',
                       'Academic Session 2024/2025, Semester 2', 'Second Semester, Session 2024/2025',
                       'Session 2024/25 February intake', 'Sesi II 2024-2025'):
            with self.subTest(intake=intake):
                self.assertEqual(pe.session_start_year(intake), '2025')

    def test_first_semester_forms_read_the_first_year(self):
        for intake in ('Sesi 2024/2025 Semester I', 'Semester 1 Sesi 2024/2025', 'SESI 1-2024/2025',
                       'Semester Pertama Sesi 2024/2025', 'Sesi 2024/2025 Ambilan September',
                       'Academic Session 2024/2025, Semester 1', 'First Semester, Session 2024/2025',
                       'Session 2024/2025 October intake', 'Sem I 2024/25'):
            with self.subTest(intake=intake):
                self.assertEqual(pe.session_start_year(intake), '2024')

    def test_a_bare_session_keeps_todays_first_year_reading(self):
        for intake in ('Sesi 2024/2025', 'SESI AKADEMIK 2024/2025', 'Academic Session 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(pe.session_start_year(intake), '2024')

    def test_the_letters_reporting_date_settles_the_year_inside_the_session(self):
        self.assertEqual(pe.session_start_year('Sesi 2024/2025', '17 Februari 2025'), '2025')
        self.assertEqual(pe.session_start_year('Sesi II 2024/2025', '2 Disember 2024'), '2024')
        self.assertEqual(pe.session_start_year('Semester 1 Sesi 2024/2025', '8 Sept 2024'), '2024')

    def test_unsure_is_unknown_never_a_guess(self):
        for intake, rd in (('Sesi 2024/2025 Semester 1 dan Semester 2', ''),   # both terms
                           ('Sesi 2024/2025 Ambilan September / Februari', ''),
                           ('Semester 3 Sesi 2024/2025', ''),                 # a continuing student
                           ('Sesi : 2026/2027 Semester : 3', ''),
                           ('Third Semester, Session 2024/2025', ''),
                           ('Sesi 2024/2025', '5 Jan 2023')):                  # date outside session
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(pe.session_start_year(intake, rd), '')

    def test_no_session_is_left_to_the_old_reading(self):
        for intake in ('', '2024', 'Ambilan Jun 2025', 'SEMESTER 1 TAHUN 2026',
                       '6 / 2025 – 12 / 2026', '2024/2026'):
            with self.subTest(intake=intake):
                self.assertIsNone(pe.session_start_year(intake))


class SessionOnTheGift(_Base):
    def test_a_second_semester_2025_starter_is_not_caught_on_the_degree_gift(self):
        app = self._app(self.degree, 'sem2')
        self._offer(app, intake='Sesi 2024/2025 Semester II')
        self.assertEqual(pe.course_start_year(app), 2025)
        self.assertFalse(self._codes(app) & {start_year.OUTSIDE, start_year.UNKNOWN})

    def test_a_first_semester_2024_starter_is_caught(self):
        app = self._app(self.degree, 'sem1')
        self._offer(app, intake='Sesi 2024/2025 Semester I')
        self.assertIn(start_year.OUTSIDE, self._codes(app))

    def test_an_unsure_session_goes_to_a_person(self):
        app = self._app(self.degree, 'sem3')
        self._offer(app, intake='Semester 3 Sesi 2024/2025')
        self.assertIsNone(pe.course_start_year(app))
        codes = self._codes(app)
        self.assertIn(start_year.UNKNOWN, codes)
        self.assertNotIn(start_year.OUTSIDE, codes)


class TheStudentsNote(_Base):
    """Owner ruling "1A" (2026-11-15): the student's offer card carries the gift's years when the
    course started outside them. Nothing for an unknown year, a gift with no setting, or an old
    (superseded) letter. Not a block: the verdict is unchanged by it."""

    def _note(self, doc):
        from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
        return ApplicantDocumentSerializer(doc).data['pathway_check']['start_year_note']

    def test_outside_carries_the_gifts_years(self):
        app = self._app(self.degree, 'note-out')
        self.assertEqual(self._note(self._offer(app, intake='2024')), {'years': [2025, 2026]})

    def test_nothing_inside_unknown_or_with_no_setting(self):
        for cohort, intake, suffix in ((self.degree, '2025', 'in'), (self.degree, '', 'unk'),
                                       (self.sabah, '2019', 'sabah'), (self.plain, '2019', 'plain')):
            with self.subTest(suffix):
                app = self._app(cohort, f'note-{suffix}')
                self.assertIsNone(self._note(self._offer(app, intake=intake)))

    def test_nothing_on_a_superseded_letter(self):
        from django.utils import timezone
        app = self._app(self.degree, 'note-old')
        doc = self._offer(app, intake='2024')
        doc.superseded_at = timezone.now()
        doc.save(update_fields=['superseded_at'])
        self.assertIsNone(self._note(doc))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class QcAcceptEndpoint(TestCase):
    """The real QC accept refuses (400 verdict_gap_floor) on the red start-year Pathway fact. Only
    the Pathway fact is kept from the real verdict, so the floor can turn on nothing else (the
    factory case has no other documents)."""

    def setUp(self):
        self.cohort = make_cohort(allowed_start_years=[2025, 2026])
        self.qc = make_admin('qc', owning_org=self.cohort.owning_organisation, email='qc-sy@example.test')
        real = build_verdict
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict',
                             side_effect=lambda a, *x, **k: [f for f in real(a, *x, **k)
                                                             if f['fact'] == 'pathway'])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _case(self, intake):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                               student=make_student(name='Anbu A/L Raj'))
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer',
            vision_fields={'fields': {'intake': intake, 'candidate_name': 'Anbu A/L Raj'},
                           'student_verdict': 'ok'})
        return app

    def _accept(self, app, **body):
        return authed_client(self.qc).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
            {'decision': 'accept', **body}, format='json')

    def test_an_outside_year_is_refused_on_the_floor(self):
        app = self._case('2024')
        self.assertIn(start_year.OUTSIDE, {i['code'] for f in build_verdict(app)
                                           if f['fact'] == 'pathway' for i in f['unresolved']})
        r = self._accept(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual((r.json()['code'], r.json()['facts']), ('verdict_gap_floor', ['pathway']))
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')

    def test_an_inside_year_is_not_held_by_the_start_year_rule(self):
        app = self._case('2025')
        self.assertNotIn('pathway', [f['fact'] for f in build_verdict(app) if f['status'] == 'gap'])


class StoredValue(TestCase):
    def test_normalise_refuses_whole_and_orders(self):
        self.assertEqual(start_year.normalise_years([2026, 2025, 2026]), ([2025, 2026], True))
        self.assertEqual(start_year.normalise_years(None), ([], True))
        self.assertEqual(start_year.normalise_years([]), ([], True))
        self.assertEqual(start_year.normalise_years([2026.0]), ([2026], True))
        for bad in ('2025', 2025, [True], ['2025'], [2025, 'x'], [2025.5], [1999], [20255], {'a': 1}):
            with self.subTest(bad=bad):
                self.assertEqual(start_year.normalise_years(bad), (None, False))

    def test_stored_reader_keeps_a_junk_rule_on(self):
        self.assertEqual(start_year.stored_years(['2025', 2026]), [2025, 2026])
        self.assertEqual(start_year.stored_years(None), [])
        self.assertEqual(start_year.stored_years(['junk']), [])
        self.assertTrue(start_year.rule_on(['junk']))

    def test_readable_years(self):
        self.assertEqual(start_year.readable_years([2026]), '2026')
        self.assertEqual(start_year.readable_years([2024, 2025, 2026]), '2024, 2025, 2026')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheGiftEditorDoor(TestCase):
    """The Rules tab's door: the real intake-year endpoints, as `allowed_birth_states`."""

    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _years(self):
        return f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/'

    def _year(self, c):
        return f'/api/v1/admin/scholarship/intake-years/{c.id}/'

    def _cohort(self, **kw):
        return make_cohort(programme=self.programme, is_active=True, is_open=False, **kw)

    def test_create_stores_and_serves_it_in_order(self):
        r = self.client.post(self._years(), {'code': 'sy-new', 'name': 'sy', 'year': 2027,
                                             'allowed_start_years': [2026, 2025]}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['requirements']['allowed_start_years'], [2025, 2026])
        self.assertEqual(ScholarshipCohort.objects.get(code='sy-new').allowed_start_years, [2025, 2026])

    def test_create_without_it_is_empty_and_the_list_serves_it(self):
        self.client.post(self._years(), {'code': 'sy-none', 'name': 'sy', 'year': 2027}, format='json')
        self.assertEqual(ScholarshipCohort.objects.get(code='sy-none').allowed_start_years, [])
        row = self.client.get(self._years()).data['years'][0]
        self.assertEqual(row['requirements']['allowed_start_years'], [])

    def test_patch_sets_then_empty_or_null_clears_and_other_patches_leave_it(self):
        c = self._cohort(code='sy-patch')
        for sent, stored in (([2025, 2026], [2025, 2026]), ([], []), ([2026], [2026]), (None, [])):
            with self.subTest(sent=sent):
                r = self.client.patch(self._year(c), {'allowed_start_years': sent}, format='json')
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.data['requirements']['allowed_start_years'], stored)
        self.client.patch(self._year(c), {'allowed_start_years': [2025]}, format='json')
        self.client.patch(self._year(c), {'name': 'Renamed'}, format='json')
        c.refresh_from_db()
        self.assertEqual(c.allowed_start_years, [2025])

    def test_a_bad_value_is_refused_and_nothing_is_saved(self):
        for bad in ('2025', 2025, [True], ['2025'], [2025.5], [1999], {'a': 1}):
            with self.subTest(bad=bad):
                c = self._cohort(allowed_start_years=[2026], min_spm_a_count=4)
                r = self.client.patch(self._year(c), {'allowed_start_years': bad, 'min_spm_a_count': 2},
                                      format='json')
                self.assertEqual(r.status_code, 400)
                self.assertEqual((r.data['code'], r.data['field']),
                                 ('bad_requirement', 'allowed_start_years'))
                c.refresh_from_db()
                self.assertEqual((c.allowed_start_years, c.min_spm_a_count), ([2026], 4))

    def test_moving_it_is_audited(self):
        c = self._cohort(code='sy-audit')
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.client.patch(self._year(c), {'allowed_start_years': [2025, 2026]}, format='json')
        line = [m for m in logs.output if 'intake_year_requirements_set' in m]
        self.assertEqual(len(line), 1)
        self.assertIn('allowed_start_years:[]->[2025, 2026]', line[0])
