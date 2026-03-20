"""
Tests for W8 Part 1: derive_institution_modifiers command.
"""
from django.test import TestCase

from apps.courses.management.commands.derive_institution_modifiers import (
    derive_cultural_safety_net,
    derive_urban,
)
from apps.courses.models import Institution


def _inst(**overrides):
    """Build a minimal Institution instance (not saved to DB)."""
    defaults = {
        'institution_id': 'TEST001',
        'institution_name': 'Test Institution',
        'type': 'IPTA',
        'state': 'Selangor',
        'address': '',
    }
    defaults.update(overrides)
    return Institution(**defaults)


# ── Urban classification ─────────────────────────────────────────────


class TestDeriveUrban(TestCase):

    def test_kl_always_urban(self):
        inst = _inst(state='WP Kuala Lumpur')
        self.assertTrue(derive_urban(inst))

    def test_putrajaya_always_urban(self):
        inst = _inst(state='WP Putrajaya')
        self.assertTrue(derive_urban(inst))

    def test_penang_always_urban(self):
        """Penang is fully urbanised — urban regardless of address."""
        inst = _inst(state='Pulau Pinang', address='')
        self.assertTrue(derive_urban(inst))

    def test_shah_alam_address_urban(self):
        inst = _inst(state='Selangor', address='Persiaran Raja Muda, Shah Alam')
        self.assertTrue(derive_urban(inst))

    def test_ipoh_address_urban(self):
        inst = _inst(state='Perak', address='Jalan Sultan Azlan Shah, Ipoh')
        self.assertTrue(derive_urban(inst))

    def test_johor_bahru_address_urban(self):
        inst = _inst(state='Johor', address='Jalan Skudai, Johor Bahru')
        self.assertTrue(derive_urban(inst))

    def test_kota_kinabalu_urban(self):
        inst = _inst(state='Sabah', address='Kota Kinabalu, Sabah')
        self.assertTrue(derive_urban(inst))

    def test_kuching_urban(self):
        inst = _inst(state='Sarawak', address='Jalan Tun Ahmad, Kuching')
        self.assertTrue(derive_urban(inst))

    def test_rural_perak_not_urban(self):
        inst = _inst(state='Perak', address='Kampung Gajah, Perak')
        self.assertFalse(derive_urban(inst))

    def test_rural_sabah_not_urban(self):
        inst = _inst(state='Sabah', address='Sandakan, Sabah')
        self.assertFalse(derive_urban(inst))

    def test_rural_kelantan_not_urban(self):
        """Kota Bharu is urban, but generic Kelantan address is not."""
        inst = _inst(state='Kelantan', address='Tanah Merah, Kelantan')
        self.assertFalse(derive_urban(inst))

    def test_kota_bharu_urban(self):
        inst = _inst(state='Kelantan', address='Jalan Post Office, Kota Bharu')
        self.assertTrue(derive_urban(inst))

    def test_city_in_institution_name(self):
        """Urban city mentioned in name (not address) still counts."""
        inst = _inst(
            state='Johor',
            institution_name='Politeknik Johor Bahru',
            address='',
        )
        self.assertTrue(derive_urban(inst))

    def test_empty_address_non_urban_state(self):
        inst = _inst(state='Pahang', address='')
        self.assertFalse(derive_urban(inst))

    def test_case_insensitive_match(self):
        inst = _inst(state='Perak', address='JALAN SULTAN AZLAN SHAH, IPOH')
        self.assertTrue(derive_urban(inst))


# ── Cultural safety net ──────────────────────────────────────────────


class TestDeriveCulturalSafetyNet(TestCase):

    def test_selangor_high(self):
        inst = _inst(state='Selangor')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_perak_high(self):
        inst = _inst(state='Perak')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_penang_high(self):
        inst = _inst(state='Pulau Pinang')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_negeri_sembilan_high(self):
        inst = _inst(state='Negeri Sembilan')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_kl_high(self):
        inst = _inst(state='WP Kuala Lumpur')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_johor_high(self):
        inst = _inst(state='Johor')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_kedah_high(self):
        inst = _inst(state='Kedah')
        self.assertEqual(derive_cultural_safety_net(inst), 'high')

    def test_kelantan_low(self):
        inst = _inst(state='Kelantan')
        self.assertEqual(derive_cultural_safety_net(inst), 'low')

    def test_terengganu_low(self):
        inst = _inst(state='Terengganu')
        self.assertEqual(derive_cultural_safety_net(inst), 'low')

    def test_sabah_low(self):
        inst = _inst(state='Sabah')
        self.assertEqual(derive_cultural_safety_net(inst), 'low')

    def test_sarawak_low(self):
        inst = _inst(state='Sarawak')
        self.assertEqual(derive_cultural_safety_net(inst), 'low')

    def test_perlis_low(self):
        inst = _inst(state='Perlis')
        self.assertEqual(derive_cultural_safety_net(inst), 'low')

    def test_pahang_low(self):
        inst = _inst(state='Pahang')
        self.assertEqual(derive_cultural_safety_net(inst), 'low')


# ── Management command (DB integration) ──────────────────────────────


class TestDeriveCommandDryRun(TestCase):

    def setUp(self):
        Institution.objects.create(
            institution_id='T001',
            institution_name='Universiti Malaya',
            type='IPTA',
            state='WP Kuala Lumpur',
            address='Jalan Universiti',
        )
        Institution.objects.create(
            institution_id='T002',
            institution_name='Kolej Matrikulasi Pahang',
            type='Kolej Matrikulasi',
            state='Pahang',
            address='Kuala Lipis',
        )

    def test_dry_run_does_not_write(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('derive_institution_modifiers', stdout=out)
        # DB should still have empty modifiers
        t001 = Institution.objects.get(pk='T001')
        self.assertEqual(t001.modifiers, {})

    def test_apply_writes_modifiers(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('derive_institution_modifiers', '--apply', stdout=out)

        t001 = Institution.objects.get(pk='T001')
        self.assertTrue(t001.modifiers['urban'])
        self.assertEqual(t001.modifiers['cultural_safety_net'], 'high')

        t002 = Institution.objects.get(pk='T002')
        self.assertFalse(t002.modifiers['urban'])
        self.assertEqual(t002.modifiers['cultural_safety_net'], 'low')

    def test_idempotent(self):
        """Running twice produces the same result."""
        from django.core.management import call_command
        from io import StringIO
        call_command('derive_institution_modifiers', '--apply', stdout=StringIO())
        call_command('derive_institution_modifiers', '--apply', stdout=StringIO())

        t001 = Institution.objects.get(pk='T001')
        self.assertTrue(t001.modifiers['urban'])
        self.assertEqual(t001.modifiers['cultural_safety_net'], 'high')
