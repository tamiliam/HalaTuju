"""LL5 phase C2b - the human lens and the coach grade as two sections of the owner's markdown report
(`report_md.render`, only when it is given either result; with neither, the report is unchanged).

SAFETY RULES (a failure must never look like a result):
* Each result is checked AGAIN before anything is printed: an error form is read first (only a code
  from the fixed sets is printed, anything else prints as ``schema``); then the JSON form of the result
  must pass its allow-list (`lens_result_schema.human_lens_result_allowed`,
  `coach_result_schema.coach_result_allowed`), else the section is the ``schema`` failure line. Only
  the checked JSON form is read, and only through keys of the allow-list.
* A failed result is ONE line (``lens failed: <code>`` / ``coach grade failed: <code>``) with the
  BLOCKING marker: no count, no score, no table. A refusal prints ``not run: <code>`` and says it is not
  a pass. A coach pair graded ``fail`` is BLOCKING. Too few facts is never a pass.
* Every fixed code is printed through a label table below; a code missing from its table prints as
  `OTHER_WORDS`, never raw. The only text printed as it is: version labels, months, the frozen time,
  digest and key check (each held to a strict shape by the allow-list), and the lens's own fixed lines
  (labels, status, the still-valid sentence, the context-failed line, the known limits), which the
  allow-list rebuilds from fixed words and the result's own ints.
* Numbers: every one is an int the result holds. The only sums are the summary's count of blocking
  items and, for a key missing from a label table, the total of those counts (`counts_in_words`).
"""
from __future__ import annotations

import json

from . import coach_result_schema as CS
from . import lens_human as L
from . import lens_result_schema as LS

HEADING = '## Human lens and coach grade'
BLOCKING = 'BLOCKING'
NOT_A_PASS = 'This is not a pass.'
TOO_FEW = 'too few facts to grade yet'
OTHER_WORDS = 'unlisted kind'
LENS_SHOWN_ERRORS = frozenset(LS.FILE_ERROR_CODES | {LS.NO_OUTPUT, LS.BAD_OUTPUT})
COACH_SHOWN_ERRORS = frozenset(CS.COACH_FILE_ERROR_CODES | {LS.NO_OUTPUT, LS.BAD_OUTPUT})

# ── the label tables: every fixed code in plain words (tests pin each table to the real code set) ──
ERROR_WORDS = {
    'schema': 'the result did not pass its allow-list',
    'no_output': 'no result was written',
    'bad_output': 'the result could not be read as plain JSON',
    'BadCaseRow': 'a case row had the wrong shape',
    'ValueError': 'a bad value',
    'TypeError': 'a value of the wrong type',
    'OSError': 'a file or folder error',
    'LookupError': 'a missing key or item',
}
REFUSAL_WORDS = {
    'file_unreadable': 'the exam file could not be read',
    'unknown_field': 'the exam file has an unknown field',
    'missing_field': 'the exam file lacks a field',
    'wrong_exam_name': 'the exam file names another exam',
    'wrong_format_version': 'the exam file has the wrong format version',
    'bad_field_type': 'a field in the exam file has the wrong type',
    'non_integer_id': 'a case number in the exam file is not a whole number',
    'duplicate_id': 'a case appears twice in the exam file',
    'size_mismatch': 'the exam file size does not match its cases',
    'digest_mismatch': 'the exam file digest does not match its cases',
    'id_below_one': 'a case number in the exam file is below one',
    'empty_exam': 'the exam file holds no case',
    'bad_decided_at': 'a decided time in the exam file is bad',
    'bad_frozen_at': 'the frozen time in the exam file is bad',
    'bad_key_check': 'the key check in the exam file is bad',
    'exam_missing': 'no frozen exam file was found',
    'folder_missing': 'the exam folder does not exist',
    'inside_git_repo': 'the exam folder is inside a git repository',
    'already_frozen': 'the exam is already frozen',
    'folder_not_writable': 'the exam folder cannot be written',
    'folder_not_absolute': 'the exam folder is not a full path',
    'debug_on': 'DEBUG is on, so nothing was read',
    'key_blank': 'the fingerprint key is blank',
    'candidate_key_checks_differ': 'the candidate cases carry different key checks',
    'current_key_check_missing': 'the current key check is missing',
    'candidate_key_check_not_current': 'the candidate cases do not carry the current key check',
    'key_check_differs_from_exam': 'the current key check differs from the exam file',
    'key_check_differs_from_cases': 'the cases carry a key check that differs from the exam file',
    'frozen_elsewhere': 'another run froze this exam first',
    'not_kept': 'the frozen exam was not kept in the bucket',
}
VALIDITY_WORDS = {
    'valid': 'still valid', 'evidence_changed': 'evidence changed', 'could_not_recompute': 'could not recompute',
    'missing': 'missing', 'context_changed': 'context record changed', 'no_longer_decided': 'no longer decided',
    'decided_again': 'decided again',
}
RECOMPUTE_WORDS = {
    'past_award_stage': 'past the award stage', 'decided_group_twin': 'twin in a decided group',
    'twin_not_unique': 'twin not unique', 'recompute_error': 'recompute error', 'key_not_current': 'key not current',
}
SPLIT_WORDS = {'matched_directly': 'matched directly', 'recovered_by_twin': 'recovered by twin'}
BAND_WORDS = {'certain': 'Certain', 'probable': 'Probable', 'unsure': 'Unsure', 'unverifiable': 'Unverifiable',
              'ruleNotMet': 'Rule not met'}
