"""Serializers for B40 Assistance Programme intake."""
from rest_framework import serializers

from . import pool
from .family import PROFESSION_CODES
from .models import (
    ApplicantDocument, BankAccount, Consent, FundingNeed, GraduationMessage, Referee,
    ResolutionItem, ScholarshipApplication, SemesterResult, Sponsor,
    SponsorReferral, StandingGift,
)


class SponsorSerializer(serializers.ModelSerializer):
    """Phase E: a sponsor's own account view (read-only). Drives the portal's
    pending/approved/rejected state. Excludes internal vetting fields."""
    is_approved = serializers.BooleanField(read_only=True)
    profile_complete = serializers.SerializerMethodField()

    class Meta:
        model = Sponsor
        fields = ['id', 'name', 'email', 'phone', 'source', 'organisation',
                  'status', 'is_approved', 'profile_complete', 'notify_frequency',
                  'created_at']
        read_only_fields = fields

    def get_profile_complete(self, obj):
        """True when the required registration details (phone, source, PDPA
        consent) are all present — a Google sponsor lands without them and must
        complete this step before vetting proceeds."""
        return bool(obj.phone and obj.source and obj.consent_at)


def _funding_need_or_none(application):
    from .models import FundingNeed
    try:
        return application.funding_need
    except FundingNeed.DoesNotExist:
        return None


def _resolve_field_image_slug(app, cache):
    """Resolve the catalogue field-artwork slug for a pool card, catalogue-first:
    (a) chosen_programme['course_id'] → Course.field_key_id → FieldTaxonomy.image_slug;
    (b) else field_of_study treated as a taxonomy key → FieldTaxonomy.image_slug;
    (c) else '' (the frontend falls back to the generic slug).

    ``cache`` is the per-request serializer context dict — the taxonomy map (37 rows) is
    loaded once and course→field_key lookups are memoised, so serialising a whole list is
    not N queries. Allowlist rationale: catalogue artwork shared by hundreds of courses is
    non-identifying — it is the field, not the student."""
    tax = cache.get('_tax_slugs')
    if tax is None:
        from apps.courses.models import FieldTaxonomy
        tax = dict(FieldTaxonomy.objects.values_list('key', 'image_slug'))
        cache['_tax_slugs'] = tax
    # (a) confirmed catalogue course → its canonical field's artwork
    cp = getattr(app, 'chosen_programme', None)
    if isinstance(cp, dict):
        course_id = (cp.get('course_id') or '').strip()
        if course_id:
            course_fk = cache.setdefault('_course_fk', {})
            if course_id not in course_fk:
                from apps.courses.models import Course
                course_fk[course_id] = (Course.objects.filter(course_id=course_id)
                                        .values_list('field_key_id', flat=True).first())
            fk = course_fk[course_id]
            if fk and tax.get(fk):
                return tax[fk]
    # (b) the broad field-of-study, when it is itself a taxonomy key
    fos = (app.field_of_study or '').strip()
    if fos and tax.get(fos):
        return tax[fos]
    # (c) unknown → generic (frontend fallback)
    return ''


