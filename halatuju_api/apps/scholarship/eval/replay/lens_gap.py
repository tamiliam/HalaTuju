"""LL7 - the GAP table of an exam: where the replayed AI lost its points against the human answer. PURE: no
database, network, clock or environment read; the scoring modules are imported inside functions only.
`lens_score.exam_score` is the only caller of `gap_block`; `lens_result_schema` checks the block with the
helpers below, so the builder and the check share one rule.

THE FACTS. Exactly the marked facts the exam's score counts: `ai_score.decided_facts` on each valid case,
band not None (the band is `fact_bands.fact_band`, read through `decided_facts`). So the facts of the
groups add up to the score's facts, and their points to the score's points.

THE BLOCK. Counts only; every key comes from a fixed set or a strict shape.
* ``groups``: band x answer -> ``facts``, ``points`` (facts x `ai_score.POINTS` of that band and answer),
  ``lost`` (`ai_score.BEST_PER_FACT` x facts - points: what a perfect AI would have scored more) and
  ``too_small`` (fewer than `GAP_MIN_FACTS` facts). THE INVARIANT (`gap_sums_hold`): the sum of ``lost``
  is 2 x the facts marked - the score's points.
* ``by_fact``: fact -> band -> answer -> facts.
* ``by_doubt_code``: fact -> doubt code -> ``passed`` / ``failed``, over the marked facts whose band is
  not Certain. The codes are those `audit._unresolved_map` reads (the AI audit page's own reading), and
  each one counts as that page counts it: once each time the fact lists it, so a code listed twice counts
  twice. A code outside `DOUBT_CODES` (or not text) counts under `OTHER_DOUBT_CODE`, so no other text
  can reach the result.
* ``by_programme``: the case's programme id (digits) or `NO_PROGRAMME` -> band -> answer -> facts.
* ``top``: up to `TOP_GROUPS` groups by ``lost``, largest first; ties in band order, then answer order.
  A too-small group, and a group that lost nothing, is never ranked.
"""
from __future__ import annotations

#: A group with fewer facts than this is too small: it is shown, never ranked.
GAP_MIN_FACTS = 10
#: How many groups `top` ranks.
TOP_GROUPS = 3
#: The reviewer's answers, in the order the table shows them (`ai_score.POINTS` keys; a test pins it).
ANSWERS = ('pass', 'fail')
#: The one key every doubt code outside `DOUBT_CODES` is counted under.
OTHER_DOUBT_CODE = 'unlisted_code'
#: The programme key of a case with no programme.
NO_PROGRAMME = 'none'
#: The most programme keys the result may hold (the allow-list refuses more).
GAP_MAX_PROGRAMMES = 50
GAP_KEYS = frozenset({'groups', 'by_fact', 'by_doubt_code', 'by_programme', 'top'})
GROUP_KEYS = frozenset({'facts', 'points', 'lost', 'too_small'})
TOP_GROUP_KEYS = frozenset({'band', 'answer', 'facts', 'lost'})
DOUBT_COUNT_KEYS = frozenset({'passed', 'failed'})

#: THE CLOSED LIST of doubt codes: every code the verdict engine writes in an item (its ``_item('...')``
#: literals, and the four codes of its two variable call sites). A test scans the engine and fails when
#: the engine has a code this list lacks, or this list a code the engine no longer has.
DOUBT_CODES = frozenset({
    'academic_extra_subjects', 'academic_grade_band_mismatch', 'academic_grade_mismatch',
    'academic_grade_uncertain', 'academic_grades_unchecked', 'academic_missing_subjects',
    'academic_slip_rows_unread',
    'birth_cert_mismatch', 'birth_cert_missing', 'birth_cert_not_genuine', 'birth_cert_unreadable',
    'document_not_genuine',
    'earner_ic_missing', 'earner_ic_present', 'earner_ic_unreadable',
    'father_patronymic_mismatch',
    'grades_unverified', 'grades_verified',
    'guardianship_letter_missing', 'guardianship_letter_not_genuine', 'guardianship_letter_unreadable',
    'higher_results_cgpa_mismatch', 'higher_results_cgpa_ok', 'higher_results_cgpa_unread',
    'higher_results_grade_mismatch', 'higher_results_grade_uncertain', 'higher_results_is_spm',
    'higher_results_kind_differs', 'higher_results_kind_ok', 'higher_results_missing',
    'higher_results_name_mismatch', 'higher_results_name_near', 'higher_results_name_ok',
    'higher_results_not_checked', 'higher_results_not_declared', 'higher_results_not_final',
    'higher_results_not_on_file', 'higher_results_not_results', 'higher_results_subjects_missing',
    'higher_results_subjects_unrecognised', 'higher_results_undeclared', 'higher_results_unreadable',
    'higher_results_unverified',
    'household_size_confirm',
    'ic_low_confidence', 'ic_missing', 'ic_service_down', 'ic_unreadable',
    'income_above_b40_line', 'income_declared_accepted_evidenced', 'income_declared_accepted_str',
    'income_declared_needs_evidence', 'income_declared_probable', 'income_earner_undeclared',
    'income_not_means_tested', 'income_per_capita_ok', 'income_proof_missing', 'income_proof_present',
    'income_salary_probable', 'income_salary_unsure', 'income_unverified_needs_interview',
    'name_match', 'name_mismatch', 'name_resolved_truncation',
    'nric_match', 'nric_mismatch',
    'offer_issuer_not_checked', 'offer_letter_missing', 'offer_name_mismatch', 'offer_no_identity',
    'offer_not_official', 'offer_not_read_yet', 'offer_programme', 'offer_reporting_official',
    'offer_unreadable',
    'pathway_confirm', 'pathway_confirmed', 'pathway_declared', 'pathway_funded_or_abroad',
    'pathway_offer_private', 'pathway_start_year_outside', 'pathway_start_year_unknown',
    'pathway_type_switch', 'pathway_undeclared',
    'relationship_confirmed',
    'results_slip_is_higher', 'results_slip_missing', 'results_slip_name_mismatch',
    'results_slip_name_near', 'results_slip_name_ok', 'results_slip_unreadable',
    'str_not_current', 'str_present_unverified', 'str_recipient_mismatch', 'str_verified',
    'unemployment_epf_corroborated',
    'utility_hardship', 'utility_percapita_b40', 'utility_percapita_high',
})


