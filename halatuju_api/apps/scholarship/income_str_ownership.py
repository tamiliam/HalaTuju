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


def str_recipient_is_stranger(application) -> bool:
    """True when the household's live STR is PROVABLY in someone else's name.

    Reads the same document ``str_not_breached`` and ``household_str_status`` read — the latest
    non-superseded ``str`` — and the same recipient verdict (``student_str_check``, which has
    already matched name and NRIC independently against every parent/guardian). ``'match'`` on
    either field is the family's own STR. Only a positive ``'mismatch'`` with no match anywhere
    is a stranger's; ``'no_ref'`` (nothing read, or nothing to compare against) is neither, and
    returns False."""
    from . import income_engine as ie
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = (docs.filter(doc_type='str', superseded_at__isnull=True)
               .order_by('-uploaded_at').first())
    if str_doc is None:
        return False
    sc = ie.student_str_check(str_doc)
    if not sc:
        return False
    if sc['name_status'] == 'match' or sc['nric_status'] == 'match':
        return False                                  # the family's own — matching succeeded
    return 'mismatch' in (sc['name_status'], sc['nric_status'])


def stranger_str_blocks_submission(application) -> bool:
    """True when a stranger's STR is the ONLY thing standing in for this household's income —
    the exact case F8 must stop at the submission gate.

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
