"""LL5 phase C2b - the replay report's human-lens and coach-grade sections (`eval/replay/report_lens.py`
through `report_md.render`). Real result shapes are built by the real `lens_human.run_human_lens` and
`coach_grade.coach_report` on made-up cases; no database, no network, no real student data."""
import copy
import datetime
import pathlib

import pytest
from django.test import override_settings

from apps.scholarship import ai_score, coach_grade, fail_reasons
from apps.scholarship.eval.replay import coach_result_schema as CS
from apps.scholarship.eval.replay import coach_rows, lens_human as L, lens_human_rows
from apps.scholarship.eval.replay import lens_result_schema as LS
from apps.scholarship.eval.replay import report_lens as R
from apps.scholarship.eval.replay import report_md, rulings
from apps.scholarship.fact_bands import BANDS, CERTAIN, PROBABLE, UNSURE
from apps.scholarship.tests.test_coach_grade import EARLY, LATER, LATEST, many
from apps.scholarship.tests.test_replay_lens_human import NOW, case
from apps.scholarship.tests.test_replay_lens_result_schema import VERSION, cases_rich, run
from apps.scholarship.verdict_engine import PRE_VERSIONING

PLANT = 'Siti Aminah binti Ahmad'
PLANT_WORD = 'SitiAminah'
V1, V2, V3, V4 = '2026-03-01.1', '2026-04-01.2', '2026-05-01.3', '2026-06-01.4'
W1, W2 = '2026-05-10.5', '2026-06-20.6'
FORBIDDEN = 'documents' + ' only'      # built here so this file never holds the phrase itself
SOURCES = [pathlib.Path(R.__file__), pathlib.Path(report_md.__file__)]


# ── builders ──────────────────────────────────────────────────────────────────────────────────────────
def lens_clean(folder):
    """Both exams frozen, then a normal run: a twin recovery and a could-not-recompute case in exam-1."""
    run(cases_rich(), folder)
    now = cases_rich()
    now[0] = case(1, note=L.RECOVERED_BY_TWIN, version=VERSION)
    now[4] = case(5, recomputed=None, note='past_award_stage', version=VERSION)
    return run(now, folder, freeze=False)


def lens_small(folder):
    """exam-1 not frozen (3 of 50); exam-old frozen with too few facts to score."""
    return run([case(i, ctx={}, version=VERSION) for i in range(1, 4)], folder)


def coach_clean():
    """Four gradeable versions (pass, fail, no clear change), two waiting versions (one with figures,
    one too few), two months for V1, malformed records and both unknown-version kinds."""
    later = datetime.timedelta(days=35)
    records = (many([(PROBABLE, 'pass', 40), (CERTAIN, 'fail', 3, 'interview_differs')], V1, EARLY)
               + many([(PROBABLE, 'pass', 6)], V1, EARLY + later)
               + many([(CERTAIN, 'pass', 40)], V2, LATER)
               + many([(UNSURE, 'pass', 40)], V3, LATEST)
               + many([(UNSURE, 'pass', 10)], W1, LATEST + datetime.timedelta(days=6))
               + many([(UNSURE, 'pass', 40)], V4, LATEST + datetime.timedelta(days=30))
               + many([(UNSURE, 'pass', 2)], W2, LATEST + datetime.timedelta(days=50))
               + many([(CERTAIN, 'pass', 6)], None) + many([(CERTAIN, 'pass', 2)], PRE_VERSIONING)
               + [('x',), ([], {}, V1, 'not a time'), (5, {'identity': 'pass'}, V1, EARLY)])
    return coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)


def coach_one_pair(prev, new):
    return coach_grade.coach_report(many(prev, V1, EARLY) + many(new, V2, LATER),
                                    leave_out_reasons=coach_grade.INTERVIEW_FAILS)


def lens_debug(folder):
    with override_settings(DEBUG=True):
        return lens_human_rows.run_human_lens_on_database(str(folder), NOW)


def text_of(lens, coach):
    return '\n'.join(R.lens_coach_section_lines(lens, coach))


def part(text, start, end=None):
    """The lines from the heading ``start`` up to (not including) the heading ``end``."""
    tail = text[text.index(start):]
    return tail[:tail.index(end)] if end else tail


