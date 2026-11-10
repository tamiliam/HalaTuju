"""The people and identity getters of the cockpit payload (names, school, source, funding need, sponsor profile)."""

from apps.courses.public import spm_grades_for
from ..models import FundingNeed, SponsorProfile
from ..serializers import FundingNeedSerializer
from .application_list import SponsorProfileSerializer, _application_merit_score, held_qualification
from .names import _admin_name_by_email, _full_name, _verified_email


class ServesTheDetailPeople:
    """The people and identity getters of the cockpit payload. Moved out of AdminApplicationDetailSerializer unchanged (audit A3.7)."""

    def get_name(self, obj):
        return _full_name(obj)

    def get_verified_by_name(self, obj):
        return _admin_name_by_email(obj.verified_by)

    def get_verdict_decided_by_name(self, obj):
        return _admin_name_by_email(obj.verdict_decided_by)

    def get_recommended_by_name(self, obj):
        return _admin_name_by_email(obj.recommended_by)

    def get_qc_override_by_name(self, obj):
        return _admin_name_by_email(obj.qc_override_by)

    def get_rejected_by_name(self, obj):
        return _admin_name_by_email(obj.rejected_by)

    def get_school(self, obj):
        return getattr(obj.profile, 'school', '') if obj.profile else ''

    def get_birth_state(self, obj):
        from ..birth_state import for_cockpit
        return for_cockpit(getattr(obj.profile, 'nric', '') if obj.profile else '',
                           getattr(obj.cohort, 'allowed_birth_states', None))

    @staticmethod
    def _org_dict(org):
        return {'id': org.id, 'code': org.code, 'name': org.name} if org else None

    def get_source(self, obj):
        return self._org_dict(obj.source)

    def get_witness_org(self, obj):
        return self._org_dict(obj.witness_org)

    def get_spm_a_count(self, obj):
        from ..shortlisting import count_spm_a_grades
        return count_spm_a_grades(spm_grades_for(obj.profile))   # tertiary: SPM prereq only (#62)

    def get_qualification(self, obj):
        return held_qualification(obj.profile)

    def get_overall_cgpa(self, obj):
        from apps.courses.public import overall_cgpa
        return overall_cgpa(getattr(obj, 'profile', None))

    def get_merit_score(self, obj):
        return _application_merit_score(obj)

    def get_guardian_needs_call(self, obj):
        from ..parent_call import needs_parent_call
        return needs_parent_call(obj.profile)

    def get_verified_email(self, obj):
        """The verified email to display on the admin card (see _verified_email)."""
        return _verified_email(obj)

    def get_funding_need(self, obj):
        try:
            return FundingNeedSerializer(obj.funding_need).data
        except FundingNeed.DoesNotExist:
            return None

    def get_sponsor_profile(self, obj):
        try:
            return SponsorProfileSerializer(obj.sponsor_profile).data
        except SponsorProfile.DoesNotExist:
            return None
