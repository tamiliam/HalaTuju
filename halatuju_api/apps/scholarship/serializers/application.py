"""Student intake serializers: create, details update, funding need and the income-route switch."""

from rest_framework import serializers
from ..family import PROFESSION_CODES, form_guardians_shape
from ..models import FundingNeed, ScholarshipApplication


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """
    Validates an incoming application. ``cohort`` and ``profile`` are resolved
    and attached by the view, not the client.

    Academic data (grades, exam type, STPM CGPA) is never accepted here — it is
    read live from the canonical HalaTuju profile. The financial fields below are
    write-only: the form may collect/refresh them, and the service syncs them
    back to the profile (their canonical home) rather than storing them on the
    application.
    """
    cohort_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        help_text="Optional; defaults to the active open cohort",
    )
    programme_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        help_text=(
            "Optional; the programme this application is FOR, from the organisation's own apply "
            "link (PF-1). Programme rather than cohort because a cohort code is year-specific "
            "and would rot each intake. Absent + more than one round open = refused, never "
            "guessed."
        ),
    )
    household_income = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, write_only=True,
    )
    household_size = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, write_only=True,
    )
    receives_str = serializers.BooleanField(required=False, write_only=True)
    receives_jkm = serializers.BooleanField(required=False, write_only=True)

    # About Me + My Family (apply-form rebuild S9): the form edits these profile
    # fields inline and commits them on submit. Like the financial fields above
    # they are write-only — the service syncs them back to the canonical profile
    # (StudentProfile), never storing them on the application. NRIC is NOT here:
    # it changes only through the validated claim path (/profile/claim-nric/).
    # max_length mirrors the profile (StudentProfile) columns these sync to. Without
    # it an over-long value reaches sync_profile_fields -> setattr -> save and
    # overflows the varchar, rolling back the whole submit as a generic error
    # (the same class of bug as the Story parents_occupation incident). With it the
    # student gets a clean field-level 400 the form can phrase as "too long".
    name = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=255)
    school = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=255)
    preferred_state = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=50)
    contact_phone = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=20)
    preferred_call_language = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=10)
    referral_source = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=50)
    guardians = serializers.JSONField(required=False, write_only=True, validators=[form_guardians_shape])

    class Meta:
        model = ScholarshipApplication
        fields = [
            'cohort_code', 'programme_code',
            'household_income', 'household_size', 'receives_str', 'receives_jkm',
            # About Me + My Family profile fields (write-only; synced to profile)
            'name', 'school', 'preferred_state', 'contact_phone',
            'preferred_call_language', 'referral_source', 'guardians',
            'intended_pathway', 'intends_tertiary_2026',
            'consent_to_contact', 'form_data',
            # Plans + Support intake (Sprint 7) — all optional (blank/default on the model)
            'field_of_study', 'pathways_considered', 'top_choices', 'upu_status',
            'other_scholarships', 'other_scholarships_text',
            'help_university', 'help_scholarship', 'anything_else',
            # Plans redesign (context-aware step) — all optional/additive
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
            # Truthfulness declaration signature (declared_at is stamped server-side)
            'declaration_name',
        ]

    def validate_consent_to_contact(self, value):
        if not value:
            raise serializers.ValidationError(
                'Consent to be contacted is required to apply.'
            )
        return value


# Anti-spam ceiling for the free-text Story/Funding fields. Generous (~900 words)
# — well above any genuine answer, well below a copy-paste flood. Enforced here
# (clean 400) AND on the web form (maxLength), so an over-long value never reaches
# the DB and silently rolls back the whole save (the parents_occupation varchar(255)
# bug). The frontend mirrors this value as STORY_TEXT_MAX.
STORY_TEXT_MAX = 5000


class FundingNeedSerializer(serializers.ModelSerializer):
    # funding_note is a TextField (no DB cap); add the same anti-spam ceiling so a
    # flood is a clean field error, not an unbounded write.
    funding_note = serializers.CharField(
        required=False, allow_blank=True, max_length=STORY_TEXT_MAX)

    class Meta:
        model = FundingNeed
        fields = ['categories', 'funding_note', 'programme_months']


class IncomeRouteSwitchSerializer(serializers.Serializer):
    """Post-submit income route switch (student self-serve, Action Centre). The student
    re-runs the income route question: STR (single earner) or salary (≥1 working member).
    Mirrors the income wizard's completeness rules (`incomeWizard.wizardComplete`)."""
    income_route = serializers.ChoiceField(choices=['str', 'salary'])
    income_earner = serializers.ChoiceField(
        choices=['', 'father', 'mother', 'guardian'], required=False, allow_blank=True, default='')
    income_working_members = serializers.ListField(
        child=serializers.ChoiceField(choices=['father', 'mother', 'guardian', 'brother', 'sister']),
        required=False, allow_empty=True, default=list)

    def validate(self, data):
        route = data['income_route']
        if route == 'str' and not data.get('income_earner'):
            raise serializers.ValidationError(
                {'income_earner': 'Choose whose income the STR is in (father / mother / guardian).'})
        if route == 'salary':
            members = data.get('income_working_members') or []
            if not members:
                raise serializers.ValidationError(
                    {'income_working_members': 'Pick at least one working household member.'})
            if len(set(members)) != len(members):
                raise serializers.ValidationError(
                    {'income_working_members': 'Duplicate members are not allowed.'})
        return data


