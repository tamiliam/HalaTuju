"""Project-wide pytest fixtures.

Test isolation for rate-limiting: the global anon throttle (added 2026-06)
keeps a sliding-window count in the cache. Without resetting it between tests,
the many anonymous API calls the suite makes — all from 127.0.0.1, one bucket —
could accumulate past the limit and cause spurious 429s in unrelated tests.
Clearing the cache before each test keeps throttle state per-test.
"""
import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _reset_cache_between_tests():
    cache.clear()
    yield


#: TD-403 (owner ruling 2026-10-26): an STR counts only if it is from THIS calendar year, read off
#: the clock (`income_engine.str_route.str_this_year`). The suite's STR fixtures are dated 2026, so
#: the clock is pinned to that year for every test — otherwise the whole suite (and the Cloud Build
#: deploy gate) would turn red at Malaysian midnight on 1 January 2027. A test that exercises the
#: real clock asks for `real_str_clock` and freezes `timezone.now` itself.
STR_TEST_YEAR = 2026


@pytest.fixture
def real_str_clock():
    """Opt out of the STR-year pin: `str_this_year` reads the (frozen) clock for real."""
    yield


@pytest.fixture(autouse=True)
def _str_year_pinned(request, monkeypatch):
    if 'real_str_clock' not in request.fixturenames:
        from apps.scholarship.income_engine import str_route
        monkeypatch.setattr(str_route, 'str_this_year', lambda: STR_TEST_YEAR)
    yield
