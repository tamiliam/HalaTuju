"""MARA diplomas and skills / TVET courses in the funding estimate — owner decisions 9-12,
2026-11-07.

Applications come from `test_funding_estimate._Base._app`, so this file adds no direct
`ScholarshipApplication` create. Course shapes are the live ones (ids, levels, semesters).
"""
from apps.courses.models import (
    Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution,
)
from apps.scholarship.funding_estimate import classify_pathway, estimate_funding
from apps.scholarship.tests.test_funding_estimate import _Base


def _course(cid, name, level, semesters, source_type, category=''):
    """One catalogue course offered at one institution of ``category`` (a TVET family)."""
    ft, _ = FieldTaxonomy.objects.get_or_create(key='fe-tvet', defaults={
        'name_en': 'x', 'name_ms': 'x', 'name_ta': 'x', 'image_slug': 'fe-tvet'})
    inst, _ = Institution.objects.get_or_create(
        institution_id=f'FE-{category or source_type}', defaults={
            'institution_name': f'Institut {category or source_type}', 'type': 'x',
            'state': 'Selangor', 'category': category})
    c = Course.objects.create(course_id=cid, course=name, level=level, department='x',
                              field='x', field_key=ft, semesters=semesters)
    CourseInstitution.objects.create(course=c, institution=inst)
    CourseRequirement.objects.create(course=c, source_type=source_type)
    return {'course_id': cid, 'course_name': name}


class TestMaraDiploma(_Base):
    def test_uitm_diploma_stays_university(self):
        app = self._app(chosen_pathway='university', pathway_certainty='sure',
                        chosen_programme={'course_id': 'UE4010001',
                                          'course_name': 'Diploma Pengurusan Perniagaan'})
        self.assertEqual(classify_pathway(app), 'university')

    def test_kolej_profesional_mara_diploma(self):
        app = self._app(chosen_pathway='university', pathway_certainty='sure',
                        chosen_programme={'course_id': 'OP4520001',
                                          'course_name': 'Diploma Perakaunan'})
        est = estimate_funding(app)
        self.assertEqual(est['pathway'], 'mara_diploma')
        # Same numbers as a public-university diploma.
        self.assertEqual((est['monthly'], est['months'], est['total'], est['variable'],
                          est['practical']), (220, 30, 6600, True, True))

    def test_mara_tvet_diploma(self):
        prog = _course('TVET-90001', 'Diploma Teknologi Automotif', 'Diploma', 6, 'tvet', 'MARA')
        self.assertEqual(classify_pathway(self._app(chosen_programme=prog)), 'mara_diploma')

    def test_mara_code_with_named_diploma_and_no_id(self):
        app = self._app(chosen_pathway='mara',
                        chosen_programme={'course_name': 'Diploma Teknologi Elektrik'})
        self.assertEqual(classify_pathway(app), 'mara_diploma')

    def test_mara_degree_follows_the_degree_rule(self):
        app = self._app(chosen_pathway='mara',
                        chosen_programme={'course_name': 'Ijazah Sarjana Muda Kejuruteraan'})
        self.assertEqual(classify_pathway(app), 'degree')


