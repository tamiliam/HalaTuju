"""LL6 phase P1: the store child (`replay.exam_store`), which fetches or keeps a frozen exam file in the
replay's Cloud Storage bucket. No network, no real bucket: the bucket, the metadata server and the name
lookup are fakes; the TLS and wire tests use a fake socket. No database."""
import base64
import datetime
import hashlib
import io
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import traceback

import pytest

from apps.scholarship.eval.replay import exam_store, guards, lens_human, netguard, parent, scrub

ES = exam_store
EVAL_DIR = pathlib.Path(lens_human.__file__).resolve().parent.parent
SOURCE = pathlib.Path(exam_store.__file__).read_text(encoding='utf-8')
#: A token that must never leave the store child.
CANARY = 'ya29.c4n4ry-' + 'Q' * 40
BUCKET = 'bkt-test'
NOW = datetime.datetime(2026, 11, 25, 9, 0, tzinfo=datetime.timezone.utc)
#: TEST-NET addresses (RFC 5737): never reachable, never written in the module itself.
ADDRS = {ES.METADATA_HOST: '192.0.2.10', ES.STORAGE_HOST: '198.51.100.7'}


def _md5(data):
    return base64.b64encode(hashlib.md5(data).digest()).decode('ascii')


def _resource(name, data, generation):
    return {'name': f'{name}.json', 'size': str(len(data)), 'md5Hash': _md5(data), 'generation': generation}


class FakeGcs:
    """The metadata server and one bucket. ``script[kind]`` (token / meta / media / upload) is a list
    used first: an exception is raised, a tuple is the answer, a callable gets the default answer
    (side effects already applied) and returns the answer."""

    def __init__(self, token=CANARY):
        self.token, self.objects, self.script, self.calls = token, {}, {}, []
        self._generation = 1700000000000000

    def _kind(self, host, method, path):
        if host == ES.METADATA_HOST:
            return 'token'
        if method == 'POST':
            return 'upload'
        return 'media' if 'alt=media' in path else 'meta'

    def __call__(self, host, method, path, headers, body=None, limit=ES.MAX_META_BYTES):
        kind = self._kind(host, method, path)
        self.calls.append((host, method, path, kind))
        queued = self.script.get(kind)
        item = queued.pop(0) if queued else None
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, tuple):
            return item
        answer = self._default(kind, host, path, headers, body)
        return item(answer) if callable(item) else answer

    def _default(self, kind, host, path, headers, body):
        if kind == 'token':
            assert headers == {'Metadata-Flavor': 'Google'}
            return 200, {'metadata-flavor': 'Google'}, json.dumps(
                {'access_token': self.token, 'expires_in': 3599, 'token_type': 'Bearer'}).encode()
        assert host == ES.STORAGE_HOST
        if headers.get('Authorization') != 'Bearer ' + self.token:
            return 401, {}, b'{}'
        if kind == 'upload':
            name = re.search(r'[?&]name=([^&]+)', path).group(1)[:-len('.json')]
            if name in self.objects:
                return 412, {}, b'{"error": {"code": 412}}'
            self._generation += 1
            self.objects[name] = (body, str(self._generation))
            return 200, {}, json.dumps(_resource(name, body, str(self._generation))).encode()
        name = path.split('/o/', 1)[1].split('?', 1)[0][:-len('.json')]
        if name not in self.objects:
            return 404, {}, b'{"error": {"code": 404}}'
        data, generation = self.objects[name]
        if kind == 'meta':
            return 200, {}, json.dumps(_resource(name, data, generation)).encode()
        assert f'ifGenerationMatch={generation}' in path
        return 200, {}, data

    def kinds(self):
        return [c[3] for c in self.calls]


class Resolver:
    """A fake `socket.getaddrinfo`, recording each name asked for."""

    def __init__(self, addrs=ADDRS):
        self.addrs, self.asked = dict(addrs), []

    def __call__(self, host, port, family=0, type=0, proto=0, flags=0):
        self.asked.append(host)
        if host not in self.addrs:
            raise socket.gaierror('no such name')
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (self.addrs[host], port))]


