"""LL6 phase P1 - the STORE CHILD: it fetches a frozen exam file from, or keeps a newly frozen one in, the
replay's private Cloud Storage bucket. Standard library only (no google SDK, no new dependency).

The parent starts it as `python -m replay.exam_store fetch|put ...`, once per exam, with the environment
`store_env` builds from nothing (PATH, PYTHONPATH, LANG). It holds no database URL, no fingerprint key, no
salt, no Django; it refuses to start with any other name in its environment (`environment_ok`). It imports
only the standard library, `netguard` and the pure `lens_human`.

TWO ENTRY POINTS, NO THIRD. The mode is the first word and is required; there is no default and no mode
that does both:
* ``fetch --bucket B --exam NAME --folder ABS`` - GET the object's metadata (size, md5Hash, generation);
  ABSENT only when that GET answers 404 AND a list GET of the same bucket (``prefix`` = the object name,
  ``maxResults=1``) answers 200 with a JSON object: the bucket is proved there, the object is not. Cloud
  Storage answers 404 for a missing bucket too, so a 404 alone is never ABSENT; a 403, or any other
  answer to either GET, is FETCH_FAILED. GET the bytes of THAT generation
  (``ifGenerationMatch``); refuse over `MAX_EXAM_BYTES`; check the size and the md5; write
  ``<folder>/<NAME>.json`` as a new file (never over an existing one). FETCHED. It never sends a POST.
  It does not judge the content: a corrupt stored exam is the lens's refusal to give, not this one's.
* ``put --bucket B --exam NAME --folder ABS --digest D12 --size N --frozen-at T`` - first, with no
  network, PROVE the file is the exam the lens froze in this run: read its bytes once (a regular file,
  never a link); `lens_human.load_exam` must accept it; its digest (first 12), size and frozen_at must
  equal the arguments; the bytes read must parse to the same exam; a second read must have the same
  sha256. Any miss is NOT_VERIFIED and nothing is sent. Then ONE create-only POST
  (``ifGenerationMatch=0``: a 412 means the object already exists, which is never overwritten):
  accepted with the same md5 and size (read by a metadata GET when the POST answer lacks them) = KEPT;
  412 and the stored object has the same md5 and size = KEPT (an earlier try of ours landed); 412 and
  another md5 = FROZEN_ELSEWHERE; a transport error, a 429 or a 5xx is tried ONE more time (safe: the
  POST is create-only), then PUT_FAILED; any other answer, or a mismatch, = PUT_FAILED.
The parent decides WHETHER to call ``put`` (only with `--human-lens-freeze`, phase P2); this module makes
sure that a ``fetch`` can never upload and that a ``put`` can only send bytes the lens itself froze.

THE NETWORK. The two names (`METADATA_HOST`, `STORAGE_HOST`) are resolved ONCE, to one IPv4 address each,
BEFORE `netguard.refuse_network` is up; then only those two (address, port) pairs may be reached. No
address is written in this file. Each request connects to the pinned address itself; Storage is spoken
over TLS with ``ssl.create_default_context()`` (certificate and host name checked against
`STORAGE_HOST`), never unverified. The access token comes from the metadata server (header
``Metadata-Flavor: Google``; the answer must carry it too).

WHAT LEAVES THE PROCESS: exactly one line on stdout, ``{"code": "<code>"}``, the code from the fixed sets
`FETCH_CODES` / `PUT_CODES`. Run as a module, fd 1 and fd 2 point at /dev/null from the moment the
module's own start-up code runs (before `main`, after only the imports, when no token, argument or exam
has been read) to the end, and the line is written to a private copy of the real stdout, so nothing else
(a library's print, a traceback) can add a line. Every error becomes a fixed code. Never a token, URL,
bucket name, message or exam content; this module has no logging and prints nothing else. The token is held in `_Token` (its repr is
fixed), checked to be plain token characters before it goes into a header, and never placed in an
exception: errors are raised OUTSIDE the ``except`` that met them, so no exception chain carries a
parsed body.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import stat
import sys
import tempfile
from urllib.parse import quote

from . import lens_human, netguard

FETCH, PUT = 'fetch', 'put'
#: The fixed result codes. A fetch answers FETCHED or ABSENT when it worked; a put KEPT or FROZEN_ELSEWHERE.
FETCHED, ABSENT, FETCH_FAILED = 'fetched', 'absent', 'fetch_failed'
KEPT, FROZEN_ELSEWHERE, PUT_FAILED, NOT_VERIFIED = 'kept', 'frozen_elsewhere', 'put_failed', 'not_verified'
REFUSED = 'refused'   # the request itself was refused (a bad or missing argument, a foreign environment)
FETCH_CODES = (FETCHED, ABSENT, FETCH_FAILED, REFUSED)
PUT_CODES = (KEPT, FROZEN_ELSEWHERE, PUT_FAILED, NOT_VERIFIED, REFUSED)
GOOD_CODES = frozenset({FETCHED, ABSENT, KEPT, FROZEN_ELSEWHERE})
#: The one key of the one result line.
RESULT_KEY = 'code'

METADATA_HOST, STORAGE_HOST = 'metadata.google.internal', 'storage.googleapis.com'
#: Each name's port and whether it is spoken over TLS. Nothing else is ever reached.
HOSTS = {METADATA_HOST: (80, False), STORAGE_HOST: (443, True)}
TOKEN_PATH = '/computeMetadata/v1/instance/service-accounts/default/token'
#: A stored exam larger than this is refused (an exam of 50 ids is a few kB).
MAX_EXAM_BYTES = 16 * 1024 * 1024
#: The most a token or metadata answer may hold.
MAX_META_BYTES = 64 * 1024
#: Seconds for each socket step (connect, send, each read). The parent's own wait bounds the whole child.
TIMEOUT_S = 20
#: The store child's WHOLE environment (`store_env`).
STORE_ENV_NAMES = ('PATH', 'PYTHONPATH', 'LANG')
#: What the child accepts in its own environment: those, and `LC_CTYPE`, which Python's own C-locale
#: coercion may set at start-up.
_ACCEPTED_ENV = frozenset(STORE_ENV_NAMES) | {'LC_CTYPE'}

#: A plain bucket name: lower-case letters, digits, `-` and `_`, 3 to 63 characters, no dots.
_BUCKET = re.compile(r'[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]')
_DIGEST_12 = re.compile(r'[0-9a-f]{12}')
_SIZE = re.compile(r'[1-9][0-9]{0,8}')
_DIGITS = re.compile(r'[0-9]{1,20}')
_MD5_B64 = re.compile(r'[A-Za-z0-9+/]{22}==')
#: An OAuth access token's characters (RFC 6750 b64token); nothing that could break a header line.
_TOKEN_SHAPE = re.compile(r'[A-Za-z0-9._~+/=-]{16,4096}')
_FROZEN_AT_MAX = 64
#: What a request may raise on the wire (a refused connection, a timeout, TLS, a broken answer).
TRANSPORT_ERRORS = (OSError, http.client.HTTPException)


class StoreFailed(Exception):
    """A fixed refusal. ``code`` is a result code, or None for the running mode's own failure code. It
    never carries a message."""

    def __init__(self, code=None):
        super().__init__(code or 'failed')
        self.code = code


class _Token:
    """The access token. Its repr and text are fixed, so a printed local or argument never shows it."""
    __slots__ = ('_value',)

    def __init__(self, value):
        self._value = value

    def __repr__(self):
        return '<token>'

    __str__ = __repr__

    def header(self):
        return {'Authorization': 'Bearer ' + self._value}


# ── The environment and the request ─────────────────────────────────────────────────────────────────
def store_env(env, harness_dir):
    """The store child's WHOLE environment, built from nothing: the path, the harness folder (the
    `replay` package; nothing of the api tree) and a UTF-8 locale. ``env`` gives the path only."""
    return {'PATH': env.get('PATH', '/usr/bin:/bin'), 'PYTHONPATH': harness_dir, 'LANG': 'C.UTF-8'}


def environment_ok(env) -> bool:
    """True only when every name in ``env`` is one the store child is given (`store_env`)."""
    return set(env) <= _ACCEPTED_ENV


def bucket_name_ok(name) -> bool:
    """True for a plain bucket name (see `_BUCKET`)."""
    return isinstance(name, str) and _BUCKET.fullmatch(name) is not None


class _Refused(Exception):
    """An argument the store child does not take. Carries nothing."""


class _Parser(argparse.ArgumentParser):
    """argparse that never prints (no usage, no help, no value echoed): any error raises `_Refused`."""

    def error(self, message):
        raise _Refused()

    def exit(self, status=0, message=None):
        raise _Refused()


def _checked(pattern):
    def check(text):
        if not isinstance(text, str) or pattern.fullmatch(text) is None:
            raise ValueError('refused')
        return text
    return check


def _absolute(text):
    if not text or not os.path.isabs(text):
        raise ValueError('refused')
    return text


def _frozen_at(text):
    if not text or len(text) > _FROZEN_AT_MAX or not text.isascii() or not text.isprintable():
        raise ValueError('refused')
    return text


def parse_args(argv):
    """The request: ``fetch`` or ``put`` and its arguments. `_Refused` for anything else, including no
    mode at all. Abbreviations are off and there is no help flag."""
    ap = _Parser(prog='exam_store', add_help=False, allow_abbrev=False)
    modes = ap.add_subparsers(dest='mode', required=True)
    for mode in (FETCH, PUT):
        sub = modes.add_parser(mode, add_help=False, allow_abbrev=False)
        sub.add_argument('--bucket', required=True, type=_checked(_BUCKET))
        sub.add_argument('--exam', required=True, choices=lens_human.EXAM_NAMES)
        sub.add_argument('--folder', required=True, type=_absolute)
        if mode == PUT:
            sub.add_argument('--digest', required=True, type=_checked(_DIGEST_12))
            sub.add_argument('--size', required=True, type=lambda t: int(_checked(_SIZE)(t)))
            sub.add_argument('--frozen-at', required=True, type=_frozen_at)
    return ap.parse_args(list(argv))


# ── The network: names resolved once, then pinned ───────────────────────────────────────────────────
def resolve_hosts(getaddrinfo=socket.getaddrinfo):
    """``{name: (ip, port)}`` for `HOSTS`: each name resolved ONCE, to its first IPv4 address. Call it
    BEFORE `netguard.refuse_network`; the result is the guard's whole allow list. StoreFailed when a
    name does not resolve."""
    found = {}
    for host, (port, _tls) in HOSTS.items():
        try:
            infos = getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        except (OSError, UnicodeError):
            infos = []
        ips = [info[4][0] for info in infos if len(info) == 5 and isinstance(info[4], tuple) and info[4]]
        if not ips or not isinstance(ips[0], str):
            raise StoreFailed()
        found[host] = (ips[0], port)
    return found


def _tls_context():
    """The default context: the system's CA bundle, certificate and host name checked, TLS 1.2 or later."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise StoreFailed()
    return context


