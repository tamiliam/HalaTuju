"""
Verification Verdict engine — the synthesis layer over the post-shortlist
signals (see ``docs/scholarship/verification-verdict-plan.md``, Sprint 1).

Rolls the scattered per-document signals (Vision OCR matchers, doc-assist fields, completeness,
the anomaly engine) into ONE four-fact verdict the coordinator AUDITS rather than assembles:

    Identity  — name + NRIC, checkable by matching → the AI may ASSERT 'verified'
    Academic  — the results slip is the student's (grade-accuracy lands in S2)
    Income    — the hard one; the AI asserts green ONLY on a verified STR
                document, else it RECOMMENDS and a human decides
    Pathway   — the offer letter

Pure + deterministic — **no LLM calls**, no model writes (mirrors ``anomaly_engine``). Each
``_verdict_*`` builder returns a fact dict; ``build_verdict`` collects the four in a fixed order.
The serializer exposes the list; the frontend resolves the human-readable labels from
``admin.scholarship.verdict.*`` by code (params interpolate), so the server stays locale-agnostic.

Design rules encoded here (settled in the plan):
  - **Green is expensive** — when in doubt the status drops to 'review', never up.
  - **Resolve before you escalate** — an OCR name truncation (the IC's name token set is a SUBSET
    of the typed name, e.g. a patronymic that spilled onto a second line) is settled silently as
    evidence, NOT raised as a mismatch; the NRIC is the hard identity key.
  - **Income green needs a verified STR *document***, not the self-declared flag.
  - **Address is a coherence test** — only a state-level (major) divergence
    escalates; sub-state postcode drift is noise and never flags.

Statuses (colour = the cockpit's Kent band, `officerCockpit.factTileTone` +
`docs/scholarship/verdict-confidence-bands.md`):
  verified  — green (Certain);  the AI asserts this fact.
  review    — blue (Probable) when ≥1 genuinely-verified value backs it, else
              amber (Unsure) — "blue needs a green"; confirm the flagged item.
  recommend — amber (Unsure);  evidence assembled, a HUMAN must place the verdict.
  gap       — red (Can't verify); a required input is missing/unreadable/unusable.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field

from .document_snapshot import latest_doc, present_doc_types
from .genuineness.bands import canonical_status, stored_status


# ⚠⚠ THE PREDICTOR'S OWN VERSION. BUMP IT WHEN A CHANGE HERE CAN ALTER A FACT'S STATUS, ITS BAND,
# OR ITS RED-CHIP COUNT — including a change in anything `build_verdict` reads (pathway_engine,
# income_engine, the genuineness ladder). Wording-only edits do not count; a moved threshold does.
#
# WHY IT EXISTS (owner, 2026-09-11): *"The model is what predicts whether a student qualifies.
# Genuineness of the document is one stage, but it not all. Otherwise where does the learning from
# predicting and being corrected sit?"* It sits in `ScholarshipApplication.ai_verdict_snapshot`
# (what THIS engine said) against `officer_verdict` (what the human said), compared per fact by
# `audit.compute_overrides` and rolled up by `audit.override_metrics` into the AI Reliability card.
# 88 such pairs were banked between 2026-06-17 and 2026-09-01 with NOTHING recording which engine
# produced them — so the scorecard averaged every generation as if it were one model. It is not
# hypothetical: `_declared_pathway` changed on 2026-09-10, and no stored row can tell you.
#
# ⚠ THIS IS NOT `MODEL_VERSION`, AND NOT `ai_registry`. `genuineness/*.MODEL_VERSION` versions
# whether ONE DOCUMENT looks genuine — one input to one fact. `halatuju.ai_registry` answers "which
# LLM would this job call right now" and explicitly RESOLVES, NEVER RECORDS. This engine calls no
# model at all; it is deterministic Python, and this constant is recorded ONTO the row so a past
# prediction can still say which logic produced it.
#
# ⚠ NEVER re-run `build_verdict` over old snapshots to "fill this in". A snapshot is the historical
# record of what the AI asserted at the time; re-running destroys the only evidence the scorecard
# rests on. Rows decided before this constant existed carry the sentinel `PRE_VERSIONING`.
#   2026-09-19.1 — TD-262 item 1 (rule 4): an STR-route household whose STR is stale, unreadable
#   or recipient-mismatched now has its salary evidence assessed too, and the STRONGER of the two
#   readings is the income fact. It can only ever RAISE a band, but it moves one, so it bumps.
#   2026-09-19.2 — TD-262 item 1b (rule 4, same day): the same preference now reaches an
#   INCOMPLETE STR cluster (a missing earner IC or birth certificate), which returned RED ahead of
#   both fall-throughs. Raise-only again, and again it moves a band, so it bumps.
#   2026-09-21.1 — audit of 2026-09-21: both fall-throughs would RAISE on a salary reading resting
#   on nothing but a DECLARED amount accepted off the household's STR, and `has_valid_str` never
#   asks whose STR that is. The gate now also requires the reading to stand WITHOUT the STR, which
#   LOWERS those households to the band they held before 2026-09-19.1/.2 — a band moves, so it
#   bumps. (The evidence carry in the same change moves no band and would not have bumped it.)
#   2026-09-29.1 — TD-285: `has_valid_str` asks WHOSE STR; a salary band can fall Certain->Unsure.
#   2026-09-30.1 — TD-292: "latest" document = newest uploaded_at, then highest id (tie-break).
#   2026-10-01.1 — TD-089: a guardian is linked off the letter's guardian AND ward names.
#   2026-10-02.1 — TD-114: a never-scored IC / slip / offer holds its fact at Probable (verdict_ladder);
#                  TD-151: a payslip figure outside RM100-20,000 a month is a misread (no figure).
#   2026-10-03.1 — TD-323: an EPF-implied salary under RM100/month is no BAND figure (earner falls to a declared
#                  amount, else verify at interview). No ceiling; evidence/gate/divergence unchanged (review F1).
#   2026-10-04.1 — TD-145: a one-campus pick compares the offer's university (another → pathway_confirm); SATU red.
#   2026-10-24.1 — AI outage: a read not yet made is no longer "unreadable" (no student ask).
#   2026-10-25.1 — TD-390: a card our outage left half-read is "service down", never a mismatch.
#   2026-10-25.2 — TD-401: an IC with no NRIC read is unreadable (a gap, not a pass on the name).
#   2026-10-26.1 — corpus-gaps C1: a known public TVET issuer's offer is NOT CHECKED (no step; Probable).
#   2026-10-26.2 — TD-403: an STR's year is asked against THIS calendar year; a later year = 'future' (Unsure).
#   2026-10-26.3 — third route S3: the higher-results Academic card; the SPM slip reads spm_grades_for.
#   2026-10-27.1 — third route S4 (#43): a higher result in the SPM card is named, never SPM-compared;
#   .2 — #388: higher results OWED over a pre-S3 snapshot cap Academic at Probable (`higher_owed`).
#   .3 TD-404 ANAK=AK, BINTI=BT/BTE; .4 STPM S3 scored (+1A); .5 TD-410 a suspect proof shows no income;
#   2026-11-13.2 — F1 slip-check rule table (owner 2026-11-13, Q1-Q4, Q6, Q7): a short SPM read names what it missed (no tick); STPM mirrors SPM (short read unchecked, extra red on a full read, a +/- difference amber on an AI read, red on the exact read); a higher result in the SPM slot holds no clean card back; one degree test (degree_bound) for the pre-submit ask
#   2026-11-13.3 — F1 review: an AI STPM read never says extra (unchecked); an SPM read short of the printed count is never complete (academic_slip_rows_unread); an SPM-entry pathway code or a preparatory name is not a degree by name.
#   2026-11-13.4 — F1 re-check: .3's degree narrowing is withdrawn from degree_bound / destination (the award, funding estimate and after-submit owed cap are as on origin/main again, so a matric / asasi / diploma / pismp code under a degree name, a preparatory name or the American Degree Program is owed and capped as before); it applies to the before-submit ask only (TD-617).
VERDICT_ENGINE_VERSION = '2026-11-14.1'   # 11-14.1 TD-617 owner ruling: an SPM-only PISMP student (code, PISMP/Perguruan name or IPG) is never owed higher results (no Academic cap); an American Degree Program or MARA "Persediaan ... Luar Negara" name turns Pathway red (pathway_funded_or_abroad).

#: Stamped on decided rows that predate the version column. NOT a version number — deliberately
#: unmistakable, so it can never be read as an engine generation.
PRE_VERSIONING = 'pre-versioning'


@dataclass(frozen=True)
class Item:
    """One evidence / unresolved line. ``params`` interpolate into the matching
    ``admin.scholarship.verdict.item.<code>`` i18n string on the frontend."""
    code: str
    params: dict = field(default_factory=dict)


def _item(code, **params):
    return asdict(Item(code, params))


def _fact(name, status, evidence, unresolved):
    return {'fact': name, 'status': status,
            'evidence': evidence, 'unresolved': unresolved}


def _income_open_item(application):
    """The line an officer reads when income could not be settled by machine.

    ⚠ TWO DIFFERENT FACTS WORE THE SAME SENTENCE until 2026-09-10. *"Income can't be
    document-verified (informal / no payslip)"* describes a defect in the EVIDENCE. A gift
    that configures no income ceiling has no such defect — it simply does not means-test
    income, and telling its officer that readable payslips "can't be verified" is false.

    ⚠ THE STATUS DOES NOT MOVE. Both cases stay 'recommend' (amber — a human places it,
    never blocked). Only the sentence differs. A band moving here would be a bug.

    NB deliberately NOT added to ``views_admin._NEEDS_INTERVIEW_AMBERS``: "this gift does
    not test income" is the opposite of an interview talking point — there is nothing to
    confirm.

    ⚠ BOTH CODES ARE WRITTEN AS LITERALS, deliberately. `test_verdict_item_i18n` walks the AST
    for `_item('...')` and can only check a code it can SEE; a conditional inside the call
    would hide both from the guard that stops a raw key path rendering in the cockpit. It
    caught exactly that on the first run of this sprint."""
    from .income_engine import income_test_configured
    if income_test_configured(application):
        return _item('income_unverified_needs_interview')
    return _item('income_not_means_tested')


# ── document readers ─────────────────────────────────────────────────────────

# Phase 2 (version history): these three are the MAIN verdict read funnel — every one
# filters `superseded_at__isnull=True` so a replaced document can never count in a verdict.
# Since TD-282 all three delegate to `document_snapshot`, which answers from one shared read
# when the officer's detail GET has a snapshot open and runs this same query otherwise. They
# stay as named functions because a dozen call sites and several tests import them.
def _latest_doc(application, doc_type):
    return latest_doc(application, doc_type)


def _latest_doc_for_member(application, doc_type, member):
    """The latest LIVE income document of *doc_type* tagged to a specific household
    *member* (salary route). The (doc_type, household_member) pair is the
    single-instance key, so this returns that member's current IC / payslip / EPF."""
    return latest_doc(application, doc_type, member=member)


