"""Tests for the deterministic anomaly engine (S16 Phase A).

One positive + one negative case per rule. Plus an integration sanity check
that ordering matches the registered detector list (so the admin sees a
predictable surface for the same data).
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.anomaly_engine import detect_anomalies
from apps.scholarship.models import (
    ApplicantDocument, FundingNeed, ScholarshipApplication, ScholarshipCohort,
)


class _Base(TestCase):
    """Shared fixture: a clean profile + a shortlisted application with
    fields zeroed out, so each test toggles only what it cares about."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        # Fresh profile + app per test to keep rule states isolated.
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'anom-{self.id()}',
            name='Priya Devi',
            nric='030101-14-1234',
            preferred_state='Selangor',
            household_income=2000,
            household_size=4,
            receives_str=False,
            receives_jkm=False,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
        )


def _add_ic(app, *, vision_nric='', vision_name='', vision_address=''):
    """Convenience: attach an IC document with S13 Vision fields populated."""
    return ApplicantDocument.objects.create(
        application=app, doc_type='ic', storage_path=f'{app.id}/ic/x',
        vision_nric=vision_nric, vision_name=vision_name, vision_address=vision_address,
        vision_run_at=timezone.now(), vision_error='',
    )


# ─── Per-rule tests ─────────────────────────────────────────────────────────

class TestVisionNricMismatch(_Base):
    def test_flag_when_ocr_nric_differs(self):
        _add_ic(self.app, vision_nric='710829-02-5709', vision_name=self.profile.name)
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('vision_nric_mismatch', codes)

    def test_no_flag_when_ocr_nric_matches(self):
        _add_ic(self.app, vision_nric=self.profile.nric, vision_name=self.profile.name)
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('vision_nric_mismatch', codes)


class TestVisionNameMismatch(_Base):
    def test_flag_on_partial_name(self):
        # OCR omits the middle name → partial → flag.
        _add_ic(self.app, vision_nric=self.profile.nric, vision_name='PRIYA KRISHNAN')
        # First override profile name so partial logic triggers.
        self.profile.name = 'PRIYA DEVI KRISHNAN'
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('vision_name_mismatch', codes)

    def test_no_flag_on_exact_match(self):
        _add_ic(self.app, vision_nric=self.profile.nric, vision_name=self.profile.name)
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('vision_name_mismatch', codes)


