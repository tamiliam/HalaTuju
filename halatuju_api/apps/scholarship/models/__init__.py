"""
Data model for the B40 Assistance Programme (scholarship) app.

Tables are named explicitly (``db_table``) so they read well in Supabase.
"""

# ── THE models PACKAGE (code health H15, 2026-09-20) ─────────────────────────────
# This file holds NO code. All 63 models, and every constant and helper beside them,
# were moved VERBATIM into a module beside this one, and every module-level name is
# re-exported below — so `from apps.scholarship.models import <anything>` resolves
# exactly as it did. 89 names are imported from here across the tree; not one importing
# file changed.
#
# ⚠ WHY THIS IS SAFE FOR THE DATABASE, which is the only question that matters here:
#   * A model's `app_label` comes from the app registry, not the file. Every module here
#     is inside `apps.scholarship`, so `get_containing_app_config` still answers
#     `scholarship` for all 63 — the label did not move.
#   * Every one of the 63 declares its `db_table` EXPLICITLY (checked: 63 classes, 63
#     `db_table` lines). Not one table name is implicit, so not one could drift with the
#     module name even in principle.
#   * Migrations address models by (app_label, model_name), never by module path, so the
#     existing migration graph still resolves. `makemigrations --check --dry-run` reports
#     no changes, and that is this sprint's most important line.
#   * There are no signal receivers and no custom managers in this app's models, so
#     nothing depended on this file being imported as one unit.
#
# The import ORDER below is a dependency order, not alphabetical: a handful of
# ForeignKeys name their target CLASS rather than a string ('Invoice', 'PaymentRun',
# 'Sponsor', 'ScholarshipApplication', 'ScholarshipCohort', 'Programme', 'Sponsorship',
# 'ApplicantDocument', 'Consent'), so the module defining a target has to be imported
# before the module that points at it. It is acyclic; keep it that way.
from .programmes import (
    Programme, ProgrammeCodeAlias, ScholarshipCohort, code_is_free,
)
from .applications import (
    ScholarshipApplication,
)
# Sources-and-referrals Sprint C (2026-10-19): moved verbatim out of `.applications` (moves only).
from .funding_need import FundingNeed
from .documents import (
    ApplicantDocument, Consent, OnboardingResponse, Referee,
)
from .interviews import (
    DecisionReopen, InterviewMessage, InterviewSession, InterviewSlot, SponsorProfile,
)
from .sponsors import (
    Sponsor, SponsorProgrammeMembership,
)
from .funding import (
    BankAccount, Disbursement, Donation, PaymentRun, PaymentRunItem, Sponsorship,
)
from .tenant_requests import (
    REQUEST_COMPONENT_TREE, _REQUEST_COMPONENT_LABELS, OrgRequest, OrgRequestAnalysis,
    OrgRequestAttachment, OrgRequestComment, flatten_component_tree,
)
from .review import (
    AssignmentEvent, GraduationMessage, ResolutionItem, ReviewerProfile, SemesterResult,
    SponsorReferral,
)
from .results import ResultsExpectation
from .content import (
    StandingGift, TrustContent, WhatsAppMessage,
)
from .agreements import (
    BursaryAgreement, ContractClause, ContractTemplate, PaymentScheduleRow,
)
from .billing import (
    BillingRate, BillingSequence, InvoiceIssuer, OrgBillingAdjustment, OrgBillingDetails,
    OrgBuildHours, OrganisationOverviewLayout, PlatformCost, ProgrammeOverviewLayout,
    UsageEvent,
)
from .invoices import (
    Invoice, InvoiceLine, InvoicePaymentDeclaration, InvoiceReceipt, OrgBillingCorrection,
)
from .comms_templates import (
    PartnerEmailLog, PartnerEmailTemplate, SponsorEmailLog, SponsorEmailTemplate,
    SponsorTermsAcceptance, SponsorTermsSection, SponsorTermsVersion, StudentEmailTemplate,
)
from .items import (
    ITEM_STATE_CHOICES, ApplicationItem, Invitation, ProgrammeApplicationItem,
    ProgrammeReferralSource,
)
from .spending import (
    SPEND_CATEGORY_CHOICES, SPEND_DECIDED_BY_CHOICES, BursarySpendTxn, MerchantCategory,
)
# Request #26 (2026-10-05) — the 64th model, NEW rather than moved: the change record for the
# parent/guardian contact. Points at ScholarshipApplication, so it imports after .applications.
from .guardian import GuardianContactChange
# Request #28 follow-up (2026-10-06) — models 65 and 66, NEW: one organisation's flag on a shop and
# its notes log. They point only at `courses.PartnerOrganisation` and at each other.
from .merchant_flags import NOTE_MAX, MerchantFlag, MerchantFlagNote
# Sources-and-referrals Sprint B (2026-10-18) — model 67, NEW: a referral source, owned by the
# organisation that added it. Points only at `courses.PartnerOrganisation`; every FK to it names it
# as a string, so its place in this order does not matter.
from .sources import ReferralSource
# Request #39 Sprint 4 (2026-10-21) — model 68, NEW: the history of a staff member's permissions.
# Points only at `courses.PartnerAdmin` / `courses.PartnerOrganisation`, by string.
from .staff_permission_changes import StaffPermissionChange

# Admin System health light (2026-10-28) — model 69, NEW: the email/cron recorders' small store.
# Points at nothing.
from .system_health import SystemHealthStatus
# Student maintenance Sprint 1 (2026-10-29) — model 70, NEW: the student file's activity log.
# Points at ScholarshipApplication by string.
from .activity import StudentActivity
