"""The IC lock — one rule, one home (2026-07-29).

**Why this module exists.** Whether a student's IC number is settled has to be answered in
three places at once: the profile screen (draw a padlock or an editable box), the write path
(refuse a change), and the moment the lock is first taken. Three copies of "is it confirmed?"
would drift — that is the standing lesson from the income gate, where "what counts as
evidence" lived in an assessment path and a submission path and the two disagreed for months.
So the rule lives here, is named, and every caller asks it.

**The rule** (owner, 2026-07-29): a student's IC number locks when their uploaded MyKad is
GENUINE, the number on it matches what they typed, and the name matches too. All three, and
only then. Until that moment they may correct it themselves.

Three deliberate choices inside that sentence, each easy to get wrong:

* **An unscored card is NOT genuine.** Elsewhere in this codebase an absent genuineness verdict
  fails OPEN (``income_engine`` treats an empty status as passing), and that is right for a soft
  signal an officer can overrule. This is not that: the lock is one-way, so "we could not check
  the card" must mean "not confirmed", never "confirmed". Same shape as the Layer 0 rule that an
  empty catalogue means NOT CONFIGURED rather than "requires nothing".
* **The name may differ by whole parts, never by spelling.** A missing middle name is the same
  person (``name_match`` → ``partial``); a one-letter difference might not be (→ ``mismatch``).
  There IS a tolerant matcher in this codebase — ``relationship_name_match``, which folds w↔v,
  doubled letters and a trailing h — built for cross-checking income documents. **Do not reach
  for it here.** It is deliberately kept off identity, on the reasoning that a lenient matcher
  can only ever weaken an identity check.
* **The number is exact.** ``nric_close`` (a single-digit edit) exists and is used to WORD the
  student's nudge more precisely. It must never widen the lock — its own docstring says so.

**The lock is STORED, never re-derived.** ``locks_now()`` answers "should it lock?", and the
caller writes ``nric_verified``. Recomputing it on every read would make the lock reversible by
deleting the evidence: upload a matching card, lock; delete the card, unlock; change the number.
A lock you can undo by removing the proof is not a lock.
"""
from .genuineness.bands import canonical_status
from .vision import name_match, nric_close, nric_match

# The name comparisons that mean "the same person". ``partial`` is one set being a strict
# subset of the other — a name typed shorter or longer than the card carries.
_SAME_PERSON = frozenset({'match', 'partial'})


def _authenticity_status(doc):
    """The stored genuineness verdict for a document, or '' when it was never scored."""
    fields = getattr(doc, 'vision_fields', None) or {}
    return ((fields.get('authenticity') or {}).get('status') or '').strip()


def card_is_genuine(doc):
    """True only on a POSITIVE genuineness verdict.

    Folded through ``genuineness.bands.canonical_status`` rather than compared to a string: the
    IC scorer emits ``likely_genuine`` as well as ``genuine`` (32 and 34 of production's live
    cards respectively), and a bare ``== 'genuine'`` would silently exclude a third of them.
    The fold also maps the legacy words (``low_confidence``, ``wrong_type``, ``not_an_ic``), and
    returns ``''`` for a card that was never scored — which is NOT genuine, per the module note.
    """
    return canonical_status(_authenticity_status(doc), 'ic') == 'genuine'


def compare(doc, profile):
    """How the uploaded MyKad reads against what the student typed.

    Returns ``{'name': …, 'nric': …, 'genuine': bool, 'card_name': str, 'card_nric': str}``
    where each comparison is ``match`` / ``partial`` / ``mismatch`` / ``unknown`` (nothing to
    compare). ``nric`` additionally reports ``near`` — a single-digit difference — which exists
    ONLY so the student's nudge can say "differs by one digit" instead of something vague. It is
    not a softer kind of match and must never reach the lock decision.

    This is the one place the two sides are compared, so the padlock, the flag and the lock can
    never disagree about what the card says.
    """
    card_name = (getattr(doc, 'vision_name', '') or '').strip() if doc else ''
    card_nric = (getattr(doc, 'vision_nric', '') or '').strip() if doc else ''
    typed_name = (getattr(profile, 'name', '') or '').strip() if profile else ''
    typed_nric = (getattr(profile, 'nric', '') or '').strip() if profile else ''

    if card_name and typed_name:
        name = name_match(card_name, typed_name)
    else:
        name = 'unknown'

    if card_nric and typed_nric:
        if nric_match(card_nric, typed_nric):
            nric = 'match'
        elif nric_close(card_nric, typed_nric):
            nric = 'near'
        else:
            nric = 'mismatch'
    else:
        nric = 'unknown'

    return {
        'name': name,
        'nric': nric,
        'genuine': bool(doc) and card_is_genuine(doc),
        'card_name': card_name,
        'card_nric': card_nric,
    }


def locks_now(comparison):
    """Should the IC lock, given ``compare()``'s answer? Genuine card, exact number, same person.

    Deliberately takes the comparison rather than the document, so the decision and the thing
    shown to the student are provably the same reading.
    """
    return (comparison['genuine']
            and comparison['nric'] == 'match'
            and comparison['name'] in _SAME_PERSON)


def flags(comparison):
    """What to tell the student, as codes the screen turns into copy.

    Anything the card and the typed value disagree about, whether or not it blocked the lock —
    including a ``partial`` name on a record that DID lock, because aligning it is still worth
    doing and nothing else will ever ask them to.

    ``unknown`` is never flagged: no card, or nothing read off it, is not a disagreement.
    """
    out = []
    if comparison['nric'] == 'near':
        out.append('nric_one_digit')
    elif comparison['nric'] == 'mismatch':
        out.append('nric_differs')
    if comparison['name'] == 'partial':
        out.append('name_incomplete')
    elif comparison['name'] == 'mismatch':
        out.append('name_differs')
    return out
