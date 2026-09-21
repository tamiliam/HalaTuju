"""The SALARY route's half of the income verdict (``verdict_engine._verdict_income``).

⚠ WHY THIS IS A MODULE AND NOT FOUR MORE FUNCTIONS IN ``verdict_engine``. The salary route read
the documents, aggregated the findings and placed the band in ONE 198-line run, so there was no
seam at which to ask a second question about the same household — which is how TD-262's rule-4
gap sat unnoticed in ``_verdict_income``: a stale / unreadable / recipient-mismatched STR returned
before the payslips on file were ever assessed. Splitting that run needed somewhere to put the
pieces, and ``verdict_engine.py`` is on the oversize ledger (`code-standards.json`), so they live
here — the same reason ``income_shown.py`` is its own module rather than more of ``income_engine``.

⚠ THE SPLIT WAS A PURE MOVE. Every line below is the line that was in ``_verdict_income_salary``,
in the same order, with the loop's shared state passed explicitly instead of closed over. No
band moved; the characterisation suites (`test_income_evidence_homes.py`, `test_income_shown.py`)
passed unedited across it, and that is what says it was a move.

The STR route stays in ``verdict_engine`` beside the rest of the four-fact engine: this module is
the route it falls through TO, never a second home for the income rule itself.
"""
from __future__ import annotations

from .verdict_engine import (_fact, _income_open_item, _item, _latest_doc_for_member,
                             _usable_relationship_fields, _utility_context)


def _salary_relationship_docs(application):
    """The two SINGLE household relationship documents, read once for the whole household: the
    birth certificate's child / mother / father names and the guardianship letter's name.

    A WRONG-TYPE doc in either slot is UNUSABLE (#27) — its fields are blanked so no relationship
    can read off it — and the two ``*_unusable`` REASON strings ('' / 'wrong_type' / 'unreadable')
    travel with the reading so the caller can ask for the re-upload in the words that fit (#23)."""
    _, bcf, bc_unusable = _usable_relationship_fields(application, 'birth_certificate')
    g_doc, _, letter_unusable = _usable_relationship_fields(application, 'guardianship_letter')
    return {
        'bc_child': bcf.get('bc_child_name', ''),
        'bc_mother': bcf.get('bc_mother_name', ''),
        'bc_father': bcf.get('bc_father_name', ''),      # #55: mononym father fallback
        'bc_unusable': bc_unusable,
        'letter_name': ('' if letter_unusable
                        else ((getattr(g_doc, 'vision_name', '') or '') if g_doc else '')),
        'letter_unusable': letter_unusable,
    }


