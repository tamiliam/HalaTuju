"""Link an offer-sourced pick to its catalogue course (owner, 2026-11-01).

An offer letter read before the matcher could see the degree catalogue (2026-10-31) left
``chosen_programme`` as LABELS only — the letter's own programme and institution lines, no
``course_id``. The cockpit then shows the course with no link to its page and the institution as
the letter printed it, a hostel line included (#243: "Sarjana Muda Seni Halus (Kepujian)" at "KOLEJ
SEROJA, UNIVERSITI TEKNOLOGI MARA"). The realignment skipped such a pick on purpose: it REPLACES a
student's choice, and a confirmed pick is settled. Linking replaces nothing — the labels already
came off this letter, so the catalogue course they name is the same pick, given its id.

``pinned_course`` is the one test of "this letter names ONE catalogue course at ONE campus, at the
letter's own level". The offer confirm uses it for a labels-only pick (``_settle_stale_course_id``)
and the linker below uses it for the picks already on file (``link_offer_courses``).
"""
import logging

#: THE PACKAGE NAME, written out (see offer_sync): one logger for every services AUDIT line.
logger = logging.getLogger('apps.scholarship.services')

#: The ``source`` values a labels-only pick may carry to be linked: the letter's own reading.
OFFER_SOURCES = ('offer_letter_auto', 'offer_letter_confirmed')


def pinned_course(cp, programme, institution, issuer=''):
    """``cp`` with the catalogue course the letter names — ``course_id``, the catalogue's
    ``course_name``, its campus as ``institution`` (``card_display.with_institution`` keeps the
    ``institution_id`` true) — or None when the letter names no ONE course, cannot pin its campus,
    names a pre-U virtual course, or does not STATE a level that is the course's own
    (``offer_course_match.pinned_match``, the test the realignment shares). Other keys of ``cp``
    (``source`` included) are kept. Read-only."""
    from .. import card_display
    from ..offer_course_match import pinned_match
    reason, match = pinned_match(programme, institution, issuer)
    if reason:
        return None
    out = card_display.with_institution(cp if isinstance(cp, dict) else {}, match['institution'])
    out.update(course_id=match['course_id'], course_name=match['course_name'])
    return out


def labels_describe(stored_name, course_name):
    """Do the stored labels name THIS catalogue course? The matcher's own test, after its own noise
    stripping — so a name copied off an older or different letter is caught (``labels_disagree``)."""
    from ..offer_course_match import _names, letter_programme
    from ..pathway_engine import distinctive_tokens
    return _names(distinctive_tokens(letter_programme(stored_name or '')), course_name or '')


def picker_pathways():
    """Every value the apply form's pathway picker stores. Anything else (blank, ``degree`` written
    by an older offer confirm) is not a picker value, and the payment calendar falls to its default."""
    from apps.courses.views_offerings import SPM_PATHWAYS
    return set(SPM_PATHWAYS) | {'matric', 'stpm'}


