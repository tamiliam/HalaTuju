"""Small student-side records: bank account, referees and consent."""

from rest_framework import serializers
from ..models import BankAccount, Consent, Referee


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

    # TD-264 (owner ruling 2026-09-19): a digit here means ASCII 0-9 and nothing else —
    # exactly what the student's own form counts (`/\d/g` is ASCII in JavaScript). The old
    # `str.isdigit()` was Unicode-aware and read '³³³³³' or '١٢٣٤٥' as five digits, so a
    # POST that never came from the form could store a payout target no bank can be paid
    # through. A digit-LIKE character is NOT a separate error: it is simply not counted,
    # so an account left with fewer than five real digits fails the floor below with the
    # error code it always had. Spaces and dashes are untouched — never counted, always kept.
    # drift-test: halatuju-web/src/lib/__tests__/payoutAccountDrift.test.ts
    def validate_account_number(self, v):
        digits = ''.join(ch for ch in v if ch in '0123456789')
        if len(digits) < 5:
            # A real Malaysian account number is well over 5 digits — guard a fat-finger
            # / OCR fragment from being saved as a payout target.
            raise serializers.ValidationError('account_number_invalid')
        return v.strip()


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
