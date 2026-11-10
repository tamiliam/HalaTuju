"""A3.6 / TD-434 drift pin: how a TVET course gets its pathway at startup.

`CoursesConfig._load_data` gives a TVET course the pathway of the FIRST offering (CourseInstitution
row, as the query returns them) whose institution's category is a TVET category; a TVET course with
no such offering falls back to 'tvet'. TD-434 is still OPEN: a course taught under two categories
shows only one of them, and "first" rests on the database's row order (the query has no order_by:
SQLite walks the course+institution unique index, Postgres may return physical order). This test does
not fix that. It pins today's behaviour per course, so a refactor cannot change it silently; the
TD-434 fix must update this test on purpose. Each pattern position has its own institution, numbered
in creation order, so the pin holds whether "first" means creation order or institution-id order.
"""
import hashlib
from unittest import mock

from django.apps import apps
from django.test import TestCase

from apps.courses.models import Course, CourseInstitution, CourseRequirement, Institution
from apps.courses.tests.conftest import load_requirements_df
from apps.courses.tvet_families import TVET_CATEGORY_PATHWAY, TVET_PATHWAYS

_STATE = ('requirements_df', 'course_tags_df', 'course_tags_map', 'inst_modifiers_map',
          'inst_subcategories', 'course_pathway_map', '_last_retry_at')

# Categories used; 'IPTA' and '' are NOT TVET categories.
_CATEGORIES = ('MARA', 'ILJTM', 'ILKBS', 'TVET', 'IPTA', '')
_MAX_POSITIONS = 3


def _inst_id(position, category):
    return f'TD434-{position}-{category or "BLANK"}'

# Offering patterns, in the order the rows are created. Each mixes TVET and non-TVET categories
# so the "first TVET category wins" and the 'tvet' fallback are both exercised.
_PATTERNS = (
    (),
    ('IPTA',),
    ('',),
    ('MARA',),
    ('ILJTM',),
    ('ILKBS',),
    ('TVET',),
    ('ILJTM', 'MARA'),
    ('MARA', 'ILJTM'),
    ('IPTA', 'ILKBS'),
    ('TVET', 'ILKBS', 'MARA'),
    ('', 'IPTA'),
    ('ILKBS', 'TVET'),
)


def _pattern_for(course_id):
    n = int(hashlib.sha256(course_id.encode('utf-8')).hexdigest()[:8], 16)
    return _PATTERNS[n % len(_PATTERNS)]


def _expected(pattern):
    """The pinned rule, written out independently of the loader: first TVET category, else 'tvet'."""
    for category in pattern:
        if category in TVET_CATEGORY_PATHWAY:
            return TVET_CATEGORY_PATHWAY[category]
    return 'tvet'


class TestTvetPathwayFirstCategoryWins(TestCase):
    fixtures = ['courses', 'requirements']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_requirements_df()

    def setUp(self):
        self.config = apps.get_app_config('courses')
        saved = {k: self.config.__dict__.get(k, mock.sentinel.absent) for k in _STATE}

        def restore():
            for k, v in saved.items():
                if v is mock.sentinel.absent:
                    self.config.__dict__.pop(k, None)
                else:
                    setattr(self.config, k, v)
        self.addCleanup(restore)
        for position in range(_MAX_POSITIONS):
            for category in _CATEGORIES:
                iid = _inst_id(position, category)
                Institution.objects.create(institution_id=iid, institution_name=f'Inst {iid}',
                                           type='TVET', category=category, state='Selangor')

    def _offer(self, course_id, pattern):
        for position, category in enumerate(pattern):
            CourseInstitution.objects.create(course_id=course_id,
                                             institution_id=_inst_id(position, category))

    def test_every_tvet_course_takes_its_first_tvet_category_else_tvet(self):
        tvet_ids = sorted(CourseRequirement.objects.filter(source_type='tvet')
                          .values_list('course_id', flat=True))
        self.assertGreater(len(tvet_ids), 100)
        expected = {}
        for cid in tvet_ids:
            pattern = _pattern_for(cid)
            self._offer(cid, pattern)
            expected[cid] = _expected(pattern)
        self.assertEqual(set(expected.values()), set(TVET_PATHWAYS) | {'tvet'})

        self.config._load_data()
        got = {cid: self.config.course_pathway_map.get(cid) for cid in tvet_ids}
        wrong = {cid: (got[cid], expected[cid]) for cid in tvet_ids if got[cid] != expected[cid]}
        self.assertEqual(wrong, {}, 'TD-434 behaviour drifted: course -> (got, pinned)')

    def test_a_course_under_two_categories_shows_only_the_first(self):
        cid = CourseRequirement.objects.filter(source_type='tvet').order_by('course_id')[0].course_id
        self._offer(cid, ('ILJTM', 'MARA'))
        self.config._load_data()
        self.assertEqual(self.config.course_pathway_map[cid], 'iljtm')

    def test_non_tvet_courses_ignore_their_offerings(self):
        req = CourseRequirement.objects.exclude(source_type='tvet').order_by('course_id')[0]
        self.config._load_data()
        before = self.config.course_pathway_map[req.course_id]
        self._offer(req.course_id, ('MARA',))
        self.config._load_data()
        self.assertEqual(self.config.course_pathway_map[req.course_id], before)
        self.assertTrue(Course.objects.filter(course_id=req.course_id).exists())