class SponsorPoolCardSerializer(serializers.Serializer):
    """Phase E2 — the ANONYMISED card a vetted sponsor sees. **Allowlist by
    construction:** every field is an explicit, derived, non-identifying value and
    nothing is passed through from the application/profile, so a new model field
    can never leak to a sponsor by accident. Input is a ``ScholarshipApplication``.
    (Tests assert no name/NRIC/address/phone/email appears in the output — for the
    student OR their parents.)

    ``institution`` is the TARGET university/college the student is heading to (from the
    confirmed offer / chosen programme) — NEVER the secondary school, which is no longer
    surfaced on any sponsor card. ``state`` stays region-level. ``blurb`` is a ≤20-word
    card-strict one-liner (generated + identifier-scanned at publish)."""
    # `id` is the application row id — used only as the opaque key to fetch the
    # detail; it is not identifying. `ref` is the human-facing alias.
    id = serializers.IntegerField(read_only=True)
    ref = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    field = serializers.SerializerMethodField()
    course = serializers.SerializerMethodField()        # the confirmed programme name
    academic = serializers.SerializerMethodField()
    institution = serializers.SerializerMethodField()   # TARGET university — never the school
    blurb = serializers.SerializerMethodField()         # ≤20-word card-strict one-liner
    funding_categories = serializers.SerializerMethodField()
    programme_months = serializers.SerializerMethodField()
    award_amount = serializers.SerializerMethodField()  # E3: admin-set; non-identifying
    progress_state = serializers.SerializerMethodField()  # F2: coarse, non-identifying
    support_status = serializers.SerializerMethodField()  # S5: coarse operational signal
    enrolment_verified = serializers.SerializerMethodField()  # R5: bare boolean badge
    field_image_slug = serializers.SerializerMethodField()  # redesign: catalogue artwork
    reporting_date = serializers.SerializerMethodField()     # redesign: course-start countdown

    def get_ref(self, app):
        return pool.pool_ref(app.id)

    def get_field_image_slug(self, app):
        # Catalogue field artwork (shared by hundreds of courses) — non-identifying.
        return _resolve_field_image_slug(app, self.context)

    def get_reporting_date(self, app):
        # DATE ONLY (never a time) — already sponsor-visible via the narrative/pathway
        # text; a coarse date drives the "starts in N days" countdown. Null-safe.
        d = getattr(app, 'reporting_date', None)
        return d.isoformat() if d else None

    def get_enrolment_verified(self, app):
        # R5: a BARE boolean — "an independent party confirmed this student's
        # enrolment". Never the verifier, the evidence, or when/how. Allowlist-safe.
        return bool(getattr(app, 'enrolment_verified', False))

    def get_progress_state(self, app):
        # F2: null until the student is sponsored; on_track thereafter (stub — F9a
        # computes the real band from semester results). Non-identifying.
        return pool.derive_progress_state(app)

    def get_support_status(self, app):
        # S5: a coarse operational signal distinct from the academic band — only
        # 'paused' (on_hold) / 'completing' (ready_to_close) are surfaced; probation is
        # never shown to a sponsor. Null in good standing. Allowlist-safe (no identity).
        from . import maintenance
        return maintenance.sponsor_support_status(app)

    def get_award_amount(self, app):
        return str(app.award_amount) if app.award_amount is not None else None

    def get_state(self, app):
        # State-level region only — street/postcode/city are never exposed.
        return (getattr(app.profile, 'preferred_state', '') or '') if app.profile else ''

    def get_field(self, app):
        return app.field_of_study or ''

    def get_course(self, app):
        # The confirmed programme NAME (e.g. "Diploma Kejuruteraan Mekanikal") — resolved
        # defence-in-depth so a mis-slotted offer (an institution name / a "Tarikh…" line in
        # the course slot) or a raw pre-U value never reaches a sponsor. See card_display.
        from . import card_display
        return card_display.resolve_course(app)

    def get_academic(self, app):
        return pool.academic_band(app.profile)

    def get_institution(self, app):
        # The TARGET institution the student will study AT, e.g. "Politeknik Ungku Omar" —
        # resolved so a date/'Tarikh' junk value and, critically, a SECONDARY SCHOOL are
        # NEVER surfaced to a sponsor (the allowlist privacy promise; card_display enforces
        # the school-block). '' when nothing safe resolves → the card shows the course only.
        from . import card_display
        return card_display.resolve_institution(app)

    def get_blurb(self, app):
        sp = getattr(app, 'sponsor_profile', None)
        return (sp.anon_blurb or '') if sp else ''

    def get_funding_categories(self, app):
        fn = _funding_need_or_none(app)
        return fn.categories if (fn and isinstance(fn.categories, list)) else []

    def get_programme_months(self, app):
        fn = _funding_need_or_none(app)
        return fn.programme_months if fn else None


class SponsorPoolDetailSerializer(SponsorPoolCardSerializer):
    """The card + the GENERATED anonymous blurb (admin-reviewed, anon-published).
    Still an allowlist — only the anon_markdown is added, never the named profile."""
    anon_profile = serializers.SerializerMethodField()

    def get_anon_profile(self, app):
        sp = getattr(app, 'sponsor_profile', None)
        return (sp.anon_markdown or '') if sp else ''


class SponsorReferralSerializer(serializers.ModelSerializer):
    """F4 — one of the inviter's own invitations (read). The inviter typed the
    invitee's email, so showing it back to them is fine; once purged (expired) the
    email/name are blank. ``code`` is the inviter's own share link token."""
    class Meta:
        model = SponsorReferral
        fields = ['id', 'invitee_email', 'invitee_name', 'note', 'code',
                  'status', 'created_at', 'joined_at']
        read_only_fields = fields


class StandingGiftSerializer(serializers.ModelSerializer):
    """R6 — a sponsor's own AutoSponsor config (their settings only, never any
    student data). Read + upsert: prefs empty = match any; ``max_amount`` null = no
    per-student cap. ``last_allocated_at`` is system-set."""
    class Meta:
        model = StandingGift
        fields = ['field_pref', 'state_pref', 'max_amount', 'active', 'last_allocated_at']
        read_only_fields = ['last_allocated_at']

    def validate_max_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('max_amount must be positive')
        return value


