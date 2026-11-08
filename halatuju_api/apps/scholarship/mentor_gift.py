"""Which gifts a mentor mentors in — Invitations I4 (2026-11-08; owner ruling 2, open points C and D).

⚠ THE GIFTS LIVE IN `MentorGift` ROWS (`mentor_gifts`), AND NO ROWS MEANS EVERY GIFT — including a gift
started later (open point C: the reviewer rule, `courses.staff_gift`, exactly). The mentors who existed
before I4 have no rows, so nothing changed for them until someone ticks.

⚠ A GIFT LIMITS WHO THE MENTOR MENTORS. `allows` is the ONE rule: `mentoring.refusal_for_mentor` asks it
(so `mentoring.assign` refuses `mentor_not_in_gift`, before the lock and again under it) and
`mentoring.assignable_mentors` applies it to the picker (`allowed_ids`, one query for the whole roster).
A scholar's gift is `services.assignment.case_gifts` — the application's own gift and its intake year's
gift, the reviewer's own answer; a scholar whose gift is not known is not refused (the reviewer rule).

⚠ NARROWING NEVER ENDS AN ASSIGNMENT (open point D). `set_gifts` refuses `mentor_has_scholars_outside`,
with how many, when an OPEN assignment's scholar would fall outside the new gifts. An ended assignment
never blocks. The count and the write happen under the MENTOR row's lock — the one `mentoring.assign`
takes before it judges the mentor again — so an assign racing an edit cannot slip a scholar past it.

⚠ EVERY GIFT IS THE MENTOR'S OWN ORGANISATION'S: rows are written ONLY by `set_gifts`, and only with
gifts `choose` found inside that organisation (another organisation's id is a 404, never a 403 — it
would confirm that tenant's gift exists). An INVITE may name only ACTIVE gifts (the ones the form
offers); an EDIT may name any of the organisation's gifts, ended ones too, as the reviewer's edit may.
"""
from django.db import transaction

from apps.courses.staff_gift import _gift_refusal, _not_found, resolve_gifts

from .models import Mentor, MentorAssignment, MentorGift
from .services.assignment import case_gifts

OUTSIDE = 'mentor_has_scholars_outside'


def choose(raw, organisation, *, active_only, required=False):
    """``(gifts, refusal Response | None)`` for a mentor's ``programme_ids``; ``[]`` = every gift.

    Absent (``None``) is every gift on an invite (its own default); an EDIT passes ``required`` and is
    refused instead. Not a list -> 400 `gift_required`; an id that is unknown, another organisation's or
    (``active_only``, the invite) a gift that has ended -> 404 `not_found` — one answer, so nothing about
    another tenant leaks."""
    if raw is None and not required:
        return [], None
    gifts, refusal = resolve_gifts(raw, organisation.pk if organisation is not None else None)
    if refusal is not None:
        return None, refusal
    if active_only and any(not g.is_active for g in gifts):
        return None, _not_found()
    return gifts, None


def gift_ids(mentor):
    """``frozenset`` of the mentor's gift ids; EMPTY means every gift. One query."""
    return frozenset(MentorGift.objects.filter(mentor=mentor).values_list('programme_id', flat=True))


def _meets(ids, application):
    """The rule itself: every gift (no ids), or a scholar whose gift is unknown, or the two meet."""
    if not ids:
        return True
    case = case_gifts(application)
    return not case or bool(case & ids)


def allows(mentor, application):
    """May ``mentor`` be assigned ``application`` by gift? See the module docstring."""
    return _meets(gift_ids(mentor), application)


def allowed_ids(mentor_ids, application):
    """The ids among ``mentor_ids`` whose gifts allow ``application`` — ONE query for the roster."""
    by_mentor = {}
    for mentor_id, programme_id in (MentorGift.objects.filter(mentor_id__in=list(mentor_ids))
                                    .values_list('mentor_id', 'programme_id')):
        by_mentor.setdefault(mentor_id, set()).add(programme_id)
    return {pk for pk in mentor_ids if _meets(frozenset(by_mentor.get(pk, ())), application)}


def gifts_by_mentor(mentor_ids):
    """``{mentor_id: [{id, code, name}, ...]}`` ordered by code — ONE query for a list's rows. A mentor
    with no entry has every gift."""
    out = {}
    for row in (MentorGift.objects.filter(mentor_id__in=list(mentor_ids)).select_related('programme')
                .order_by('programme__code')):
        p = row.programme
        out.setdefault(row.mentor_id, []).append({'id': p.pk, 'code': p.code, 'name': p.name_en or p.code})
    return out


def choices(organisation_id):
    """The gifts a mentor of ``organisation_id`` may be given, for the details box's tick list: every gift
    of that organisation, ended ones marked (`is_active`), ordered by code. Never another organisation's."""
    from .models import Programme
    return [{'id': p.pk, 'code': p.code, 'name': p.name_en or p.code, 'is_active': p.is_active}
            for p in Programme.objects.filter(organisation_id=organisation_id).order_by('code')]


def outside_count(mentor, ids):
    """How many of ``mentor``'s OPEN assignments a scholar outside gift ids ``ids`` holds (0 when
    ``ids`` is empty: every gift holds everybody)."""
    if not ids:
        return 0
    rows = (MentorAssignment.objects.filter(mentor=mentor, ended_at__isnull=True)
            .select_related('application__cohort'))
    return sum(1 for row in rows if not _meets(ids, row.application))


def set_gifts(mentor, gifts, *, check_open=True):
    """THE ONE WRITER of ``mentor``'s gift rows: afterwards they are exactly ``gifts`` (``[]`` = every
    gift), or nothing is written and the answer is ``(OUTSIDE, n)``. ``(None, 0)`` when written.

    The caller has already resolved ``gifts`` inside the mentor's organisation (`choose`).
    ``check_open=False`` only for a mentor who CANNOT hold an open assignment (just created)."""
    wanted = frozenset(g.pk for g in gifts)
    with transaction.atomic():
        if check_open:
            # Lock the MENTOR row — the lock `mentoring.assign` takes before it re-asks `allows` — so an
            # assign cannot add a scholar between this count and the write, nor judge the old gifts.
            list(Mentor.objects.select_for_update().filter(pk=mentor.pk).values_list('pk', flat=True))
            n = outside_count(mentor, wanted)
            if n:
                return OUTSIDE, n
        MentorGift.objects.filter(mentor=mentor).exclude(programme_id__in=wanted).delete()
        MentorGift.objects.bulk_create([MentorGift(mentor=mentor, programme_id=pk) for pk in sorted(wanted)],
                                       ignore_conflicts=True)
    return None, 0


def outside_refusal(n):
    """The 409 for open point D, naming how many scholars stand outside the new gifts."""
    response = _gift_refusal(OUTSIDE, 409, f'This mentor has {n} current scholar(s) outside those gifts. '
                                           'End or change those mentoring first.')
    response.data['count'] = n
    return response
