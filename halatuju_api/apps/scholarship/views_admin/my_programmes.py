"""The Programmes LANDING read (Team tables T5c P5 S1, 2026-11-04; owner rulings in RUN_STATE.md "T5c P5").

`GET admin/scholarship/my-programmes/` → `{'every_gift': bool, 'programmes': [row, ...]}`, rows by code.

WHO SEES WHICH GIFTS (owner, 2026-11-04: "a reviewer's or mentor's list shows ONLY the programmes where
they have work"):

- EVERY GIFT of the caller's organisation (`sees_every_gift`): a person at the Admins table
  (`staff_tables.in_admins` — super, org admin, admin, finance, a team member holding an admin key) or one
  whose Applications scope is 'all' (`see_all` / `qc`). Nothing new: `admin/scholarship/scopes/` already
  serves every one of them every gift's name, and the Overview opens for every gift to each of them.
- OTHERWISE ONLY GIFTS WITH WORK: a gift holding a case ASSIGNED to the caller, open or done (lead ruling:
  "work" = all assigned cases), and a gift holding a student they mentor NOW (`mentor_desk.current_assignments`).
  A person who is both sees the union. Archived gifts are listed only when they hold such work.
- Nobody else: a referral `partner` (and a stopped mentor holding no staff seat) is 403; a source user and an
  inactive row are refused at sign-in (`get_admin`).

WHAT A ROW CARRIES — a key is ABSENT, never zeroed, when the caller may not read it:

- always: `id, code, name_en, name_ms, name_ta, is_active, lifecycle, archived, opens`;
- `intake_years, applications, awarded` (today's card counts, `_programme_row`'s own readers) only for an
  Applications scope of 'all' — finance gets the list without them (it never reads application counts);
- `cases` ("Cases assigned to you") for a person at the Reviewers table;
- `scholars` ("Scholars you mentor") for a person mentoring now;
- `opens`: 'overview' when the caller sees every gift or holds a case here; 'my_students' for a
  mentoring-only gift (owner option 1: the mentor card opens My students, not the Overview).

THE OVERVIEW 404 (lead ruling): a caller who does NOT see every gift, opening the Programme Overview of a
gift where they hold no assigned case, gets 404 — `may_open_overview`, asked by `overview.py`.

tenancy: org-fenced — the gifts through `_fenced_programmes` (super: all; else the caller's own
organisation; no organisation: none), the cases on `owning_organisation_id`, the mentored students through
`mentor_desk.current_assignments` (the mentor's own organisation). Classified in test_org_fence.py.
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from apps.courses import staff_tables

from .. import mentor_desk
from ..closure import ever_awarded_q
from ..models import Programme, ScholarshipApplication, ScholarshipCohort
from .base import _AdminBase
from .gifts import programme_lifecycle


def sees_every_gift(admin, b40_scope):
    """The Admins table, or an Applications scope of 'all' (`_AdminBase._b40_scope`)."""
    return b40_scope == 'all' or staff_tables.in_admins(admin)


def lands(admin, b40_scope):
    """Who opens the Overview landing at all — this read and its pending cards (`my_pending`, T5c P5b):
    a person who sees every gift, sits at the Reviewers table, or mentors now. Nobody else (403)."""
    return (sees_every_gift(admin, b40_scope) or staff_tables.in_reviewers(admin)
            or mentor_desk.mentor_of(admin) is not None)


def _fenced_programmes(admin, organisation_id=None):
    """Every gift inside the caller's fence (inactive ones included, as on the gift cards).
    `organisation_id` fences to that organisation instead (a mentor's own, `current_assignments`)."""
    qs = Programme.objects.all()
    if organisation_id is not None:
        return qs.filter(organisation_id=organisation_id)
    if admin.is_super:
        return qs
    org_id = admin.owning_organisation_id
    return qs.filter(organisation_id=org_id) if org_id else qs.none()


def _assigned(admin):
    """The caller's assigned cases, open or done, inside their organisation (a super: every one)."""
    # org-fence: the caller's own `owning_organisation_id` (a NULL one reads only NULL-org files, the
    # `_org_scoped` degenerate bucket); a super is global, as on every B40 list.
    qs = ScholarshipApplication.objects.filter(assigned_to=admin)
    return qs if admin.is_super else qs.filter(owning_organisation_id=admin.owning_organisation_id)


_gifts_of = mentor_desk.gifts_of_file


def cases_by_gift(admin):
    counts = {}
    for pid, cpid in _assigned(admin).values_list('programme_id', 'cohort__programme_id'):
        for gift in _gifts_of(pid, cpid):
            counts[gift] = counts.get(gift, 0) + 1
    return counts


def scholars_by_gift(admin):
    """Current mentees per gift. The cohort's gift rides on the assignments' own query
    (`current_assignments` selects `application__cohort`), so a mentee costs no query of its own."""
    counts = {}
    for a in mentor_desk.current_assignments(admin):
        for gift in mentor_desk.gifts_of(a.application):
            counts[gift] = counts.get(gift, 0) + 1
    return counts


def has_review_work(admin, programme_id):
    """Does the caller hold any case of this gift assigned to them, open or done?"""
    return _assigned(admin).filter(Q(programme_id=programme_id) | Q(cohort__programme_id=programme_id)).exists()


def may_open_overview(admin, b40_scope, programme, cohort=None):
    """The Overview's 404 rule: a narrowed caller opens a named gift's Overview only where they have work.

    S1b (review item 1): a named ROUND with no gift named is judged by the round's own gift — the
    `?intake=` door must not open a gift the `?programme=` door refuses. A round that belongs to no gift
    opens only where a case of THAT round is assigned to the caller. Nothing named: the pooled Overview,
    shaped by role (`SECTIONS_BY_ROLE`), as before."""
    if sees_every_gift(admin, b40_scope):
        return True
    if programme is not None:
        return has_review_work(admin, programme.pk)
    if cohort is None:
        return True
    if cohort.programme_id is not None:
        return has_review_work(admin, cohort.programme_id)
    return _assigned(admin).filter(cohort=cohort).exists()


def _counts_by_gift(programme_ids):
    """`{gift id: {intake_years, applications, awarded}}` for every gift in `programme_ids`, in TWO
    queries whatever the number of gifts (S1b review item 2; it was three per gift). Same answers as
    `programme_student_queryset(p)` (column OR cohort, each file once per gift) and `ever_awarded_q`."""
    from django.db.models import BooleanField, Count, ExpressionWrapper
    counts = {pid: {'intake_years': 0, 'applications': 0, 'awarded': 0} for pid in programme_ids}
    if not counts:
        return counts
    for pid, n in (ScholarshipCohort.objects.filter(programme_id__in=counts).values('programme_id')
                   .annotate(n=Count('id')).values_list('programme_id', 'n')):
        counts[pid]['intake_years'] = n
    # org-fence: every id came from `_fenced_programmes`, so the join cannot widen past the caller's fence.
    files = (ScholarshipApplication.objects
             .filter(Q(programme_id__in=counts) | Q(cohort__programme_id__in=counts))
             .annotate(_won=ExpressionWrapper(ever_awarded_q(), output_field=BooleanField()))
             .values_list('pk', 'programme_id', 'cohort__programme_id', '_won').distinct())
    for _pk, pid, cpid, won in files:
        for gift in _gifts_of(pid, cpid) & counts.keys():
            counts[gift]['applications'] += 1
            counts[gift]['awarded'] += 1 if won else 0
    return counts


def _gifts_with_files(programme_ids):
    """The gifts in `programme_ids` that ever took a student — one query (finance's lifecycle)."""
    held = set()
    # org-fence: every id came from `_fenced_programmes`, so the join cannot widen past the caller's fence.
    for pid, cpid in (ScholarshipApplication.objects
                      .filter(Q(programme_id__in=programme_ids) | Q(cohort__programme_id__in=programme_ids))
                      .values_list('programme_id', 'cohort__programme_id').distinct()):
        held |= _gifts_of(pid, cpid)
    return held & set(programme_ids)


class AdminMyProgrammesView(_AdminBase):
    """GET /api/v1/admin/scholarship/my-programmes/ — see the module docstring.

    tenancy: org-fenced in `_fenced_programmes` / `_assigned` / `mentor_desk.current_assignments`.
    Classified in test_org_fence.py."""

    #: A MENTOR login reads its own gifts here (`test_mentor_denied_everywhere.ALLOWED`); a source user never.
    mentor_methods = ('get',)

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        scope = self._b40_scope(admin)
        every = sees_every_gift(admin, scope)
        reviews = staff_tables.in_reviewers(admin)
        mentor = mentor_desk.mentor_of(admin)
        if not lands(admin, scope):
            return self._deny_role()
        cases = cases_by_gift(admin) if reviews else None
        scholars = scholars_by_gift(admin) if mentor is not None else None
        if every:
            programmes = list(_fenced_programmes(admin))
        else:
            case_ids, mentor_ids = set(cases or {}), set(scholars or {}) - set(cases or {})
            programmes = list(_fenced_programmes(admin).filter(pk__in=case_ids))
            if mentor_ids:
                programmes += list(_fenced_programmes(admin, mentor.organisation_id).filter(pk__in=mentor_ids))
        ids = [p.pk for p in programmes]
        counts = _counts_by_gift(ids) if scope == 'all' else None
        if not every:
            with_files = set(ids)            # work in every listed gift, so somebody applied: no query
        elif counts is not None:
            with_files = {i for i in ids if counts[i]['applications']}
        else:
            with_files = _gifts_with_files(ids)
        rows = [self._row(p, counts, with_files, every, cases, scholars)
                for p in sorted(programmes, key=lambda p: p.code)]
        return Response({'every_gift': every, 'programmes': rows}, status=status.HTTP_200_OK)

    @staticmethod
    def _row(p, counts, with_files, every, cases, scholars):
        counts = counts[p.pk] if counts is not None else None
        lifecycle = programme_lifecycle(p, p.pk in with_files)
        row = {'id': p.id, 'code': p.code, 'name_en': p.name_en, 'name_ms': p.name_ms, 'name_ta': p.name_ta,
               'is_active': p.is_active, 'lifecycle': lifecycle, 'archived': lifecycle == 'archived'}
        if counts is not None:
            row.update(counts)
        if cases is not None:
            row['cases'] = cases.get(p.id, 0)
        if scholars is not None:
            row['scholars'] = scholars.get(p.id, 0)
        row['opens'] = 'overview' if every or row.get('cases') else 'my_students'
        return row
