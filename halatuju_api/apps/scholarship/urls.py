"""URL routing for the B40 Assistance Programme API."""
from django.urls import path

from .views import (
    ApplicationConfirmView,
    ApplicationOnboardingCompleteView,
    ApplicationDetailView,
    ApplicationListCreateView,
    ScholarshipIntakeView,
    BursaryAgreementView,
    BankAccountView,
    StudentComprehensionView,
    StudentComprehensionQuizView,
    GuarantorPhoneVerifyStartView,
    GuarantorPhoneVerifyCheckView,
    ConsentView,
    CronRunView,
    DocumentDetailView,
    DocumentHelpView,
    IncomeRouteSwitchView,
    GraduationMessageView,
    IncomeClusterHelpView,
    DocumentListCreateView,
    DocumentSignUploadView,
    PromotionalConsentView,
    RefereeListCreateView,
    ResolutionItemListView,
    ResolutionItemResolveView,
    SemesterResultView,
    StudentAwardView,
    StudentInterviewView,
    StudentInterviewBookView,
    StudentInterviewCancelView,
    StudentInterviewMessageView,
    StudentInterviewRequestAlternativesView,
    WhatsAppInboundView,
)
from .views_sponsor import (
    SponsorActivityView,
    SponsorCancelOfferView,
    SponsorCommunityView,
    SponsorDonateView,
    SponsorFundView,
    SponsorGraduationMessagesView,
    SponsorImpactView,
    SponsorMeView,
    SponsorNotificationsView,
    SponsorPoolCountView,
    SponsorPoolDetailView,
    SponsorPoolListView,
    SponsorReferralView,
    SponsorRegisterView,
    SponsorSponsorshipsView,
    SponsorStandingGiftView,
    SponsorStatementView,
    SponsorTrustView,
    SponsorWalletView,
)
from .views_admin import (
    AdminApplicationDetailView,
    AdminVerdictSummaryView,
    AdminApplicationListView,
    AdminBursaryCountersignView,
    AdminBursaryWitnessView,
    AdminCloseApplicationView,
    AdminDisbursementActionView,
    AdminDisbursementScheduleView,
    AdminMaintenanceSubstateView,
    AdminGraduationMessageListView,
    AdminGraduationMessageReviewView,
    AdminSetAwardAmountView,
    AdminSponsorshipListView,
    AdminApplicationRefereeView,
    AdminAssignableAdminsView,
    AdminGenerateProfileView,
    AdminPublishAnonProfileView,
    AdminInterviewView,
    AdminInterviewSubmitView,
    AdminInterviewReopenView,
    AdminFinaliseProfileView,
    AdminProfileEditView,
    AdminPublishProfileView,
    AdminRejectView,
    AdminCancelDeclineView,
    AdminHoldAwardView,
    AdminRefereeDetailView,
    AdminRecordVerdictView,
    AdminReopenDecisionView,
    AdminCancelReopenView,
    AdminQcDecisionView,
    AdminRequestInfoView,
    AdminResolutionItemView,
    AdminAssignReviewerView,
    AdminInterviewSlotsView,
    AdminInterviewSlotDetailView,
    AdminResolutionItemActionView,
    AdminRunVisionView,
    AdminVerdictMetricsView,
    ReviewerProfileView,
    AdminSponsorListView,
    AdminSponsorReviewView,
    AdminSuggestGapsView,
    AdminVerifyAcceptView,
    AdminPaymentRunListView,
    AdminPaymentRunDetailView,
    AdminPaymentRunItemView,
    AdminPaymentRunSignView,
    AdminPaymentRunCancelView,
    AdminPaymentRunCsvView,
    AdminContractTemplateListView,
    AdminContractTemplateDetailView,
    AdminContractClausesView,
    AdminContractScheduleView,
    AdminContractGenerateQuizView,
    AdminContractVettingView,
    AdminContractValidateView,
    AdminContractSubmitView,
    AdminContractRevertView,
    AdminContractDeployView,
    AdminContractPreviewView,
    AdminContractQuizPreviewView,
)

