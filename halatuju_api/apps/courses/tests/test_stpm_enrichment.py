"""
Tests for STPM quiz data enrichment (Sprint 2).

Covers:
- RIASEC mapping completeness and correctness
- Difficulty level mapping
- Efficacy domain mapping
- FieldTaxonomy riasec_primary
- Management command (enrich_stpm_riasec)
"""
import pytest
from io import StringIO

from django.core.management import call_command

from apps.courses.management.commands.enrich_stpm_riasec import (
    FIELD_KEY_TO_RIASEC,
    FIELD_KEY_TO_DIFFICULTY,
    FIELD_KEY_TO_EFFICACY,
    FIELD_TAXONOMY_RIASEC,
)
from apps.courses.models import FieldTaxonomy, StpmCourse


# ── Mapping completeness ─────────────────────────────────────────────

class TestRiasecMapping:
    """FIELD_KEY_TO_RIASEC covers all expected field_keys."""

    VALID_RIASEC = {'R', 'I', 'A', 'S', 'E', 'C'}

    def test_all_values_are_valid_riasec(self):
        for key, val in FIELD_KEY_TO_RIASEC.items():
            assert val in self.VALID_RIASEC, f"{key} has invalid RIASEC '{val}'"

    def test_all_six_types_represented(self):
        types_used = set(FIELD_KEY_TO_RIASEC.values())
        assert types_used == self.VALID_RIASEC

    def test_design_doc_r_keys(self):
        """Section 10: R = mekanikal, automotif, mekatronik, elektrik, sivil, etc."""
        r_keys = [k for k, v in FIELD_KEY_TO_RIASEC.items() if v == 'R']
        assert 'mekanikal' in r_keys
        assert 'elektrik' in r_keys
        assert 'sivil' in r_keys
        assert 'pertanian' in r_keys

    def test_design_doc_i_keys(self):
        """Section 10: I = perubatan, farmasi, sains-hayat, sains-tulen, etc."""
        i_keys = [k for k, v in FIELD_KEY_TO_RIASEC.items() if v == 'I']
        assert 'perubatan' in i_keys
        assert 'farmasi' in i_keys
        assert 'it-perisian' in i_keys

    def test_design_doc_e_keys(self):
        """Section 10: E = perniagaan, pengurusan, pemasaran, undang-undang."""
        e_keys = [k for k, v in FIELD_KEY_TO_RIASEC.items() if v == 'E']
        assert 'perniagaan' in e_keys
        assert 'undang-undang' in e_keys

    def test_design_doc_c_keys(self):
        """Section 10: C = perakaunan, kewangan, pentadbiran, sains-aktuari."""
        c_keys = [k for k, v in FIELD_KEY_TO_RIASEC.items() if v == 'C']
        assert 'perakaunan' in c_keys
        assert 'sains-aktuari' in c_keys

    def test_design_doc_s_keys(self):
        """Section 10: S = pendidikan, kaunseling, sains-sukan, pengajian-islam."""
        s_keys = [k for k, v in FIELD_KEY_TO_RIASEC.items() if v == 'S']
        assert 'pendidikan' in s_keys
        assert 'kaunseling' in s_keys

    def test_design_doc_a_keys(self):
        """Section 10: A = senireka, multimedia, fesyen."""
        a_keys = [k for k, v in FIELD_KEY_TO_RIASEC.items() if v == 'A']
        assert 'senireka' in a_keys
        assert 'multimedia' in a_keys

    def test_umum_not_mapped(self):
        """umum is the catch-all — should NOT have a RIASEC mapping."""
        assert 'umum' not in FIELD_KEY_TO_RIASEC


class TestDifficultyMapping:
    """FIELD_KEY_TO_DIFFICULTY covers all non-catch-all field_keys."""

    VALID_LEVELS = {'low', 'moderate', 'high'}

    def test_all_values_are_valid(self):
        for key, val in FIELD_KEY_TO_DIFFICULTY.items():
            assert val in self.VALID_LEVELS, f"{key} has invalid difficulty '{val}'"

    def test_all_three_levels_represented(self):
        levels_used = set(FIELD_KEY_TO_DIFFICULTY.values())
        assert levels_used == self.VALID_LEVELS

    def test_medicine_is_high(self):
        assert FIELD_KEY_TO_DIFFICULTY['perubatan'] == 'high'

    def test_law_is_high(self):
        assert FIELD_KEY_TO_DIFFICULTY['undang-undang'] == 'high'

    def test_business_is_low(self):
        assert FIELD_KEY_TO_DIFFICULTY['perniagaan'] == 'low'

    def test_accounting_is_moderate(self):
        assert FIELD_KEY_TO_DIFFICULTY['perakaunan'] == 'moderate'


