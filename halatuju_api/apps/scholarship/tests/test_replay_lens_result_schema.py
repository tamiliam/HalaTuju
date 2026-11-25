"""LL5 phase C1c - the allow-list for the human lens's result file (`eval/replay/lens_result_schema.py`),
the child's write through it, and the parent's reader. Made-up data only; every exam folder is a pytest
temp folder outside the repository (one test uses this test folder itself, which the lens refuses)."""
import copy
import datetime
import json
import os
import pathlib

import pytest
from django.test import override_settings

from apps.scholarship.eval.replay import child, lens_human as L, lens_human_rows, parent
from apps.scholarship.eval.replay import lens_result_schema as S
from apps.scholarship.tests.test_replay_lens_human import FAILED_CTX, KC, NOW, case, snap
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION

VERSION = '2026-11-18.2'
PLANTED_NAME = 'Siti Aminah binti Ahmad'
PLANTED_ID = '987654321'
REPO_FOLDER = str(pathlib.Path(__file__).resolve().parent)


def run(cases, folder, freeze=True, blank=False, kc=KC):
    return L.run_human_lens(cases, exam_folder=str(folder), key_is_blank=blank, current_key_check=kc,
                            now=NOW, freeze=freeze)


def cases_rich():
    """50 FULL cases (exam-1), and old cases with Fails of every kind (exam-old, the Other share shown)."""
    out = [case(i, version=VERSION) for i in range(1, 51)]
    plan = [('certain', 'other'), ('probable', 'other'), ('unsure', 'proof_missing'),
            ('ruleNotMet', 'document_false'), ('certain', 'interview_differs'), ('unverifiable', None)]
    for i, (band, reason) in enumerate(plan, start=101):
        verdict = {'identity': 'fail'} if reason is None else {'identity': 'fail', 'fail_reasons': {'identity': reason}}
        out.append(case(i, ctx={}, verdict=verdict, snapshot=snap(identity=band), version=VERSION))
    out.append(case(201, ctx=FAILED_CTX, version=VERSION))
    out.append(case(202, decided=False, version=VERSION))
    return out


@pytest.fixture
def rich(tmp_path):
    return run(cases_rich(), tmp_path)


def _real_shapes(tmp_path):
    """Every result shape the lens really returns, by name."""
    shapes = {}
    a = tmp_path / 'a'
    a.mkdir()
    shapes['freeze'] = run(cases_rich(), a)
    shapes['normal'] = run(cases_rich(), a, freeze=False)
    shapes['key_blank'] = run(cases_rich(), a, freeze=False, blank=True)
    shapes['key_check_differs'] = run(cases_rich(), a, freeze=False, kc='0000ffff')
    b = tmp_path / 'b'
    b.mkdir()
    shapes['exam_missing'] = run(cases_rich(), b, freeze=False)
    shapes['not_frozen_yet'] = run([case(i, version=VERSION) for i in range(1, 50)], b)
    c = tmp_path / 'c'
    c.mkdir()
    shapes['small_numbers'] = run([case(i, ctx={}, version=VERSION) for i in range(1, 4)], c)
    d = tmp_path / 'd'
    d.mkdir()
    shapes['no_cases'] = run([], d)
    e = tmp_path / 'e'
    e.mkdir()
    (e / 'exam-1.json').write_text('{oops', encoding='utf-8')
    shapes['file_unreadable'] = run(cases_rich(), e, freeze=False)
    for name, folder in (('folder_not_absolute', 'exams'), ('folder_missing', str(tmp_path / 'none')),
                         ('inside_git_repo', REPO_FOLDER)):
        shapes[name] = run(cases_rich(), folder)
    with override_settings(DEBUG=True):
        shapes['debug_on'] = lens_human_rows.run_human_lens_on_database(str(tmp_path), NOW)
    for code in S.FILE_ERROR_CODES:
        shapes[f'error_{code}'] = {'error': code}
    return shapes