def _present_doc_types(application):
    return present_doc_types(application)


def _doc_assist_verdict(doc):
    """The deterministic student_verdict stored by doc-assist (ok / name_mismatch
    / address_mismatch / wrong_doc / unreadable), or '' if never run."""
    if doc is None:
        return ''
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    return vf.get('student_verdict', '') or ''


def _doc_assist_fields(doc):
    if doc is None:
        return {}
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    f = vf.get('fields', {})
    return f if isinstance(f, dict) else {}


def _doc_wrong_type(doc):
    """True when the doc's genuineness verdict says it is NOT that kind of document at all
    (canonical ``not_<type>``). Its extracted fields then prove nothing — e.g. a non-BC in the
    birth-certificate slot must not confirm a mother↔student relationship (#27, owner 2026-07-08)."""
    if doc is None:
        return False
    raw = stored_status(doc.vision_fields)                                  # TD-293
    return canonical_status(raw, getattr(doc, 'doc_type', None)).startswith('not_')


def _usable_relationship_fields(application, doc_type):
    """The latest live relationship doc of ``doc_type`` + its fields, with an unusable doc's
    fields blanked so no relationship can be read off it. Returns ``(doc, fields, unusable)``.

    ⚠ ``unusable`` IS A REASON STRING, NOT A BOOLEAN — '' / 'wrong_type' / 'unreadable'. It stays
    truthy in all the existing ``if bc_unusable`` sites, and it exists because the two states owe
    the student DIFFERENT messages: 'wrong_type' says *that is not a birth certificate* (#27),
    'unreadable' says *we could not read yours, please send a clearer copy* (#23). Collapsing them
    would tell a family with a poor scan that their certificate is not genuine.
    """
    from .income_engine import relationship_doc_unreadable   # lazy: income_engine imports us
    d = _latest_doc(application, doc_type)
    if d is None:
        return d, {}, ''
    if _doc_wrong_type(d):
        return d, {}, 'wrong_type'
    if relationship_doc_unreadable(d):
        return d, {}, 'unreadable'
    return d, _doc_assist_fields(d), ''


