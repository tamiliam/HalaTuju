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
#: HalaTuju does not support study abroad ("Program Persediaan ... Luar Negara", run by MARA, JPA or
#: another sponsor: the name alone decides, never the sponsor). The ADP
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


def _own_pick(application):
    """The degree the student picked HERSELF — ``chosen_programme`` with a course id or a course name,
    any source but the offer's autofill (``offer_letter_auto``); else {}."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    named = (cp.get('course_id') or '').strip() or (cp.get('course_name') or '').strip()
    return cp if named and cp.get('source') != 'offer_letter_auto' else {}


def _top_choices(application):
    """The degrees a waiting student named (``top_choices``, up to three), each a dict with a course."""
    tc = application.top_choices if isinstance(application.top_choices, list) else []
    return [c for c in tc if isinstance(c, dict)
            and ((c.get('course_id') or '').strip() or (c.get('course_name') or '').strip())]


def _tertiary(application):
    """She holds STPM / matriculation / asasi / diploma results (``results_route.held_kind``)."""
    from .results_route import held_kind
    return bool(held_kind(application))


def declared_degree(application):
    """Owner 2026-11-18 (R8): what a TERTIARY student declared, for the no-offer cockpit line — her own
    pick as "course — institution", else her named degrees joined by "; ". '' for anyone else."""
    if not _tertiary(application):
        return ''

    def label(d):
        name = (d.get('course_name') or d.get('course_id') or '').strip()
        inst = (d.get('institution') or '').strip()
        return f'{name} — {inst}' if name and inst else name or inst
    pick = _own_pick(application)
    return label(pick) if pick else '; '.join(filter(None, (label(c) for c in _top_choices(application))))


def _letter_course(chk, prog, inst):
    """The ONE catalogue course the letter pins at ONE campus at its own stated level — the linker's own
    test (``offer_link.pinned_course``, which ``plan_offer_link`` and the realignment share), else None."""
    from .services import offer_link
    return offer_link.pinned_course({}, prog, inst, chk.get('issuer') or '')


def _linked_course(application, offer, chk, prog, inst):
    """R4 / R5's clean match (review 2026-11-18): the course the linker WILL write for this letter
    (``plan_offer_link`` — an empty pick needs a GENUINE letter), or the one it already wrote from this
    letter; else None, and she is asked to pick (R6). A loose name match that nothing links is not clean."""
    from .services import offer_link
    reason, new_cp, _ = offer_link.plan_offer_link(application, offer, chk)
    if not reason:
        return new_cp
    if reason == 'has_course_id':
        cp, match = application.chosen_programme, _letter_course(chk, prog, inst)
        return match if match and match['course_id'] == (cp.get('course_id') or '').strip() else None
    return None


def _same_course(application, clean):
    """R2 (owner 2026-11-18): her own pick IS the course the letter cleanly names — by course id, or
    for a name-only pick by the matcher's own name test — so a word clash elsewhere asks nothing."""
    pick = _own_pick(application)
    if not pick:
        return False
    match = clean('pinned')
    if not match:
        return False
    cid = (pick.get('course_id') or '').strip()
    if cid:
        return cid == match['course_id']
    from .pathway_match import _field_status
    from .services.offer_link import labels_describe
    return (labels_describe(pick.get('course_name') or '', match['course_name'])
            and _field_status(pick.get('institution') or '', match.get('institution') or '') != 'clash')


def _course_ask(application, chk, prog, inst, offer_type, clean, pismp_extra):
    """The ask for a student with no pick of her own (owner 2026-11-18): the one-tap confirm for a
    unique-bidang PISMP letter (as before, checked first); none when the linker links the letter's ONE
    catalogue course (R4, R5); the one-tap confirm for a pre-U letter whose stream parses (as before);
    else pick your course (R6)."""
    from . import offer_pathway as _op
    pismp_unique = offer_type == 'pismp' and bool(_op.resolve_pismp_course((chk.get('bidang') or '').strip()))
    if not pismp_unique and clean('linked'):
        return None
    pre_u_parsed = _op.is_pre_u(offer_type) and _op.offer_is_resolvable(prog, inst, chk.get('issuer') or '')
    extra = pismp_extra() if offer_type == 'pismp' else {}
    if pre_u_parsed or pismp_unique:
        return _item('pathway_confirm', programme=prog, institution=inst,
                     declared_programme='', declared_institution='', **extra)
    return _item('pathway_undeclared', programme=prog, institution=inst, **extra)


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
    #   Case 1 — the student declared NOTHING (#127), or is a tertiary student with no pick of her own
    #     (owner 2026-11-18): a unique-bidang PISMP letter → one-tap confirm; a letter whose ONE catalogue
    #     course the linker writes (plan_offer_link: one campus, its own level, a genuine letter for an
    #     empty pick) → no ask; a pre-U letter whose stream parses → one-tap confirm; anything else →
    #     pick your course on the profile (pathway_undeclared).
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

        # The CLEAN match (owner 2026-11-18; review): 'pinned' = the letter pins ONE catalogue course at
        # its own level (R2); 'linked' = the linker writes, or wrote, that course for her (R4 / R5).
        # Never for a pre-U letter (no course id). Each read once, lazily.
        _clean = {}

        def clean(kind):
            if kind not in _clean:
                _clean[kind] = None if _op.is_pre_u(offer_type) else (
                    _letter_course(chk, prog, inst) if kind == 'pinned'
                    else _linked_course(application, offer, chk, prog, inst))
            return _clean[kind]

        # A TERTIARY student with no degree pick of her own (nothing, or only her named top choices)
        # is never asked "is this where you're going?" against her old pre-U school (R5); a clean
        # letter settles it, else she picks her course (R4 / R6). Her named degrees ARE a declaration
        # (R1): she is never told she chose nothing.
        tertiary_open = _tertiary(application) and not _own_pick(application)
        dfam, ofam = _op.pathway_family(declared_type), _op.pathway_family(offer_type)
        if dfam and ofam and dfam != ofam:
            sw = {'programme': prog, 'institution': inst,
                  'declared_pathway': declared_type, 'offer_pathway': offer_type}
            if offer_type == 'pismp':
                sw.update(_pismp_extra())
            unresolved.append(_item('pathway_type_switch', **sw))
        elif chk['pathway'] == 'mismatch' and not confirmed and not tertiary_open \
                and not _same_course(application, clean):
            unresolved.append(_item('pathway_confirm', programme=prog, institution=inst,
                                    declared_programme=chk['declared_programme'],
                                    declared_institution=chk['declared_institution']))
        elif not confirmed and (prog or inst) and (tertiary_open or _no_declared_pathway(application)):
            ask = _course_ask(application, chk, prog, inst, offer_type, clean, _pismp_extra)
            if ask:
                unresolved.append(ask)

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
