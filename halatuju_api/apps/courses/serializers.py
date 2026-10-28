"""
Serializers for the courses API.
"""
import re
from types import SimpleNamespace

from rest_framework import serializers

from .exam_questions import QUALIFICATIONS, THIRD_ROUTE, is_tertiary, results_held
from .models import Course, FieldTaxonomy, Institution, CourseRequirement, CourseTag, MascoOccupation, StudentProfile

#: The shape of an SPM subject key as the web catalogue writes them ('bm', 'b_tamil', 'addmath').
_SUBJECT_KEY = re.compile(r'[a-z0-9_]{1,40}')
#: A sanity bound on the STPM path's SPM lists — NOT the form's cap of 7 (that is the web's
#: MAX_SPM_ELECTIVES and is not copied here). Far above any real entry, far below abuse.
_MAX_SPM_ENTRIES = 20


class FieldTaxonomySerializer(serializers.ModelSerializer):
    """Serializer for FieldTaxonomy entries."""
    children = serializers.SerializerMethodField()

    class Meta:
        model = FieldTaxonomy
        fields = [
            'key', 'name_en', 'name_ms', 'name_ta',
            'image_slug', 'parent_key', 'sort_order', 'children',
        ]

    def get_children(self, obj):
        """Return child entries for parent groups."""
        if obj.parent_key is not None:
            return []
        children = FieldTaxonomy.objects.filter(parent_key=obj.key).order_by('sort_order')
        return FieldTaxonomySerializer(children, many=True).data


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""
    course_name = serializers.CharField(source='course', read_only=True)

    class Meta:
        model = Course
        fields = [
            'course_id', 'course', 'course_name', 'wbl', 'level', 'department',
            'field', 'field_key', 'semesters',
            'headline', 'headline_en', 'description', 'description_en',
        ]


class MascoOccupationSerializer(serializers.ModelSerializer):
    """Serializer for MASCO occupation."""

    class Meta:
        model = MascoOccupation
        fields = ['masco_code', 'job_title', 'emasco_url']


class InstitutionSerializer(serializers.ModelSerializer):
    """Serializer for Institution model."""

    class Meta:
        model = Institution
        fields = [
            'institution_id', 'institution_name', 'acronym', 'type',
            'category', 'subcategory', 'state', 'address', 'phone',
            'url', 'latitude', 'longitude'
        ]