class TestAddressStateMismatch(_Base):
    def test_flag_when_ic_state_differs_from_profile_state(self):
        # Profile says Selangor; IC address says Kedah.
        _add_ic(
            self.app, vision_nric=self.profile.nric, vision_name=self.profile.name,
            vision_address='NO 12 JALAN ABC, TAMAN BAHAGIA, 08000 SUNGAI PETANI, KEDAH',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('address_state_mismatch', codes)

    def test_no_flag_when_states_align_after_wp_normalisation(self):
        self.profile.preferred_state = 'W.P. Putrajaya'
        self.profile.save()
        _add_ic(
            self.app, vision_nric=self.profile.nric, vision_name=self.profile.name,
            vision_address='BLOK A, PERSIARAN PERDANA, 62100 PUTRAJAYA',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        # "Putrajaya" / "W.P. Putrajaya" normalise equal — no flag.
        self.assertNotIn('address_state_mismatch', codes)


class TestJkmHighIncome(_Base):
    def test_flag_when_jkm_with_income_over_3000(self):
        self.profile.receives_jkm = True
        self.profile.household_income = 5000
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('jkm_high_income', codes)

    def test_no_flag_when_jkm_with_low_income(self):
        self.profile.receives_jkm = True
        self.profile.household_income = 2500
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('jkm_high_income', codes)


class TestHouseholdSizeOne(_Base):
    def test_flag_when_household_size_is_one(self):
        self.profile.household_size = 1
        self.profile.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('household_size_one', codes)

    def test_no_flag_when_household_size_is_normal(self):
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('household_size_one', codes)


class TestFirstInFamilyWithSiblingsStudying(_Base):
    def test_flag_when_first_in_family_and_legacy_siblings_studying(self):
        # Legacy combined count, no split → can't confirm first-gen → flag (clarify-query).
        self.app.first_in_family = True
        self.app.siblings_studying_count = 2
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('first_in_family_with_siblings_studying', codes)

    def test_no_flag_when_count_is_zero(self):
        self.app.first_in_family = True
        self.app.siblings_studying_count = 0
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('first_in_family_with_siblings_studying', codes)

    def test_flag_when_sibling_in_tertiary(self):
        # P2: the split is authoritative — a sibling in tertiary genuinely contradicts.
        self.app.first_in_family = True
        self.app.siblings_in_school = 1
        self.app.siblings_in_tertiary = 1
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('first_in_family_with_siblings_studying', codes)

    def test_auto_resolved_when_only_siblings_in_school(self):
        # P2: siblings only in school do NOT contradict first-to-university → no flag,
        # even though the legacy count is positive. The split wins.
        self.app.first_in_family = True
        self.app.siblings_studying_count = 2
        self.app.siblings_in_school = 2
        self.app.siblings_in_tertiary = 0
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('first_in_family_with_siblings_studying', codes)


def _add_bill(app, doc_type, amount):
    """Attach a utility bill with a Gemini-extracted monthly amount."""
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'{app.id}/{doc_type}/x',
        vision_fields={'fields': {'amount': amount}}, vision_fields_run_at=timezone.now(),
    )


class TestUtilityHighVsIncome(_Base):
    def test_flag_when_utilities_disproportionate(self):
        # RM180 of bills on a declared RM500 income = 36% → flag.
        self.profile.household_income = 500
        self.profile.save()
        _add_bill(self.app, 'water_bill', 'RM 90.00')
        _add_bill(self.app, 'electricity_bill', 'RM 90.00')
        anomalies = {a['code']: a['params'] for a in detect_anomalies(self.app)}
        self.assertIn('utility_high_vs_income', anomalies)
        self.assertEqual(anomalies['utility_high_vs_income']['percent'], 36)

    def test_no_flag_when_utilities_modest(self):
        # RM180 of bills on a declared RM2000 income = 9% → no flag.
        _add_bill(self.app, 'water_bill', 'RM 90.00')
        _add_bill(self.app, 'electricity_bill', 'RM 90.00')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('utility_high_vs_income', codes)

    def test_no_flag_when_income_unknown(self):
        self.profile.household_income = 0
        self.profile.save()
        _add_bill(self.app, 'water_bill', 'RM 90.00')
        _add_bill(self.app, 'electricity_bill', 'RM 90.00')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('utility_high_vs_income', codes)


class TestFundingOtherWithoutNote(_Base):
    def test_flag_when_other_ticked_but_note_blank(self):
        FundingNeed.objects.create(
            application=self.app, categories=['living', 'other'], funding_note='',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('funding_other_without_note', codes)

    def test_no_flag_when_other_ticked_with_note(self):
        FundingNeed.objects.create(
            application=self.app, categories=['other'],
            funding_note='Bus pass for the daily commute.',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('funding_other_without_note', codes)


class TestDeclarationNameMismatch(_Base):
    def test_flag_when_declaration_differs_from_profile(self):
        # Profile name has a middle name absent from the declaration — partial.
        self.profile.name = 'NUR AISYAH BINTI ABDULLAH'
        self.profile.save()
        self.app.declaration_name = 'NUR AISYAH ABDULLA'  # missing H — true diff
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('declaration_name_mismatch', codes)

    def test_no_flag_when_declaration_matches_profile(self):
        self.app.declaration_name = self.profile.name
        self.app.save()
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('declaration_name_mismatch', codes)


class TestDeviceInFunding(_Base):
    def test_flag_when_device_ticked(self):
        FundingNeed.objects.create(
            application=self.app, categories=['living', 'device'],
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('device_in_funding', codes)

    def test_no_flag_when_device_not_ticked(self):
        FundingNeed.objects.create(
            application=self.app, categories=['living', 'transport'],
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('device_in_funding', codes)


# ─── Integration / shape tests ──────────────────────────────────────────────

class TestAnomalyShape(_Base):
    def test_empty_application_returns_empty_list(self):
        """A bare application with default values produces no flags."""
        self.assertEqual(detect_anomalies(self.app), [])

    def test_anomaly_dict_shape(self):
        """Each flag is a JSON-serialisable dict with code + params."""
        self.profile.household_size = 1
        self.profile.save()
        anomalies = detect_anomalies(self.app)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(set(anomalies[0].keys()), {'code', 'params'})
        self.assertIsInstance(anomalies[0]['code'], str)
        self.assertIsInstance(anomalies[0]['params'], dict)

    def test_multiple_flags_in_registration_order(self):
        """Order is stable + matches the _DETECTORS tuple — so the admin
        always sees the same flags in the same order for the same data."""
        # Trigger flags from two detectors registered in this order (jkm_high_income then
        # funding_other_without_note) and confirm the output preserves _DETECTORS order.
        self.profile.receives_jkm = True
        self.profile.household_income = 5000
        self.profile.save()
        FundingNeed.objects.create(
            application=self.app, categories=['other'], funding_note='',
        )
        codes = [a['code'] for a in detect_anomalies(self.app)]
        # jkm comes before funding_other in _DETECTORS.
        self.assertEqual(codes, [
            'jkm_high_income',
            'funding_other_without_note',
        ])


# ─── S17: parent_ic anomalies ───────────────────────────────────────────────

def _add_parent_ic(app, *, vision_nric='', vision_name=''):
    return ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'{app.id}/parent_ic/x',
        vision_nric=vision_nric, vision_name=vision_name,
        vision_run_at=timezone.now(), vision_error='',
    )


class TestParentIcNameMismatch(_Base):
    def _add_guardian_consent(self, name='Grandma'):
        from apps.scholarship.models import Consent
        return Consent.objects.create(
            application=self.app, version='t', is_active=True,
            granted_by='guardian', guardian_name=name,
            guardian_relationship='grandparent',
        )

    def test_flag_when_ocr_name_differs_from_typed_guardian(self):
        self._add_guardian_consent(name='Grandma Lim')
        _add_parent_ic(self.app, vision_nric='600101-14-0001', vision_name='Totally Different Person')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('parent_ic_name_mismatch', codes)

    def test_no_flag_when_names_match(self):
        self._add_guardian_consent(name='GRANDMA LIM')
        _add_parent_ic(self.app, vision_nric='600101-14-0001', vision_name='Grandma Lim')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('parent_ic_name_mismatch', codes)

    def test_no_flag_when_no_active_consent(self):
        """Without a guardian consent row, there's no typed name to compare against."""
        _add_parent_ic(self.app, vision_nric='600101-14-0001', vision_name='Anyone')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('parent_ic_name_mismatch', codes)


class TestParentIcUnderage(_Base):
    def test_flag_when_parent_ic_age_under_18(self):
        # IC NRIC year 2010 → age ~16 (uploaded as the supposed parent's IC).
        _add_parent_ic(self.app, vision_nric='100101-14-1111', vision_name='Some Name')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertIn('parent_ic_underage', codes)

    def test_no_flag_when_parent_ic_is_adult(self):
        _add_parent_ic(self.app, vision_nric='710101-14-2222', vision_name='Adult Person')
        codes = [a['code'] for a in detect_anomalies(self.app)]
        self.assertNotIn('parent_ic_underage', codes)


class CockpitAnomalyDedupeTests(TestCase):
    """Cockpit consolidation: the admin serializer drops identity NRIC/name
    mismatch flags (the verdict tile + the identity caveat own them) so the
    merged Outstanding panel never double-asks. The raw engine still emits them."""

    def test_serializer_drops_identity_mismatch_flags(self):
        from unittest.mock import patch
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        raw = [
            {'code': 'vision_nric_mismatch', 'params': {}},
            {'code': 'vision_name_mismatch', 'params': {}},
            {'code': 'household_size_one', 'params': {}},
        ]
        with patch('apps.scholarship.anomaly_engine.detect_anomalies', return_value=raw):
            out = AdminApplicationDetailSerializer().get_anomalies(object())
        codes = [a['code'] for a in out]
        self.assertEqual(codes, ['household_size_one'])
        self.assertNotIn('vision_nric_mismatch', codes)
        self.assertNotIn('vision_name_mismatch', codes)
