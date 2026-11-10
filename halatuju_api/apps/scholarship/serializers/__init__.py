"""Serializers for B40 Assistance Programme intake.

Audit sprint A3.7 turned the single file into this package; every body moved unchanged and every
old name is re-exported here, so `from apps.scholarship.serializers import X` keeps working."""

# Everything the old module imported stays reachable under its old name.
from rest_framework import serializers
from apps.courses.public import ResultsHeldField, spm_grades_for
from .. import pool, results_review
from ..family import PROFESSION_CODES, form_guardians_shape
from ..serializers_maintenance import StudentMaintenanceFields
from ..models import (
    ApplicantDocument,
    BankAccount,
    Consent,
    FundingNeed,
    GraduationMessage,
    Referee,
    ResolutionItem,
    ScholarshipApplication,
    SemesterResult,
    Sponsor,
    SponsorReferral,
    StandingGift,
)

# The classes and functions, each from the module it moved to.
from .sponsor import (
    SponsorSerializer,
    _funding_need_or_none,
    _resolve_field_image_slug,
    SponsorPoolCardSerializer,
    SponsorPoolDetailSerializer,
    SponsorReferralSerializer,
    StandingGiftSerializer,
)
from .sponsor_students import (
    SponsorSponsorshipSerializer,
    SponsorMyStudentDetailSerializer,
    StudentAwardSerializer,
    BursaryAgreementSerializer,
    SemesterResultSerializer,
    GraduationMessageSerializer,
    GraduationRelaySerializer,
)
from .application import (
    ApplicationCreateSerializer,
    STORY_TEXT_MAX,
    FundingNeedSerializer,
    IncomeRouteSwitchSerializer,
    ApplicationDetailsUpdateSerializer,
)
from .application_read import ApplicationReadSerializer
from .documents import (
    ApplicantDocumentSerializer,
    SignUploadSerializer,
    DocumentCreateSerializer,
    ResolutionItemSerializer,
)
from .student_records import (
    BankAccountSerializer,
    BankAccountConfirmSerializer,
    RefereeSerializer,
    ConsentSerializer,
    ConsentCreateSerializer,
)

# What the old module exposed, so a star-import and a reader both see the same list.
__all__ = [
    'ApplicantDocument',
    'ApplicantDocumentSerializer',
    'ApplicationCreateSerializer',
    'ApplicationDetailsUpdateSerializer',
    'ApplicationReadSerializer',
    'BankAccount',
    'BankAccountConfirmSerializer',
    'BankAccountSerializer',
    'BursaryAgreementSerializer',
    'Consent',
    'ConsentCreateSerializer',
    'ConsentSerializer',
    'DocumentCreateSerializer',
    'form_guardians_shape',
    'FundingNeed',
    'FundingNeedSerializer',
    'GraduationMessage',
    'GraduationMessageSerializer',
    'GraduationRelaySerializer',
    'IncomeRouteSwitchSerializer',
    'pool',
    'PROFESSION_CODES',
    'Referee',
    'RefereeSerializer',
    'ResolutionItem',
    'ResolutionItemSerializer',
    'results_review',
    'ResultsHeldField',
    'ScholarshipApplication',
    'SemesterResult',
    'SemesterResultSerializer',
    'serializers',
    'SignUploadSerializer',
    'spm_grades_for',
    'Sponsor',
    'SponsorMyStudentDetailSerializer',
    'SponsorPoolCardSerializer',
    'SponsorPoolDetailSerializer',
    'SponsorReferral',
    'SponsorReferralSerializer',
    'SponsorSerializer',
    'SponsorSponsorshipSerializer',
    'StandingGift',
    'StandingGiftSerializer',
    'STORY_TEXT_MAX',
    'StudentAwardSerializer',
    'StudentMaintenanceFields',
    '_funding_need_or_none',
    '_resolve_field_image_slug',
]