# ── every real shape passes unchanged ────────────────────────────────────────────────────────────────
def test_every_real_result_shape_passes_unchanged(tmp_path):
    shapes = _real_shapes(tmp_path)
    assert shapes['freeze']['exams'][L.EXAM_1]['status'] == 'frozen'
    assert shapes['freeze']['exams'][L.EXAM_OLD]['fails']['share_other']['too_few'] is False
    assert shapes['small_numbers']['exams'][L.EXAM_OLD]['score']['too_few'] is True
    assert shapes['key_blank']['exams'][L.EXAM_1]['refusal'] == L.KEY_BLANK
    assert shapes['key_check_differs']['exams'][L.EXAM_1]['refusal'] == L.KEY_CHECK_DIFFERS_EXAM
    assert shapes['exam_missing']['exams'][L.EXAM_OLD]['refusal'] == L.EXAM_MISSING
    assert shapes['not_frozen_yet']['exams'][L.EXAM_1]['status'] == 'not frozen yet: 49 of 50'
    assert shapes['file_unreadable']['exams'][L.EXAM_1]['refusal'] == L.UNREADABLE
    assert shapes['inside_git_repo']['exams'][L.EXAM_OLD]['refusal'] == L.INSIDE_GIT_REPO
    assert shapes['debug_on']['exams'][L.EXAM_1] == {'exam': L.EXAM_1, 'refusal': L.DEBUG_ON,
                                                     'status': f'refused: {L.DEBUG_ON}'}
    for name, shape in shapes.items():
        assert S.human_lens_result_allowed(shape), name
        assert json.loads(S.checked_result_text(shape)) == shape, name
        assert S.parse_human_lens_bytes(S.checked_result_text(shape).encode('utf-8')) == shape, name


def test_the_full_allowed_key_list_is_pinned():
    assert S.TOP_KEYS == {'engine_version', 'cases_read', 'not_decided', 'no_human_verdict', 'context_failed',
                          'context_failed_line', 'exams'}
    assert S.ERROR_KEYS == {'error'}
    assert S.EXAM_KEYS == {'exam', 'label', 'frozen', 'status', 'size', 'digest', 'frozen_at', 'key_check',
                           'engine_version', 'refusal', 'cases_with_other_key_check', 'validity', 'still_valid',
                           'valid_split', 'could_not_recompute_reasons', 'qc_turned_to_pass', 'score',
                           'score_without_interview_fails', 'fails', 'candidates', 'known_limits'}
    assert S.EXAM_DEBUG_KEYS == {'exam', 'refusal', 'status'}
    assert S.SMALL_LINE_KEYS == {'label', 'facts', 'too_few'}
    assert S.SCORE_KEYS == {'label', 'facts', 'too_few', 'points', 'best', 'score_pct', 'not_scored', 'outcomes',
                            'coverage', 'generous_wrong'}
    assert S.EXTRA_LINE_KEYS == {'label', 'facts', 'too_few', 'points', 'best', 'score_pct', 'left_out'}
    assert S.COUNT_OF_KEYS == {'count', 'of'}
    assert S.VALID_SPLIT_KEYS == {'matched_directly', 'recovered_by_twin'}
    assert S.FAILS_KEYS == {'fails', 'by_band_and_reason', 'interview_by_band', 'share_other'}
    assert S.SHARE_SMALL_KEYS == {'count', 'of', 'too_few'}
    assert S.SHARE_KEYS == {'count', 'of', 'too_few', 'pct'}
    assert S.FILE_ERROR_CODES == {'schema', 'BadCaseRow', 'ValueError', 'TypeError', 'OSError'}
    # the keyed maps take their keys from the lens and scoring constants
    bands, reasons, outcomes = S._known_codes()  # noqa: SLF001 (the module's own test)
    assert reasons == {'proof_missing', 'document_false', 'documents_differ', 'other', 'not_given'}
    assert bands == {'certain', 'probable', 'unsure', 'unverifiable', 'ruleNotMet'}
    assert outcomes == {'right_sure', 'right_leaning', 'unsure', 'wrong_leaning', 'wrong_sure'}


# ── a plant is refused, and nothing of it reaches the file ───────────────────────────────────────────
def _plant(result, path, value):
    """``result`` with ``value`` at ``path`` (a key list; '+' appends to a list); ``...`` deletes the key."""
    out = copy.deepcopy(result)
    target = out
    for key in path[:-1]:
        target = target[key]
    if path[-1] == '+':
        target.append(value)
    elif value is ...:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return out