# ── Identity (name + NRIC) ───────────────────────────────────────────────────

def _verdict_identity(application):
    """The identity fact's home is ``verdict_identity`` (moved there whole, audit sprint A3.4,
    moves only); this seam keeps ``build_verdict`` and every ``verdict_engine`` reader working."""
    from .verdict_identity import _verdict_identity as identity_fact   # lazy: it imports our helpers
    return identity_fact(application)


# ── Academic (results slip) ──────────────────────────────────────────────────

def _verdict_academic(application, spm_only=False):
    """The academic fact's home is ``verdict_academic`` (moved there whole, request #62 split,
    moves only); this seam keeps ``build_verdict`` and every ``verdict_engine`` reader working."""
    from .verdict_academic import _verdict_academic as academic_fact   # lazy: it imports our helpers
    return academic_fact(application, spm_only)


# ── Income (the hard one) ────────────────────────────────────────────────────

def _utility_context(application):
    """Soft, officer-facing income context from the utility bills (never a gate): the
    combined water+electricity per-capita as a B40 proxy, + an arrears hardship signal.
    Imperfect — surfaced as evidence the coordinator weighs, not a verdict driver."""
    from .income_engine import (utility_per_capita, utility_hardship,
                                unemployment_corroborated_members, household_size_shortfall)
    # Every code emitted here is SOFT evidence — it must sit in officerCockpit.ts SOFT_EVIDENCE
    # (blue needs a green). The `# SOFT` markers are machine-pinned by the jest guard test
    # `soft-evidence-drift.test.ts`; tag any new soft code the same way.
    items = []
    pc = utility_per_capita(application)
    if pc and pc['signal'] == 'b40':
        items.append(_item('utility_percapita_b40', amount=int(round(pc['per_capita']))))  # SOFT
    elif pc and pc['signal'] == 'high':
        items.append(_item('utility_percapita_high', amount=int(round(pc['per_capita']))))  # SOFT
    if utility_hardship(application):
        items.append(_item('utility_hardship'))  # SOFT
    # Phase 2B (P7): an EPF (all-zeros / lapsed) corroborating a member's unemployment — soft
    # reviewer evidence for the "why little income" story. Household context, both routes; never a gate.
    corroborated = unemployment_corroborated_members(application)
    if corroborated:
        items.append(_item('unemployment_epf_corroborated', members=corroborated))  # SOFT
    # Phase 2C (P4): the people described outnumber the stated household size → the per-capita
    # denominator may be too small (income overstated). Soft reviewer flag to confirm; never a gate.
    hs = household_size_shortfall(application)
    if hs:
        items.append(_item('household_size_confirm', described=hs['described'], size=hs['size']))  # SOFT
    return items