class CourseRequirementSerializer(serializers.Serializer):
    """
    Serializes CourseRequirement into structured general/special groups.
    Only includes truthy (non-default) fields.
    """

    # General requirement fields → BM labels
    GENERAL_FIELDS = {
        'req_malaysian': 'Warganegara Malaysia',
        'req_male': 'Lelaki sahaja',
        'req_female': 'Perempuan sahaja',
        'no_colorblind': 'Tidak buta warna',
        'no_disability': 'Tidak cacat fizikal',
        'single': 'Belum berkahwin',
    }

    # Special requirement fields → BM labels
    SPECIAL_FIELDS = {
        # Core pass
        'pass_bm': 'Lulus Bahasa Melayu',
        'pass_history': 'Lulus Sejarah',
        'pass_eng': 'Lulus Bahasa Inggeris',
        'pass_math': 'Lulus Matematik',
        'pass_sci': 'Lulus Sains',
        'pass_islam': 'Lulus Pendidikan Islam',
        'pass_moral': 'Lulus Pendidikan Moral',
        # Credit
        'credit_bm': 'Kredit Bahasa Melayu',
        'credit_english': 'Kredit Bahasa Inggeris',
        'credit_math': 'Kredit Matematik',
        'credit_addmath': 'Kredit Matematik Tambahan',
        'credit_sci': 'Kredit Sains',
        'credit_islam': 'Kredit Pendidikan Islam',
        'credit_moral': 'Kredit Pendidikan Moral',
        # Composite OR-groups (simple flags)
        'credit_stv': 'Kredit Sains/Teknikal/Vokasional',
        'credit_sf': 'Kredit Sains atau Fizik',
        'credit_sfmt': 'Kredit Sains/Fizik/Matematik Tambahan',
        'credit_bmbi': 'Kredit BM atau BI',
        'credit_science_group': 'Kredit kumpulan Sains',
        'credit_math_or_addmath': 'Kredit Matematik atau Matematik Tambahan',
        # TVET composite
        'pass_math_addmath': 'Lulus Matematik atau Matematik Tambahan',
        'pass_science_tech': 'Lulus Sains atau subjek Teknikal',
        'pass_math_science': 'Lulus Matematik atau Sains',
        'credit_math_sci': 'Kredit Matematik atau Sains',
        'credit_math_sci_tech': 'Kredit Matematik/Sains/Teknikal',
        'pass_stv': 'Lulus Sains/Teknikal/Vokasional',
        'three_m_only': 'Boleh membaca, menulis dan mengira (3M)',
        # Grade B
        'credit_bm_b': 'Gred B+ Bahasa Melayu',
        'credit_eng_b': 'Gred B+ Bahasa Inggeris',
        'credit_math_b': 'Gred B+ Matematik',
        'credit_addmath_b': 'Gred B+ Matematik Tambahan',
        # Distinction
        'distinction_bm': 'Cemerlang (A-) Bahasa Melayu',
        'distinction_eng': 'Cemerlang (A-) Bahasa Inggeris',
        'distinction_math': 'Cemerlang (A-) Matematik',
        'distinction_addmath': 'Cemerlang (A-) Matematik Tambahan',
        'distinction_phy': 'Cemerlang (A-) Fizik',
        'distinction_chem': 'Cemerlang (A-) Kimia',
        'distinction_bio': 'Cemerlang (A-) Biologi',
        'distinction_sci': 'Cemerlang (A-) Sains',
    }

    def to_representation(self, instance):
        general = []
        special = []

        # Demographic / general flags
        for field, label in self.GENERAL_FIELDS.items():
            if getattr(instance, field, False):
                general.append({'key': field, 'label': label})

        # Min credits / min pass
        if instance.min_credits and instance.min_credits > 0:
            general.append({
                'key': 'min_credits',
                'label': f'Minimum {instance.min_credits} kredit SPM',
                'value': instance.min_credits,
            })
        if instance.min_pass and instance.min_pass > 0:
            general.append({
                'key': 'min_pass',
                'label': f'Minimum {instance.min_pass} lulus SPM',
                'value': instance.min_pass,
            })

        # Academic / special flags
        for field, label in self.SPECIAL_FIELDS.items():
            if getattr(instance, field, False):
                special.append({'key': field, 'label': label})

        # Advisory
        if instance.req_interview:
            special.append({'key': 'req_interview', 'label': 'Temuduga diperlukan'})

        return {
            'source_type': getattr(instance, 'source_type', ''),
            'general': general,
            'special': special,
            'complex_requirements': instance.complex_requirements,
            'subject_group_req': instance.subject_group_req,
            'merit_cutoff': instance.merit_cutoff,
            'remarks': instance.remarks or '',
        }


# Frontend → engine value maps. The engine compares against the Malay forms
# ('Lelaki'/'Perempuan', 'Warganegara'/'Bukan Warganegara'), so every entry point
# that feeds the engine raw profile values must normalise first. Shared so the SPM
# serializer and the STPM view (which has no serializer) can't drift apart.
GENDER_MAP = {
    'male': 'Lelaki', 'female': 'Perempuan',
    'lelaki': 'Lelaki', 'perempuan': 'Perempuan',
    'ஆண்': 'Lelaki', 'பெண்': 'Perempuan',
}
NATIONALITY_MAP = {
    'malaysian': 'Warganegara', 'non_malaysian': 'Bukan Warganegara',
    'non-malaysian': 'Bukan Warganegara',
    'warganegara': 'Warganegara', 'bukan warganegara': 'Bukan Warganegara',
}


def normalize_gender(value):
    """Map a frontend/profile gender to the engine's value (idempotent)."""
    return GENDER_MAP.get((value or '').lower(), value)


def normalize_nationality(value):
    """Map a frontend/profile nationality to the engine's value (idempotent)."""
    return NATIONALITY_MAP.get((value or '').lower(), value)