def _salary_member_scan(application, members, student_name, present, rel_docs):
    """Read every working member's cluster — their IC, their relationship to the student, and
    whether their income is SHOWN — and return ``(evidence, found)``.

    ``found`` carries the per-member gaps BY KIND rather than as finished items, because the
    resolution layer keys tickets by code (one per code per application): emitting the same code
    twice would collide, so ``_salary_unresolved`` aggregates each kind into ONE item that lists
    everyone."""
    from .income_engine import (member_relationship_status, relationship_doc_for,
                                chain_verified_earner, earner_monthly_income)
    from .income_shown import income_shown
    evidence = []
    found = {
        'any_financial': False,   # ≥1 member supplied a payslip/EPF (or an ACCEPTED declared income)
        'all_confirmed': True,    # every member's relationship is a positive 'match'
        'declared_backed': [], 'declared_unproven': [],   # Phase 2A: carried by a declared amount
        'ic_missing': [], 'ic_unreadable': [], 'patronymic_mismatch': [],
        'bc_missing': False, 'bc_mismatch': False, 'letter_missing': False,
    }
    for m in members:
        ic_doc = _latest_doc_for_member(application, 'parent_ic', m)
        ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
        if ic_doc is None:
            found['ic_missing'].append(m)
            found['all_confirmed'] = False
        elif not ic_name:
            found['ic_unreadable'].append(m)
            found['all_confirmed'] = False
        else:
            evidence.append(_item('earner_ic_present', member=m, name=ic_name))

        # Relationship proof document (mother → BC, guardian → letter; single docs).
        rel_doc = relationship_doc_for(m)
        if rel_doc == 'birth_certificate' and 'birth_certificate' not in present:
            found['bc_missing'] = True
            found['all_confirmed'] = False
        elif rel_doc == 'guardianship_letter' and 'guardianship_letter' not in present:
            found['letter_missing'] = True
            found['all_confirmed'] = False

        # Relationship verdict (father/brother/sister share the patronymic; father also has
        # the #55 BC fallback for a mononym student).
        rel = member_relationship_status(m, student_name, ic_name, rel_docs['bc_child'],
                                         rel_docs['bc_mother'], rel_docs['letter_name'],
                                         rel_docs['bc_father'])
        # IC-number chain: BC parent number == income-proof number confirms a mother/father earner
        # even when the IC uploaded in their slot is the wrong card or absent (#9).
        if rel != 'match' and m in ('mother', 'father') and chain_verified_earner(application, m):
            rel = 'match'
        if rel == 'match':
            evidence.append(_item('relationship_confirmed', member=m))
        elif rel == 'mismatch':
            if m == 'mother':
                found['bc_mismatch'] = True
            else:
                found['patronymic_mismatch'].append(m)
            found['all_confirmed'] = False
        else:                       # 'unknown' (no patronymic) / 'pending' (not read) — no claim
            found['all_confirmed'] = False

        # ⚠ SHOWN, NOT PRESENT (TD-262 chunk 3, F10). This asked whether a payslip/EPF ROW exists,
        # so a MyKad photographed into the payslip slot painted the officer's screen with financial
        # evidence about a household the gate was holding shut (application 73). It now reads the
        # gate's own answer. The DECLARED arm below is UNCHANGED and still owns the third way
        # ('declared_evidenced' IS a declared amount + a letter that read) plus the one household
        # fact a per-earner answer cannot see — a declared amount accepted on a valid STR.
        if income_shown(application, m).way in ('salary_slip', 'epf'):
            found['any_financial'] = True
        else:
            # Phase 2A: no payslip/EPF for this member — a DECLARED informal amount may still
            # carry their income (accepted via a valid STR or a supporting doc), else it's unproven.
            _amt, _src = earner_monthly_income(application, m)
            if _src in ('declared_str', 'declared_evidenced'):
                found['any_financial'] = True
                found['declared_backed'].append(m)
            elif _src == 'declared_unproven':
                found['declared_unproven'].append(m)
    return evidence, found


def _salary_unresolved(members, rel_docs, found):
    """Aggregate the scan's per-member findings into the unresolved items — ONE item per code,
    each carrying a ``members`` list (see ``_salary_member_scan``). Returns ``(gap, review)``."""
    from .income_engine import relationship_doc_for
    gap, review = [], []
    if found['ic_missing']:
        gap.append(_item('earner_ic_missing', members=found['ic_missing']))
    if found['bc_missing']:
        gap.append(_item('birth_cert_missing'))
    elif rel_docs['bc_unusable'] and any(relationship_doc_for(m) == 'birth_certificate'
                                         for m in members):
        # required + unusable → re-upload, in the words that fit: wrong-type (#27) says it is not
        # a birth certificate; unreadable (#23) says we could not read the one they sent. Both
        # codes are written OUT as literals so the i18n coverage guard can see them.
        if rel_docs['bc_unusable'] == 'unreadable':
            gap.append(_item('birth_cert_unreadable'))
        else:
            gap.append(_item('birth_cert_not_genuine'))
    if found['letter_missing']:
        gap.append(_item('guardianship_letter_missing'))
    elif rel_docs['letter_unusable'] and any(relationship_doc_for(m) == 'guardianship_letter'
                                             for m in members):
        if rel_docs['letter_unusable'] == 'unreadable':
            gap.append(_item('guardianship_letter_unreadable'))
        else:
            gap.append(_item('guardianship_letter_not_genuine'))
    if found['ic_unreadable']:
        review.append(_item('earner_ic_unreadable', members=found['ic_unreadable']))
    if found['patronymic_mismatch']:
        review.append(_item('father_patronymic_mismatch', members=found['patronymic_mismatch']))
    if found['bc_mismatch']:
        review.append(_item('birth_cert_mismatch'))
    return gap, review


