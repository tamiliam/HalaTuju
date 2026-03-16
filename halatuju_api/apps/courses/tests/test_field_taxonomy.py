"""
Tests for FieldTaxonomy model, SPM backfill logic, and STPM classification.
"""
import pytest
from django.test import TestCase

from apps.courses.models import FieldTaxonomy, Course
from apps.courses.management.commands.backfill_spm_field_key import classify_course
from apps.courses.management.commands.classify_stpm_fields import classify_stpm_course


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

    # ── Substring false-positive regression tests ──

    def test_fisioterapi_not_kecantikan(self):
        """'fisioterapi' contains 'terapi' but is medical, not beauty."""
        self.assertEqual(
            classify_course('', 'Fisioterapi', 'Diploma Fisioterapi'),
            'perubatan'
        )

    def test_kecergasan_not_minyak_gas(self):
        """'kecergasan' contains 'gas' but is fitness, not oil & gas."""
        self.assertEqual(
            classify_course('', 'Kecergasan Pertahanan', 'Diploma Kecergasan Pertahanan'),
            'sains-sosial'
        )

    def test_kesetiausahaan_is_perniagaan(self):
        """'Sains Kesetiausahaan' contains 'sains' but is secretarial/business."""
        self.assertEqual(
            classify_course('', 'Sains Kesetiausahaan', 'Diploma Sains Kesetiausahaan'),
            'perniagaan'
        )


