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
from django.db.models import Func, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Lower

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
    ('reviewer_notes', 'scholarship', 'ReviewerNote', ('author_email',)),   # request #55
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
    # Sprint T2 (D6, 2026-11-08): reviewers, QC and mentors become deletable under this test, so the
    # stamps THEIR work leaves are counted too — a missed one would be a silent deletion of a record.
    ('declines_scheduled', 'scholarship', 'ScholarshipApplication', ('pending_decline_by',)),
    ('maintenance_changes', 'scholarship', 'ScholarshipApplication',
     ('maintenance_substate_changed_by',)),
    ('qc_overrides', 'scholarship', 'ScholarshipApplication', ('qc_override_by',)),
    ('mentors_stopped', 'scholarship', 'Mentor', ('deactivated_by_email',)),
    ('mentoring_changes', 'scholarship', 'MentorAssignment', ('started_by_email', 'ended_by_email')),
    ('meetings_logged', 'scholarship', 'MentoringSession',
     ('logged_by_email', 'concern_handled_by_email')),
    ('module_reviews', 'scholarship', 'ModuleProgress', ('reviewed_by_email',)),
    ('terms_exemptions_granted', 'scholarship', 'SponsorTermsAcceptance', ('granted_by_email',)),
    ('award_withdrawals', 'scholarship', 'AwardWithdrawalRequest',
     ('requested_by_email', 'decided_by_email')),
)

#: The email stamps older than TD-443, kept under their first keys (the People tooltip reads them).
#: ⚠ The other two payment-run signatures (review M1, 2026-10-09): a checker or an approver who signed
#: run 34 must keep meaning somebody exactly as its maker does. `payment_runs_countersigned` is, since
#: #39 S2, the APPROVER's slot (Finance's approvals as well as an organisation admin's countersignatures).
CORE_EMAIL_STAMPS = (
    ('payment_runs_made', 'scholarship', 'PaymentRun', ('created_by',)),
    ('payment_runs_signed', 'scholarship', 'PaymentRun', ('admin_signed_email',)),
    ('payment_runs_checked', 'scholarship', 'PaymentRun', ('finance_signed_email',)),
    ('payment_runs_countersigned', 'scholarship', 'PaymentRun', ('org_admin_signed_email',)),
    ('benefactors_vetted', 'scholarship', 'Sponsor', ('reviewed_by',)),
    ('applications_decided', 'scholarship', 'ScholarshipApplication',
     ('verified_by', 'rejected_by', 'verdict_decided_by')),
)

#: By FOREIGN KEY to the login: `(key, app label, model, the fields naming them, extra filter)`.
#: Deleting would cascade, SET_NULL or be refused outright.
#: ⚠ TD-484 (A1.11a): `cases_held_before` and `review_actions` are the QC separation guard's own
#: evidence. A reviewer reassigned off a case holds no `assigned_to` any more, so they used to be
#: DELETABLE — and the delete SET_NULLs their `AssignmentEvent`s and CASCADEs their review
#: `StaffActivity` rows, so a re-invited namesake could then QC the very case they reviewed.
FK_TRACES = (
    ('assigned_applications', 'scholarship', 'ScholarshipApplication', ('assigned_to',), None),
    ('interview_slots', 'scholarship', 'InterviewSlot', ('reviewer',), None),
    ('interviews', 'scholarship', 'InterviewSession', ('interviewer',), None),
    ('requests_raised', 'scholarship', 'OrgRequest', ('submitted_by',), None),
    ('request_files', 'scholarship', 'OrgRequestAttachment', ('uploaded_by',), None),
    ('cases_held_before', 'scholarship', 'AssignmentEvent', ('from_admin', 'to_admin'), None),
    ('review_actions', 'scholarship', 'StaffActivity', ('actor',), 'review'),
    # Sprint T2 (D6): what a QC checker, a corrected reviewer and a request's commenter leave.
    ('qc_decisions', 'scholarship', 'StaffActivity', ('actor',), {'verb': 'qc_decision'}),
    ('corrections_attributed', 'scholarship', 'DecisionReopen', ('reviewer',), None),
    ('request_comments', 'scholarship', 'OrgRequestComment', ('author_admin',), None),
    ('requests_approved', 'scholarship', 'OrgRequest', ('approved_by',), None),
)