def _run(argv, fake=None, resolver=None, env=None):
    fake = FakeGcs() if fake is None else fake
    resolver = Resolver() if resolver is None else resolver
    code = ES.run(argv, env=ES.store_env({'PATH': '/usr/bin:/bin'}, '/h') if env is None else env,
                  getaddrinfo=resolver, opener=lambda addresses: fake)
    return code, fake, resolver


def _freeze(folder, name='exam-old', n=3):
    ids = list(range(1, n + 1))
    exam, refusal = lens_human.freeze_exam(folder, name, ids, [NOW - datetime.timedelta(days=i) for i in ids],
                                           NOW, key_check='0123abcd' if name == 'exam-1' else None)
    assert refusal is None
    return exam


def _put_argv(folder, exam, **over):
    values = {'--bucket': BUCKET, '--exam': exam['exam'], '--folder': str(folder), '--digest': exam['digest'][:12],
              '--size': str(exam['size']), '--frozen-at': exam['frozen_at']}
    values.update(over)
    argv = ['put']
    for flag, value in values.items():
        if value is not None:
            argv += [flag, value]
    return argv


def _fetch_argv(folder, name='exam-old'):
    return ['fetch', '--bucket', BUCKET, '--exam', name, '--folder', str(folder)]


def _exam_bytes(folder, name='exam-old'):
    return (pathlib.Path(folder) / f'{name}.json').read_bytes()


# ── put: the create-only keep ─────────────────────────────────────────────────────────────────────
def test_put_keeps_a_new_exam_with_one_create_only_post(tmp_path):
    exam = _freeze(tmp_path, 'exam-1', n=50)
    code, fake, _r = _run(_put_argv(tmp_path, exam))
    assert code == ES.KEPT
    assert fake.objects['exam-1'][0] == _exam_bytes(tmp_path, 'exam-1')
    posts = [c for c in fake.calls if c[1] == 'POST']
    assert [p[2] for p in posts] == [
        f'/upload/storage/v1/b/{BUCKET}/o?uploadType=media&name=exam-1.json&ifGenerationMatch=0']
    assert fake.kinds() == ['token', 'upload']


