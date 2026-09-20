/**
 * Admin API client for partner organisations.
 *
 * All endpoints require Supabase auth and return 403 if the user
 * is not a partner admin.
 *
 * ⚠ THIS FILE IS A BARREL AND HOLDS NO CODE (code health H13). Every name below is declared
 * in `src/lib/admin-api/`, one module per domain, and re-exported from here so that **every
 * import of `@/lib/admin-api` anywhere in the app keeps working unchanged** — including the
 * thirty-odd test files that `jest.mock('@/lib/admin-api')`. Nothing was renamed, reworded or
 * reshaped in the split: the bodies were cut by line range from this file's own bytes.
 *
 * WHERE TO ADD A NEW CALL: in the module that owns its domain, then one line here. Do not put
 * code back in this file — the oversize ledger in `code-standards.json` now holds it at the
 * barrel's size, and that ledger only ratchets down.
 *
 * ⚠ `adminFetch`, `adminMutate`, `adminBursaryPost`, `giftQuery`, `API_BASE` and `ApiOptions`
 * stay PRIVATE to the folder (`./admin-api/client`) — they are not re-exported here, because
 * they were not exported before. `admin-api/client.ts` is NOT the same helper as
 * `api/client.ts`: `adminFetch` does not raise `nric-required` and does not carry DRF field
 * errors, and that difference is deliberate.
 */
// The partner organisation's own dashboard, student list and export.
export {
  getPartnerDashboard, DEFAULT_ADMIN_PAGE_SIZE, getPartnerStudents, getPartnerStudent,
  getExportUrl, deleteStudent,
} from './admin-api/partners'
export type {
  DashboardData, StudentListItem, StudentListData, StudentDetailData,
} from './admin-api/partners'

// Staff of an organisation: who they are, inviting them, revoking them.
export {
  getAdmins, deleteAdmin, revokeAdmin, resendAdminInvite, adminSetPassword, inviteAdmin,
} from './admin-api/admins'
export type { AdminItem } from './admin-api/admins'

// Every invitation this organisation has sent, of every kind.
export { getInvitations, inviteSponsor } from './admin-api/invitations'
export type { InvitationKind, InvitationRow, InvitationsPayload } from './admin-api/invitations'

// An admin's own profile, and a reviewer's own credentials.
export {
  getAdminProfile, updateAdminProfile, getReviewerProfile, updateReviewerProfile,
} from './admin-api/profiles'
export type { AdminProfile, ReviewerProfile, LangFluency } from './admin-api/profiles'

// The referral organisations a student arrives through, and witness assignment.
export { getOrgs, getSources, createSource, updateSource, assignWitness } from './admin-api/sources'
export type { OrgItem, SourceItem } from './admin-api/sources'

// The partner, reviewer, invitation and sponsor e-mail templates an officer authors.
export {
  getSponsorEmails, updateSponsorEmail, getPartnerEmails, getReviewerEmails, getInvitationEmails,
  getReviewerSystemEmails, updatePartnerEmail,
} from './admin-api/emails'
export type {
  PartnerEmailTemplate, PartnerEmailOrg, PartnerEmailsPayload, SponsorEmailTemplate,
  SponsorEmailsPayload, ReviewerSystemEmail,
} from './admin-api/emails'

// Sponsor terms authoring: sections, quiz, validation, publish, import.
export {
  getSponsorTermsList, getSponsorTerms, createSponsorTerms, updateSponsorTermsIntro,
  putSponsorTermsSections, generateSponsorTermsQuiz, validateSponsorTerms, publishSponsorTerms,
  importSponsorTermsDocx, previewSponsorTerms,
} from './admin-api/sponsorTerms'
export type {
  SponsorTermsSection, SponsorQuizPayload, SponsorTermsSummary, SponsorTermsDetail,
  SponsorTermsRule, SponsorTermsValidation, SponsorTermsListPayload,
} from './admin-api/sponsorTerms'

// The cockpit list, the whole detail payload, and assignment.
export {
  getScholarshipApplications, assignApplication, requestMoreInfo, getAssignableAdmins,
  getScholarshipApplication,
} from './admin-api/applications'
export type {
  AdminScholarshipListItem, AdminCompleteness, AdminInterviewSession, AdminSponsorProfile,
  AdminNudge, AdminScholarshipDetail, AdminScholarshipListData,
} from './admin-api/applications'

