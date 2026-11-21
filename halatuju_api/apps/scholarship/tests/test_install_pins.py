"""The session pin check (`_install_pins`, called from the root conftest): a test session stops at start
unless its pypdf, pypdfium2 and Python major.minor are what production installs."""
from pathlib import Path

import pytest

from apps.scholarship.tests import _install_pins as pins

LOCK = 'pyparsing==3.3.2\npypdf==6.21.4\nPyPDFium2 == 4.30.0  # renderer\npython-bidi==0.6.11\n'
DOCKER = '# api\nFROM python:3.11-slim\nENV PORT=8080\n'
SAME = {'pypdf': '6.21.4', 'pypdfium2': '4.30.0'}


class _Config:
    def __init__(self, opt_out=False):
        self.opt_out, self.warned = opt_out, []

    def getoption(self, name):
        assert name == pins.OPT_OUT
        return self.opt_out

    def issue_config_time_warning(self, warning, stacklevel):
        self.warned.append(str(warning))


def test_the_lock_pins_are_read_by_name_whatever_the_case_or_spacing():
    assert pins.lock_pins(LOCK) == SAME


def test_the_production_python_is_the_dockerfile_from_line():
    assert pins.production_python(DOCKER) == '3.11'
    for bad in ('FROM node:20\n', DOCKER + 'FROM python:3.12-slim\n', 'FROM python:latest\n'):
        with pytest.raises(ValueError):
            pins.production_python(bad)


def test_the_real_lock_and_dockerfile_are_readable():
    lock = (pins.API_DIR / 'requirements.lock').read_text(encoding='utf-8')
    docker = (pins.API_DIR / 'Dockerfile').read_text(encoding='utf-8')
    assert set(pins.lock_pins(lock)) == set(pins.PINNED)
    assert pins.production_python(docker) == '3.11'
    assert Path(pins.__file__).resolve().parents[3] == pins.API_DIR


def test_a_match_is_no_problem():
    assert pins.mismatches(LOCK, DOCKER, SAME, '3.11') == []


def test_each_mismatch_names_both_sides():
    problems = pins.mismatches(LOCK, DOCKER, {'pypdf': '5.9.0', 'pypdfium2': None}, '3.13')
    assert problems == ['pypdf: installed 5.9.0, requirements.lock pins 6.21.4',
                        'pypdfium2: installed nothing, requirements.lock pins 4.30.0',
                        'Python: running 3.13, production (Dockerfile FROM) is 3.11']


def test_a_package_the_lock_does_not_pin_or_an_unclear_dockerfile_is_a_problem():
    problems = pins.mismatches('pypdf==6.21.4\n', 'FROM python:latest\n', SAME, '3.11')
    assert problems[0] == 'pypdfium2 is not pinned (name==version) in requirements.lock'
    assert problems[1].startswith('Python: expected one "FROM python:X.Y" line')


def test_a_mismatch_stops_the_session_with_the_fix():
    with pytest.raises(pytest.UsageError) as stop:
        pins.enforce(_Config(), ['pypdf: installed 5.9.0, requirements.lock pins 6.21.4'])
    text = str(stop.value)
    assert 'installed 5.9.0, requirements.lock pins 6.21.4' in text
    assert 'pip install -r requirements.lock -r requirements-dev.txt' in text and 'py -3.11 -m venv' in text
    assert pins.OPT_OUT in text


def test_the_cross_check_option_only_warns():
    config = _Config(opt_out=True)
    pins.enforce(config, ['Python: running 3.13, production (Dockerfile FROM) is 3.11'])
    assert len(config.warned) == 1 and 'UNPINNED CROSS-CHECK, not a gate run' in config.warned[0]


def test_no_mismatch_neither_stops_nor_warns():
    config = _Config()
    pins.enforce(config, [])
    assert config.warned == []


def test_a_session_off_the_pins_got_here_only_by_asking_for_the_cross_check(pytestconfig):
    if pins.check():
        assert pytestconfig.getoption(pins.OPT_OUT) is True
