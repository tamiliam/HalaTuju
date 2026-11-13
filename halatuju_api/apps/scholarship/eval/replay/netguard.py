"""The socket guard (design 3.2): no outgoing connection from Python except to the database host.

`socket.socket.connect` / `connect_ex` are replaced for the length of the block; a client library that
speaks HTTP from PYTHON sockets (requests, httpx, urllib, the google-auth call to the metadata server)
goes through them, so such a reach for Gemini, Storage, Brevo or Vircle raises `NetworkRefused`.

NOT covered: anything that opens its socket in C. gRPC clients (the Vision client can use gRPC) and the
database driver (libpq) do. What stops a gRPC reach is that the job holds no key and its service account
has no role but reading its one secret (owner steps), plus `guards.shut_doors`, which makes the Vision
entry points raise. ``allow`` lists the database host's addresses so a pure-Python driver would still work.
"""
import contextlib
import socket


class NetworkRefused(BaseException):
    """An outgoing connection to anything but the database. A BaseException: no `except Exception` hides it."""


def db_addresses(host, port):
    """Every (ip, port) ``host`` resolves to, for the allow list. Resolved once, before the guard is up."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError:
        return set()
    return {(info[4][0], port) for info in infos}


def _address_key(address):
    if isinstance(address, tuple) and len(address) >= 2:
        return (str(address[0]), address[1])
    return address


@contextlib.contextmanager
def refuse_network(allow=()):
    """Refuse every Python-level outgoing connection whose (ip, port) is not in ``allow``."""
    allowed = {_address_key(a) for a in allow}
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def _check(address):
        if _address_key(address) not in allowed:
            raise NetworkRefused('replay: an outgoing connection was refused')

    def connect(self, address):
        _check(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        _check(address)
        return real_connect_ex(self, address)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex = real_connect, real_connect_ex