FAIL_REASON_WORDS = {
    'proof_missing': 'proof missing', 'document_false': 'document false', 'documents_differ': 'documents differ',
    'interview_differs': 'interview differs', 'other': '"other"', 'not_given': 'no reason stored',
}
OUTCOME_WORDS = {'right_sure': 'right and sure', 'right_leaning': 'right but leaning', 'unsure': 'unsure',
                 'wrong_leaning': 'wrong but leaning', 'wrong_sure': 'wrong and sure'}
GRADE_WORDS = {'pass': 'pass', 'fail': 'fail', 'no_change': 'no clear change'}
COACH_REASON_WORDS = {
    'coverage_dropped': 'coverage dropped', 'generous_wrong_rose': 'generous-wrong rose',
    'score_up': 'score went up', 'no_clear_change': 'no clear change', 'score_down': 'score went down',
}
#: Malformed-record kinds: `coach_grade.MALFORMED_LABELS`, `coach_grade.OTHER_ERROR` and the built-in
#: error classes a record can raise. Any other kind (the allow-list lets any short identifier through)
#: is counted under `OTHER_WORDS` and never printed.
MALFORMED_WORDS = {
    'too_short': 'record too short', 'not_a_datetime': 'decided time is not a date and time',
    'no_offset': 'decided time has no time zone', 'other_error': 'other error',
    'TypeError': 'a value of the wrong type', 'ValueError': 'a bad value', 'KeyError': 'a missing key',
    'IndexError': 'a missing item', 'LookupError': 'a missing key or item', 'AttributeError': 'a missing attribute',
}
UNKNOWN_VERSION_WORDS = {'(unknown version)': 'version not recorded',
                         'pre-versioning': 'made before versions were recorded'}
CAVEATS = (
    'The exam lens turns a Fail the QC disagreed with into a Pass. The coach grade keeps the reviewer\'s '
    'stored answer. So the two can differ on those facts.',
    'A coach grade moves from run to run on small numbers. "No clear change" means the difference is not '
    'bigger than luck.',
    'Counts only: this section holds no case id and no name.',
)


def words_for(table: dict, code) -> str:
    """The plain words for a fixed ``code``; `OTHER_WORDS` for anything not in ``table``."""
    return table.get(code, OTHER_WORDS) if type(code) is str else OTHER_WORDS


def counts_in_words(counts: dict, table: dict) -> str:
    """``label N, label N`` in the table's order; keys missing from the table are summed under
    `OTHER_WORDS` (never printed)."""
    parts = [f'{words} {counts[code]}' for code, words in table.items() if code in counts]
    unlisted = [value for code, value in counts.items() if code not in table]
    if unlisted:
        parts.append(f'{OTHER_WORDS} {sum(unlisted)}')
    return ', '.join(parts) or 'none'


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _of(pair: dict) -> str:
    return f'{pair["count"]} of {pair["of"]}'


# ── the checks: (error code, None) or (None, the checked JSON form) ──────────────────────────────────
def lens_result_checked(result):
    if result is None:
        return LS.NO_OUTPUT, None
    if type(result) is dict and frozenset(result) == LS.ERROR_KEYS:
        code = result['error']
        return (code if type(code) is str and code in LENS_SHOWN_ERRORS else LS.SCHEMA), None
    data = json.loads(LS.checked_result_text(result))
    if not LS.human_lens_result_allowed(data) or frozenset(data) == LS.ERROR_KEYS:
        return LS.SCHEMA, None
    return None, data


def coach_result_checked(result):
    if result is None:
        return LS.NO_OUTPUT, None
    if type(result) is dict and frozenset(result) == CS.ERROR_KEYS:
        code = result['error']
        return (code if type(code) is str and code in COACH_SHOWN_ERRORS else LS.SCHEMA), None
    data = json.loads(CS.checked_coach_text(result))
    if not CS.coach_result_allowed(data) or frozenset(data) == CS.ERROR_KEYS:
        return LS.SCHEMA, None
    return None, data