def lens_part(text):
    return part(text, '### Human lens', '### Coach grade')


def coach_part(text):
    return part(text, '### Coach grade', '### Read with care') if '### Read with care' in text else \
        part(text, '### Coach grade')


def summary(text):
    return text.splitlines()[2]


@pytest.fixture
def clean_lens(tmp_path):
    return lens_clean(tmp_path)


# ── lens off: byte for byte the old report ────────────────────────────────────────────────────────────
OLD_EMPTY_REPORT = '\n'.join(
    ['# Replay report', '', 'Old tree a1, new tree b2.', '', '## Counts', '',
     '| Family | Records | Same | A | B | C | N |', '|---|---|---|---|---|---|---|',
     '', '## A - expected (an owner ruling explains it)', '', 'None.',
     '', '## B - unexplained (the owner looks at each)', '', 'None.',
     '', '## C - could not run', '', 'None.',
     '', '## N - noise (the new tree disagreed with itself)', '', 'None.',
     '', '## Pending (not shipped: differences are B)', '']
    + [f'- {pid}: {text}' for pid, text in rulings.PENDING]
    + ['', '## Owner sign-off', '', '- Reviewed by:', '- Date:', ''])


def test_lens_off_is_byte_identical_to_the_old_report():
    off = report_md.render([], old_commit='a1', new_commit='b2')
    assert off == OLD_EMPTY_REPORT
    assert off == report_md.render([], old_commit='a1', new_commit='b2', human_lens=None, coach_grade=None)
    assert 'Human lens' not in off and 'Coach grade' not in off and '\n\n\n' not in off


def test_lens_on_adds_only_the_two_sections_before_the_sign_off(clean_lens):
    coach = coach_clean()
    off = report_md.render([], old_commit='a1', new_commit='b2')
    on = report_md.render([], old_commit='a1', new_commit='b2', human_lens=clean_lens, coach_grade=coach)
    block = '\n'.join(R.lens_coach_section_lines(clean_lens, coach))
    assert on == off.replace('\n\n## Owner sign-off', f'\n\n{block}\n\n## Owner sign-off')
    assert on.index(R.HEADING) > on.index('## Pending') and on.index(R.HEADING) < on.index('## Owner sign-off')


def test_one_result_given_alone_shows_the_other_as_no_output(clean_lens):
    text = report_md.render([], human_lens=clean_lens)
    assert '- coach grade failed: no_output. BLOCKING.' in text
    text = report_md.render([], coach_grade=coach_clean())
    assert '- lens failed: no_output. BLOCKING.' in text


# ── failures never look like results ──────────────────────────────────────────────────────────────────
def _one_failure_line(section, prefix, code):
    lines = [line for line in section.splitlines() if line]
    assert lines[1:] == [f'- {prefix}: {code}. {R.BLOCKING}. Meaning: {R.ERROR_WORDS[code]}. '
                         'There is no result, so this is not a pass.'], lines
    assert not any(ch.isdigit() for ch in section)
    assert '|' not in section and 'Score' not in section


def test_both_clean_has_no_blocking_item(clean_lens):
    text = text_of(clean_lens, coach_one_pair([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)]))
    assert summary(text) == 'No blocking item.'
    assert '### Read with care' in text


@pytest.mark.parametrize('code', sorted(R.LENS_SHOWN_ERRORS))
def test_lens_error_only(clean_lens, code):
    text = text_of({'error': code}, coach_clean())
    _one_failure_line(lens_part(text), 'lens failed', code)
    assert summary(text).startswith('BLOCKING: 2 item(s): human lens (failed), coach pair ')
    assert '### Read with care' in text and '#### Monthly score' in text


@pytest.mark.parametrize('code', sorted(R.COACH_SHOWN_ERRORS))
def test_coach_error_only(clean_lens, code):
    text = text_of(clean_lens, {'error': code})
    _one_failure_line(coach_part(text), 'coach grade failed', code)
    assert summary(text) == 'BLOCKING: 1 item(s): coach grade (failed).'
    assert '#### exam-1' in text and '### Read with care' in text


