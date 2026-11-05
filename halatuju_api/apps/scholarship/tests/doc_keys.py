"""The storage key a test records a document under (audit SEC-01).

The document POST accepts only the key the sign-upload step issues for THIS application and doc
type: ``build_doc_key(app, app.id, doc_type)`` + ``/`` + 32 lowercase hex. A test that records a
document through the API names it with ``issued_key``; the hex tail is derived from ``tag`` so the
test can name the same key again in an assertion.
"""
import hashlib

from apps.scholarship.storage import build_doc_key


def issued_key(app, doc_type, tag=''):
    """The key the upload step would have issued for ``app`` + ``doc_type``, tail derived from ``tag``."""
    return build_doc_key(app, app.id, doc_type, hashlib.sha256(str(tag).encode()).hexdigest()[:32])