class _PinnedConnection(http.client.HTTPConnection):
    """An HTTP connection to ONE pinned address, spoken to ``host`` (the Host header, and the TLS host
    name when ``tls``). It never resolves a name itself."""

    def __init__(self, host, address, *, tls, timeout, socket_factory):
        super().__init__(host, address[1], timeout=timeout)
        self.default_port = address[1]          # so the Host header is the bare name
        self._address, self._tls, self._socket_factory = address, tls, socket_factory

    def connect(self):
        sock = self._socket_factory(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect(self._address)
            if self._tls:
                sock = _tls_context().wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise
        self.sock = sock


class PinnedHttp:
    """``http(host, method, path, headers, body=None, limit=...)`` -> ``(status, {lower-case header:
    value}, body bytes)``, at most ``limit + 1`` bytes of body read. One connection per request, to
    the address resolved for ``host``; any other name raises StoreFailed."""

    def __init__(self, addresses, *, timeout=TIMEOUT_S, socket_factory=socket.socket):
        self._addresses, self._timeout, self._socket_factory = dict(addresses), timeout, socket_factory

    def __call__(self, host, method, path, headers, body=None, limit=MAX_META_BYTES):
        if host not in self._addresses or host not in HOSTS:
            raise StoreFailed()
        conn = _PinnedConnection(host, self._addresses[host], tls=HOSTS[host][1], timeout=self._timeout,
                                 socket_factory=self._socket_factory)
        try:
            conn.request(method, path, body=body, headers=dict(headers, Connection='close'))
            response = conn.getresponse()
            data = response.read(limit + 1)
            return response.status, {k.lower(): v for k, v in response.getheaders()}, data
        finally:
            conn.close()


# ── Answers ─────────────────────────────────────────────────────────────────────────────────────────
def _json(body):
    """The JSON object in ``body``, or None. Never raises, so no exception ever holds the body."""
    try:
        data = json.loads(body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError, RecursionError, AttributeError):
        return None
    return data if isinstance(data, dict) else None


def md5_b64(data) -> str:
    """The md5 of ``data`` as Cloud Storage writes ``md5Hash`` (base64 of the 16 bytes)."""
    return base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode('ascii')


def _size_md5(data):
    """``(size, md5Hash)`` from an object resource, or None unless both have their one form."""
    if not isinstance(data, dict):
        return None
    size, md5 = data.get('size'), data.get('md5Hash')
    if not (isinstance(size, str) and _DIGITS.fullmatch(size) and isinstance(md5, str)
            and _MD5_B64.fullmatch(md5)):
        return None
    return int(size), md5


def object_path(bucket, name) -> str:
    """The metadata path of ``<name>.json`` in ``bucket``."""
    return f'/storage/v1/b/{bucket}/o/{quote(name + ".json", safe="")}'


def media_path(bucket, name, generation) -> str:
    """The bytes of ``<name>.json``, of that one generation only."""
    return f'{object_path(bucket, name)}?alt=media&ifGenerationMatch={generation}'


def list_path(bucket, name) -> str:
    """A list of ``bucket`` holding at most the one object named ``<name>.json`` (and only its name).
    It proves the bucket is there; it needs only the list right that ``objectViewer`` gives."""
    return (f'/storage/v1/b/{bucket}/o?prefix={quote(name + ".json", safe="")}&maxResults=1'
            f'&fields={quote("items(name)", safe="")}')


def upload_path(bucket, name) -> str:
    """The create-only upload of ``<name>.json``: ``ifGenerationMatch=0`` refuses (412) when it exists."""
    return (f'/upload/storage/v1/b/{bucket}/o?uploadType=media&name={quote(name + ".json", safe="")}'
            '&ifGenerationMatch=0')


def metadata_token(http) -> _Token:
    """The service account's access token from the metadata server. StoreFailed on any other answer."""
    status, headers, body = http(METADATA_HOST, 'GET', TOKEN_PATH, {'Metadata-Flavor': 'Google'},
                                 limit=MAX_META_BYTES)
    data = None
    if status == 200 and headers.get('metadata-flavor') == 'Google' and len(body) <= MAX_META_BYTES:
        data = _json(body)
    value = data.get('access_token') if data else None
    if not isinstance(value, str) or _TOKEN_SHAPE.fullmatch(value) is None:
        raise StoreFailed()
    return _Token(value)


def object_meta(http, token, bucket, name):
    """``(size, md5Hash, generation)`` of the stored ``<name>.json``; None on HTTP 404 and nothing else.
    A 404 is NOT yet "absent": Cloud Storage answers 404 for a missing bucket too. Only `fetch_exam`
    turns it into ABSENT, after `bucket_reachable`; a put treats None as a failure. StoreFailed on any
    other answer (a 403 included)."""
    status, _headers, body = http(STORAGE_HOST, 'GET', object_path(bucket, name), token.header(),
                                  limit=MAX_META_BYTES)
    if status == 404:
        return None
    data = _json(body) if status == 200 and len(body) <= MAX_META_BYTES else None
    found = _size_md5(data)
    generation = data.get('generation') if data else None
    if found is None or not isinstance(generation, str) or _DIGITS.fullmatch(generation) is None:
        raise StoreFailed()
    return found[0], found[1], generation


def bucket_reachable(http, token, bucket, name) -> bool:
    """True only when ONE list GET of ``bucket`` (`list_path`) answers 200 with a JSON object (with or
    without ``items``): the bucket is there. False on any other answer; a transport error is raised.
    No error text is read. Called by `fetch_exam` only, after a 404 on the object."""
    status, _headers, body = http(STORAGE_HOST, 'GET', list_path(bucket, name), token.header(),
                                  limit=MAX_META_BYTES)
    return status == 200 and len(body) <= MAX_META_BYTES and _json(body) is not None


# ── fetch ───────────────────────────────────────────────────────────────────────────────────────────
def _write_new(folder, name, data):
    """``<folder>/<name>.json`` as a NEW file: a temp file, then a hard link to the name (fails when the
    name exists, unlike a rename). The temp file is always removed."""
    target = os.path.join(folder, f'{name}.json')
    if os.path.lexists(target):
        raise StoreFailed()
    handle, temp = tempfile.mkstemp(prefix=f'.{name}.', suffix='.fetch', dir=folder)
    try:
        with os.fdopen(handle, 'wb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.link(temp, target)
    finally:
        try:
            os.unlink(temp)
        except OSError:   # clean-up only
            pass


def fetch_exam(http, token, bucket, name, folder) -> str:
    """FETCHED (the file is written) or ABSENT (the object GET answers 404 and `bucket_reachable` proves
    the bucket is there). StoreFailed or a transport error otherwise; `run` turns either into
    FETCH_FAILED. GET requests only."""
    if not os.path.isabs(folder) or not os.path.isdir(folder):
        raise StoreFailed()
    meta = object_meta(http, token, bucket, name)
    if meta is None:
        if not bucket_reachable(http, token, bucket, name):
            raise StoreFailed()                 # no such bucket, or no right to it: never ABSENT
        return ABSENT
    size, md5, generation = meta
    if size > MAX_EXAM_BYTES:
        raise StoreFailed()
    status, _headers, body = http(STORAGE_HOST, 'GET', media_path(bucket, name, generation), token.header(),
                                  limit=MAX_EXAM_BYTES)
    if status != 200 or len(body) != size or md5_b64(body) != md5:
        raise StoreFailed()
    _write_new(folder, name, body)
    return FETCHED


# ── put ─────────────────────────────────────────────────────────────────────────────────────────────
def _read_exam_bytes(path):
    """The file's bytes, read once: a regular file (never a link, a folder or a FIFO), at most
    `MAX_EXAM_BYTES`; else None. ``O_NONBLOCK`` so a FIFO's open does not wait for a writer."""
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as fh:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = fh.read(MAX_EXAM_BYTES + 1)
    return data if len(data) <= MAX_EXAM_BYTES else None


def _proved_bytes(folder, name, digest, size, frozen_at):
    path = os.path.join(folder, f'{name}.json')
    if os.path.islink(path):
        return None
    first = _read_exam_bytes(path)
    if first is None:
        return None
    exam, refusal = lens_human.load_exam(folder, name)
    if refusal is not None or exam is None:
        return None
    if exam['digest'][:12] != digest or exam['size'] != size or exam['frozen_at'] != frozen_at:
        return None
    if _json(first) != exam:                    # the bytes to send are the bytes the lens accepted
        return None
    second = _read_exam_bytes(path)
    if second is None or hashlib.sha256(second).digest() != hashlib.sha256(first).digest():
        return None
    return first


def prove_new_exam(folder, name, digest, size, frozen_at) -> bytes:
    """The bytes of ``<folder>/<name>.json`` once PROVED to be the exam the lens froze: `load_exam`
    accepts it, its digest (first 12), size and frozen_at are the given ones, the bytes read parse to
    that exam and a second read is unchanged. StoreFailed(NOT_VERIFIED) otherwise. No network."""
    try:
        data = _proved_bytes(folder, name, digest, size, frozen_at)
    except (OSError, ValueError, TypeError, KeyError):
        data = None
    if data is None:
        raise StoreFailed(NOT_VERIFIED)
    return data


def _post_once(http, token, bucket, name, data):
    """``(status, body)`` of one create-only POST; status None on a transport error."""
    headers = dict(token.header(), **{'Content-Type': 'application/json'})
    try:
        status, _headers, body = http(STORAGE_HOST, 'POST', upload_path(bucket, name), headers, body=data,
                                      limit=MAX_META_BYTES)
    except TRANSPORT_ERRORS:
        return None, b''
    return status, body


def _retryable(status):
    return status is None or status == 429 or 500 <= status <= 599


def keep_exam(http, token, bucket, name, data) -> str:
    """KEPT, FROZEN_ELSEWHERE or PUT_FAILED for ONE create-only upload of ``data`` (proved first by
    `prove_new_exam`). A transport error, 429 or 5xx is tried once more; never an overwrite."""
    mine = (len(data), md5_b64(data))
    status, body = _post_once(http, token, bucket, name, data)
    if _retryable(status):
        status, body = _post_once(http, token, bucket, name, data)
    if status == 412:                           # it exists: ours from the first try, or another run's
        stored = object_meta(http, token, bucket, name)
        if stored is None:
            return PUT_FAILED
        return KEPT if (stored[0], stored[1]) == mine else FROZEN_ELSEWHERE
    if status != 200:
        return PUT_FAILED
    landed = _size_md5(_json(body) if len(body) <= MAX_META_BYTES else None)
    if landed is None:                          # the answer lacks them: read the stored object's own
        stored = object_meta(http, token, bucket, name)
        landed = (stored[0], stored[1]) if stored else None
    return KEPT if landed == mine else PUT_FAILED


# ── The child ───────────────────────────────────────────────────────────────────────────────────────
def run(argv, *, env, getaddrinfo=socket.getaddrinfo, opener=None) -> str:
    """The store child's whole work; returns ONE fixed code and never raises. In order: the request
    (`parse_args`) and the environment (`environment_ok`), both REFUSED; for a put, the proof
    (`prove_new_exam`), for a fetch, a folder with no exam file in it yet, both with no network; the two names resolved (`resolve_hosts`); then, inside
    `netguard.refuse_network` with only those two addresses, the token and the one fetch or keep.
    ``opener(addresses)`` returns the ``http`` callable (`PinnedHttp` unless the tests give one)."""
    failure = PUT_FAILED if list(argv[:1]) == [PUT] else FETCH_FAILED
    try:
        try:
            args = parse_args(argv)
        except _Refused:
            args = None
        if args is None or not environment_ok(env):
            return REFUSED
        data = None
        if args.mode == PUT:
            data = prove_new_exam(args.folder, args.exam, args.digest, args.size, args.frozen_at)
        elif not os.path.isdir(args.folder) or os.path.lexists(os.path.join(args.folder, f'{args.exam}.json')):
            return FETCH_FAILED                 # nowhere to write, or a local exam already there: no network
        addresses = resolve_hosts(getaddrinfo)
        with netguard.refuse_network(set(addresses.values())):
            http = (opener or PinnedHttp)(addresses)
            token = metadata_token(http)
            if args.mode == FETCH:
                return fetch_exam(http, token, args.bucket, args.exam, args.folder)
            return keep_exam(http, token, args.bucket, args.exam, data)
    except StoreFailed as exc:
        return exc.code or failure
    except BaseException:                       # anything at all: the mode's fixed failure, never a message
        return failure


def result_line(code) -> str:
    """The one line the child prints."""
    return json.dumps({RESULT_KEY: code}, sort_keys=True) + '\n'


def _private_stdout():
    """Point fd 1 and fd 2 at /dev/null for the rest of the run; return a private copy of the real
    stdout, which receives the one result line and nothing else."""
    out = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)
    return out


def main(argv=None, env=None) -> str:
    return run(sys.argv[1:] if argv is None else argv, env=os.environ if env is None else env)


if __name__ == '__main__':
    _out = _private_stdout()
    _code = main()
    os.write(_out, result_line(_code).encode('ascii'))
    sys.exit(0 if _code in GOOD_CODES else 1)
