"""Sponsor-facing serializers for a sponsored student: sponsorship, awards, bursary agreement, semester results and graduation messages."""

from rest_framework import serializers
from .. import results_review
from ..models import GraduationMessage, SemesterResult
from .sponsor import SponsorPoolCardSerializer


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
        return results_review.accepted_count(sponsorship.application)  # S4a: accepted only


class SponsorMyStudentDetailSerializer(SponsorSponsorshipSerializer):
    """A student the sponsor OWNS, for their portfolio detail page: the sponsorship (amount /
    status / journey signals) + the anonymised student card + the generated anon PROFILE markdown.
    Still an allowlist — only the reviewed anon_markdown is added, never the named profile."""
    anon_profile = serializers.SerializerMethodField()
    spending = serializers.SerializerMethodField()

    def get_anon_profile(self, sponsorship):
        sp = getattr(sponsorship.application, 'sponsor_profile', None)
        return (sp.anon_markdown or '') if sp else ''

    def get_spending(self, sponsorship):
        """Categories and totals only — see `spend_sponsor`, which builds the payload one
        aggregate at a time.

        ⚠ **NEVER reuse `spend_report` here.** That module serves the OFFICER and names
        merchants and students deliberately; this field serves an outsider. Two audiences that
        different must not share a payload, or a field added for the officer arrives on the
        sponsor card by accident.

        ⚠ `None` (not an empty card) when nothing has been imported: four zeroes and an empty
        donut would claim the student has spent nothing, and the likelier truth is that no
        report has reached us yet.
        """
        from .. import spend_sponsor
        return spend_sponsor.sponsor_card(sponsorship.application)


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
        from .. import agreement_guard, storage
        if not obj.pdf_storage_path or agreement_guard.is_void(obj):   # A1.13: not a withdrawn PDF
            return None
        # org-fence (Sprint 4, belt-and-braces) — see ApplicantDocumentSerializer.
        app = getattr(obj, 'application', None)
        path_org = storage.resolve_org_for_path(obj.pdf_storage_path)
        if path_org is not None and app is not None and path_org != app.owning_organisation_id:
            return None
        return storage.create_signed_download_url(obj.pdf_storage_path)


class SemesterResultSerializer(serializers.ModelSerializer):
    """F9a — a student's own in-programme semester result (read). This is the
    student's own data (not the sponsor boundary), so a ModelSerializer is fine.
    The uploaded ``results_slip`` is myNADI-only; only its id is surfaced here."""
    class Meta:
        model = SemesterResult
        fields = ['id', 'semester', 'cgpa', 'graduated', 'results_slip', 'note', 'created_at', 'review_status', 'review_note']
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
