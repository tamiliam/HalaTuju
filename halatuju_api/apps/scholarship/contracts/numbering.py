"""Contract module: the languages, the clause-level limits and the clause numbering.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""


# The three languages the module carries. English is authoritative.
LANGUAGES = ('en', 'ms', 'ta')

# Config fields an author may set on a draft (whitelist for update_config).
_CONFIG_FIELDS = (
    'title_en', 'title_ms', 'title_ta',
    'preamble_en', 'preamble_ms', 'preamble_ta',
    'progress_standard_en', 'progress_standard_ms', 'progress_standard_ta',
    'counterparty_name', 'counterparty_title', 'counterparty_nric',
    'counterparty_address',
    'counterparty_notify_emails', 'parent_role', 'parent_pin_required',
    'witness_policy',
)

# Clause hierarchy (2026-07-19): three levels — 0 clause, 1 sub-clause, 2 sub-sub-clause.
MAX_CLAUSE_LEVEL = 2
# The comprehension quiz may be attached at a CLAUSE (0) or SUB-CLAUSE (1), not a sub-sub-clause (2)
# — owner 2026-07-25. A flagged clause's quiz covers its whole subtree, so a clause and any of its
# own descendants are MUTUALLY EXCLUSIVE (never both flagged); overlap is prevented at save
# (`replace_clauses`) and in the editor. The individual level-2 items are too granular for a
# checkpoint and stay ineligible.
MAX_QUIZ_LEVEL = 1
_ROMAN = ((10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i'))

# ContractClause.heading_* is CharField(max_length=255); body_* is TextField (unlimited).
# HEADING_MAX_LEN is the hard DB limit (the save guard); a "heading" longer than
# HEADING_TITLE_MAX is treated as a SENTENCE (clause body), not a short title — real docs
# style full sub-clauses as a Heading, which would otherwise overflow the column (TD, 2026-07-21).
HEADING_MAX_LEN = 255
HEADING_TITLE_MAX = 120


def _fit_heading(heading, body):
    """Keep a clause heading inside the varchar(255) column: a heading longer than the limit
    is not a title — fold it into the body (lossless) so a save can NEVER overflow, whatever
    the source (import, Gemini, hand-typed, copy-from). Returns (heading, body)."""
    heading = (heading or '').strip()
    body = body or ''
    if len(heading) <= HEADING_MAX_LEN:
        return heading, body
    return '', (heading + '\n\n' + body).strip() if body else heading


def _roman(n):
    """Lowercase roman numeral for n >= 1 (i, ii, iii, iv, v, …). Small n only (clause depth)."""
    out = []
    for value, sym in _ROMAN:
        while n >= value:
            out.append(sym)
            n -= value
    return ''.join(out)


def normalise_levels(levels):
    """Clamp each level to 0..MAX and forbid SKIPPING a level: a clause may be at most one level
    deeper than the clause before it (the first is forced to 0); going shallower is unrestricted.
    Returns the cleaned list — the single place the no-skip rule lives (both import and save use it)."""
    out = []
    prev = -1  # first allowed level is 0
    for lv in levels:
        try:
            lv = int(lv)
        except (TypeError, ValueError):
            lv = 0
        lv = max(0, min(MAX_CLAUSE_LEVEL, lv))
        if lv > prev + 1:
            lv = prev + 1
        out.append(lv)
        prev = lv
    return out


def clause_numbers(levels):
    """Display label per clause from its level run (Word-document style): level 0 → '1.', '2.';
    level 1 → '1.1.', '1.2.'; level 2 → 'I.', 'II.' (uppercase roman). Levels are assumed already
    valid (see normalise_levels). This is the ONE numbering source of truth — the FE mirror in
    lib/clauseNumbering.ts must match it (paired test). Numbers are computed, never stored, so
    reorder/insert always renumbers correctly."""
    counters = [0, 0, 0]
    labels = []
    for lv in levels:
        lv = max(0, min(MAX_CLAUSE_LEVEL, int(lv)))
        counters[lv] += 1
        for deeper in range(lv + 1, MAX_CLAUSE_LEVEL + 1):
            counters[deeper] = 0
        # Word-document style (owner choice 2026-07-21): 1.  /  1.1.  /  I.
        # (uppercase roman for sub-sub-clauses, full stops throughout).
        if lv == 0:
            labels.append(f'{counters[0]}.')
        elif lv == 1:
            labels.append(f'{counters[0]}.{counters[1]}.')
        else:
            labels.append(f'{_roman(counters[2]).upper()}.')
    return labels