def test_both_errors_and_no_caveats():
    text = text_of({'error': 'bad_output'}, {'error': 'LookupError'})
    assert summary(text) == 'BLOCKING: 2 item(s): human lens (failed), coach grade (failed).'
    _one_failure_line(lens_part(text), 'lens failed', 'bad_output')
    _one_failure_line(part(text, '### Coach grade'), 'coach grade failed', 'LookupError')
    assert '### Read with care' not in text


def test_none_is_no_output_and_an_unknown_code_prints_as_schema():
    text = text_of(None, None)
    _one_failure_line(lens_part(text), 'lens failed', 'no_output')
    for bad_lens, bad_coach in (({'error': PLANT}, {'error': PLANT}), ({'error': 'LookupError'}, {'error': 'OSError'}),
                                ({'error': 3}, {'error': None}), ({'error': 'schema', 'x': 1}, {'refusal': PLANT}),
                                ([], 'text'), ({1, 2}, {'refusal': {1}})):
        text = text_of(bad_lens, bad_coach)
        _one_failure_line(lens_part(text), 'lens failed', 'schema')
        _one_failure_line(part(text, '### Coach grade'), 'coach grade failed', 'schema')
        assert PLANT not in text


def test_a_coach_fail_is_blocking_with_its_reasons_and_pass_and_no_change_are_not(clean_lens):
    text = text_of(clean_lens, coach_one_pair([(CERTAIN, 'pass', 40)], [(UNSURE, 'pass', 40)]))
    assert summary(text) == f'BLOCKING: 1 item(s): coach pair {V1} to {V2} (fail).'
    assert f'- {V1} to {V2}: fail. BLOCKING. Reasons: coverage dropped. Versions skipped between them: 0.' in text
    for prev, new, words in (([(PROBABLE, 'pass', 40)], [(CERTAIN, 'pass', 40)], 'pass'),
                             ([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)], 'no clear change')):
        text = text_of(clean_lens, coach_one_pair(prev, new))
        assert summary(text) == 'No blocking item.'
        line = next(x for x in text.splitlines() if x.startswith(f'- {V1} to {V2}: '))
        assert line.startswith(f'- {V1} to {V2}: {words}. Reasons: ') and R.BLOCKING not in line


def test_the_coach_refusal_is_not_run_and_never_counts(clean_lens):
    text = text_of(clean_lens, coach_rows.coach_debug_refusal())
    section = part(text, '### Coach grade', '### Read with care')
    assert [x for x in section.splitlines() if x][1:] == [
        '- not run: debug_on. Meaning: DEBUG is on, so nothing was read. This is not a pass.']
    assert not any(ch.isdigit() for ch in section)
    assert summary(text) == 'No blocking item. Not run: coach grade (refused).'


def test_the_lens_debug_refusal_is_not_run_for_both_exams(tmp_path):
    text = text_of(lens_debug(tmp_path), {'error': 'schema'})
    section = lens_part(text)
    assert section.count('- not run: debug_on. Meaning: DEBUG is on, so nothing was read. This is not a pass.') == 2
    assert '- Engine version: not read.' in section and '- Cases read: not read. Not decided: not read.' in section
    assert not any(ch.isdigit() for ch in section.replace('exam-1', ''))
    assert summary(text) == ('BLOCKING: 1 item(s): coach grade (failed). '
                             'Not run: exam-1 (refused), exam-old (refused).')


def test_a_refused_exam_beside_a_clean_exam(tmp_path):
    run(cases_rich(), tmp_path)
    lens = run(cases_rich(), tmp_path, freeze=False, blank=True)
    assert lens['exams'][L.EXAM_1]['refusal'] == L.KEY_BLANK and lens['exams'][L.EXAM_OLD]['frozen'] is True
    text = text_of(lens, coach_rows.coach_debug_refusal())
    exam_1 = part(text, '#### exam-1', '#### exam-old')
    assert '- not run: key_blank. Meaning: the fingerprint key is blank. This is not a pass.' in exam_1
    assert 'Score' not in exam_1 and 'Validity' not in exam_1
    exam_old = part(text, '#### exam-old', '### Coach grade')
    assert '- Score: ' in exam_old and 'not run' not in exam_old
    assert summary(text) == 'No blocking item. Not run: exam-1 (refused), coach grade (refused).'


