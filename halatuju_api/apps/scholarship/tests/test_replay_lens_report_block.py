"""LL5 phase C2d - `parent.main` prints the human lens and the coach grade, as `report_lens` renders them,
between two fixed marker lines, after the JSON lines, and only with `--human-lens`.

`main` runs with the preflight and Django set-up stubbed; a stand-in `run_replay` prints fixed JSON
lines (as the real one does, to stdout) and answers a made-up result. Made-up data only; the planted
name never reaches stdout or stderr."""
import copy
import logging

import pytest

from apps.scholarship.eval.replay import coach_rows, guards, parent
from apps.scholarship.eval.replay import lens_human as L
from apps.scholarship.eval.replay import report_lens as R
from apps.scholarship.fact_bands import CERTAIN
from apps.scholarship.tests.test_replay_harness import INSTANT
from apps.scholarship.tests.test_replay_report_lens import PLANT, coach_clean, coach_one_pair, lens_clean, lens_debug

#: What the stand-in `run_replay` prints: the run's JSON lines, as today.
JSON_LINES = ('{"event": "start", "months": ["2026-11", "2026-12"], "snapshot_joined": true}',
              '{"engine": "same", "event": "totals", "same": 1}')
TODAY = ''.join(line + '\n' for line in JSON_LINES)
TOTALS = {'same': {'same': 1}}


@pytest.fixture
def main_run(monkeypatch, request, capsys):
    """``run(result, *argv, raises=None)`` -> (exit code, stdout, stderr). ``argv`` follows the two
    required arguments; ``raises`` makes the stand-in `run_replay` raise after its JSON lines."""
    request.addfinalizer(lambda level=logging.root.manager.disable: logging.disable(level))
    monkeypatch.setattr(guards, 'check_environment', lambda env: True)
    monkeypatch.setattr(guards, 'check_database_url', lambda url: ('localhost', 5432))
    monkeypatch.setattr(parent, 'setup_django', lambda: None)

    def run(result, *argv, raises=None):
        def run_replay(args, env):
            for line in JSON_LINES:
                print(line)
            if raises is not None:
                raise raises
            return result
        monkeypatch.setattr(parent, 'run_replay', run_replay)
        capsys.readouterr()
        try:
            code = parent.main(['--instant', INSTANT, '--months', '2026-11,2026-12', *argv])
        except SystemExit as stop:                                  # main lets argparse's exit through
            code = ('SystemExit', stop.code)
        out, err = capsys.readouterr()
        return code, out, err
    return run


def lens_on(folder):
    return ['--human-lens', '--human-lens-exam-folder', str(folder)]


def block_of(lens, coach):
    """The block the renderer gives for these two results, marker lines around it."""
    return '\n'.join([parent.LENS_REPORT_START, *R.lens_coach_section_lines(lens, coach), parent.LENS_REPORT_END]) + '\n'


def coach_passing():
    return coach_one_pair([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)])


def planted(result, path, value):
    result = copy.deepcopy(result)
    target = result
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return result


def assert_no_block(out, err):
    for marker in (parent.LENS_REPORT_START, parent.LENS_REPORT_END):
        assert marker not in out and marker not in err


# ── the markers ───────────────────────────────────────────────────────────────────────────────────────
def test_the_marker_lines_are_the_two_fixed_texts():
    assert parent.LENS_REPORT_START == '=== LL5 lens report start ==='
    assert parent.LENS_REPORT_END == '=== LL5 lens report end ==='


def test_the_render_errors_are_a_narrow_fixed_set_and_the_failure_line_is_fixed_words():
    assert R.RENDER_ERRORS == (LookupError, TypeError, ValueError, AttributeError)
    assert Exception not in R.RENDER_ERRORS and BaseException not in R.RENDER_ERRORS
    assert R.RENDER_FAILED_LINE == 'lens report failed. BLOCKING. There is no result, so this is not a pass.'


# ── lens on: the block after the JSON lines ───────────────────────────────────────────────────────────
def test_lens_on_clean_prints_the_rendered_block_after_the_json_lines_and_nothing_after(main_run, tmp_path):
    lens, coach = lens_clean(tmp_path), coach_passing()
    code, out, err = main_run({**TOTALS, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: coach},
                              *lens_on(tmp_path))
    assert code == 0 and err == ''
    assert out == TODAY + block_of(lens, coach)
    assert out.endswith(parent.LENS_REPORT_END + '\n') and out.count(parent.LENS_REPORT_START) == 1
    assert 'No blocking item.' in out and R.BLOCKING not in out.split(parent.LENS_REPORT_START)[1]


def test_a_coach_pair_graded_fail_is_blocking_in_the_block_and_keeps_its_exit_code(main_run, tmp_path):
    lens, coach = lens_clean(tmp_path), coach_clean()       # one pair graded fail
    code, out, _err = main_run({**TOTALS, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: coach},
                               *lens_on(tmp_path))
    assert out == TODAY + block_of(lens, coach) and 'BLOCKING: 1 item(s): coach pair ' in out
    assert code == 0                                                # exit codes unchanged by this phase


