"""Case 1048 (owner 2026-11-27): a HANDWRITTEN income declaration in the salary-slip slot.

A "Surat Akuan Pengesahan Pendapatan" is filled in by hand and uploaded where a payslip goes. Two
things went wrong on it, and this module holds the fix for both.

**1. A near-miss name is 'close', not red.** The AI misreads a handwritten name by a letter or two
(and often reads the "A/L" as a short stray word such as "ALE"), so the earner's own form failed the
tolerant matcher (`vision._tokens_close`: five letters or more, one edit) and the Name chip went red
as if the form named a stranger. The owner ruled:

* a near miss on a declaration SHOWS its own word, ``CLOSE`` (amber: a person must look);
* review round 1 (owner rule): 'close' must NEVER count as clean or ok anywhere. So it is a DISPLAY word
  only. ``soften`` is called by `link_display.income_proof_display` alone, on ``display_name_status``.
  The decision field ``student_income_proof_check()['name_status']`` stays 'mismatch', so every gate,
  resolution, promotion, income-satisfaction, verdict band, route switch, coach and blocker treats the
  form exactly as before (``for_decisions`` is the mapping for any future caller that holds a shown
  word). The stored student verdict is not changed either: it stays 'name_mismatch';
* the matcher is NOT loosened anywhere else. A typed or printed payslip one letter off still says
  'mismatch'. The change is scoped to a salary-slip-slot document the read saw as a declaration
  (``income_declaration.is_declaration``: ``doc_seen == 'declaration'``), which is our only proxy for
  "handwritten" — no stored handwriting flag exists.

The near miss is deliberately narrow. First the patronymic connectors drop out on BOTH sides (A/L,
A/P, S/O, D/O, BIN, BINTI, BT as `vision._canonical_name_seq` already drops them, plus BN). Then:

* **same number of parts** (two or more): every part agrees under the tolerant matcher but at most ONE,
  and that odd pair is at least ``MIN_PART_LETTERS`` long on both sides, shares its first letter and is
  at most ``MAX_EDITS`` apart (no odd pair at all — an exact match once the connectors are gone — is a
  near miss too);
* **one part more on one side**: that extra part is the ONLY inner part (never the first or the last
  word) of at most ``MAX_EXTRA_LETTERS`` letters that is within one edit of a connector (ALE, AIL, NL
  for A/L). It drops, and the rest must agree IN PRINTED ORDER, with at most one odd pair as above.
  Two extra parts, or an extra part that is not connector-like, are never close.

A reversed patronymic (a father and a son) is never close. A different given name is still 'mismatch'.

**2. The payslip-only warnings do not show on a declaration.** The read's free-text ``warnings`` (the
AI's notes, stored at read time and shown to the officer) say "no employer" and "no pay period" on
almost every declaration — a declaration has neither, by design. ``shown_warnings`` hides exactly those
two kinds at DISPLAY time (the serializer); the stored read is never edited, and no warning feeds a
verdict, a blocker or the money.

It sits in ``income_engine/`` so the verdict-engine fingerprint covers it: BUMP
``verdict_engine.VERDICT_ENGINE_VERSION`` on any change to the rule.
"""
from __future__ import annotations

#: The SHOWN status word (``display_name_status`` only). Never a decision value.
CLOSE = 'close'


def for_decisions(status: str) -> str:
    """The decision value of a name status: 'close' is 'mismatch' for every gate and decision (owner
    rule, review round 1). Every other status is returned unchanged."""
    return 'mismatch' if status == CLOSE else status

MIN_PART_LETTERS = 4
MAX_EDITS = 2

#: The connector forms an extra short part may be one edit from (A/L and A/P lose their slash).
CONNECTORS = ('al', 'ap', 'so', 'do', 'bin', 'binti', 'bt', 'bn')
#: `_canonical_name_seq` keeps BN (it is not in `vision._NAME_NOISE`); it is a connector here.
_ALSO_DROPPED = frozenset({'bn'})
MAX_EXTRA_LETTERS = 3


def _parts(name: str) -> list:
    from ..vision import _canonical_name_seq
    return [t for t in _canonical_name_seq(name or '') if t not in _ALSO_DROPPED]


def _one_part_off(x: str, y: str) -> bool:
    from ..vision import _fold_name_token, _levenshtein
    x, y = _fold_name_token(x), _fold_name_token(y)
    return min(len(x), len(y)) >= MIN_PART_LETTERS and x[:1] == y[:1] and _levenshtein(x, y) <= MAX_EDITS