class SponsorSponsorshipSerializer(serializers.Serializer):
    """Phase E3 — a sponsor's own allocation: the ANONYMISED student card + the
    money/status only. Allowlist: the student is the anon card, never identity."""
    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    offered_at = serializers.DateTimeField(read_only=True)
    accept_deadline = serializers.DateTimeField(read_only=True)
    decided_at = serializers.DateTimeField(read_only=True)
    student = serializers.SerializerMethodField()
    # R2: non-identifying journey signals (a bool + an int) — the FE derives the
    # Matched → Onboarded → Studying → Graduated tracker from these + progress_state.
    onboarded = serializers.SerializerMethodField()
    semesters = serializers.SerializerMethodField()

    def get_student(self, sponsorship):
        return SponsorPoolCardSerializer(sponsorship.application).data

    def get_onboarded(self, sponsorship):
        return sponsorship.application.onboarded_at is not None

    def get_semesters(self, sponsorship):
        return sponsorship.application.semester_results.count()


class StudentAwardSerializer(serializers.Serializer):
    """Phase E3 — a student's award offer: amount + deadline + status only.
    Allowlist: NO sponsor field — the student never sees who the sponsor is."""
    id = serializers.IntegerField(read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    offered_at = serializers.DateTimeField(read_only=True)
    accept_deadline = serializers.DateTimeField(read_only=True)


class BursaryAgreementSerializer(serializers.Serializer):
    """The student's view of their bursary agreement: derived status + the frozen
    particulars + a time-limited signed URL to the PDF. Allowlist-safe: there is NO
    donor field anywhere — the document names only the Foundation signatory."""
    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True)
    locale = serializers.CharField(read_only=True)
    award_amount = serializers.DecimalField(max_digits=10, decimal_places=2,
                                            read_only=True, allow_null=True)
    payment_schedule = serializers.CharField(read_only=True)
    institution_name = serializers.CharField(read_only=True)
    course_name = serializers.CharField(read_only=True)
    progress_standard = serializers.CharField(read_only=True)
    foundation_signatory_name = serializers.CharField(read_only=True)
    foundation_signatory_title = serializers.CharField(read_only=True)
    student_signed_name = serializers.CharField(read_only=True)
    student_signed_at = serializers.DateTimeField(read_only=True)
    guarantor_name = serializers.CharField(read_only=True)
    guarantor_relationship = serializers.CharField(read_only=True)
    guarantor_signed_at = serializers.DateTimeField(read_only=True)
    foundation_signed_at = serializers.DateTimeField(read_only=True)
    witness_signed_at = serializers.DateTimeField(read_only=True)
    agreement_sha256 = serializers.CharField(read_only=True)
    pdf_url = serializers.SerializerMethodField()

    def get_pdf_url(self, obj):
        if not obj.pdf_storage_path:
            return None
        from .storage import create_signed_download_url, resolve_org_for_path
        # org-fence (Sprint 4, belt-and-braces) — see ApplicantDocumentSerializer.
        app = getattr(obj, 'application', None)
        path_org = resolve_org_for_path(obj.pdf_storage_path)
        if path_org is not None and app is not None and path_org != app.owning_organisation_id:
            return None
        return create_signed_download_url(obj.pdf_storage_path)


class SemesterResultSerializer(serializers.ModelSerializer):
    """F9a — a student's own in-programme semester result (read). This is the
    student's own data (not the sponsor boundary), so a ModelSerializer is fine.
    The uploaded ``results_slip`` is myNADI-only; only its id is surfaced here."""
    class Meta:
        model = SemesterResult
        fields = ['id', 'semester', 'cgpa', 'graduated', 'results_slip', 'note', 'created_at']
        read_only_fields = fields


class GraduationMessageSerializer(serializers.ModelSerializer):
    """F9a — a student's own view of a graduation thank-you they submitted: the
    review ``status`` + the scan outcome, so the FE can show "blocked — please
    remove identifying details" vs "awaiting review" vs "approved"."""
    class Meta:
        model = GraduationMessage
        fields = ['id', 'status', 'raw_text', 'scrubbed_text', 'scan_result',
                  'created_at', 'reviewed_at']
        read_only_fields = fields


class GraduationRelaySerializer(serializers.Serializer):
    """F9a — the SPONSOR-facing graduation relay. **Allowlist by construction**
    (plain Serializer, explicit fields, input is a plain dict from
    ``in_programme.approved_messages_for_sponsor``): only the anonymous ``ref``, the
    staff-approved ``text``, and the approval time cross. There is NO student
    identity and NO model passthrough, so nothing identifying can leak. A sponsor
    sees this as *"a message from a student you supported"* — never a direct
    channel. (A leak test asserts no name/NRIC/etc. appears in the output.)"""
    ref = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)
    approved_at = serializers.DateTimeField(read_only=True)


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
    guardians = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'cohort_code',
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
    earner_work_status = serializers.ChoiceField(
        choices=['', 'payslip', 'informal', 'not_working'], required=False, allow_blank=True)
    household_other_earners = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=20)
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
        from . import family
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


