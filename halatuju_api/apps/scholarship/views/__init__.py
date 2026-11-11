"""B40 Assistance Programme API: the student-facing views, split by area (audit A3.2).

This package replaced the single `views.py`. Every name that module held is re-exported here, so
`from apps.scholarship.views import X`, the URLconf and tests that name `apps.scholarship.views.X`
keep working. A `mock.patch` of a name a view LOOKS UP (not a class attribute) must target the
submodule that holds the view, e.g. `apps.scholarship.views.consent.consent_blockers`.
"""
from .common import (
    _log_coach_serve,
    _get_profile,
    _FUNDED_STATES,
    SET_ASIDE_STATES,
    AmbiguousApplication,
    _current_application,
)
from .intake import (
    WhatsAppInboundView,
    _open_round_choices,
    ScholarshipIntakeView,
)
from .applications import (
    ApplicationListCreateView,
    ApplicationDetailView,
    IncomeRouteSwitchView,
    ApplicationConfirmView,
    ApplicationOnboardingCompleteView,
)
from .interview import (
    _StudentInterviewBase,
    StudentInterviewView,
    StudentInterviewBookView,
    StudentInterviewCancelView,
    StudentInterviewRequestAlternativesView,
    StudentInterviewMessageView,
)
from .in_programme import (
    _OwnInProgrammeView,
    SemesterResultView,
    PromotionalConsentView,
    GraduationMessageView,
)
from .document_attempts import (
    _note_unresolved_attempts,
    _open_doc_request_items,
    _stage_attempts_exhausted,
    _flag_needs_officer_eye,
)
from .document_rules import (
    BILL_DOC_TYPES,
    _BYPASS_JUDGE_TYPES,
    RELATIONSHIP_DOC_TYPES,
    _reslot_income_doc,
    _ACADEMIC_SINGLE_TYPES,
    _collapse_duplicate_docs,
    SUPPORTING_NAME_CHECK_TYPES,
    TEXT_READ_DOC_TYPES,
    _ALLOWED_UPLOAD_EXTENSIONS,
    _is_allowed_upload,
)
from .documents import (
    DocumentSignUploadView,
    DocumentListCreateView,
    DocumentReadView,
    DocumentDetailView,
)
from .resolution import (
    ResolutionItemListView,
    ResolutionItemResolveView,
)
from .help import (
    DocumentHelpView,
    IncomeClusterHelpView,
)
from .consent import (
    ConsentView,
)
from .cron import (
    CronRunView,
    VircleAirtableUpdateView,
)
from .award import (
    BankAccountView,
    StudentComprehensionQuizView,
    StudentComprehensionView,
    _mask_phone,
    GuarantorPhoneVerifyStartView,
    GuarantorPhoneVerifyCheckView,
    StudentAwardView,
    BursaryAgreementView,
)

# Every name above is a re-export (the old views.py namespace), so ruff reads them as used.
__all__ = [n for n in dir() if not n.startswith("__")]