class TestSkillsInstitutes(_Base):
    def _est(self, **kw):
        return estimate_funding(self._app(**kw))

    def test_228_ikbn_shape(self):
        prog = _course('IKBN-CET-015', 'Sijil Lanjutan Teknologi Hospitaliti (Penyediaan Pastri)',
                       'Sijil Lanjutan', 4, 'tvet', 'ILKBS')
        est = self._est(chosen_pathway='ilkbs', pathway_certainty='sure', chosen_programme=prog)
        self.assertEqual(est, {'pathway': 'ilkbs', 'known': True, 'monthly': 350, 'months': 24,
                               'total': 8400, 'variable': False, 'practical': False})

    def test_tvet_id_in_the_ilkbs_family(self):
        prog = _course('TVET-90002', 'Sijil Kimpalan', 'Sijil', 3, 'tvet', 'ILKBS')
        est = self._est(chosen_programme=prog)
        self.assertEqual((est['pathway'], est['months'], est['total']), ('ilkbs', 18, 6300))

    def test_no_semesters_falls_back_to_24(self):
        prog = _course('IKBN-CET-999', 'Sijil Elektrik', 'Sijil', None, 'tvet', 'ILKBS')
        est = self._est(chosen_programme=prog)
        self.assertEqual((est['pathway'], est['months']), ('ilkbs', 24))

    def test_485_kolej_komuniti_shape(self):
        prog = _course('KKOM-CET-016', 'Sijil Pengoperasian Perniagaan', 'Sijil', 4, 'kkom')
        est = self._est(chosen_pathway='kkom', pathway_certainty='sure', chosen_programme=prog)
        self.assertEqual(est, {'pathway': 'kkom', 'known': True, 'monthly': 450, 'months': 24,
                               'total': 10800, 'variable': False, 'practical': False})

    def test_529_iljtm_shape(self):
        prog = _course('IJTM-CET-033', 'Sijil Teknologi Penyelenggaraan Mekanikal', 'Sijil', 5,
                       'tvet', 'ILJTM')
        est = self._est(chosen_pathway='iljtm', pathway_certainty='sure', chosen_programme=prog)
        self.assertEqual((est['pathway'], est['monthly'], est['months'], est['total']),
                         ('iljtm', 450, 30, 13500))

    def test_kolej_komuniti_by_name_without_an_id(self):
        app = self._app(chosen_programme={'course_name': 'Sijil Kulinari, Kolej Komuniti Selayang'})
        self.assertEqual(classify_pathway(app), 'kkom')


class TestOtherTvet(_Base):
    def test_450_mara_certificate_shape(self):
        # #450: chosen_pathway 'mara', TVET-30721 "Jahitan Pakaian dan Fesyen", Sijil, 1 semester.
        prog = _course('TVET-30721', 'Jahitan Pakaian dan Fesyen', 'Sijil', 1, 'tvet', 'MARA')
        est = estimate_funding(self._app(chosen_pathway='mara', pathway_certainty='sure',
                                         chosen_programme=prog))
        self.assertEqual(est, {'pathway': 'mara_cert', 'known': True, 'monthly': 450,
                               'months': 6, 'total': 2700, 'variable': False,
                               'practical': False})

    def test_tvet_id_in_another_family(self):
        prog = _course('TVET-90003', 'Sijil Penyelenggaraan', 'Sijil', 2, 'tvet', 'TVET')
        est = estimate_funding(self._app(chosen_programme=prog))
        self.assertEqual((est['pathway'], est['monthly'], est['months'], est['total']),
                         ('tvet', 450, 12, 5400))

    def test_tvet_id_not_in_the_catalogue(self):
        app = self._app(chosen_programme={'course_id': 'TVET-00000', 'course_name': 'Sijil X'})
        self.assertEqual(estimate_funding(app)['pathway'], 'tvet')

    def test_bare_tvet_pathway_without_a_course_is_24_months(self):
        est = estimate_funding(self._app(chosen_pathway='tvet'))
        self.assertEqual((est['pathway'], est['months'], est['total']), ('tvet', 24, 10800))

    def test_mara_code_without_a_programme_is_a_certificate(self):
        self.assertEqual(classify_pathway(self._app(chosen_pathway='mara')), 'mara_cert')

    def test_mara_code_keeps_a_readable_asasi(self):
        app = self._app(chosen_pathway='mara',
                        chosen_programme={'course_id': 'OM0010001', 'course_name': 'Asasi Sains'})
        self.assertEqual(classify_pathway(app), 'asasi')

    def test_unknown_stays_unknown(self):
        self.assertFalse(estimate_funding(self._app())['known'])
        many = self._app(pathway_certainty='uncertain', pathways_considered=['iljtm', 'mara'])
        self.assertEqual(classify_pathway(many), 'unknown')
