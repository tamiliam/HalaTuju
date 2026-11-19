"""Run pdfium on an upload in a child process with a hard wall-clock limit (S-visible fix round 8, 2026-11-19).

Replaces round 6's process-wide pdfium lock. pypdfium2 4.30 is not thread-safe, and under the lock one crafted PDF
that kept pdfium busy (an annotation's appearance stream rendered for 38 s, a 746-byte page of huge text 11 s, 10,500
clip paths 14 s, Type3 glyphs 13.5 s) froze every upload in the gunicorn worker. Modelling pdfium's cost (rounds 5-7)
never ended, so it is no longer the safety line: every pdfium operation on an upload runs in `pdfium_worker`, a fresh
``python -I`` child per call (no shared state, so no lock), killed past its time limit, its address space and CPU time
capped on Linux, at most `MAX_CHILDREN` at once per web process. The round 5-7 whitelists and caps stay as a cheap
pre-filter (a refusal there spawns nothing).

Fix round 9 (availability): each DOCUMENT (keyed by the SHA-256 of its bytes, shared by every step and reader in the
process) has `DOC_BUDGET_S` of child wall time and `DOC_WAIT_S` of waiting for a child slot. Every child's time is
charged; a child's own limit is the budget left (at most `TIMEOUT_S`); once a document has spent its budget every
further question about it gets the safe answer at once. So a file tuned to finish just under the limit costs the
budget once, not once per step, and a hostile upload holds a slot for at most `DOC_BUDGET_S` in all.

Fix round 10: a child's limit is RESERVED from the budget before it starts and the unused part refunded after, so
concurrent questions about the same bytes cannot each spend `TIMEOUT_S` (a question that finds the budget held by
a running child waits for it, charged to the wait budget). Only a child killed at the FULL `TIMEOUT_S` marks the
document for good (`_SPENT`); one killed at a limit the budget had shrunk only spends the budget, which restarts.

Timeout, crash, non-zero exit, out of memory, output past its size cap or that does not parse, no slot within the
wait budget: `ask` returns None and the caller takes its safe answer — the visibility check: hidden (the Vision
route); a render: None / [] (the "cannot read" path); the page count: 0; the SPM word boxes: none (the Gemini read).
Never the hidden text. Only a failure that the same bytes would repeat is remembered: a spawn error is retried once
and, like a slot wait that ran out, a failure after the child started that is not the child's (a thread that would
not start), or a child killed by a signal we did not send (checked FIRST, whatever it wrote), never remembered.
"""
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from typing import Optional

from . import pdfium_worker

logger = logging.getLogger(__name__)

#: Wall-clock seconds one child may run (start-up included), and never past the document's budget left. Real corpus
#: (533 PDFs, 2026-11-19): the slowest child call took 1.53 s on the idle dev machine (median 0.34 s).
TIMEOUT_S = 20.0
#: Child wall time one document may spend in all, over every step and reader in this process (round 9). Real corpus
#: (533 PDFs, EVERY step any reader takes, so more than one upload's path): the slowest document spent 4.0 s in all
#: on a quiet dev machine, 16.1 s with it saturated (p95 6.7 s, median 1.9 s). A hostile upload holds a child slot
#: for at most this long, so it is also what 4 hostile uploads cost a genuine one queued behind them (2 slots:
#: about 2 x this); 20 s keeps that under a minute.
DOC_BUDGET_S = 20.0
#: Seconds one document may wait for a child slot in all (round 9). A real child holds a slot 0.15-1.5 s idle, so a
#: genuine upload waits seconds. 4 threads per worker means at most 3 other uploads, each holding slots for at most
#: `DOC_BUDGET_S` in all, 2 at a time: 1.5 x `DOC_BUDGET_S` + margin. Only a sustained flood of new hostile
#: uploads runs a genuine one out of it (then the safe answer: "cannot read").
DOC_WAIT_S = 45.0
#: A document's budgets restart this long after its first child, so a genuine document read again much later (its
#: answers long gone from the memo) is never refused for its history. Only a child killed at the full `TIMEOUT_S`
#: marks the document for good (`_SPENT`, bounded); a kill at a limit the budget had shrunk spends the budget only.
BUDGET_WINDOW_S = 600.0
_BUDGET_SIZE = 256
#: Bytes a child may add to its address space after loading Python, pypdfium2 and Pillow (Linux only). Largest real
#: child peak 176 MB in all (median 66 MB; the loaded child itself 26 MB resident on Windows, allowed 45 MB here, so
#: at most about 150 MB of growth): 256 MiB is about 1.7x that. Measured on Linux with the cap on (round 10, WSL,
#: Python 3.12, the production pins; 533 PDFs, 2,150 children): address space when the cap is set 37.7-44.9 MiB,
#: largest growth past it 136.8 MiB (VmPeak 181.4 MiB, resident peak 163.3 MiB), no MemoryError, every answer the
#: same as with no cap. Instance 2 GiB: 2 web processes (estimated 350 MiB each) + 2 workers x 2 children x
#: (45 + 256 MiB) = about 1.9 GiB (round 8's 640 MiB cap summed to 3.2 GiB).
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024
#: Seconds of CPU past the child's own time limit before the kernel kills it (Linux `RLIMIT_CPU`): an orphan whose
#: parent was killed still dies.
CPU_GRACE_S = 5
#: Children running at once per web process (each gunicorn worker); see `MEMORY_LIMIT_BYTES` for the sum.
MAX_CHILDREN = 2
_SLOTS = threading.BoundedSemaphore(MAX_CHILDREN)
_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdfium_worker.py')
#: The child's output: a JSON header line, then the PNG bytes it names. More PNG bytes than the asked renders could
#: ever make (`max_output_bytes`), or a header past this, is a failed child (the largest real header: the word
#: boxes of a dense page 1, well under 1 MB).
MAX_HEADER_BYTES = 8 << 20