#: By the MENTOR record the login carries (a mentor login, or a staff member who also mentors —
#: S7d, lead ruling 2026-11-01): a scholar they mentored, a meeting, a concern. Their name lives on
#: this login and every scholar's mentoring history reads it. `MentorAssignment.mentor` and
#: `MentoringSession.mentor` are PROTECT as the database's backstop; this refuses first.
MENTOR_TRACES = (
    ('scholars_mentored', 'scholarship', 'MentorAssignment', None),
    ('mentoring_sessions', 'scholarship', 'MentoringSession', None),
    ('concerns_raised', 'scholarship', 'MentoringSession', {'concern': True}),
)


class _Count(Func):
    """`COUNT(pk)` as a plain function, so the subquery stays ungrouped and returns ONE row."""
    function = 'COUNT'
    output_field = IntegerField()


def _counted(qs):
    return Subquery(qs.order_by().annotate(n=_Count('pk')).values('n')[:1],
                    output_field=IntegerField())


def _email_match(fields):
    """A row naming the outer login's address in ANY of ``fields`` (case-insensitive; a blank stamp
    never matches, so a login with no address matches nothing). One row counts once."""
    match = Q()
    for i, field in enumerate(fields):
        match |= Q(**{f'_fp{i}': Lower(OuterRef('email'))}) & ~Q(**{field: ''})
    return match


def annotations():
    """``{key: Subquery}`` — the WHOLE footprint as correlated subqueries of a `PartnerAdmin` query.
    ``.annotate(**staff_footprint.annotations())`` puts it on a list's own query, so a list pays NO
    extra query for it (the Reviewers list is pinned at 6), and `from_row` reads it back."""
    from django.apps import apps
    from .qc_separation import REVIEW_VERBS
    out = {}
    for key, label, model_name, fields, extra in FK_TRACES:
        model = apps.get_model(label, model_name)
        match = Q()
        for field in fields:
            match |= Q(**{field: OuterRef('pk')})
        qs = model.objects.filter(match)
        if extra == 'review':
            qs = qs.filter(verb__in=REVIEW_VERBS)
        elif extra:
            qs = qs.filter(**extra)
        out[key] = _counted(qs)
    for key, label, model_name, extra in MENTOR_TRACES:
        qs = apps.get_model(label, model_name).objects.filter(mentor_id=OuterRef('mentor_id'))
        out[key] = _counted(qs.filter(**extra) if extra else qs)
    for key, label, model_name, fields in CORE_EMAIL_STAMPS + EMAIL_STAMPS:
        model = apps.get_model(label, model_name)
        lowered = {f'_fp{i}': Lower(field) for i, field in enumerate(fields)}
        out[key] = _counted(model.objects.alias(**lowered).filter(_email_match(fields)))
    return {f'fp_{k}': v for k, v in out.items()}


def from_row(row):
    """The footprint of a `PartnerAdmin` fetched with `annotations()` (an instance or a values dict)."""
    get = row.get if isinstance(row, dict) else (lambda name: getattr(row, name, 0))
    keys = ([k for k, *_ in FK_TRACES] + [k for k, *_ in MENTOR_TRACES]
            + [k for k, *_ in CORE_EMAIL_STAMPS + EMAIL_STAMPS])
    return {k: get(f'fp_{k}') for k in keys if get(f'fp_{k}')}


def footprints(admins):
    """``{admin pk: footprint}`` for many logins in ONE query, whatever their number."""
    from apps.courses.models import PartnerAdmin
    pks = [a.pk for a in admins if a is not None and a.pk is not None]
    if not pks:
        return {}
    ann = annotations()
    rows = PartnerAdmin.objects.filter(pk__in=pks).annotate(**ann).values('pk', *ann)
    return {r['pk']: from_row(r) for r in rows}


def footprint(admin):
    """`{what: count}` of everything this staff account has done, empty keys omitted. ONE query.

    Two kinds of trace, and both count:
      * FOREIGN KEYS — assignments, interview slots, org requests, the QC guard's evidence, and the
        scholars, meetings and concerns of the mentor record the login carries. Deleting would
        cascade or be refused outright.
      * EMAIL STRINGS — payment runs (made, and each of the three signatures), verdicts, vetting,
        verify-and-accept and every stamp in `EMAIL_STAMPS`. Deleting breaks nothing and erases
        nobody, which is exactly what makes them dangerous: the row keeps an address that no longer
        resolves to a person.
    """
    if admin is None or admin.pk is None:
        return {}
    return footprints([admin]).get(admin.pk, {})


def has_footprint(admin) -> bool:
    """True when this account has done ANY recorded work, so it may only ever be revoked."""
    return bool(footprint(admin))