def _salary_place_verdict(application, members, evidence, found, gap, review):
    """Place the salary route's income band from the assembled evidence and findings."""
    from .income_engine import has_valid_str
    if gap:
        return _fact('income', 'gap', evidence, gap + review)
    # Phase 2A: an ACCEPTED declared income is honest evidence — surface it, and say WHY the
    # self-report counts (a valid STR is the means-test, else a supporting doc backs it). Two
    # distinct codes, not an ICU `select` param: the custom `t` has no MessageFormat engine.
    if found['declared_backed']:
        code = ('income_declared_accepted_str' if has_valid_str(application)
                else 'income_declared_accepted_evidenced')
        evidence.append(_item(code, members=found['declared_backed']))
    # A declared income with NO valid STR and NO supporting doc can't count yet. Firm-steward
    # stance: Unsure = proof required from the student (Check 2 raises the income_support_doc
    # request). Route to 'recommend' (amber) — never a blue read off the earner-IC/relationship
    # greens. Code-health S4 #20: this must run BEFORE the 'review' return — 'review' is the
    # BLUE band, so an unrelated review item (e.g. an unreadable IC) used to hide the unproven
    # declaration behind blue, contradicting the amber rule above.
    if found['declared_unproven']:
        return _fact('income', 'recommend', evidence, review + [
            _item('income_declared_needs_evidence', members=found['declared_unproven'])])

    # NB a valid non-breached STR no longer needs handling here: STR PRECEDENCE (_str_precedence_verdict)
    # settles it BEFORE the route split, so this salary path is only reached when there is no dispositive
    # STR. Salary is the genuine fallback (str-proof-spec.md §8).
    if review:
        return _fact('income', 'review', evidence, review)
    # The cluster adds up (every IC + relationship confirmed, financial evidence present).
    # Income GREEN also needs the AMOUNT to clear the B40 line (I4) — via the SAME
    # ``income_headroom`` band the STR fall-through uses (code-health S4 #14: the old
    # per-capita-only strict-< test here contradicted spec §7's two-test rule — gross
    # ceiling primary, per-capita a safety net — so the two routes could give opposite
    # answers for one household, and pc == ceiling read as "over"). Never blocks —
    # over-the-line or uncomputable goes to the officer/interview.
    # ⚠ THE 'over' RED IS TESTED WITHOUT `any_financial`, AND THAT KEEPS F10 ONE-WAY (TD-262
    # chunk 3). Tightening `any_financial` to READABILITY must only ever paint a household LESS
    # confidently, never more; left inside the old `any_financial and all_confirmed` guard it
    # would have taken a RED off the one household whose unusable payslip still reads a figure
    # over the line, turning a red advisory amber. Reachable only there: with no readable income
    # at all, `income_per_capita` cannot compute and the band is 'unknown'.
    if found['all_confirmed']:
        from .income_engine import income_headroom
        band, ctx = income_headroom(application, members)
        pc = ctx.get('per_capita')
        ceiling = ctx.get('per_capita_ceiling')
        if band == 'over':
            # V5 (#10): over-the-line = RED on BOTH routes (spec §8 rule 1). The STR fall-through
            # already banded the identical household economics 'gap'; the assembled salary route
            # banding it amber was the three-way seam inconsistency. Advisory only — the officer
            # still places the final verdict; circumstances may apply at interview.
            return _fact('income', 'gap', evidence,
                         [_item('income_above_b40_line', amount=pc, ceiling=ceiling)])
        if found['any_financial'] and band in ('probable', 'unsure'):
            # Under the (two-test) line — I4 keeps its historical binary green here: the
            # cluster is fully confirmed on this path, so the fall-through's thin-margin
            # 'unsure' demotion deliberately does NOT apply (that grading compensates for
            # an UNverified household; the salary-track redesign will revisit).
            evidence.append(_item('income_per_capita_ok', amount=pc, ceiling=ceiling))
            return _fact('income', 'verified', evidence, [])
    # A human places it: income not shown (an unusable document, or informal with no payslip/EPF),
    # a relationship we couldn't machine-confirm, or a household income that couldn't be computed.
    # Never blocks. (A dispositive STR would have been settled by STR precedence upstream.)
    return _fact('income', 'recommend', evidence, [_income_open_item(application)])


