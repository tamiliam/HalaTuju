"""
MyNadi admin API for the B40 Assistance Programme (Sprint 6a).

Reuses the existing PartnerAdmin auth (super admin sees all). Routes live under
/api/v1/admin/scholarship/ — covered by the NRIC-gate /admin/ whitelist;
PartnerAdminMixin does the real authorisation.
"""

# ── THE views_admin PACKAGE (code health H11 2026-09-20, H12 2026-09-20) ─────────
# This file holds NO code. Every view, helper and constant that used to live here was
# moved VERBATIM into a domain module beside it, and every module-level name each one
# defines is re-exported below — so `urls.py` is byte-identical, and `from
# apps.scholarship.views_admin import <anything>` still resolves exactly as it did.
#
# ⚠ WHAT IS NO LONGER AN ATTRIBUTE OF THIS MODULE. The old import block at the top of
# this file put `build_verdict`, `refine_sponsor_profile`, `timezone`,
# `send_request_info_email` and some sixty other DEPENDENCIES in this namespace, and a
# `mock.patch('apps.scholarship.views_admin.<dep>')` string addressed them here. Those
# dependencies now live in the module that reads them, so a patch string must name that
# module — `…views_admin.verdict.build_verdict`, not `…views_admin.build_verdict`. H12
# moved all 23 such strings. A patch string that still names this module will raise
# `AttributeError`, which is the failure you want: it cannot silently patch nothing.
#
# H11 moved ten modules (base … sponsor_terms); H12 moved the remaining nineteen domains
# as twenty modules. `base.py` holds `_AdminBase`, the organisation fence, which every
# view in the package still inherits.
from .base import (
    _AdminBase, _MONTH_RE, _org_or_none,
)
from .contracts import (
    _CONTRACT_RULE_LABELS, _ContractsBase, _contract_clause_dict, _contract_schedule_dict,
    _contract_template_detail, _contract_template_summary, _contract_validation_dict,
    _contracts_err, AdminContractClausesView, AdminContractDeployView,
    AdminContractGenerateQuizView, AdminContractImportDocxView, AdminContractPreviewView,
    AdminContractQuizPreviewView, AdminContractRevertView, AdminContractScheduleView,
    AdminContractSubmitView, AdminContractTemplateDetailView, AdminContractTemplateListView,
    AdminContractValidateView, AdminContractVettingView,
)
from .gifts import (
    REQUIREMENT_FIELDS, _apply_copy_terms, _cohort_row, _programme_row, _window_from,
    programme_delete_blocker, programme_lifecycle, programme_student_queryset, round_state,
)
from .gift_programmes import (
    CODE_RE, _ProgrammeScopedBase, AdminApplyCopyDraftView, AdminProgrammeDetailView,
    AdminProgrammeListView,
)
from .intake_years import (
    _requirements_from, AdminIntakeYearDetailView, AdminIntakeYearFinishView,
    AdminIntakeYearListView,
)
from .invoices import (
    _InvoiceBase, _invoice_money, _invoice_payload, AdminInvoiceActionView, AdminInvoicePdfView,
    AdminInvoiceSettingsView, AdminInvoicesView, AdminOrgBuildHoursView,
)
from .payments import (
    _PAYMENTS_READ_ROLES, _PAYMENTS_WRITE_ROLES, _PaymentsBase, _payment_item_dict,
    _payment_run_detail, _payment_run_summary, _run_programme, _sig,
    AdminPaymentFundingSummaryView, AdminPaymentRunCancelView, AdminPaymentRunCsvView,
    AdminPaymentRunDetailView, AdminPaymentRunItemView, AdminPaymentRunListView,
    AdminPaymentRunSignView,
)
from .requests import (
    _OrgRequestsBase, _org_request_err, AdminOrgRequestAnswerView, AdminOrgRequestApproveView,
    AdminOrgRequestAskView, AdminOrgRequestCommentView, AdminOrgRequestCountView,
    AdminOrgRequestDeclineView, AdminOrgRequestDeferView, AdminOrgRequestDetailView,
    AdminOrgRequestListView, AdminOrgRequestModifyView,
)
from .requests_delivery import (
    AdminOrgRequestAiRerunView, AdminOrgRequestAnalysisApproveView, AdminOrgRequestAnalysisView,
    AdminOrgRequestAttachmentCreateView, AdminOrgRequestAttachmentDeleteView,
    AdminOrgRequestAttachmentSignUploadView, AdminOrgRequestDoneView, AdminOrgRequestQuoteView,
    AdminOrgRequestRequoteView, AdminOrgRequestScheduleView, AdminOrgRequestTriageView,
    AdminOrgRequestWithdrawAnalysisView,
)
from .sponsor_terms import (
    _SponsorTermsBase, _terms_detail_dict, _terms_err, _terms_section_dict, _terms_summary_dict,
    _terms_validation_dict, AdminSponsorTermsDetailView, AdminSponsorTermsGenerateQuizView,
    AdminSponsorTermsImportDocxView, AdminSponsorTermsListView, AdminSponsorTermsPreviewView,
    AdminSponsorTermsPublishView, AdminSponsorTermsSectionsView, AdminSponsorTermsValidateView,
)
from .applications import (
    AdminApplicationDetailView, AdminApplicationListView, AdminApplicationRefereeView,
    AdminCancelDeclineView, AdminHoldAwardView, AdminNudgeStudentView, AdminOrgRejectView,
    AdminRefereeDetailView, AdminRejectView, AdminReportingDateView, AdminVerdictSummaryView,
    AdminVerifyAcceptView,
)
from .billing import AdminBillingRatesView, AdminBillingUsageView, AdminPlatformCostsView
from .credits import (
    _CreditsBase, _credit_dict, AdminWalletCreditCancelView, AdminWalletCreditListCreateView,
    AdminWalletCreditSignView,
)
from .graduation import (
    _BursaryAdminBase, AdminBursaryCountersignView, AdminBursaryWitnessView,
    AdminGraduationMessageListView, AdminGraduationMessageReviewView,
)
from .interview_slots import (
    _parse_slot_starts, AdminInterviewSlotDetailView, AdminInterviewSlotsView,
)
from .interviews import (
    _NEEDS_INTERVIEW_AMBERS, _RATIONALE_MAX, _VALID_VERDICTS, _interview_agenda, _is_authoring,
    _validate_findings, AdminInterviewReopenView, AdminInterviewSubmitView, AdminInterviewView,
    interview_agenda_full,
)
from .invitations import AdminInvitationsView
from .lifecycle import (
    AdminApplicationWitnessView, AdminAssignableAdminsView, AdminCloseApplicationView,
    AdminDisbursementActionView, AdminDisbursementScheduleView, AdminMaintenanceSubstateView,
    AdminScopeListView,
)
from .org_config import AdminOrganisationConfigurationView, AdminProgrammeConfigurationView
from .org_emails import (
    _SponsorEmailsBase, _partner_email_dict, _sponsor_email_dict, AdminPartnerEmailDetailView,
    AdminPartnerEmailsView, AdminSponsorEmailDetailView, AdminSponsorEmailsView,
)
from .overview import AdminOverviewLayoutView, AdminProgrammeOverviewView
from .profiles import (
    AdminFinaliseProfileView, AdminGenerateProfileView, AdminProfileEditView,
    AdminPublishAnonProfileView, AdminPublishProfileView, AdminRunVisionView,
    AdminSuggestGapsView,
)
from .resolution import (
    AdminRequestInfoView, AdminResolutionItemActionView, AdminResolutionItemView,
)
from .reviewers import (
    _REVIEWER_OPEN_STATUSES, _REVIEWER_PROGRESSED_STATUSES, _REVIEW_FLUENCY, _ReviewersBase,
    _median_days, _reviewer_dict, _reviewer_languages, _reviewer_workloads,
    AdminReviewerDetailView, AdminReviewerListView, AdminReviewerPauseView,
    AdminReviewerProgrammeView, AdminReviewerSystemEmailsView, ReviewerProfileView,
)
from .sources import (
    _SourcesBase, _source_application_counts, _source_dict, AdminSourceDetailView,
    AdminSourcesView, HOUSE_ORG_CODE,
)
from .spending import (
    _SPENDING_ROLES, _SpendingBase, _spending_gaps, AdminSpendingCategoryView, AdminSpendingView,
)
from .sponsors import (
    _SponsorScope, _chain_organisations, _sponsor_detail_dict, _sponsor_dict,
    AdminReleaseNricLockView, AdminSponsorListView, AdminSponsorPendingCountView,
    AdminSponsorReviewView,
)
from .sponsorships import (
    _sponsorship_dict, AdminSetAwardAmountView, AdminSponsorDetailView,
    AdminSponsorMembershipView, AdminSponsorshipListView,
)
from .theme import (
    _checks_both_modes, AdminOrganisationThemePublishView, AdminOrganisationThemeRevertView,
    AdminOrganisationThemeView,
)
from .verdict import (
    _OFFICER_FACT_VALUES, _OFFICER_OVERALL_VALUES, AdminAssignReviewerView, AdminCancelReopenView,
    AdminQcDecisionView, AdminRecordVerdictView, AdminReopenDecisionView, AdminSubmitDeclineView,
    AdminVerdictMetricsView,
)
