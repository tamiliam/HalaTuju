"""The suite runs on what production installs (2026-11-21; docs/technical-debt.md, the station
gate suites on pypdf 5.9.0).

The station's system Python carried pypdf 5.9.0 while the production image installs ``requirements.lock``
(pypdf 6.21.4) on Python 3.11, so gate suites passed on a pypdf production never runs. The root
``conftest.py`` calls `enforce` at the start of every pytest session: a session whose pypdf, pypdfium2 or
Python major.minor differs from production stops before any test runs. ``--unpinned-cross-check`` (off
by default) runs anyway with a warning, ONLY to compare behaviour on another version on purpose.

Test-only: this folder never enters the production image (``.dockerignore``), and ``manage.py`` never
imports it.
"""
import re
import sys
from importlib import metadata
from pathlib import Path

#: halatuju_api/, where requirements.lock and the Dockerfile live.
API_DIR = Path(__file__).resolve().parents[3]
#: The packages whose version changes what the document checks read (the PDF text layer and the renderer).
PINNED = ('pypdf', 'pypdfium2')
OPT_OUT = '--unpinned-cross-check'
#: One ``FROM [--flag=x ...] python:X.Y[-tag] [AS name]`` line: FROM/AS in any case, any spaces or tabs, any
#: ``--platform=...`` style flags. Read on LF text (`_lf`), so CRLF and LF files match alike.
_FROM_PYTHON = re.compile(
    r'^[ \t]*FROM[ \t]+(?:--\S+[ \t]+)*python:(\d+\.\d+)\S*(?:[ \t]+AS[ \t]+\S+)?[ \t]*$',
    re.MULTILINE | re.IGNORECASE)


def _lf(text: str) -> str:
    """The text with CRLF (and lone CR) line ends read as LF, so the checks do not depend on the checkout."""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _norm(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def lock_pins(lock_text: str, names=PINNED) -> dict:
    """``{name: version}`` for each of ``names`` pinned ``name==version`` in a requirements lock."""
    wanted, out = {_norm(n): n for n in names}, {}
    for line in _lf(lock_text).split('\n'):
        # ``name==v`` or, with extras, ``name[extra,other]==v``: the extras do not change which package it is
        m = re.match(r'\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*==\s*([^\s;#]+)', line)
        if m and _norm(m.group(1)) in wanted:
            out[wanted[_norm(m.group(1))]] = m.group(2)
    return out


def production_python(dockerfile_text: str) -> str:
    """The major.minor of the Dockerfile's ``FROM python:X.Y...`` line. ValueError unless exactly one: no
    matching stage is a loud failure (a problem line, a stopped session), never a silent pass."""
    found = _FROM_PYTHON.findall(_lf(dockerfile_text))
    if len(found) != 1:
        raise ValueError(f'expected one "FROM python:X.Y" line in the Dockerfile, found {len(found)}')
    return found[0]


def installed_versions(names=PINNED) -> dict:
    out = {}
    for name in names:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def mismatches(lock_text: str, dockerfile_text: str, installed: dict, python: str) -> list:
    """Each way this interpreter differs from production, one plain line each ([] when it matches)."""
    problems, pins = [], lock_pins(lock_text)
    for name in PINNED:
        want, have = pins.get(name), installed.get(name)
        if want is None:
            problems.append(f'{name} is not pinned (name==version) in requirements.lock')
        elif have != want:
            problems.append(f'{name}: installed {have or "nothing"}, requirements.lock pins {want}')
    try:
        want_py = production_python(dockerfile_text)
    except ValueError as e:
        problems.append(f'Python: {e}')
    else:
        if python != want_py:
            problems.append(f'Python: running {python}, production (Dockerfile FROM) is {want_py}')
    return problems


def check(api_dir: Path = API_DIR) -> list:
    """`mismatches` for THIS interpreter against the repo's requirements.lock and Dockerfile."""
    lock = (api_dir / 'requirements.lock').read_text(encoding='utf-8')
    docker = (api_dir / 'Dockerfile').read_text(encoding='utf-8')
    return mismatches(lock, docker, installed_versions(), f'{sys.version_info.major}.{sys.version_info.minor}')


def message(problems: list) -> str:
    return ('This test session does not run on what production installs:\n'
            + ''.join(f'  - {p}\n' for p in problems)
            + 'Fix: run the suite in a venv built from the lock, on the production Python:\n'
              '  py -3.11 -m venv <dir>\n'
              '  <dir>/Scripts/python -m pip install -r requirements.lock -r requirements-dev.txt\n'
              '  <dir>/Scripts/python -m pytest ...\n'
            + f'Only to compare behaviour on another version ON PURPOSE: pytest {OPT_OUT} ... (never a gate run).')


def enforce(config, problems=None) -> None:
    """At session start: raise ``pytest.UsageError`` (the session stops, no test runs) on any mismatch,
    unless ``--unpinned-cross-check`` was given; then only a warning."""
    import pytest
    problems = check() if problems is None else problems
    if not problems:
        return
    if config.getoption(OPT_OUT):
        config.issue_config_time_warning(
            pytest.PytestConfigWarning('UNPINNED CROSS-CHECK, not a gate run. ' + message(problems)), stacklevel=2)
        return
    raise pytest.UsageError(message(problems))
