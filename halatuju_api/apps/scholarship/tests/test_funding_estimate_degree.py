"""The degree (post-STPM) funding estimate — owner decisions 2-6, 2026-11-07.

Applications come from `test_funding_estimate._Base._app` (one fresh cohort per call, year
2026 + n), so this file adds no direct `ScholarshipApplication` create.
"""
from datetime import date

from apps.courses.models import FieldTaxonomy, Institution, StpmCourse
from apps.scholarship.funding_estimate import classify_pathway, estimate_funding
from apps.scholarship.tests.test_funding_estimate import _Base

#: #278's course (prod `stpm_courses`: UH6145006, stream 'arts').
EDU = ('UH6145006', 'Ijazah Sarjana Muda Pendidikan dengan Kepujian (Sejarah) #', 'arts')


def _degree(cid, name, stream):
    ft, _ = FieldTaxonomy.objects.get_or_create(key='fe-degree', defaults={
        'name_en': 'x', 'name_ms': 'x', 'name_ta': 'x', 'image_slug': 'fe-degree'})
    inst, _ = Institution.objects.get_or_create(institution_id='RA-FE', defaults={
        'institution_name': 'Universiti Ujian', 'type': 'IPTA', 'state': 'Selangor'})
    StpmCourse.objects.get_or_create(course_id=cid, defaults={
        'course_name': name, 'university': inst.institution_name, 'institution': inst,
        'field_key': ft, 'stream': stream})
    return {'course_id': cid, 'course_name': name}


class TestDegreeEstimate(_Base):
    def _degree_app(self, cid, name, stream, **kw):
        return self._app(chosen_pathway='university', pathway_certainty='sure',
                         chosen_programme=_degree(cid, name, stream), **kw)

    def test_278_education_degree(self):
        # Arts: 1,200 x 10 + 2,900 - 6,180 = 8,720/yr; Pendidikan = 4 years.
        est = estimate_funding(self._degree_app(*EDU))
        self.assertEqual(est, {'pathway': 'degree', 'known': True, 'monthly': 872, 'months': 40,
                               'total': 34900, 'variable': True, 'practical': False,
                               'study_months': True, 'continuing': False})

    def test_science_degree_is_four_years_at_the_science_loan(self):
        # 12,000 + 2,900 - 6,650 = 8,250/yr x 4.
        est = estimate_funding(self._degree_app('UK0001', 'Ijazah Sarjana Muda Sains Kimia',
                                                'science'))
        self.assertEqual((est['monthly'], est['months'], est['total']), (825, 40, 33000))

    def test_arts_degree_is_three_years(self):
        est = estimate_funding(self._degree_app('UK0002', 'Ijazah Sarjana Muda Sejarah', 'arts'))
        self.assertEqual((est['monthly'], est['months'], est['total']), (872, 30, 26200))

    def test_both_stream_reads_as_unknown(self):
        # stpm_courses.stream also holds 'both' (331 courses): the arts loan, the default 4 years.
        est = estimate_funding(self._degree_app('UK0003', 'Ijazah Sarjana Muda Pengurusan',
                                                'both'))
        self.assertEqual((est['monthly'], est['months'], est['total']), (872, 40, 34900))

    def test_medicine_and_dentistry_are_five_years(self):
        for cid, name in (('UK0004', 'Doktor Perubatan'),
                          ('UK0005', 'Sarjana Muda Perubatan dan Pembedahan'),
                          ('UK0006', 'Doktor Pembedahan Pergigian')):
            est = estimate_funding(self._degree_app(cid, name, 'science'))
            self.assertEqual(est['months'], 50, name)

    def test_allied_health_is_not_medicine(self):
        est = estimate_funding(self._degree_app('UK0007', 'Ijazah Sarjana Muda Sains Bioperubatan',
                                                'science'))
        self.assertEqual(est['months'], 40)

    def test_251_named_degree_with_stale_stpm_code(self):
        # #251: chosen_pathway 'stpm' left over, programme a degree with no catalogue id.
        app = self._app(chosen_pathway='stpm', pathway_certainty='uncertain',
                        pathways_considered=['university', 'pismp'],
                        chosen_programme={'course_name': 'SARJANA MUDA SAINS GUNAAN (SAINS SUMBER '
                                                         'ASLI) DENGAN KEPUJIAN'})
        self.assertEqual(classify_pathway(app), 'degree')
        est = estimate_funding(app)
        self.assertEqual((est['monthly'], est['months'], est['total']), (872, 40, 34900))

    def test_133_named_degree_with_blank_code(self):
        app = self._app(chosen_pathway='', pathway_certainty='sure', pathways_considered=['stpm'],
                        chosen_programme={'course_name': 'SARJANA MUDA PENTADBIRAN PERNIAGAAN '
                                                         '(LOGISTIK DAN PENGANGKUTAN) DENGAN KEPUJIAN'})
        self.assertEqual(classify_pathway(app), 'degree')

    def test_pismp_degree_stays_pismp(self):
        app = self._app(chosen_programme={'course_id': '',
                                          'course_name': 'Ijazah Sarjana Muda Perguruan'})
        self.assertEqual(classify_pathway(app), 'pismp')

    def test_ua_diploma_stays_university(self):
        app = self._app(chosen_pathway='university', pathway_certainty='sure',
                        chosen_programme={'course_id': 'UH4010001',
                                          'course_name': 'Diploma Pengurusan'})
        self.assertEqual(estimate_funding(app)['pathway'], 'university')
        self.assertNotIn('study_months', estimate_funding(app))


class TestContinuingDegree(_Base):
    def _started(self, years_before):
        app = self._app(chosen_pathway='university', pathway_certainty='sure',
                        chosen_programme=_degree(*EDU))
        app.reporting_date = date(app.cohort.year - years_before, 9, 1)
        app.save(update_fields=['reporting_date'])
        return app

    def test_continuing_student_is_estimated_for_the_years_left(self):
        est = estimate_funding(self._started(1))
        self.assertEqual((est['months'], est['total'], est['continuing']), (30, 26200, True))

    def test_started_this_year_is_full_length(self):
        est = estimate_funding(self._started(0))
        self.assertEqual((est['months'], est['continuing']), (40, False))

    def test_unknown_start_is_full_length(self):
        est = estimate_funding(self._app(chosen_pathway='university', pathway_certainty='sure',
                                         chosen_programme=_degree(*EDU)))
        self.assertEqual((est['months'], est['continuing']), (40, False))

    def test_years_left_floor_at_one(self):
        est = estimate_funding(self._started(9))
        self.assertEqual((est['months'], est['total'], est['continuing']), (10, 8700, True))
