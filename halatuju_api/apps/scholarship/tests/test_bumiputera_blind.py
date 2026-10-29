"""⚠ THE SCHOLARSHIP SIDE NEVER SEES THE BUMIPUTERA ANSWER (Bumi coverage Sprint B, 2026-10-28).

`StudentProfile.bumiputera` exists for the COURSE GUIDE only — it unlocks Bumiputera-only courses
for a student who said yes. The owner's ruling keeps it out of the scholarship engine and apps,
sponsor views and reports, which is what lets us keep saying we do not collect ethnicity for the
bursary (the s44(6) stance, docs/decisions.md). These tests FAIL the day somebody wires it in:

  * a source scan: no scholarship / reports module reads the field, or selects `*` from the
    profile table (which would carry it along unnamed);
  * the served payloads: the student's own application and a sponsor's pool card carry no such key,
    even for a student whose stored answer is yes.
"""
import re
from pathlib import Path

from django.test import TestCase

from apps.scholarship.tests.factories import make_application, make_student

_APPS = Path(__file__).resolve().parents[2]          # halatuju_api/apps
_READS_FIELD = re.compile(r"""\.bumiputera\b|['"]bumiputera['"]|bumiputera\s*=""")
#: The one legitimate mention: the criteria guard's list of sensitive WORDS (it flags them in
#: funder copy), which is not a read of the student's answer.
_ALLOWED = {('scholarship', 'apply_copy.py')}
#: Every way the code reads ALL profile columns: a PostgREST `rest(…, "api_student_profiles", "*")`
#: call (across line breaks), a `select=*` URL, or SQL `SELECT * / alias.* … FROM api_student_profiles`.
_SELECT_ALL_PROFILES = (
    re.compile(r"""api_student_profiles['"]\s*,\s*['"]\s*\*\s*['"]"""),
    re.compile(r'api_student_profiles\?[^\s\'"]*select=\*'),
    re.compile(r'select\s+(?:\w+\.)?\*\s+from\s+"?api_student_profiles', re.IGNORECASE),
)


def _sources(app):
    for path in (_APPS / app).rglob('*.py'):
        rel = path.relative_to(_APPS / app).parts
        if rel[0] in ('tests', 'migrations'):
            continue
        yield path


def _keys(obj):
    """Every dict key anywhere in a served payload."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _keys(v)


class TestNoScholarshipOrReportCodeReadsIt(TestCase):
    def test_source_scan(self):
        offenders = []
        for app in ('scholarship', 'reports'):
            for path in _sources(app):
                if (app, path.name) in _ALLOWED:
                    continue
                for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                    if _READS_FIELD.search(line):
                        offenders.append(f'{app}/{path.relative_to(_APPS / app)}:{n}')
        self.assertEqual(offenders, [], 'The Bumiputera answer is course-guide only (owner '
                                        'ruling 2026-10-28) — it must not be read here.')

    def test_no_scholarship_or_report_code_reads_the_course_flag_either(self):
        """Bumi Sprint D1: SPM courses carry `CourseRequirement.req_bumiputera` too. The scholarship
        side offers EVERY course (Option A) and reads courses by id, so it has no reason to name the
        flag — a read of it is the first step to filtering a picker by ethnicity."""
        offenders = [f'{app}/{path.relative_to(_APPS / app)}'
                     for app in ('scholarship', 'reports') for path in _sources(app)
                     if 'req_bumiputera' in path.read_text(encoding='utf-8')]
        self.assertEqual(offenders, [])

    def test_nothing_selects_every_profile_column(self):
        """A `select *` from the profile table would carry the answer along without naming it
        (fetch_corpus.py did, into applicants.json — review round, 2026-10-28). Name the columns."""
        offenders = []
        for app in ('scholarship', 'reports'):
            for path in _sources(app):
                text = path.read_text(encoding='utf-8')
                if any(p.search(text) for p in _SELECT_ALL_PROFILES):
                    offenders.append(f'{app}/{path.relative_to(_APPS / app)}')
        self.assertEqual(offenders, [], 'Select named columns from api_student_profiles, never "*".')

    def test_the_select_star_guard_catches_the_shapes_it_must(self):
        for bad in ('rest(b, k, "api_student_profiles", "*")',
                    "_rest(b, k, 'api_student_profiles',\n        '*')",
                    '/rest/v1/api_student_profiles?select=*',
                    'SELECT * FROM "api_student_profiles"',
                    'select p.* from api_student_profiles p'):
            self.assertTrue(any(p.search(bad) for p in _SELECT_ALL_PROFILES), bad)
        self.assertFalse(any(p.search(s) for p in _SELECT_ALL_PROFILES for s in (
            "_rest(b, k, 'api_student_profiles',\n 'supabase_user_id,nric')",)))

    def test_the_eval_corpus_profile_columns_leave_the_answer_out(self):
        from apps.courses.models import StudentProfile
        from apps.scholarship.eval.fetch_corpus import PROFILE_COLS
        cols = PROFILE_COLS.split(',')
        self.assertNotIn('bumiputera', cols)
        known = {f.column for f in StudentProfile._meta.concrete_fields}
        self.assertEqual([c for c in cols if c not in known], [])   # every name is a real column

    def test_the_allowed_file_only_lists_the_word(self):
        """The allow-list entry stays honest: apply_copy mentions the word only as a term to flag."""
        text = (_APPS / 'scholarship' / 'apply_copy.py').read_text(encoding='utf-8')
        self.assertNotIn('.bumiputera', text)


class TestServedPayloadsCarryNoBumiKey(TestCase):
    def setUp(self):
        self.student = make_student(nationality='malaysian', bumiputera=True)
        self.app = make_application('submitted', student=self.student)

    def test_the_students_own_application_payload(self):
        from apps.scholarship.serializers import ApplicationReadSerializer
        keys = set(_keys(ApplicationReadSerializer(self.app).data))
        self.assertFalse({k for k in keys if 'bumi' in k.lower()})

    def test_a_sponsors_pool_card(self):
        from apps.scholarship.serializers import SponsorPoolCardSerializer
        keys = set(_keys(SponsorPoolCardSerializer(self.app).data))
        self.assertFalse({k for k in keys if 'bumi' in k.lower()})