def _str_precedence_verdict(application, utility=None):
    """STR PRECEDENCE (owner 2026-07-07), route-agnostic. A genuine, approved, non-breached STR whose
    recipient matches — exhaustively, name OR nric (``household_str_status``) — a parent/guardian whose
    relationship to the student is CONFIRMED settles income B40 BEFORE the route split; the salary
    route is explored ONLY when no such STR exists (str-proof-spec.md §8). Returns an income ``_fact``,
    or None when there is no dispositive STR (→ the route-specific assessment runs unchanged).

      - current STR + confirmed parent/guardian recipient → 'verified' (Certain).
      - unconfirmed STR (approved, no date) + confirmed → 'review' (Probable / blue).
      - recipient matches an on-file IC but the parent/guardian LINK isn't confirmed → None (fall
        through): an unproven relationship isn't an established parent/guardian yet, so the route
        logic asks for the missing tie (BC / patronymic) — the fraud guard the salary route already
        applied via ``confirmed_members``."""
    from .income_engine import (household_str_status, _member_ic_doc, letter_names,
                                member_relationship_status, chain_verified_earner,
                                student_name_for_link)
    grade, member = household_str_status(application)
    if not grade or not member:
        return None
    # The IC-aware name: a typed profile name without the A/P connector must not lose the
    # patronymic father link when the student's own verified IC carries it (#88).
    student_name = student_name_for_link(application)
    ic_doc = _member_ic_doc(application, member)
    ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
    # Confirm the matched recipient really is the student's parent/guardian: father → patronymic,
    # mother → birth certificate, guardian → letter, or the BC↔proof IC-number chain (#9).
    # A WRONG-TYPE relationship doc is unusable — its fields must not confirm anything (#27).
    _, bcf, _ = _usable_relationship_fields(application, 'birth_certificate')
    g_doc, _, g_unusable = _usable_relationship_fields(application, 'guardianship_letter')
    g_name, g_ward = letter_names(None if g_unusable else g_doc)    # TD-089 + review F1
    rel = member_relationship_status(member, student_name, ic_name, bcf.get('bc_child_name', ''),
                                     bcf.get('bc_mother_name', ''), g_name,
                                     bcf.get('bc_father_name', ''), g_ward)
    if rel != 'match' and member in ('mother', 'father') and chain_verified_earner(application, member):
        rel = 'match'
    if rel != 'match':
        return None            # recipient not yet an established parent/guardian → route logic runs
    # TD-287 (review F5): the caller's own bills reading, deep-copied; None reads them here.
    evidence = _utility_context(application) if utility is None else copy.deepcopy(utility)
    if ic_name:
        evidence.append(_item('earner_ic_present', member=member, name=ic_name))
    evidence.append(_item('relationship_confirmed', member=member))
    evidence.append(_item('str_verified'))
    if grade == 'current':
        return _fact('income', 'verified', evidence, [])
    # unconfirmed (approved, no date) → Probable (blue); confirm the cycle at interview.
    return _fact('income', 'review', evidence, [_item('str_not_current', status='unconfirmed')])


