"""TD-145: the declared institution of a degree pick that stored only `course_id`.

Built 2026-10-03, WIRED 2026-10-04 on the owner's ruling ("Student declares UMK but uploads, say,
UTHM. This should be flagged and student asked to confirm."):

* The resolver (`pathway_engine.catalogue_declared_institution`) answers the entry's question:
  course_id -> the catalogue's ONE campus, or '' (multi-campus is never a guess).
* `_declared_pathway` now uses it, ahead of the free-text pre-U school, so the `pathway_confirm`
  query names the institution the student actually PICKED. It moves no verdict by itself: a
  course_id's institution axis is `offer_pathway.institution_agreement`'s.
* That axis's rule 1 was narrowed the same day: a one-campus course compares the letter with its
  campus, and a letter that POSITIVELY names another catalogue institution is a clash. The test
  that pinned the old blind spot is kept below, its claim reversed.
"""
from django.test import TestCase

from apps.courses.models import Course, CourseInstitution, FieldTaxonomy, Institution
from apps.scholarship import offer_pathway as op
from apps.scholarship.pathway_engine import _declared_pathway, catalogue_declared_institution
from apps.scholarship.tests.factories import make_application

UMK = 'Universiti Malaysia Kelantan'


class _Catalogue(TestCase):
    @classmethod
    def setUpTestData(cls):
        ft = FieldTaxonomy.objects.create(key='td145', name_en='Science', name_ms='Sains',
                                          name_ta='x', image_slug='td145')

        def inst(iid, name, acronym):
            return Institution.objects.create(institution_id=iid, institution_name=name,
                                              acronym=acronym, type='UA', state='Kelantan')

        def course(cid, *campuses):
            c = Course.objects.create(course_id=cid, course='Ijazah Sarjana Muda Sains',
                                      level='Ijazah', department='Sains', field='Sains',
                                      field_key=ft)
            for campus in campuses:
                CourseInstitution.objects.create(course=c, institution=campus)
            return c

        cls.umk = inst('umk', UMK, 'UMK')
        cls.um = inst('um', 'Universiti Malaya', 'UM')
        course('UMK-ONE', cls.umk)                       # one campus
        course('TWO-CAMPUS', cls.umk, cls.um)            # a real question about WHERE

    def _app(self, **cp):
        return make_application('profile_complete', chosen_pathway='ua_degree',
                                chosen_programme={'course_name': 'Ijazah Sarjana Muda Sains', **cp})


class CatalogueDeclaredInstitutionTest(_Catalogue):
    def test_a_one_campus_course_resolves_to_that_campus(self):
        self.assertEqual(catalogue_declared_institution(self._app(course_id='UMK-ONE')), UMK)

    def test_a_multi_campus_course_resolves_to_nothing_never_a_guess(self):
        self.assertEqual(catalogue_declared_institution(self._app(course_id='TWO-CAMPUS')), '')

    def test_nothing_to_resolve(self):
        for cp in ({},                                                       # no course_id
                   {'course_id': 'UMK-ONE', 'institution': 'UMK Jeli'},       # already recorded
                   {'course_id': 'UMK-ONE', 'source': 'offer_letter_auto'},   # the offer's own
                   {'course_id': 'NOT-IN-CATALOGUE'}):                        # a catalogue gap
            with self.subTest(cp=cp):
                self.assertEqual(catalogue_declared_institution(self._app(**cp)), '')


class WiredTest(_Catalogue):
    def test_declared_pathway_declares_the_catalogue_campus(self):
        # WIRED (owner 2026-10-04): a course_id-only pick declares its one campus…
        self.assertEqual(_declared_pathway(self._app(course_id='UMK-ONE')),
                         ('Ijazah Sarjana Muda Sains', UMK))
        # …and a multi-campus pick still declares nothing — never a guess.
        self.assertEqual(_declared_pathway(self._app(course_id='TWO-CAMPUS')),
                         ('Ijazah Sarjana Muda Sains', ''))

    def test_a_genuine_other_university_offer_now_clashes(self):
        # The blind spot this test used to PIN is closed (TD-145 ruled). The signal…
        self.assertTrue(op.offer_contradicts_course_institution('UMK-ONE', 'UNIVERSITI MALAYA'))
        # …is now consulted by the one-campus rule: a letter that names another university clashes.
        self.assertEqual(op.institution_agreement('UMK-ONE', '', 'UNIVERSITI MALAYA'), 'clash')
        # The naming variant the rule exists for stays a match (#48's shape).
        self.assertFalse(op.offer_contradicts_course_institution('UMK-ONE', 'UMK - KAMPUS JELI'))
        self.assertEqual(op.institution_agreement('UMK-ONE', '', 'UMK - KAMPUS JELI'), 'match')