class EligibilityRequestSerializer(serializers.Serializer):
    """
    Serializer for eligibility check request.

    Validates the student profile data sent to the eligibility endpoint.
    Accepts multiple input formats and normalizes to engine-expected values.
    """
    grades = serializers.DictField(
        child=serializers.CharField(),
        required=True,
        help_text="SPM grades: {'bm': 'A+', 'math': 'B', ...}"
    )
    gender = serializers.CharField(default='Lelaki')
    nationality = serializers.CharField(default='Warganegara')
    colorblind = serializers.BooleanField(default=False, required=False)
    disability = serializers.BooleanField(default=False, required=False)
    other_tech = serializers.BooleanField(default=False)
    other_voc = serializers.BooleanField(default=False)
    coq_score = serializers.FloatField(default=5.0, required=False,
        help_text="Co-curricular score (0-10). Defaults to 5.0 if not provided."
    )
    student_merit = serializers.FloatField(required=False, default=None,
        help_text="Pre-computed merit score from frontend (0-100). If provided, backend skips recalculation."
    )

    def validate_coq_score(self, value):
        """Clamp CoQ to 0-10 range."""
        return min(max(float(value), 0), 10.0)

    def validate_gender(self, value):
        """Normalize gender to engine format."""
        return normalize_gender(value)

    def validate_nationality(self, value):
        """Normalize nationality to engine format."""
        return normalize_nationality(value)

    def to_internal_value(self, data):
        """Drop explicit nulls before validation.

        The apply form posts the **full** student profile, where optional fields
        (`coq_score`, `colorblind`, `student_merit`, …) are legitimately ``null``
        for students who never set them. DRF would reject those with "may not be
        null" and 400 the whole eligibility check. Stripping nulls lets each field
        fall back to its declared default instead — e.g. a null `coq_score` becomes
        the 5.0 default rather than blocking the request. (`grades` is required, so
        a null/absent `grades` still correctly errors.)
        """
        if hasattr(data, 'items'):
            data = {k: v for k, v in data.items() if v is not None}
        return super().to_internal_value(data)


class EligibilityResponseSerializer(serializers.Serializer):
    """Serializer for eligibility check response."""
    eligible_courses = serializers.ListField()
    total_count = serializers.IntegerField()
    stats = serializers.DictField()