def verdict_income_salary(application, student_name, present, any_route=False):
    """Salary (non-STR) route: one or more working household members, each with their
    own IC + (optional) payslip + EPF, tagged via ``household_member``. Relationship to
    the student: father/brother/sister via the SHARED student-IC patronymic (siblings
    carry the same father's name); mother via birth certificate; guardian via letter.

      - no member ticked          → 'review' (`income_earner_undeclared`).
      - a required IC / relationship doc missing → 'gap' (member-tagged).
      - a relationship/IC that FAILS reading or matching → 'review'.
      - every IC present + every relationship confirmed + ≥1 payslip/EPF → 'verified'
        (the document DATA checks out; the income AMOUNT/B40 test is a later sprint).
      - **never blocks**: assembled but thin proof (no payslip/EPF = informal) or an
        unprovable relationship (e.g. a Chinese-style name with no patronymic) →
        'recommend' + `income_unverified_needs_interview`, for the officer to place.

    ``any_route=True`` is passed by the STR-route caller when the declared STR route holds no
    dispositive STR and the household nonetheless has a complete salary cluster (§6 rule 2, and
    TD-262 item 1 / rule 4). Such a student never touched the salary checkboxes, so
    ``income_working_members`` is empty and the earners must be reconstructed from the
    documents they actually tagged — the same reconstruction the submission gate uses."""
    from .income_engine import effective_working_members
    members = effective_working_members(application, any_route=any_route)
    if not members:
        # No working member declared → no income information yet → red (see STR route).
        return _fact('income', 'gap', _utility_context(application),
                     [_item('income_earner_undeclared')])

    rel_docs = _salary_relationship_docs(application)
    member_evidence, found = _salary_member_scan(application, members, student_name,
                                                 present, rel_docs)
    evidence = _utility_context(application) + member_evidence
    if found['any_financial']:
        evidence.append(_item('income_proof_present'))
    gap, review = _salary_unresolved(members, rel_docs, found)
    return _salary_place_verdict(application, members, evidence, found, gap, review)


def salary_evidence_stands_without_the_str(application) -> bool:
    """Does ANY working member's income stand on its own — WITHOUT leaning on a household STR?

    The gate `verdict_engine._stronger_income_fact` asks before it lets a salary reading RAISE a
    verdict the STR has just failed to settle (audit 2026-09-21). It is `income_shown`'s three
    per-earner ways, over the same earners the salary reading reconstructs, and it is deliberately
    NOT a second derivation: the per-earner answer has no STR arm, by the owner's ruling of
    2026-09-19, and that absence is the whole reason it is the right question here.

    ⚠ WHY `income_proof_present` ALONE WAS NOT ENOUGH, AND THE MISTAKE IS WORTH KEEPING IN VIEW.
    That marker follows `found['any_financial']`, one of whose arms is `earner_monthly_income`
    answering `declared_str` — a figure the family TYPED, accepted because `has_valid_str` says an
    approved, in-cycle STR is on file. `has_valid_str` reads CURRENCY and never asks whose STR it
    is. So an STR-route household with a stranger's current STR, one parent IC and a typed figure
    produced a salary reading resting ENTIRELY on the STR the fall-through exists to look past,
    and that reading then raised the very verdict the STR had failed. **A gate that asks "is there
    salary evidence?" must ask what that evidence itself rests on.**

    ⚠ THIS DOES NOT REPAIR `has_valid_str`, AND THAT IS A DECISION, NOT AN OVERSIGHT. Making a
    stranger's STR stop vouching for a declared amount EVERYWHERE also moves the Check-2
    declared-wage ask (`income_declared_gaps`'s STR short-circuit — a 2026-09-20 RULING with its
    own pinned rows), the officer follow-up context's `on_str`, the rendered
    `income_declared_accepted_str` evidence code, and per-capita arithmetic on BOTH routes. That
    is the owner's call, raised as **TD-285**; this is the ruling applied where the ruling bites.

    ⚠ AND IT IS NOT `salary_income_satisfied` EITHER, for the reason at `_stronger_income_fact`:
    that predicate's fourth way is a non-breached household STR, so it is satisfied by the very
    document in question.
    """
    from .income_engine import effective_working_members
    from .income_shown import income_shown
    return any(income_shown(application, m).shown
               for m in effective_working_members(application, any_route=True))


