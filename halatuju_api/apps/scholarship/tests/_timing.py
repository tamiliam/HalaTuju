"""TD-693: a test pins a guard by the WORK it counts, never by how fast this machine is.

Cloud Build failed twice on wall-clock asserts (a fast runner, then a slow one: 2.5 s against a 1 s limit, 19 s
against 8 s) while every guard worked. So a guard is pinned by what it counts (parses, children spawned, function
calls, budgets), and time is only `WALL_BACKSTOP_S`: a limit no machine speed can fail, which still catches a
hang. `test_no_tight_wall_clock` refuses any other elapsed-time limit in the api's tests.
"""
import sys
import time
from contextlib import contextmanager

#: The ONE wall-clock limit an api test may assert on elapsed time (seconds). At least 10x every limit it
#: replaced and at least 60 s: the slow runner took 19 s on a check the dev machine does in 3 s.
WALL_BACKSTOP_S = 60.0


@contextmanager
def wall_backstop(test):
    """Fail ``test`` only when the block runs past `WALL_BACKSTOP_S` (a hang, not a slow machine)."""
    t0 = time.perf_counter()
    yield
    test.assertLess(time.perf_counter() - t0, WALL_BACKSTOP_S)


def calls(fn, *args, **kwargs):
    """(``fn(*args, **kwargs)``, the Python and C function calls made while it ran, in this thread). The same
    input gives the same count on any machine: work, not time."""
    count = [0]

    def profile(_frame, event, _arg):
        if event in ('call', 'c_call'):
            count[0] += 1
    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        out = fn(*args, **kwargs)
    finally:
        sys.setprofile(previous)
    return out, count[0]


def assert_linear(test, fn, make, n, msg=''):
    """``fn(make(2n))`` makes at most 2.5x the calls of ``fn(make(n))``: linear (about 2x), never quadratic
    (about 4x). Each run is also under `WALL_BACKSTOP_S`."""
    with wall_backstop(test):
        _out, small = calls(fn, make(n))
    with wall_backstop(test):
        _out, big = calls(fn, make(2 * n))
    test.assertLessEqual(big, 2.5 * small, f'{msg}: {small} calls at size {n}, {big} at size {2 * n}')
    return small, big
