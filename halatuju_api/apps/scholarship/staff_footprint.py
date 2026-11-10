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

⚠ **THE NARROW WINDOW (T2 review N1).** A delete locks the login row, re-reads this footprint and
deletes inside one transaction. The lock holds back a write that names the person by FOREIGN KEY
(Postgres makes it wait on the locked row), but an EMAIL-ONLY stamp written by another request
between the check and the delete takes no lock on the login, so it can land in that gap and be left
naming an address with nobody behind it. The window is a few milliseconds and the person would have
to be working while being deleted; it is accepted, not closed.

⚠ **COVERAGE IS PINNED BY A DRIFT TEST** (`test_t2_footprint_drift.py`). Every foreign key or one-to-one
to `PartnerAdmin` or `Mentor`, and every field named `*_by`, `*_email`, `actor`, `author`, `*_actor` or
`*_author`, anywhere in the project, is either counted here or allowlisted there with the reason it is
not work. `test_t2_footprint_sources.py` builds one row per source and checks both paths agree. A new field
fails that test until somebody classifies it.
"""
from django.db.models import CharField, Count, F, Func, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, Lower

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
    # T2 review B1 (2026-11-09): the stamps the first T2 pass missed. A QC user who had written one
    # student note read as `{}` and deletable; every one of these is somebody's act on a record.
    ('student_notes', 'scholarship', 'StudentActivity', ('actor_email',)),
    ('results_reviewed', 'scholarship', 'SemesterResult', ('reviewed_by',)),
    ('graduation_messages', 'scholarship', 'GraduationMessage', ('approved_by',)),
    ('rounds_finished', 'scholarship', 'ScholarshipCohort', ('finished_by',)),
    ('merchant_categories', 'scholarship', 'MerchantCategory', ('decided_by_email',)),
    ('themes_published', 'courses', 'OrganisationTheme', ('published_by_email',)),
    ('org_settings_changed', 'courses', 'OrganisationConfiguration', ('updated_by_email',)),
    ('billing_details', 'scholarship', 'OrgBillingDetails', ('updated_by_email',)),
    ('invoice_issuers', 'scholarship', 'InvoiceIssuer', ('updated_by_email',)),
    ('billing_rates', 'scholarship', 'BillingRate', ('updated_by_email',)),
    ('organisation_layouts', 'scholarship', 'OrganisationOverviewLayout', ('updated_by_email',)),
    ('programme_layouts', 'scholarship', 'ProgrammeOverviewLayout', ('updated_by_email',)),
    ('staff_archived', 'courses', 'PartnerAdmin', ('archived_by_email',)),   # M1a: who archived whom
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
    # T2 review B1: `StaffActivity.actor` is CASCADE, so EVERY act they did goes with a delete —
    # a countersigned contract, a resolved query, a decline, an invitation sent, a withdrawal. All
    # count but the three a person does only to themselves (`SELF_ONLY_VERBS`).
    ('other_actions', 'scholarship', 'StaffActivity', ('actor',), 'other'),
    ('corrections_attributed', 'scholarship', 'DecisionReopen', ('reviewer',), None),
    ('request_comments', 'scholarship', 'OrgRequestComment', ('author_admin',), None),
    ('requests_approved', 'scholarship', 'OrgRequest', ('approved_by',), None),
    # T2 review B1: SET_NULL foreign keys — the row survives a delete and forgets who acted.
    ('invitations_sent', 'scholarship', 'Invitation', ('invited_by',), None),
    ('analyses_approved', 'scholarship', 'OrgRequestAnalysis', ('approved_by',), None),
    ('agreements_witnessed', 'scholarship', 'BursaryAgreement', ('witness_admin',), None),
)

#: The `StaffActivity` verbs a person does only to THEMSELVES: arriving is not work.
SELF_ONLY_VERBS = ('first_sign_in', 'invitation_accepted', 'profile_updated')

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


def _narrow(qs, extra):
    """A trace's own filter: the review verbs, every other act (`other`), or a plain lookup."""
    from .qc_separation import REVIEW_VERBS
    if extra == 'review':
        return qs.filter(verb__in=REVIEW_VERBS)
    if extra == 'other':
        return qs.exclude(verb__in=(*REVIEW_VERBS, 'qc_decision', *SELF_ONLY_VERBS))
    return qs.filter(**extra) if extra else qs


def _staff_rows(label, model_name):
    """Every row, whatever the model's default manager hides: counting is exhaustive."""
    from django.apps import apps
    return apps.get_model(label, model_name)._base_manager.all()


def _keys():
    return ([k for k, *_ in FK_TRACES] + [k for k, *_ in MENTOR_TRACES]
            + [k for k, *_ in CORE_EMAIL_STAMPS + EMAIL_STAMPS])


def _email_match(fields):
    """A row naming the outer login's address in ANY of ``fields`` (case-insensitive; a blank stamp
    never matches, so a login with no address matches nothing). One row counts once."""
    match = Q()
    for i, field in enumerate(fields):
        match |= Q(**{f'_fp{i}': Lower(OuterRef('email'))}) & ~Q(**{field: ''})
    return match


