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
                           interview — never touched);
    ``has_course_id``      it is already linked;
    ``decided``            the realignment's own test (``querying_locked`` — a submitted interview
                           included; an interview still open is not decided — or a recorded verdict);
    ``not_own_letter``     the letter's name or IC is a mismatch;
    ``not_offer_letter``   the letter is scored a FAKE. Linking replaces no choice, so a genuine score
                           is NOT required — suspect and unscored letters link; a fake never does;
    ``pre_u_offer`` / ``pre_u``  a Form 6 / matriculation letter or stored pathway (no course_id shape);
    ``unresolved``         the letter names no ONE catalogue course at one campus, at its own level;
    ``no_course_name`` / ``labels_disagree``  the stored labels name nothing, or another course;
    ``place_disagrees``    the stored institution label names another place than the matched campus
                           (when it is a hostel line, the letter's issuer must name the campus — the
                           shared ``letter_place``). Round-3 review: labels "Seni Halus" at "UNIVERSITI
                           MALAYA" and a later letter for Seni Halus at UiTM is not the same pick.

    ``new_pathway`` is the course's picker pathway, set only when the stored value is blank or not
    a picker value (``degree``); a picker value is the student's or a confirm's and is kept — UNLESS the
    realignment would take this record too, when the link gives the realignment's own answer, so the
    two never leave a record different by the order they ran in (round-3 review)."""
    from apps.courses.course_pathway import course_pathway_type
    from .. import offer_pathway as op
    from ..pathway_engine import offer_band
    from .querying import querying_locked
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    if (cp.get('source') or '') not in OFFER_SOURCES:
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
    prog, inst = (chk.get('programme') or '').strip(), (chk.get('institution') or '').strip()
    if op.is_pre_u(op.detect_pathway_type(prog, inst)):
        return 'pre_u_offer', None, ''
    pathway = (application.chosen_pathway or '').strip().lower()
    if op.is_pre_u(pathway):
        return 'pre_u', None, ''
    new_cp = pinned_course(cp, prog, inst, (chk.get('issuer') or '').strip())
    if new_cp is None:
        return 'unresolved', None, ''
    if not (cp.get('course_name') or '').strip():
        return 'no_course_name', None, ''
    if not labels_describe(cp['course_name'], new_cp['course_name']):
        return 'labels_disagree', None, ''
    if not _label_names_campus(cp.get('institution') or '', new_cp, (chk.get('issuer') or '').strip()):
        return 'place_disagrees', None, ''
    from .offer_sync import plan_bumi_realign
    realign = plan_bumi_realign(application, offer, chk)
    if not realign[0]:
        return '', new_cp, realign[2]                  # the realignment's own pathway answer
    new_pathway = '' if pathway in picker_pathways() else course_pathway_type(new_cp['course_id'])
    return '', new_cp, new_pathway


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
    application.chosen_programme = new_cp
    fields = ['chosen_programme']
    if new_pathway and new_pathway != old_pathway.strip().lower():
        application.chosen_pathway = new_pathway
        fields.append('chosen_pathway')
    if application.pathway_certainty != 'sure':        # the place is settled, as the autofill says
        application.pathway_certainty = 'sure'
        fields.append('pathway_certainty')
    with transaction.atomic():
        application.save(update_fields=fields)
        if profile_follows(application):
            sync_profile_pathway(application, may_clear=lambda f: False)
    logger.info('AUDIT offer_course_link app_id=%s course_id=%s source=%s old_pathway=%s new_pathway=%s',
                application.id, new_cp['course_id'], new_cp.get('source') or '-', old_pathway or '-',
                application.chosen_pathway or '-')
    return True
