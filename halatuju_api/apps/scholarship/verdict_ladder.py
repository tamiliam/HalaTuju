"""The genuineness / red-chip LADDER for Identity, Academic and Pathway (owner 2026-07-07).

⚠ MOVED, NOT REWRITTEN (Now sprint 3, 2026-10-02). Every line from the ladder's comment block to
the end of ``_apply_genuineness_ladder`` is the block that sat in ``verdict_engine.py``, in the same
order — moved because ``verdict_engine.py`` is on the oversize ledger (`code-standards.json`) and
TD-114 had to add a rule here, the same reason ``verdict_income_salary.py`` is a module.
``verdict_engine._apply_genuineness_ladder`` stays as a seam so its callers and imports are
unchanged. The one rule ADDED after the move is marked ``TD-114`` below.
"""
from __future__ import annotations

from .genuineness.bands import canonical_status
from .services import ic_identity_blockers
from .verdict_engine import _item, _latest_doc, _suspect_genuineness


# ── Genuineness / eligibility LADDER (identity + academic + pathway) — owner 2026-07-07 ──
# The band is REBUILT explicitly (not "step the bespoke content band"):
#
#     band_index = max(base_index, genuineness_step + red_chip_count),  floored at 'gap'
#     _BAND_LADDER = ('verified'=Certain, 'review'=Probable, 'recommend'=Unsure, 'gap'=Fail)
#
#   • genuineness_step — by SCORE, uniform for every signature-scored doc (offers INCLUDED as of
#     MODEL_VERSION 1.4.0): genuine (p≥0.70) → 0, suspect (0.35–0.70) → 1, fake (p<0.35) → 2.
#   • red_chip_count — one −1 per RED content variable: Identity Name·NRIC; Academic Name·Subjects·
#     Results; Pathway Name·IC·Pathway. A variable is red when its value MISMATCHES or is
#     required-but-missing on an extracted offer (merely unread/pending → grey, the base band's
#     under-claim). The PATHWAY variable is additionally red when the document cannot establish any
#     pathway — a non-genuine offer (suspect/fake: interview slip, pemakluman, private-IPTS letter)
#     proves no pathway, so its chip stacks with the genuineness step (owner arithmetic: #31/#131
#     suspect −1 + pathway −1 = Unsure; #84 fake −2 + pathway −1 = Fail).
#   • base_index — the `_verdict_*` band, which carries only the missing→gap and unread→review
#     under-claims (mismatches are NOT baked into it any more, they are chips); `max` keeps an
#     unread-but-genuine doc at Probable rather than letting 0 chips + step 0 read Certain.
#
# Worked (owner-verified): #12 offer p=0.30 → fake(2) + Name+IC+Pathway(3) = 5 → Fail; #31 pemakluman
# p=0.40 → suspect(1) + Pathway(1), Name+IC green = 2 → Unsure. A lone academic name mismatch on a
# genuine slip → 0+1 = Probable (softens the old hard-Fail — owner accepted, rare / OCR misread).
# Income keeps its own model (STR-precedence + headroom / flat cap).
_BAND_LADDER = ('verified', 'review', 'recommend', 'gap')

# The document whose genuineness fingerprint scores each card's step.
_LADDER_DOCS = {'identity': ['ic'], 'academic': ['results_slip'], 'pathway': ['offer_letter']}


def _genuineness_step(application, doc_types):
    """0 (genuine / not scored), 1 (suspect), or 2 (fake / wrong-type) from the feeding docs'
    fingerprint — by SCORE (``canonical_status`` folds band_for's genuine/suspect/not_<type>)."""
    st = _suspect_genuineness(application, doc_types)
    if not st:
        return 0
    return 2 if st.startswith('not_') else 1


def _genuineness_reason(application, doc_types):
    """The human reason string from the first non-genuine feeding doc (for the ic_low_confidence copy)."""
    for dt in doc_types:
        d = _latest_doc(application, dt)
        vf = d.vision_fields if (d and isinstance(d.vision_fields, dict)) else {}
        auth = vf.get('authenticity') or {}
        if canonical_status(auth.get('status'), getattr(d, 'doc_type', None) or dt) not in ('', 'genuine'):
            return auth.get('reason', '')
    return ''