class TestEfficacyMapping:
    """FIELD_KEY_TO_EFFICACY covers all non-catch-all field_keys."""

    VALID_DOMAINS = {'quantitative', 'scientific', 'verbal', 'practical'}

    def test_all_values_are_valid(self):
        for key, val in FIELD_KEY_TO_EFFICACY.items():
            assert val in self.VALID_DOMAINS, f"{key} has invalid efficacy '{val}'"

    def test_all_four_domains_represented(self):
        domains_used = set(FIELD_KEY_TO_EFFICACY.values())
        assert domains_used == self.VALID_DOMAINS

    def test_engineering_is_quantitative(self):
        assert FIELD_KEY_TO_EFFICACY['mekanikal'] == 'quantitative'

    def test_medicine_is_scientific(self):
        assert FIELD_KEY_TO_EFFICACY['perubatan'] == 'scientific'

    def test_law_is_verbal(self):
        assert FIELD_KEY_TO_EFFICACY['undang-undang'] == 'verbal'

    def test_design_is_practical(self):
        assert FIELD_KEY_TO_EFFICACY['senireka'] == 'practical'


class TestMappingConsistency:
    """All three mappings should cover the same set of field_keys."""

    def test_riasec_and_difficulty_same_keys(self):
        riasec_keys = set(FIELD_KEY_TO_RIASEC.keys())
        diff_keys = set(FIELD_KEY_TO_DIFFICULTY.keys())
        missing_in_difficulty = riasec_keys - diff_keys
        missing_in_riasec = diff_keys - riasec_keys
        assert not missing_in_difficulty, f"In RIASEC but not difficulty: {missing_in_difficulty}"
        assert not missing_in_riasec, f"In difficulty but not RIASEC: {missing_in_riasec}"

    def test_riasec_and_efficacy_same_keys(self):
        riasec_keys = set(FIELD_KEY_TO_RIASEC.keys())
        eff_keys = set(FIELD_KEY_TO_EFFICACY.keys())
        missing_in_efficacy = riasec_keys - eff_keys
        missing_in_riasec = eff_keys - riasec_keys
        assert not missing_in_efficacy, f"In RIASEC but not efficacy: {missing_in_efficacy}"
        assert not missing_in_riasec, f"In efficacy but not RIASEC: {missing_in_riasec}"

    def test_taxonomy_riasec_is_same_as_course_riasec(self):
        """FIELD_TAXONOMY_RIASEC should be the same dict as FIELD_KEY_TO_RIASEC."""
        assert FIELD_TAXONOMY_RIASEC is FIELD_KEY_TO_RIASEC


# ── Database tests ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestFieldTaxonomyRiasec:
    """FieldTaxonomy.riasec_primary field works correctly."""

    def test_riasec_primary_default_is_empty(self):
        tax = FieldTaxonomy.objects.create(
            key='test-field',
            name_en='Test', name_ms='Ujian', name_ta='Test',
            image_slug='test',
        )
        assert tax.riasec_primary == ''

    def test_riasec_primary_accepts_valid_code(self):
        tax = FieldTaxonomy.objects.create(
            key='test-field-r',
            name_en='Test R', name_ms='Ujian R', name_ta='Test R',
            image_slug='test-r',
            riasec_primary='R',
        )
        tax.refresh_from_db()
        assert tax.riasec_primary == 'R'

    def test_leaf_nodes_have_riasec_after_enrichment(self):
        """After running enrich command, leaf taxonomy entries should have riasec_primary."""
        parent, _ = FieldTaxonomy.objects.get_or_create(
            key='test-eng-parent',
            defaults={'name_en': 'Engineering', 'name_ms': 'Kejuruteraan',
                      'name_ta': 'Eng', 'image_slug': 'engineering'},
        )
        leaf, _ = FieldTaxonomy.objects.get_or_create(
            key='mekanikal',
            defaults={'name_en': 'Mechanical', 'name_ms': 'Mekanikal',
                      'name_ta': 'Mech', 'image_slug': 'mekanikal'},
        )
        if not leaf.parent_key:
            leaf.parent_key = parent
            leaf.save(update_fields=['parent_key'])
        # Clear any prior riasec_primary
        leaf.riasec_primary = ''
        leaf.save(update_fields=['riasec_primary'])

        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        leaf.refresh_from_db()
        assert leaf.riasec_primary == 'R'