class ApplicationDetailsUpdateSerializer(serializers.Serializer):
    """PATCH payload for STEP 2 deeper-info + funding need."""
    aspirations = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    plans = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    fears = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    justification = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    funding_need = FundingNeedSerializer(required=False)
    # "Your story" guided narrative fields (S2 redesign)
    first_in_family = serializers.BooleanField(required=False)
    parents_occupation = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    # TD-061: the legacy siblings_studying boolean is gone; only the count remains.
    siblings_studying_count = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=20,
    )
    family_context = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    daily_life = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    # Address — stored on the profile, captured in the Story tab (S14). Caps mirror
    # the profile columns (address=text, postal_code=varchar(5), city=varchar(100))
    # so an over-long value fails cleanly here instead of as a DB rollback.
    address = serializers.CharField(required=False, allow_blank=True, max_length=STORY_TEXT_MAX)
    postal_code = serializers.CharField(required=False, allow_blank=True, max_length=5)
    city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    # Income Check-1 wizard answers (Documents → Household income).
    income_route = serializers.ChoiceField(
        choices=['', 'str', 'salary'], required=False, allow_blank=True)
    income_earner = serializers.ChoiceField(
        choices=['', 'father', 'mother', 'guardian'], required=False, allow_blank=True)
    # Salary route: the multi-select of working household members (replaces the single
    # earner + work-status + other-earner for that route).
    income_working_members = serializers.ListField(
        child=serializers.ChoiceField(choices=['father', 'mother', 'guardian', 'brother', 'sister']),
        required=False, allow_empty=True)
    # Phase 2A: a working member's DECLARED average monthly income (RM), {member: amount}.
    # Only for a member with no payslip/EPF. Accepted if a valid STR is on file, else needs
    # an income_support_doc (see income_engine.earner_monthly_income).
    income_declared = serializers.DictField(
        child=serializers.IntegerField(min_value=0, max_value=100000),
        required=False, allow_empty=True)
    # Phase 2B: unemployment detail per 'unemployed' roster member, {member: {reason, since}}.
    income_nonearning = serializers.DictField(
        child=serializers.DictField(), required=False, allow_empty=True)
    siblings_in_school = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=20)
    siblings_in_tertiary = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=20)
    # ── Structured family roster (redesign 2026-06). first_in_family +
    #    parents_occupation above are DERIVED from these on save, so the form no
    #    longer sends them. occupation_other only matters when occupation == 'other'.
    father_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    father_occupation = serializers.ChoiceField(
        choices=[''] + sorted(PROFESSION_CODES), required=False, allow_blank=True)
    father_occupation_other = serializers.CharField(required=False, allow_blank=True, max_length=120)
    mother_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    mother_occupation = serializers.ChoiceField(
        choices=[''] + sorted(PROFESSION_CODES), required=False, allow_blank=True)
    mother_occupation_other = serializers.CharField(required=False, allow_blank=True, max_length=120)
    # The optional pool — validated/normalised by family.clean_other_members on save.
    other_family_members = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=True)

    _VALID_MEMBERS = {'father', 'mother', 'guardian', 'brother', 'sister'}

    def _validate_person_name(self, value):
        # Authoritative guard (the FE mirrors it): a parent name may not contain digits — an IC /
        # phone number typed into the name box is rejected here, not silently stored (a real case:
        # a father_name persisted as an IC number, which broke name-resolution).
        from .. import family
        if not family.is_valid_person_name(value):
            raise serializers.ValidationError(
                'Enter the name as printed on the IC — letters only, not the IC number.')
        return value

    def validate_father_name(self, value):
        return self._validate_person_name(value)

    def validate_mother_name(self, value):
        return self._validate_person_name(value)

    def validate_income_declared(self, value):
        bad = sorted(set(value) - self._VALID_MEMBERS)
        if bad:
            raise serializers.ValidationError(f'Unknown household member(s): {bad}')
        return value

    def validate_income_nonearning(self, value):
        bad = sorted(set(value) - self._VALID_MEMBERS)
        if bad:
            raise serializers.ValidationError(f'Unknown household member(s): {bad}')
        # Keep only the two known keys per member; coerce to trimmed strings (reason free text,
        # since 'YYYY-MM'). Defensive — the wizard sends exactly these, but never trust the client.
        out = {}
        for m, detail in value.items():
            if isinstance(detail, dict):
                out[m] = {k: (str(detail.get(k, '')) or '').strip()[:200]
                          for k in ('reason', 'since') if detail.get(k)}
        return out
