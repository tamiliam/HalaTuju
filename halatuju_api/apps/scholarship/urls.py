"""URL routing for the B40 Assistance Programme API."""
from django.urls import path

from .views import (
    ApplicationConfirmView,
    ApplicationDetailView,
    ApplicationListCreateView,
    ConsentView,
    CronRunView,
    DocumentDetailView,
    DocumentListCreateView,
    DocumentSignUploadView,
    RefereeListCreateView,
    SponsorInterestView,
)
from .views_admin import (
    AdminApplicationDetailView,
    AdminApplicationListView,
    AdminApplicationRefereeView,
    AdminAssignableAdminsView,
    AdminGenerateProfileView,
    AdminInterviewView,
    AdminInterviewSubmitView,
    AdminProfileEditView,
    AdminPublishProfileView,
    AdminRefereeDetailView,
    AdminRequestInfoView,
    AdminRunVisionView,
    AdminSponsorInterestView,
    AdminSuggestGapsView,
    AdminVerifyAcceptView,
)

urlpatterns = [
    path('scholarship/applications/', ApplicationListCreateView.as_view()),
    path('scholarship/applications/<int:pk>/', ApplicationDetailView.as_view()),
    path('scholarship/applications/<int:pk>/confirm/', ApplicationConfirmView.as_view()),
    path('scholarship/documents/sign-upload/', DocumentSignUploadView.as_view()),
    path('scholarship/documents/', DocumentListCreateView.as_view()),
    path('scholarship/documents/<int:pk>/', DocumentDetailView.as_view()),
    path('scholarship/referees/', RefereeListCreateView.as_view()),
    path('scholarship/consent/', ConsentView.as_view()),
    # Public sponsor-interest lead capture (no auth)
    path('sponsor-interest/', SponsorInterestView.as_view()),

    # Internal cron — Cloud Scheduler runs whitelisted commands via a shared
    # secret header (X-Cron-Secret). Inert without the secret.
    path('internal/cron/<str:job>/', CronRunView.as_view()),

    # MyNadi admin (PartnerAdmin auth; /admin/ is NRIC-gate whitelisted)
    path('admin/sponsor-interest/', AdminSponsorInterestView.as_view()),
    path('admin/scholarship/assignable-admins/', AdminAssignableAdminsView.as_view()),
    path('admin/scholarship/applications/', AdminApplicationListView.as_view()),
    path('admin/scholarship/applications/<int:pk>/', AdminApplicationDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/verify-accept/', AdminVerifyAcceptView.as_view()),
    path('admin/scholarship/applications/<int:pk>/referees/', AdminApplicationRefereeView.as_view()),
    path('admin/scholarship/applications/<int:pk>/referees/<int:ref_id>/', AdminRefereeDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/documents/<int:doc_id>/re-run-vision/', AdminRunVisionView.as_view()),
    path('admin/scholarship/applications/<int:pk>/generate-profile/', AdminGenerateProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/suggest-gaps/', AdminSuggestGapsView.as_view()),
    path('admin/scholarship/applications/<int:pk>/profile/', AdminProfileEditView.as_view()),
    path('admin/scholarship/applications/<int:pk>/publish/', AdminPublishProfileView.as_view()),
    # Phase C: interview capture + request-more-docs
    path('admin/scholarship/applications/<int:pk>/interview/', AdminInterviewView.as_view()),
    path('admin/scholarship/applications/<int:pk>/interview/submit/', AdminInterviewSubmitView.as_view()),
    path('admin/scholarship/applications/<int:pk>/request-info/', AdminRequestInfoView.as_view()),
]