def _identity_red_chips(application):
    """RED identity content chips — Name and/or NRIC MISMATCH (0–2). Mirrors the name/NRIC reads in
    ``_verdict_identity`` (and the cockpit's identity chips). A missing/unreadable IC is a gap
    pre-empt, not a chip."""
    if _latest_doc(application, 'ic') is None:
        return 0
    blockers = ic_identity_blockers(application)
    return (1 if 'ic_nric_mismatch' in blockers else 0) + \
           (1 if 'ic_name_mismatch' in blockers else 0)


def _academic_red_chips(application):
    """RED academic content chips — Name (slip in a different name), Subjects (a slip subject the
    student never entered), Results (a CONFIRMED typed-vs-slip grade mismatch). 0–3. An uncertain
    grade (band disagreement) and an unread slip are grey/pending, not red."""
    from .academic_engine import compare_academics, read_slip, _slip_name_status
    slip = _latest_doc(application, 'results_slip')
    if slip is None:
        return 0
    n = 1 if _slip_name_status(slip) == 'mismatch' else 0
    data = read_slip(slip)
    if data['names']:
        cmp = compare_academics(getattr(application.profile, 'grades', None), data)
        if cmp['missing']:
            n += 1
        if cmp['mismatched']:
            n += 1
    return n


# A pathway identity chip (Name / IC) is RED when its value MISMATCHES **or** is required-but-missing
# on an extracted offer (owner 2026-07-07: "missing-required on an offer = red"). This mirrors the
# cockpit's own chip tone exactly — `officerCockpit.factStatus` reds 'mismatch' AND 'unreadable' (an
# empty candidate field on an offer that WAS OCR'd), so the verdict band and the visible chips agree.
# 'pending' (not yet extracted) is NOT red — it's a genuine unknown.
_OFFER_CHIP_RED = {'mismatch', 'unreadable'}


def _pathway_effective_step(application):
    """The offer's genuineness step AFTER the reporting-date BONUS (owner 2026-07-08): a VALIDATED
    official registration summons (``offer_reporting_bonus`` — the issuer family's own Malay label +
    the public-issuer signature on the page + no private-company marker) is genuineness evidence and
    lifts the step one band, floored at 0 (suspect→0, fake→1). The bonus is genuineness-only: the
    Name/IC/pathway-mismatch content chips, the Official chip's colour, ``offer_official_status``
    and the Check-2 official-doc request are all UNTOUCHED."""
    from .pathway_engine import offer_reporting_bonus
    step = _genuineness_step(application, ['offer_letter'])
    if step and offer_reporting_bonus(_latest_doc(application, 'offer_letter')):
        step -= 1
    return step


def _pathway_red_chips(application):
    """RED pathway content chips — Name, IC (wrong-person OR the offer doesn't show one) and Pathway.
    0–3. Reads the SAME ``student_offer_check`` the cockpit chips + ``_verdict_pathway`` read.

    The Pathway VARIABLE (owner 2026-07-08, off #131/#84 — refining the locked #31 example) asks
    "does this document establish the declared pathway?" — red when the offer names a genuinely
    DIFFERENT place/field than declared (unreconciled), **or** when the document cannot establish ANY
    pathway because it is not a genuine official offer (suspect / fake / non-official — an interview
    slip, a pemakluman, a private-IPTS letter). This mirrors the cockpit chip exactly
    (officerCockpit ``documentFacts``: notOfficial → Pathway red), so the tile counts precisely the
    chips the reviewer sees. NB it deliberately STACKS with the genuineness step — the owner's
    arithmetic: #31/#131 suspect(−1) + pathway-not-established(−1) = Unsure; #84 fake(−2) +
    pathway(−1) = Fail. 'Official' remains the step's own display chip, never counted here.

    Reporting-date BONUS (owner 2026-07-08): "not official" is judged on the EFFECTIVE step — a
    suspect offer carrying a validated official registration summons (step lifted to 0) DOES
    establish the pathway (the letter provably summons the student to register at a public
    institution), so its Pathway chip is not red. A fake offer stays not-official even with the
    bonus (effective step 1). The mismatch arm is untouched — the bonus never offsets a genuine
    declared-vs-offer clash."""
    from .pathway_engine import student_offer_check
    offer = _latest_doc(application, 'offer_letter')
    if offer is None:
        return 0
    chk = student_offer_check(offer)
    n = (1 if chk['name'] in _OFFER_CHIP_RED else 0) + (1 if chk['ic'] in _OFFER_CHIP_RED else 0)
    not_official = _pathway_effective_step(application) > 0
    if not_official or (chk['pathway'] == 'mismatch' and application.pathway_confirmed_at is None):
        n += 1
    return n