#: The income bands, weakest first. Used ONLY to pick the stronger of two readings of the SAME
#: household (``_stronger_income_fact``) — never to compare one fact against another.
_INCOME_BAND_ORDER = ('gap', 'recommend', 'review', 'verified')


def _stronger_income_fact(current, application, student_name, present, utility=None):
    """TD-262 items 1 and 1b — **"the stronger proof should be given preference"** (owner
    2026-09-19, `docs/decisions.md`). An STR-route household whose STR was stale, unreadable or in
    somebody else's name was capped at Unsure with the payslips on file NEVER ASSESSED: the
    `str_unsure` / `str_mismatch` branches returned before the salary route was ever reached. Only
    a REJECTED or wrong-type STR opened that net. So assess the salary evidence too, and answer
    with whichever of the two readings is stronger.

    ⚠ ITEM 1b EXTENDS THAT TO AN INCOMPLETE CLUSTER (owner, same day). A missing earner IC or
    birth certificate returned RED from the `gap` branch, ahead of both fall-throughs — a red
    about the STR CLUSTER, read as though the household had shown nothing about what it earns.
    The mother is often the STR recipient while the FATHER is the one whose payslip is on file;
    that household answers the income question, and it now reads as having answered it.

    ⚠ IT CAN ONLY EVER RAISE. The readings are compared by band and the weaker is discarded, so
    no household comes out below the answer it had before — the salary route's own
    `income_above_b40_line` RED, for one, is never taken over an amber STR reading.

    ⚠ THE STR'S UNRESOLVED ITEMS ARE CARRIED ONTO THE RAISED FACT, deliberately. The band moves
    and nothing else is lost: the officer still reads why the STR did not settle it, and the
    student's `str_not_current` re-upload ask stays open (`resolution.CODE_TO_TICKET`). Under
    item 1b that carry is load-bearing rather than tidy — the cluster's `earner_ic_missing` /
    `birth_cert_missing` asks are the whole reason the band was red, and a raised household must
    still be asked for the documents it owes.

    ⚠ THERE MUST BE SOMETHING TO PREFER, and the test for that is the salary route's OWN
    `income_proof_present` marker — appended iff at least one member's income is SHOWN by a
    payslip, an EPF or an ACCEPTED declared amount. Without it the salary reading rests on an IC
    and a patronymic and nothing about what the household earns, which is not "stronger proof":
    a two-earner household with one unreadable IC would otherwise be lifted from Unsure to
    Probable by a document that says nothing about money.

    ⚠ AND `salary_income_satisfied` IS NOT THAT TEST, though it reads like it. It is the
    submission gate's "one complete cluster", and a cluster is complete on ANY of the owner's
    four ways — the fourth being a non-breached household STR. A stale, unreadable or
    recipient-mismatched STR is not BREACHED, so that predicate is satisfied by the very STR
    this function exists to look past, and it would open the door for a household with no
    payslip at all. One derivation, but it answers a different question.

    ⚠ AND THAT MARKER IS NOT ENOUGH ON ITS OWN (audit 2026-09-21): it counts a DECLARED amount
    accepted off a stranger's STR. `salary_evidence_stands_without_the_str` is the second half of
    the gate and carries the whole reasoning; it runs FIRST because it is much the cheaper.

    R1/R2 are untouched: a CURRENT genuine STR is settled by STR PRECEDENCE long before this
    runs, so payslips can still never lower it."""
    from .verdict_income_salary import (raised_income_fact,
                                        salary_evidence_stands_without_the_str,
                                        verdict_income_salary)
    if not salary_evidence_stands_without_the_str(application):
        return current
    salary = verdict_income_salary(application, student_name, present, any_route=True,
                                   utility=utility)   # TD-287: the bills, read once
    if not any(i['code'] == 'income_proof_present' for i in salary['evidence']):
        return current
    if _INCOME_BAND_ORDER.index(salary['status']) <= _INCOME_BAND_ORDER.index(current['status']):
        return current
    return raised_income_fact(salary, current)


