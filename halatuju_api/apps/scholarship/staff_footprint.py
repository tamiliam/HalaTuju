"""Has this staff account DONE anything? The one question a staff delete turns on.

⚠ **WHY A FOOTPRINT AND NOT THE DATABASE'S OWN PROTECTIONS.** The gift-programme delete is
governed by foreign keys — a gift that has taken a student or a ringgit cannot be deleted because
`PROTECT` refuses it — and the obvious move was to reuse that shape here. It is WRONG for staff,
and provably so: a `PaymentRun` records who made it as `created_by`, an **email string with no
foreign key at all**. On production one admin has created 25 of the 27 runs and signed 8, and the
database would have raised no objection whatever to deleting her (owner, 2026-09-09: *"Kulaly for
example is assigned to create payment runs. She cannot be deleted until someone else is assigned
first"*). Foreign keys answer "would this delete break a row?"; they do not answer "is this person
doing a job?", and for staff that is the only question worth asking.

⚠ **WHAT THE SYSTEM CANNOT KNOW, and must not pretend to.** Nobody is *assigned* to payments: the
right to author a run is granted by ROLE (`_PAYMENTS_WRITE_ROLES`), never to a named person. So
there is no assignment to hand over and no handover this module could verify. The rule is therefore
the stricter and honest one — **once you have done work you are revoked, never deleted** — because
run 34 has to keep saying who made it.

Counting is deliberately EXHAUSTIVE rather than clever: any single trace of work refuses the
delete. A missed relation would be a silent deletion of somebody's record, so the failure has to
land on the side of keeping people.
"""
from django.db.models import Q


def footprint(admin):
    """`{what: count}` of everything this staff account has done, empty keys omitted.

    Two kinds of trace, and both count:
      * FOREIGN KEYS — assignments, interview slots, org requests. Deleting would cascade or be
        refused outright.
      * EMAIL STRINGS — payment runs, verdicts, vetting, verify-and-accept. Deleting breaks
        nothing and erases nobody, which is exactly what makes them dangerous: the row keeps an
        address that no longer resolves to a person.
    """
    from .models import (InterviewSession, InterviewSlot, OrgRequest, OrgRequestAttachment,
                         PaymentRun, ScholarshipApplication, Sponsor)
    email = (getattr(admin, 'email', '') or '').strip().lower()
    counts = {
        # By foreign key.
        'assigned_applications': ScholarshipApplication.objects.filter(assigned_to=admin).count(),
        'interview_slots': InterviewSlot.objects.filter(reviewer=admin).count(),
        'interviews': InterviewSession.objects.filter(interviewer=admin).count(),
        'requests_raised': OrgRequest.objects.filter(submitted_by=admin).count(),
        'request_files': OrgRequestAttachment.objects.filter(uploaded_by=admin).count(),
    }
    if email:
        # By recorded email. These survive a delete and stop naming anybody — the quiet damage.
        counts.update({
            'payment_runs_made': PaymentRun.objects.filter(created_by__iexact=email).count(),
            'payment_runs_signed': PaymentRun.objects.filter(
                admin_signed_email__iexact=email).count(),
            'benefactors_vetted': Sponsor.objects.filter(reviewed_by__iexact=email).count(),
            'applications_decided': ScholarshipApplication.objects.filter(
                Q(verified_by__iexact=email) | Q(rejected_by__iexact=email)
                | Q(verdict_decided_by__iexact=email)).count(),
        })
    return {k: v for k, v in counts.items() if v}


def has_footprint(admin) -> bool:
    """True when this account has done ANY recorded work, so it may only ever be revoked."""
    return bool(footprint(admin))
