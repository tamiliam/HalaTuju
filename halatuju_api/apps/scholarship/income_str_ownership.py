"""TD-262 F8 — *only the family's own STR counts* at the SUBMISSION gate.

**The ruling** (owner, 2026-09-19, ``docs/decisions.md``): *"only the family's own STR count."*
An STR document clears the income requirement only when its recipient is a parent or guardian of
the applicant. Somebody else's STR is evidence about somebody else's household.

**What the gate did before.** ``income_engine.str_not_breached`` answers *has this household's
STR FAILED?* — approved-ish and not judged non-genuine — and never *whose STR is this?*. It is
the fourth arm of ``member_income_evidenced``, so an unrelated person's screenshot satisfied the
submission gate while the verdict's ``household_str_status`` correctly refused it. Two bars, one
function apart (code health H8, finding F8).

**Why the test lives HERE and not inside ``str_not_breached``.** That predicate feeds
``member_income_evidenced`` → ``member_cluster_complete`` → ``salary_income_satisfied``, which
``verdict_engine._verdict_income`` reads at str-proof-spec §6 rule 2 — so tightening it would
move a verdict BAND as well as the gate. F8 is a ruling about the GATE, and the officer cockpit's
``strNotBreached`` mirror (``halatuju-web/src/lib/officerCockpit.ts``) reproduces the un-tightened
predicate, so leaving it alone keeps that mirror honest too. The ownership test is therefore
applied where the gate asks its question: ``services.income_doc_blockers``.

**⚠ TWO RULES BOUND THIS MODULE.**

1. **Absence is not a mismatch.** An STR nothing could be read off, or one uploaded before any
   household IC is on file, yields ``no_ref`` — not ``mismatch``. We block on a POSITIVE
   mismatch only. A family is never refused for a gap in OUR reading of their document; the
   unread STR keeps clearing the gate exactly as it did, and a human settles it at review.
2. **Matching is exhausted first** (owner, ``feedback_str_precedence``). Name OR NRIC,
   independently, against EVERY parent/guardian whose IC is on file — that work is already done
   inside ``income_engine._str_recipient_household_match``, and this module only reads its verdict
   so a second, different matching rule can never appear.

And one more, which is why ``stranger_str_blocks_submission`` is not simply the negation of (1):
a useless STR beside a REAL income proof is beside the point. The block fires only when nothing
else in the household shows what it earns (``income_shown`` — the per-earner answer, which has no
STR arm), so the tightening can never newly block a family that documented an earner properly.
"""

#: The blocker code the gate emits. Rendered to the student as
#: ``scholarship.consent.blocker.str_not_household`` and to the officer as
#: ``admin.scholarship.blockers.item.str_not_household`` (en / ms / ta).
STR_NOT_HOUSEHOLD = 'str_not_household'


#: A parent the application records in one of these states is not in the household an STR could
#: be paid to, so no IC is expected of them (the roster's own vocabulary, ``family.PROFESSION``).
_NOT_IN_HOUSEHOLD = frozenset({'deceased', 'no_contact'})


def str_roster(application) -> list:
    """THE ROSTER — the household members an STR recipient must be judged against before it may be
    called somebody else's (owner's F1 ruling, 2026-09-29: *"we cannot judge" is NOT "stranger"*).

    Exactly these, in ``_MEMBER_ORDER``, all read off fields the application already holds (no
    query):
      * **the father and the mother**, whenever the application records one (a name or an
        occupation) who is not recorded as ``deceased`` or ``no_contact`` — an STR is a household
        benefit that can be paid to either spouse (owner 2026-07-07), so both are candidates
        whether or not they work;
      * **a guardian**, when the roster lists one on the same terms — the third person the F8
        rule itself names ("a parent or guardian of the applicant");
      * **the STR route's declared earner** and **every ticked working member** — the people the
        student has TOLD us carry the household's income, siblings included.
    A sibling who is neither the earner nor a working member is NOT on the roster: the STR model is
    a head-of-household benefit, and demanding every sibling's IC before we could ever call an STR
    somebody else's would switch the ownership rule off for most families."""
    from .income_engine.relationships import _MEMBER_ORDER, working_members
    roster = set(working_members(application))
    earner = (getattr(application, 'income_earner', '') or '').strip()
    if earner in _MEMBER_ORDER:
        roster.add(earner)
    for parent in ('father', 'mother'):
        occ = (getattr(application, f'{parent}_occupation', '') or '').strip()
        named = (getattr(application, f'{parent}_name', '') or '').strip()
        if (occ or named) and occ not in _NOT_IN_HOUSEHOLD:
            roster.add(parent)
    for person in (getattr(application, 'other_family_members', None) or []):
        if (isinstance(person, dict) and person.get('role') == 'guardian'
                and (person.get('occupation') or '') not in _NOT_IN_HOUSEHOLD):
            roster.add('guardian')
    return [m for m in _MEMBER_ORDER if m in roster]


