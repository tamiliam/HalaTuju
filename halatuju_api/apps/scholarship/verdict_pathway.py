"""The PATHWAY fact's offer-letter reading, moved out of ``verdict_engine._verdict_pathway``.

⚠ WHY THIS IS A MODULE (audit sprint A3.4, 2026-11-10). ``verdict_engine.py`` was on the
oversize ledger at 941 lines. Everything ``_verdict_pathway`` did once an offer letter IS on file —
the identity chips on the letter, the under-read cases, the pathway hearing and the base band —
moved here whole, in the same order, with ``_no_declared_pathway`` (its only caller is here).

⚠ THE NO-OFFER BRANCH STAYED IN ``verdict_engine``, deliberately. Its ``pathway_declared`` line
carries a ``# SOFT`` marker that the web's ``soft-evidence-drift.test.ts`` reads out of
``verdict_engine.py`` itself; moving it would silently drop a marker the mirror counts.

Every collaborator a test patches at its source (``pathway_engine.student_offer_check``,
``offer_pathway.*``) is still imported INSIDE the function, exactly as it was.
"""
from __future__ import annotations

import re

from .genuineness.bands import NOT_CHECKED, stored_status
from .genuineness.offer_issuers import not_checked_issuer
from .read_errors import read_deferred
from .verdict_engine import _fact, _item


#: TD-617 (owner 2026-11-14, option 1): the American Degree Program under MARA is fully funded, and
#: HalaTuju does not support study abroad (MARA's "Program Persediaan ... Luar Negara"). The ADP
#: spelling is `results_route._NOT_ASKED_NAME`'s: never "American Degree Transfer Program", never a
#: plain "Degree Programme".
_FUNDED_OR_ABROAD = re.compile(r'american\s+degree\s+program(?:me)?s?\b|persediaan\b.*\bluar\s+negara\b',
                               re.IGNORECASE)


def funded_or_abroad(application, fact):
    """The pathway fact, RED ('gap') with `pathway_funded_or_abroad` named when the chosen programme's
    name is one of `_FUNDED_OR_ABROAD` (an award CONFIDENT_DISQUALIFIER: the cockpit flag shows). The
    reviewer still decides; the award amount is untouched (a pure function of the pathway)."""
    prog = getattr(application, 'chosen_programme', None)
    name = (prog.get('course_name') or '') if isinstance(prog, dict) else ''
    if _FUNDED_OR_ABROAD.search(name):
        fact['status'] = 'gap'
        fact['unresolved'].append(_item('pathway_funded_or_abroad', programme=name))
    return fact


