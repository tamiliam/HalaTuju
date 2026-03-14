import pytest
from apps.courses.management.commands.populate_stpm_urls import build_mohe_url


class TestBuildMoheUrl:
    def test_science_url(self):
        url = build_mohe_url('UP6314001', 'science')
        assert url == 'https://online.mohe.gov.my/epanduan/carianNamaProgram/UP/UP6314001/S/stpm'

    def test_arts_url(self):
        url = build_mohe_url('UM1234001', 'arts')
        assert url == 'https://online.mohe.gov.my/epanduan/carianNamaProgram/UM/UM1234001/A/stpm'

    def test_both_defaults_to_science(self):
        url = build_mohe_url('UK5551001', 'both')
        assert url == 'https://online.mohe.gov.my/epanduan/carianNamaProgram/UK/UK5551001/S/stpm'
