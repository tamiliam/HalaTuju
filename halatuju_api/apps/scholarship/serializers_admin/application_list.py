"""The officer list: the sponsor profile, the held qualification and the application list row."""

from rest_framework import serializers
from apps.courses import public as courses_public
from ..models import ScholarshipApplication, SponsorProfile
from .. import serializers_admin_gift as _gift
from .names import _full_name


class SponsorProfileSerializer(serializers.ModelSerializer):
    current_markdown = serializers.CharField(read_only=True)

    class Meta:
        model = SponsorProfile
        fields = [
            'draft_markdown', 'edited_markdown', 'current_markdown', 'status',
            'model_used', 'generated_at', 'published_at', 'updated_at',
            'final_markdown', 'final_model_used', 'finalised_at', 'finalise_state',  # A2.1: '' / pending / failed; A2.3b: drafting
            # Phase E2 anonymous (sponsor-pool) profile — admin-facing here.
            'anon_markdown', 'anon_model_used', 'anon_generated_at',
            'anon_published', 'anon_published_at',
        ]


# ⚠ `held_qualification` IS `apps.courses.exam_questions.results_held` (TD-218, 2026-10-02). The rule — the
# recorded completion wins; else the declaration, corrected only where ABSENCE of STPM results is
# conclusive — moved there unchanged, with its reasons (BrightPath #14, #15, #106). The name stays
# because the admin label, the merit source below, the audit command and their tests call it.
#
# ⚠ IT IS NOW A GATE. A dated sequence, because the old warning is quoted elsewhere:
# * BrightPath #14 (2026-08-18) wrote it for the admin label and the merit ranking and said "NOT A
#   GATE, AND MUST NOT BECOME ONE": `shortlisting`, `pool`, `income_engine` and `vision` all read
#   `exam_type` for their own reasons, and widening this would re-band live applicants.
# * Now sprint 4 (2026-10-02, TD-218) asked each of those readers which question it means. The
#   income checks mean the exam she is heading for and read `heading_for`; the shortlist gate, the
#   sponsor band and the slip-parser gate mean the results she holds and were held on the
#   declaration pending a production count.
# * The same day the owner ruled "switch all three" (TD-324) on that count — 68 live applications
#   agree, 1 Form Six explorer (declared STPM, holds SPM), 0 the other way. So `shortlisting`
#   (who clears a programme's grade bar), `pool` (the sponsor's academic line) and `vision` (whether
#   the SPM slip parser runs) now read this rule. A change to it moves who is shortlisted and which
#   parser runs, not only a label: characterise it first (`tests/test_exam_questions.py`).
held_qualification = courses_public.results_held


def _application_merit_score(obj):
    """The application's merit, 0-100 on every route — `exam_questions.merit_100(obj.profile)`.

    The ONE definition lives there (third results route S1, 2026-10-25): SPM the course-guide
    merit (unchanged to the byte), STPM the overall CGPA / 4 x 100 (it was the raw PNGK before
    S1, so every STPM holder sorted below every SPM holder). None when there is nothing to score —
    absent, never 0 (#106). The list, the detail, the merit sort and the AI profile input all
    read this, so they cannot disagree."""
    from apps.courses import public
    return public.merit_100(getattr(obj, 'profile', None))


class AdminApplicationListSerializer(_gift.ServesTheCaseGifts, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    # Academic data is read live from the canonical profile, not the application.
    # The qualification we hold RESULTS for, not the one declared at sign-up — see
    # `held_qualification`. A Form Six student holds SPM results and reads SPM.
    qualification = serializers.SerializerMethodField()
    stpm_pngk = serializers.FloatField(source='profile.stpm_pngk', read_only=True)   # CGPA sprint C2
    overall_cgpa = serializers.SerializerMethodField()    # S2a: tertiary CGPA; None for SPM
    spm_a_count = serializers.SerializerMethodField()
    # Source (THIS application's answer, kept at submit — sources Sprint C) + the merit, for the list.
    referral_source = serializers.CharField(source='referral_code', read_only=True)
    merit_score = serializers.SerializerMethodField()
    # The student's preferred call language (en/ms/ta/mixed) — drives reviewer language matching.
    call_language = serializers.CharField(source='profile.preferred_call_language', read_only=True, allow_blank=True)
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)
    # May this case change hands at all right now (Completed / interviewing only)? Computed here
    # so the list UI disables the dropdown rather than re-deriving the rule — an action the server
    # will refuse should not look available. See services.ASSIGNABLE_STATUSES.
    assignable = serializers.SerializerMethodField()
    # First-assignment readiness (mirrors the detail cockpit): all student tasks done OR the org's
    # `query_answer_days` submit-clock lapsed. The list dropdown disables a FIRST assignment while false, so it never
    # offers an assign the server would refuse with 'not_ready' (= services.is_ready_for_assignment,
    # the same value the detail serializer ships inside query_sla).
    ready_for_assignment = serializers.SerializerMethodField()

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'profile_id', 'cohort_code', 'qualification',
            'spm_a_count', 'stpm_pngk', 'overall_cgpa', 'referral_source', 'merit_score',
            'call_language',
            'status', 'bucket', 'shortlist_reason',
            'submitted_at', 'profile_completed_at',
            'assigned_to_id', 'assigned_to_name', 'assignable', 'ready_for_assignment',
            # When set, the list pill shows "Reopened" (overriding accepted/rejected).
            'decision_reopened_at',
        ]

    def get_assignable(self, obj):
        from ..services import is_assignable
        return is_assignable(obj)

    def get_ready_for_assignment(self, obj):
        from ..services import is_ready_for_assignment
        return is_ready_for_assignment(obj)

    def get_name(self, obj):
        return _full_name(obj)

    def get_qualification(self, obj):
        return held_qualification(obj.profile)

    def get_overall_cgpa(self, obj):
        return courses_public.overall_cgpa(getattr(obj, 'profile', None))

    def get_merit_score(self, obj):
        return _application_merit_score(obj)

    def get_spm_a_count(self, obj):
        from ..shortlisting import count_spm_a_grades
        return count_spm_a_grades(courses_public.spm_grades_for(obj.profile))   # tertiary: SPM prereq only (#62)
