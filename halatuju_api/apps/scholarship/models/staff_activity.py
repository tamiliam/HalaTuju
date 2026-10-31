"""A staff member's own activity list (common profile S3, 2026-10-31) — model 72, NEW.

Roadmap `docs/plans/2026-10-31-common-profile-roadmap.md` (S3 writes, S4 reads and back-fills, S5
shows it on the profile page). One row each time a person on the admin platform DOES something:
signs in for the first time, saves their profile, records a verdict, assigns a case, witnesses a
contract... Written ONLY by `apps/scholarship/staff_activity.record` (best-effort, D9).

⚠ A ROW HOLDS IDS, NEVER COPIED TEXT. No name, no email, no reason, no note: `subject_type` +
`subject_id` say WHAT it was about, `meta` holds only ids, short enum codes, numbers and booleans
(`staff_activity.META_KEYS`, checked in code). The S4 reader looks a student's name up when the list
is read and shows it only if the viewer may still see that student now (D8).

⚠ `subject_id` IS AN INTEGER, NOT A FOREIGN KEY (D7). A student's PDPA purge must never cascade into
somebody's history, and must not be refused by it either; the S4 reader renders a subject that has
gone as "a student (removed)".

⚠ `actor` CASCADES (D6). The list is OWN-ONLY — nobody reads another person's rows — so when a staff
row is deleted (only ever one with no recorded work, `staff_footprint`) its list goes with it.

`created_at` is `default=timezone.now`, NOT `auto_now_add`: the S4 back-fill writes rows dated at the
moment the old stamp records, and `auto_now_add` would overwrite that date with today's. `backfilled`
marks those rebuilt rows (S5 shows them as rebuilt); it carries a DATABASE default as well, the 0193
pattern, so an insert that does not name it still works.
"""
from django.db import models
from django.utils import timezone


class StaffActivityVerb(models.TextChoices):
    """The CLOSED list of things a row can say. A verb outside it is refused by `record` (logged and
    dropped). `staff_activity.WIRED` names every verb's writers and the drift test
    (`tests/test_staff_activity.py`) proves every verb has one (S4 wired the last)."""
    # ── S3: sign-in, profile, invitations, permissions ──────────────────────────────────────────
    INVITATION_SENT = 'invitation_sent', 'Sent an invitation'
    INVITATION_ACCEPTED = 'invitation_accepted', 'Accepted an invitation'
    FIRST_SIGN_IN = 'first_sign_in', 'Signed in for the first time'
    PROFILE_UPDATED = 'profile_updated', 'Updated their profile'
    PERMISSIONS_CHANGED = 'permissions_changed', "Changed a person's permissions"
    # ── S3: the case actions ───────────────────────────────────────────────────────────────────
    ASSIGNED = 'assigned', 'Assigned a case'
    UNASSIGNED = 'unassigned', 'Unassigned a case'
    QUERY_RAISED = 'query_raised', 'Asked a student for something'
    QUERY_RESOLVED = 'query_resolved', "Closed a student's query"
    INTERVIEW_SUBMITTED = 'interview_submitted', 'Submitted interview findings'
    VERDICT_RECORDED = 'verdict_recorded', 'Recorded a verdict'
    VERIFY_ACCEPT = 'verify_accept', 'Verified and sent a recommendation to QC'
    DECLINE_SENT_TO_QC = 'decline_sent_to_qc', 'Sent a decline to QC'
    DECLINED = 'declined', 'Declined a case'
    QC_DECISION = 'qc_decision', 'Made a QC decision'
    DECISION_REOPENED = 'decision_reopened', 'Reopened a decision'
    CASE_CLOSED = 'case_closed', 'Closed a case'
    CONTRACT_WITNESSED = 'contract_witnessed', 'Witnessed a contract'
    # ── S4: money, contracts, requests ─────────────────────────────────────────────────────────
    PAYMENT_RUN_CREATED = 'payment_run_created', 'Prepared a payment run'
    PAYMENT_RUN_SIGNED = 'payment_run_signed', 'Signed a payment run'
    TRANCHE_RELEASED = 'tranche_released', 'Released a payment'
    TRANCHE_WITHHELD = 'tranche_withheld', 'Withheld a payment'
    TRANCHE_RETURNED = 'tranche_returned', 'Recorded a returned payment'
    CREDIT_RECORDED = 'credit_recorded', 'Recorded a credit'
    CREDIT_CHECKED = 'credit_checked', 'Checked a credit'
    CREDIT_CONFIRMED = 'credit_confirmed', 'Confirmed a credit'
    CONTRACT_TEMPLATE_CREATED = 'contract_template_created', 'Created a contract template'
    CONTRACT_TEMPLATE_VETTED = 'contract_template_vetted', 'Vetted a contract template'
    CONTRACT_TEMPLATE_SUBMITTED = 'contract_template_submitted', 'Submitted a contract template'
    CONTRACT_TEMPLATE_DEPLOYED = 'contract_template_deployed', 'Deployed a contract template'
    CONTRACT_COUNTERSIGNED = 'contract_countersigned', 'Countersigned a contract'
    BENEFACTOR_VETTED = 'benefactor_vetted', 'Vetted a benefactor'
    INVOICE_ISSUED = 'invoice_issued', 'Issued an invoice'
    INVOICE_SENT = 'invoice_sent', 'Sent an invoice'
    INVOICE_VOIDED = 'invoice_voided', 'Voided an invoice'
    PAYMENT_DECLARED = 'payment_declared', 'Declared a payment'
    PAYMENT_CONFIRMED = 'payment_confirmed', 'Confirmed a payment'
    PAYMENT_REJECTED = 'payment_rejected', 'Rejected a payment'
    ORG_REQUEST_RAISED = 'org_request_raised', 'Raised a request'
    ORG_REQUEST_APPROVED = 'org_request_approved', 'Approved a request'
    ORG_REQUEST_DECLINED = 'org_request_declined', 'Declined a request'
    MERCHANT_FLAG_OPENED = 'merchant_flag_opened', 'Flagged a shop'
    MERCHANT_FLAG_CLOSED = 'merchant_flag_closed', 'Closed a shop flag'


