"""The ruling catalogue (design 4.3) and the A / B split.

A difference is EXPECTED (class A) only when an owner ruling below matches it; anything else is
UNEXPLAINED (class B). A record's difference is cut into UNITS: for `verdict.build_verdict` one unit per
fact that changed; for every other engine one unit per top-level field that changed (`facts`, the case
facts, is never a unit). A record is A only when EVERY unit is matched by at least one ruling AND no case
fact changed between the sides (`fact_changes`: a fact such as degree-bound is computed by engine code that
is not replayed, so a gate one side alone sets is B), and the report names every ruling that matched (a unit
two rulings match is listed under both). A status may stay, or fall from Certain / Probable into the
ruling's band; a move out of red or up from Unsure is never A.

Each test is NARROW: it reads the old and new value of ONE unit and non-personal case facts (`facts`:
stored pathway code, degree-bound, start year unknown, stored award, Academic card). There is no "any
change in X" rule. Too narrow is safe (the difference shows as B for the owner); too broad hides a
regression.

Every code a test compares is a REAL engine code and is registered here (`NAMED_CODES`): an unregistered
code is hashed by the scrubber, so a test naming it could never match a real record (R2 review).

Rulings catalogued but NOT encoded (their test is None) never match: their differences stay B until R3
has seen a real record's shape and the owner confirms. So does every PENDING item (not shipped).
No ruling exists for a "moves only" refactor (A3.1, A3.4, A3.6, A3.8, F1 step 2): a difference there is B
by definition.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Optional

from . import scrub

#: Every ruling id, so the report can name it (a literal: the registry takes nothing else).
scrub.register_codes((
    'R-TD465', 'R-TD465-UNKNOWN', 'R-DEG7-AWARD', 'R-DEG7-PATHWAY', 'R-DEG7-ESTIMATE', 'R-DEG7-SCHEDULE', 'R-56',
    'R-62', 'R-388', 'R-OWED', 'R-F1-Q1', 'R-F1-Q4', 'R-67', 'R-3ROUTES', 'R-278', 'R-F1-Q2', 'R-F1-Q3',
    'R-F1-Q6', 'TD-617', 'rulings', 'unit',
    # Every code a ruling test below compares (NAMED_CODES; RulingRegistryTest asserts each is registered,
    # and that every code-shaped literal in this module is).
    'ilkbs', 'iljtm', 'kkom', 'tvet', 'tvet_other', 'mara', 'mara_cert', 'mara_diploma',
    'results_slip_name_mismatch', 'results_slip_name_near', 'higher_results_name_mismatch',
    'higher_results_name_near', 'academic_extra_subjects', 'academic_grades_unchecked',
    'higher_results_not_on_file', 'higher_results_not_declared', 'higher_results_undeclared',
    'academic_slip_rows_unread', 'higher_results_grade_mismatch', 'higher_results_grade_uncertain',
    'verified', 'review', 'recommend', 'gap', 'stpm', 'degree', 'unknown', 'university', 'spm', 'academic_card',
))

# --- the codes the tests compare ------------------------------------------------------------------------

DEGREE_SCHEDULE_AWARDS = (None, '2000.00')
#: R-DEG7's unknown-to-TVET branch: the STORED chosen_pathway code (`facts.pathway_code`, read off the
#: record, not computed by engine code) -> the estimate key(s) decisions 9-12 give it (`funding_estimate`).
STORED_TVET = {
    'ilkbs': frozenset({'ilkbs'}), 'iljtm': frozenset({'iljtm'}), 'kkom': frozenset({'kkom'}),
    'tvet': frozenset({'tvet'}), 'tvet_other': frozenset({'tvet'}),
    'mara': frozenset({'mara_cert', 'mara_diploma'}),
}
TVET_PATHWAYS = frozenset().union(*STORED_TVET.values())
#: R-56: (red, amber) per card: the SPM slip (`verdict_academic`) and the higher results (`higher_results`).
R56_PAIRS = (('results_slip_name_mismatch', 'results_slip_name_near'),
             ('higher_results_name_mismatch', 'higher_results_name_near'))
R62_CODES = frozenset({'academic_extra_subjects', 'academic_grades_unchecked'})
R388_CODE = 'higher_results_not_on_file'                                    # higher_owed.NOTE_CODE
OWED_CODES = frozenset({'higher_results_not_declared', 'higher_results_undeclared'})
F1_Q1_CODES = frozenset({'academic_slip_rows_unread', 'academic_grades_unchecked'})
F1_Q4_PAIR = ('higher_results_grade_mismatch', 'higher_results_grade_uncertain')
STATUSES = ('verified', 'review', 'recommend', 'gap')
PATHWAYS = ('stpm', 'degree', 'unknown', 'university')
#: Every code any test compares. They are registered by the literal call at the top, because the registry
#: takes literals only (test_replay_guards). RulingRegistryTest asserts each one is registered, and that every
#: code-shaped literal in this module is, so a new test cannot name an unregistered code.
NAMED_CODES = tuple(sorted(
    set(STORED_TVET) | TVET_PATHWAYS | {c for pair in R56_PAIRS for c in pair} | R62_CODES | {R388_CODE}
    | OWED_CODES | F1_Q1_CODES | set(F1_Q4_PAIR) | set(STATUSES) | set(PATHWAYS) | {'spm', 'academic_card'}))


@dataclass(frozen=True)
class Unit:
    engine: str
    field: str          # a fact name for the verdict, else the record field
    old: object
    new: object
    old_record: dict
    new_record: dict

    @property
    def facts(self):
        """The case facts BOTH sides agree on: the rule's non-personal gates. A fact the two sides read
        differently is left out (it reads as None), and makes the record B anyway (`fact_changes`)."""
        n = (self.new_record or {}).get('facts') or {}
        o = (self.old_record or {}).get('facts') or {}
        return {k: v for k, v in n.items() if k in o and o[k] == v}

    def both_facts(self, key, value):
        """True when the OLD and the NEW side's case facts both hold ``key`` == ``value``."""
        return all(((r or {}).get('facts') or {}).get(key) == value for r in (self.old_record, self.new_record))


