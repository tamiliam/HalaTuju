"""URL routing for the B40 Assistance Programme API."""
from django.urls import path

from .views import (
    ApplicationConfirmView,
    ApplicationOnboardingCompleteView,
    ApplicationDetailView,
    ApplicationListCreateView,
    ConsentView,
    CronRunView,
    DocumentDetailView,
    DocumentHelpView,
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
)
from .views_sponsor import (
    SponsorCancelOfferView,
    SponsorDonateView,
    SponsorFundView,
    SponsorGraduationMessagesView,
    SponsorMeView,
    SponsorNotificationsView,
    SponsorPoolCountView,
    SponsorPoolDetailView,
    SponsorPoolListView,
    SponsorReferralView,
    SponsorRegisterView,
    SponsorSponsorshipsView,
    SponsorWalletView,
)
from .views_admin import (
    AdminApplicationDetailView,
    AdminApplicationListView,
    AdminGraduationMessageListView,
    AdminGraduationMessageReviewView,
    AdminSetAwardAmountView,
    AdminSponsorshipListView,
    AdminApplicationRefereeView,
    AdminAssignableAdminsView,
    AdminGenerateAnonProfileView,
    AdminGenerateProfileView,
    AdminPublishAnonProfileView,
    AdminInterviewView,
    AdminInterviewSubmitView,
    AdminFinaliseProfileView,
    AdminProfileEditView,
    AdminPublishProfileView,
    AdminRejectView,
    AdminRefereeDetailView,
    AdminRecordVerdictView,
    AdminRequestInfoView,
    AdminResolutionItemView,
    AdminAssignReviewerView,
    AdminResolutionItemActionView,
    AdminRunVisionView,
    AdminVerdictMetricsView,
    ReviewerProfileView,
    AdminSponsorListView,
    AdminSponsorReviewView,
    AdminSuggestGapsView,
    AdminVerifyAcceptView,
)

