"""Unfinished work, per group (Sprint M1a, 2026-11-10; owner O5 and O7).

Brief `docs/plans/2026-11-10-m1-staff-list-brief.md` §4 and §5. ONE home for "what is still waiting on
this person", read by three doors:

  Remove from a group (O5)   refused while there is unfinished work IN THAT GROUP
                             (`staff_tables_admin._plan_remove`, `staff_mentor.stop`, the mentor `remove`);
  Delete (O7)                refused while there is unfinished work in ANY group (`unfinished` / `any_work`);
  the Staff list             `work` per row, counted for the whole page in a FIXED number of queries
                             (`unfinished_counts`), never per row.

The three groups:
  reviewers  open cases (`staff_lifecycle.open_cases`: in-play or reopened, assigned to them);
  mentors    scholars mentored now (open `MentorAssignment` rows of their Mentor, `mentoring.scholars_now`);
  admins     the per-KEY registry `ADMIN_WAITING` (brief addendum item 2): a key → the work it leaves
             waiting on its holder. Today `payments_prepare` → a payment run they made or maker-signed
             that is not finished (`staff_lifecycle.runs_in_progress`). Credits and award withdrawals join
             in M3/M4 by adding an entry here; no refusal code changes.

⚠ LEAD RULING (M1a): a Remove from Admins checks EVERY registry entry, whether or not the person still
holds the key — a run they made stays waiting on them after the key went (O5: "anything waiting on
them"). The key names the kind of work; it does not decide whether the work counts.

Considered and NOT counted (lead, brief §4), because each waits on SOMEONE ELSE: a pending
`AwardWithdrawalRequest` (any other checker decides), a quoted `OrgRequest` (any org admin approves), a
`ContractTemplate` pending deployment (a super deploys).
"""
from collections import namedtuple

from django.db.models import Q
from django.db.models.functions import Lower

ADMINS, REVIEWERS, MENTORS = 'admins', 'reviewers', 'mentors'

#: One kind of Admins work: the `field` the Staff list serves, the refusal `code` a Remove meets, the
#: count for one person and the count for a page of people (`{admin_id: n}`, one query), and the words.
Waiting = namedtuple('Waiting', 'field code one many message')


# ── reviewers ───────────────────────────────────────────────────────────────────────────────────────
def open_cases(admin):
    from . import staff_lifecycle
    return staff_lifecycle.open_cases(admin)


def open_cases_counts(admins):
    from . import staff_tables_admin
    return staff_tables_admin.open_case_counts([a.pk for a in admins])


# ── mentors ─────────────────────────────────────────────────────────────────────────────────────────
def scholars_now(admin):
    """Scholars ``admin``'s Mentor still mentors (open assignments), whatever the Mentor's state."""
    from . import mentoring
    if admin is None or admin.mentor_id is None:
        return 0
    return mentoring.scholars_now([admin.mentor_id]).get(admin.mentor_id, 0)


def scholars_now_counts(admins):
    from . import mentoring
    by_mentor = mentoring.scholars_now({a.mentor_id for a in admins if a.mentor_id is not None})
    return {a.pk: by_mentor.get(a.mentor_id, 0) for a in admins if a.mentor_id is not None}


# ── admins ──────────────────────────────────────────────────────────────────────────────────────────
def runs_in_progress(admin):
    from . import staff_lifecycle
    return staff_lifecycle.runs_in_progress(admin)


def runs_counts(admins):
    """`{admin_id: unfinished runs}` — `staff_lifecycle.runs_in_progress`'s rule for a page, ONE query.
    A run counts once per person even when they both made and maker-signed it."""
    from .models import PaymentRun
    from .staff_lifecycle import RUN_IN_PROGRESS
    ids_by_email = {}
    for a in admins:
        email = (a.email or '').strip().lower()
        if email:
            ids_by_email.setdefault(email, []).append(a.pk)
    if not ids_by_email:
        return {}
    rows = (PaymentRun.objects.filter(status__in=RUN_IN_PROGRESS)
            .annotate(maker=Lower('created_by'), signer=Lower('admin_signed_email'))
            .filter(Q(maker__in=list(ids_by_email)) | Q(signer__in=list(ids_by_email)))
            .values_list('maker', 'signer'))
    out = {}
    for maker, signer in rows:
        for email in {(maker or '').strip(), (signer or '').strip()} & set(ids_by_email):
            for pk in ids_by_email[email]:
                out[pk] = out.get(pk, 0) + 1
    return out


def _runs_message(name, n):
    return (f'{name} made or signed {n} payment run(s) that are not finished. Finish or cancel them '
            'first.')


#: Brief addendum item 2: the Admins "waiting on them" registry, by the key whose work it is.
ADMIN_WAITING = {
    'payments_prepare': Waiting('runs_in_progress', 'run_in_progress', runs_in_progress, runs_counts,
                                _runs_message),
}


def admins_waiting(admin):
    """`[(Waiting, n)]` for every registry entry with work waiting on ``admin`` (registry order)."""
    out = []
    for entry in ADMIN_WAITING.values():
        n = entry.one(admin)
        if n:
            out.append((entry, n))
    return out


# ── every group ─────────────────────────────────────────────────────────────────────────────────────
def _shape(admin_n, open_n, scholars_n):
    return {ADMINS: admin_n, REVIEWERS: {'open_cases': open_n}, MENTORS: {'scholars_now': scholars_n}}


def unfinished(admin):
    """`{admins: {<field>: n, ...}, reviewers: {open_cases}, mentors: {scholars_now}}` for one person."""
    return _shape({e.field: e.one(admin) for e in ADMIN_WAITING.values()},
                  open_cases(admin), scholars_now(admin))


def unfinished_counts(admins):
    """`{admin_id: unfinished(...)}` for a page of people in a FIXED number of queries (one per registry
    entry, one for open cases, one for scholars), never per row."""
    admins = list(admins)
    many = {e.field: e.many(admins) for e in ADMIN_WAITING.values()}
    opened = open_cases_counts(admins)
    scholars = scholars_now_counts(admins)
    return {a.pk: _shape({f: counts.get(a.pk, 0) for f, counts in many.items()},
                         opened.get(a.pk, 0), scholars.get(a.pk, 0)) for a in admins}


def any_work(work):
    """Is anything in an `unfinished` answer still waiting? (Delete's union, owner O7.)"""
    return any(n for group in work.values() for n in group.values())