def plan_offer_link(application, offer, chk):
    """``(skip_reason, new_chosen_programme, new_pathway)``; ``skip_reason`` '' means link it.

    Checked in this order (each failure is what ``link_offer_courses`` prints):

    ``not_offer_sourced``  the pick is not the letter's own reading (a student's pick, a repair, an
                           interview — never touched) — unless it is EMPTY (no course id, no course
                           name): an empty pick is FILLED from the letter (``fill_empty_pick``, owner
                           2026-11-01), source ``offer_letter_auto``, without the label checks;
    ``has_course_id``      it is already linked;
    ``decided``            the realignment's own test (``querying_locked`` — a submitted interview
                           included; an interview still open is not decided — or a recorded verdict);
    ``not_own_letter``     the letter's name or IC is a mismatch;
    ``not_offer_letter``   the letter is scored a FAKE. Linking replaces no choice, so a genuine score
                           is NOT required — suspect and unscored letters link; a fake never does;
    ``confirmation_letter``  a confirmation of studies (S6, ruling 4) — it may stand in for an offer, never a pick;
    ``pre_u_offer`` / ``pre_u``  a Form 6 / matriculation letter or stored pathway (no course_id shape);
    ``unresolved``         the letter names no ONE catalogue course at one campus, at its own level;
    ``labels_disagree``    the stored labels name another course (labels that name NO course are an
                           empty pick, filled — 2026-11-01);
    ``place_disagrees``    the stored institution label names another place than the matched campus
                           (when it is a hostel line, the letter's issuer must name the campus — the
                           shared ``letter_place``). Round-3 review: labels "Seni Halus" at "UNIVERSITI
                           MALAYA" and a later letter for Seni Halus at UiTM is not the same pick.

    ``new_pathway`` is the course's picker pathway, set only when the stored value is blank or not
    a picker value (``degree``); a picker value is the student's or a confirm's and is kept — UNLESS the
    realignment would take this record too, when the link gives the realignment's own answer, so the
    two never leave a record different by the order they ran in (round-3 review)."""
    from apps.courses import public as courses_public
    from .. import offer_pathway as op
    from ..pathway_engine import is_confirmation_letter, offer_band
    from .querying import querying_locked
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    empty = is_empty_pick(cp)
    if not empty and (cp.get('source') or '') not in OFFER_SOURCES:
        return 'not_offer_sourced', None, ''
    if (cp.get('course_id') or '').strip():
        return 'has_course_id', None, ''
    verdict = application.officer_verdict if isinstance(application.officer_verdict, dict) else {}
    if querying_locked(application) or application.verdict_decided_at or verdict.get('overall'):
        return 'decided', None, ''
    if chk.get('name') == 'mismatch' or chk.get('ic') == 'mismatch':
        return 'not_own_letter', None, ''
    if offer_band(offer) == 'not_offer_letter':
        return 'not_offer_letter', None, ''
    if is_confirmation_letter(offer):          # S6 (ruling 4): it may stand in for an offer, never a pick
        return 'confirmation_letter', None, ''
    if empty and offer_band(offer) != 'genuine':
        # Round-6 review: a fill LOCKS the pick (offer_letter_auto + course_id), so it needs the realign's
        # bar — a suspect letter's course would stand while a later genuine one went to a human question.
        return 'not_genuine', None, ''
    prog, inst = (chk.get('programme') or '').strip(), (chk.get('institution') or '').strip()
    if op.is_pre_u(op.detect_pathway_type(prog, inst)):
        return 'pre_u_offer', None, ''
    pathway = (application.chosen_pathway or '').strip().lower()
    if op.is_pre_u(pathway):
        return 'pre_u', None, ''
    new_cp = pinned_course(cp, prog, inst, (chk.get('issuer') or '').strip())
    if new_cp is None:
        return 'unresolved', None, ''
    if empty:                                         # nothing stored to agree with: the letter's fact
        new_cp['source'] = cp.get('source') if cp.get('source') in OFFER_SOURCES else 'offer_letter_auto'
        # ALWAYS the course's own pathway (round-6 review): an empty pick has no course to protect, and a
        # degree left on `poly` would be paid on the polytechnic calendar.
        return '', new_cp, courses_public.course_pathway_type(new_cp['course_id'])
    if not labels_describe(cp['course_name'], new_cp['course_name']):
        return 'labels_disagree', None, ''
    if not _label_names_campus(cp.get('institution') or '', new_cp, (chk.get('issuer') or '').strip()):
        return 'place_disagrees', None, ''
    return '', new_cp, _link_pathway(application, offer, chk, new_cp, pathway)


def _link_pathway(application, offer, chk, new_cp, pathway):
    """The pathway a link writes: the realignment's own answer when the realignment would take the
    record too (one row whichever runs first), else the course's picker pathway only over a blank or a
    non-picker value (``degree``)."""
    from apps.courses import public as courses_public
    from .offer_sync import plan_bumi_realign
    realign = plan_bumi_realign(application, offer, chk)
    if not realign[0]:
        return realign[2]
    return '' if pathway in picker_pathways() else courses_public.course_pathway_type(new_cp['course_id'])


