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
