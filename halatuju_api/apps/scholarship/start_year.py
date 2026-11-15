"""The course-start-year rule per intake year — H3 (#597, owner 2026-11-15).

An intake year may accept only students whose course STARTED in chosen calendar years
(`ScholarshipCohort.allowed_start_years`, e.g. the Degree round's ``[2025, 2026]``). EMPTY = the
rule is not applied (the list form of "the value is the switch", as `allowed_birth_states`), so
every gift that has not set it keeps today's behaviour. The Sabah gift allows earlier starters:
it leaves the list empty.

⚠ WHY THIS IS NOT A SHORTLISTING GATE. The start year is read from the OFFER LETTER
(`possible_start_years`, its own conservative reading; the money keeps
`pathway_engine.course_start_year`), and the letter arrives after the shortlist. So the rule lives
where the TD-617 programme rule lives (`verdict_pathway.funded_or_abroad`): the Pathway fact.

  * a year OUTSIDE the list → the Pathway fact turns RED ('gap') with `pathway_start_year_outside`.
    It is an `award.CONFIDENT_DISQUALIFIER` (the cockpit flag) and, being red, it joins QC's
    red-fact floor (an accept needs a recorded reason). Nothing is declined automatically and the
    amount does not move: the reviewer decides.
  * a year that CANNOT BE READ off a letter that was read → `pathway_start_year_unknown`, a reviewer
    line that changes NO band and blocks nothing (owner-approved: a person checks, never an
    automatic fail). No line while the letter is not read yet (`read_deferred`, the TD-396 rule) or
    when there is no letter (`offer_letter_missing` already says so).

Neither code is a student ticket (`resolution.CODE_TO_TICKET`): the student cannot "fix" a start year.
"""

FIELD = 'allowed_start_years'
OUTSIDE = 'pathway_start_year_outside'
UNKNOWN = 'pathway_start_year_unknown'

#: The years an admin may store. Wide on purpose; a typo like 20255 is refused, never trimmed.
MIN_YEAR, MAX_YEAR = 2000, 2100


def normalise_years(value):
    """An `allowed_start_years` value from an admin request → ``(stored_list, ok)``.

    It REFUSES, it never drops (request #30's lesson, as `birth_state.normalise_states`): a list
    holding one bad entry is refused whole. ``None`` or ``[]`` clears the rule. Each entry must be a
    whole number (a JSON boolean is not one) between `MIN_YEAR` and `MAX_YEAR`. Duplicates collapse
    and the list is stored in order, so the same choice is always stored the same way."""
    if value is None:
        return [], True
    if not isinstance(value, list):
        return None, False
    out = set()
    for v in value:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v):
            return None, False
        if not MIN_YEAR <= int(v) <= MAX_YEAR:
            return None, False
        out.add(int(v))
    return sorted(out), True


def stored_years(value):
    """A STORED `allowed_start_years` → its years as ints, in order. The ONE reader of the stored
    value (the verdict and the Rules tab's row), so what is enforced and what is shown agree.

    Only a database edit can store anything but a list of whole years. An entry that is not a year
    is DROPPED from the reading but the rule stays ON (`rule_on`), so a list of junk accepts nobody
    and every case shows red, rather than the rule silently switching off."""
    if not value:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    out = set()
    for v in items:
        try:
            if isinstance(v, bool):
                continue
            out.add(int(str(v).strip()))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def rule_on(value):
    """True when the stored value switches the rule on (anything non-empty)."""
    return bool(value)


def readable_years(years):
    """``[2026]`` → '2026'; ``[2025, 2026]`` → '2025, 2026'. Commas only: the string goes into the
    en / ms / ta copy as a parameter, so it must carry no English word."""
    return ', '.join(str(y) for y in years)


def possible_start_years(application):
    """The years the course may have started in, for THIS rule only (`session_year.gift_start_years`,
    conservative: empty = unknown). Never the money's reading: award sizing and the funding
    estimate read `pathway_engine.course_start_year`, main's reading, unchanged (H3a rebuild)."""
    from .pathway_engine import _latest_offer, is_confirmation_letter, student_offer_check
    from .session_year import gift_start_years, looks_stpm
    rd = getattr(application, 'reporting_date', None)
    stored_year = rd.year if rd else None
    from .award import _sized_as_stpm               # a Form 6 student (not a degree-bound one)
    stpm = _sized_as_stpm(application)
    offer = _latest_offer(application)
    if offer is None:
        return frozenset({stored_year}) if stored_year else frozenset()
    chk = student_offer_check(offer)
    words = ' '.join(chk.get(k) or '' for k in ('programme', 'institution', 'stream', 'intake'))
    return gift_start_years(chk.get('intake') or '', chk.get('reporting_date') or '',
                            stored_year=stored_year, confirmation=is_confirmation_letter(offer),
                            stpm=stpm or looks_stpm(words))


def reading(application):
    """None when the intake sets no years; else ``{state, start_year, years}`` where state is
    'inside', 'outside' or 'unknown' (no start year could be established, start_year None).

    The course may have started in one year or in either of a session's two (`possible_start_years`):
    all of them in the list → inside; none of them → outside (start_year names them all, '2023,
    2024'); some in and some out, or none known → unknown, so a person checks, never an automatic
    fail."""
    value = getattr(getattr(application, 'cohort', None), FIELD, None)
    if not rule_on(value):
        return None
    years = stored_years(value)
    span = sorted(possible_start_years(application))
    inside = [y in years for y in span]
    if span and all(inside):
        state = 'inside'
    elif span and not any(inside):
        state = 'outside'
    else:
        state = 'unknown'
    return {'state': state, 'start_year': readable_years(span) if state != 'unknown' else None,
            'years': years}


def apply_to_pathway_fact(application, fact):
    """The Pathway fact with the start-year line added (see the module docstring). Returns it."""
    r = reading(application)
    if r is None or r['state'] == 'inside':
        return fact
    from .verdict_engine import _item
    years = readable_years(r['years'])
    if r['state'] == 'outside':
        fact['status'] = 'gap'
        fact['unresolved'].append(_item('pathway_start_year_outside', start_year=str(r['start_year']), years=years))
        return fact
    from .document_snapshot import latest_doc
    from .read_errors import read_deferred
    offer = latest_doc(application, 'offer_letter')
    if offer is None or read_deferred(getattr(offer, 'vision_fields', None)):
        return fact
    fact['unresolved'].append(_item('pathway_start_year_unknown', years=years))
    return fact