def annotations():
    """``{key: Subquery}`` — the WHOLE footprint of ONE login as correlated subqueries, for the
    single-person path (`footprint`: a person page, the delete's own re-check). ⚠ NOT FOR A TABLE
    (T2 review S1): each row would carry one `Lower(field) = Lower(email)` subquery per source, and
    none of them can use an index. A table reads `footprints`, a fixed number of queries per page."""
    out = {}
    for key, label, model_name, fields, extra in FK_TRACES:
        match = Q()
        for field in fields:
            match |= Q(**{field: OuterRef('pk')})
        out[key] = _counted(_narrow(_staff_rows(label, model_name).filter(match), extra))
    for key, label, model_name, extra in MENTOR_TRACES:
        qs = _staff_rows(label, model_name).filter(mentor_id=OuterRef('mentor_id'))
        out[key] = _counted(_narrow(qs, extra))
    for key, label, model_name, fields in CORE_EMAIL_STAMPS + EMAIL_STAMPS:
        lowered = {f'_fp{i}': Lower(field) for i, field in enumerate(fields)}
        out[key] = _counted(_staff_rows(label, model_name).alias(**lowered).filter(_email_match(fields)))
    return {f'fp_{k}': v for k, v in out.items()}


def from_row(row):
    """The footprint of a `PartnerAdmin` fetched with `annotations()` (an instance or a values dict)."""
    get = row.get if isinstance(row, dict) else (lambda name: getattr(row, name, 0))
    return {k: get(f'fp_{k}') for k in _keys() if get(f'fp_{k}')}


def _first_holder(names, i):
    """Branch ``i`` of a many-field source counts a row only where field ``i`` is the FIRST of
    ``names`` to hold the person, so a row naming them in two fields still counts ONCE. ⚠ An earlier
    field that is NULL holds nobody: `NOT (NULL = x)` is NULL in SQL, so it is let through by hand."""
    q = Q()
    for j in range(i):
        q &= ~Q(**{names[j]: F(names[i])}) | Q(**{f'{names[j]}__isnull': True})
    return q


def _branches(pks, mentor_ids, emails):
    """One grouped `SELECT key, who, COUNT(*)` per (source, field), for `footprints`' UNION ALL.
    ``who`` is text throughout (an id is cast) so the branches line up."""
    text = CharField()
    for key, label, model_name, fields, extra in (FK_TRACES if pks else ()):
        for i, field in enumerate(fields):
            qs = _narrow(_staff_rows(label, model_name), extra).filter(**{f'{field}__in': pks})
            yield (qs.filter(_first_holder(fields, i))
                   .annotate(k=Value(key), who=Cast(F(field), text)))
    for key, label, model_name, extra in (MENTOR_TRACES if mentor_ids else ()):
        qs = _narrow(_staff_rows(label, model_name), extra).filter(mentor_id__in=mentor_ids)
        yield qs.annotate(k=Value(key), who=Cast(F('mentor_id'), text))
    for key, label, model_name, fields in (CORE_EMAIL_STAMPS + EMAIL_STAMPS if emails else ()):
        names = [f'_fp{i}' for i in range(len(fields))]
        lowered = _staff_rows(label, model_name).annotate(**{n: Lower(f) for n, f in zip(names, fields)})
        for i, name in enumerate(names):
            yield (lowered.filter(**{f'{name}__in': emails}).filter(_first_holder(names, i))
                   .annotate(k=Value(key), who=F(name)))


def footprints(admins):
    """``{admin pk: footprint}`` for a whole TABLE in ONE query, whatever its number of rows.

    T2 review S1: the page's ids, mentor ids and lowered addresses go into ONE `UNION ALL` of grouped
    counts, a branch per (source, field), each `WHERE field IN (...)`, and the counts are merged here.
    Same sources as `annotations` (one list feeds both), so the two paths cannot disagree."""
    admins = [a for a in admins if a is not None and a.pk is not None]
    if not admins:
        return {}
    out = {a.pk: {} for a in admins}
    owners = {'fk': {}, 'mentor': {}, 'email': {}}
    for a in admins:
        owners['fk'].setdefault(str(a.pk), []).append(a.pk)
        if getattr(a, 'mentor_id', None):
            owners['mentor'].setdefault(str(a.mentor_id), []).append(a.pk)
        if a.email:
            owners['email'].setdefault(a.email.lower(), []).append(a.pk)
    kind = {k: 'fk' for k, *_ in FK_TRACES}
    kind.update({k: 'mentor' for k, *_ in MENTOR_TRACES})
    branches = [b.values('k', 'who').annotate(n=Count('pk')).order_by() for b in _branches(
        [a.pk for a in admins], [int(m) for m in owners['mentor']], list(owners['email']))]
    rows = branches[0].union(*branches[1:], all=True) if len(branches) > 1 else branches[0]
    for row in rows:
        for pk in owners[kind.get(row['k'], 'email')].get(row['who'], ()):
            out[pk][row['k']] = out[pk].get(row['k'], 0) + row['n']
    order = {k: i for i, k in enumerate(_keys())}
    return {pk: dict(sorted(w.items(), key=lambda kv: order[kv[0]])) for pk, w in out.items()}


def footprint(admin):
    """`{what: count}` of everything this staff account has done, empty keys omitted. ONE query.

    Two kinds of trace, and both count:
      * FOREIGN KEYS — assignments, interview slots, org requests, invitations sent, the QC guard's
        evidence, every act in their `StaffActivity` but arriving, and the scholars, meetings and
        concerns of the mentor record the login carries. Deleting would cascade, SET_NULL or be
        refused outright.
      * EMAIL STRINGS — payment runs (made, and each of the three signatures), verdicts, vetting,
        verify-and-accept and every stamp in `EMAIL_STAMPS`. Deleting breaks nothing and erases
        nobody, which is exactly what makes them dangerous: the row keeps an address that no longer
        resolves to a person.
    """
    from apps.courses.models import PartnerAdmin
    if admin is None or admin.pk is None:
        return {}
    ann = annotations()
    row = PartnerAdmin.objects.filter(pk=admin.pk).annotate(**ann).values(*ann).first()
    return from_row(row) if row else {}


def has_footprint(admin) -> bool:
    """True when this account has done ANY recorded work, so it may only ever be revoked."""
    return bool(footprint(admin))