def _verdict_income(application):
    """Income Check-1 (item 3): the guided wizard says which documents the family
    needs (income_engine.income_requirements); this assembles whether they're present,
    whether the EARNER is the student's family (father=patronymic, mother=Birth
    Certificate, guardian=letter), and places the verdict:

      - STR route, all compulsory present + relationship OK → 'verified' (gold standard).
      - salary route assembled → 'recommend' (a human still places the B40 amount call).
      - a compulsory DOC missing → 'gap'; a relationship/check that FAILS → 'review'.
      - **never blocks** a genuinely poor family: an informal/no-EPF earner whose income
        can't be document-proven gets 'recommend' + `income_unverified_needs_interview`,
        which the officer confirms via the interview (lifestyle, household, burden).

    Wizard not walked yet → 'review' (`income_earner_undeclared`), unless a present,
    name-matched STR already settles it on its own.

    The SALARY route delegates to ``_verdict_income_salary`` (multi-earner); the declared STR
    route's four steps live in ``verdict_income_str`` (audit sprint A3.4, a pure move)."""
    from .income_engine import student_name_for_link, salary_income_satisfied
    # Lazy: `verdict_income_salary` and `verdict_income_str` import this module's `_fact` /
    # `_item` primitives, so the edge has to be one-way at import time (the `income_engine` pattern).
    from .verdict_income_salary import verdict_income_salary
    from .verdict_income_str import str_route_income_fact
    evidence = list(utility := _utility_context(application))  # TD-287
    present = _present_doc_types(application)
    # IC-aware (#88): prefer the student's verified IC read when the typed name lacks the
    # patronymic connector, so the father link doesn't silently die on a typing habit.
    student_name = student_name_for_link(application)
    earner = (getattr(application, 'income_earner', '') or '').strip()
    route = (getattr(application, 'income_route', '') or '').strip()

    # STR PRECEDENCE (owner 2026-07-07): a genuine, approved, non-breached STR whose recipient
    # matches ANY parent/guardian settles B40 before the income route is even considered — the
    # salary route is explored ONLY when no such STR exists. Route- and tag-agnostic, so a
    # misfiled route/earner (e.g. #45 on the salary route with the STR tagged 'mother') no longer
    # drops a genuine-STR household to salary.
    settled = _str_precedence_verdict(application, utility)
    if settled is not None:
        return settled

    str_doc = _latest_doc(application, 'str')

    # Salary (non-STR) route → multi-earner path.
    if route == 'salary':
        return verdict_income_salary(application, student_name, present, utility=utility)

    # Wizard not walked → no income information at all yet. Like a missing IC / slip /
    # offer, "nothing provided" is a hard red (can't verify), not a soft amber — the
    # student must complete the income wizard (and its docs) before we can check anything.
    if not earner or not route:
        return _fact('income', 'gap', evidence, [_item('income_earner_undeclared')])

    # ── Declared STR route, NO STR letter at all → judge what they SUPPLIED (2026-08-01) ──
    # str-proof-spec.md §6 rule 2 has always said the STR fails and the salary route is evaluated
    # when the STR is "rejected / wrong_type / ABSENT". Only the first two were implemented: an
    # absent STR filed `income_proof_missing` as a hard gap and returned RED below, before the §6
    # fall-through could run. So a family that ticked "STR" and then documented an earner properly
    # was judged on WHAT THEY DECLARED instead of WHAT THEY SUPPLIED — while `income_established`,
    # the SUBMISSION gate, read the same household as satisfied and let them through. That
    # disagreement is the whole defect (#106: father's IC + payslip, submitted fine, then red).
    #
    # GATED on a complete cluster, deliberately, and on the SAME predicate the submission gate
    # uses — one derivation, not a second copy of "is there salary evidence?" (a divergent second
    # copy is how the two surfaces came to disagree in the first place). The gate is also what
    # holds §8's 🔴 row: with no STR *and* no salary evidence there is "no usable income evidence
    # at all", which stays RED and keeps asking for the STR.
    if str_doc is None and salary_income_satisfied(application):
        return verdict_income_salary(application, student_name, present, True, utility)

    # ── The declared STR route: earner IC, relationship, the STR document, then the verdict ──
    # Moved whole to `verdict_income_str` (audit sprint A3.4) — four named steps, same lines, same
    # order; this function was 210 lines on the long-function ledger.
    return str_route_income_fact(application, earner, str_doc, student_name, present, evidence,
                                 utility)