def _failed_line(prefix: str, code: str) -> str:
    return (f'- {prefix}: {code}. {BLOCKING}. Meaning: {words_for(ERROR_WORDS, code)}. '
            f'There is no result, so {NOT_A_PASS[0].lower()}{NOT_A_PASS[1:]}')


def _not_run_line(code: str) -> str:
    return f'- not run: {code}. Meaning: {words_for(REFUSAL_WORDS, code)}. {NOT_A_PASS}'


# ── the summary line ──────────────────────────────────────────────────────────────────────────────────
def _summary_line(lens_error, lens, coach_error, coach) -> str:
    blocking, not_run, no_grade = [], [], []
    if lens_error is not None:
        blocking.append('human lens (failed)')
    else:
        for name in L.EXAM_NAMES:
            exam = lens['exams'][name]
            if exam['refusal'] is not None:
                not_run.append(f'{name} (refused)')
            elif exam['frozen'] is not True:
                no_grade.append(f'{name} (not frozen yet)')
            elif exam['score']['too_few']:
                no_grade.append(f'{name} ({TOO_FEW})')
    if coach_error is not None:
        blocking.append('coach grade (failed)')
    elif frozenset(coach) == CS.REFUSAL_KEYS:
        not_run.append('coach grade (refused)')
    else:
        blocking += [f'coach pair {p["previous"]["version"]} to {p["new"]["version"]} (fail)'
                     for p in coach['coach'] if p['grade'] == 'fail']
        if not coach['coach']:
            no_grade.append('coach grade (no pair to grade yet)')
    line = f'{BLOCKING}: {len(blocking)} item(s): {", ".join(blocking)}.' if blocking else 'No blocking item.'
    if not_run:
        line += f' Not run: {", ".join(not_run)}.'
    if no_grade:
        line += f' No grade yet: {", ".join(no_grade)}.'
    return line


# ── the human lens ────────────────────────────────────────────────────────────────────────────────────
def _lens_top_lines(lens: dict) -> list:
    def count(key):
        return 'not read' if lens[key] is None else str(lens[key])
    failed = lens['context_failed_line'] or f'{L.FAILED_CONTEXT_LINE}: not read'
    return [f'- Engine version: {lens["engine_version"] or "not read"}.',
            f'- Cases read: {count("cases_read")}. Not decided: {count("not_decided")}. '
            f'No human verdict: {count("no_human_verdict")}.',
            f'- {_capital(failed)}.']


def _second_line_text(line: dict) -> str:
    """A ``score without ... Fails`` line (an exam's, or a coach cell's or side's ``without_left_out``)."""
    if line['too_few']:
        facts = f' ({line["facts"]} facts)' if 'facts' in line else ''
        return f'{TOO_FEW}{facts}. {NOT_A_PASS}'
    return (f'{line["facts"]} facts, {line["points"]} points of {line["best"]} best, score {line["score_pct"]}%, '
            f'{line["left_out"]} left out.')


def _exam_score_lines(score: dict) -> list:
    if score['too_few']:
        return [f'- Score: {TOO_FEW} ({score["facts"]} facts). {NOT_A_PASS}']
    return [f'- Score: {score["facts"]} facts, {score["points"]} points of {score["best"]} best, '
            f'score {score["score_pct"]}%, {score["not_scored"]} not scored.',
            f'- Outcomes: {counts_in_words(score["outcomes"], OUTCOME_WORDS)}.',
            f'- Coverage: {_of(score["coverage"])}. Generous-wrong: {_of(score["generous_wrong"])}.']


def _fails_lines(fails: dict) -> list:
    table = fails['by_band_and_reason']
    first_row = next(iter(table.values()), {})
    reasons = [code for code in FAIL_REASON_WORDS if code in first_row]
    out = [f'- Fails: {fails["fails"]}. By band and reason (interview Fails are counted apart, below):', '',
           '| Band | ' + ' | '.join(FAIL_REASON_WORDS[r] for r in reasons) + ' |',
           '|---|' + '---|' * len(reasons)]
    out += [f'| {BAND_WORDS[band]} | ' + ' | '.join(str(table[band][r]) for r in reasons) + ' |'
            for band in BAND_WORDS if band in table]
    share = fails['share_other']
    tail = ', too few to give a share' if share['too_few'] else f' ({share["pct"]}%)'
    return out + ['', f'- Interview Fails by band: {counts_in_words(fails["interview_by_band"], BAND_WORDS)}.',
                  f'- Share of "other" among the Fails: {_of(share)}{tail}.']