class ApplicationReadSerializer(serializers.ModelSerializer):
    """
    Output representation of an application (read-only).

    Academic + financial fields are derived live from the linked profile (the
    single source of truth), never stored on the application. ``intake_snapshot``
    is the frozen audit copy of what was declared at submit time.
    """
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    cohort_name = serializers.CharField(source='cohort.name', read_only=True)
    profile_id = serializers.CharField(
        source='profile.pk', read_only=True, allow_null=True,
    )
    # Profile-derived (read live from the canonical StudentProfile).
    exam_type = serializers.CharField(source='profile.exam_type', read_only=True)
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
    household_income = serializers.IntegerField(source='profile.household_income', read_only=True)
    household_size = serializers.IntegerField(source='profile.household_size', read_only=True)
    receives_str = serializers.BooleanField(source='profile.receives_str', read_only=True)
    receives_jkm = serializers.BooleanField(source='profile.receives_jkm', read_only=True)
    # Address pre-fill for the Story tab (writes round-trip via the details
    # serializer below; state already comes from /apply as preferred_state).
    address = serializers.CharField(source='profile.address', read_only=True, allow_blank=True)
    postal_code = serializers.CharField(source='profile.postal_code', read_only=True, allow_blank=True)
    city = serializers.CharField(source='profile.city', read_only=True, allow_blank=True)
    preferred_state = serializers.CharField(source='profile.preferred_state', read_only=True, allow_blank=True)
    spm_a_count = serializers.SerializerMethodField()
    funding_need = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    # The address decision/comms emails are actually sent to (resolved at submit).
    notify_email = serializers.EmailField(read_only=True)
    # Pre-fills the Vircle setup task's mobile field (the student may correct it there if they
    # registered with Vircle under a different number).
    contact_phone = serializers.CharField(
        source='profile.contact_phone', read_only=True, allow_blank=True,
    )

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'cohort_code', 'cohort_name', 'profile_id',
            'exam_type', 'spm_a_count', 'stpm_pngk',
            'household_income', 'household_size',
            'receives_str', 'receives_jkm',
            'intended_pathway', 'intends_tertiary_2026',
            'consent_to_contact',
            'field_of_study', 'pathways_considered', 'top_choices', 'upu_status',
            'other_scholarships', 'other_scholarships_text',
            'help_university', 'help_scholarship', 'anything_else', 'mentoring_candidate',
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
            'declaration_name', 'declared_at',
            'status', 'bucket', 'shortlist_reason',
            # S5: the student's own maintenance sub-state (e.g. on_hold) — only meaningful
            # while status='maintenance'; lets the in-programme page show "support paused".
            'maintenance_substate',
            # S6: closure bucket — lets the in-programme page show the right "programme
            # complete" (graduated/completed) vs neutral closed copy.
            'closure_reason',
            'acknowledged_at', 'submitted_at', 'updated_at',
            # Phase C: confirm-submit timestamp + the admin's request-more-docs note
            'profile_completed_at', 'info_request_note', 'info_requested_at',
            # B40 Phase E/F (F8a): post-award onboarding completion timestamp
            'onboarded_at',
            'aspirations', 'plans', 'fears', 'justification',
            # "Your story" guided narrative fields (S2 redesign)
            'first_in_family', 'parents_occupation',
            'siblings_studying_count',
            'family_context', 'daily_life',
            # Structured family roster (redesign 2026-06) — the new inputs.
            'father_name', 'father_occupation', 'father_occupation_other',
            'mother_name', 'mother_occupation', 'mother_occupation_other',
            'other_family_members',
            # Income Check-1 wizard answers.
            'income_route', 'income_earner', 'income_working_members', 'income_declared',
            'income_nonearning', 'earner_work_status',
            'household_other_earners', 'siblings_in_school', 'siblings_in_tertiary',
            # Address pre-fill (profile-derived, read-only here; written via
            # ApplicationDetailsUpdateSerializer + save_application_details).
            'address', 'postal_code', 'city', 'preferred_state',
            'funding_need', 'completeness', 'notify_email', 'contact_phone',
            'form_data', 'intake_snapshot',
        ]

    def get_status(self, obj):
        # The student-facing status is deliberately masked at two points (the admin cockpit uses
        # a different serializer and always sees the real status):
        #
        # 1. Immediate-rejection model: the decision flips to 'rejected' at once, but the student
        #    email is EMBARGOED for the cool-off to soften the news. Until that email goes (the
        #    pending marker is still set), the STUDENT sees the in-review state, not the rejection.
        # 2. 'recommended' (formerly 'accepted') is an INTERNAL verification decision a super-admin
        #    can still reverse (reopen -> interviewed -> possibly declined). The student must NOT
        #    perceive the jump — a reversal would otherwise be visible (and embarrassing). They see
        #    the in-review state; real good news reaches them only via a concrete, non-reversible
        #    AWARD OFFER (the award panel keys off the award object, not this status). Once they
        #    accept an award the app becomes 'sponsored' (a real commitment, not masked).
        if obj.status == 'rejected' and (obj.pending_rejection_category or ''):
            return 'interviewed'
        if obj.status == 'recommended':
            return 'interviewed'
        return obj.status

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0

    def get_funding_need(self, obj):
        try:
            return FundingNeedSerializer(obj.funding_need).data
        except FundingNeed.DoesNotExist:
            return None

    def get_completeness(self, obj):
        from .services import application_completeness
        return application_completeness(obj)