#: One upload is asked about by several readers (the slip gate, the Vision route, the offer reader): the answers
#: of one child call are kept, keyed on the SHA-256 of the bytes and the operation, so a repeated question spawns
#: nothing. Failures the same bytes would repeat are kept too. Small LRU.
_MEMO_SIZE = 16
_MEMO_MAX_BYTES = 48_000_000
_MEMO: 'OrderedDict[tuple, tuple]' = OrderedDict()
_MEMO_LOCK = threading.Lock()
#: Signalled (under `_MEMO_LOCK`) whenever a child's reserved time is settled (round 10).
_SETTLED = threading.Condition(_MEMO_LOCK)
#: digest -> [child seconds spent or reserved, seconds waited, monotonic time of the first charge, children running]
#: (round 9; reservations and the running count round 10).
_BUDGET: 'OrderedDict[bytes, list]' = OrderedDict()
#: Documents whose child ran past the full `TIMEOUT_S`: every later question gets the safe answer at once, for good.
_SPENT: 'OrderedDict[bytes, None]' = OrderedDict()
_SPENT_SIZE = 64


class _TimedOut(Exception):
    pass


class _Transient(Exception):
    """A failure that says nothing about the bytes (no slot, no process, a signal we did not send): not kept."""


def memo_clear() -> None:
    with _MEMO_LOCK:
        _MEMO.clear()
        _BUDGET.clear()
        _SPENT.clear()


def _key(digest: bytes, op: dict) -> tuple:
    return digest, json.dumps(op, sort_keys=True)


def _account(digest: bytes) -> list:
    """The document's budget row (under `_MEMO_LOCK`), restarted past `BUDGET_WINDOW_S`."""
    now = time.monotonic()
    row = _BUDGET.get(digest)
    if row is None or now - row[2] > BUDGET_WINDOW_S:
        row = [0.0, 0.0, now, 0]
        _BUDGET[digest] = row
    _BUDGET.move_to_end(digest)
    while len(_BUDGET) > _BUDGET_SIZE:
        _BUDGET.popitem(last=False)
    return row