def _sat_exam_lines(exam: dict) -> list:
    """The lines of an exam that sat (frozen)."""
    out = [f'- Validity: {counts_in_words(exam["validity"], VALIDITY_WORDS)}.', f'- {_capital(exam["still_valid"])}.']
    if exam['valid_split'] is None:
        out.append('- Valid split and could-not-recompute reasons: not kept for this exam.')
    else:
        out += [f'- Valid split: {counts_in_words(exam["valid_split"], SPLIT_WORDS)}.',
                f'- Could not recompute, by reason: '
                f'{counts_in_words(exam["could_not_recompute_reasons"], RECOMPUTE_WORDS)}.']
    out.append(f'- Fails the QC turned to Pass: {exam["qc_turned_to_pass"]}.')
    out += _exam_score_lines(exam['score'])
    extra = exam['score_without_interview_fails']
    out.append(f'- {_capital(extra["label"])}: {_second_line_text(extra)}')
    return out + _fails_lines(exam['fails'])


def _exam_lines(name: str, exam: dict) -> list:
    out = [f'#### {name}: {exam.get("label", LS.EXAM_LABELS[name])}', '']
    if exam['refusal'] is not None:
        out.append(_not_run_line(exam['refusal']))
    out.append(f'- Status: {exam["status"]}.')
    if frozenset(exam) == LS.EXAM_DEBUG_KEYS:
        return out
    if exam['frozen'] is True:
        key_check = exam['key_check'] or 'not used for this exam'
        out.append(f'- Frozen: yes, at {exam["frozen_at"]}. Size: {exam["size"]}. Digest: {exam["digest"]}. '
                   f'Key check: {key_check}.')
    else:
        out.append('- Frozen: no.')
    if exam['candidates'] is not None:
        out.append(f'- Candidates: {exam["candidates"]}.')
    if exam['cases_with_other_key_check'] is not None:
        out.append(f'- Cases with another key check: {exam["cases_with_other_key_check"]}.')
    if exam['frozen'] is True:
        out += _sat_exam_lines(exam)
    elif exam['refusal'] is None:
        out.append(f'- No score: the exam is not frozen yet. {NOT_A_PASS}')
    if exam['known_limits']:
        out.append(f'- Known limits: {"; ".join(exam["known_limits"])}.')
    return out


def _lens_lines(error, lens) -> list:
    out = ['### Human lens', '']
    if error is not None:
        return out + [_failed_line('lens failed', error)]
    out += _lens_top_lines(lens)
    for name in L.EXAM_NAMES:
        out += [''] + _exam_lines(name, lens['exams'][name])
    return out


# ── the coach grade ───────────────────────────────────────────────────────────────────────────────────
def _second_label(left_out_reasons: list) -> str:
    if left_out_reasons == ['interview_differs']:
        return L.EXTRA_LINE_LABEL
    return 'score without left-out Fails'


def _side_text(side: dict) -> str:
    if side['too_few']:
        return f'{TOO_FEW}. {NOT_A_PASS}'
    return (f'{side["facts"]} facts, score {side["score_pct"]}%, coverage {_of(side["coverage"])}, '
            f'generous-wrong {_of(side["generous_wrong"])}.')


def _version_words(cell: dict) -> str:
    if cell['unknown_version']:
        return f'unknown: {words_for(UNKNOWN_VERSION_WORDS, cell["version"])}'
    return cell['version']


def _month_table(coach: dict, second: str) -> list:
    if not coach['months']:
        return ['No month has a marked fact yet.']
    extra = bool(coach['left_out_reasons'])
    head = ['Version', 'Month', 'Facts', 'Points', 'Best', 'Score %', 'Not scored', 'Outcomes']
    head += [_capital(second)] if extra else []
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for cell in coach['months']:
        row = [_version_words(cell), cell['month']]
        if cell['too_few']:
            row += [TOO_FEW] + ['-'] * (len(head) - 3)
        else:
            row += [str(cell[k]) for k in ('facts', 'points', 'best', 'score_pct', 'not_scored')]
            row.append(counts_in_words(cell['outcomes'], OUTCOME_WORDS))
            row += [_second_line_text(cell[CS.EXTRA_LINE])] if extra else []
        out.append('| ' + ' | '.join(row) + ' |')
    return out


def _side_lines(role: str, side: dict, second: str) -> list:
    out = [f'  - {role}, {side["version"]}: {_side_text(side)}']
    if CS.EXTRA_LINE in side:
        out.append(f'  - {role}, {second}: {_second_line_text(side[CS.EXTRA_LINE])}')
    return out


