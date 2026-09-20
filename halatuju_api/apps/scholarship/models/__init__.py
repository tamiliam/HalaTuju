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
    FundingNeed, ScholarshipApplication,
)
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
from .content import (
    StandingGift, TrustContent, WhatsAppMessage,
)
from .agreements import (
    BursaryAgreement, ContractClause, ContractTemplate, PaymentScheduleRow,
)
from .billing import (
    BillingRate, BillingSequence, InvoiceIssuer, OrgBillingAdjustment, OrgBillingDetails,
    OrgBuildHours, OrganisationOverviewLayout, PlatformCost, UsageEvent,
)
from .invoices import (
    Invoice, InvoiceLine, InvoiceReceipt,
)
from .comms_templates import (
    PartnerEmailLog, PartnerEmailTemplate, SponsorEmailLog, SponsorEmailTemplate,
    SponsorTermsAcceptance, SponsorTermsSection, SponsorTermsVersion,
)
from .items import (
    ITEM_STATE_CHOICES, ApplicationItem, Invitation, ProgrammeApplicationItem,
)
from .spending import (
    SPEND_CATEGORY_CHOICES, SPEND_DECIDED_BY_CHOICES, BursarySpendTxn, MerchantCategory,
)

