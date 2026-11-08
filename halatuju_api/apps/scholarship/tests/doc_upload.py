"""Upload a document the way the web does (A2.3, TD-519).

Since A2.3 an upload whose type has a paid read answers at once with ``reading: true``, and the web
then asks for the read (``documents/<id>/read/``). ``post_doc`` does both, so a test that is about
what an upload DECIDES reads the decision, exactly as the student sees it. The returned response is
the read's, carrying the upload's own status code (201), so the upload's status assertions still
hold. A refused upload (4xx) or a type with no read is returned as it came.

Tests about the queue itself (no inline read, the claim, the cron) post directly instead — see
``test_upload_read.py``.
"""
DOCS = '/api/v1/scholarship/documents/'


def post_doc(client, data, **kwargs):
    kwargs.setdefault('format', 'json')
    resp = client.post(DOCS, data, **kwargs)
    if resp.status_code == 201 and resp.json().get('reading'):
        read = client.post(f"{DOCS}{resp.json()['id']}/read/", format='json')
        assert read.status_code == 200, read.content
        read.status_code = resp.status_code
        return read
    return resp
