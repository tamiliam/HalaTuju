"""Sponsor-facing serializers: the sponsor, the pool cards, referrals and standing gifts."""

from rest_framework import serializers
from .. import pool
from ..models import Sponsor, SponsorReferral, StandingGift


class SponsorSerializer(serializers.ModelSerializer):
    """Phase E: a sponsor's own account view (read-only). Drives the portal's
    pending/approved/rejected state. Excludes internal vetting fields."""
    is_approved = serializers.BooleanField(read_only=True)
    profile_complete = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()

    class Meta:
        model = Sponsor
        fields = ['id', 'name', 'email', 'phone', 'source', 'organisation',
                  'status', 'is_approved', 'profile_complete', 'notify_frequency',
                  'created_at', 'terms']
        read_only_fields = fields

    def get_profile_complete(self, obj):
        """True when the required registration details (phone, source, PDPA
        consent) are all present — a Google sponsor lands without them and must
        complete this step before vetting proceeds."""
        return bool(obj.phone and obj.source and obj.consent_at)

    def get_terms(self, obj):
        """Whether this sponsor still owes an acceptance of the current terms.

        The RULE lives on the server (`sponsor_terms.acceptance_state`) and the screen only reads
        the answer — the same discipline as `finance_check_required`. `needs_terms` is the whole
        gate: an active version exists and this sponsor has no row for it. Grandfathering is
        therefore data (a pre-written row), never a branch here.

        ⚠ Also gated on the PLATFORM flag. While `SPONSOR_TERMS_ENABLED` is off, `needs_terms` is
        always False, so today's approved sponsors cannot be locked out of a portal they already
        use by a version being published.
        """
        from django.conf import settings
        from .. import sponsor_terms
        state = sponsor_terms.acceptance_state(obj)
        if not getattr(settings, 'SPONSOR_TERMS_ENABLED', False):
            state = {**state, 'needs_terms': False}
        return state


def _funding_need_or_none(application):
    from ..models import FundingNeed
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
    confirmed offer / chosen programme). ``school`` is the student's SECONDARY school (the
    one they attended) — surfaced on the sponsor DETAIL by owner decision 2026-07-18 (it is
    material context for a sponsor; the anonymity promise to sponsors covers name/NRIC/photo/
    contact/address, not the school). ``state`` stays region-level. ``blurb`` is a ≤20-word
    card-strict one-liner (generated + identifier-scanned at publish)."""
    # `id` is the application row id — used only as the opaque key to fetch the
    # detail; it is not identifying. `ref` is the human-facing alias.
    id = serializers.IntegerField(read_only=True)
    ref = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    school = serializers.SerializerMethodField()        # the SECONDARY school attended (owner 2026-07-18)
    field = serializers.SerializerMethodField()
    course = serializers.SerializerMethodField()        # the confirmed programme name
    academic = serializers.SerializerMethodField()
    institution = serializers.SerializerMethodField()   # TARGET university — never the school
    blurb = serializers.SerializerMethodField()         # ≤20-word card-strict one-liner
    funding_categories = serializers.SerializerMethodField()
    programme_months = serializers.SerializerMethodField()
    award_amount = serializers.SerializerMethodField()  # E3: admin-set; non-identifying
    funded_amount = serializers.SerializerMethodField()  # partial-funding seam: raised so far
    funded = serializers.SerializerMethodField()          # grace window: a just-funded read-only card
    portfolio_status = serializers.SerializerMethodField()  # My-students: single lifecycle badge (post-accept)
    supported_semesters = serializers.SerializerMethodField()  # how many semesters the bursary funds
    progress_state = serializers.SerializerMethodField()  # F2: coarse, non-identifying
    support_status = serializers.SerializerMethodField()  # S5: coarse operational signal
    enrolment_verified = serializers.SerializerMethodField()  # R5: bare boolean badge
    field_image_slug = serializers.SerializerMethodField()  # redesign: catalogue artwork
    reporting_date = serializers.SerializerMethodField()     # redesign: course-start countdown
    course_href = serializers.SerializerMethodField()        # link to the public course page

    def get_ref(self, app):
        return pool.pool_ref(app.id)

    def get_field_image_slug(self, app):
        # Catalogue field artwork (shared by hundreds of courses) — non-identifying.
        return _resolve_field_image_slug(app, self.context)

    def get_course_href(self, app):
        # The programme's public HalaTuju page, so the course name is a link and not dead text
        # (owner 2026-07-25). Non-identifying by construction: a course page is shared by every
        # student on that programme — the same class as field_image_slug above. '' → plain text.
        from .. import card_display
        return card_display.course_href(app)

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
        from .. import maintenance
        return maintenance.sponsor_support_status(app)

    def get_award_amount(self, app):
        return str(app.award_amount) if app.award_amount is not None else None

    def get_funded_amount(self, app):
        # Money RAISED toward award_amount so far = sum of HOLDING (offered+active)
        # sponsorships. Non-identifying (a ringgit figure). Today a pooled ('recommended')
        # student has none — funding is full-or-nothing and a funded student leaves the
        # pool — so this is '0' on every card; it drives the funding bar as an EMPTY rail.
        # When partial funding (TD-075) ships, the same field renders partial/full with NO
        # frontend change. Reads the list view's `funded_total` annotation when present
        # (avoids an N+1 across the card grid); falls back to a per-object sum otherwise.
        from django.db.models import Sum
        from ..models import Sponsorship
        if hasattr(app, 'funded_total'):
            total = app.funded_total
        else:
            total = (app.sponsorships.filter(status__in=Sponsorship.HOLDING)
                     .aggregate(t=Sum('amount'))['t'])
        return str(total or 0)

    def get_funded(self, app):
        # True for a just-funded card in the grace window (bar full, no fund button). The DISPLAY
        # pool holds only fundable ('recommended') OR recently-funded students, so any non-recommended
        # card here is a funded one — a single, unambiguous signal for the frontend's "Funded" state.
        return app.status != 'recommended'

    def get_portfolio_status(self, app):
        # The single sponsor-facing lifecycle badge for a student in the My-students portfolio; None
        # for a discovery-pool ('recommended') card. 'Awaiting acceptance' is FE-derived from the
        # sponsorship 'offered' status, not here.
        return pool.sponsor_portfolio_status(app)

    def get_supported_semesters(self, app):
        return pool.supported_semesters(app)

    def get_state(self, app):
        # State-level region only — street/postcode/city are never exposed.
        return (getattr(app.profile, 'preferred_state', '') or '') if app.profile else ''

    def get_school(self, app):
        # The SECONDARY school the student attended (owner 2026-07-18: shown to sponsors as
        # material context). Distinct from the TARGET `institution`.
        return (getattr(app.profile, 'school', '') or '') if app.profile else ''

    def get_field(self, app):
        return app.field_of_study or ''

    def get_course(self, app):
        # The confirmed programme NAME (e.g. "Diploma Kejuruteraan Mekanikal") — resolved
        # defence-in-depth so a mis-slotted offer (an institution name / a "Tarikh…" line in
        # the course slot) or a raw pre-U value never reaches a sponsor. See card_display.
        from .. import card_display
        return card_display.resolve_course(app)

    def get_academic(self, app):
        return pool.academic_band(app.profile)

    def get_institution(self, app):
        # The TARGET institution the student will study AT, e.g. "Politeknik Ungku Omar" —
        # resolved so a date/'Tarikh' junk value and, critically, a SECONDARY SCHOOL are
        # NEVER surfaced to a sponsor (the allowlist privacy promise; card_display enforces
        # the school-block). '' when nothing safe resolves → the card shows the course only.
        from .. import card_display
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