def is_empty_pick(cp):
    """No course at all — no ``course_id`` and no ``course_name`` (owner, 2026-11-01, #202)."""
    cp = cp if isinstance(cp, dict) else {}
    return not (cp.get('course_id') or '').strip() and not (cp.get('course_name') or '').strip()


def fill_empty_pick(application, offer, chk):
    """Owner, 2026-11-01: *"That's not a decision at check 1. Its role is to get the facts as they
    are. The only restrictions are imposed in the gift rules."* An EMPTY pick has nothing to protect,
    so the offer letter's course is recorded as a fact — no date cut-off, no "may have re-picked", and
    a pre-U college on file (where she studied before) does not block it. Everything else is
    ``plan_offer_link``'s (decided, own letter, a GENUINE letter — a fill locks the pick —, not pre-U, ONE
    course at ONE campus at the letter's level); the course's own pathway is always written, and the
    profile takes it only when its own plan is empty too (round-6 review). Called from ``autofill_pathway_from_offer`` before its mismatch exit, and by
    ``link_offer_courses``. Returns True when it wrote."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    return is_empty_pick(cp) and link_offer_course(application, offer, chk)


def _label_names_campus(label, new_cp, issuer):
    """Does the stored institution label name the matched campus — itself, or as a hostel line whose
    letterhead names it (``letter_place``)? A blank label names nothing."""
    from .. import offer_pathway as op
    from ..offer_course_match import catalogue_index, letter_place
    if not label.strip():
        return False
    rows = op._campus_rows(new_cp['course_id'])
    index = catalogue_index()
    place = letter_place(new_cp['course_id'], label, issuer, rows=rows, index=index)
    campus = (new_cp.get('institution') or '').strip()
    return any(n.strip() == campus and op._refers_to_campus(n, a, place, index) for n, a in rows)


def link_offer_course(application, offer, chk):
    """Apply ``plan_offer_link``; the source is KEPT (a confirmed pick stays confirmed). Refreshes the
    following profile in the same transaction (as the realignment does) and logs an AUDIT line.
    Returns True when it wrote. Idempotent: a linked pick is ``has_course_id``."""
    from django.db import transaction

    from .confirmation import profile_follows, sync_profile_pathway
    reason, new_cp, new_pathway = plan_offer_link(application, offer, chk)
    if reason:
        return False
    old_pathway = application.chosen_pathway or ''
    old_cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    filling = is_empty_pick(old_cp)
    application.chosen_programme = new_cp
    fields = ['chosen_programme']
    if new_pathway and new_pathway != old_pathway.strip().lower():
        application.chosen_pathway = new_pathway
        fields.append('chosen_pathway')
    if application.pathway_certainty != 'sure':        # the place is settled, as the autofill says
        application.pathway_certainty = 'sure'
        fields.append('pathway_certainty')
    profile_note = 'not_following'
    with transaction.atomic():
        application.save(update_fields=fields)
        if profile_follows(application):
            # Round-6 review: a FILL never overwrites a plan the student made on her profile — only an
            # empty profile plan takes the letter's course; a link (labels off a letter) refreshes as before.
            profile = application.profile
            profile.refresh_from_db(fields=['chosen_programme'])
            if filling and not is_empty_pick(profile.chosen_programme):
                profile_note = 'kept_own_plan'
            else:
                sync_profile_pathway(application, may_clear=lambda f: False)
                profile_note = 'refreshed'
    logger.info('AUDIT offer_course_link app_id=%s kind=%s course_id=%s source=%s old_pick=%s old_pathway=%s '
                'new_pathway=%s profile=%s', application.id, 'fill' if filling else 'link', new_cp['course_id'],
                new_cp.get('source') or '-', _pick_text(old_cp), old_pathway or '-',
                application.chosen_pathway or '-', profile_note)
    return True


def _pick_text(cp):
    """The pick an AUDIT line keeps: course_id | course_name | institution, '-' for each blank."""
    cp = cp if isinstance(cp, dict) else {}
    return ' | '.join((str(cp.get(k) or '').strip() or '-') for k in ('course_id', 'course_name', 'institution'))
