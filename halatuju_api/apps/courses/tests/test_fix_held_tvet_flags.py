"""`fix_held_tvet_flags` (Bumi F1b): the fix file is reproducible from the committed source, the fixture
mirrors prod AFTER the fix, and the command is a dry run by default, writes only the three flags it
lists, refuses the whole run on any stale `old` or missing course (compare-and-set), and `--reverse`
is an exact rollback."""
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.management.commands.ingest_tvet_courses import held_courses_from_fixtures, load_held_links
from apps.courses.models import CourseRequirement
from apps.courses.tvet_held_flags import FLAGS, before_fix, build_flag_fix, changes

DATA = Path(__file__).resolve().parents[3] / 'data' / 'tvet'
FIX = DATA / 'held_flag_fix_F1b.json'


def _fix():
    return json.loads(FIX.read_text(encoding='utf-8'))


def _run(*args):
    out = StringIO()
    call_command('fix_held_tvet_flags', *args, stdout=out, stderr=out)
    return out.getvalue()


class TestFixFile:
    def test_rebuilt_byte_for_byte_from_the_committed_source(self):
        fix = _fix()
        source = json.loads((DATA / 'uptvet_F1_source.json').read_text(encoding='utf-8'))
        links = DATA / 'held_tvet_links.json'
        prod_links = json.loads(links.read_text(encoding='utf-8'))['links']
        f1 = json.loads((DATA / 'tvet_new_courses_F1.json').read_text(encoding='utf-8'))
        f1_new = [x for x in f1['held_links'] if not x['already_linked']]
        rebuilt = build_flag_fix(source, load_held_links(links), prod_links, f1_new,
                                 before_fix(held_courses_from_fixtures(), fix))
        assert json.loads(json.dumps(rebuilt, ensure_ascii=False)) == fix

    def test_the_fixture_mirrors_prod_after_the_fix(self):
        held = held_courses_from_fixtures()
        for course in _fix()['courses']:
            assert {f: held[course['course_id']]['requirement'][f] for f in FLAGS} == course['new']

    def test_only_prod_linked_courses_and_only_the_three_flags(self):
        fix = _fix()
        prod = {x['course_id'] for x in json.loads((DATA / 'held_tvet_links.json').read_text(encoding='utf-8'))['links']}
        ids = [c['course_id'] for c in fix['courses']]
        assert len(ids) == len(set(ids)) and set(ids) <= prod and 'IKBN-DIP-002' not in ids
        assert all(set(c['old']) == set(c['new']) == set(FLAGS) for c in fix['courses'])
        assert not any(x['field'] in FLAGS for x in fix['not_applied'])
        assert {c['course_id'] for c in fix['courses']}.isdisjoint(c['course_id'] for c in fix['no_page'])

    def test_a_conflict_is_never_changed(self):
        fix = _fix()
        by_id = {c['course_id']: c for c in fix['courses']}
        assert fix['conflicts']
        for conflict in fix['conflicts']:
            course = by_id[conflict['course_id']]
            assert course['new'][conflict['flag']] == course['old'][conflict['flag']]
            assert len({p['value'] for p in conflict['pages']}) > 1 or not all(p['conditions_read'] for p in conflict['pages'])

    def test_every_change_follows_its_pages_unanimously(self):
        conflicted = {(x['course_id'], x['flag']) for x in _fix()['conflicts']}
        for course in _fix()['courses']:
            for flag in FLAGS:
                if (course['course_id'], flag) not in conflicted:
                    assert {p['page'][flag] for p in course['campuses']} == {course['new'][flag]}

    def test_the_counts(self):
        per_flag = _fix()['counts']['per_flag']
        assert per_flag['req_malaysian'] == {'false_to_true': 63, 'true_to_false': 0, 'unchanged': 0, 'conflict': 0}
        assert per_flag['no_colorblind'] == {'false_to_true': 16, 'true_to_false': 0, 'unchanged': 43, 'conflict': 4}
        assert per_flag['no_disability'] == {'false_to_true': 0, 'true_to_false': 63, 'unchanged': 0, 'conflict': 0}
        assert len(changes(_fix())) == 142


def _snapshot():
    return {r['course_id']: r for r in CourseRequirement.objects.values()}


def _set(fix, side):
    """Put the DB's listed courses on the file's `old` (prod before the fix) or `new` side."""
    for course in fix['courses']:
        CourseRequirement.objects.filter(course_id=course['course_id']).update(**course[side])


def _write(tmp_path, fix):
    path = tmp_path / 'fix.json'
    path.write_text(json.dumps(fix, ensure_ascii=False), encoding='utf-8')
    return str(path)