def ask(data: bytes, ops: list) -> Optional[list]:
    """The answers to ``ops`` (one dict per operation, PNG blob indices replaced by the bytes), or None when the
    child timed out, crashed, exited non-zero or wrote anything that does not parse, or the document has spent its
    budget, or no slot came free within its wait budget."""
    digest = hashlib.sha256(data).digest()
    keys = [_key(digest, op) for op in ops]
    with _MEMO_LOCK:
        while True:
            if digest in _SPENT:
                return None
            hits = [_MEMO.get(k) for k in keys]
            for k, hit in zip(keys, hits):
                if hit is not None:
                    _MEMO.move_to_end(k)
            if all(h is not None for h in hits):
                return None if any(h[0] is None for h in hits) else [h[0] for h in hits]
            row = _account(digest)
            time_left, wait_left = DOC_BUDGET_S - row[0], DOC_WAIT_S - row[1]
            if time_left > 0 or not row[3] or wait_left <= 0:
                break
            t0 = time.monotonic()           # the budget is reserved by this document's running child: wait for it
            _SETTLED.wait(wait_left)
            row[1] += time.monotonic() - t0
        held = row[3]
        if time_left > 0:
            limit = min(TIMEOUT_S, time_left)
            row[0] += limit                 # reserved now, the unused part refunded when the child is done
            row[3] += 1
    if time_left <= 0:
        logger.warning('pdfium budget %s: %.0f s of child time for this document',
                       'held by a running child past the wait budget' if held else 'spent', DOC_BUDGET_S)
        return None
    used = [0.0]
    try:
        results = _spawn(data, ops, digest, limit, wait_left, used)
    except _TimedOut:
        if limit >= TIMEOUT_S:              # killed at the full limit: the bytes, not the budget, are to blame
            with _MEMO_LOCK:
                _SPENT[digest] = None
                while len(_SPENT) > _SPENT_SIZE:
                    _SPENT.popitem(last=False)
        return None
    except _Transient:
        return None
    finally:
        with _MEMO_LOCK:
            row[0] -= limit - used[0]
            row[3] -= 1
            _SETTLED.notify_all()
    with _MEMO_LOCK:
        for i, k in enumerate(keys):
            _MEMO[k] = (None if results is None else results[i],)
        while len(_MEMO) > _MEMO_SIZE or (len(_MEMO) > 1 and _memo_bytes() > _MEMO_MAX_BYTES):
            _MEMO.popitem(last=False)
    return results


def _memo_bytes() -> int:
    return sum(_result_bytes(v[0]) for v in _MEMO.values())


def _result_bytes(result) -> int:
    if not isinstance(result, dict):
        return 0
    return sum(len(p) for p in result.get('pngs') or ()) + len(result.get('png') or b'')


def _charge(digest: bytes, waited: float) -> None:
    """Seconds waited for a slot, charged to the document's wait budget (child time is reserved and settled by
    `ask`, round 10)."""
    with _MEMO_LOCK:
        _account(digest)[1] += waited


def max_png_bytes(max_side_px: int) -> int:
    """The largest PNG a raster of at most ``max_side_px`` square can be: RGB stored uncompressed, a filter byte per
    row, and 1 MiB for zlib's framing and the PNG chunks."""
    side = int(max_side_px)
    return side * side * 3 + side + (1 << 20)


def max_output_bytes(ops: list) -> int:
    """The most PNG bytes ``ops`` can make: one PNG per rendered page, one per stack, each within its raster bound."""
    total = 0
    for op in ops:
        if op.get('op') in ('render', 'stack'):
            count = len(op['pages']) if op['op'] == 'render' else 1
            total += count * max_png_bytes(op['scale'][1])
    return total


def _spawn(data: bytes, ops: list, digest: bytes = b'', timeout: float = TIMEOUT_S,
           wait: float = DOC_WAIT_S, used: Optional[list] = None) -> Optional[list]:
    """One child for ``ops``. Waits at most ``wait`` s for a slot (charged to the document) and runs at most
    ``timeout`` s (its wall time put in ``used[0]``; `ask` settles it against the time it reserved). None for a
    failure the same bytes would repeat; raises `_TimedOut` past the limit and `_Transient` for a failure that is
    not the document's."""
    used = [0.0] if used is None else used
    t0 = time.monotonic()
    got = _SLOTS.acquire(timeout=max(0.0, wait))
    _charge(digest, waited=time.monotonic() - t0)
    if not got:
        logger.warning('pdfium child slot not free within %.0f s', wait)
        raise _Transient
    try:
        request = {'ops': ops, 'parent': os.getpid()}
        if sys.platform.startswith('linux'):
            request.update(memory=MEMORY_LIMIT_BYTES, cpu=int(math.ceil(timeout)) + CPU_GRACE_S)
        payload = json.dumps(request).encode() + b'\n' + data
        for attempt in (1, 2):              # a spawn error (no memory, too many processes) is retried once
            try:
                return _run_child(payload, timeout, len(ops), max_output_bytes(ops), used)
            except OSError as e:
                logger.warning('pdfium child could not start (try %d): %s', attempt, type(e).__name__)
        raise _Transient
    finally:
        _SLOTS.release()