class ClassifyStpmCourseTest(TestCase):
    """Test the STPM deterministic classification function."""

    # ── SPM-matching categories (delegated) ──

    def test_stpm_pendidikan(self):
        self.assertEqual(
            classify_stpm_course('Pendidikan', 'Pendidikan', 'Sarjana Muda Pendidikan'),
            'pendidikan'
        )

    def test_stpm_perniagaan_perdagangan(self):
        self.assertEqual(
            classify_stpm_course('Perniagaan & Perdagangan', 'Perniagaan & Perdagangan', 'Sarjana Muda Perniagaan'),
            'perniagaan'
        )

    def test_stpm_perniagaan_perakaunan(self):
        self.assertEqual(
            classify_stpm_course('Perniagaan & Perdagangan', 'Perniagaan & Perdagangan', 'Sarjana Muda Perakaunan'),
            'perakaunan'
        )

    def test_stpm_komputer_it_multimedia(self):
        self.assertEqual(
            classify_stpm_course('Komputer, IT & Multimedia', 'Komputer, IT & Multimedia', 'Sarjana Muda Sains Komputer'),
            'it-perisian'
        )

    def test_stpm_komputer_it_multimedia_rangkaian(self):
        self.assertEqual(
            classify_stpm_course('Komputer, IT & Multimedia', 'Komputer, IT & Multimedia',
                                 'Sarjana Muda Sains Komputer (Rangkaian Komputer)'),
            'it-rangkaian'
        )

    def test_stpm_komputer_it_multimedia_animasi(self):
        self.assertEqual(
            classify_stpm_course('Komputer, IT & Multimedia', 'Komputer, IT & Multimedia',
                                 'Sarjana Muda Reka Bentuk (Animasi)'),
            'multimedia'
        )

    def test_stpm_elektrik_elektronik(self):
        self.assertEqual(
            classify_stpm_course('Elektrik & Elektronik', 'Elektrik & Elektronik', 'Sarjana Muda Kejuruteraan Elektrik'),
            'elektrik'
        )

    def test_stpm_mekanikal_automotif(self):
        self.assertEqual(
            classify_stpm_course('Mekanikal & Automotif', 'Mekanikal & Automotif', 'Sarjana Muda Kejuruteraan Mekanikal'),
            'mekanikal'
        )

    def test_stpm_pertanian_bio_industri(self):
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri', 'Sarjana Muda Sains Pertanian'),
            'pertanian'
        )

    def test_stpm_sivil_senibina(self):
        """Sivil default — course name has no architecture keywords."""
        self.assertEqual(
            classify_stpm_course('Sivil, Seni Bina & Pembinaan', 'Sivil, Seni Bina & Pembinaan', 'Sarjana Muda Kejuruteraan Sivil'),
            'sivil'
        )

    def test_stpm_sivil_senibina_architecture(self):
        """Seni Bina in course name → senibina."""
        self.assertEqual(
            classify_stpm_course('Sivil, Seni Bina & Pembinaan', 'Sivil, Seni Bina & Pembinaan', 'Sarjana Muda Seni Bina'),
            'senibina'
        )

    def test_stpm_aero_marin_minyak_gas(self):
        self.assertEqual(
            classify_stpm_course('Aero, Marin, Minyak & Gas', 'Aero, Marin, Minyak & Gas', 'Sarjana Muda Kejuruteraan Aeroangkasa'),
            'aero'
        )

    def test_stpm_aero_marin_marin(self):
        self.assertEqual(
            classify_stpm_course('Aero, Marin, Minyak & Gas', 'Aero, Marin, Minyak & Gas', 'Sarjana Muda Kejuruteraan Marin'),
            'marin'
        )

    def test_stpm_hospitaliti_kulinari(self):
        self.assertEqual(
            classify_stpm_course('Hospitaliti, Kulinari & Pelancongan', 'Hospitaliti, Kulinari & Pelancongan', 'Sarjana Muda Pengurusan Hotel'),
            'hospitaliti'
        )

    def test_stpm_hospitaliti_kulinari_food(self):
        self.assertEqual(
            classify_stpm_course('Hospitaliti, Kulinari & Pelancongan', 'Hospitaliti, Kulinari & Pelancongan', 'Sarjana Muda Seni Kulinari'),
            'kulinari'
        )

    def test_stpm_seni_reka_kreatif(self):
        self.assertEqual(
            classify_stpm_course('Seni Reka & Kreatif', 'Seni Reka & Kreatif', 'Sarjana Muda Seni Reka Grafik'),
            'senireka'
        )

    # ── STPM-specific categories ──

    def test_stpm_sains_sosial(self):
        self.assertEqual(
            classify_stpm_course('Sains Sosial', 'Sains Sosial', 'Sarjana Muda Sains Sosial'),
            'sains-sosial'
        )

    def test_stpm_kejuruteraan_kimia(self):
        self.assertEqual(
            classify_stpm_course('Kejuruteraan Kimia', 'Kejuruteraan Kimia', 'Sarjana Muda Kejuruteraan Kimia'),
            'kimia-proses'
        )

    def test_stpm_kimia(self):
        self.assertEqual(
            classify_stpm_course('Kimia', 'Kimia', 'Sarjana Muda Kimia'),
            'kimia-proses'
        )

    def test_stpm_kimia_forensik(self):
        self.assertEqual(
            classify_stpm_course('Kimia Forensik', 'Kimia', 'Sarjana Muda Kimia Forensik'),
            'kimia-proses'
        )

    def test_stpm_matematik(self):
        self.assertEqual(
            classify_stpm_course('Matematik', 'Matematik', 'Sarjana Muda Matematik'),
            'sains-fizikal'
        )

    def test_stpm_matematik_kewangan(self):
        self.assertEqual(
            classify_stpm_course('Matematik Kewangan', 'Matematik', 'Sarjana Muda Matematik Kewangan'),
            'perakaunan'
        )

    def test_stpm_fizik(self):
        self.assertEqual(
            classify_stpm_course('Fizik', 'Fizik', 'Sarjana Muda Fizik'),
            'sains-fizikal'
        )

    def test_stpm_fizik_perubatan(self):
        self.assertEqual(
            classify_stpm_course('Fizik Perubatan', 'Sains Perubatan', 'Sarjana Muda Fizik Perubatan'),
            'perubatan'
        )

    def test_stpm_perubatan(self):
        self.assertEqual(
            classify_stpm_course('Perubatan', 'Perubatan', 'Sarjana Muda Perubatan'),
            'perubatan'
        )

    def test_stpm_kejururawatan(self):
        self.assertEqual(
            classify_stpm_course('Kejururawatan', 'Kejururawatan', 'Sarjana Muda Sains Kejururawatan'),
            'kejururawatan'
        )

    def test_stpm_farmasi(self):
        self.assertEqual(
            classify_stpm_course('Farmasi', 'Farmasi', 'Sarjana Muda Farmasi'),
            'farmasi'
        )

    def test_stpm_undang_undang(self):
        self.assertEqual(
            classify_stpm_course('Undang-Undang', 'Undang-Undang', 'Sarjana Muda Undang-Undang'),
            'undang-undang'
        )

    def test_stpm_pengajian_islam(self):
        self.assertEqual(
            classify_stpm_course('Pengajian Islam', 'Pengajian Islam', 'Sarjana Muda Pengajian Islam'),
            'pengajian-islam'
        )

    def test_stpm_pengajian_agama(self):
        self.assertEqual(
            classify_stpm_course('Pengajian Agama', 'Pengajian Agama', 'Sarjana Muda Pengajian Agama'),
            'pengajian-islam'
        )

    def test_stpm_bahasa_linguistik(self):
        self.assertEqual(
            classify_stpm_course('Bahasa & Linguistik', 'Bahasa', 'Sarjana Muda Linguistik'),
            'bahasa'
        )

    def test_stpm_ekonomi(self):
        self.assertEqual(
            classify_stpm_course('Ekonomi', 'Ekonomi', 'Sarjana Muda Ekonomi'),
            'perniagaan'
        )

    def test_stpm_kewangan(self):
        self.assertEqual(
            classify_stpm_course('Kewangan', 'Kewangan', 'Sarjana Muda Kewangan'),
            'perakaunan'
        )

    def test_stpm_perakaunan(self):
        self.assertEqual(
            classify_stpm_course('Perakaunan', 'Perakaunan', 'Sarjana Muda Perakaunan'),
            'perakaunan'
        )

    def test_stpm_sains_alam_sekitar(self):
        self.assertEqual(
            classify_stpm_course('Sains Alam Sekitar', 'Sains Alam Sekitar', 'Sarjana Muda Sains Alam Sekitar'),
            'alam-sekitar'
        )

    def test_stpm_komunikasi_media(self):
        self.assertEqual(
            classify_stpm_course('Komunikasi & Media', 'Komunikasi', 'Sarjana Muda Komunikasi'),
            'komunikasi'
        )

    def test_stpm_sains_kemasyarakatan(self):
        self.assertEqual(
            classify_stpm_course('Sains Kemasyarakatan', 'Sosiologi', 'Sarjana Muda Sains Kemasyarakatan'),
            'sains-sosial'
        )

    def test_stpm_psikologi(self):
        self.assertEqual(
            classify_stpm_course('Psikologi', 'Psikologi', 'Sarjana Muda Psikologi'),
            'sains-sosial'
        )

    def test_stpm_biologi(self):
        self.assertEqual(
            classify_stpm_course('Biologi', 'Biologi', 'Sarjana Muda Biologi'),
            'sains-hayat'
        )

    def test_stpm_bioteknologi(self):
        self.assertEqual(
            classify_stpm_course('Bio-Teknologi', 'Bioteknologi', 'Sarjana Muda Bioteknologi'),
            'sains-hayat'
        )

    def test_stpm_geologi(self):
        self.assertEqual(
            classify_stpm_course('Geologi', 'Geologi', 'Sarjana Muda Geologi'),
            'sains-fizikal'
        )

    def test_stpm_sains_makanan(self):
        self.assertEqual(
            classify_stpm_course('Sains Makanan', 'Sains Makanan', 'Sarjana Muda Sains Makanan'),
            'kulinari'
        )

    def test_stpm_teknologi_maritim(self):
        self.assertEqual(
            classify_stpm_course('Teknologi Maritim', 'Teknologi Maritim', 'Sarjana Muda Teknologi Maritim'),
            'marin'
        )

    def test_stpm_sains_sukan(self):
        self.assertEqual(
            classify_stpm_course('Sains Sukan', 'Sains Sukan', 'Sarjana Muda Sains Sukan'),
            'sains-sosial'
        )

    def test_stpm_sains_data(self):
        self.assertEqual(
            classify_stpm_course('Sains Data', 'Sains Data', 'Sarjana Muda Sains Data'),
            'sains-data'
        )

    def test_stpm_veterinar(self):
        self.assertEqual(
            classify_stpm_course('Veterinar', 'Veterinar', 'Doktor Perubatan Veterinar'),
            'perubatan'
        )

    def test_stpm_tekstil_fesyen(self):
        self.assertEqual(
            classify_stpm_course('Tekstil & Fesyen', 'Seni Reka', 'Sarjana Muda Seni Reka Tekstil'),
            'senireka'
        )

    def test_stpm_seni_persembahan(self):
        self.assertEqual(
            classify_stpm_course('Seni Persembahan', 'Muzik', 'Sarjana Muda Muzik'),
            'multimedia'
        )

    def test_stpm_lain_lain_catch_all(self):
        self.assertEqual(
            classify_stpm_course('Lain-lain', 'Lain-lain', 'Sarjana Muda Umum'),
            'umum'
        )

    def test_stpm_lain_lain_kejururawatan(self):
        """Lain-lain (Kejururawatan) → kejururawatan via name override."""
        self.assertEqual(
            classify_stpm_course('Lain-lain (Kejururawatan)', 'Kejururawatan', 'Sarjana Muda Kejururawatan'),
            'kejururawatan'
        )

    def test_stpm_lain_lain_kimia_gunaan(self):
        """Lain-lain (Kimia Gunaan) → kimia-proses via keyword matching."""
        self.assertEqual(
            classify_stpm_course('Lain-lain (Kimia Gunaan)', 'Kimia', 'Sarjana Muda Kimia Gunaan'),
            'kimia-proses'
        )

    def test_stpm_kejuruteraan_bahan(self):
        self.assertEqual(
            classify_stpm_course('Kejuruteraan Bahan', 'Kejuruteraan', 'Sarjana Muda Kejuruteraan Bahan'),
            'mekanikal'
        )

    def test_stpm_teknologi_tenaga(self):
        self.assertEqual(
            classify_stpm_course('Teknologi Tenaga', 'Kejuruteraan', 'Sarjana Muda Teknologi Tenaga'),
            'elektrik'
        )

    def test_stpm_minyak_gas(self):
        self.assertEqual(
            classify_stpm_course('Minyak & Gas', 'Kejuruteraan', 'Sarjana Muda Teknologi Minyak & Gas'),
            'minyak-gas'
        )

    def test_stpm_landskap(self):
        self.assertEqual(
            classify_stpm_course('Landskap', 'Seni Bina Landskap', 'Sarjana Muda Seni Bina Landskap'),
            'senibina'
        )

    def test_stpm_ukur_bahan(self):
        self.assertEqual(
            classify_stpm_course('Ukur Bahan', 'Ukur Bahan', 'Sarjana Muda Ukur Bahan'),
            'sivil'
        )

    def test_stpm_keusahawanan(self):
        self.assertEqual(
            classify_stpm_course('Keusahawanan Kesejahteraan', 'Keusahawanan', 'Sarjana Muda Keusahawanan'),
            'perniagaan'
        )

    def test_stpm_undang_undang_islam(self):
        self.assertEqual(
            classify_stpm_course('Undang-Undang Islam', 'Syariah', 'Sarjana Muda Syariah'),
            'pengajian-islam'
        )

    def test_stpm_sains_bahan(self):
        self.assertEqual(
            classify_stpm_course('Sains Bahan', 'Sains Bahan', 'Sarjana Muda Sains Bahan'),
            'sains-fizikal'
        )


    # ── Audit-specific tests ──

    def test_stpm_pergigian(self):
        self.assertEqual(
            classify_stpm_course('Pergigian', 'Pergigian', 'Sarjana Muda Pergigian'),
            'pergigian'
        )

    def test_stpm_allied_health_fisioterapi(self):
        self.assertEqual(
            classify_stpm_course('Fisioterapi', 'Fisioterapi', 'Sarjana Muda Fisioterapi'),
            'kejururawatan'
        )

    def test_stpm_nutrition_not_kejururawatan(self):
        """Nutrition → kulinari, NOT kejururawatan."""
        self.assertEqual(
            classify_stpm_course('Pemakanan', 'Sains Kesihatan', 'Sarjana Muda Sains Pemakanan'),
            'kulinari'
        )

    def test_stpm_statistik_sains_data(self):
        self.assertEqual(
            classify_stpm_course('Statistik', 'Statistik', 'Sarjana Muda Statistik'),
            'sains-data'
        )

    def test_stpm_pendidikan_fizik_stays(self):
        """Education degrees stay as pendidikan regardless of subject."""
        self.assertEqual(
            classify_stpm_course('Pendidikan', 'Pendidikan', 'Sarjana Muda Pendidikan (Fizik)'),
            'pendidikan'
        )

    def test_stpm_pertanian_food_science_kulinari(self):
        """Food science under pertanian → kulinari."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Sarjana Muda Sains Makanan'),
            'kulinari'
        )

    def test_stpm_pertanian_biotech_sains_hayat(self):
        """Pure biotech under pertanian → sains-hayat."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Sarjana Muda Bioteknologi'),
            'sains-hayat'
        )

    def test_stpm_pertanian_agro_stays(self):
        """Agricultural biotech stays as pertanian."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Sarjana Muda Bioteknologi Pertanian'),
            'pertanian'
        )

    def test_stpm_komunikasi_perhubungan_awam(self):
        """Perhubungan awam → komunikasi via name override."""
        self.assertEqual(
            classify_stpm_course('Sains Sosial', 'Sains Sosial',
                                 'Sarjana Muda Perhubungan Awam'),
            'komunikasi'
        )

    def test_stpm_kejuruteraan_kimia_override(self):
        """Kejuruteraan Kimia under wrong category → kimia-proses."""
        self.assertEqual(
            classify_stpm_course('Aero, Marin, Minyak & Gas', 'Aero, Marin, Minyak & Gas',
                                 'Sarjana Muda Kejuruteraan Kimia'),
            'kimia-proses'
        )

    def test_stpm_veterinar_override(self):
        """Veterinar under agriculture category → perubatan via name."""
        self.assertEqual(
            classify_stpm_course('Pertanian & Bio-Industri', 'Pertanian & Bio-Industri',
                                 'Doktor Perubatan Veterinar'),
            'perubatan'
        )

    def test_stpm_biodiversiti_alam_sekitar(self):
        """Biodiversiti → alam-sekitar."""
        self.assertEqual(
            classify_stpm_course('Biodiversiti', 'Biodiversiti', 'Sarjana Muda Biodiversiti'),
            'alam-sekitar'
        )

    def test_spm_ua_muzik_senireka(self):
        """UA Diploma Muzik → senireka."""
        self.assertEqual(
            classify_course('Perniagaan & Perdagangan', 'Umum', 'Diploma Muzik'),
            'senireka'
        )

    def test_spm_ua_pendidikan_kanak(self):
        """UA Diploma Pendidikan Awal Kanak-Kanak → pendidikan."""
        self.assertEqual(
            classify_course('Perniagaan & Perdagangan', 'Umum', 'Diploma Pendidikan Awal Kanak-Kanak'),
            'pendidikan'
        )

    def test_spm_ua_bahasa_etnik(self):
        """UA Diploma Bahasa Etnik → bahasa."""
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Bahasa', 'Diploma Bahasa Etnik Baru'),
            'bahasa'
        )

    def test_spm_ua_turath_islami(self):
        """UA Diploma Pengajian Turath Islami → pengajian-islam."""
        self.assertEqual(
            classify_course('Seni Reka & Kreatif', 'Pengajian Islam', 'Diploma Pengajian Turath Islami'),
            'pengajian-islam'
        )

    def test_spm_ua_sains_sukan(self):
        """UA Diploma Sains Sukan → sains-sosial."""
        self.assertEqual(
            classify_course('Pertanian & Bio-Industri', 'Sains', 'Diploma Sains Sukan Dan Kejurulatihan'),
            'sains-sosial'
        )

    def test_spm_ua_diploma_sains(self):
        """UA Diploma Sains → sains-hayat."""
        self.assertEqual(
            classify_course('Pertanian & Bio-Industri', 'Sains', 'Diploma Sains'),
            'sains-hayat'
        )

    def test_spm_ua_sains_matematik(self):
        """UA Diploma Sains (Matematik) → sains-fizikal."""
        self.assertEqual(
            classify_course('Pertanian & Bio-Industri', 'Sains', 'Diploma Sains (Matematik)'),
            'sains-fizikal'
        )


class FieldListAPITest(TestCase):
    """Test the GET /api/v1/fields/ endpoint."""

    def test_fields_endpoint_returns_200(self):
        from django.test import Client
        client = Client()
        response = client.get('/api/v1/fields/')
        self.assertEqual(response.status_code, 200)

    def test_fields_endpoint_returns_groups(self):
        from django.test import Client
        client = Client()
        response = client.get('/api/v1/fields/')
        data = response.json()
        self.assertIn('groups', data)
        # 10 parent groups
        self.assertEqual(len(data['groups']), 10)

    def test_fields_endpoint_groups_have_children(self):
        from django.test import Client
        client = Client()
        response = client.get('/api/v1/fields/')
        data = response.json()
        # Each group should have children
        for group in data['groups']:
            self.assertIn('children', group)
            self.assertIn('key', group)
            self.assertIn('name_en', group)
            self.assertIn('name_ms', group)
            self.assertIn('name_ta', group)

    def test_fields_endpoint_total_children(self):
        from django.test import Client
        client = Client()
        response = client.get('/api/v1/fields/')
        data = response.json()
        total_children = sum(len(g['children']) for g in data['groups'])
        self.assertEqual(total_children, 37)
