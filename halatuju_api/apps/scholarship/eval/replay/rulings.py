"""The ruling catalogue (design 4.3) and the A / B split.

A difference is EXPECTED (class A) only when an owner ruling below matches it; anything else is
UNEXPLAINED (class B). A record's difference is cut into UNITS: for `verdict.build_verdict` one unit per
fact that changed; for every other engine one unit per top-level field that changed (`facts`, the case
facts, is never a unit). A record is A only when EVERY unit is matched by at least one ruling, and the
report names every ruling that matched (a unit two rulings match is listed under both).

Each test is NARROW: it reads the old and new value of ONE unit and non-personal case facts (`facts`:
pathway code, degree-bound, start year unknown, stored award, document type). There is no "any change
in X" rule. Too narrow is safe (the difference shows as B for the owner); too broad hides a regression.

Rulings catalogued but NOT encoded (their test is None) never match: their differences stay B until R3
has seen a real record's shape and the owner confirms. So does every PENDING item (not shipped).
No ruling exists for a "moves only" refactor (A3.1, A3.4, A3.6, A3.8, F1 step 2): a difference there is B
by definition.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from . import scrub

#: Every ruling id, so the report can name it (a literal: the registry takes nothing else).
scrub.register_codes((
    'R-TD465', 'R-TD465-UNKNOWN', 'R-DEG7-AWARD', 'R-DEG7-PATHWAY', 'R-DEG7-ESTIMATE', 'R-DEG7-SCHEDULE', 'R-56',
    'R-62', 'R-388', 'R-OWED', 'R-F1-Q1', 'R-F1-Q4', 'R-67', 'R-3ROUTES', 'R-278', 'R-F1-Q2', 'R-F1-Q3',
    'R-F1-Q6', 'TD-617', 'rulings', 'unit',
))

DEGREE_SCHEDULE_AWARDS = (None, '2000.00')
TVET_PATHWAYS = frozenset({'ilkbs', 'iljtm', 'kkom', 'mara_cert', 'tvet', 'mara_diploma'})


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
        """The NEW side's case facts (old as fallback): the rule's non-personal gates."""
        n = (self.new_record or {}).get('facts') or {}
        o = (self.old_record or {}).get('facts') or {}
        return {**o, **n}


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


def _status_moves(u, allowed):
    """The fact's status is unchanged, or moved to one of ``allowed``."""
    old, new = (u.old or {}).get('status'), (u.new or {}).get('status')
    return old == new or new in allowed


def _evidence_only_lost(u):
    return not _added(u, 'evidence')


def _adds_only(u, codes, *, statuses=('review',)):
    """The fact gained at least one of ``codes``, nothing else, lost nothing, and its status stayed or
    moved to one of ``statuses``. Present on both sides."""
    a = _added(u)
    return (bool(u.old) and bool(u.new) and bool(a) and a <= set(codes) and not _removed(u)
            and _status_moves(u, statuses) and _evidence_only_lost(u))


def _fact_is(u, *names):
    return u.engine == 'verdict.build_verdict' and u.field in names


# --- the tests ----------------------------------------------------------------------------------------

def _td465_amount(u):
    f = u.facts
    return (u.field == 'amount' and u.old == '3000.00' and u.new is None
            and f.get('start_unknown') is True and f.get('pathway_code') == 'stpm')


def _td465_unknown(u):
    return u.field == 'value' and u.old is False and u.new is True and u.facts.get('pathway_code') == 'stpm'


def _deg7_award(u):
    return (u.field == 'amount' and u.old in ('3000.00', '1000.00', None) and u.new == '2000.00'
            and u.facts.get('degree_bound') is True)


def _deg7_pathway_change(old, new, facts):
    if new == 'degree' and old != 'degree' and facts.get('degree_bound') is True:
        return True
    return old == 'unknown' and new in TVET_PATHWAYS


def _deg7_classify(u):
    return u.field == 'value' and _deg7_pathway_change(u.old, u.new, u.facts)