@dataclass(frozen=True)
class Ruling:
    id: str
    citation: str
    engines: tuple
    test: Optional[Callable] = None

    def matches(self, unit):
        return self.test is not None and unit.engine in self.engines and bool(self.test(unit))


# --- helpers ------------------------------------------------------------------------------------------

def _items(part, key):
    return set((part or {}).get(key) or ()) if isinstance(part, dict) else set()


def _added(u, key='unresolved'):
    return _items(u.new, key) - _items(u.old, key)


def _removed(u, key='unresolved'):
    return _items(u.old, key) - _items(u.new, key)


def _status(part):
    return part.get('status') if isinstance(part, dict) else None


FALLS_FROM = ('verified', 'review')
#: R-56 and R-F1-Q4 ARE an owner-ruled red -> amber: exactly one red item swapped for its amber twin.
RED_TO_AMBER_FROM = ('gap',) + FALLS_FROM


def _status_moves(u, allowed, from_=FALLS_FROM):
    """The fact's status is unchanged, or moved from ``from_`` (default Certain / Probable: 'verified' /
    'review') into one of ``allowed``. A move out of red ('gap') or up from Unsure is a softened band and
    never a ruling (B), except for the two red -> amber twin rulings (`RED_TO_AMBER_FROM`)."""
    old, new = _status(u.old), _status(u.new)
    return old == new or (old in from_ and new in allowed)


def _evidence_only_lost(u):
    return not _added(u, 'evidence')


def _params_by_item(part):
    """{(section, code): sorted item hashes} from a fact's `params` (`normalise.item_params`)."""
    out = defaultdict(list)
    for entry in (part.get('params') or ()) if isinstance(part, dict) else ():
        if isinstance(entry, list) and len(entry) == 3:
            out[(entry[0], entry[1])].append(entry[2])
    return {k: sorted(v, key=str) for k, v in out.items()}


def _params_kept(u):
    """Every item present on BOTH sides kept its params (one hash per item): a ruling about one item
    never hides a params change on another."""
    old, new = _params_by_item(u.old), _params_by_item(u.new)
    return all(old[k] == new[k] for k in set(old) & set(new))


