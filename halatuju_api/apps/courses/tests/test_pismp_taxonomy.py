"""Unit tests for the PISMP taxonomy parser (pure, no DB)."""
from apps.courses.pismp_taxonomy import (
    aliran_of, is_elektif, classify_pismp,
    ALIRAN_SK, ALIRAN_SJKC, ALIRAN_SJKT, ALIRAN_KHAS,
)


class TestAliranOf:
    def test_suffix_is_authoritative(self):
        assert aliran_of('Bahasa Tamil Pendidikan Rendah (SJKT)', '50PD040T00P') == ALIRAN_SJKT
        assert aliran_of('Bahasa Cina Pendidikan Rendah (SJKC)', '50PD030C00P') == ALIRAN_SJKC
        assert aliran_of('Bahasa Melayu Pendidikan Rendah (Khas)', '50PD060M00P') == ALIRAN_KHAS

    def test_no_suffix_defaults_to_sk(self):
        assert aliran_of('Bahasa Melayu Pendidikan Rendah', '50PD010M00P') == ALIRAN_SK

    def test_falls_back_to_id_digit_when_no_suffix(self):
        # No name suffix, but the id 6th char encodes the aliran.
        assert aliran_of('', '50PD040T00P') == ALIRAN_SJKT
        assert aliran_of('', '50PD030C00P') == ALIRAN_SJKC
        assert aliran_of('', '50PD060M00P') == ALIRAN_KHAS
        assert aliran_of('', '50PD050M9MP') == ALIRAN_SK  # digit 5 → SK (elektif)


class TestIsElektif:
    def test_elektif_by_name(self):
        assert is_elektif('Bahasa Melayu Pendidikan Rendah Elektif', '50PD010M9MP') is True

    def test_elektif_by_id_when_name_silent(self):
        # Same name as the major, but the id marks it as the elektif variant.
        assert is_elektif('Pendidikan Seni Visual Pendidikan Rendah', '50PD016V8MP') is True

    def test_major_is_not_elektif(self):
        assert is_elektif('Bahasa Tamil Pendidikan Rendah (SJKT)', '50PD040T00P') is False
        assert is_elektif('Sains Pendidikan Rendah (SJKT)', '50PD041S004') is False


class TestClassifyPismp:
    def test_returns_both_facets(self):
        assert classify_pismp('50PD040T00P', 'Bahasa Tamil Pendidikan Rendah (SJKT)') == {
            'aliran': ALIRAN_SJKT, 'is_elektif': False,
        }
        assert classify_pismp('50PD040M9MP', 'Bahasa Melayu Pendidikan Rendah Elektif (SJKT)') == {
            'aliran': ALIRAN_SJKT, 'is_elektif': True,
        }