def _positive_mismatch(sc) -> bool:
    """F8's field rule, unchanged: a match on name OR NRIC is the family's own; otherwise a
    positive ``'mismatch'`` on either field. ``'no_ref'`` on both is neither (rule 1)."""
    if not sc:
        return False
    if sc['name_status'] == 'match' or sc['nric_status'] == 'match':
        return False                                  # the family's own — matching succeeded
    return 'mismatch' in (sc['name_status'], sc['nric_status'])


def str_unjudged_members(application, sc) -> list:
    """The roster members the recipient could NOT be compared against — ``[]`` when judgement is
    possible. Read off the ``student_str_check`` reading in hand (its per-field
    ``ic_read_members``), so it costs no query.

    ⚠ "READ" IS PER FIELD (review F-A). A member counts as compared on NAME only if their IC's name
    read, and on NRIC only if their IC's NRIC read. Judgement is possible when, on at least one
    field the STR actually OFFERS, the recipient mismatched and EVERY roster member was compared
    on that field. Otherwise the answer is every roster member missing from an offered field — an
    IC that read only her NRIC is no comparison at all against an STR that shows only her name."""
    if not sc:
        return []
    read = sc.get('ic_read_members') or {}
    roster = str_roster(application)
    gaps = set()
    for field in ('name', 'nric'):
        if not (sc.get(field) or '').strip():
            continue                                  # the STR does not offer this field
        missing = {m for m in roster if m not in (read.get(field) or ())}
        if not missing and sc.get(f'{field}_status') == 'mismatch':
            return []                                 # a complete comparison, and no match
        gaps |= missing
    return [m for m in roster if m in gaps]


def str_check_names_a_stranger(sc, application) -> bool:
    """The ownership rule itself, applied to a ``student_str_check`` reading already in hand.

    A stranger's STR is a POSITIVE mismatch (F8's field rule, ``_positive_mismatch``) that is
    COMPLETE on at least one field the STR offers: every member of ``str_roster`` was compared on
    that field (``str_unjudged_members``, per FIELD — review F-A). Otherwise **we cannot judge** —
    the answer is not "stranger", the STR counts, and the IC that would settle it is asked for
    (``str_owner_ic_asks``) and offered on the Documents page (``str_ic_slots``, TD-309). Owner's
    F1 ruling, 2026-09-29.

    ⚠ ONE RULE, TWO READERS, AND IT IS SPLIT OUT SO IT STAYS ONE (TD-285). ``str_recipient_is_
    stranger`` asks it of the live STR for the submission gate, and ``income_engine.has_valid_str``
    asks it of the reading it has ALREADY taken. Neither may re-read the household ICs: the
    comparison set travels on the reading, and the roster is read off the application's own
    fields — the query budgets say so."""
    return _positive_mismatch(sc) and not str_unjudged_members(application, sc)


def _latest_str_check(application):
    from . import income_engine as ie
    from .document_snapshot import latest_doc
    if getattr(application, 'documents', None) is None:
        return None
    str_doc = latest_doc(application, 'str')
    return ie.student_str_check(str_doc) if str_doc is not None else None


