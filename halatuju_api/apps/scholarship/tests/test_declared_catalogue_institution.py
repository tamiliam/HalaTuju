"""TD-145 (2026-10-03): the declared institution of a degree pick that stored only `course_id`.

BUILT, NOT WIRED — and why, so the next reader does not "finish the job" blind:

* The resolver (`pathway_engine.catalogue_declared_institution`) answers the entry's question:
  course_id -> the catalogue's ONE campus, or '' (multi-campus is never a guess).
* Wiring it into `_declared_pathway`, as the entry proposed in June, would move NO verdict today.
  Since #48 (2026-07-25) a course_id's institution axis is decided by
  `offer_pathway.institution_agreement`, and its rule 1 answers 'match' for a one-campus course
  WITHOUT comparing — so `declared_institution` never reaches the comparison for these records.
* The switch that WOULD catch a genuine wrong-university offer is that rule 1 itself
  (`offer_contradicts_course_institution` already exists to say "this names another place").
  It reverses an owner rule, so it waits on the owner and on the lead's read-only probe
  (scratchpad `batch3_probe.py`). The PINNED test below is today's blind spot, on purpose: when
  the owner rules, it is edited deliberately, never quietly.
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


class HeldWiringTest(_Catalogue):
    def test_declared_pathway_is_unchanged_until_the_switch(self):
        # The wiring is HELD: a course_id-only pick still declares no institution.
        self.assertEqual(_declared_pathway(self._app(course_id='UMK-ONE')),
                         ('Ijazah Sarjana Muda Sains', ''))

    def test_PINNED_a_genuine_other_university_offer_reads_match_today(self):
        # ⚠ PINNED BLIND SPOT (TD-145, owner's ruling pending). The signal exists…
        self.assertTrue(op.offer_contradicts_course_institution('UMK-ONE', 'UNIVERSITI MALAYA'))
        # …and the one-campus rule does not consult it.
        self.assertEqual(op.institution_agreement('UMK-ONE', '', 'UNIVERSITI MALAYA'), 'match')
        # The naming variant the rule exists for stays a match either way (#48's shape).
        self.assertFalse(op.offer_contradicts_course_institution('UMK-ONE', 'UMK - KAMPUS JELI'))