class StaffActivitySubject(models.TextChoices):
    """What a row is ABOUT — the closed list of `subject_type`. `subject_id` is that row's id."""
    APPLICATION = 'application', 'A student application'
    STAFF = 'staff', 'A staff member'
    INVITATION = 'invitation', 'An invitation'
    # S4. A tranche's subject is its STUDENT (the application; the tranche id is in meta) and a
    # declaration's or a receipt's is its INVOICE, so the reader's rules stay few.
    PAYMENT_RUN = 'payment_run', 'A payment run'
    CREDIT = 'credit', 'A credit'
    CONTRACT_TEMPLATE = 'contract_template', 'A contract template'
    SPONSOR = 'sponsor', 'A benefactor'
    INVOICE = 'invoice', 'An invoice'
    ORG_REQUEST = 'org_request', 'A request'
    MERCHANT_FLAG = 'merchant_flag', 'A shop flag'


class StaffActivity(models.Model):
    """One thing one person did, newest first. Append-only: nothing edits a row."""
    actor = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.CASCADE, related_name='staff_activities')
    #: The organisation the action happened in (the case's, else the person's). NULL for a platform
    #: super acting outside any organisation. Kept on a delete of the organisation (SET_NULL).
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+')
    verb = models.CharField(max_length=40, choices=StaffActivityVerb.choices)
    subject_type = models.CharField(max_length=30, blank=True, default='',
                                    choices=StaffActivitySubject.choices)
    subject_id = models.BigIntegerField(null=True, blank=True,
                                        help_text='The subject row id. NOT a foreign key (D7).')
    meta = models.JSONField(default=dict, blank=True,
                            help_text='Ids, short codes, numbers and booleans only — never free text')
    created_at = models.DateTimeField(default=timezone.now)
    backfilled = models.BooleanField(default=False, db_default=False,
                                     help_text='Rebuilt from an older record by the S4 back-fill')

    class Meta:
        db_table = 'staff_activity'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['actor', '-created_at'],
                                name='staff_act_actor_created_idx')]
        verbose_name_plural = 'Staff activities'

    def __str__(self):
        return f'{self.verb} by {self.actor_id} on {self.subject_type or "-"}:{self.subject_id or "-"}'