def str_recipient_is_stranger(application) -> bool:
    """True when the household's live STR is PROVABLY in someone else's name — a positive mismatch
    against every roster member's IC (``str_check_names_a_stranger``)."""
    return str_check_names_a_stranger(_latest_str_check(application), application)


def str_ic_slots(sc, application) -> dict:
    """The ICs that would settle whose STR this is, read off a ``student_str_check`` reading
    ALREADY IN HAND: ``{'missing': [...], 'unreadable': [...]}``. A member whose IC is not on file
    is ``missing``; one whose IC IS on file but did not read the field needed is ``unreadable``
    (review F-C — never tell a student an IC they uploaded is "not on file"). Both empty for no
    reading, the family's own STR, an unread STR, and a true stranger's. PURE — no query.

    ⚠ ONE RULE, TWO READERS (TD-309). Check 2 ASKS for these ICs after submission
    (``str_owner_ic_asks``); the Documents page OFFERS a card for each of them before it
    (``student_str_payload`` → the served ``str_check.ic_slots``). A demand and an offer that read
    the same fact must be one reading, or the student is chased for a document the page will not
    take (docs/lessons.md, TD-262 F2) — so both call this, and neither holds a copy."""
    members = str_unjudged_members(application, sc) if _positive_mismatch(sc) else []
    on_file = set(((sc or {}).get('ic_read_members') or {}).get('on_file') or ())
    return {'missing': [m for m in members if m not in on_file],
            'unreadable': [m for m in members if m in on_file]}


def str_owner_ic_asks(application) -> dict:
    """The ICs to ASK for, AFTER submission (Check 2), because the STR cannot be judged without
    them — ``str_ic_slots`` of the household's live STR, the same rule the Documents page offers
    from (TD-309).

    ⚠ IT RE-READS THE STR on every call (TD-308): `check2_queries._gap_sets` has no STR reading in
    hand, and threading one through the oversize-ledgered `check2_queries.py` is its own change."""
    return str_ic_slots(_latest_str_check(application), application)


def student_str_payload(doc):
    """The STR document's ``str_check`` as the STUDENT is served it: the ``student_str_check``
    reading with the server-only ``ic_read_members`` stripped and ``ic_slots`` (``str_ic_slots``)
    added — the members whose IC the income wizard offers a tagged card for (TD-309). None for a
    non-STR doc. No query beyond the reading's own: ``str_ic_slots`` reads only the reading and the
    application's fields, which the reading has already loaded."""
    from . import income_engine as ie
    sc = ie.student_str_check(doc)
    if sc is None:
        return None
    out = {k: v for k, v in sc.items() if k != 'ic_read_members'}
    out['ic_slots'] = str_ic_slots(sc, doc.application)
    return out


def stranger_str_blocks_submission(application) -> bool:
    """True when a TRUE stranger's STR is the ONLY thing standing in for this household's income —
    the exact case F8 stops at the submission gate.

    ⚠ A STR WE CANNOT JUDGE DOES NOT BLOCK (the lead's reading of the owner's F1 ruling, review
    F-B/F-D, 2026-09-29). It counts; its missing IC is asked after submission, through Check 2,
    because before submission the Documents page offers a mother's IC slot only when she is a
    working member or the earner — asking there would be a dead end (TD-309). So this fires on
    a SUBSET of the households the pre-ruling gate blocked: nobody is newly blocked.

    False the moment any working member's income is SHOWN on its own (a usable payslip, a
    readable EPF, or a declared amount backed by a letter that read): the household has answered
    the income question, and a useless extra document must not newly block it. Earners are
    resolved ``any_route=True`` for the usual reason — a student who declared the STR route never
    ticks a salary checkbox, yet may well have tagged her father's payslip."""
    from . import income_engine as ie
    from .income_shown import income_shown
    if not str_recipient_is_stranger(application):
        return False
    return not any(income_shown(application, m).shown
                   for m in ie.effective_working_members(application, any_route=True))
