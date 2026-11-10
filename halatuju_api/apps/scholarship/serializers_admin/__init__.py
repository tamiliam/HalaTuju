"""Admin-facing serializers for the B40 Assistance Programme (Sprint 6a).

Audit sprint A3.7 turned the single file into this package; every body moved unchanged and every
old name is re-exported here, so `from apps.scholarship.serializers_admin import X` keeps working."""

# Everything the old module imported stays reachable under its old name.
from rest_framework import serializers
from apps.courses.public import results_held, spm_grades_for
from apps.courses.utils import tidy_parentage_marker
from ..models import (
    FundingNeed,
    GraduationMessage,
    InterviewSession,
    InterviewSlot,
    ReviewerProfile,
    ScholarshipApplication,
    SponsorProfile,
)
from .. import (
    pool,
    results_route as _notes,
    serializers_admin_family as _family,
    serializers_admin_gift as _gift,
    stpm_marks as _stpm,
)
from .. import serializers_org_requests, serializers_admin_decision_mail as _dmail
from ..sgd_conversion import AdminApplicantDocumentSerializer
from ..serializers import ConsentSerializer, FundingNeedSerializer, RefereeSerializer

# The classes and functions, each from the module it moved to.
from .names import _admin_name_by_email, _full_name, _verified_email
from .interviews import (
    InterviewSessionSerializer,
    InterviewSlotSerializer,
    interview_schedule_payload,
    _slot_rules_payload,
)
from .application_list import (
    SponsorProfileSerializer,
    held_qualification,
    _application_merit_score,
    AdminApplicationListSerializer,
)
from .application_detail import AdminApplicationDetailSerializer
from .records import (
    ReviewerProfileSerializer,
    AdminGraduationMessageSerializer,
    FundingSummaryRowSerializer,
)
from .detail_blocks import ServesTheDetailBlocks
from .detail_people import ServesTheDetailPeople

# ── Requests space (Sprint 15) ──────────────────────────────────
#
# Moved to `serializers_org_requests.py` on 2026-10-29 (moves only: this file was already ON
# its 1,234-line allowance). Bound as names rather than imported, so the re-export is a USED
# import and needs no F401 suppression — that count is a budget too.
_serialize_org_request_attachments = serializers_org_requests._serialize_org_request_attachments

_comment_dicts = serializers_org_requests._comment_dicts

OrgRequestOrgSerializer = serializers_org_requests.OrgRequestOrgSerializer

OrgRequestOwnerSerializer = serializers_org_requests.OrgRequestOwnerSerializer

# What the old module exposed, so a star-import and a reader both see the same list.
__all__ = [
    'AdminApplicantDocumentSerializer',
    'AdminApplicationDetailSerializer',
    'AdminApplicationListSerializer',
    'AdminGraduationMessageSerializer',
    'ConsentSerializer',
    'FundingNeed',
    'FundingNeedSerializer',
    'FundingSummaryRowSerializer',
    'GraduationMessage',
    'held_qualification',
    'interview_schedule_payload',
    'InterviewSession',
    'InterviewSessionSerializer',
    'InterviewSlot',
    'InterviewSlotSerializer',
    'OrgRequestOrgSerializer',
    'OrgRequestOwnerSerializer',
    'pool',
    'RefereeSerializer',
    'results_held',
    'ReviewerProfile',
    'ReviewerProfileSerializer',
    'ScholarshipApplication',
    'serializers',
    'serializers_org_requests',
    'ServesTheDetailBlocks',
    'ServesTheDetailPeople',
    'spm_grades_for',
    'SponsorProfile',
    'SponsorProfileSerializer',
    'tidy_parentage_marker',
    '_admin_name_by_email',
    '_application_merit_score',
    '_comment_dicts',
    '_dmail',
    '_family',
    '_full_name',
    '_gift',
    '_notes',
    '_serialize_org_request_attachments',
    '_slot_rules_payload',
    '_stpm',
    '_verified_email',
]