def test_too_few_and_waiting_are_never_a_pass(tmp_path):
    lens = lens_small(tmp_path)
    text = text_of(lens, coach_clean())
    assert summary(text).endswith('No grade yet: exam-1 (not frozen yet), exam-old (too few facts to grade yet).')
    assert '- No score: the exam is not frozen yet. This is not a pass.' in text
    facts = lens['exams'][L.EXAM_OLD]['score']['facts']
    assert f'- Score: too few facts to grade yet ({facts} facts). This is not a pass.' in text
    assert f'- {W1}: too few facts to grade yet. This is not a pass. So far: 10 facts, score ' in text
    assert f'- {W2}: too few facts to grade yet. This is not a pass.' in text
    text = text_of(lens, coach_grade.coach_report([]))
    assert 'coach grade (no pair to grade yet)' in summary(text)
    assert 'No pair to grade yet' in text and 'No month has a marked fact yet.' in text


# ── a clean run shows every allowed key ───────────────────────────────────────────────────────────────
def test_the_clean_lens_section(clean_lens):
    text = text_of(clean_lens, coach_clean())
    lens = clean_lens
    e1, old = lens['exams'][L.EXAM_1], lens['exams'][L.EXAM_OLD]
    assert e1['valid_split']['recovered_by_twin'] == 1 and e1['could_not_recompute_reasons']['past_award_stage'] == 1
    top = lens_part(text)
    assert f'- Engine version: {VERSION}.' in top
    assert (f'- Cases read: {lens["cases_read"]}. Not decided: {lens["not_decided"]}. '
            f'No human verdict: {lens["no_human_verdict"]}.') in top
    assert f'- Decided cases whose context record failed (in neither exam): {lens["context_failed"]}.' in top
    exam_1 = part(text, '#### exam-1: same evidence, checked by fingerprint', '#### exam-old')
    assert (f'- Frozen: yes, at {e1["frozen_at"]}. Size: 50. Digest: {e1["digest"]}. '
            f'Key check: {e1["key_check"]}.') in exam_1
    assert '- Status: frozen.' in exam_1 and f'- {e1["still_valid"]}.' in exam_1
    assert '- Validity: still valid ' in exam_1 and ', could not recompute 1, ' in exam_1
    assert '- Valid split: matched directly ' in exam_1 and 'recovered by twin 1.' in exam_1
    assert '- Could not recompute, by reason: past the award stage 1, twin in a decided group 0, ' in exam_1
    assert f'- Fails the QC turned to Pass: {e1["qc_turned_to_pass"]}.' in exam_1
    score = e1['score']
    assert (f'- Score: {score["facts"]} facts, {score["points"]} points of {score["best"]} best, '
            f'score {score["score_pct"]}%, {score["not_scored"]} not scored.') in exam_1
    assert '- Outcomes: right and sure ' in exam_1 and '- Coverage: ' in exam_1 and 'Generous-wrong: ' in exam_1
    assert '- Score without interview Fails: ' in exam_1 and ' left out.' in exam_1
    assert f'- Known limits: a score on {score["facts"]} facts; drop-outs shrink the exam.' in exam_1
    exam_old = part(text, '#### exam-old: weaker exam: evidence state unknown', '### Coach grade')
    assert 'Key check: not used for this exam.' in exam_old
    assert '- Valid split and could-not-recompute reasons: not kept for this exam.' in exam_old
    assert f'- Fails: {old["fails"]["fails"]}. By band and reason' in exam_old
    assert '| Band | proof missing | document false | documents differ | "other" | no reason stored |' in exam_old
    assert '| Certain | ' in exam_old and '| Rule not met | ' in exam_old
    assert '- Interview Fails by band: Certain 1, Probable 0, Unsure 0, Unverifiable 0, Rule not met 0.' in exam_old
    share = old['fails']['share_other']
    assert f'- Share of "other" among the Fails: {share["count"]} of {share["of"]} ({share["pct"]}%).' in exam_old
    assert '- Known limits: weaker exam: evidence state unknown; a score on ' in exam_old


def test_the_exam_missing_candidates_line(tmp_path):
    lens = run(cases_rich(), tmp_path, freeze=False)
    text = text_of(lens, coach_rows.coach_debug_refusal())
    assert '- not run: exam_missing. Meaning: no frozen exam file was found. This is not a pass.' in text
    assert f'- Status: refused: exam_missing ({lens["exams"][L.EXAM_1]["candidates"]} of 50 candidates).' in text
    assert f'- Candidates: {lens["exams"][L.EXAM_1]["candidates"]}.' in text


