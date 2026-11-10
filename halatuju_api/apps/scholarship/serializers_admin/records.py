"""Reviewer profile, graduation-message moderation and the funding summary row."""

from rest_framework import serializers
from ..models import GraduationMessage, ReviewerProfile
from .. import pool


class ReviewerProfileSerializer(serializers.ModelSerializer):
    """A reviewer's own credentials + contact details (F6). Narrow + self-scoped:
    the phone + share switch are read-only (TD-439); the FK is never exposed or accepted.
    Sensitive staff PII (phone/address) lives only here, never in any outward
    (student/sponsor) serializer.

    ⚠ **One inward widening, and it is PARTIAL** (owner, 2026-08-02, request #10). The reviewers
    surface (`AdminReviewerDetailView`) shows an org_admin the credentials, the languages and the
    PHONE of their own organisation's reviewers — the person handing out cases needs to reach
    them. It does **not** serialise the ADDRESS fields, and must not start to: assigning a case
    is no reason to read where somebody lives. `share_phone_with_students` travels with the phone
    so the screen can say which number a student may be given; showing a withheld number without
    that caveat would defeat the consent this organisation asked the reviewer for.

    Recorded in `docs/scholarship/role-matrix.md`; a test in `test_reviewers_surface.py` asserts
    the address cannot appear in that payload. Widen it only by owner decision, doc first."""

    class Meta:
        model = ReviewerProfile
        fields = [
            'highest_qualification', 'university', 'graduation_year',
            'field_of_study', 'phone', 'address',
            'street_address', 'postcode', 'city', 'state',
            'english_fluency', 'bm_fluency', 'tamil_fluency', 'other_language', 'other_language_fluency',
            'share_phone_with_students']
        read_only_fields = ['phone', 'share_phone_with_students']   # TD-439: written by admin/me/ only

    def validate(self, attrs):   # S2: the optional 4th language is both or neither (`staff_languages`)
        from ..staff_languages import checked_other_language
        return checked_other_language(super().validate(attrs), self.instance)

    def validate_graduation_year(self, value):
        # A plausible graduation year (or None). PositiveSmallIntegerField already
        # bars negatives; keep the upper bound generous and the lower bound sane.
        if value is not None and not (1950 <= value <= 2100):
            raise serializers.ValidationError('Enter a valid graduation year.')
        return value


class AdminGraduationMessageSerializer(serializers.ModelSerializer):
    """F9a — staff (myNADI) view of a graduation thank-you awaiting moderation. Staff
    are NOT the anonymity boundary (they can see the student), so the full text +
    scan outcome is shown. ``ref`` is included so the reviewer sees the same anon
    alias the sponsor will, and ``application`` links to the cockpit."""
    ref = serializers.SerializerMethodField()

    class Meta:
        model = GraduationMessage
        fields = ['id', 'application', 'ref', 'status', 'raw_text', 'scrubbed_text',
                  'scan_result', 'approved_by', 'review_note', 'created_at', 'reviewed_at']
        read_only_fields = fields

    def get_ref(self, obj):
        return pool.pool_ref(obj.application_id)


class FundingSummaryRowSerializer(serializers.Serializer):
    """Sprint 14 — one student's line in the Payments FUNDING SUMMARY.

    **Allowlist by construction** (the `SponsorPoolCardSerializer` pattern): a plain
    ``Serializer`` where every field is explicit and derived, with ZERO model passthrough — so
    a new column on `ScholarshipApplication` can never reach this payload by accident. Input is
    a `ScholarshipApplication`.

    This is the ONLY student data the `finance` role ever sees, so the boundary is drawn at
    "what do you need to reconcile a payment run": who, how much was awarded, how much has been
    paid, what is left, which eWallet it goes to, and when they were last paid. Deliberately
    EXCLUDED and not to be added without a role-matrix change: NRIC, contact details, address,
    documents, income figures, verdicts, academic results, narrative — none of it is needed to
    check a payment, and finance has no B40 scope to see it through. A snapshot test pins the
    exact key set so a well-meant addition fails loudly.

    ``name`` is included on purpose: a payment file is made of named people, and finance must be
    able to match a line to the Vircle CSV. It is NOT a link — the frontend renders it as plain
    text, because finance has no applicant route to link to.
    """
    application_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    ref = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    pathway = serializers.SerializerMethodField()
    award_amount = serializers.SerializerMethodField()
    paid_to_date = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    vircle_id = serializers.SerializerMethodField()
    last_run = serializers.SerializerMethodField()
    # P2b — WHICH GIFT funds this student. Finance reconciles per programme once an org runs
    # more than one, and a payment file is drawn from one gift's money. A column, deliberately
    # not a grouping: grouping is a layout change to a live finance screen and owes a design
    # pass; the fact itself is useful now and costs no redesign.
    programme = serializers.SerializerMethodField()
    # TD-244 (2026-10-03) — Vircle gave this student a wallet but has not reported it switched on
    # (`vircle_id` held, `vircle_activated_at` null). A REPORT, never an email (decisions.md "The
    # 48-hour activation chaser is retired"): the screen names them so the gap is somebody's job.
    # A yes/no about payment readiness — no date, no phone, nothing about the student.
    wallet_not_live = serializers.SerializerMethodField()

    # Coarse funding status — the three payable states, nothing finer. A finance admin needs to
    # know a student is in the paying loop, not where they sit in the review funnel.
    _STATUS = {'awarded': 'awarded', 'active': 'active', 'maintenance': 'maintenance'}

    def get_application_id(self, obj):
        return obj.id

    def get_name(self, obj):
        return (getattr(getattr(obj, 'profile', None), 'name', '') or '').strip()

    def get_ref(self, obj):
        return pool.pool_ref(obj.id) or ''

    def get_status(self, obj):
        return self._STATUS.get(obj.status, '')

    def get_pathway(self, obj):
        return (obj.chosen_pathway or '').strip()

    def get_award_amount(self, obj):
        return str(obj.award_amount or 0)

    def get_paid_to_date(self, obj):
        from .. import payments
        return str(payments.paid_to_date(obj))

    def get_remaining(self, obj):
        from .. import payments
        award = obj.award_amount or 0
        rem = award - payments.paid_to_date(obj)
        return str(rem if rem > 0 else 0)

    def get_vircle_id(self, obj):
        return (obj.vircle_id or '').strip()

    def get_wallet_not_live(self, obj):
        return bool((obj.vircle_id or '').strip()) and obj.vircle_activated_at is None

    def get_programme(self, obj):
        """The gift funding this student — ``{id, name}`` or None. Name only (no code, no
        organisation): finance needs to tell two gifts apart, not to navigate the tenancy."""
        p = getattr(obj, 'programme', None)
        if p is None:
            return None
        return {'id': p.id, 'name': (p.name_en or '').strip()}

    def get_last_run(self, obj):
        """The newest COMPLETED run this student was paid in — {reference, payment_date}, or
        None. Answers "when did we last pay them?" without exposing the run's other students."""
        item = (obj.payment_run_items
                .filter(included=True, run__status='completed')
                .select_related('run').order_by('-run__payment_date', '-run_id').first())
        if item is None:
            return None
        return {'reference': item.run.reference, 'payment_date': item.run.payment_date}
