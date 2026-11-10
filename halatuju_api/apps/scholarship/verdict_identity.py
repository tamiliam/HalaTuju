"""The IDENTITY fact of the verification verdict (name + NRIC), moved out of ``verdict_engine``.

⚠ WHY THIS IS A MODULE (audit sprint A3.4, 2026-11-10). ``verdict_engine.py`` was on the
oversize ledger at 941 lines; the fact builders are leaving it one per module, as the Academic
fact did for request #62 (``verdict_academic``). The function below is the one that sat there,
moved whole and unchanged; ``verdict_engine._verdict_identity`` is kept as a seam so
``build_verdict`` and every caller and test that names it keep working.
"""
from __future__ import annotations

from .read_errors import ic_second_opinion_deferred
from .services import ic_identity_blockers
from .verdict_engine import _fact, _item, _latest_doc
from .vision import name_match


def _verdict_identity(application):
    """Identity is checkable by matching, so the AI may assert 'verified'. It
    NEVER auto-fails: every mismatch has an innocent cause more likely than
    fraud (OCR truncation, a typo, a missing connector), so the worst the engine
    does is 'review' (confirm) or 'gap' (re-upload an unreadable IC)."""
    evidence, unresolved = [], []
    ic = _latest_doc(application, 'ic')
    if ic is None:
        return _fact('identity', 'gap', evidence, [_item('ic_missing')])

    # Reuse the consent-gate identity logic so the verdict and the consent gate
    # can never disagree. It returns at most: ic_service_down / ic_unreadable /
    # ic_nric_mismatch / ic_name_mismatch (a 'partial' name is NOT a blocker).
    blockers = ic_identity_blockers(application)
    if 'ic_service_down' in blockers:
        # The OCR *service* failed (not a bad image) — confirm later, never fail.
        return _fact('identity', 'review', evidence, [_item('ic_service_down')])
    if 'ic_unreadable' in blockers:
        return _fact('identity', 'gap', evidence, [_item('ic_unreadable')])

    profile = application.profile
    pnric = (getattr(profile, 'nric', '') or '').strip()
    pname = (getattr(profile, 'name', '') or '').strip()

    # NRIC — the hard identity key.
    if 'ic_nric_mismatch' in blockers:
        unresolved.append(_item('nric_mismatch',
                                ocr_nric=ic.vision_nric, profile_nric=pnric))
    elif ic.vision_nric and pnric:
        evidence.append(_item('nric_match', nric=pnric))

    # Name — disjoint tokens raise a flag; a subset (OCR truncation) is RESOLVED
    # silently because the NRIC already anchors identity.
    if ic.vision_name and pname:
        verdict = name_match(ic.vision_name, pname)
        if verdict == 'match':
            evidence.append(_item('name_match', name=pname))
        elif verdict == 'partial':
            evidence.append(_item('name_resolved_truncation',
                                  ocr_name=ic.vision_name, profile_name=pname))
        elif ic_second_opinion_deferred(ic):   # TD-390: half a read is no name mismatch — no ask
            unresolved.append(_item('ic_service_down'))
        else:  # 'mismatch'
            unresolved.append(_item('name_mismatch',
                                    ocr_name=ic.vision_name, profile_name=pname))

    # NOTE: the IC's registered-address state is deliberately NOT an identity caveat.
    # A MyKad carries the *least-current* address on file (people relocate; the IC is
    # not reissued — fresher addresses come from the offer letter / bills / STR) and it
    # is not an identity key: name + NRIC are. A state divergence therefore stays a
    # pre-interview flag ("ask which is current" — `_detect_address_state_mismatch` in
    # anomaly_engine), NOT a verdict downgrade. So identity reads green when name + NRIC
    # match, consistent with the Documents panel and the student's own identity card.

    # NB the IC genuineness fingerprint is applied AFTER this by the genuineness LADDER
    # (_apply_genuineness_ladder): the band is rebuilt as max(this base, genuineness_step + red chips),
    # where the red chips are the Name/NRIC mismatches emitted here (counted by _identity_red_chips) and
    # the step is the IC fingerprint (suspect −1 / not_ic −2). This function returns the CONTENT base
    # (verified when clean, review when a value mismatches or a sub-read is pending).
    return _fact('identity', 'verified' if not unresolved else 'review',
                 evidence, unresolved)