def _pair_lines(pairs: list, second: str) -> list:
    if not pairs:
        return ['No pair to grade yet: a grade needs two versions that each reach the coach floor.']
    out = []
    for pair in pairs:
        mark = f' {BLOCKING}.' if pair['grade'] == 'fail' else ''
        reasons = ', '.join(words_for(COACH_REASON_WORDS, r) for r in pair['reasons'])
        out.append(f'- {pair["previous"]["version"]} to {pair["new"]["version"]}: '
                   f'{words_for(GRADE_WORDS, pair["grade"])}.{mark} Reasons: {reasons}. '
                   f'Versions skipped between them: {pair["skipped_versions"]}.')
        out += _side_lines('Previous', pair['previous'], second) + _side_lines('New', pair['new'], second)
    return out


def _waiting_lines(waiting: list, second: str) -> list:
    if not waiting:
        return ['No version is waiting.']
    out = []
    for side in waiting:
        so_far = '' if side['too_few'] else f' So far: {_side_text(side)}'
        out.append(f'- {side["version"]}: {TOO_FEW}. {NOT_A_PASS}{so_far}')
        if CS.EXTRA_LINE in side:
            out.append(f'  - {_capital(second)}: {_second_line_text(side[CS.EXTRA_LINE])}')
    return out


def _coach_top_lines(coach: dict, second: str) -> list:
    kinds = counts_in_words(coach['malformed_by_error'], MALFORMED_WORDS)
    left_out = coach['left_out_reasons']
    if left_out:
        reasons = ', '.join(words_for(FAIL_REASON_WORDS, r) for r in left_out)
        left_line = f'- The line "{second}" leaves out Fails with reason: {reasons}.'
    else:
        left_line = '- Nothing is left out, so there is no second score line.'
    return [f'- Floors: a month needs {coach["cell_min_facts"]} facts for a score; a version needs '
            f'{coach["coach_min_facts"]} facts to be graded.',
            f'- Guard level: {coach["guard_alpha"]["count"]} in {coach["guard_alpha"]["of"]}. Score margin: {coach["score_z"]} standard errors.',
            f'- Decided records: {coach["decided_records"]}. Versions without marks: '
            f'{coach["versions_without_marks"]}.',
            f'- Malformed records: {coach["malformed_records"]} (by kind: {kinds}).', left_line]


def _coach_lines(error, coach) -> list:
    out = ['### Coach grade', '']
    if error is not None:
        return out + [_failed_line('coach grade failed', error)]
    if frozenset(coach) == CS.REFUSAL_KEYS:
        return out + [_not_run_line(coach['refusal'])]
    second = _second_label(coach['left_out_reasons'])
    out += _coach_top_lines(coach, second)
    out += ['', '#### Monthly score', ''] + _month_table(coach, second)
    out += ['', '#### Coach pairs', ''] + _pair_lines(coach['coach'], second)
    out += ['', '#### Waiting versions', ''] + _waiting_lines(coach['waiting'], second)
    return out


#: The error classes a render can raise on a result its checks let through (a key or item missing, a
#: value of the wrong type or shape). `parent.main` catches ONLY these and then prints `RENDER_FAILED_LINE`.
RENDER_ERRORS = (LookupError, TypeError, ValueError, AttributeError)
#: The one line `parent.main` prints in place of the two sections when the render raised: fixed words only,
#: nothing from either result and no error message.
RENDER_FAILED_LINE = f'lens report failed. {BLOCKING}. There is no result, so this is not a pass.'


def lens_coach_report(human_lens, coach_grade) -> tuple:
    """(lines, failed): the two sections as markdown lines - the summary line first, then the human lens,
    the coach grade and (when either is clean) the fixed caveats - and True when either result failed
    its check (a refusal is a result, not a failure). A None result is the ``no_output`` failure. The
    one path for both callers: `lens_coach_section_lines` (the markdown report) and `parent.main`."""
    lens_error, lens = lens_result_checked(human_lens)
    coach_error, coach = coach_result_checked(coach_grade)
    out = [HEADING, '', _summary_line(lens_error, lens, coach_error, coach), '']
    out += _lens_lines(lens_error, lens) + [''] + _coach_lines(coach_error, coach)
    if lens_error is None or coach_error is None:
        out += ['', '### Read with care', ''] + [f'- {line}' for line in CAVEATS]
    return out, lens_error is not None or coach_error is not None


def lens_coach_section_lines(human_lens, coach_grade) -> list:
    """The two sections as markdown lines (`lens_coach_report`, without the failed flag)."""
    return lens_coach_report(human_lens, coach_grade)[0]
