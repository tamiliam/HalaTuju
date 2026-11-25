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
import threading
import traceback
import urllib.parse

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
    """The metadata server and one bucket, named ``bucket`` (any other bucket answers 404, as Cloud
    Storage does). ``script[kind]`` (token / meta / list / media / upload) is a list used first: an
    exception is raised, a tuple is the answer, a callable gets the default answer (side effects
    already applied) and returns the answer. ``calls`` holds (host, method, path, kind, headers, body)."""

    def __init__(self, token=CANARY, bucket=BUCKET):
        self.token, self.bucket, self.objects, self.script, self.calls = token, bucket, {}, {}, []
        self._generation = 1700000000000000

    def _kind(self, host, method, path):
        if host == ES.METADATA_HOST:
            return 'token'
        if method == 'POST':
            return 'upload'
        if 'alt=media' in path:
            return 'media'
        return 'list' if '/o?' in path else 'meta'

    def __call__(self, host, method, path, headers, body=None, limit=ES.MAX_META_BYTES):
        kind = self._kind(host, method, path)
        self.calls.append((host, method, path, kind, dict(headers), body))
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
        if path.split('/b/', 1)[1].split('/', 1)[0] != self.bucket:
            return 404, {}, b'{"error": {"code": 404}}'
        if kind == 'list':
            prefix = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)['prefix'][0]
            items = [{'name': f'{n}.json'} for n in sorted(self.objects) if f'{n}.json'.startswith(prefix)]
            return 200, {}, json.dumps({'items': items[:1]} if items else {}).encode()
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
    create_only = f'/upload/storage/v1/b/{BUCKET}/o?uploadType=media&name=exam-old.json&ifGenerationMatch=0'
    assert [c[2] for c in fake.calls if c[1] == 'POST'] == [create_only, create_only]   # the retry too
    fake = FakeGcs()
    fake.script['upload'] = [(429, {}, b'')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.KEPT
    assert fake.kinds().count('upload') == 2
    assert [c[2] for c in fake.calls if c[1] == 'POST'] == [create_only, create_only]


def test_a_lost_answer_then_412_with_our_bytes_is_kept(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.objects['exam-old'] = (_exam_bytes(tmp_path), '9')     # the first POST landed; its answer was lost
    fake.script['upload'] = [ConnectionResetError()]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.KEPT
    assert fake.kinds() == ['token', 'upload', 'upload', 'meta']
    assert all(c[2].endswith('&ifGenerationMatch=0') for c in fake.calls if c[1] == 'POST')


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
    assert fake.kinds() == ['token', 'upload', 'meta']       # a 404 on a put never asks about the bucket


def test_put_an_accepted_answer_then_a_404_on_the_metadata_fails_with_no_list(tmp_path):
    exam = _freeze(tmp_path)
    fake = FakeGcs()
    fake.script['upload'] = [lambda answer: (200, {}, b'{"kind": "storage#object"}')]
    fake.script['meta'] = [(404, {}, b'')]
    assert _run(_put_argv(tmp_path, exam), fake)[0] == ES.PUT_FAILED
    assert fake.kinds() == ['token', 'upload', 'meta']


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


def test_put_refuses_an_exam_file_over_the_cap_before_any_network(tmp_path, monkeypatch):
    exam = _freeze(tmp_path)
    size = len(_exam_bytes(tmp_path))
    monkeypatch.setattr(ES, 'MAX_EXAM_BYTES', size - 1)
    code, fake, resolver = _run(_put_argv(tmp_path, exam))
    assert (code, fake.calls, resolver.asked) == (ES.NOT_VERIFIED, [], [])
    with pytest.raises(ES.StoreFailed) as caught:
        ES.prove_new_exam(str(tmp_path), 'exam-old', exam['digest'][:12], exam['size'], exam['frozen_at'])
    assert caught.value.code == ES.NOT_VERIFIED
    monkeypatch.setattr(ES, 'MAX_EXAM_BYTES', size)              # at the cap itself it is taken
    assert _run(_put_argv(tmp_path, exam))[0] == ES.KEPT


def test_put_refuses_a_folder_at_the_exam_path_with_no_network(tmp_path):
    exam = _freeze(tmp_path)
    source = tmp_path / 'source'
    source.mkdir()
    (tmp_path / 'exam-old.json').rename(source / 'exam-old.json')
    (tmp_path / 'exam-old.json').mkdir()
    code, fake, resolver = _run(_put_argv(tmp_path, exam))
    assert (code, fake.calls, resolver.asked) == (ES.NOT_VERIFIED, [], [])


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='no FIFOs on this system')
def test_put_refuses_a_fifo_at_the_exam_path_without_waiting_for_a_writer(tmp_path):
    exam = _freeze(tmp_path)
    path = tmp_path / 'exam-old.json'
    path.unlink()
    os.mkfifo(path)
    done = []
    worker = threading.Thread(target=lambda: done.append(_run(_put_argv(tmp_path, exam))), daemon=True)
    worker.start()
    worker.join(10)
    if worker.is_alive():                                       # release the blocked open, then fail
        os.close(os.open(path, os.O_WRONLY | os.O_NONBLOCK))
        worker.join(10)
        pytest.fail('the store child waited on a FIFO')
    code, fake, resolver = done[0]
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


def test_fetch_404_in_a_bucket_proved_there_is_absent_and_writes_nothing(tmp_path):
    code, fake, _r = _run(_fetch_argv(tmp_path))
    assert code == ES.ABSENT
    assert os.listdir(tmp_path) == []
    assert fake.kinds() == ['token', 'meta', 'list']


def test_fetch_from_a_bucket_that_is_not_there_is_fetch_failed_not_absent(tmp_path):
    fake = FakeGcs(bucket='another-bucket')     # a mistyped, not yet made or deleted bucket: 404 on both
    code, fake, _r = _run(_fetch_argv(tmp_path), fake)
    assert code == ES.FETCH_FAILED
    assert fake.kinds() == ['token', 'meta', 'list']
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize('answer', [
    (404, {}, b'{"error": {"code": 404}}'), (403, {}, b'{}'), (401, {}, b''), (500, {}, b'{}'),
    (503, {}, b''), (200, {}, b'not json'), (200, {}, b'[]'), (200, {}, b'"items"'), (200, {}, b''),
    (200, {}, b'{"items": []}' + b' ' * ES.MAX_META_BYTES),
    ConnectionResetError(), TimeoutError(),
])
def test_fetch_404_then_any_list_answer_but_a_json_object_is_fetch_failed(tmp_path, answer):
    fake = FakeGcs()
    fake.script['list'] = [answer]
    assert _run(_fetch_argv(tmp_path), fake)[0] == ES.FETCH_FAILED
    assert fake.kinds() == ['token', 'meta', 'list']
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize('body', [b'{}', b'{"items": [{"name": "exam-old.json"}]}',
                                  b'{"items": [{"name": "exam-older.json"}]}'])
def test_fetch_404_then_a_list_answer_of_200_is_absent_with_no_second_try(tmp_path, body):
    fake = FakeGcs()
    fake.script['list'] = [(200, {}, body)]     # even when the list names the object (a race): no loop
    assert _run(_fetch_argv(tmp_path), fake)[0] == ES.ABSENT
    assert fake.kinds() == ['token', 'meta', 'list']
    assert os.listdir(tmp_path) == []


def test_the_list_request_is_a_get_to_storage_with_the_token_only_in_its_header(tmp_path):
    fake = FakeGcs()
    assert _run(_fetch_argv(tmp_path), fake)[0] == ES.ABSENT
    host, method, path, kind, headers, body = fake.calls[2]
    assert (host, method, kind, headers, body) == (
        ES.STORAGE_HOST, 'GET', 'list', {'Authorization': 'Bearer ' + CANARY}, None)
    split = urllib.parse.urlsplit(path)
    assert split.path == f'/storage/v1/b/{BUCKET}/o' and CANARY not in path
    assert urllib.parse.parse_qs(split.query, strict_parsing=True) == {
        'prefix': ['exam-old.json'], 'maxResults': ['1'], 'fields': ['items(name)']}
    assert path == ES.list_path(BUCKET, 'exam-old')


def test_the_list_path_encodes_the_name_as_strictly_as_the_other_paths():
    assert ES.list_path(BUCKET, 'exam-old') == (
        f'/storage/v1/b/{BUCKET}/o?prefix=exam-old.json&maxResults=1&fields=items%28name%29')
    odd = ES.list_path(BUCKET, 'a b/&?#=')
    assert odd.startswith(f'/storage/v1/b/{BUCKET}/o?prefix=a%20b%2F%26%3F%23%3D.json&maxResults=1&')
    assert ES.object_path(BUCKET, 'a b/&?#=').endswith('/o/a%20b%2F%26%3F%23%3D.json')


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
    yield _fetch_argv(tmp_path / 'f5'), {'meta': [(404, {}, b'')], 'list': [(403, {}, echo)]}
    yield _fetch_argv(tmp_path / 'f6'), {'meta': [(404, {}, b'')], 'list': [ValueError(CANARY)]}
    yield _put_argv(exam_dir, exam), {'upload': [(500, {}, echo), (500, {}, echo)]}
    yield _put_argv(exam_dir, exam), {'upload': [(403, {}, echo)]}


def test_no_token_reaches_any_output(tmp_path, capfd, caplog):
    caplog.set_level('DEBUG')
    for name in ('f1', 'f2', 'f3', 'f4', 'f5', 'f6'):
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


@pytest.mark.parametrize('list_answer', [
    (403, {}, json.dumps({'error': {'message': 'Bearer ' + CANARY}}).encode()),
    (404, {}, CANARY.encode()), ValueError(CANARY), ConnectionResetError(CANARY)])
def test_a_failed_list_call_while_the_token_is_held_gives_only_the_fixed_line(tmp_path, capfd, caplog,
                                                                             list_answer):
    caplog.set_level('DEBUG')
    fake = FakeGcs()
    fake.script = {'meta': [(404, {}, b'')], 'list': [list_answer]}
    code = _run(_fetch_argv(tmp_path), fake)[0]
    assert fake.kinds() == ['token', 'meta', 'list']
    assert fake.calls[2][4] == {'Authorization': 'Bearer ' + CANARY}      # the token was held and sent
    assert code == ES.FETCH_FAILED
    assert ES.result_line(code) == '{"code": "fetch_failed"}\n'
    out, err = capfd.readouterr()
    assert (out, err) == ('', '') and CANARY not in caplog.text
    assert os.listdir(tmp_path) == []


def test_a_refused_list_answer_carries_no_token():
    token = ES._Token(CANARY)
    echo = json.dumps({'error': 'Bearer ' + CANARY}).encode()
    for answer in ((403, {}, echo), (404, {}, echo), (200, {}, echo[:-3])):
        assert ES.bucket_reachable(lambda *a, **k: answer, token, BUCKET, 'exam-old') is False


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