_LADDER_CHIPS = {'identity': _identity_red_chips, 'academic': _academic_red_chips,
                 'pathway': _pathway_red_chips}


def _add_genuineness_caveat(application, fact, docs, step):
    """Surface WHY the genuineness step bit (the 'Official' dimension), decoupled from the content
    chips. Identity → ``ic_low_confidence``; academic → ``document_not_genuine``; pathway → the
    confident ``offer_not_official`` when fake (step 2, an award CONFIDENT_DISQUALIFIER), else the
    softer ``document_not_genuine`` (suspect / cropped)."""
    if step == 0:
        return
    st = _suspect_genuineness(application, docs)
    if fact['fact'] == 'identity':
        code = 'ic_low_confidence'
    elif fact['fact'] == 'pathway' and step == 2:
        code = 'offer_not_official'
    else:
        code = 'document_not_genuine'
    if any(i['code'] == code for i in fact['unresolved']):
        return
    if code == 'ic_low_confidence':
        fact['unresolved'].append(_item('ic_low_confidence', status=st,
                                        reason=_genuineness_reason(application, docs)))
    elif code == 'offer_not_official':
        fact['unresolved'].append(_item('offer_not_official'))
    else:
        fact['unresolved'].append(_item('document_not_genuine', status=st))


def _apply_genuineness_ladder(application, facts):
    """Rebuild the identity/academic/pathway band as ``max(base, genuineness_step + red_chips)``,
    floored at 'gap' (income keeps the flat cap). Downgrade-only: a genuine doc with clean content
    (step 0, 0 chips) leaves the base untouched.

    PATHWAY uses the EFFECTIVE step (raw − the reporting-date bonus) for the BAND, but the RAW step
    for the caveat — so a suspect-with-bonus offer can read Certain while the tile still carries the
    truthful "may not be a genuine original" line (the Official chip stays amber, Check-2 still
    requests the official copy). A ``str_verified``-style evidence line explains the lift."""
    for fact in facts:
        docs = _LADDER_DOCS.get(fact['fact'])
        if not docs:
            continue
        step = _genuineness_step(application, docs)
        band_step = step
        if fact['fact'] == 'pathway':
            band_step = _pathway_effective_step(application)
            if band_step < step:                 # the bonus fired — say why the band lifted
                fact['evidence'].append(_item('offer_reporting_official'))
        chips = _LADDER_CHIPS[fact['fact']](application)
        try:
            base_i = _BAND_LADDER.index(fact['status'])
        except ValueError:
            base_i = 0
        band_i = max(base_i, band_step + chips)
        if band_i == 0 and _genuineness_unscored(application, docs):     # TD-114
            band_i = _UNSCORED_FLOOR
        fact['status'] = _BAND_LADDER[min(band_i, len(_BAND_LADDER) - 1)]
        _add_genuineness_caveat(application, fact, docs, step)
    return facts


# ── TD-114 (2026-10-02): a NEVER-SCORED anchor document holds its fact at Probable ──
# The rule is the owner's approved design for exactly this gap (2026-06-13,
# `docs/scholarship/verification-genuineness-gating-plan.md`, rule 1): "a fact cannot be Certain
# unless a genuineness check actually RAN and passed on its anchor document — not-run → Probable at
# most." It is a FLOOR, never a step: the 2026-07-07 ladder steps by SCORE and an unscored document
# has none, so it is not "suspect" and does not stack with the red chips (one red chip on an
# unscored slip is still Probable, not Unsure). Same shape as the base band's unread→Probable
# under-claim, and as the 2026-07-29 IC-lock ruling: "we could not check" never means "checked".
# Inert while DOC_GENUINENESS_CHECK_ENABLED is off — nothing is scored then, as the design says.
_UNSCORED_FLOOR = _BAND_LADDER.index('review')


def _genuineness_unscored(application, doc_types):
    """True when a feeding anchor document is on file but carries NO genuineness signal."""
    from django.conf import settings
    if not getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False):
        return False
    for dt in doc_types:
        d = _latest_doc(application, dt)
        if d is None:
            continue        # a missing document is the base band's gap, not this rule's
        vf = d.vision_fields if isinstance(d.vision_fields, dict) else {}
        if not canonical_status((vf.get('authenticity') or {}).get('status', ''), dt):
            return True
    return False