def gap_cell(band: str, answer: str, facts: int) -> dict:
    """One group: its facts, its points (`ai_score.POINTS`, never re-typed), what it lost, too small."""
    from apps.scholarship import ai_score
    points = facts * ai_score.POINTS[(band, answer)]
    return {'facts': facts, 'points': points, 'lost': ai_score.BEST_PER_FACT * facts - points,
            'too_small': facts < GAP_MIN_FACTS}


def gap_ranked(groups: dict) -> list:
    """`top`: the largest `TOP_GROUPS` groups by ``lost`` (see the module docstring)."""
    from apps.scholarship.fact_bands import BANDS
    cells = [(band, answer, groups[band][answer]) for band in BANDS for answer in ANSWERS]
    kept = [c for c in cells if not c[2]['too_small'] and c[2]['lost'] > 0]
    kept.sort(key=lambda c: -c[2]['lost'])          # a stable sort: ties stay in band, then answer, order
    return [{'band': band, 'answer': answer, 'facts': cell['facts'], 'lost': cell['lost']}
            for band, answer, cell in kept[:TOP_GROUPS]]


def gap_sums_hold(gap: dict, facts: int, points: int) -> bool:
    """THE INVARIANT: the groups hold ``facts`` facts, and their ``lost`` adds up to 2 x facts - points."""
    from apps.scholarship import ai_score
    cells = [cell for row in gap['groups'].values() for cell in row.values()]
    return (sum(cell['facts'] for cell in cells) == facts
            and sum(cell['lost'] for cell in cells) == ai_score.BEST_PER_FACT * facts - points)


def _gap_table() -> dict:
    from apps.scholarship.fact_bands import BANDS
    return {band: dict.fromkeys(ANSWERS, 0) for band in BANDS}


def _gap_entries(snapshot) -> list:
    """The snapshot entries the audit reader can read safely: an object with a fact name in text and an
    ``unresolved`` that is a list or empty (any other entry is left out of the doubt codes only)."""
    return [entry for entry in (snapshot if isinstance(snapshot, list) else [])
            if isinstance(entry, dict) and isinstance(entry.get('fact'), str) and entry['fact']
            and (not entry.get('unresolved') or isinstance(entry['unresolved'], list))]


def _gap_code(code) -> str:
    return code if type(code) is str and code in DOUBT_CODES else OTHER_DOUBT_CODE


def gap_block(records: list, programmes: list) -> dict:
    """The gap block of ``records`` (``(snapshot, answer, version)`` per valid case, as the score reads
    them) and ``programmes`` (the programme id or None of each case, in the same order)."""
    from apps.scholarship import ai_score, audit
    from apps.scholarship.fact_bands import BANDS, CERTAIN
    if len(records) != len(programmes):
        raise ValueError('gap: one programme per case')
    cells = _gap_table()
    by_fact = {fact: _gap_table() for fact in ai_score.FACTS}
    by_doubt = {fact: {} for fact in ai_score.FACTS}
    by_programme: dict = {}
    for (snapshot, answer, _version), programme in zip(records, programmes):
        codes = audit._unresolved_map(_gap_entries(snapshot))
        key = NO_PROGRAMME if programme is None else str(programme)
        for fact, band, officer in ai_score.decided_facts(snapshot, answer):
            if band is None:
                continue
            cells[band][officer] += 1
            by_fact[fact][band][officer] += 1
            by_programme.setdefault(key, _gap_table())[band][officer] += 1
            if band == CERTAIN:
                continue
            for code in codes.get(fact, ()):
                entry = by_doubt[fact].setdefault(_gap_code(code), dict.fromkeys(('passed', 'failed'), 0))
                entry['passed' if officer == 'pass' else 'failed'] += 1
    groups = {band: {a: gap_cell(band, a, cells[band][a]) for a in ANSWERS} for band in BANDS}
    return {'groups': groups, 'by_fact': by_fact, 'by_doubt_code': by_doubt, 'by_programme': by_programme,
            'top': gap_ranked(groups)}