def _adds_only(u, codes, *, statuses=('review',)):
    """The fact gained at least one of ``codes`` and nothing else, lost nothing, its status stayed or
    moved to one of ``statuses``, it gained no evidence, and every item it kept kept its params. Present
    on both sides."""
    a = _added(u)
    return (bool(u.old) and bool(u.new) and bool(a) and a <= set(codes) and not _removed(u)
            and _status_moves(u, statuses) and _evidence_only_lost(u) and _params_kept(u))


def _degree_bound(u):
    """Degree-bound on BOTH sides: `results_route.degree_bound` is engine code that is not itself
    replayed, so a candidate that newly sets it must never turn a degree ruling to A unseen."""
    return u.both_facts('degree_bound', True)


def _fact_is(u, *names):
    return u.engine == 'verdict.build_verdict' and u.field in names


def _spm_card(u):
    """The Academic fact sits on the SPM card on BOTH sides (`adapters.app_facts`: academic_card)."""
    return u.both_facts('academic_card', 'spm')


# --- the tests ----------------------------------------------------------------------------------------

def _td465_amount(u):
    f = u.facts
    return (u.field == 'amount' and u.old == '3000.00' and u.new is None
            and f.get('start_unknown') is True and f.get('pathway_code') == 'stpm')


def _td465_unknown(u):
    """Since v3.1.0 an STPM `course_start_unknown` can only go True -> False, and only for a degree-bound
    student under a stale 'stpm' code (`award._sized_as_stpm`, decision 7). Gated on the stored code AND
    degree_bound: with 'stpm' stored and NOT degree-bound the rule is unchanged, so a flip there (a
    course-start read change) stays B. False -> True is never expected: it is a regression (B)."""
    f = u.facts
    return (u.field == 'value' and u.old is True and u.new is False and f.get('pathway_code') == 'stpm'
            and _degree_bound(u))


def _deg7_award(u):
    return (u.field == 'amount' and u.old in ('3000.00', '1000.00', None) and u.new == '2000.00'
            and _degree_bound(u))


def _deg7_pathway_change(old, new, u):
    """Unknown-to-TVET (decisions 10-12) is gated on the STORED pathway code read off the record
    (`facts.pathway_code`), never on engine code: the new category must be the one decisions 9-12 give
    that stored code (`STORED_TVET`). A TVET category reached from a programme name alone stays B."""
    if new == 'degree' and old != 'degree' and _degree_bound(u):
        return True
    return old == 'unknown' and new in STORED_TVET.get(u.facts.get('pathway_code'), ())


def _deg7_classify(u):
    return u.field == 'value' and _deg7_pathway_change(u.old, u.new, u)


def _deg7_estimate(u):
    """Any estimate field, but ONLY when the same record's pathway moved as R-DEG7 rules."""
    old_p = (u.old_record or {}).get('pathway')
    new_p = (u.new_record or {}).get('pathway')
    fields = ('pathway', 'monthly', 'months', 'total', 'known', 'degree', 'practical', 'variable')
    return u.field in fields and _deg7_pathway_change(old_p, new_p, u)


def _deg7_schedule(u):
    """A stale 'stpm' row becomes the university row for a degree-bound student whose stored award is
    empty or RM2,000 (a stored RM3,000 / RM1,000 keeps the STPM row, `6c58efae5`)."""
    old_p = (u.old_record or {}).get('pathway')
    new_p = (u.new_record or {}).get('pathway')
    f = u.facts
    return (old_p == 'stpm' and new_p == 'university' and _degree_bound(u)
            and f.get('stored_award') in DEGREE_SCHEDULE_AWARDS)


def _r56(u):
    """A results name one look-alike letter off: the red name item becomes its amber twin ON THE SAME
    CARD - exactly that one item out and its twin in, nothing else."""
    if not (_fact_is(u, 'academic') and _status_moves(u, ('review',), RED_TO_AMBER_FROM) and _evidence_only_lost(u)
            and _params_kept(u)):
        return False
    return any(_removed(u) == {red} and _added(u) == {amber} for red, amber in R56_PAIRS)


def _r62(u):
    """Request #62: a typed SPM subject not on the slip; amber (review) only. The SPM card only: both codes
    are folded into the higher card too, where F1 Q2 / Q3 rule (not encoded)."""
    return _fact_is(u, 'academic') and _spm_card(u) and _adds_only(u, R62_CODES, statuses=('review',))