def test_lens_off_is_byte_identical_and_prints_no_marker(main_run):
    code, out, err = main_run(TOTALS)
    assert (code, out, err) == (0, TODAY, '')
    assert_no_block(out, err)
    code, out, err = main_run({})                                   # --counts-only answers {}
    assert (code, out, err) == (0, TODAY, '')


def test_counts_only_with_the_lens_on_prints_no_block(main_run, tmp_path):
    code, out, err = main_run({}, '--counts-only', *lens_on(tmp_path))
    assert (code, out, err) == (0, TODAY, '')


# ── failures never look like results ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('which, path, value', [
    ('lens', ('note',), PLANT), ('lens', ('exams', L.EXAM_1, 'status'), PLANT),
    ('coach', ('note',), PLANT), ('coach', ('months', 0, 'version'), PLANT)])
def test_a_planted_bad_result_shows_only_the_schema_failure_and_exits_4(main_run, tmp_path, which, path, value):
    lens, coach = lens_clean(tmp_path), coach_passing()
    if which == 'lens':
        lens = planted(lens, path, value)
    else:
        coach = planted(coach, path, value)
    code, out, err = main_run({**TOTALS, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: coach},
                              *lens_on(tmp_path))
    assert code == parent.HUMAN_LENS_FAILED_EXIT == 4
    assert out == TODAY + block_of(lens, coach)
    prefix = 'lens failed' if which == 'lens' else 'coach grade failed'
    assert f'- {prefix}: schema. {R.BLOCKING}.' in out
    assert PLANT not in out and PLANT not in err and err == ''


@pytest.mark.parametrize('lens_error, coach_error', [
    ('BadCaseRow', None), (None, 'LookupError'), ('no_output', 'bad_output')])
def test_an_error_result_shows_its_failure_form_and_exits_4(main_run, tmp_path, lens_error, coach_error):
    lens = {'error': lens_error} if lens_error else lens_clean(tmp_path)
    coach = {'error': coach_error} if coach_error else coach_passing()
    code, out, err = main_run({**TOTALS, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: coach},
                              *lens_on(tmp_path))
    assert code == 4 and err == '' and out == TODAY + block_of(lens, coach)
    if lens_error:
        assert f'- lens failed: {lens_error}. {R.BLOCKING}.' in out
    if coach_error:
        assert f'- coach grade failed: {coach_error}. {R.BLOCKING}.' in out


def test_a_refusal_shows_not_run_and_exits_0(main_run, tmp_path):
    lens, coach = lens_debug(tmp_path), coach_rows.coach_debug_refusal()
    code, out, err = main_run({**TOTALS, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: coach},
                              *lens_on(tmp_path))
    assert (code, err) == (0, '') and out == TODAY + block_of(lens, coach)
    assert out.count('- not run: debug_on.') == 3 and R.BLOCKING not in out


@pytest.mark.parametrize('error_class', [KeyError, IndexError, TypeError, ValueError, AttributeError])
def test_a_render_that_raises_prints_only_the_fixed_failure_and_exits_4(main_run, tmp_path, monkeypatch,
                                                                         error_class):
    def broken(*_a, **_k):
        raise error_class(PLANT)
    monkeypatch.setattr(R, 'lens_coach_report', broken)
    clean = {**TOTALS, parent.HUMAN_LENS_KEY: lens_clean(tmp_path), parent.COACH_GRADE_KEY: coach_passing()}
    code, out, err = main_run(clean, *lens_on(tmp_path))
    assert code == 4 and err == ''                                  # it would have exited 0: not a pass
    assert out == TODAY + '\n'.join([parent.LENS_REPORT_START, R.RENDER_FAILED_LINE, parent.LENS_REPORT_END]) + '\n'
    assert PLANT not in out and 'Traceback' not in out and error_class.__name__ not in out


def test_a_render_error_outside_the_set_is_the_fatal_path_with_no_block(main_run, tmp_path, monkeypatch):
    def broken(*_a, **_k):
        raise RuntimeError(PLANT)
    monkeypatch.setattr(R, 'lens_coach_report', broken)
    code, out, err = main_run({**TOTALS, parent.HUMAN_LENS_KEY: {'error': 'schema'}}, *lens_on(tmp_path))
    assert code == 3 and err == '' and out.startswith(TODAY)
    tail = out[len(TODAY):]
    assert tail.count('\n') == 1 and '"event": "fatal"' in tail      # the one fatal line, by class name
    assert_no_block(out, err)
    assert PLANT not in out


# ── no result, no block ───────────────────────────────────────────────────────────────────────────────
def test_the_fatal_path_prints_no_block_and_exits_3(main_run, tmp_path):
    code, out, err = main_run(None, *lens_on(tmp_path), raises=RuntimeError(PLANT))
    assert code == 3 and err == '' and out.startswith(TODAY) and '"event": "fatal"' in out
    assert_no_block(out, err)
    assert PLANT not in out


def test_an_argument_error_prints_no_block_and_exits_2(main_run, tmp_path):
    for argv in (['--human-lens'], ['--human-lens-freeze'], [*lens_on(tmp_path), '--months', 'one']):
        code, out, err = main_run(TOTALS, *argv)
        assert code == ('SystemExit', 2) and out == '' and 'error:' in err
        assert_no_block(out, err)
