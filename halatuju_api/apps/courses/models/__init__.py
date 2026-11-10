"""Database models for HalaTuju courses and eligibility.

All data lives in Supabase PostgreSQL. Audit sprint A3.7 turned `models.py` into this package with no
migration change (app label, model names, Meta, db_table and field order kept). Models:
- FieldTaxonomy (canonical field classification)
- Course, CourseRequirement, CourseTag
- StpmCourse, StpmRequirement
- Institution, CourseInstitution
- MascoOccupation (M2M via Course.career_occupations)
- StudentProfile, SavedCourse
"""

# Everything the old module imported stays reachable under its old name.
from django.db import models
from django.db.models import Q, Value
from ..exam_questions import EXAM_CHOICES, INSTITUTION_TYPE_CHOICES
from ..stpm_pngk import stpm_cgpa_of
from ..utils import tidy_parentage_marker

# The classes and functions, each from the module it moved to.
from .catalogue import (
    FieldTaxonomy,
    Course,
    MascoOccupation,
    CourseRequirement,
    Institution,
    CourseInstitution,
)
from .organisations import (
    PartnerOrganisationQuerySet,
    PartnerOrganisation,
    OrganisationTheme,
    OrganisationConfiguration,
)
from .student import StudentProfile, EmailVerification
from .outcomes import SavedCourse, AdmissionOutcome, CourseDataStatus

# Re-exports that sat at the foot of the old module, kept in the same order.
from ..models_claim import ProfileClaimEvent, ProfileLoginAlias
from ..models_stpm import StpmCourse, StpmRequirement
from ..models_staff import PartnerAdmin, ReviewerGift
from ..models_course_tag import CourseTag

# What the old module exposed, so a star-import and a reader both see the same list.
__all__ = [
    'AdmissionOutcome',
    'Course',
    'CourseDataStatus',
    'CourseInstitution',
    'CourseRequirement',
    'CourseTag',
    'EmailVerification',
    'EXAM_CHOICES',
    'FieldTaxonomy',
    'Institution',
    'INSTITUTION_TYPE_CHOICES',
    'MascoOccupation',
    'models',
    'OrganisationConfiguration',
    'OrganisationTheme',
    'PartnerAdmin',
    'PartnerOrganisation',
    'PartnerOrganisationQuerySet',
    'ProfileClaimEvent',
    'ProfileLoginAlias',
    'Q',
    'ReviewerGift',
    'SavedCourse',
    'stpm_cgpa_of',
    'StpmCourse',
    'StpmRequirement',
    'StudentProfile',
    'tidy_parentage_marker',
    'Value',
]