# ── Documents / referee / consent (Sprint 5a) ────────────────────────────

class ApplicantDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    # S13: server-computed match verdicts (so client doesn't reimplement matchers).
    vision_nric_verdict = serializers.SerializerMethodField()
    vision_name_verdict = serializers.SerializerMethodField()
    # Genuineness fingerprint (verification-assurance): {status, reason, doc_seen} — soft,
    # flag-gated. status ∈ canonical genuine / suspect / not_<type>. Null if it didn't run.
    authenticity = serializers.SerializerMethodField()
    # Check-1 Academic: the three clinical checks for a results slip (name/subjects/
    # results), server-computed against the student's own profile — null for other types.
    academic_check = serializers.SerializerMethodField()
    # Check-1 Pathway: the offer-letter facts (name + IC checks + data points) —
    # null unless doc_type=offer_letter.
    pathway_check = serializers.SerializerMethodField()
    # Check-1 Income: the earner-IC relationship facts — null unless doc_type=parent_ic.
    income_ic_check = serializers.SerializerMethodField()
    # Check-1 Income: a member-tagged salary slip / EPF vs that member's IC.
    income_proof_check = serializers.SerializerMethodField()
    # Check-1 Income: the STR document — recipient vs the earner IC + currency.
    str_check = serializers.SerializerMethodField()
    # Check-1 Income: a utility bill — address (vs home) + monthly bill + unpaid balance.
    utility_check = serializers.SerializerMethodField()
    # Check-1 Income: relationship proof — birth certificate / guardianship letter.
    bc_check = serializers.SerializerMethodField()
    guardianship_check = serializers.SerializerMethodField()
    # V1: the declared-income supporting doc — whether it READ (officer chip).
    support_doc_check = serializers.SerializerMethodField()
    # Academic: a post-SPM semester-result slip — name/NRIC (vs the student) + CGPA. Null otherwise.
    semester_check = serializers.SerializerMethodField()
    # Academic: a school-leaving cert — school + name/NRIC (vs the student) + kelakuan + activities.
    school_leaving_check = serializers.SerializerMethodField()
    # Officer box: the household member this income doc belongs to — its stored tag, or (for a
    # blank-tagged doc) resolved by the name on the doc against the family roster. Display-only.
    resolved_member = serializers.SerializerMethodField()

    class Meta:
        model = ApplicantDocument
        fields = [
            'id', 'doc_type', 'household_member', 'original_filename', 'content_type', 'size',
            'verification_status', 'uploaded_at', 'download_url',
            # S13: Vision OCR soft-signal fields (populated only for IC).
            # Post-S14: vision_address surfaced for admin cross-check, no matcher.
            'vision_nric', 'vision_name', 'vision_address',
            'vision_run_at', 'vision_error',
            'vision_nric_verdict', 'vision_name_verdict', 'authenticity',
            # Supporting-doc soft checks (name/address presence). Stored at upload.
            'vision_name_match', 'vision_address_match',
            # Document-assist: Gemini-extracted fields + student verdict (stored).
            'vision_fields', 'vision_fields_run_at',
            # Check-1 Academic: results-slip 3-check (null unless doc_type=results_slip).
            'academic_check',
            # Check-1 Pathway: offer-letter facts (null unless doc_type=offer_letter).
            'pathway_check',
            # Check-1 Income: earner-IC relationship facts (null unless doc_type=parent_ic).
            'income_ic_check',
            # Check-1 Income: salary slip / EPF vs the member's IC (null otherwise).
            'income_proof_check',
            # Check-1 Income: STR recipient vs the earner IC + currency (null otherwise).
            'str_check',
            # Check-1 Income: utility bill — address + monthly bill + unpaid balance.
            'utility_check',
            # Check-1 Income: relationship proof checklists (BC / guardianship letter).
            'bc_check', 'guardianship_check',
            # V1: declared-income supporting doc read-status (null unless income_support_doc).
            'support_doc_check',
            # Academic: semester-result name/NRIC/CGPA (null unless semester_result).
            'semester_check',
            # Academic: school-leaving cert school/name/NRIC/kelakuan/activities (null otherwise).
            'school_leaving_check',
            # Officer box: resolved household member (stored tag or name-resolved). Display-only.
            'resolved_member',
            # Phase 2 version history: when this doc was replaced (null = live) + which
            # doc replaced it. The admin path returns superseded rows to show history;
            # the student GET filters them out.
            'superseded_at', 'superseded_by',
        ]
        read_only_fields = [
            'vision_nric', 'vision_name', 'vision_address',
            'vision_run_at', 'vision_error',
            'vision_name_match', 'vision_address_match',
            'vision_fields', 'vision_fields_run_at',
            'superseded_at', 'superseded_by',
        ]

    def get_download_url(self, obj):
        from .storage import create_signed_download_url, resolve_org_for_path
        # org-fence (Sprint 4, belt-and-braces): refuse to sign a doc whose key-org
        # disagrees with its application's org. The real fence is upstream (student
        # sees own docs; admin reads are org-scoped) — this catches a mis-keyed blob.
        app = getattr(obj, 'application', None)
        path_org = resolve_org_for_path(obj.storage_path)
        if path_org is not None and app is not None and path_org != app.owning_organisation_id:
            return None
        return create_signed_download_url(obj.storage_path)

    def get_vision_nric_verdict(self, obj):
        """'match' / 'mismatch' / 'unreadable' — soft signal. Empty when Vision hasn't run."""
        if obj.doc_type != 'ic' or obj.vision_run_at is None:
            return ''
        if obj.vision_error or not obj.vision_nric:
            return 'unreadable'
        from .vision import nric_match
        return 'match' if nric_match(obj.vision_nric, getattr(obj.application.profile, 'nric', '') or '') else 'mismatch'

    def get_vision_name_verdict(self, obj):
        """'match' / 'partial' / 'mismatch' / 'unreadable' — soft signal. Empty when Vision hasn't run."""
        if obj.doc_type != 'ic' or obj.vision_run_at is None:
            return ''
        if obj.vision_error or not obj.vision_name:
            return 'unreadable'
        from .vision import name_match
        return name_match(obj.vision_name, getattr(obj.application.profile, 'name', '') or '')

    def get_authenticity(self, obj):
        """Genuineness fingerprint summary {status, reason, doc_seen} — soft, flag-gated.
        IC/parent_ic (Sprint 1) + the standardised supporting docs (Sprint 2: STR, results
        slip, birth cert, EPF). Null when the check didn't run (flag off / AI outage)."""
        if obj.doc_type not in ('ic', 'parent_ic', 'str', 'results_slip', 'birth_certificate', 'epf',
                                'offer_letter', 'salary_slip', 'electricity_bill', 'water_bill',
                                'school_leaving_cert'):
            return None
        vf = obj.vision_fields if isinstance(obj.vision_fields, dict) else {}
        auth = vf.get('authenticity')
        if not isinstance(auth, dict) or not auth.get('status'):
            return None
        from .genuineness.bands import canonical_status
        # Expose the CANONICAL outcome (genuine / suspect / not_<type>), folding any legacy
        # stored value, so the FE renders one consistent vocabulary across all document types.
        status = canonical_status(auth.get('status'), obj.doc_type)
        # Salary slip (MODEL_VERSION 1.0.0): surface ONLY the WRONG-TYPE reject (not_salary — a MyKad
        # or other document in the salary-slip slot, #47) → the red "wrong document" chip. The informal
        # 'suspect' band (a genuine but weakly-verifiable slip, common for real B40 families) would be
        # amber noise, so a genuine/suspect slip renders normally (no chip). Mirrors how a genuine EPF
        # shows nothing while a not_epf shows the wrong-type chip.
        if obj.doc_type == 'salary_slip' and not status.startswith('not_'):
            return None
        # Electricity bill (MODEL_VERSION 1.0.0): same — surface ONLY the wrong-type reject
        # (not_electricity_bill: a MyKad / water bill / junk in the electricity slot) → the red chip.
        # The 'suspect' band is a thin/cropped-but-genuine bill (common), so hide it as amber noise;
        # a genuine/suspect bill renders normally.
        if obj.doc_type == 'electricity_bill' and not status.startswith('not_'):
            return None
        # Water bill (MODEL_VERSION 1.0.0): same — surface ONLY the wrong-type reject (not_water_bill:
        # a MyKad / an ELECTRICITY bill / junk in the water slot) → the red chip. The 'suspect' band is
        # a thin/cropped-but-genuine bill (common for real B40 families), so hide it as amber noise; a
        # genuine/suspect bill renders normally. Closes the swap symmetrically with electricity_bill.
        if obj.doc_type == 'water_bill' and not status.startswith('not_'):
            return None
        # School-leaving cert (MODEL_VERSION 1.0.0): surface ONLY the wrong-type reject
        # (not_school_leaving_cert: a MyKad / results slip / another document in the slot) → the red
        # chip. A 'suspect' (thin/cropped) OR 'unrecognised' (a free-form testimonial we can't
        # structurally confirm — folded to 'suspect' by canonical_status) is a real B40 leaver doc, so
        # hide it as amber noise; a genuine/suspect cert renders normally (never a false reject).
        if obj.doc_type == 'school_leaving_cert' and not status.startswith('not_'):
            return None
        return {'status': status,
                'reason': auth.get('reason', ''), 'doc_seen': auth.get('doc_seen', '')}

    def get_academic_check(self, obj):
        """{name, subjects, results, candidate_name, missing, mismatched, slip_count}
        for a results slip — the three clinical checks against the student's own
        profile. Null for every other doc type (the FE renders the IC/supporting
        chips instead)."""
        if obj.doc_type != 'results_slip':
            return None
        from .academic_engine import student_slip_check
        return student_slip_check(obj)

    def get_pathway_check(self, obj):
        """{name, ic, + data points} for an offer letter — the clinical facts against
        the student's own profile, plus ``switched_from`` on the LIVE offer when it replaced a
        genuinely different prior offer (the course-switch note). Null for every other doc type."""
        if obj.doc_type != 'offer_letter':
            return None
        from .pathway_engine import student_offer_check, offer_pathway_switch
        chk = student_offer_check(obj)
        sw = offer_pathway_switch(obj.application) if getattr(obj, 'superseded_at', None) is None else None
        chk['switched_from'] = ({'programme': sw['from_programme'], 'institution': sw['from_institution']}
                                if sw else None)
        return chk

    def get_income_ic_check(self, obj):
        """{nric, name, address, member, name_status, readable} for an income earner's
        IC (parent_ic) — the OCR'd values + the RELATIONSHIP verdict (the earner's IC
        links to the student's family via patronymic / birth cert / letter), NOT an
        identity match against the student. Null for every other doc type."""
        if obj.doc_type != 'parent_ic':
            return None
        from .income_engine import student_income_ic_check, income_cluster_advice
        chk = student_income_ic_check(obj)
        if chk:
            # The CLUSTER verdict (relationship + coherence across this member's income
            # docs) drives the single per-member coach anchored on the IC.
            chk['cluster_status'] = (income_cluster_advice(obj.application, chk['member'])
                                     if chk['member'] else '')
        return chk

    def get_income_proof_check(self, obj):
        """{name, nric, amount, period, member, name_status, nric_status, ic_present}
        for a salary slip / EPF in an income context — the earner facts cross-checked
        against THAT earner's IC (salary route = the member's IC; STR route = the single
        earner's IC). Null for everything else (the check returns None with no context)."""
        if obj.doc_type not in ('salary_slip', 'epf'):
            return None
        from .income_engine import student_income_proof_check
        return student_income_proof_check(obj)

    def get_str_check(self, obj):
        """{name, nric, status, year, amount, member, name_status, nric_status,
        current_status, ic_present} for an STR document — recipient vs the earner IC +
        whether it's a CURRENT STR. Null for every other doc type."""
        if obj.doc_type != 'str':
            return None
        from .income_engine import student_str_check
        return student_str_check(obj)

    def get_utility_check(self, obj):
        """{name, address, monthly_bill, unpaid_balance, address_status, current_status, bill_month,
        reasonable_status, reasonable_detail, outstanding_status, name_note} for a water /
        electricity bill — address + soft consumption/recency/arrears signals + the standardised
        'MMM YYYY' bill month, never the student's name. Null for every other doc type."""
        if obj.doc_type not in ('water_bill', 'electricity_bill'):
            return None
        from .income_engine import utility_check
        return utility_check(obj)

    def get_bc_check(self, obj):
        """{child/mother/father names + statuses} for a birth certificate — links the
        student to their mother (the income earner). Null for other doc types."""
        if obj.doc_type != 'birth_certificate':
            return None
        from .income_engine import student_bc_check
        return student_bc_check(obj)

    def get_guardianship_check(self, obj):
        """{guardian/ward names + statuses + doc_kind} for a guardianship letter — ties the
        guardian to the student. Null for other doc types."""
        if obj.doc_type != 'guardianship_letter':
            return None
        from .income_engine import student_guardianship_check
        return student_guardianship_check(obj)

    def get_semester_check(self, obj):
        """{name, nric, cgpa, name_status, nric_status} for a semester-result slip — null otherwise."""
        if obj.doc_type != 'semester_result':
            return None
        from .academic_engine import semester_check
        return semester_check(obj)

    def get_school_leaving_check(self, obj):
        """{school, name, name_status, nric, nric_status, kelakuan, activities} for a school-leaving
        certificate — the officer chips (name/NRIC vs the student) + school/conduct/leadership.
        Null for every other doc type."""
        if obj.doc_type != 'school_leaving_cert':
            return None
        from .academic_engine import student_school_leaving_check
        return student_school_leaving_check(obj)

    def get_support_doc_check(self, obj):
        """{name/amount/issuer/kind + read_status} for a declared-income supporting doc.
        Null for other doc types. V1: the officer sees whether the declared informal income
        actually has a readable supporting document behind it."""
        if obj.doc_type != 'income_support_doc':
            return None
        from .income_engine import student_income_support_check
        return student_income_support_check(obj)

    def get_resolved_member(self, obj):
        """The household member this income doc belongs to — stored tag, or name-resolved for a
        blank-tagged doc. '' for non-income docs / when unresolvable. The cockpit box uses it to
        place a doc under the right person even when it was uploaded without a tag."""
        from .income_engine import resolved_member_for
        return resolved_member_for(obj.application, obj)


