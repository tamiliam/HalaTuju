"""Case 1048 (owner 2026-11-27): a near-miss name on a HANDWRITTEN income declaration is 'close', not red.

A "Surat Akuan Pengesahan Pendapatan" is filled in by hand. The AI misreads a handwritten name by a
letter or two, so the earner's own form failed the tolerant matcher (`vision._tokens_close`: five
letters or more, one edit) and the Name chip went red as if the form named a stranger. The owner ruled:

* a near miss on a declaration gets its own word, ``CLOSE``. Its LOGIC is the same as 'unreadable' — a
  person must look — and never 'mismatch' (no red, no "wrong person" coach) and never 'match' (it does
  not link the earner, credit the evidence or clear a gate);
* the matcher is NOT loosened anywhere else. A typed or printed payslip one letter off still says
  'mismatch'. The change is scoped to a salary-slip-slot document the read saw as a declaration
  (``income_declaration.is_declaration``: ``doc_seen == 'declaration'``), which is our only proxy for
  "handwritten" — no stored handwriting flag exists.

The near miss is deliberately narrow: the same number of name parts (two or more), every part agreeing
under the tolerant matcher but ONE, and that odd pair at least ``MIN_PART_LETTERS`` long on both sides,
sharing its first letter and at most ``MAX_EDITS`` apart. A reversed patronymic (a father and a son) is
never close. A different given name is still 'mismatch'.

It sits in ``income_engine/`` so the verdict-engine fingerprint covers it: BUMP
``verdict_engine.VERDICT_ENGINE_VERSION`` on any change to the rule.
"""
from __future__ import annotations

#: The status word. Consumers compare name_status with 'match' / 'mismatch' only, so this word falls
#: through exactly like 'no_ref' / 'unreadable' everywhere (see the consumer tests).
CLOSE = 'close'

MIN_PART_LETTERS = 4
MAX_EDITS = 2


def near_miss(extracted: str, reference: str) -> bool:
    """True when the two names differ only by a small misread in ONE part (the rule above)."""
    from .buckets import _near_miss_reversal
    from ..vision import _canonical_name_seq, _fold_name_token, _levenshtein, _tokens_close
    a, b = _canonical_name_seq(extracted or ''), _canonical_name_seq(reference or '')
    if len(a) != len(b) or len(a) < 2 or _near_miss_reversal(extracted, reference):
        return False
    rest, odd = list(b), []
    for x in a:
        hit = next((i for i, y in enumerate(rest) if _tokens_close(x, y)), None)
        if hit is None:
            odd.append(x)
        else:
            rest.pop(hit)
    if len(odd) != 1 or len(rest) != 1:
        return False
    x, y = _fold_name_token(odd[0]), _fold_name_token(rest[0])
    return (min(len(x), len(y)) >= MIN_PART_LETTERS and x[:1] == y[:1]
            and _levenshtein(x, y) <= MAX_EDITS)


def soften(doc, status: str, extracted: str, reference: str) -> str:
    """``CLOSE`` in place of 'mismatch' for a near-miss name on a declaration in the salary-slip slot;
    every other status, document type or name is returned unchanged."""
    if status != 'mismatch' or getattr(doc, 'doc_type', '') != 'salary_slip':
        return status
    if not near_miss(extracted, reference):
        return status
    from ..income_declaration import is_declaration
    return CLOSE if is_declaration(doc) else status
