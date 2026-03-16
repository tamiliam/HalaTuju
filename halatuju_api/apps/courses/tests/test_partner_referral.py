from django.test import TestCase
from apps.courses.models import PartnerOrganisation


class PartnerOrganisationModelTest(TestCase):
    def test_create_partner(self):
        partner = PartnerOrganisation.objects.create(
            code='cumig',
            name='CUMIG',
            contact_email='admin@cumig.org',
        )
        self.assertEqual(partner.code, 'cumig')
        self.assertEqual(str(partner), 'CUMIG (cumig)')
        self.assertTrue(partner.is_active)

    def test_code_unique(self):
        PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        with self.assertRaises(Exception):
            PartnerOrganisation.objects.create(code='cumig', name='CUMIG 2')
