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
right to author a run is granted by PERMISSION (`payments.may_prepare`), never to a named person. So
there is no assignment to hand over and no handover this module could verify. The rule is therefore
the stricter and honest one — **once you have done work you are revoked, never deleted** — because
run 34 has to keep saying who made it.

Counting is deliberately EXHAUSTIVE rather than clever: any single trace of work refuses the
delete. A missed relation would be a silent deletion of somebody's record, so the failure has to
land on the side of keeping people.
"""
from django.db.models import Func, IntegerField, Q, Subquery

# ⚠ TD-443 (A1.11a): EVERY recorded-email stamp a staff member leaves, not only the payment and
# verdict ones. Each was a quiet erasure: delete the person and the row keeps an address that no
# longer resolves to anybody (who reassigned this case, who closed it, who signed this credit, who
# vetted this membership, who wrote this template). `(key, app label, model, stamp fields)`; one
# row counts once even when it carries the address in two of its stamps. The key is what the
# People tooltip shows (underscores read as spaces). A test pins that every field here exists.
EMAIL_STAMPS = (
    ('assignments_made', 'scholarship', 'AssignmentEvent', ('by_email',)),
    ('cases_closed', 'scholarship', 'ScholarshipApplication', ('closed_by',)),
    ('cases_recommended', 'scholarship', 'ScholarshipApplication', ('recommended_by',)),
    ('resolution_items', 'scholarship', 'ResolutionItem', ('created_by', 'resolved_by')),
    ('decisions_reopened', 'scholarship', 'DecisionReopen', ('reopened_by',)),
    ('permission_changes_made', 'scholarship', 'StaffPermissionChange', ('changed_by_email',)),
    ('credits_signed', 'scholarship', 'Donation',
     ('recorded_by_email', 'finance_checked_by_email', 'confirmed_by_email')),
    ('tranches_actioned', 'scholarship', 'Disbursement', ('actioned_by',)),
    ('invoices_handled', 'scholarship', 'Invoice',
     ('issued_by_email', 'sent_by_email', 'voided_by_email')),
    ('receipts_recorded', 'scholarship', 'InvoiceReceipt', ('recorded_by_email',)),
    ('payment_declarations_handled', 'scholarship', 'InvoicePaymentDeclaration',
     ('declared_by_email', 'confirmed_by_email', 'rejected_by_email')),
    ('billing_corrections', 'scholarship', 'OrgBillingCorrection', ('set_by_email',)),
    ('billing_adjustments', 'scholarship', 'OrgBillingAdjustment', ('set_by_email',)),
    ('build_hours_recorded', 'scholarship', 'OrgBuildHours', ('recorded_by_email',)),
    ('memberships_vetted', 'scholarship', 'SponsorProgrammeMembership', ('vetted_by',)),
    ('merchant_flags', 'scholarship', 'MerchantFlag', ('opened_by_email', 'closed_by_email')),
    ('merchant_notes', 'scholarship', 'MerchantFlagNote', ('author_email',)),
    ('guardian_changes', 'scholarship', 'GuardianContactChange', ('changed_by_email',)),
    ('partner_templates', 'scholarship', 'PartnerEmailTemplate', ('updated_by_email',)),
    ('sponsor_templates', 'scholarship', 'SponsorEmailTemplate', ('updated_by_email',)),
    ('sponsor_terms', 'scholarship', 'SponsorTermsVersion',
     ('created_by_email', 'published_by_email')),
    ('student_templates', 'scholarship', 'StudentEmailTemplate', ('updated_by_email',)),
    ('student_email_switches', 'scholarship', 'StudentEmailSwitch', ('updated_by_email',)),
    ('contract_templates', 'scholarship', 'ContractTemplate',
     ('created_by_email', 'submitted_by_email', 'deployed_by_email',
      'vetting_attested_by_email')),
    ('letter_templates', 'scholarship', 'LetterTemplate', ('updated_by_email',)),
    ('letters', 'scholarship', 'Letter', ('issued_by_email', 'withdrawn_by_email')),
    ('announcements', 'scholarship', 'Announcement', ('created_by_email', 'withdrawn_by_email')),
    ('surveys', 'scholarship', 'Survey', ('created_by_email',)),
    ('development_modules', 'scholarship', 'DevelopmentModule', ('created_by_email',)),
    ('mentors_added', 'scholarship', 'Mentor', ('created_by_email',)),
    ('application_items', 'scholarship', 'ProgrammeApplicationItem', ('updated_by_email',)),
    ('programme_aliases', 'scholarship', 'ProgrammeCodeAlias', ('created_by',)),
)


class _Count(Func):
    """`COUNT(pk)` as a plain function, so the subquery stays ungrouped and returns ONE row."""
    function = 'COUNT'
    output_field = IntegerField()


def _stamp_counts(admin, email):
    """All of `EMAIL_STAMPS` in ONE query (the People list calls `footprint` for every row)."""
    from django.apps import apps
    from apps.courses.models import PartnerAdmin
    subqueries = {}
    for key, label, model_name, fields in EMAIL_STAMPS:
        model = apps.get_model(label, model_name)
        match = Q()
        for field in fields:
            match |= Q(**{f'{field}__iexact': email})
        subqueries[key] = Subquery(
            model.objects.filter(match).order_by().annotate(n=_Count('pk')).values('n')[:1],
            output_field=IntegerField())
    row = PartnerAdmin.objects.filter(pk=admin.pk).annotate(**subqueries).values(*subqueries).first()
    return row or {}


def footprint(admin):
    """`{what: count}` of everything this staff account has done, empty keys omitted.

    Two kinds of trace, and both count:
      * FOREIGN KEYS — assignments, interview slots, org requests, and (S7d) the scholars they mentored.
        Deleting would cascade or be refused outright.
      * EMAIL STRINGS — payment runs (made, and each of the three signatures), verdicts, vetting,
        verify-and-accept. Deleting breaks
        nothing and erases nobody, which is exactly what makes them dangerous: the row keeps an
        address that no longer resolves to a person.
    """
    from .models import (AssignmentEvent, InterviewSession, InterviewSlot, OrgRequest,
                         OrgRequestAttachment, PaymentRun, ScholarshipApplication, Sponsor,
                         StaffActivity)
    from .qc_separation import REVIEW_VERBS
    email = (getattr(admin, 'email', '') or '').strip().lower()
    counts = {
        # By foreign key.
        'assigned_applications': ScholarshipApplication.objects.filter(assigned_to=admin).count(),
        'interview_slots': InterviewSlot.objects.filter(reviewer=admin).count(),
        'interviews': InterviewSession.objects.filter(interviewer=admin).count(),
        'requests_raised': OrgRequest.objects.filter(submitted_by=admin).count(),
        'request_files': OrgRequestAttachment.objects.filter(uploaded_by=admin).count(),
        # ⚠ TD-484 (A1.11a): the QC separation guard's own evidence. A reviewer reassigned off a
        # case holds no `assigned_to` any more, so they used to be DELETABLE — and the delete
        # SET_NULLs their `AssignmentEvent`s and CASCADEs their review `StaffActivity` rows, so a
        # re-invited namesake could then QC the very case they reviewed. Either trace now keeps them.
        'cases_held_before': AssignmentEvent.objects.filter(
            Q(from_admin=admin) | Q(to_admin=admin)).count(),
        'review_actions': StaffActivity.objects.filter(
            actor=admin, verb__in=REVIEW_VERBS).count(),
    }
    if getattr(admin, 'mentor_id', None):
        # S7d (lead ruling 2026-11-01): a staff member who has MENTORED anybody has done work. Their
        # name lives on this login and every scholar's mentoring history reads it, so they are revoked,
        # never deleted. A mentor record that never had a scholar is no footprint.
        from .models import MentorAssignment
        counts['scholars_mentored'] = MentorAssignment.objects.filter(mentor_id=admin.mentor_id).count()
    if email:
        # By recorded email. These survive a delete and stop naming anybody — the quiet damage.
        counts.update({
            'payment_runs_made': PaymentRun.objects.filter(created_by__iexact=email).count(),
            'payment_runs_signed': PaymentRun.objects.filter(
                admin_signed_email__iexact=email).count(),
            # ⚠ The other two signatures (review M1, 2026-10-09). `finance` and `org_admin` are
            # deletable roles, and the delete now also removes the login — a checker or an approver
            # who signed run 34 must keep meaning somebody exactly as its maker does.
            'payment_runs_checked': PaymentRun.objects.filter(
                finance_signed_email__iexact=email).count(),
            # Key name kept (the People tooltip reads it): since #39 S2 this slot is the APPROVER's,
            # i.e. Finance's approvals as well as an organisation admin's countersignatures.
            'payment_runs_countersigned': PaymentRun.objects.filter(
                org_admin_signed_email__iexact=email).count(),
            'benefactors_vetted': Sponsor.objects.filter(reviewed_by__iexact=email).count(),
            'applications_decided': ScholarshipApplication.objects.filter(
                Q(verified_by__iexact=email) | Q(rejected_by__iexact=email)
                | Q(verdict_decided_by__iexact=email)).count(),
        })
        if admin.pk is not None:
            counts.update(_stamp_counts(admin, email))
    return {k: v for k, v in counts.items() if v}


def has_footprint(admin) -> bool:
    """True when this account has done ANY recorded work, so it may only ever be revoked."""
    return bool(footprint(admin))