E1, EO = ('exams', L.EXAM_1), ('exams', L.EXAM_OLD)
PLANTS = [
    (('cases_read',), PLANTED_ID), (('cases_read',), PLANTED_NAME), (('not_decided',), True),
    (('context_failed',), 1.5), (('engine_version',), PLANTED_NAME), (('engine_version',), f'{VERSION} x'),
    (('context_failed_line',), f'{L.FAILED_CONTEXT_LINE}: {PLANTED_ID}'),
    ((*E1, 'status'), PLANTED_NAME), ((*E1, 'status'), f'refused: {PLANTED_ID}'),
    ((*E1, 'label'), PLANTED_NAME), ((*E1, 'refusal'), PLANTED_NAME), ((*E1, 'exam'), PLANTED_ID),
    ((*E1, 'digest'), PLANTED_ID), ((*E1, 'digest'), 'SITIAMINAH01'), ((*E1, 'frozen_at'), PLANTED_NAME),
    ((*E1, 'frozen_at'), '2026-11-24T12:00:00+00:00'), ((*E1, 'key_check'), PLANTED_ID),
    ((*E1, 'key_check'), 'ABCD1234'), ((*E1, 'engine_version'), '2026-11-18.3'),
    ((*E1, 'still_valid'), f'{PLANTED_ID} of 50 still valid'), ((*E1, 'known_limits', '+'), PLANTED_NAME),
    ((*E1, 'candidates'), 3), ((*E1, 'frozen'), 1), ((*E1, 'size'), PLANTED_ID),
    ((*E1, 'validity', 'valid'), True), ((*E1, 'valid_split', 'recovered_by_twin'), PLANTED_NAME),
    ((*E1, 'score', 'points'), 1.5), ((*E1, 'score', 'outcomes', 'unsure'), PLANTED_ID),
    ((*E1, 'score', 'label'), PLANTED_NAME), ((*E1, 'score', 'too_few'), 0),
    ((*EO, 'fails', 'by_band_and_reason', 'certain', 'other'), PLANTED_NAME),
    ((*EO, 'fails', 'share_other', 'pct'), PLANTED_ID), ((*EO, 'fails', 'share_other', 'too_few'), True),
    ((*EO, 'known_limits', 0), PLANTED_NAME), ((*EO, 'key_check'), KC),
    # unknown keys at each level (one is named like the plant), and a missing key
    (('applicant',), 1), ((PLANTED_NAME,), 1), ((*E1, 'name'), 1), ((*E1, 'score', 'note'), 1),
    ((*EO, 'fails', 'by_band_and_reason', 'certain', PLANTED_ID), 1), (('exams', 'exam-2'), 1),
    ((*E1, 'label'), ...), (('exams', L.EXAM_OLD), ...),
]


@pytest.mark.parametrize('path, value', PLANTS)
def test_a_plant_anywhere_gives_exactly_the_schema_error_and_nothing_of_it(rich, path, value):
    planted = _plant(rich, path, value)
    assert not S.human_lens_result_allowed(planted)
    text = S.checked_result_text(planted)
    assert text == S.SCHEMA_TEXT == '{"error": "schema"}'
    assert S.parse_human_lens_bytes(json.dumps(planted).encode('utf-8')) == {'error': 'schema'}


@pytest.mark.parametrize('planted', [
    {'error': PLANTED_NAME}, {'error': PLANTED_ID}, {'error': 'no_output'}, {'error': 1},
    {'error': 'schema', 'note': 1}, {'cases_read': datetime.datetime(2026, 1, 1)}, {'x': float('nan')},
    [PLANTED_NAME], PLANTED_NAME, 7, None])
def test_odd_results_and_unknown_error_codes_give_the_schema_error(planted):
    assert S.checked_result_text(planted) == S.SCHEMA_TEXT


@pytest.mark.parametrize('path, value', [(('cases_read',), PLANTED_ID), ((*E1, 'status'), PLANTED_NAME),
                                         (((*EO, 'fails', 'by_band_and_reason', 'certain', 'other')), PLANTED_NAME),
                                         ((PLANTED_NAME,), 1)])
def test_the_child_writes_only_the_schema_error_for_a_plant(rich, tmp_path, monkeypatch, path, value):
    planted = _plant(rich, path, value)
    monkeypatch.setattr(lens_human_rows, 'run_human_lens_on_database', lambda *_a, **_k: planted)
    target = tmp_path / child.HUMAN_LENS_FILE
    child.write_human_lens((str(tmp_path), False), now=NOW, path=str(target))
    text = target.read_text(encoding='utf-8')
    assert text == '{"error": "schema"}' and PLANTED_NAME not in text and PLANTED_ID not in text
    assert parent.read_human_lens(str(target)) == {'error': 'schema'}
    assert parent.replay_exit_code({parent.HUMAN_LENS_KEY: parent.read_human_lens(str(target))}) == 4


@pytest.mark.parametrize('raised, recorded', [
    (L.BadCaseRow('application_id', 'repeats'), 'BadCaseRow'), (ValueError('x'), 'ValueError'),
    (TypeError('x'), 'TypeError'), (OSError('x'), 'OSError'), (FileNotFoundError('x'), 'OSError'),
    (PermissionError('x'), 'OSError'), (UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'x'), 'ValueError'),
    (json.JSONDecodeError('x', 'doc', 0), 'ValueError')])