class ResolutionItemSerializer(serializers.ModelSerializer):
    """A resolution ticket (S3). Read-only to the client; the `code` resolves to
    `admin.scholarship.verdict.item.<code>` copy on the frontend (officer items
    carry their own `prompt`)."""
    class Meta:
        model = ResolutionItem
        fields = [
            'id', 'fact', 'code', 'params', 'prompt', 'kind', 'doc_type',
            'status', 'source', 'resolution_text', 'created_at', 'resolved_at',
        ]
        read_only_fields = fields



class BankAccountSerializer(serializers.ModelSerializer):
    """The student's confirmed payout account (read). Stored only — surfaced to the
    student so they can see/replace what they saved; no admin/sponsor surface yet."""
    class Meta:
        model = BankAccount
        fields = ['bank_name', 'account_number', 'account_holder',
                  'holder_verdict', 'confirmed_at', 'updated_at']
        read_only_fields = fields


class BankAccountConfirmSerializer(serializers.Serializer):
    """The three confirmed fields the student reviews/corrects before saving. The
    holder==student gate runs in the view (it needs the application)."""
    bank_name = serializers.CharField(max_length=120, trim_whitespace=True)
    account_number = serializers.CharField(max_length=40, trim_whitespace=True)
    account_holder = serializers.CharField(max_length=200, trim_whitespace=True)

    def validate_account_number(self, v):
        digits = ''.join(ch for ch in v if ch.isdigit())
        if len(digits) < 5:
            # A real Malaysian account number is well over 5 digits — guard a fat-finger
            # / OCR fragment from being saved as a payout target.
            raise serializers.ValidationError('account_number_invalid')
        return v.strip()


class SignUploadSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=[c[0] for c in ApplicantDocument.DOC_TYPES])
    filename = serializers.CharField(max_length=255, required=False, allow_blank=True)


class DocumentCreateSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=[c[0] for c in ApplicantDocument.DOC_TYPES])
    # Salary-route income docs tag the household member they belong to (so father's
    # and mother's payslips don't overwrite each other). Blank for everything else.
    household_member = serializers.ChoiceField(
        choices=[c[0] for c in ApplicantDocument.HOUSEHOLD_MEMBER_CHOICES],
        required=False, allow_blank=True, default='')
    # Set ONLY for an Action-Centre reviewer-requested upload (the officer ResolutionItem
    # code, e.g. 'officer_3') — gives each request its own document slot. Blank otherwise.
    request_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    storage_path = serializers.CharField(max_length=500)
    original_filename = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    content_type = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    size = serializers.IntegerField(required=False, default=0)


class RefereeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referee
        fields = ['id', 'name', 'role', 'relationship', 'phone', 'email']


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        fields = [
            'id', 'consent_type', 'version', 'locale', 'granted_by',
            'guardian_name', 'guardian_relationship', 'guardian_nric',
            'is_active', 'granted_at',
        ]


class ConsentCreateSerializer(serializers.Serializer):
    """Validates the consent attestation payload.

    S17: when ``granted_by='guardian'``, ``guardian_relationship`` MUST be one
    of the structured codes (no free-text gibberish accepted). The view layer
    additionally enforces (a) guardian-only path when the applicant is a
    minor, and (b) that the required parent_ic / guardianship_letter docs
    have been uploaded before the consent can be recorded.
    """
    _RELATIONSHIPS = [code for code, _ in Consent.GUARDIAN_RELATIONSHIPS]

    consent_type = serializers.CharField(required=False, default='share_with_sponsors')
    locale = serializers.CharField(required=False, default='en')
    granted_by = serializers.ChoiceField(choices=['self', 'guardian'], required=False, default='self')
    guardian_name = serializers.CharField(required=False, allow_blank=True, default='')
    guardian_relationship = serializers.CharField(required=False, allow_blank=True, default='')
    # S19 — guardian's own NRIC (typed); validated against parent_ic Vision
    # OCR at the view layer (hard gate, not just a soft anomaly flag).
    guardian_nric = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_guardian_relationship(self, value):
        if value and value not in self._RELATIONSHIPS:
            raise serializers.ValidationError(
                f'Must be one of: {", ".join(self._RELATIONSHIPS)}.'
            )
        return value