class _Ended(ValueError):
    """The child's output stopped short: it closed stdout (it exited or something killed it), so there is nothing
    to stop, and how it exited says why."""


def _run_child(payload: bytes, timeout: float, n_ops: int, max_blobs: int, used: list) -> Optional[list]:
    t0 = time.monotonic()
    proc = subprocess.Popen([sys.executable, '-I', _WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    try:
        return _watch(proc, payload, timeout, n_ops, max_blobs)
    except (_TimedOut, _Transient):
        raise
    except BaseException as e:      # round 10: anything else once the child exists (a thread that will not start)
        _stop(proc)
        if not isinstance(e, Exception):
            raise
        logger.warning('pdfium child abandoned: %s', type(e).__name__)
        raise _Transient from None
    finally:
        used[0] = time.monotonic() - t0


def _stop(proc) -> None:
    """Kill the child, reap it and close its pipes; never raises."""
    for step in (proc.kill, lambda: proc.wait(5), proc.stdin.close, proc.stdout.close):
        try:
            step()
        except Exception:
            pass


def _watch(proc, payload: bytes, timeout: float, n_ops: int, max_blobs: int) -> Optional[list]:
    box = {}

    def feed():
        try:
            proc.stdin.write(payload)
        except OSError:             # the child exited early (it is judged by its exit and output)
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    def drain():
        try:
            box['out'] = _read_output(proc.stdout, n_ops, max_blobs)
        except _Ended as e:         # the child closed its output: judged by how it exited, nothing to kill
            box['err'] = e
        except Exception as e:      # output that does not parse or is past its cap: the child is stopped
            box['err'] = e
            box['killed'] = True    # by us: its signal says nothing about the instance
            proc.kill()

    threads = [threading.Thread(target=feed, daemon=True), threading.Thread(target=drain, daemon=True)]
    for t in threads:
        t.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        logger.warning('pdfium child killed after %.1f s', timeout)
        raise _TimedOut from None
    finally:
        for t in threads:
            t.join(5)
        proc.stdout.close()
    if proc.returncode < 0 and not box.get('killed'):
        # Round 10: checked FIRST. A signal we did not send (the instance's OOM killer) says nothing about the
        # bytes, whatever the child wrote before it (usually nothing: its output then does not parse).
        logger.warning('pdfium child killed by signal %s', -proc.returncode)
        raise _Transient
    if proc.returncode == pdfium_worker.OUT_OF_MEMORY:
        logger.warning('pdfium child out of memory (address space capped at its size + %d MiB)',
                       MEMORY_LIMIT_BYTES >> 20)
        return None
    if 'err' in box:
        logger.warning('pdfium child output unreadable: %s', type(box['err']).__name__)
        return None
    if proc.returncode != 0:
        logger.warning('pdfium child failed: exit %s', proc.returncode)
        return None
    if 'out' not in box:
        logger.warning('pdfium child output unreadable: no answer')
        return None
    return box['out']


def _read_output(stream, n_ops: int, max_blobs: int) -> list:
    """The child's answers read straight off its stdout, each PNG read once into its own bytes. Raises on any
    mismatch, a header past `MAX_HEADER_BYTES`, PNGs past ``max_blobs`` or bytes after the last PNG; `_Ended` when
    the output stops short (no header line, a short PNG)."""
    head = stream.readline(MAX_HEADER_BYTES + 1)
    if not head.endswith(b'\n'):
        if len(head) <= MAX_HEADER_BYTES:
            raise _Ended('no header')
        raise ValueError('a header past its cap')
    header = json.loads(head)
    del head
    sizes, results = header['blobs'], header['results']
    if (not isinstance(results, list) or len(results) != n_ops or not isinstance(sizes, list)
            or not all(isinstance(s, int) and s >= 0 for s in sizes)):
        raise ValueError('a header that does not match the output')
    if sum(sizes) > max_blobs:
        raise ValueError('more PNG bytes than the renders asked for')
    blobs = []
    for s in sizes:
        blob = stream.read(s)
        if len(blob) != s:
            raise _Ended('a short PNG')
        blobs.append(blob)
    if stream.read(1):
        raise ValueError('a header that does not match the output')
    for r in results:
        if not isinstance(r, dict):
            raise ValueError('an answer that is not a dict')
        if 'pngs' in r:
            r['pngs'] = [blobs[i] for i in r['pngs']]
        if r.get('png') is not None:
            r['png'] = blobs[r['png']]
    return results