def _r388(u):
    """#388 (2026-11-06): an Academic fact already capped for owed higher results (the note on BOTH
    sides: v3.1.0 capped at Probable) falls from Probable / Certain to Unsure (`higher_owed.cap`:
    'recommend'). Nothing added or removed: a new note is not this ruling (B)."""
    return (_fact_is(u, 'academic') and R388_CODE in _items(u.old, 'unresolved')
            and _items(u.old, 'unresolved') == _items(u.new, 'unresolved')
            and _status(u.old) in ('verified', 'review') and _status(u.new) == 'recommend'
            and _evidence_only_lost(u) and _params_kept(u))


def _owed(u):
    """2026-11-07: a degree-bound student owes higher results (`higher_owed.cap` / `cap_undeclared`): the
    note is added and Probable / Certain fall to Unsure ('recommend'); a worse band stands."""
    return (_fact_is(u, 'academic') and _degree_bound(u)
            and _adds_only(u, OWED_CODES, statuses=('recommend',)))


def _f1_q1(u):
    """F1 Q1: a short SPM read names what it missed. The SPM card only (Q2 / Q3 rule the higher card)."""
    return _fact_is(u, 'academic') and _spm_card(u) and _adds_only(u, F1_Q1_CODES)


def _f1_q4(u):
    """An STPM +/- difference on an AI read: red grade mismatch becomes amber grade uncertain."""
    red, amber = F1_Q4_PAIR
    return (_fact_is(u, 'academic') and _removed(u) == {red} and _added(u) == {amber}
            and _status_moves(u, ('review',), RED_TO_AMBER_FROM) and _evidence_only_lost(u) and _params_kept(u))


V =('verdict.build_verdict',)
CATALOGUE = (
    Ruling('R-TD465', 'decisions.md "TD-465 hotfix: an unknown STPM course-start year gives NO automatic '
           'amount - 2026-11-05"; b0bedd549', ('award.proposed_award_amount',), _td465_amount),
    Ruling('R-TD465-UNKNOWN', 'same, with decision 7 (2026-11-07): a degree-bound student under a stale stpm '
           'code is not sized as STPM, so the unknown-start stop lifts; 43a4b727a',
           ('award.course_start_unknown',), _td465_unknown),
    Ruling('R-DEG7-AWARD', 'decisions.md "A degree student gets a degree funding estimate; every skills / TVET '
           'course is estimated - 2026-11-07" (decision 7); 43a4b727a', ('award.proposed_award_amount',),
           _deg7_award),
    Ruling('R-DEG7-PATHWAY', 'same; a29381e5e', ('funding.classify_pathway',), _deg7_classify),
    Ruling('R-DEG7-ESTIMATE', 'same', ('funding.estimate_funding',), _deg7_estimate),
    Ruling('R-DEG7-SCHEDULE', 'same; 6c58efae5 (a stored STPM award keeps the STPM row)',
           ('payments.schedule_row', 'schedule.row_for', 'contracts.pick_schedule_row',
            'contracts.schedule_calendar'), _deg7_schedule),
    Ruling('R-56', 'decisions.md "Request #56 ..." - 2026-11-05; verdict 2026-11-05.1', V, _r56),
    Ruling('R-62', 'decisions.md "2026-11-06 - Request #62: a typed subject that is not on the slip ..."; '
           'verdict 2026-11-06.1, .4, .5', V, _r62),
    Ruling('R-388', 'decisions.md "2026-11-06 - Missing higher results cap Academic at Unsure ..."; '
           'verdict 2026-11-06.6', V, _r388),
    Ruling('R-OWED', 'decisions.md "2026-11-07 - Every degree student must have higher results on file; '
           'declare AND upload"; verdict 2026-11-07.1', V, _owed),
    Ruling('R-F1-Q1', 'decisions.md "2026-11-13 - F1 slip-check matrix: the owner\'s six rule changes, Q1-Q4, '
           'Q6, Q7"; verdict 2026-11-13.2, .3', V, _f1_q1),
    Ruling('R-F1-Q4', 'same (Q4)', V, _f1_q4),
    # Catalogued, NOT encoded (test None): the field shape must be seen on a real record first (R3).
    # R-67: its code `offer_letter_mismatch` exists only in services/blockers.py; the verdict emits
    # `offer_name_mismatch`, and widening the test to that would be too broad. Encode it in R3.
    Ruling('R-67', 'decisions.md "2026-11-13 - Request #67: an offer-letter name with a read slip AND extra '
           'name parts ..."; verdict 2026-11-13.1', V),
    Ruling('R-3ROUTES', 'decisions.md "2026-11-06 - Three exclusive routes for SPM grades"; 2026-11-06.2, .3',
           ('academic.student_slip_check', 'shortlist.evaluate', 'courses.check_eligibility')),
    Ruling('R-278', 'decisions.md "2026-11-07 - Undeclared higher results compare nothing; typo-tolerant STPM '
           'subject names"; verdict 2026-11-07.2', ('higher.student_higher_check', 'higher.match_verdict')),
    Ruling('R-F1-Q2', 'F1 Q2 (a short STPM read names its unchecked subjects)', ('higher.student_higher_check',)),
    Ruling('R-F1-Q3', 'F1 Q3 (an entered STPM subject not on a full exact read is red)',
           ('higher.student_higher_check',)),
    Ruling('R-F1-Q6', 'F1 Q6 (a higher result in the SPM slot holds no clean card back)', V),
)
#: Q7 (F1, verdict 2026-11-13.4) narrows the BEFORE-SUBMIT ask only: every replayed case is past draft, so
#: it has NO rule; a requirements difference on a replayed case is B.
#: R-54 (no code change, by design), R-IIUM and R-59 (reading changes) and R-A28B (no owner ruling) have
#: no rule: their differences are B.
PENDING = (
    ('TD-617', 'PISMP SPM route not owed higher results; ADP / MARA overseas preparation red flag: an owner '
               'money decision IN PROGRESS, not shipped. Its differences are B.'),
)
BY_ID = {r.id: r for r in CATALOGUE}