# ── Pathway (offer letter) ───────────────────────────────────────────────────

def _verdict_pathway(application):
    """The offer letter settles the FINAL chosen pathway. Identity on the letter
    (name + IC — the IC is the strong check) must be the applicant's, then the
    offer is reconciled against what the student declared at apply time:

      - the offer agrees (or there's nothing specific to clash with) → 'verified':
        the offer IS the evidence; nagging a student whose offer matches is pointless.
      - the offer is for a genuinely DIFFERENT place/field than declared → ask the
        student to confirm which is final (an AI-raised query, no human officer);
        on Yes the record is realigned + stamped → 'verified'.

    No offer letter → 'gap' (red) AND a submission blocker (`offer_letter_missing`
    in consent_blockers): the programme funds a CONFIRMED place, so without an offer
    there is nothing to fund. (An older design tolerated "declared-only → review";
    that changed with the 2026-06-07 confidence-scale alignment.)

    With an offer on file the reading lives in ``verdict_pathway.offer_pathway_fact`` (moved
    there whole, audit sprint A3.4). The no-offer branch stays HERE because its ``# SOFT`` line
    is read out of this file by the web's ``soft-evidence-drift.test.ts``."""
    offer = _latest_doc(application, 'offer_letter')
    chosen = (application.chosen_pathway or application.intended_pathway or '').strip()

    if offer is None:
        # The offer letter is compulsory: the programme supports a CONFIRMED place, so
        # without an offer there is nothing to fund (income can be settled at interview,
        # a pathway cannot). Red + submission blocker; the declared pathway rides along
        # as context when present.
        decl = [_item('pathway_declared', pathway=chosen)] if chosen else []  # SOFT
        fact = _fact('pathway', 'gap', decl, [_item('offer_letter_missing')])
    else:
        from .verdict_pathway import offer_pathway_fact   # lazy: it imports our helpers
        fact = offer_pathway_fact(application, offer)
    from .verdict_pathway import funded_or_abroad     # TD-617: ADP / overseas preparation → red
    return funded_or_abroad(application, fact)