def _no_declared_pathway(application):
    """True when the student declared NOTHING about a pathway — no chosen/intended pathway type, no
    pre-U track, and no SPECIFIC chosen programme (a value autofilled FROM the offer, source
    'offer_letter_auto', does NOT count as a declaration). This is the #127 all-blank case that the
    'confirm or complete your pathway' flow targets; a type-only or specific declaration is left as
    the offer settling it (owner 2026-07-15)."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    real_pick = bool(cp.get('course_id')) and cp.get('source') != 'offer_letter_auto'
    return not (
        (application.chosen_pathway or '').strip()
        or (application.intended_pathway or '').strip()
        or (application.pre_u_track or '').strip()
        or real_pick)


def offer_pathway_fact(application, offer):
    """The pathway fact when an offer letter is on file (``offer`` is the latest live one).
    The body that followed the no-offer branch of ``verdict_engine._verdict_pathway``, unchanged."""
    from .pathway_engine import student_offer_check
    evidence, unresolved = [], []
    chk = student_offer_check(offer)
    # Identity on the letter: a wrong name OR IC is a RED chip the ladder counts (owner 2026-07-07), not an
    # early return — one slip → −1, both → −2, stacking with the genuineness step (#12 → Fail). Amber, no
    # block (decisions.md 2026-07-04: usually a family upload slip-up). The three chips are independent.
    if chk['ic'] == 'mismatch' or chk['name'] == 'mismatch':
        unresolved.append(_item('offer_name_mismatch'))
    # A general NOTICE / wrong document (body read fine — issuer/programme present — but no name or
    # IC, e.g. a "your offer will be released later" memo) vs a genuinely blurry scan → grey/pending
    # (an under-read, capped at Probable), NOT a red chip. Only when identity didn't already flag.
    elif chk['name'] in ('unreadable', 'pending') and chk['ic'] in ('unreadable', 'pending'):
        if read_deferred(offer.vision_fields):   # not read yet / our outage: no claim, no ask (2026-10-24)
            return _fact('pathway', 'review', evidence, [_item('offer_not_read_yet')])  # TD-396: officer-only
        if chk['programme'] or chk['institution']:
            return _fact('pathway', 'review', evidence, [_item('offer_no_identity')])
        return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])

    prog, inst = chk['programme'], chk['institution']
    if stored_status(offer.vision_fields) == NOT_CHECKED:   # C1: officer-only, see `offer_issuers`
        unresolved.append(_item('offer_issuer_not_checked', issuer=not_checked_issuer(offer.vision_fields)))
    confirmed = application.pathway_confirmed_at is not None
    if confirmed:
        evidence.append(_item('pathway_confirmed', programme=prog, institution=inst))
    elif prog or inst:
        evidence.append(_item('offer_programme', institution=inst, programme=prog))

    # ── The pathway HEARING — ONE band-aware, mutually-exclusive detector (owner 2026-07-18) ──────
    # A "which pathway?" hearing fires only for a SCORED, non-fake offer — genuine OR suspect
    # (offer_hearing_ok). A FAKE (not_offer_letter) or UNSCORED offer never gets one: fake is flagged
    # + submission-blocked elsewhere, and we don't ask about an offer whose genuineness isn't scored.
    # Then AT MOST ONE of three cases (if/elif → the type switch suppresses the generic confirm):
    #   Case 2 — the offer is a different pathway FAMILY than declared (STPM→PISMP/Matric, #43):
    #     ask to confirm the SWITCH. Fires regardless of pathway_confirmed_at (the prior offer-confirm
    #     wrote chosen_programme but never chosen_pathway); on Yes confirm_pathway adopts the new type
    #     + drops the stale pre-U stream. A PISMP switch carries an aliran picker default (the letter
    #     never states SK/SJKT/SJKC), inferred from the student's SPM vernacular subject.
    #   Case 3 — SAME family but the institution/stream CLASHES (the #117 within-type case): the
    #     generic "is this where you're going?" confirm. Not re-asked once confirmed (minor drift).
    #   Case 1 — the student declared NOTHING (#127): resolvable → one-tap confirm; ambiguous (a PISMP
    #     offer with no aliran) → the profile Aliran/Bidang picker (pathway_undeclared).
    from . import offer_pathway as _op
    from .pathway_engine import offer_hearing_ok
    if offer_hearing_ok(offer):
        declared_type = (application.chosen_pathway or '').strip().lower()
        offer_type = _op.detect_pathway_type(prog, inst)
        profile = getattr(application, 'profile', None)

        # PISMP extras (owner 2026-07-18): the letter states the BIDANG (major) but NOT the aliran.
        # Carry the bidang; when it pins a UNIQUE catalogue course (a vernacular bidang — Bahasa Tamil
        # → SJKT) carry that course so the confirm NAMES + pins it directly (no picker); else carry the
        # inferred aliran default for the scoped picker. Reliable-datum-first: never trust the
        # Gemini-inferred aliran to pin a course.
        def _pismp_extra():
            bidang = (chk.get('bidang') or '').strip()
            extra = {'bidang': bidang}
            resolved = _op.resolve_pismp_course(bidang) if bidang else None
            if resolved:
                extra.update({'course_id': resolved['course_id'], 'course_name': resolved['course_name'],
                              'aliran': resolved['aliran']})
            else:
                extra['aliran_hint'] = _op.infer_pismp_aliran(profile)
            return extra

        dfam, ofam = _op.pathway_family(declared_type), _op.pathway_family(offer_type)
        if dfam and ofam and dfam != ofam:
            sw = {'programme': prog, 'institution': inst,
                  'declared_pathway': declared_type, 'offer_pathway': offer_type}
            if offer_type == 'pismp':
                sw.update(_pismp_extra())
            unresolved.append(_item('pathway_type_switch', **sw))
        elif chk['pathway'] == 'mismatch' and not confirmed:
            unresolved.append(_item('pathway_confirm', programme=prog, institution=inst,
                                    declared_programme=chk['declared_programme'],
                                    declared_institution=chk['declared_institution']))
        elif not confirmed and (prog or inst) and _no_declared_pathway(application):
            # A unique-bidang PISMP offer is now RESOLVABLE (one-tap confirm + pin), like a pre-U/tertiary
            # offer; a multi-aliran bidang still needs the profile picker.
            pismp_unique = offer_type == 'pismp' and bool(
                _op.resolve_pismp_course((chk.get('bidang') or '').strip()))
            if _op.offer_is_resolvable(prog, inst, chk.get('issuer') or '') or pismp_unique:
                cp = {'programme': prog, 'institution': inst,
                      'declared_programme': '', 'declared_institution': ''}
                if offer_type == 'pismp':
                    cp.update(_pismp_extra())
                unresolved.append(_item('pathway_confirm', **cp))
            else:
                ud = {'programme': prog, 'institution': inst}
                if offer_type == 'pismp':
                    ud.update(_pismp_extra())
                unresolved.append(_item('pathway_undeclared', **ud))

    # NB the course-SWITCH note is deliberately NOT a verdict item here (owner 2026-07-10): a PUBLIC
    # switch is acceptable — a student may legitimately move STPM → matriculation → a UA diploma — so
    # it must NOT downgrade the pathway band. It is surfaced separately as an always-visible cockpit
    # banner + the offer's "Switched" chip (both from `offer_pathway_switch` / `pathway_check`), which
    # inform the reviewer without penalising. A switch INTO a private/IPTS arm is red on its own via
    # the genuineness veto, not via the switch.

    # Base band (the ladder then applies the genuineness step + red-chip deductions): a clean letter
    # with a readable programme (or an already-confirmed pathway) settles it → verified; any red chip
    # or an unread programme is an under-claim → review.
    if not unresolved:
        if prog or inst or confirmed:
            return _fact('pathway', 'verified', evidence, unresolved)
        return _fact('pathway', 'review', evidence, [_item('offer_unreadable')])
    return _fact('pathway', 'review', evidence, unresolved)
