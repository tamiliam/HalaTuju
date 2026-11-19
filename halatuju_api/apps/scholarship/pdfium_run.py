"""Run pdfium on an upload in a child process with a hard wall-clock limit (S-visible fix round 8, 2026-11-19).

Replaces round 6's process-wide pdfium lock. pypdfium2 4.30 is not thread-safe, and under the lock one crafted PDF
that kept pdfium busy (an annotation's appearance stream rendered for 38 s, a 746-byte page of huge text 11 s, 10,500
clip paths 14 s, Type3 glyphs 13.5 s) froze every upload in the gunicorn worker. Modelling pdfium's cost (rounds 5-7)
never ended, so it is no longer the safety line: every pdfium operation on an upload runs in `pdfium_worker`, a fresh
``python -I`` child per call (no shared state, so no lock), killed after `TIMEOUT_S`, its address space capped on
Linux (`MEMORY_LIMIT_BYTES`), at most `MAX_CHILDREN` at once per web process. The round 5-7 whitelists and caps stay
as a cheap pre-filter (a refusal there spawns nothing).

Timeout, crash, non-zero exit or output that does not parse: `ask` returns None and the caller takes its safe
answer — the visibility check: hidden (the Vision route); a render: None / [] (the "cannot read" path); the page
count: 0; the SPM word boxes: none (the Gemini read). Never the hidden text.
"""
import hashlib
import json
import logging
import os
import subprocess
import sys
import threading
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)

#: Wall-clock seconds one child may run (start-up included). Real corpus (533 PDFs, 2026-11-19): the slowest child
#: call took 1.53 s on the dev machine (median 0.34 s); 20 s leaves room for a 1-vCPU instance running several at
#: once. Past it the child is killed and the caller gets the safe answer.
TIMEOUT_S = 20.0
#: Bytes a child may add to its address space after loading Python, pypdfium2 and Pillow (Linux only). The
#: instance has 2 GiB for 2 gunicorn workers; the largest real child peaked at 176 MB (median 66 MB).
MEMORY_LIMIT_BYTES = 640 * 1024 * 1024
#: Children running at once per web process (each gunicorn worker): 2 workers x 2 x 640 MB stays inside the
#: instance with the workers' own memory. A thread waits for a slot; each slot is freed within `TIMEOUT_S`.
MAX_CHILDREN = 2
_SLOTS = threading.BoundedSemaphore(MAX_CHILDREN)
_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdfium_worker.py')

#: One upload is asked about by several readers (the slip gate, the Vision route, the offer reader): the answers
#: of one child call are kept, keyed on the SHA-256 of the bytes and the operation, so a repeated question spawns
#: nothing. Failures are kept too (a hostile file times out once per worker, not once per reader). Small LRU.
_MEMO_SIZE = 16
_MEMO_MAX_BYTES = 48_000_000
_MEMO: 'OrderedDict[tuple, tuple]' = OrderedDict()
_MEMO_LOCK = threading.Lock()
#: Uploads whose child ran past `TIMEOUT_S`: every later question about them gets the safe answer at once, so
#: one request that asks several things of a hostile file waits out the limit once, not once per question.
_TIMED_OUT: 'OrderedDict[bytes, None]' = OrderedDict()
_TIMED_OUT_SIZE = 64


class _TimedOut(Exception):
    pass


def memo_clear() -> None:
    with _MEMO_LOCK:
        _MEMO.clear()
        _TIMED_OUT.clear()


def _key(digest: bytes, op: dict) -> tuple:
    return digest, json.dumps(op, sort_keys=True)


def ask(data: bytes, ops: list) -> Optional[list]:
    """The answers to ``ops`` (one dict per operation, PNG blob indices replaced by the bytes), or None when the
    child timed out, crashed, exited non-zero or wrote anything that does not parse."""
    digest = hashlib.sha256(data).digest()
    keys = [_key(digest, op) for op in ops]
    with _MEMO_LOCK:
        if digest in _TIMED_OUT:
            return None
        hits = [_MEMO.get(k) for k in keys]
        for k, hit in zip(keys, hits):
            if hit is not None:
                _MEMO.move_to_end(k)
    if all(h is not None for h in hits):
        return None if any(h[0] is None for h in hits) else [h[0] for h in hits]
    try:
        results = _spawn(data, ops)
    except _TimedOut:
        with _MEMO_LOCK:
            _TIMED_OUT[digest] = None
            while len(_TIMED_OUT) > _TIMED_OUT_SIZE:
                _TIMED_OUT.popitem(last=False)
        return None
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


def _spawn(data: bytes, ops: list) -> Optional[list]:
    request = {'ops': ops, 'memory': MEMORY_LIMIT_BYTES if sys.platform.startswith('linux') else 0}
    payload = json.dumps(request).encode() + b'\n' + data
    with _SLOTS:
        try:
            done = subprocess.run([sys.executable, '-I', _WORKER], input=payload, capture_output=True,
                                  timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            logger.warning('pdfium child killed after %.0f s', TIMEOUT_S)
            raise _TimedOut from None
        except OSError as e:
            logger.warning('pdfium child could not start: %s', type(e).__name__)
            return None
    if done.returncode != 0:
        logger.warning('pdfium child failed: exit %s', done.returncode)
        return None
    try:
        return _parse_output(done.stdout, len(ops))
    except Exception as e:   # output that does not parse is a failed child
        logger.warning('pdfium child output unreadable: %s', type(e).__name__)
        return None


def _parse_output(out: bytes, n_ops: int) -> list:
    """The child's answers with blob indices swapped for the bytes. Raises on any mismatch."""
    head, sep, rest = out.partition(b'\n')
    if not sep:
        raise ValueError('no header')
    header = json.loads(head)
    sizes, results = header['blobs'], header['results']
    if (not isinstance(results, list) or len(results) != n_ops or not isinstance(sizes, list)
            or not all(isinstance(s, int) and s >= 0 for s in sizes) or sum(sizes) != len(rest)):
        raise ValueError('a header that does not match the output')
    blobs, at = [], 0
    for s in sizes:
        blobs.append(rest[at:at + s])
        at += s
    for r in results:
        if not isinstance(r, dict):
            raise ValueError('an answer that is not a dict')
        if 'pngs' in r:
            r['pngs'] = [blobs[i] for i in r['pngs']]
        if r.get('png') is not None:
            r['png'] = blobs[r['png']]
    return results