urlpatterns = [
    path('scholarship/applications/', ApplicationListCreateView.as_view()),
    path('scholarship/applications/<int:pk>/', ApplicationDetailView.as_view()),
    path('scholarship/applications/<int:pk>/confirm/', ApplicationConfirmView.as_view()),
    path('scholarship/applications/<int:pk>/onboarding-complete/', ApplicationOnboardingCompleteView.as_view()),  # F8a
    # F9a — in-programme student lifecycle (results → progress, 18+ promo consent, graduation relay)
    path('scholarship/applications/<int:pk>/semester-results/', SemesterResultView.as_view()),
    path('scholarship/applications/<int:pk>/promotional-consent/', PromotionalConsentView.as_view()),
    path('scholarship/applications/<int:pk>/graduation-message/', GraduationMessageView.as_view()),
    path('scholarship/documents/sign-upload/', DocumentSignUploadView.as_view()),
    path('scholarship/documents/', DocumentListCreateView.as_view()),
    path('scholarship/documents/<int:pk>/', DocumentDetailView.as_view()),
    path('scholarship/documents/<int:pk>/help/', DocumentHelpView.as_view()),
    path('scholarship/income/<str:member>/help/', IncomeClusterHelpView.as_view()),
    path('scholarship/referees/', RefereeListCreateView.as_view()),
    path('scholarship/consent/', ConsentView.as_view()),
    # Phase E3: the student's award offer (accept/decline; guardian-gated for minors)
    path('scholarship/award/', StudentAwardView.as_view()),
    # S3: the student's resolution queue (IBKR Action Centre)
    path('scholarship/resolution-items/', ResolutionItemListView.as_view()),
    path('scholarship/resolution-items/<int:pk>/resolve/', ResolutionItemResolveView.as_view()),

    # Phase E: sponsor accounts (authenticated self-registration + own status)
    path('sponsor/register/', SponsorRegisterView.as_view()),
    path('sponsor/me/', SponsorMeView.as_view()),
    path('sponsor/notifications/', SponsorNotificationsView.as_view()),  # F3: notify preference
    path('sponsor/pool/count/', SponsorPoolCountView.as_view()),  # F1: public landing counter
    path('sponsor/pool/', SponsorPoolListView.as_view()),
    path('sponsor/pool/<int:pk>/', SponsorPoolDetailView.as_view()),
    # Phase E3: wallet + funding (flag + approved-sponsor gated)
    path('sponsor/wallet/', SponsorWalletView.as_view()),
    path('sponsor/graduation-messages/', SponsorGraduationMessagesView.as_view()),  # F9a relay
    path('sponsor/referrals/', SponsorReferralView.as_view()),  # F4 referral/invite
    path('sponsor/wallet/donate/', SponsorDonateView.as_view()),
    path('sponsor/pool/<int:pk>/fund/', SponsorFundView.as_view()),
    path('sponsor/sponsorships/', SponsorSponsorshipsView.as_view()),
    path('sponsor/sponsorships/<int:pk>/cancel/', SponsorCancelOfferView.as_view()),

    # Internal cron — Cloud Scheduler runs whitelisted commands via a shared
    # secret header (X-Cron-Secret). Inert without the secret.
    path('internal/cron/<str:job>/', CronRunView.as_view()),

    # MyNadi admin (PartnerAdmin auth; /admin/ is NRIC-gate whitelisted)
    # Phase E: sponsor account vetting
    path('admin/sponsors/', AdminSponsorListView.as_view()),
    path('admin/sponsors/<int:pk>/review/', AdminSponsorReviewView.as_view()),
    # Phase E3: match oversight + set the award amount
    path('admin/sponsorships/', AdminSponsorshipListView.as_view()),
    path('admin/scholarship/applications/<int:pk>/award-amount/', AdminSetAwardAmountView.as_view()),
    path('admin/scholarship/assignable-admins/', AdminAssignableAdminsView.as_view()),
    path('admin/scholarship/applications/', AdminApplicationListView.as_view()),
    path('admin/scholarship/applications/<int:pk>/', AdminApplicationDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/verify-accept/', AdminVerifyAcceptView.as_view()),
    path('admin/scholarship/applications/<int:pk>/reject/', AdminRejectView.as_view()),
    # F7: super-only audited reviewer (re)assignment.
    path('admin/scholarship/applications/<int:pk>/assign/', AdminAssignReviewerView.as_view()),
    path('admin/scholarship/applications/<int:pk>/referees/', AdminApplicationRefereeView.as_view()),
    path('admin/scholarship/applications/<int:pk>/referees/<int:ref_id>/', AdminRefereeDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/documents/<int:doc_id>/re-run-vision/', AdminRunVisionView.as_view()),
    path('admin/scholarship/applications/<int:pk>/generate-profile/', AdminGenerateProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/finalise-profile/', AdminFinaliseProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/suggest-gaps/', AdminSuggestGapsView.as_view()),
    path('admin/scholarship/applications/<int:pk>/profile/', AdminProfileEditView.as_view()),
    path('admin/scholarship/applications/<int:pk>/publish/', AdminPublishProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/anon-profile/generate/', AdminGenerateAnonProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/anon-profile/publish/', AdminPublishAnonProfileView.as_view()),
    # Phase C: interview capture + request-more-docs
    path('admin/scholarship/applications/<int:pk>/interview/', AdminInterviewView.as_view()),
    path('admin/scholarship/applications/<int:pk>/interview/submit/', AdminInterviewSubmitView.as_view()),
    path('admin/scholarship/applications/<int:pk>/request-info/', AdminRequestInfoView.as_view()),
    # S3: officer-raised resolution tickets + waive/resolve
    path('admin/scholarship/applications/<int:pk>/resolution-items/', AdminResolutionItemView.as_view()),
    path('admin/scholarship/resolution-items/<int:item_id>/<str:action>/', AdminResolutionItemActionView.as_view()),
    # S5: officer records the verification verdict (+ optional finalise) + override metrics
    path('admin/scholarship/applications/<int:pk>/record-verdict/', AdminRecordVerdictView.as_view()),
    path('admin/scholarship/verdict-metrics/', AdminVerdictMetricsView.as_view()),
    # F6: a reviewer's own credentials + contact profile (self-scoped, reviewer/super).
    path('admin/reviewer-profile/', ReviewerProfileView.as_view()),
    # F9a — graduation thank-you moderation queue
    path('admin/graduation-messages/', AdminGraduationMessageListView.as_view()),
    path('admin/graduation-messages/<int:pk>/review/', AdminGraduationMessageReviewView.as_view()),
]