def _deg7_estimate(u):
    """Any estimate field, but ONLY when the same record's pathway moved as R-DEG7 rules."""
    old_p = (u.old_record or {}).get('pathway')
    new_p = (u.new_record or {}).get('pathway')
    return u.field in ('pathway', 'monthly', 'months', 'total', 'known', 'degree', 'practical', 'variable') \
        and _deg7_pathway_change(old_p, new_p, u.facts)


def _deg7_schedule(u):
    """A stale 'stpm' row becomes the university row for a degree-bound student whose stored award is
    empty or RM2,000 (a stored RM3,000 / RM1,000 keeps the STPM row, `6c58efae5`)."""
    old_p = (u.old_record or {}).get('pathway')
    new_p = (u.new_record or {}).get('pathway')
    f = u.facts
    return (old_p == 'stpm' and new_p == 'university' and f.get('degree_bound') is True
            and f.get('stored_award') in DEGREE_SCHEDULE_AWARDS)


def _r56(u):
    """A results / IC name one look-alike letter off: the red name item becomes amber."""
    return (_fact_is(u, 'identity', 'academic')
            and _removed(u) & {'name_mismatch', 'higher_results_name_mismatch'}
            and _added(u) <= {'name_near', 'higher_results_name_near'}
            and _status_moves(u, ('review',)) and _evidence_only_lost(u))


def _r62(u):
    return _fact_is(u, 'academic') and _adds_only(u, {'academic_extra_subjects', 'academic_grades_unchecked'},
                                                  statuses=('review', 'gap'))


def _r388(u):
    return _fact_is(u, 'academic') and _adds_only(u, {'higher_results_not_on_file'})


def _owed(u):
    return (_fact_is(u, 'academic') and u.facts.get('degree_bound') is True
            and _adds_only(u, {'higher_results_not_declared', 'higher_results_undeclared'}))


def _f1_q1(u):
    return _fact_is(u, 'academic') and _adds_only(u, {'academic_slip_rows_unread', 'academic_grades_unchecked'})


def _f1_q4(u):
    """An STPM +/- difference on an AI read: red grade mismatch becomes amber grade uncertain."""
    return (_fact_is(u, 'academic') and _removed(u) == {'higher_results_grade_mismatch'}
            and _added(u) == {'higher_results_grade_uncertain'} and _status_moves(u, ('review',))
            and _evidence_only_lost(u))


def _r67(u):
    """Request #67: an offer-letter name with a read slip AND extra name parts is no longer a block."""
    return (_fact_is(u, 'pathway') and _removed(u) == {'offer_letter_mismatch'} and not _added(u)
            and _status_moves(u, ('review', 'verified')) and _evidence_only_lost(u))


V = ('verdict.build_verdict',)
CATALOGUE = (
    Ruling('R-TD465', 'decisions.md "TD-465 hotfix: an unknown STPM course-start year gives NO automatic '
           'amount - 2026-11-05"; b0bedd549', ('award.proposed_award_amount',), _td465_amount),
    Ruling('R-TD465-UNKNOWN', 'same; roadmap A1.13 (one course-start read point)',
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
    Ruling('R-67', 'decisions.md "2026-11-13 - Request #67: an offer-letter name with a read slip AND extra '
           'name parts ..."; verdict 2026-11-13.1', V, _r67),
    # Catalogued, NOT encoded (test None): the field shape must be seen on a real record first (R3).
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


def classify_difference(engine, old, new):
    """('expected', [ruling ids]) when every changed unit matches a ruling, else ('unexplained', [ids of
    the rulings that matched some unit])."""
    matched, all_ok = set(), True
    for u in units(engine, old, new):
        hits = {r.id for r in CATALOGUE if r.matches(u)}
        matched |= hits
        all_ok = all_ok and bool(hits)
    return ('expected' if all_ok and matched else 'unexplained'), sorted(matched)
