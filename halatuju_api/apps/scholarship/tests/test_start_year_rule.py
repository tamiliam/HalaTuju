"""H3 (#597, owner 2026-11-15): the per-intake course-start-year rule (`start_year`).

Per gift setting: a 2024 starter in a 2025/2026 intake is caught (red Pathway, a confident
disqualifier, QC's floor); a 2025 starter in an intake with no limit (Sabah) is not; an intake with
no setting is unchanged; an unreadable year is a reviewer line for a person, never a fail.
"""
from django.test import TestCase, override_settings

from apps.scholarship import award, start_year
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