// Interview scheduling from the OFFICER's side, and the Check-3 session.
export {
  getInterview, saveInterview, submitInterview, reopenInterview, proposeInterviewSlots,
  getInterviewSlots, withdrawInterviewSlot, suggestInterviewGaps,
} from './admin-api/interviews'
export type { InterviewSlot, InterviewSchedule } from './admin-api/interviews'

// The verdict, its facts and audit, the QC gate, reopening, and the metrics.
export {
  reopenDecision, cancelReopen, recordQcDecision, getVerdictCaseSummary, recordVerdict,
  getVerdictMetrics,
} from './admin-api/verdict'
export type {
  VerdictMetrics, VerdictCaseSummary, AdminAnomaly, AdminAgendaEntry, AdminVerdictItem,
  AdminVerdictFact, AdminLedgerRow, AdminSubmissionReview, AdminFundingEstimate, AdminQuerySla,
  RecordVerdictPayload, RecordVerdictResult,
} from './admin-api/verdict'

// The irreversible ones: reject, decline, hold, accept, reporting date, nudge.
export {
  rejectApplication, orgRejectApplication, nudgeStudent, setReportingDate, cancelPendingDecline,
  holdPendingAward, verifyAcceptApplication, submitDeclineApplication, setMentoringCandidate,
} from './admin-api/decisions'

// The admin view of an uploaded document, its checks, and the referees.
export { reRunVision, addReferee, deleteReferee } from './admin-api/documents'
export type { AdminApplicantDocument, AdminReferee } from './admin-api/documents'

// Asking the student for more, and what comes back.
export { raiseResolutionItem, actionResolutionItem } from './admin-api/resolution'
export type { AdminResolutionItem } from './admin-api/resolution'

// Post-award: the bursary signatures, award amount, tranches, maintenance, closure.
export {
  adminCountersignBursary, adminWitnessBursary, setAwardAmount, scheduleTranche,
  actOnDisbursement, setMaintenanceSubstate, closeApplication,
} from './admin-api/lifecycle'
export type {
  MaintenanceSubstate, ClosureReason, AdminDisbursement, DisbursementAction,
} from './admin-api/lifecycle'

// The reviewer roster, their workload, their gift and their pause.
export {
  setReviewerPaused, setReviewerProgramme, listReviewers, getReviewerDetail,
} from './admin-api/reviewers'
export type {
  AdminReviewer, AdminReviewerGift, AdminReviewerReopen, AdminReviewerDetail,
} from './admin-api/reviewers'

// The sponsor queue, the review decision, memberships and wallet credits.
export {
  getSponsorDetail, setSponsorMembership, listSponsors, getPendingSponsorCount, reviewSponsor,
  recordSponsorCredit, signSponsorCredit, voidSponsorCredit,
} from './admin-api/sponsors'
export type {
  AdminSponsor, AdminSponsorWallet, AdminSponsorCredit, AdminSponsorStudent, AdminSponsorDetail,
} from './admin-api/sponsors'

// The Requests space: a request, its conversation, its analysis and its files.
export {
  getOrgRequests, getOrgRequest, getOrgRequestCount, createOrgRequest, answerOrgRequest,
  askOrgRequest, commentOrgRequest, recordOrgRequestAnalysis, approveOrgRequestAnalysis,
  withdrawOrgRequestAnalysis, approveOrgRequest, deferOrgRequest, modifyOrgRequest,
  declineOrgRequest, triageOrgRequest, quoteOrgRequest, requoteOrgRequest, scheduleOrgRequest,
  doneOrgRequest, aiRerunOrgRequest, deleteOrgRequestAttachment, uploadOrgRequestAttachment,
} from './admin-api/requests'
export type {
  OrgRequestComment, OrgRequestAttachment, OrgRequestAnalysis, OrgRequestDetail,
} from './admin-api/requests'

// The tenant usage screen, the platform cost ledger and the rate card.
export { getBillingUsage, getBillingCosts, setBillingAdjustment } from './admin-api/billing'
export type {
  BillingServiceRow, BillingModelRow, AiJobRow, BillingOrgBlock, BillingUsagePayload,
  BillingBlockedLine, BillingUnconverted, PlatformCostBlock, BillingChargeLine, BillingCharge,
  UnbilledRequest, BillingCostsPayload,
} from './admin-api/billing'