@pytest.mark.django_db
class TestStpmCourseEnrichmentFields:
    """New fields on StpmCourse work correctly."""

    def _make_taxonomy(self, key='perubatan'):
        tax, _ = FieldTaxonomy.objects.get_or_create(
            key=key,
            defaults={
                'name_en': 'Medicine', 'name_ms': 'Perubatan', 'name_ta': 'Med',
                'image_slug': 'perubatan',
            }
        )
        return tax

    def test_riasec_type_default_empty(self):
        tax = self._make_taxonomy()
        course = StpmCourse.objects.create(
            course_id='TEST001', course_name='Test', university='UM',
            field_key=tax,
        )
        assert course.riasec_type == ''

    def test_riasec_type_set_and_read(self):
        tax = self._make_taxonomy()
        course = StpmCourse.objects.create(
            course_id='TEST002', course_name='Test', university='UM',
            field_key=tax, riasec_type='I',
        )
        course.refresh_from_db()
        assert course.riasec_type == 'I'

    def test_difficulty_level_set_and_read(self):
        tax = self._make_taxonomy()
        course = StpmCourse.objects.create(
            course_id='TEST003', course_name='Test', university='UM',
            field_key=tax, difficulty_level='high',
        )
        course.refresh_from_db()
        assert course.difficulty_level == 'high'

    def test_efficacy_domain_set_and_read(self):
        tax = self._make_taxonomy()
        course = StpmCourse.objects.create(
            course_id='TEST004', course_name='Test', university='UM',
            field_key=tax, efficacy_domain='scientific',
        )
        course.refresh_from_db()
        assert course.efficacy_domain == 'scientific'

    def test_all_three_fields_set_together(self):
        tax = self._make_taxonomy()
        course = StpmCourse.objects.create(
            course_id='TEST005', course_name='Test Medicine', university='UM',
            field_key=tax,
            riasec_type='I', difficulty_level='high', efficacy_domain='scientific',
        )
        course.refresh_from_db()
        assert course.riasec_type == 'I'
        assert course.difficulty_level == 'high'
        assert course.efficacy_domain == 'scientific'


@pytest.mark.django_db
class TestEnrichCommand:
    """Management command enrich_stpm_riasec works correctly."""

    def _setup_course(self, course_id, field_key_str):
        tax, _ = FieldTaxonomy.objects.get_or_create(
            key=field_key_str,
            defaults={
                'name_en': field_key_str, 'name_ms': field_key_str,
                'name_ta': field_key_str, 'image_slug': field_key_str,
            }
        )
        course = StpmCourse.objects.create(
            course_id=course_id, course_name=f'Test {field_key_str}',
            university='UM', field_key=tax,
        )
        return course

    def test_dry_run_does_not_change_data(self):
        course = self._setup_course('DRY001', 'mekanikal')
        out = StringIO()
        call_command('enrich_stpm_riasec', stdout=out)
        course.refresh_from_db()
        assert course.riasec_type == ''  # No change in dry run

    def test_apply_sets_riasec(self):
        course = self._setup_course('APP001', 'mekanikal')
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        course.refresh_from_db()
        assert course.riasec_type == 'R'

    def test_apply_sets_difficulty(self):
        course = self._setup_course('APP002', 'perubatan')
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        course.refresh_from_db()
        assert course.difficulty_level == 'high'

    def test_apply_sets_efficacy(self):
        course = self._setup_course('APP003', 'undang-undang')
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        course.refresh_from_db()
        assert course.efficacy_domain == 'verbal'

    def test_unmapped_field_key_leaves_empty(self):
        course = self._setup_course('UNM001', 'umum')
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        course.refresh_from_db()
        assert course.riasec_type == ''
        assert course.difficulty_level == ''
        assert course.efficacy_domain == ''

    def test_apply_sets_taxonomy_riasec(self):
        tax, _ = FieldTaxonomy.objects.get_or_create(
            key='elektrik',
            defaults={
                'name_en': 'Electrical', 'name_ms': 'Elektrik',
                'name_ta': 'Elect', 'image_slug': 'elektrik',
            }
        )
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        tax.refresh_from_db()
        assert tax.riasec_primary == 'R'

    def test_idempotent(self):
        """Running twice with --apply produces same result."""
        course = self._setup_course('IDP001', 'farmasi')
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        course.refresh_from_db()
        first_riasec = course.riasec_type

        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        course.refresh_from_db()
        assert course.riasec_type == first_riasec

    def test_multiple_courses_same_field(self):
        """Multiple courses with same field_key all get classified."""
        tax, _ = FieldTaxonomy.objects.get_or_create(
            key='sivil',
            defaults={
                'name_en': 'Civil', 'name_ms': 'Sivil',
                'name_ta': 'Civil', 'image_slug': 'sivil',
            }
        )
        c1 = StpmCourse.objects.create(
            course_id='MUL001', course_name='Civil Eng A',
            university='UM', field_key=tax,
        )
        c2 = StpmCourse.objects.create(
            course_id='MUL002', course_name='Civil Eng B',
            university='UTM', field_key=tax,
        )
        out = StringIO()
        call_command('enrich_stpm_riasec', '--apply', stdout=out)
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert c1.riasec_type == 'R'
        assert c2.riasec_type == 'R'
