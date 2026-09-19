"""TD-262 F2 — who is still owed a question about a DECLARED informal wage.

The owner's fourth way of showing income (2026-07-25) is *tell us the amount and add one simple
letter*. ``declared_income_gaps`` is what makes the second half of that sentence happen: a
working member who declared a figure the household has not backed becomes a Check-2 request for
an ``income_support_doc`` (``check2_queries`` → ``declared_income_evidence_missing``).

⚠ THE DEFECT THIS MODULE WAS SPLIT OUT TO FIX (F2, the dead-end chase). The gap used to fire on
a declared amount alone. A family who typed a figure and then uploaded a perfectly good payslip
was chased for a letter they did not need — and, because the student screen hid the cash panel
the moment ANY salary/EPF file existed, they could neither answer the chase nor retract the
figure. It asked a question that had already been answered, through a door it had locked.

**What decides it now.** No gap for a member whose income is already SHOWN another way —
``income_shown``, the owner's per-earner answer, which is the same answer the submission gate,
the officer's chase list and the AI verdict read. Deliberately SHOWN and not PRESENT: a
``not_salary`` photo or a blank EPF documents nothing, so that household is still asked (the
F4 / F5 rule, applied here too).

⚠ NOTHING ABOUT ELIGIBILITY MOVES. This is a Check-2 ASK. It is read by ``_gap_sets`` and by
nothing else — no gate, no blocker code, no verdict fact — so no student's ability to submit
and no fact on an AI card can move with it. ``VERDICT_ENGINE_VERSION`` is therefore NOT bumped.

It lives in its own module because ``income_engine.py`` sits on the oversize ledger
(``halatuju_api/code-standards.json``) and the Phase-4 standing rule of 2026-09-19 says a
feature sprint does not grow a file that is waiting on its split. ``income_engine`` re-exports
the name, so every importer — ``check2_queries._gap_sets`` among them — is unchanged. Same
reason, same shape as ``income_shown.py``, ``income_str_ownership.py`` and
``verdict_income_salary.py``.
"""


def declared_income_gaps(application):
    """Working members who DECLARED an informal income (Phase 2A) that isn't yet accepted:
    the household has NO valid STR, this member's income is not shown any other way, and there
    is no supporting income document for them. Each → a doc request for an
    ``income_support_doc`` (D1: flexible evidence). Returns ``[{'member': m}, …]`` (empty when
    every declared amount is accounted for).

    ⛔ THE TWO EARLY RETURNS ARE RULINGS, NOT UNFINISHED EDGES — DO NOT "COMPLETE" THEM. Salary
    route only, and a valid STR accepts EVERY declared amount at once. Owner, 2026-09-20: *"If
    STR has been fulfilled, there is no need for the student to complete the cash door. It is
    there primarily for those without STR or salary slip."* The fourth way exists for households
    with NEITHER a current STR NOR a payslip; the cash door is never added to the STR route
    (`docs/decisions.md`). Each return has a pinned row in ``test_income_declared_gaps.py``.

    ⚠ THE ``income_shown`` TEST IS NOT A TIDY-UP; IT IS THE FIX (F2). Without it the letter is
    demanded from a member whose payslip or EPF already answered the question. With it, the ask
    survives exactly where it is still a real question: nothing on file, or only a document
    that cannot carry the income.

    ⚠ AND IT SUBSUMES THE OLD ``has_income_support_doc`` TEST RATHER THAN SITTING BESIDE IT.
    Once a declared amount is known to exist, ``income_shown``'s third arm *is* that predicate
    (both read ``income_support_docs`` and require ``student_verdict == 'ok'``), so keeping
    both would put one rule in two places here — the very thing TD-262 exists to undo. The
    letter path stays pinned from this side by its own rows."""
    from . import income_engine as ie
    from .income_shown import income_shown

    if (getattr(application, 'income_route', '') or '').strip() != 'salary':
        return []
    if ie.has_valid_str(application):
        return []
    gaps = []
    for m in ie.effective_working_members(application):
        if ie.declared_amount(application, m) is None:
            continue
        if income_shown(application, m).shown:     # already answered — a payslip, an EPF, or
            continue                               # this very amount backed by a letter
        gaps.append({'member': m})
    return gaps