// Tenant invoices, receipts, issuer settings and build hours.
export {
  getInvoices, issueInvoice, sendInvoice, voidInvoice, recordInvoiceReceipt, fetchBillingPdf,
  getInvoiceSettings, saveInvoiceIssuer, saveTenantBillingDetails, getBillingRates,
  setBillingRate, recordBuildHours,
} from './admin-api/invoices'
export type {
  InvoiceStatus, InvoiceLineRow, InvoiceReceiptRow, InvoiceRow, InvoiceProblem, InvoiceReadiness,
  InvoicesPayload, InvoiceIssuerSettings, TenantBillingDetails, InvoiceSettingsPayload,
  BillingRateRow,
} from './admin-api/invoices'

// The read-only course-data health dashboard.
export { getCourseDataStatus, runCourseDataCheck } from './admin-api/courseData'
export type {
  LinkFailure, CourseDataStatusEntry, CourseDataCoverage, CourseDataStatusResponse,
} from './admin-api/courseData'

// Monthly Vircle payment runs and the funding summary behind them.
export {
  getFundingSummary, getPaymentRuns, createPaymentRun, getPaymentRun, updatePaymentRunItem,
  signPaymentRun, cancelPaymentRun, fetchPaymentRunCsv,
} from './admin-api/payments'
export type {
  PaymentRunSummary, PaymentRunItem, PaymentRunSkipped, PaymentSignature, PaymentRunDetail,
  FundingSummaryRow, FundingSummary,
} from './admin-api/payments'

// The Programme Overview — how is this gift doing, shaped by role.
export { getProgrammeOverview, getOverviewLayout, saveOverviewLayout } from './admin-api/overview'
export type {
  OverviewFunnel, OverviewMoney, OverviewAttention, OverviewWeekCount, OverviewMonthCount,
  OverviewMoneyMonth, OverviewStudentWeek, OverviewStudentOverall, OverviewCategory,
  OverviewBand, OverviewMyCase, OverviewQcCase, OverviewPace, OverviewIntake, OverviewLayoutRow,
  OverviewLayout, ProgrammeOverview,
} from './admin-api/overview'

// The officer's sponsor-spending screen.
export { getSpendingOverview, setSpendingCategory } from './admin-api/spending'
export type {
  SpendingMerchantRow, SpendingStudentRow, SpendingOverview,
} from './admin-api/spending'

// Org-owned versioned bursary contract templates.
export {
  getContractTemplates, createContractTemplate, getContractTemplate, updateContractConfig,
  putContractClauses, putContractSchedule, generateContractQuiz, recordContractVetting,
  getContractValidation, submitContractTemplate, revertContractTemplate, deployContractTemplate,
  getContractQuizPreview, fetchContractPreviewHtml, importContractDocx, fetchContractPreviewPdf,
} from './admin-api/contracts'
export type {
  ContractStatus, ContractQuizPayload, ContractClauseData, ContractScheduleRowData,
  ContractTemplateSummary, ContractTemplateDetail, ContractValidation,
} from './admin-api/contracts'

// What this admin's scope is, and the layered organisation/programme settings.
export {
  getAdminScopes, getProgrammeConfiguration, saveProgrammeConfiguration,
  getOrganisationConfiguration, saveOrganisationConfiguration,
} from './admin-api/orgConfig'
export type {
  AdminScopeOrg, AdminScopeProgramme, AdminScopes, ProgrammeItemState, ProgrammeConfigItem,
  ProgrammeConfiguration, OrganisationConfigSetting, OrganisationConfiguration,
} from './admin-api/orgConfig'

// The organisation's colours: draft, contrast check, publish, revert.
export {
  getOrganisationTheme, saveOrganisationThemeDraft, discardOrganisationThemeDraft,
  publishOrganisationTheme, revertOrganisationTheme,
} from './admin-api/theme'
export type { ThemeCheck, ThemeVersion, OrganisationTheme } from './admin-api/theme'

// Gift programmes, their apply copy, and their intake years.
export {
  getAdminProgrammes, createAdminProgramme, updateAdminProgramme, draftApplyCopy,
  deleteAdminProgramme, getAdminIntakeYears, createAdminIntakeYear, updateAdminIntakeYear,
  finishAdminIntakeYear,
} from './admin-api/programmes'
export type {
  ProgrammeRequirements, AdminApplyCopyBlock, AdminApplyCopy, AdminProgramme, AdminIntakeYear,
} from './admin-api/programmes'