def test_a_caught_lens_error_is_recorded_by_the_nearest_known_class(tmp_path, monkeypatch, raised, recorded):
    def broken(*_a, **_k):
        raise raised
    monkeypatch.setattr(lens_human_rows, 'run_human_lens_on_database', broken)
    target = tmp_path / child.HUMAN_LENS_FILE
    child.write_human_lens((str(tmp_path), False), now=NOW, path=str(target))
    assert json.loads(target.read_text(encoding='utf-8')) == {'error': recorded}
    assert parent.read_human_lens(str(target)) == {'error': recorded}
    assert S.lens_error_name(RuntimeError('x')) == S.SCHEMA          # never caught by the child; never a name


# ── the shaped values ────────────────────────────────────────────────────────────────────────────────
def test_the_engine_version_shape():
    assert S.engine_version_ok(VERDICT_ENGINE_VERSION)               # the live constant has the shape
    for good in ('2026-11-18.2', '2026-09-11.1', '2099-12-31.999'):
        assert S.engine_version_ok(good), good
    for bad in ('v-test', 'pre-versioning', '2026-11-18', '2026-13-01.1', '2026-11-32.1', '2026-11-18.1234',
                '2026-11-18.2\n', ' 2026-11-18.2', '２０２６-11-18.2', '1999-11-18.1', 20261118, None):
        assert not S.engine_version_ok(bad), bad


def test_the_frozen_at_and_digest_shapes(rich):
    exam = rich['exams'][L.EXAM_1]
    assert S.FROZEN_AT_SHAPE.fullmatch(exam['frozen_at']) and S.DIGEST_SHAPE.fullmatch(exam['digest'])
    for bad in ('2026-02-30T12:00:00.000000+00:00', '2026-11-24T12:00:00.000000+08:00',
                '2026-11-24 12:00:00.000000+00:00', '2026-11-24T12:00:00.000000Z'):
        assert S.checked_result_text(_plant(rich, (*E1, 'frozen_at'), bad)) == S.SCHEMA_TEXT, bad
    for bad in ('abc', 'abcdef0123456', 'ABCDEF012345', 'abcdef01234g'):
        assert S.checked_result_text(_plant(rich, (*E1, 'digest'), bad)) == S.SCHEMA_TEXT, bad


# ── the parent's reader ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('raw', [
    b'{oops', b'', b'[1, 2]', b'"Siti Aminah binti Ahmad"', b'987654321', b'null', b'\xff\xfe{}',
    b'{"error": "schema", "error": "schema"}', b'{"cases_read": NaN}', b'[' * 100000,
    b' ' * (S.MAX_RESULT_BYTES + 1)])
def test_a_broken_file_is_bad_output_with_no_crash_and_no_echo(tmp_path, capsys, raw):
    target = tmp_path / child.HUMAN_LENS_FILE
    target.write_bytes(raw)
    assert parent.read_human_lens(str(target)) == {'error': 'bad_output'}
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''


def test_a_missing_file_a_folder_and_a_good_file(tmp_path, rich):
    target = tmp_path / child.HUMAN_LENS_FILE
    assert parent.read_human_lens(str(target)) == {'error': 'no_output'}
    target.mkdir()
    assert parent.read_human_lens(str(target)) == {'error': 'bad_output'}
    os.rmdir(target)
    target.write_text(S.checked_result_text(rich), encoding='utf-8')
    assert parent.read_human_lens(str(target)) == rich
    target.write_text(json.dumps({'error': 'no_output'}), encoding='utf-8')   # a code only the parent makes
    assert parent.read_human_lens(str(target)) == {'error': 'schema'}


# ── fix round: a JSON true or false is never a count, even deep inside ───────────────────────────────
NESTED_COUNTS = [(*EO, 'fails', 'by_band_and_reason', 'certain', 'other'),
                 (*EO, 'fails', 'by_band_and_reason', 'unverifiable', 'other'),
                 (*E1, 'score', 'outcomes', 'wrong_sure')]


@pytest.mark.parametrize('path', NESTED_COUNTS)
def test_a_json_bool_in_a_nested_count_slot_is_refused(rich, tmp_path, path):
    """A bool equal to the count it replaces (true for 1, false for 0), so only the int rule can catch it."""
    target = rich
    for key in path:
        target = target[key]
    assert type(target) is int and target in (0, 1)                # the precondition: a real 0 or 1 count
    planted = _plant(rich, path, bool(target))
    assert not S.human_lens_result_allowed(planted)
    raw = json.dumps(planted).encode('utf-8')
    assert b'true' in raw or b'false' in raw
    assert S.parse_human_lens_bytes(raw) == {'error': 'schema'}
    assert S.checked_result_text(planted) == S.SCHEMA_TEXT