# ── Aggregator ───────────────────────────────────────────────────────────────

# The INCOME fact's flat genuineness cap (which route-required documents may lower it, and the
# wrong-type STR exception) lives in ``verdict_caps`` (audit sprint A3.4). `_suspect_genuineness`
# stays here: ``verdict_ladder`` imports it from this module at load time.


def _suspect_genuineness(application, doc_types):
    """The CANONICAL genuineness status among the latest of the given doc types (the higher results:
    `higher_results.anchor_doc`, M4b SF4) if it warrants a soft cap ('suspect' / 'not_<type>'), else ''.
    Folds any value — current or legacy — via ``canonical_status``. SOFT: the reviewer is the authority."""
    from .higher_results import anchor_doc
    for dt in doc_types:
        d = anchor_doc(application, dt)
        raw = stored_status(d.vision_fields if d else None)                 # TD-293
        st = canonical_status(raw, getattr(d, 'doc_type', None) or dt)
        if st and st != 'genuine':
            return st
    return ''


def _apply_genuineness_caps(application, facts):
    """The income fact's flat genuineness cap — its home is ``verdict_caps`` (moved there whole with
    the route-required document list and the wrong-type STR exception, audit sprint A3.4, because
    this file is on the oversize ledger). This name is kept for ``build_verdict`` and its tests."""
    from .verdict_caps import _apply_genuineness_caps as apply_caps   # lazy: it imports our helpers
    return apply_caps(application, facts)


def _apply_genuineness_ladder(application, facts):
    """The genuineness / red-chip ladder — its home is ``verdict_ladder`` (moved there whole,
    Now sprint 3, because this file is on the oversize ledger). This name is kept for callers."""
    from .verdict_ladder import _apply_genuineness_ladder as apply_ladder
    return apply_ladder(application, facts)


def build_verdict(application) -> list[dict]:
    """The four-fact verification verdict in fixed order (identity, academic,
    pathway, income). Pure + deterministic — safe to call inside a serializer
    GET. Each fact: ``{fact, status, evidence[], unresolved[]}`` where evidence
    and unresolved items are ``{code, params}`` dicts resolved on the frontend.

    Genuineness is applied last: the LADDER (identity/academic/pathway) + the flat cap (income).

    **A fact whose evidence this programme does not ask for is OMITTED (Layer 0).** Not green and
    not red — both would be lies. Green asserts we verified something; red asserts a gap, when
    there is no gap because nobody wanted the document. The reviewer should simply not be shown a
    Pathway tile for a programme that does not collect offer letters. Callers already map over
    whatever facts they receive, so a shorter list is not a new shape.

    For every programme today the answer is all four, because the catalogue defaults make all four
    documents required — so this is inert until an organisation changes something in Sprint 5.
    """
    from . import requirements

    # fact name → the catalogue item that supplies its evidence.
    EVIDENCE_FOR = {
        'identity': 'ic',
        'academic': 'results_slip',
        'pathway': 'offer_letter',
        'income': 'income_proof',
    }

    facts = [
        _verdict_identity(application),
        _verdict_academic(application),
        _verdict_pathway(application),
        _verdict_income(application),
    ]
    facts = [
        f for f in facts
        if requirements.asks_for(application, 'document', EVIDENCE_FOR.get(f.get('fact'), ''))
        or f.get('fact') not in EVIDENCE_FOR   # an unmapped fact is never silently dropped
    ]
    return _apply_genuineness_ladder(application, _apply_genuineness_caps(application, facts))