def test_the_clean_coach_section(clean_lens):
    coach = coach_clean()
    assert sorted(p['grade'] for p in coach['coach']) == ['fail', 'no_change', 'pass']
    assert {(s['version'], s['too_few']) for s in coach['waiting']} == {(W1, False), (W2, True)}
    text = coach_part(text_of(clean_lens, coach))
    assert '- Floors: a month needs 5 facts for a score; a version needs 40 facts to be graded.' in text
    assert '- Guard level: 1 in 20. Score margin: 2 standard errors.' in text
    assert (f'- Decided records: {coach["decided_records"]}. Versions without marks: '
            f'{coach["versions_without_marks"]}.') in text
    assert ('- Malformed records: 3 (by kind: record too short 1, decided time is not a date and time 1, '
            'a value of the wrong type 1).') in text
    assert '- The line "score without interview Fails" leaves out Fails with reason: interview differs.' in text
    assert ('| Version | Month | Facts | Points | Best | Score % | Not scored | Outcomes | '
            'Score without interview Fails |') in text
    assert f'| {V1} | 2026-03 | 43 | ' in text and f'| {V1} | 2026-04 | 6 | ' in text
    assert f'| {W2} | 2026-06 | too few facts to grade yet | - | - | - | - | - | - |' in text
    assert '| unknown: version not recorded | 2026-03 | 6 | ' in text
    assert '| unknown: made before versions were recorded | 2026-03 | too few facts to grade yet |' in text
    assert f'- {V1} to {V2}: pass. Reasons: score went up. Versions skipped between them: 0.' in text
    assert f'- {V2} to {V3}: fail. BLOCKING. Reasons: coverage dropped. Versions skipped between them: 0.' in text
    assert f'- {V3} to {V4}: no clear change. Reasons: no clear change. Versions skipped between them: 1.' in text
    assert f'  - Previous, {V1}: 49 facts, score ' in text and ', coverage 49 of 49, generous-wrong 3 of 49.' in text
    assert '  - Previous, score without interview Fails: 46 facts, ' in text and '3 left out.' in text
    assert f'  - New, {V2}: 40 facts, score 100%, coverage 40 of 40, generous-wrong 0 of 40.' in text


def test_the_caveats_are_printed_with_a_clean_section(clean_lens):
    text = text_of(clean_lens, {'error': 'schema'})
    tail = part(text, '### Read with care')
    assert tail.splitlines()[2:] == [f'- {line}' for line in R.CAVEATS]
    assert 'turns a Fail the QC disagreed with into a Pass' in tail and 'not bigger than luck' in tail
    # The report's A and B sections list example case keys, so the caveat speaks for this section only.
    assert 'this section holds no case id and no name' in tail and 'this report holds' not in tail


# ── planted free text never prints ────────────────────────────────────────────────────────────────────
def _planted(result, path, value):
    result = copy.deepcopy(result)
    target = result
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return result


@pytest.mark.parametrize('path, value', [
    (('note',), PLANT), (('exams', L.EXAM_1, 'status'), PLANT), (('exams', L.EXAM_OLD, 'label'), PLANT),
    (('exams', L.EXAM_1, 'score', 'facts'), PLANT), (('engine_version',), PLANT),
    (('exams', L.EXAM_1, 'known_limits'), [PLANT])])
def test_a_planted_lens_text_prints_the_schema_failure(clean_lens, path, value):
    text = text_of(_planted(clean_lens, path, value), coach_clean())
    _one_failure_line(lens_part(text), 'lens failed', 'schema')
    assert PLANT not in text


@pytest.mark.parametrize('path, value', [
    (('note',), PLANT), (('months', 0, 'version'), PLANT), (('coach', 0, 'grade'), PLANT),
    (('coach', 0, 'reasons'), [PLANT]), (('waiting', 0, 'version'), PLANT)])