def raised_income_fact(salary, current):
    """The income fact `_stronger_income_fact` answers with when the SALARY reading wins.

    It is the salary reading's band and asks, plus **everything the STR route had already
    established** — its unresolved items (item 1's rule, unchanged) and, since the audit of
    2026-09-21, its EVIDENCE.

    ⚠ THE GREENS USED TO LEAVE WITH THE BAND. The raised fact took `salary['evidence']` wholesale,
    so `str_verified` — the line saying the government's own means-test was confirmed for this
    family — and the STR earner's own `earner_ic_present` vanished from the officer's card at the
    moment the household was upgraded. The IC line matters most in the ordinary shape of this
    case: the STR names the MOTHER while the FATHER's payslip carries the raise, so the two lines
    are about two different people and the salary reading can only ever have named one of them.

    ⚠ EXACT ITEMS, NEVER CODES, AND THE REDUNDANCY IS THE PRICE. De-duplicating by code would
    read better on a household whose two routes name the same earner — and would have dropped the
    mother's IC line because the card already carried the father's. Deciding that two items with
    one code are "the same claim" is a new matching rule, and this module does not invent one. So
    only a VERBATIM repeat is dropped, and a single-earner household carries one untagged line
    twice. Pinned, with the reasoning, in
    `test_income_evidence_homes.TestTheRaisedFactKeepsTheStrEvidence`.

    ⚠ IT MOVES NO BAND. Status, band and unresolved list are exactly what they were; this adds
    lines to a card. That is why the evidence carry alone would not bump `VERDICT_ENGINE_VERSION`.

    ORDER: the winning reading first, then the STR route's lines in their own order — the same
    convention as the unresolved carry beside it, so the two halves cannot drift apart.
    """
    carried = [i for i in current['evidence'] if i not in salary['evidence']]
    return _fact('income', salary['status'], salary['evidence'] + carried,
                 salary['unresolved'] + current['unresolved'])


def _failed_str_headroom_fact(application, earner, evidence, review):
    """The §6 evidence-driven fall-through for a FAILED STR (rejected / wrong-type): the STR is
    not a current STR, but salary/benefit documents on file may still show B40 — assess them and
    let the ``income_headroom`` band drive the income tile.

    ⚠ IT IS AN STR-ROUTE BRANCH LIVING IN THE SALARY MODULE, and the module docstring's line —
    *"the STR route stays in ``verdict_engine``"* — still holds: what stays there is the ORDER OF
    PRECEDENCE, which decides that a failed STR falls through at all. What it falls through TO is
    a salary reading, and that is this file. Moved here VERBATIM for TD-262 item 1b, with no
    behaviour change: `_verdict_income` is on the long-function ledger and `verdict_engine.py` on
    the oversize one, and neither number is ever raised — so the room for item 1b's branch was
    made by moving a self-contained block into the smaller module, not by lengthening the body.

    NB unsure/over return 'recommend' (→ amber) rather than 'review': a review tile reads BLUE off
    the verified earner-IC/relationship greens, which would overstate an unsure income."""
    # Code-health S4 #19: assess EVERY member with income evidence, not just the single
    # STR-route earner — after a route switch, tagged payslips/EPF for other members can
    # exist, and excluding them understates the household gross (a genuinely-over
    # household could band 'probable' off one earner's slip).
    from .income_engine import effective_working_members, income_headroom
    hh_members = list(dict.fromkeys([earner] + list(effective_working_members(application))))
    band, ctx = income_headroom(application, hh_members)
    if band == 'over':
        # Salary route FAILS — household income is over the B40 line → income fact FAILS (RED).
        # (Advisory only: the tiles guide, the officer still places the final verdict — not an
        # auto-reject; circumstances may still apply at interview.)
        return _fact('income', 'gap', evidence, review + [
            _item('income_above_b40_line', amount=ctx['per_capita'], ceiling=ctx['per_capita_ceiling'])])
    if band == 'unsure':
        return _fact('income', 'recommend', evidence, review + [
            _item('income_salary_unsure', amount=ctx['gross'])])
    if band == 'probable':
        evidence.append(_item('income_salary_probable', amount=ctx['gross']))
        return _fact('income', 'review', evidence, review)
    # 'unknown' — the STR failed AND there are no usable salary docs to assess → Unsure (amber):
    # we simply can't confirm B40, a human looks. NOT a blue review off incidental earner greens.
    return _fact('income', 'recommend', evidence, review)
