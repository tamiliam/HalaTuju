"""
Tests for FieldTaxonomy model and SPM backfill logic.
"""
import pytest
from django.test import TestCase

from apps.courses.models import FieldTaxonomy, Course
from apps.courses.management.commands.backfill_spm_field_key import classify_course


class FieldTaxonomyModelTest(TestCase):
    """Test that the data migration populated all 37 + 10 entries."""

    def test_total_entries(self):
        """37 leaf fields + 10 parent groups = 47 entries."""
        self.assertEqual(FieldTaxonomy.objects.count(), 47)

    def test_leaf_entries(self):
        """37 leaf entries have a parent_key set."""
        leaves = FieldTaxonomy.objects.filter(parent_key__isnull=False)
        self.assertEqual(leaves.count(), 37)

    def test_parent_groups(self):
        """10 parent groups have no parent_key."""
        groups = FieldTaxonomy.objects.filter(parent_key__isnull=True)
        self.assertEqual(groups.count(), 10)

    def test_all_leaves_have_trilingual_names(self):
        """Every leaf entry has non-empty EN, MS, TA names."""
        for ft in FieldTaxonomy.objects.filter(parent_key__isnull=False):
            self.assertTrue(ft.name_en, f"{ft.key} missing name_en")
            self.assertTrue(ft.name_ms, f"{ft.key} missing name_ms")
            self.assertTrue(ft.name_ta, f"{ft.key} missing name_ta")

    def test_all_leaves_have_image_slug(self):
        """Every leaf entry has an image_slug."""
        for ft in FieldTaxonomy.objects.filter(parent_key__isnull=False):
            self.assertTrue(ft.image_slug, f"{ft.key} missing image_slug")

    def test_known_keys_exist(self):
        """Spot-check critical taxonomy keys."""
        expected = [
            'mekanikal', 'elektrik', 'it-perisian', 'perniagaan',
            'hospitaliti', 'pertanian', 'perubatan', 'pendidikan',
            'undang-undang', 'umum',
        ]
        for key in expected:
            self.assertTrue(
                FieldTaxonomy.objects.filter(key=key).exists(),
                f"Missing taxonomy key: {key}"
            )

    def test_unique_sort_orders(self):
        """All sort_order values are unique."""
        orders = list(FieldTaxonomy.objects.values_list('sort_order', flat=True))
        self.assertEqual(len(orders), len(set(orders)))