@pytest.fixture
def prod_before(db):
    """The catalogue as prod holds it BEFORE the fix (the fixture carries the fix already)."""
    call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
    _set(_fix(), 'old')


@pytest.mark.django_db
class TestCommand:
    def test_dry_run_writes_nothing(self, prod_before):
        before = _snapshot()
        out = _run('--file', str(FIX))
        assert 'DRY RUN' in out and '142 flag change(s) on 63 course(s)' in out
        assert 'IJTM-CET-004 req_malaysian: False -> True' in out
        assert _snapshot() == before

    def test_apply_changes_exactly_the_listed_flags(self, prod_before):
        before = _snapshot()
        out = _run('--file', str(FIX), '--apply')
        assert 'Applied 142 flag change(s) on 63 course(s).' in out
        after = _snapshot()
        moved = {(cid, k, before[cid][k], after[cid][k]) for cid in before for k in before[cid]
                 if before[cid][k] != after[cid][k]}
        assert moved == set(changes(_fix()))

    def test_refuses_the_whole_run_on_a_stale_old(self, prod_before, tmp_path):
        fix = _fix()
        CourseRequirement.objects.filter(course_id='IJTM-CET-005').update(no_colorblind=False)   # file: old True
        before = _snapshot()
        with pytest.raises(CommandError, match='1 mismatch'):
            _run('--file', str(FIX), '--apply')
        assert _snapshot() == before
        # every mismatch is printed, not just the first
        fix['courses'][0]['old']['no_disability'] = not fix['courses'][0]['old']['no_disability']
        out = StringIO()
        with pytest.raises(CommandError, match='2 mismatch'):
            call_command('fix_held_tvet_flags', '--file', _write(tmp_path, fix), '--apply', stdout=out, stderr=out)
        assert 'IJTM-CET-005.no_colorblind: database has False, the file expects True' in out.getvalue()
        assert f"{fix['courses'][0]['course_id']}.no_disability" in out.getvalue()
        assert _snapshot() == before

    def test_refuses_a_missing_course(self, prod_before, tmp_path):
        fix = _fix()
        fix['courses'].append({**fix['courses'][0], 'course_id': 'IJTM-CET-999'})
        before = _snapshot()
        with pytest.raises(CommandError):
            out = StringIO()
            call_command('fix_held_tvet_flags', '--file', _write(tmp_path, fix), '--apply', stdout=out, stderr=out)
        assert _snapshot() == before

    def test_reverse_restores_exactly(self, prod_before):
        before = _snapshot()
        _run('--file', str(FIX), '--apply')
        assert _snapshot() != before
        with pytest.raises(CommandError):   # applying twice is refused: the database no longer holds `old`
            _run('--file', str(FIX), '--apply')
        out = _run('--file', str(FIX), '--reverse', '--apply')
        assert 'Applied 142 flag change(s)' in out
        assert _snapshot() == before

    def test_a_column_the_file_does_not_list_is_never_written(self, prod_before, tmp_path):
        fix = _fix()
        course = fix['courses'][0]
        cid = course['course_id']
        # A file that also names another column in old / new: only the three flags are ever written.
        course['old']['three_m_only'], course['new']['three_m_only'] = False, True
        CourseRequirement.objects.filter(course_id=cid).update(three_m_only=False)
        before = _snapshot()
        _run('--file', _write(tmp_path, fix), '--apply')
        after = _snapshot()
        assert after[cid]['three_m_only'] is False
        unlisted = set(before) - {c['course_id'] for c in fix['courses']}
        assert all(after[c] == before[c] for c in unlisted)
        assert {k for c in before for k in before[c] if before[c][k] != after[c][k]} <= set(FLAGS)

    def test_the_read_only_check_sql_returns_only_mismatches(self, prod_before):
        from django.db import connection
        sql = _run('--file', str(FIX), '--sql').strip()
        words = set(sql.upper().replace('(', ' ').replace(',', ' ').split())
        assert not words & {'UPDATE', 'INSERT', 'DELETE', 'DROP', 'ALTER', 'TRUNCATE', 'CREATE'}
        assert sql.count("('I") == 63

        def rows():
            with connection.cursor() as cursor:
                cursor.execute(sql.rstrip(';'))
                return cursor.fetchall()
        assert rows() == []
        CourseRequirement.objects.filter(course_id='IJTM-CET-005').update(no_colorblind=False)
        CourseRequirement.objects.filter(course_id='IKBN-DIP-006').delete()
        assert [r[:2] for r in rows()] == [('IJTM-CET-005', 0), ('IKBN-DIP-006', 1)]
