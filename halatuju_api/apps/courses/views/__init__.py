"""The course-guide API: the views, split by page (audit A3.5).

This package replaced the single `views.py`. Every name that module held is re-exported here, so
`from apps.courses.views import X`, the URLconf and tests that name `apps.courses.views.X` keep working.
A `mock.patch` of a name a view LOOKS UP (not a class attribute) must target the submodule that holds
the view. Every logger in the package keeps the old name, `apps.courses.views`.
"""
import logging

from .course_search import (
    SOURCE_TYPE_ORDER,
    _tvet_pick_list,
    FieldListView,
    CourseSearchView,
)

from .eligibility import (
    EligibilityCheckView,
    RankingView,
)

from .quiz import (
    QuizQuestionsView,
    QuizSubmitView,
    _persist_quiz_signals,
)

from .catalogue import (
    CourseListView,
    CourseDetailView,
    InstitutionListView,
    InstitutionDetailView,
)

from .saved_courses import (
    SavedCoursesView,
    SavedCourseDetailView,
)

from .profile import (
    ProfileView,
    ProfileSyncView,
)

from .nric_claim import (
    NricClaimView,
    NricClaimSendCodeView,
    NricClaimConfirmCodeView,
)

from .verification import (
    VERIFICATION_EMAIL_SUBJECTS,
    VERIFICATION_EMAIL_BODIES,
    SendVerificationView,
    VerifyEmailView,
    PhoneVerifyStartView,
    PhoneVerifyCheckView,
)

from .outcomes import (
    OutcomeListView,
    OutcomeDetailView,
)

from .stpm import (
    StpmEligibilityCheckView,
    StpmRankingView,
    StpmSearchView,
    StpmCourseDetailView,
)

from .calculate import (
    CalculateMeritView,
    CalculateCgpaView,
    CalculatePathwaysView,
)

logger = logging.getLogger('apps.courses.views')