urlpatterns = [
    # Twilio inbound-WhatsApp webhook (STOP/START → opt-out sync; Twilio-signature authed). TD-135.
    path('scholarship/whatsapp/inbound/', WhatsAppInboundView.as_view()),
    path('scholarship/intake/', ScholarshipIntakeView.as_view()),
    path('scholarship/applications/', ApplicationListCreateView.as_view()),
    path('scholarship/applications/<int:pk>/', ApplicationDetailView.as_view()),
    path('scholarship/applications/<int:pk>/confirm/', ApplicationConfirmView.as_view()),
    path('scholarship/applications/<int:pk>/income-route/', IncomeRouteSwitchView.as_view()),
    path('scholarship/applications/<int:pk>/onboarding-complete/', ApplicationOnboardingCompleteView.as_view()),  # F8a
    # F9a — in-programme student lifecycle (results → progress, 18+ promo consent, graduation relay)
    path('scholarship/applications/<int:pk>/semester-results/', SemesterResultView.as_view()),
    path('scholarship/applications/<int:pk>/promotional-consent/', PromotionalConsentView.as_view()),
    path('scholarship/applications/<int:pk>/graduation-message/', GraduationMessageView.as_view()),
    # Interview scheduling (student side; dark behind INTERVIEW_SCHEDULING_ENABLED)
    path('scholarship/applications/<int:pk>/interview/', StudentInterviewView.as_view()),
    path('scholarship/applications/<int:pk>/interview/book/', StudentInterviewBookView.as_view()),
    path('scholarship/applications/<int:pk>/interview/cancel/', StudentInterviewCancelView.as_view()),
    path('scholarship/applications/<int:pk>/interview/request-alternatives/',
         StudentInterviewRequestAlternativesView.as_view()),
    path('scholarship/applications/<int:pk>/interview/message/',
         StudentInterviewMessageView.as_view()),
    path('scholarship/documents/sign-upload/', DocumentSignUploadView.as_view()),
    path('scholarship/documents/', DocumentListCreateView.as_view()),
    path('scholarship/documents/<int:pk>/', DocumentDetailView.as_view()),
    path('scholarship/documents/<int:pk>/help/', DocumentHelpView.as_view()),
    path('scholarship/income/<str:member>/help/', IncomeClusterHelpView.as_view()),
    path('scholarship/referees/', RefereeListCreateView.as_view()),
    path('scholarship/consent/', ConsentView.as_view()),
    # Phase E3: the student's award offer (accept/decline; guardian-gated for minors)
    path('scholarship/award/', StudentAwardView.as_view()),
    # Conditional Bursary Award Agreement — the student's own signed contract (flag-gated)
    path('scholarship/bursary-agreement/', BursaryAgreementView.as_view()),
    # Post-award comprehension quiz — GET the template-served checkpoints, POST the pass
    # (version-pinned) — recorded for defensibility
    path('scholarship/award/comprehension-quiz/', StudentComprehensionQuizView.as_view()),
    path('scholarship/award/comprehension/', StudentComprehensionView.as_view()),
    # Post-award parent gate — SMS PIN to the guarantor's locked phone before signing
    path('scholarship/award/guarantor/verify-phone/send/', GuarantorPhoneVerifyStartView.as_view()),
    path('scholarship/award/guarantor/verify-phone/check/', GuarantorPhoneVerifyCheckView.as_view()),
    # S3: the student's resolution queue (IBKR Action Centre)
    path('scholarship/resolution-items/', ResolutionItemListView.as_view()),
    path('scholarship/resolution-items/<int:pk>/resolve/', ResolutionItemResolveView.as_view()),
    path('scholarship/bank-account/', BankAccountView.as_view()),

    # Phase E: sponsor accounts (authenticated self-registration + own status)
    path('sponsor/register/', SponsorRegisterView.as_view()),
    path('sponsor/me/', SponsorMeView.as_view()),
    path('sponsor/notifications/', SponsorNotificationsView.as_view()),  # F3: notify preference
    path('sponsor/pool/count/', SponsorPoolCountView.as_view()),  # F1: public landing counter
    path('sponsor/pool/', SponsorPoolListView.as_view()),
    path('sponsor/pool/<int:pk>/', SponsorPoolDetailView.as_view()),
    # Phase E3: wallet + funding (flag + approved-sponsor gated)
    path('sponsor/wallet/', SponsorWalletView.as_view()),
    path('sponsor/impact/', SponsorImpactView.as_view()),  # R2: My Giving dashboard aggregate
    path('sponsor/activity/', SponsorActivityView.as_view()),  # R3: activity feed
    path('sponsor/community/', SponsorCommunityView.as_view()),  # R3: community strip
    path('sponsor/statement/', SponsorStatementView.as_view()),  # R4: giving statement (two ledgers)
    path('sponsor/trust/', SponsorTrustView.as_view()),  # R5: Trust & Transparency hub
    path('sponsor/standing-gift/', SponsorStandingGiftView.as_view()),  # R6: AutoSponsor
    path('sponsor/graduation-messages/', SponsorGraduationMessagesView.as_view()),  # F9a relay
    path('sponsor/referrals/', SponsorReferralView.as_view()),  # F4 referral/invite
    path('sponsor/wallet/donate/', SponsorDonateView.as_view()),
    path('sponsor/pool/<int:pk>/fund/', SponsorFundView.as_view()),
    path('sponsor/sponsorships/', SponsorSponsorshipsView.as_view()),
    path('sponsor/sponsorships/<int:pk>/cancel/', SponsorCancelOfferView.as_view()),

    # Internal cron — Cloud Scheduler runs whitelisted commands via a shared
    # secret header (X-Cron-Secret). Inert without the secret.
    path('internal/cron/<str:job>/', CronRunView.as_view()),

    # Payments module (P2): monthly Vircle payment runs. Admin/org_admin, org-fenced.
    path('admin/scholarship/payment-runs/', AdminPaymentRunListView.as_view()),
    path('admin/scholarship/payment-runs/<int:pk>/', AdminPaymentRunDetailView.as_view()),
    path('admin/scholarship/payment-runs/<int:pk>/items/<int:item_id>/', AdminPaymentRunItemView.as_view()),
    path('admin/scholarship/payment-runs/<int:pk>/sign/', AdminPaymentRunSignView.as_view()),
    path('admin/scholarship/payment-runs/<int:pk>/cancel/', AdminPaymentRunCancelView.as_view()),
    path('admin/scholarship/payment-runs/<int:pk>/csv/', AdminPaymentRunCsvView.as_view()),

    # Contract module (S3): org-owned versioned bursary templates. Super/org_admin,
    # org-fenced (cross-org 404); deploy super-only. Service = apps.scholarship.contracts.
    path('admin/scholarship/contract-templates/', AdminContractTemplateListView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/', AdminContractTemplateDetailView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/clauses/', AdminContractClausesView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/clauses/<int:order>/generate-quiz/',
         AdminContractGenerateQuizView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/schedule/', AdminContractScheduleView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/vetting/', AdminContractVettingView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/validate/', AdminContractValidateView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/submit/', AdminContractSubmitView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/revert/', AdminContractRevertView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/deploy/', AdminContractDeployView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/preview/', AdminContractPreviewView.as_view()),
    path('admin/scholarship/contract-templates/<int:pk>/quiz-preview/', AdminContractQuizPreviewView.as_view()),

    # MyNadi admin (PartnerAdmin auth; /admin/ is NRIC-gate whitelisted)
    # Phase E: sponsor account vetting
    path('admin/sponsors/', AdminSponsorListView.as_view()),
    path('admin/sponsors/<int:pk>/review/', AdminSponsorReviewView.as_view()),
    # Phase E3: match oversight + set the award amount
    path('admin/sponsorships/', AdminSponsorshipListView.as_view()),
    path('admin/scholarship/applications/<int:pk>/award-amount/', AdminSetAwardAmountView.as_view()),
    # Post-award S4: disbursement/tranche ledger (schedule + release/withhold/return)
    path('admin/scholarship/applications/<int:pk>/disbursements/',
         AdminDisbursementScheduleView.as_view()),
    path('admin/scholarship/disbursements/<int:pk>/<str:action>/',
         AdminDisbursementActionView.as_view()),
    # Post-award S5: maintenance sub-state (on_track/probation/on_hold/ready_to_close)
    path('admin/scholarship/applications/<int:pk>/maintenance/',
         AdminMaintenanceSubstateView.as_view()),
    # Post-award S6: manual closure (status='closed' + closure_reason)
    path('admin/scholarship/applications/<int:pk>/close/',
         AdminCloseApplicationView.as_view()),
    path('admin/scholarship/assignable-admins/', AdminAssignableAdminsView.as_view()),
    path('admin/scholarship/applications/', AdminApplicationListView.as_view()),
    path('admin/scholarship/applications/<int:pk>/', AdminApplicationDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/verdict-summary/', AdminVerdictSummaryView.as_view()),
    path('admin/scholarship/applications/<int:pk>/verify-accept/', AdminVerifyAcceptView.as_view()),
    path('admin/scholarship/applications/<int:pk>/reject/', AdminRejectView.as_view()),
    # Conditional Bursary Award Agreement — Foundation countersignature (super-only) +
    # partner-org witness attestation (referring-org admin or super; non-blocking).
    path('admin/scholarship/applications/<int:pk>/bursary-agreement/countersign/',
         AdminBursaryCountersignView.as_view()),
    path('admin/scholarship/applications/<int:pk>/bursary-agreement/witness/',
         AdminBursaryWitnessView.as_view()),
    # Cool-off controls: cancel a pending decline / hold a pending award before it reveals.
    path('admin/scholarship/applications/<int:pk>/cancel-decline/', AdminCancelDeclineView.as_view()),
    path('admin/scholarship/applications/<int:pk>/hold-award/', AdminHoldAwardView.as_view()),
    # F7: super-only audited reviewer (re)assignment.
    path('admin/scholarship/applications/<int:pk>/assign/', AdminAssignReviewerView.as_view()),
    # Interview scheduling (reviewer proposes times; dark behind INTERVIEW_SCHEDULING_ENABLED)
    path('admin/scholarship/applications/<int:pk>/interview-slots/', AdminInterviewSlotsView.as_view()),
    path('admin/scholarship/applications/<int:pk>/interview-slots/<int:slot_id>/', AdminInterviewSlotDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/referees/', AdminApplicationRefereeView.as_view()),
    path('admin/scholarship/applications/<int:pk>/referees/<int:ref_id>/', AdminRefereeDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/documents/<int:doc_id>/re-run-vision/', AdminRunVisionView.as_view()),
    path('admin/scholarship/applications/<int:pk>/generate-profile/', AdminGenerateProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/finalise-profile/', AdminFinaliseProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/suggest-gaps/', AdminSuggestGapsView.as_view()),
    path('admin/scholarship/applications/<int:pk>/profile/', AdminProfileEditView.as_view()),
    path('admin/scholarship/applications/<int:pk>/publish/', AdminPublishProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/anon-profile/publish/', AdminPublishAnonProfileView.as_view()),
    # Phase C: interview capture + request-more-docs
    path('admin/scholarship/applications/<int:pk>/interview/', AdminInterviewView.as_view()),
    path('admin/scholarship/applications/<int:pk>/interview/submit/', AdminInterviewSubmitView.as_view()),
    path('admin/scholarship/applications/<int:pk>/interview/reopen/', AdminInterviewReopenView.as_view()),
    path('admin/scholarship/applications/<int:pk>/request-info/', AdminRequestInfoView.as_view()),
    # S3: officer-raised resolution tickets + waive/resolve
    path('admin/scholarship/applications/<int:pk>/resolution-items/', AdminResolutionItemView.as_view()),
    path('admin/scholarship/resolution-items/<int:item_id>/<str:action>/', AdminResolutionItemActionView.as_view()),
    # S5: officer records the verification verdict (+ optional finalise) + override metrics
    path('admin/scholarship/applications/<int:pk>/record-verdict/', AdminRecordVerdictView.as_view()),
    # Reverse a recorded decision (super-only): reopen holds the profile from the pool,
    # cancel-reopen restores it with no change.
    path('admin/scholarship/applications/<int:pk>/reopen-decision/', AdminReopenDecisionView.as_view()),
    path('admin/scholarship/applications/<int:pk>/cancel-reopen/', AdminCancelReopenView.as_view()),
    # QC gate on an AWAITING-QC ('interviewed') case: accept → recommended, or reopen → back to reviewer.
    path('admin/scholarship/applications/<int:pk>/qc-decision/', AdminQcDecisionView.as_view()),
    path('admin/scholarship/verdict-metrics/', AdminVerdictMetricsView.as_view()),
    # F6: a reviewer's own credentials + contact profile (self-scoped, reviewer/super).
    path('admin/reviewer-profile/', ReviewerProfileView.as_view()),
    # F9a — graduation thank-you moderation queue
    path('admin/graduation-messages/', AdminGraduationMessageListView.as_view()),
    path('admin/graduation-messages/<int:pk>/review/', AdminGraduationMessageReviewView.as_view()),
]