class RankingRequestSerializer(serializers.Serializer):
    """
    Serializer for ranking request.

    Validates the eligible courses list and student signals
    sent to the ranking endpoint.
    """
    eligible_courses = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text="List of eligible course dicts from eligibility check",
    )
    student_signals = serializers.DictField(
        required=True,
        help_text="Categorised student signals from quiz",
    )

    def validate_eligible_courses(self, value):
        """Ensure each course dict has a course_id."""
        if not value:
            raise serializers.ValidationError("eligible_courses must not be empty.")
        for i, course in enumerate(value):
            if 'course_id' not in course:
                raise serializers.ValidationError(
                    f"eligible_courses[{i}] missing course_id."
                )
        return value


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for profile update (PUT /profile/ and POST /profile/sync/).

    Validates field types and constrains values to prevent 500 errors
    from malformed input (e.g. string for siblings, invalid JSON for grades).
    """

    # TD-069 review F3: declared here WITHOUT the model's max_length, so an over-long label reaches
    # `validate_spm_stream` and is DROPPED there, instead of 400-ing the whole sync first.
    spm_stream = serializers.CharField(required=False, allow_blank=True)
    # Third results route S2a: range-checked here (a CGPA is 0-4, co-curriculum 0-10); an
    # out-of-range number is REFUSED, like any other malformed field — the form never sends one.
    higher_cgpa = serializers.FloatField(required=False, allow_null=True, min_value=0,
                                         max_value=4)
    higher_koko = serializers.FloatField(required=False, allow_null=True, min_value=0,
                                         max_value=10)

    def validate(self, attrs):
        """⚠ `results_exam_type` MUST BE BACKED BY RESULTS, and that is checked HERE — on the
        server — because the whole value of the field is that it cannot be set by a selection.

        The browser sets it when a results form is completed, and both forms refuse to continue
        until they are; but a promise kept only in the client is not a guarantee, and this field
        exists precisely because `exam_type` had no such guarantee. Checked against the payload
        MERGED with what is already stored, since a partial sync may carry the results, the
        marker, or both.

        An unbacked value is DROPPED, not rejected: the marker is a refinement, and failing a
        student's whole profile sync over it would trade a display fault for a data-loss one.
        """
        inst = self.instance
        self._refuse_third_route_while_closed(attrs)

        def _merged(field):
            return attrs[field] if field in attrs else getattr(inst, field, None)

        def _backed(q):
            if q == 'stpm':
                return bool(_merged('stpm_grades') or {}) or _merged('stpm_cgpa') is not None
            if q in THIRD_ROUTE:                        # third results route S2a
                return _merged('higher_cgpa') is not None
            return bool(_merged('grades') or {}) or bool(_merged('spm_prereq_grades') or {})

        claimed = (attrs.get('results_exam_type') or '').strip().lower()
        if claimed and claimed != 'spm' and not _backed(claimed):
            attrs.pop('results_exam_type', None)
        elif claimed == 'spm' and not bool(_merged('grades') or {}):
            attrs.pop('results_exam_type', None)      # SPM's marker: `grades` only, as before S2a
        self._one_higher_qualification(attrs)

        # S2a: `completed_qualifications` is what "highest" ranks over (`results_held`), so it is
        # kept IN STEP ON EVERY WRITE, not only when sent (review round 1): an entry whose results
        # are gone is PRUNED (presence never promotes, #15; nor does a stale entry); one third-route
        # kind at a time — `higher_cgpa` holds one CGPA — the recorded one when it is one; and an
        # STPM holder the old rule reads as STPM keeps 'stpm' while STPM data backs it, so a list
        # that omits it can never demote her. A blank list stays blank (the old rule, D1).
        # A third-route marker (a new value; no legacy row holds one) goes when its CGPA goes.
        marker = _merged('results_exam_type') or ''
        if marker in THIRD_ROUTE and not _backed(marker):
            attrs['results_exam_type'] = ''
        stored = list(getattr(inst, 'completed_qualifications', None) or []) if inst else []
        base = attrs.get('completed_qualifications', stored)
        if base:
            recorded = (_merged('results_exam_type') or '').strip().lower()
            done = [q for q in base if _backed(q)]
            legacy = SimpleNamespace(
                exam_type=_merged('exam_type'), results_exam_type=recorded, grades=_merged('grades'),
                stpm_grades=_merged('stpm_grades'), stpm_cgpa=_merged('stpm_cgpa'),
                higher_cgpa=_merged('higher_cgpa'), completed_qualifications=[])
            if 'stpm' not in done and _backed('stpm') and results_held(legacy) == 'stpm':
                done.append('stpm')
            if recorded in THIRD_ROUTE and recorded not in done and _backed(recorded):
                done.append(recorded)                 # the recorded completion is a completion
            third = [q for q in done if q in THIRD_ROUTE]
            if len(third) > 1 or (recorded in THIRD_ROUTE and third and third != [recorded]):
                keep = recorded if recorded in THIRD_ROUTE else third[-1]
                done = [q for q in done if q not in THIRD_ROUTE or q == keep]
            if done != stored or 'completed_qualifications' in attrs:
                attrs['completed_qualifications'] = done
        self._never_demote_held_results(attrs, _merged, _backed)
        self._stpm_cgpa_from_grades(attrs, _merged)
        return attrs

    @staticmethod
    def _stpm_cgpa_from_grades(attrs, _merged):
        """⚠ THE STPM CGPA IS WORKED OUT, NEVER TYPED (STPM CGPA sprint C2, owner 2026-10-28). A
        write touching the STPM results stores the PNGK of the grades it leaves on file (Pengajian
        Am + best three, `stpm_pngk.pngk_from_grades`) in `stpm_cgpa`, over whatever figure the
        browser sent — the onboarding calculator's overall, or a stale copy riding a sync. With
        fewer than PA + three graded subjects there is no PNGK, and the sent figure stands
        ("not calculated"). Readers ask `stpm_cgpa_of` either way; this keeps the column honest."""
        if 'stpm_grades' not in attrs and 'stpm_cgpa' not in attrs:
            return
        from .stpm_pngk import pngk_from_grades
        pngk = pngk_from_grades(_merged('stpm_grades'))
        if pngk is not None:
            attrs['stpm_cgpa'] = pngk

    @staticmethod
    def _one_higher_qualification(attrs):
        """⚠ ONE HIGHER QUALIFICATION AT A TIME (third results route S3a, owner ruling D11/D13).
        A write that COMPLETES the third-route form — its marker kept above AND its CGPA in this
        payload — clears any earlier STPM entries; one that completes the STPM form — marker kept
        AND STPM results in this payload — clears the third route's. Set IN THE ATTRS, so it wins
        over a stale browser copy riding in the same sync (the web resends its stored STPM CGPA on
        every finish), and BEFORE the bookkeeping below, so `completed_qualifications` is pruned to
        match and the no-demote guard reads the switch as the deliberate move it is (the old
        results are no longer on file). A marker sent with no results behind it clears nothing."""
        kept = (attrs.get('results_exam_type') or '').strip().lower()
        if kept in THIRD_ROUTE and attrs.get('higher_cgpa') is not None:
            attrs['stpm_grades'], attrs['stpm_cgpa'] = {}, None
        elif kept == 'stpm' and (attrs.get('stpm_grades') or attrs.get('stpm_cgpa') is not None):
            attrs['higher_cgpa'], attrs['higher_koko'], attrs['higher_institution_type'] = None, None, ''

    def _never_demote_held_results(self, attrs, _merged, _backed):
        """⚠ S2b review (HIGH): a sync may NOT move a profile DOWN from tertiary results it still
        holds. Built from the STORED profile — never the incoming marker, which is exactly what a
        stale browser sends (a sign-in from a device that last saw `'spm'`). If the profile held
        STPM / Matriculation / Asasi / Diploma before this write, the write would make it hold SPM,
        and that qualification's results are still on file after the write, the results fields of
        the write (`results_exam_type`, `completed_qualifications` and `exam_type` — the stored
        answer may rest on the declaration) are DROPPED and the stored answer stands. Only clearing the
        results themselves (`stpm_grades` + `stpm_cgpa`, or `higher_cgpa`) demotes."""
        inst = self.instance
        if inst is None or getattr(inst, 'pk', None) is None:
            return
        before = results_held(inst)
        if not is_tertiary(before) or not _backed(before):
            return

        def _after(field):
            return attrs[field] if field in attrs else _merged(field)
        # The SAME rule as `before`, D1 included (S4 review finding 4): the stored row's identity and
        # state ride along, so a profile promoted on its STPM document is still promoted "after" and
        # may save its results fields; nothing that does not lower the held results is dropped.
        after = results_held(SimpleNamespace(
            pk=inst.pk, _state=inst._state,
            exam_type=_after('exam_type'), results_exam_type=_after('results_exam_type'),
            grades=_merged('grades'), stpm_grades=_merged('stpm_grades'),
            stpm_cgpa=_merged('stpm_cgpa'), higher_cgpa=_merged('higher_cgpa'),
            completed_qualifications=_after('completed_qualifications') or []))
        if is_tertiary(after):
            return
        for f in ('results_exam_type', 'completed_qualifications', 'exam_type'):
            attrs.pop(f, None)

    def _refuse_third_route_while_closed(self, attrs):
        """⚠ THE DOOR IS SHUT UNTIL S2b (`settings.THIRD_ROUTE_OPEN`, default off; review round 1).
        The server side is built, but with no student form and no document check yet, a logged-in
        SPM applicant could PUT `results_exam_type='asasi'` + a 4.00 CGPA and leave the SPM rules.
        While closed: the new exam values, any non-empty third-route field and a
        `completed_qualifications` naming a third-route kind are REFUSED (400, code
        'third_route_closed'); null / '' / [] and an SPM / STPM list (S2b) are harmless and pass."""
        from django.conf import settings
        if getattr(settings, 'THIRD_ROUTE_OPEN', False):
            return
        bad = [f for f in ('exam_type', 'results_exam_type')
               if (attrs.get(f) or '').strip().lower() in THIRD_ROUTE]
        bad += [f for f in ('higher_cgpa', 'higher_koko', 'higher_institution_type')
                if attrs.get(f) not in (None, '', [])]
        # S2b: the web sends the WHOLE list with every SPM / STPM sync, so only a list NAMING a
        # third-route kind is the escape — refusing ['spm'] would 400 every onboarding sync (and
        # lose its grades) on a web release that beat the switch.
        if any(q in THIRD_ROUTE for q in (attrs.get('completed_qualifications') or [])):
            bad.append('completed_qualifications')
        if bad:
            raise serializers.ValidationError(
                {'error': 'third_route_closed',
                 **{f: 'Matriculation / Asasi / Diploma results are not open yet.' for f in bad}},
                code='third_route_closed')

    def validate_completed_qualifications(self, value):
        """A list of qualification codes (S2a). A non-list is refused; unknown entries and
        duplicates are dropped, case and spaces normalised. Backing is checked in ``validate``."""
        if not isinstance(value, list) or len(value) > 10:
            raise serializers.ValidationError('Expected a list of qualifications.')
        out = []
        for q in value:
            q = q.strip().lower() if isinstance(q, str) else ''
            if q in QUALIFICATIONS and q not in out:
                out.append(q)
        return out

    def validate_spm_elective_subjects(self, value):
        """A list of subject KEYS, nothing else (TD-069). `elective_subjects` has never been
        checked; this new field is, for shape only — there is no server-side list of SPM subject
        keys to check membership against (the web's `subjects.ts` is the catalogue), and the cap
        of 7 is the form's, so it is not repeated here. Duplicates and blanks are dropped."""
        if (not isinstance(value, list) or len(value) > _MAX_SPM_ENTRIES
                or not all(isinstance(k, str) for k in value)):
            raise serializers.ValidationError('Expected a list of subject keys.')
        keys = [k.strip() for k in value if k.strip()]
        if any(not _SUBJECT_KEY.fullmatch(k) for k in keys):
            raise serializers.ValidationError('Expected a list of subject keys.')
        return list(dict.fromkeys(keys))

    def validate_spm_stream(self, value):
        """A form label ('science' / 'arts' / 'technical'), stored only so the form can light the
        right pill again. Anything not key-shaped is DROPPED to blank rather than failing the sync
        — failing a student's whole profile sync over a label would trade a cosmetic fault for
        data loss (the same reasoning as `results_exam_type` above). Membership is not checked
        here: the list of streams is the form's, and a copy of it here would be a mirror."""
        value = (value or '').strip().lower()
        return value if _SUBJECT_KEY.fullmatch(value) and len(value) <= 20 else ''   # model: 20

    def validate_spm_prereq_grades(self, value):
        """`{subject key: SPM grade}` (TD-069 review F4 — the web sends it since this sprint; it
        had no check at all). A non-dict or an oversized one is refused; an entry whose key is not
        key-shaped or whose grade is not an SPM grade is DROPPED, so one bad cell never costs the
        student the rest of her grades. The grade list is the STPM engine's own — the consumer of
        these grades — so it is read, not copied."""
        from .stpm_engine import SPM_GRADE_ORDER
        if not isinstance(value, dict) or len(value) > _MAX_SPM_ENTRIES:
            raise serializers.ValidationError('Expected SPM grades by subject key.')
        return {k: g for k, g in value.items()
                if isinstance(k, str) and _SUBJECT_KEY.fullmatch(k) and g in SPM_GRADE_ORDER}

    class Meta:
        model = StudentProfile
        fields = [
            'grades', 'gender', 'nationality', 'colorblind', 'disability',
            'student_signals', 'preferred_state', 'preferred_call_language',
            'name', 'school',
            'nric', 'angka_giliran', 'address', 'postal_code', 'city',
            # TD-061: household_income/household_size are the canonical financial
            # fields (shared with /apply). They replace the legacy free-text
            # family_income range + siblings count, which used to be listed here
            # but were never readable/writable in tandem with the /profile UI —
            # the page reads/writes household_* (this fixes that latent gap too).
            'household_income', 'household_size',
            'exam_type', 'results_exam_type',
            'stpm_grades', 'stpm_cgpa', 'muet_band', 'coq_score',
            # Third results route S2a (Matriculation / Asasi / Diploma) + "highest completed"
            'higher_cgpa', 'higher_koko', 'higher_institution_type', 'completed_qualifications',
            # `referral_source` is NOT here (two columns, 2026-10-09): PUT ignores it, and the sync
            # hands it to `referral_links.apply_ref_code` (first touch) — never a plain overwrite.
            'spm_prereq_grades', 'stream_subjects', 'elective_subjects',
            # TD-069: the STPM path's SPM elective picks + stream, so its form rebuilds on login.
            'spm_elective_subjects', 'spm_stream',
            'contact_email', 'contact_phone', 'whatsapp_opt_in',
            # Structured family roster (the profile-level home; two-way synced with an
            # open application by ProfileView.put).
            'father_name', 'father_occupation', 'father_occupation_other',
            'mother_name', 'mother_occupation', 'mother_occupation_other',
            'other_family_members', 'siblings_in_school', 'siblings_in_tertiary',
            # Pathway / "Your Plans" (profile-level home; two-way synced with an open app).
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'pathways_considered', 'uncertainty_reasons', 'uncertainty_note',
        ]
        # NRIC only changes via the validated claim endpoint (/profile/claim-nric/),
        # never an unchecked PUT or sync — closes the soft-NRIC write gap.
        extra_kwargs = {f: {'required': False} for f in fields}
        extra_kwargs['nric'] = {'required': False, 'read_only': True}