def _same_count(a: list, b: list) -> bool:
    """The rule for two names of the same number of parts (matched in any order, as before)."""
    from ..vision import _tokens_close
    if len(a) < 2:
        return False
    rest, odd = list(b), []
    for x in a:
        hit = next((i for i, y in enumerate(rest) if _tokens_close(x, y)), None)
        if hit is None:
            odd.append(x)
        else:
            rest.pop(hit)
    if not odd:
        return True                                   # exact once the connectors are gone
    return len(odd) == 1 and len(rest) == 1 and _one_part_off(odd[0], rest[0])


def _connector_like(tok: str) -> bool:
    from ..vision import _levenshtein
    return len(tok) <= MAX_EXTRA_LETTERS and any(_levenshtein(tok, c) <= 1 for c in CONNECTORS)


def _without_misread_connector(longer: list):
    """``longer`` without its ONE connector-like inner part, or None when there is not exactly one."""
    hits = [i for i in range(1, len(longer) - 1) if _connector_like(longer[i])]
    return longer[:hits[0]] + longer[hits[0] + 1:] if len(hits) == 1 else None


def _in_order(a: list, b: list) -> bool:
    """Part by part in printed order: all agree, or exactly one odd pair within the near-miss limits."""
    from ..vision import _tokens_close
    if len(a) != len(b) or len(a) < 2:
        return False
    odd = [(x, y) for x, y in zip(a, b) if not _tokens_close(x, y)]
    return not odd or (len(odd) == 1 and _one_part_off(*odd[0]))


def near_miss(extracted, reference) -> bool:
    """True when the two names differ only by a small misread (the rule above)."""
    from .buckets import _near_miss_reversal
    a, b = _parts(extracted), _parts(reference)
    if _near_miss_reversal(extracted, reference):
        return False
    if len(a) == len(b):
        return _same_count(a, b)
    if abs(len(a) - len(b)) != 1:
        return False
    if len(a) > len(b):
        a = _without_misread_connector(a)
    else:
        b = _without_misread_connector(b)
    return a is not None and b is not None and _in_order(a, b)


def soften(doc, status: str, extracted: str, reference: str) -> str:
    """The SHOWN name status: ``CLOSE`` in place of 'mismatch' for a near-miss name on a declaration in
    the salary-slip slot; every other status, document type or name is returned unchanged. DISPLAY
    ONLY (`link_display.income_proof_display`): never call it on a decision field."""
    if status != 'mismatch' or getattr(doc, 'doc_type', '') != 'salary_slip':
        return status
    if not near_miss(extracted, reference):
        return status
    from ..income_declaration import is_declaration
    return CLOSE if is_declaration(doc) else status


# ── 2. The payslip-only warnings ─────────────────────────────────────────────────────────────────
#: A warning ABOUT the employer or the pay period (the AI's own words vary, so these are the topics).
_EMPLOYER_WORDS = ('employer', 'majikan', 'company', 'syarikat')
_PERIOD_WORDS = ('period', 'pay month', 'salary month', 'month of pay', 'pay date', 'tempoh',
                 'bulan gaji', 'month/year', 'month and year')
#: ...that ALSO speaks of identity or approval is kept whole: those are substantive on a declaration.
_KEEP_WORDS = ('name', 'nric', 'kad pengenalan', 'mykad', 'ic number', 'ic no', 'identity',
               'signature', 'signed', 'sign ', 'stamp', 'tandatangan', 'approv', 'cop rasmi')
#: "the employer's NAME" is still about the employer, not about who the earner is.
_EMPLOYER_NAME_PHRASES = ("employer's name", 'employer name', 'name of the employer', 'name of employer',
                          "company's name", 'company name', 'name of the company', 'name of company',
                          'nama majikan', 'nama syarikat')


def payslip_only_warning(warning) -> bool:
    """True for a warning about the employer or the pay period alone (nothing about who or approval)."""
    s = str(warning or '').lower()
    if not any(k in s for k in _EMPLOYER_WORDS + _PERIOD_WORDS):
        return False
    for phrase in _EMPLOYER_NAME_PHRASES:
        s = s.replace(phrase, 'employer')
    return not any(k in s for k in _KEEP_WORDS)


def shown_warnings(doc, warnings):
    """The warnings to SHOW for ``doc``: a declaration in the salary-slip slot loses its payslip-only
    ones; any other document gets ``warnings`` back unchanged (the same object). Display only."""
    if getattr(doc, 'doc_type', '') != 'salary_slip' or not isinstance(warnings, list) or not warnings:
        return warnings
    from ..income_declaration import is_declaration
    if not is_declaration(doc):
        return warnings
    return [w for w in warnings if not payslip_only_warning(w)]