class ClassifyCourseTest(TestCase):
    """Test the deterministic classification function."""

    def test_pendidikan_frontend_label(self):
        self.assertEqual(
            classify_course('Pendidikan', 'Pendidikan', 'PISMP Bahasa Melayu'),
            'pendidikan'
        )

    def test_mekanikal_frontend_label(self):
        self.assertEqual(
            classify_course('Mekanikal & Pembuatan', 'Mekanikal Am', 'Diploma Kejuruteraan Mekanikal'),
            'mekanikal'
        )

    def test_mekanikal_mekatronik(self):
        self.assertEqual(
            classify_course('Mekanikal & Pembuatan', 'Mekatronik', 'Diploma Mekatronik'),
            'mekatronik'
        )

    def test_elektrik_frontend_label(self):
        self.assertEqual(
            classify_course('Elektrik & Elektronik', 'Elektrik Kuasa', 'Diploma Kejuruteraan Elektrik'),
            'elektrik'
        )

    def test_it_perisian(self):
        self.assertEqual(
            classify_course('Teknologi Maklumat', 'Teknologi Maklumat', 'Diploma Teknologi Maklumat'),
            'it-perisian'
        )

    def test_it_rangkaian(self):
        self.assertEqual(
            classify_course('Teknologi Maklumat', 'Teknologi Maklumat', 'Diploma Networking & Security'),
            'it-rangkaian'
        )

    def test_aero(self):
        self.assertEqual(
            classify_course('Aero & Marin', 'Aero', 'Sijil Teknologi Penerbangan'),
            'aero'
        )

    def test_marin(self):
        self.assertEqual(
            classify_course('Aero & Marin', 'Marin', 'Sijil Marin Perkapalan'),
            'marin'
        )

    def test_hospitaliti(self):
        self.assertEqual(
            classify_course('Hospitaliti & Gaya Hidup', 'Hospitaliti', 'Diploma Pengurusan Hotel'),
            'hospitaliti'
        )

    def test_kulinari(self):
        self.assertEqual(
            classify_course('Hospitaliti & Gaya Hidup', 'Kulinari', 'Sijil Seni Kulinari Pastri'),
            'kulinari'
        )

    def test_kecantikan(self):
        self.assertEqual(
            classify_course('Hospitaliti & Gaya Hidup', 'Kecantikan', 'Sijil Dandanan Rambut & Spa'),
            'kecantikan'
        )

    def test_automotif_field(self):
        self.assertEqual(
            classify_course('', 'Automotif', 'Sijil Teknologi Automotif'),
            'automotif'
        )

    def test_sivil_field(self):
        self.assertEqual(
            classify_course('', 'Kejuruteraan Sivil', 'Diploma Kejuruteraan Sivil'),
            'sivil'
        )

    def test_senibina_field(self):
        self.assertEqual(
            classify_course('', 'Seni Bina', 'Diploma Seni Bina'),
            'senibina'
        )

    def test_senibina_kapal_is_marin(self):
        """'senibina kapal' = naval architecture → marin, not senibina."""
        self.assertEqual(
            classify_course('', 'Senibina Kapal', 'Diploma Senibina Kapal'),
            'marin'
        )

    def test_kimia_proses(self):
        self.assertEqual(
            classify_course('', 'Kejuruteraan Kimia', 'Diploma Kejuruteraan Kimia'),
            'kimia-proses'
        )

    def test_perniagaan(self):
        self.assertEqual(
            classify_course('', 'Perniagaan', 'Diploma Perniagaan'),
            'perniagaan'
        )

    def test_perakaunan(self):
        self.assertEqual(
            classify_course('', 'Perakaunan', 'Diploma Perakaunan'),
            'perakaunan'
        )

    def test_pertanian(self):
        self.assertEqual(
            classify_course('', 'Pertanian', 'Diploma Pertanian'),
            'pertanian'
        )

    def test_umum_catch_all(self):
        self.assertEqual(
            classify_course('Umum', 'Umum', 'Sijil Tahfiz'),
            'pengajian-islam'
        )

    def test_umum_default(self):
        self.assertEqual(
            classify_course('Umum', 'Umum', 'Sijil Am'),
            'umum'
        )

    def test_unknown_falls_to_umum(self):
        self.assertEqual(
            classify_course('', 'Something Unknown', 'Random Course'),
            'umum'
        )

    def test_ict_multimedia(self):
        self.assertEqual(
            classify_course('ICT & Multimedia', 'ICT & Multimedia', 'Diploma ICT'),
            'multimedia'
        )

    def test_fesyen_under_hospitaliti(self):
        """Fashion courses under Hospitaliti label should map to senireka."""
        self.assertEqual(
            classify_course('Hospitaliti & Gaya Hidup', 'Fesyen', 'Sijil Fesyen & Pakaian'),
            'senireka'
        )

    # ── Production frontend_label tests ──

    def test_prod_mekanikal_automotif_label(self):
        """Production label 'Mekanikal & Automotif' with automotif field."""
        self.assertEqual(
            classify_course('Mekanikal & Automotif', 'Automotif', 'Sijil Teknologi Automotif'),
            'automotif'
        )

    def test_prod_mekanikal_automotif_default(self):
        """Production label defaults to mekanikal."""
        self.assertEqual(
            classify_course('Mekanikal & Automotif', 'Kejuruteraan Mekanikal', 'Diploma Teknologi Kejuruteraan Mekanikal'),
            'mekanikal'
        )

    def test_prod_komputer_it_multimedia_default(self):
        """Production label 'Komputer, IT & Multimedia' with TM field."""
        self.assertEqual(
            classify_course('Komputer, IT & Multimedia', 'Teknologi Maklumat', 'Diploma Teknologi Maklumat'),
            'it-perisian'
        )

    def test_prod_komputer_it_multimedia_ict(self):
        """Production label with ICT field → multimedia."""
        self.assertEqual(
            classify_course('Komputer, IT & Multimedia', 'ICT & Multimedia', 'Diploma ICT'),
            'multimedia'
        )

    def test_prod_perniagaan_perdagangan_default(self):
        self.assertEqual(
            classify_course('Perniagaan & Perdagangan', 'Perniagaan', 'Diploma Perniagaan'),
            'perniagaan'
        )

    def test_prod_perniagaan_perdagangan_perakaunan(self):
        self.assertEqual(
            classify_course('Perniagaan & Perdagangan', 'Perakaunan', 'Diploma Perakaunan'),
            'perakaunan'
        )

    def test_prod_perniagaan_perdagangan_pengurusan(self):
        self.assertEqual(
            classify_course('Perniagaan & Perdagangan', 'Pengurusan', 'Diploma Pengurusan'),
            'pengurusan'
        )

    def test_prod_pertanian_bio_industri(self):
        self.assertEqual(
            classify_course('Pertanian & Bio-Industri', 'Pertanian', 'Diploma Pertanian'),
            'pertanian'
        )

    def test_prod_pertanian_bio_industri_alam_sekitar(self):
        self.assertEqual(
            classify_course('Pertanian & Bio-Industri', 'Kejuruteraan Alam Sekitar', 'Diploma Kejuruteraan Alam Sekitar'),
            'alam-sekitar'
        )

    def test_prod_sivil_senibina_default(self):
        self.assertEqual(
            classify_course('Sivil, Seni Bina & Pembinaan', 'Sivil & Bangunan', 'Diploma Kejuruteraan Sivil'),
            'sivil'
        )

    def test_prod_sivil_senibina_architecture(self):
        self.assertEqual(
            classify_course('Sivil, Seni Bina & Pembinaan', 'Seni Bina', 'Diploma Seni Bina'),
            'senibina'
        )

    def test_prod_hospitaliti_kulinari_pelancongan(self):
        self.assertEqual(
            classify_course('Hospitaliti, Kulinari & Pelancongan', 'Hospitaliti & Gaya Hidup', 'Diploma Pengurusan Hotel'),
            'hospitaliti'
        )

    def test_prod_hospitaliti_kulinari_food(self):
        self.assertEqual(
            classify_course('Hospitaliti, Kulinari & Pelancongan', 'Kulinari', 'Sijil Seni Kulinari'),
            'kulinari'
        )

    def test_prod_aero_marin_minyak_gas_default(self):
        self.assertEqual(
            classify_course('Aero, Marin, Minyak & Gas', 'Aero & Marin', 'Sijil Teknologi Penerbangan'),
            'aero'
        )

    def test_prod_aero_marin_minyak_gas_minyak(self):
        self.assertEqual(
            classify_course('Aero, Marin, Minyak & Gas', 'Minyak & Gas', 'Diploma Teknologi Minyak & Gas'),
            'minyak-gas'
        )

    def test_prod_aero_marin_minyak_gas_marin(self):
        self.assertEqual(
            classify_course('Aero, Marin, Minyak & Gas', 'Kejuruteraan Perkapalan', 'Diploma Kejuruteraan Perkapalan'),
            'marin'
        )

    def test_prod_seni_reka_kreatif_default(self):
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Rekabentuk Grafik', 'Diploma Rekabentuk Grafik'),
            'senireka'
        )

    def test_prod_seni_reka_kreatif_animasi(self):
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Animasi 3D', 'Diploma Animasi 3D'),
            'multimedia'
        )

    def test_prod_sains_teknologi(self):
        self.assertEqual(
            classify_course('Sains & Teknologi', 'Sains', 'Diploma Sains'),
            'sains-hayat'
        )

    def test_prod_perakaunan_kewangan_label(self):
        self.assertEqual(
            classify_course('Perakaunan & Kewangan', 'Perakaunan & Kewangan', 'Diploma Perakaunan'),
            'perakaunan'
        )

    def test_prod_sains_sosial_label(self):
        self.assertEqual(
            classify_course('Sains Sosial', 'Sains Sosial', 'Diploma Sains Sosial'),
            'sains-sosial'
        )

    def test_prod_kejuruteraan_label(self):
        self.assertEqual(
            classify_course('Kejuruteraan & Pembuatan', 'Kejuruteraan', 'Asasi Teknologi Kejuruteraan'),
            'mekanikal'
        )

    def test_field_teknologi_maklumat_keyword(self):
        """Field 'Teknologi Maklumat' should match it-perisian via keyword."""
        self.assertEqual(
            classify_course('', 'Teknologi Maklumat', 'Diploma Teknologi Maklumat'),
            'it-perisian'
        )

    def test_field_mekanikal_pembuatan_keyword(self):
        """Field 'Mekanikal & Pembuatan' should match mekanikal via keyword."""
        self.assertEqual(
            classify_course('', 'Mekanikal & Pembuatan', 'Diploma Mekanikal'),
            'mekanikal'
        )