def test_put_412_with_the_same_bytes_is_kept_and_another_md5_is_frozen_elsewhere(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.objects['exam-old'] = (_exam_bytes(tmp_path), '7')
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.KEPT
    other = FakeGcs()
    other.objects['exam-old'] = (b'{"another": "exam"}', '8')
    assert _run(_put_argv(tmp_path, exam), other)[0] == ES.FROZEN_ELSEWHERE
    assert other.objects['exam-old'] == (b'{"another": "exam"}', '8')     # never overwritten
    assert other.kinds() == ['token', 'upload', 'meta']


def test_put_retries_a_5xx_exactly_once_then_fails(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.script['upload'] = [(503, {}, b''), (500, {}, b'')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.PUT_FAILED
    assert fake.kinds().count('upload') == 2
    fake = FakeGcs()
    fake.script['upload'] = [(429, {}, b'')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.KEPT
    assert fake.kinds().count('upload') == 2


def test_a_lost_answer_then_412_with_our_bytes_is_kept(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.objects['exam-old'] = (_exam_bytes(tmp_path), '9')     # the first POST landed; its answer was lost
    fake.script['upload'] = [ConnectionResetError()]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.KEPT
    assert fake.kinds() == ['token', 'upload', 'upload', 'meta']


@pytest.mark.parametrize('status', [400, 401, 403, 404, 409])
def test_put_any_other_answer_fails_with_no_retry(tmp_path, status):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.script['upload'] = [(status, {}, b'{}')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.PUT_FAILED
    assert fake.kinds().count('upload') == 1
    assert 'exam-old' not in fake.objects


def test_put_an_answer_with_another_md5_or_size_fails(tmp_path):
    exam = _freeze(tmp_path)
    for change in ({'md5Hash': _md5(b'other')}, {'size': '1'}):
        fake = FakeGcs()
        fake.script['upload'] = [lambda answer, change=change: (200, {}, json.dumps(
            dict(json.loads(answer[2]), **change)).encode())]
        assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.PUT_FAILED


def test_put_reads_the_metadata_when_the_answer_lacks_md5_and_size(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.script['upload'] = [lambda answer: (200, {}, b'{"kind": "storage#object"}')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.KEPT
    assert fake.kinds() == ['token', 'upload', 'meta']
    fake = FakeGcs()
    fake.script['upload'] = [lambda answer: (200, {}, b'not json')]
    fake.script['meta'] = [(200, {}, json.dumps(_resource('exam-old', b'x', '3')).encode())]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.PUT_FAILED


def test_put_412_with_the_object_gone_again_fails(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.script['upload'] = [(412, {}, b'')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.PUT_FAILED


# ── put: the proof comes first, with no network ───────────────────────────────────────────────────
def test_put_sends_nothing_unless_the_file_is_the_exam_the_lens_froze(tmp_path):
    exam = _freeze(tmp_path)
    for over in ({'--digest': 'f' * 12}, {'--size': str(exam['size'] + 1)},
                 {'--frozen-at': '2026-11-24T09:00:00.000000+00:00'}, {'--exam': 'exam-1'}):
        code, fake, resolver = _run(_put_argv(tmp_path, exam, **over))
        assert code == ES.NOT_VERIFIED
        assert fake.calls == [] and resolver.asked == []
    empty = tmp_path / 'empty'
    empty.mkdir()
    code, fake, resolver = _run(_put_argv(empty, exam))
    assert (code, fake.calls, resolver.asked) == (ES.NOT_VERIFIED, [], [])


def test_put_refuses_a_corrupt_or_linked_exam_file(tmp_path):
    exam = _freeze(tmp_path)
    path = tmp_path / 'exam-old.json'
    good = path.read_bytes()
    path.write_bytes(good.replace(b'"size": 3', b'"size": 4'))
    assert _run(_put_argv(tmp_path, exam))[0] == ES.NOT_VERIFIED
    path.write_bytes(good[:-5])
    assert _run(_put_argv(tmp_path, exam))[0] == ES.NOT_VERIFIED
    real = tmp_path / 'real'
    real.mkdir()
    (real / 'exam-old.json').write_bytes(good)
    path.unlink()
    path.symlink_to(real / 'exam-old.json')
    code, fake, resolver = _run(_put_argv(tmp_path, exam))
    assert (code, fake.calls, resolver.asked) == (ES.NOT_VERIFIED, [], [])


# ── fetch ─────────────────────────────────────────────────────────────────────────────────────────
def test_fetch_writes_the_stored_generation_and_uses_get_only(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    _freeze(source)
    data = _exam_bytes(source)
    fake = FakeGcs()
    fake.objects['exam-old'] = (data, '1234')
    dest = tmp_path / 'dest'
    dest.mkdir()
    assert _run(_fetch_argv(dest), fake)[0] == ES.FETCHED
    assert _exam_bytes(dest) == data
    assert sorted(os.listdir(dest)) == ['exam-old.json']
    assert fake.kinds() == ['token', 'meta', 'media']
    assert fake.calls[2][2].endswith('/o/exam-old.json?alt=media&ifGenerationMatch=1234')
    assert {c[1] for c in fake.calls} == {'GET'}


def test_fetch_404_is_absent_and_writes_nothing(tmp_path):
    code, fake, _r = _run(_fetch_argv(tmp_path))
    assert code == ES.ABSENT
    assert os.listdir(tmp_path) == []
    assert fake.kinds() == ['token', 'meta']


@pytest.mark.parametrize('kind,answer', [
    ('meta', (403, {}, b'{}')), ('meta', (500, {}, b'{}')), ('meta', (401, {}, b'')),
    ('meta', (200, {}, b'not json')), ('meta', (200, {}, b'{"size": "3"}')),
    ('meta', (200, {}, json.dumps({'size': str(ES.MAX_EXAM_BYTES + 1), 'md5Hash': _md5(b''),
                                   'generation': '1'}).encode())),
    ('media', (200, {}, b'{"exam": "tampered"}')),
    ('media', (200, {}, b'{}')),
    ('media', (403, {}, b'')), ('media', (404, {}, b'')), ('media', (412, {}, b'')),
    ('media', ConnectionResetError()), ('meta', TimeoutError()),
    ('token', (500, {'metadata-flavor': 'Google'}, b'')),
    ('token', (200, {}, json.dumps({'access_token': CANARY}).encode())),
    ('token', (200, {'metadata-flavor': 'Google'}, b'{"access_token": "short"}')),
    ('token', (200, {'metadata-flavor': 'Google'}, json.dumps({'access_token': CANARY + '\r\nX: y'}).encode())),
])
def test_fetch_every_other_answer_is_fetch_failed_and_writes_nothing(tmp_path, kind, answer):
    fake = FakeGcs()
    fake.objects['exam-old'] = (b'{"exam": "exam-old", "pad": "abcd"}', '5')
    fake.script[kind] = [answer]
    assert _run(_fetch_argv(tmp_path), fake)[0] == ES.FETCH_FAILED
    assert os.listdir(tmp_path) == []
    if kind == 'token':
        assert fake.kinds() == ['token']
    assert 'upload' not in fake.kinds()


def test_fetch_never_replaces_a_local_exam_and_needs_a_folder(tmp_path):
    (tmp_path / 'exam-old.json').write_bytes(b'mine')
    code, fake, resolver = _run(_fetch_argv(tmp_path))
    assert (code, fake.calls, resolver.asked) == (ES.FETCH_FAILED, [], [])
    assert (tmp_path / 'exam-old.json').read_bytes() == b'mine'
    code, fake, resolver = _run(_fetch_argv(tmp_path / 'missing'))
    assert (code, fake.calls, resolver.asked) == (ES.FETCH_FAILED, [], [])


# ── The interface: two entry points, no third ─────────────────────────────────────────────────────
@pytest.mark.parametrize('argv', [
    [], ['auto'], ['both'], ['--bucket', BUCKET], ['fetch'], ['put'], ['fetch', '--help'], ['-h'],
    ['fetch', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', '/x', '--digest', 'a' * 12],
    ['fetch', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', '/x', '--size', '3'],
    ['fetch', '--buck', BUCKET, '--exam', 'exam-old', '--folder', '/x'],
    ['fetch', '--bucket', BUCKET, '--exam', 'exam-2', '--folder', '/x'],
    ['fetch', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', 'relative/x'],
    ['fetch', '--bucket', 'Bad.Bucket', '--exam', 'exam-old', '--folder', '/x'],
    ['fetch', '--bucket', 'b/../o', '--exam', 'exam-old', '--folder', '/x'],
    ['put', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', '/x'],
    ['put', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', '/x', '--digest', 'XYZ', '--size', '3',
     '--frozen-at', 't'],
    ['put', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', '/x', '--digest', 'a' * 12, '--size', '0',
     '--frozen-at', 't'],
])
def test_anything_but_fetch_or_put_with_their_own_arguments_is_refused_before_any_network(argv):
    code, fake, resolver = _run(argv)
    assert (code, fake.calls, resolver.asked) == (ES.REFUSED, [], [])


def test_the_mode_names_and_codes_are_fixed():
    assert (ES.FETCH, ES.PUT) == ('fetch', 'put')
    assert set(ES.FETCH_CODES) & {ES.KEPT, ES.FROZEN_ELSEWHERE, ES.PUT_FAILED} == set()
    assert ES.GOOD_CODES == {ES.FETCHED, ES.ABSENT, ES.KEPT, ES.FROZEN_ELSEWHERE}
    assert ES.result_line(ES.KEPT) == '{"code": "kept"}\n'
    assert ES.bucket_name_ok('halatuju-replay-exams') and not ES.bucket_name_ok('a.b.c')


# ── The environment ───────────────────────────────────────────────────────────────────────────────
def test_the_store_env_is_three_names_and_holds_no_key_salt_or_database():
    env = ES.store_env({'PATH': '/p', guards.DB_ENV: 'postgres://u:p@h/d', parent.FINGERPRINT_KEY_ENV: 'k',
                        scrub.SALT_ENV: 's', 'GOOGLE_APPLICATION_CREDENTIALS': '/c'}, '/harness')
    assert env == {'PATH': '/p', 'PYTHONPATH': '/harness', 'LANG': 'C.UTF-8'}
    assert tuple(sorted(env)) == tuple(sorted(ES.STORE_ENV_NAMES))
    assert guards.check_environment(env) is True
    assert ES.environment_ok(env)


@pytest.mark.parametrize('extra', [guards.DB_ENV, parent.FINGERPRINT_KEY_ENV, scrub.SALT_ENV,
                                   'GOOGLE_APPLICATION_CREDENTIALS', 'DJANGO_SETTINGS_MODULE', 'HOME'])
def test_any_other_name_in_the_environment_is_refused_before_any_network(tmp_path, extra):
    env = dict(ES.store_env({'PATH': '/p'}, '/h'), **{extra: 'x'})
    code, fake, resolver = _run(_fetch_argv(tmp_path), env=env)
    assert (code, fake.calls, resolver.asked) == (ES.REFUSED, [], [])


# ── The network: resolved once, before the guard; nothing else reachable ─────────────────────────
def test_names_are_resolved_once_before_the_guard_and_only_they_are_allowed(tmp_path, monkeypatch):
    events, real_guard = [], netguard.refuse_network
    resolver = Resolver()

    def spy_resolve(host, *a, **k):
        events.append(('resolve', host, socket.socket.connect))
        return resolver(host, *a, **k)

    def spy_guard(allow=()):
        events.append(('guard', frozenset(allow)))
        return real_guard(allow)

    monkeypatch.setattr(ES.netguard, 'refuse_network', spy_guard)
    fake = FakeGcs()
    refused = []

    def opener(addresses):
        events.append(('open', dict(addresses)))
        with socket.socket() as sock:
            try:
                sock.connect(('203.0.113.9', 443))
            except netguard.NetworkRefused:
                refused.append(True)
        return fake

    assert ES.run(_fetch_argv(tmp_path), env=ES.store_env({}, '/h'), getaddrinfo=spy_resolve,
                  opener=opener) == ES.ABSENT
    assert [e[0] for e in events] == ['resolve', 'resolve', 'guard', 'open']
    assert sorted(e[1] for e in events[:2]) == sorted(ES.HOSTS)
    assert events[2][1] == {(ADDRS[ES.METADATA_HOST], 80), (ADDRS[ES.STORAGE_HOST], 443)}
    assert events[3][1] == {ES.METADATA_HOST: (ADDRS[ES.METADATA_HOST], 80),
                            ES.STORAGE_HOST: (ADDRS[ES.STORAGE_HOST], 443)}
    assert refused == [True]                         # inside the guard, a third address is refused
    assert socket.socket.connect is events[0][2]    # and the guard is gone afterwards


def test_a_name_that_does_not_resolve_fails_with_no_call(tmp_path):
    code, fake, _r = _run(_fetch_argv(tmp_path), resolver=Resolver({ES.METADATA_HOST: '192.0.2.10'}))
    assert (code, fake.calls) == (ES.FETCH_FAILED, [])


def test_the_module_writes_no_address_and_never_turns_tls_checks_off():
    assert re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', SOURCE) is None
    for banned in ('CERT_NONE', 'check_hostname = False', '_create_unverified_context', 'verify_mode =',
                   'print(', 'import logging', 'urlopen', 'create_connection'):
        assert banned not in SOURCE, banned
    context = ES._tls_context()
    assert context.check_hostname is True and context.verify_mode == ES.ssl.CERT_REQUIRED


class FakeSocket:
    def __init__(self, answer):
        self.answer, self.sent, self.connected, self.timeout, self.closed = answer, b'', None, None, False

    def settimeout(self, value):
        self.timeout = value

    def connect(self, address):
        self.connected = address

    def sendall(self, data):
        self.sent += data

    def makefile(self, *_a, **_k):
        return io.BytesIO(self.answer)

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self):
        self.wrapped = []

    def wrap_socket(self, sock, server_hostname=None):
        self.wrapped.append(server_hostname)
        return sock


def test_pinned_http_connects_to_the_pinned_address_and_checks_tls_against_the_name(monkeypatch):
    context = FakeContext()
    monkeypatch.setattr(ES, '_tls_context', lambda: context)
    sockets = []

    def factory(family, kind):
        assert (family, kind) == (socket.AF_INET, socket.SOCK_STREAM)
        sockets.append(FakeSocket(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}'))
        return sockets[-1]

    addresses = {ES.METADATA_HOST: (ADDRS[ES.METADATA_HOST], 80), ES.STORAGE_HOST: (ADDRS[ES.STORAGE_HOST], 443)}
    http = ES.PinnedHttp(addresses, socket_factory=factory)
    status, _headers, body = http(ES.STORAGE_HOST, 'GET', '/storage/v1/b/x/o/y', {'Authorization': 'Bearer t'})
    assert (status, body) == (200, b'{}')
    assert context.wrapped == [ES.STORAGE_HOST]
    assert sockets[0].connected == (ADDRS[ES.STORAGE_HOST], 443) and sockets[0].timeout == ES.TIMEOUT_S
    head = sockets[0].sent.split(b'\r\n')
    assert head[0] == b'GET /storage/v1/b/x/o/y HTTP/1.1'
    assert b'Host: storage.googleapis.com' in head and b'Connection: close' in head
    http(ES.METADATA_HOST, 'GET', ES.TOKEN_PATH, {'Metadata-Flavor': 'Google'})
    assert context.wrapped == [ES.STORAGE_HOST]          # the metadata server is plain HTTP
    assert sockets[1].connected == (ADDRS[ES.METADATA_HOST], 80)
    assert b'Host: metadata.google.internal' in sockets[1].sent.split(b'\r\n')
    with pytest.raises(ES.StoreFailed):
        http('example.com', 'GET', '/', {})
    assert len(sockets) == 2


def test_the_resolver_asks_for_ipv4_tcp_once_per_name():
    asked = []

    def lookup(host, port, family, kind, proto):
        asked.append((host, port, family, kind, proto))
        return [(family, kind, proto, '', (ADDRS[host], port))]

    assert ES.resolve_hosts(lookup) == {h: (ADDRS[h], p) for h, (p, _tls) in ES.HOSTS.items()}
    assert sorted(asked) == sorted((h, p, socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
                                   for h, (p, _tls) in ES.HOSTS.items())


# ── No token anywhere ─────────────────────────────────────────────────────────────────────────────
def _leak_scenarios(tmp_path):
    exam_dir = tmp_path / 'put'
    exam_dir.mkdir()
    exam = _freeze(exam_dir)
    echo = json.dumps({'error': {'message': 'Bearer ' + CANARY}}).encode()
    yield _fetch_argv(tmp_path / 'f1'), {'meta': [(403, {}, echo)]}
    yield _fetch_argv(tmp_path / 'f2'), {'token': [(200, {'metadata-flavor': 'Google'},
                                                    b'{"access_token": "' + CANARY.encode() + b'", ')]}
    yield _fetch_argv(tmp_path / 'f3'), {'token': [(200, {'metadata-flavor': 'Google'}, json.dumps(
        {'access_token': CANARY + '\n'}).encode())]}
    yield _fetch_argv(tmp_path / 'f4'), {'media': [ValueError(CANARY)]}
    yield _put_argv(exam_dir, exam), {'upload': [(500, {}, echo), (500, {}, echo)]}
    yield _put_argv(exam_dir, exam), {'upload': [(403, {}, echo)]}


def test_no_token_reaches_any_output(tmp_path, capfd, caplog):
    caplog.set_level('DEBUG')
    for name in ('f1', 'f2', 'f3', 'f4'):
        (tmp_path / name).mkdir()
    for argv, script in _leak_scenarios(tmp_path):
        fake = FakeGcs()
        if argv[0] == 'fetch':
            fake.objects['exam-old'] = (b'{"x": 1}', '2')
        fake.script = script
        code = _run(argv, fake)[0]
        assert code in ES.FETCH_CODES + ES.PUT_CODES and CANARY not in code
    out, err = capfd.readouterr()
    assert CANARY not in out + err and out == '' and err == ''
    assert CANARY not in caplog.text


def _all_text(exc):
    return ' '.join([str(exc), repr(exc), repr(exc.args), ''.join(traceback.format_exception(exc))])


@pytest.mark.parametrize('answer', [
    (200, {'metadata-flavor': 'Google'}, b'{"access_token": "' + CANARY.encode() + b'"'),
    (200, {'metadata-flavor': 'Google'}, json.dumps({'access_token': CANARY + ' \r\n'}).encode()),
    (200, {'metadata-flavor': 'Google'}, json.dumps([CANARY]).encode()),
    (200, {}, json.dumps({'access_token': CANARY}).encode()),
    (500, {'metadata-flavor': 'Google'}, CANARY.encode()),
])
def test_a_refused_token_answer_raises_with_no_token_and_no_chain(answer):
    with pytest.raises(ES.StoreFailed) as caught:
        ES.metadata_token(lambda *a, **k: answer)
    exc = caught.value
    assert exc.__context__ is None and exc.__cause__ is None
    assert CANARY not in _all_text(exc)


def test_a_refused_storage_answer_raises_with_no_token_and_the_token_object_hides_it():
    token = ES._Token(CANARY)
    assert CANARY not in repr(token) + str(token) + repr([token])
    echo = json.dumps({'error': 'Bearer ' + CANARY}).encode()
    for answer in ((403, {}, echo), (200, {}, echo), (200, {}, echo[:-3])):
        with pytest.raises(ES.StoreFailed) as caught:
            ES.object_meta(lambda *a, **k: answer, token, BUCKET, 'exam-old')
        assert caught.value.__context__ is None and CANARY not in _all_text(caught.value)


# ── Run as a module: one line, nothing else ───────────────────────────────────────────────────────
def _module(argv, env_extra=None, cwd=None):
    env = dict(ES.store_env(os.environ, str(EVAL_DIR)), **(env_extra or {}))
    return subprocess.run([sys.executable, '-m', 'replay.exam_store', *argv], env=env, cwd=cwd,
                          capture_output=True, timeout=60)


@pytest.mark.parametrize('argv,extra,code', [
    ([], None, 'refused'),
    (['fetch', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', 'rel'], None, 'refused'),
    (['fetch', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', '/x'], {parent.FINGERPRINT_KEY_ENV: 'k'},
     'refused'),
    (['fetch', '--help'], None, 'refused'),
])
def test_as_a_module_it_prints_one_line_and_nothing_on_stderr(tmp_path, argv, extra, code):
    done = _module(argv, extra, cwd=tmp_path)
    assert done.stdout == f'{{"code": "{code}"}}\n'.encode()
    assert done.stderr == b''
    assert done.returncode == 1


def test_as_a_module_an_unproved_put_is_not_verified_with_no_network(tmp_path):
    done = _module(['put', '--bucket', BUCKET, '--exam', 'exam-old', '--folder', str(tmp_path), '--digest',
                    'a' * 12, '--size', '3', '--frozen-at', '2026-11-25T09:00:00.000000+00:00'], cwd=tmp_path)
    assert (done.stdout, done.stderr, done.returncode) == (b'{"code": "not_verified"}\n', b'', 1)