def units(engine, old, new):
    """The changed units of one record (old and new as the scrubbed records)."""
    old_r = old if isinstance(old, dict) else {'value': old}
    new_r = new if isinstance(new, dict) else {'value': new}
    if engine == 'verdict.build_verdict':
        of = {f.get('fact'): f for f in old_r.get('verdict') or ()}
        nf = {f.get('fact'): f for f in new_r.get('verdict') or ()}
        out = [Unit(engine, k, of.get(k), nf.get(k), old_r, new_r)
               for k in sorted(set(of) | set(nf), key=str) if of.get(k) != nf.get(k)]
        rest = {k for k in set(old_r) | set(new_r) if k not in ('verdict', 'facts') and old_r.get(k) != new_r.get(k)}
    else:
        out, rest = [], {k for k in set(old_r) | set(new_r) if k != 'facts' and old_r.get(k) != new_r.get(k)}
    out += [Unit(engine, k, old_r.get(k), new_r.get(k), old_r, new_r) for k in sorted(rest)]
    return out


#: An engine whose answer IS one of the case facts (`adapters.app_facts` calls the same function): that
#: fact moving with the answer is the unit itself, not a separate fact change.
ANSWER_FACT = {'award.course_start_unknown': 'start_unknown'}


def fact_changes(engine, old, new):
    """The case facts that differ between the sides (sorted). Facts are computed partly by engine code
    that is not itself replayed (`degree_bound`), so any change makes the record B (A5 R2 re-check)."""
    of = (old.get('facts') if isinstance(old, dict) else None) or {}
    nf = (new.get('facts') if isinstance(new, dict) else None) or {}
    echo = ANSWER_FACT.get(engine)
    out = []
    for k in sorted(set(of) | set(nf), key=str):
        if of.get(k) == nf.get(k):
            continue
        if (k == echo and isinstance(old, dict) and isinstance(new, dict)
                and of.get(k) == old.get('value') and nf.get(k) == new.get('value')):
            continue
        out.append(k)
    return out


def classify_difference(engine, old, new):
    """('expected', [ruling ids]) when every changed unit matches a ruling AND no case fact changed
    between the sides, else ('unexplained', [ids of the rulings that matched some unit])."""
    matched, all_ok = set(), not fact_changes(engine, old, new)
    for u in units(engine, old, new):
        hits = {r.id for r in CATALOGUE if r.matches(u)}
        matched |= hits
        all_ok = all_ok and bool(hits)
    return ('expected' if all_ok and matched else 'unexplained'), sorted(matched)