def test_a_planted_coach_text_prints_the_schema_failure(clean_lens, path, value):
    text = text_of(clean_lens, _planted(coach_clean(), path, value))
    _one_failure_line(coach_part(text), 'coach grade failed', 'schema')
    assert PLANT not in text


def test_a_word_kind_that_passes_the_allow_list_is_never_printed(clean_lens):
    coach = _planted(coach_clean(), ('malformed_by_error',), {PLANT_WORD + 'Error': 2, 'too_short': 1})
    coach['malformed_records'] = 3
    assert CS.coach_result_allowed(coach)
    text = text_of(clean_lens, coach)
    assert PLANT_WORD not in text
    assert '- Malformed records: 3 (by kind: record too short 1, unlisted kind 2).' in text


def test_the_forbidden_phrase_is_nowhere(clean_lens, tmp_path):
    texts = [text_of(clean_lens, coach_clean()), text_of(None, None), text_of(lens_debug(tmp_path), {'refusal': 'debug_on'}),
             report_md.render([], human_lens=clean_lens, coach_grade=coach_clean())]
    for text in texts:
        assert FORBIDDEN not in text.lower()
    for source in SOURCES:
        assert FORBIDDEN not in source.read_text(encoding='utf-8').lower()


# ── the label tables cover every fixed code; an unknown code never prints raw ─────────────────────────
def test_the_label_tables_are_pinned_to_the_real_codes():
    assert set(R.REFUSAL_WORDS) == LS.REFUSAL_CODES
    assert tuple(R.VALIDITY_WORDS) == L.VALIDITY and tuple(R.RECOMPUTE_WORDS) == L.RECOMPUTE_REASONS
    assert set(R.SPLIT_WORDS) == LS.VALID_SPLIT_KEYS and tuple(R.BAND_WORDS) == BANDS
    assert set(R.FAIL_REASON_WORDS) == set(fail_reasons.CODES) | {L.NOT_GIVEN}
    assert tuple(R.OUTCOME_WORDS) == ai_score.OUTCOMES
    assert set(R.GRADE_WORDS) == set(coach_grade.GRADES) and set(R.COACH_REASON_WORDS) == set(coach_grade.REASON_CODES)
    assert set(R.MALFORMED_WORDS) >= {*coach_grade.MALFORMED_LABELS, coach_grade.OTHER_ERROR}
    assert set(R.UNKNOWN_VERSION_WORDS) == {coach_grade.UNKNOWN_VERSION, PRE_VERSIONING}
    assert set(R.ERROR_WORDS) == R.LENS_SHOWN_ERRORS | R.COACH_SHOWN_ERRORS
    assert R.LENS_SHOWN_ERRORS == LS.FILE_ERROR_CODES | {LS.NO_OUTPUT, LS.BAD_OUTPUT}
    assert R.COACH_SHOWN_ERRORS == CS.COACH_FILE_ERROR_CODES | {LS.NO_OUTPUT, LS.BAD_OUTPUT}


def test_an_unknown_code_falls_back_to_fixed_words():
    assert R.words_for(R.GRADE_WORDS, PLANT) == R.OTHER_WORDS and R.words_for(R.GRADE_WORDS, ['x']) == R.OTHER_WORDS
    assert R.counts_in_words({'certain': 1, PLANT: 2, 'zz': 3}, R.BAND_WORDS) == 'Certain 1, unlisted kind 5'
    assert R.counts_in_words({}, R.BAND_WORDS) == 'none'


@pytest.mark.parametrize('code, words', ((L.FROZEN_ELSEWHERE, 'another run froze this exam first'),
                                         (L.NOT_KEPT, 'the frozen exam was not kept in the bucket')))
def test_a_parent_refusal_prints_its_exact_words_and_no_score(clean_lens, code, words):
    assert R.REFUSAL_WORDS[code] == words
    lens = copy.deepcopy(clean_lens)
    lens['exams'][L.EXAM_1] = L.refused_exam(L.EXAM_1, lens['engine_version'], code)
    assert LS.human_lens_result_allowed(lens)
    text = text_of(lens, coach_rows.coach_debug_refusal())
    exam_1 = part(text, '#### exam-1', '#### exam-old')
    assert f'- not run: {code}. Meaning: {words}. This is not a pass.' in exam_1
    assert 'Score' not in exam_1 and 'Validity' not in exam_1
