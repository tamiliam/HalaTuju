"""Supporting-document genuineness (STR / birth cert / EPF) — moved here from vision.py
(behaviour unchanged).

The same idea as the IC, generalised to the OTHER standardised documents — but the "what
counts as official" rule is doc-type-specific (validated on our real files):
  * STR — a genuine MySTR app SCREENSHOT (Semakan Status / Dashboard) IS legitimate evidence
    (the owner's call; it's the preferred, harder-to-fake source). Only a typed or fabricated
    version is suspect. The existing STR currency/source-type logic still decides whether it's
    an APPROVAL — genuineness here is mainly WRONG-TYPE.
  * results slip / birth cert / EPF statement — a typed sheet / screenshot of text / printout
    is NOT official; we expect a photo or scan of the real document.
Wrong-type (e.g. an IC uploaded as an STR, a KWSP withdrawal form instead of a statement) →
status 'wrong_type'. Soft throughout; the reviewer is the authority.

(NOTE: results_slip genuineness is moving to the probabilistic signature scorer in
``genuineness.results_doc``; this module keeps str / birth_certificate / epf.)

The Gemini seam is reached via ``vision._call_gemini_json`` (imported lazily inside the function
so the module-level import isn't circular and the test patch target stays valid).
"""
_GENUINENESS_DOCS = {
    'str': {'screenshot_ok': True,
            'desc': 'a Malaysian STR (Sumbangan Tunai Rahmah) cash-aid document — a MySTR app '
                    'screenshot (Semakan Status / Dashboard) OR an official Kementerian Kewangan letter'},
    # TD-139: results_slip dropped — it's scored by the probabilistic SIGNATURE scorer in the
    # upload path (its branch wins first), so the holistic membership was dead. (BC/EPF are kept
    # here for the holistic doc_genuineness API even though their live path is now signatures too.)
    'birth_certificate': {'screenshot_ok': False,
                          'desc': "a Malaysian birth certificate (Sijil Kelahiran) from Jabatan "
                                  "Pendaftaran Negara (JPN), with a registration number, the child "
                                  "and both parents' details and an official seal"},
    'epf': {'screenshot_ok': False,
            'desc': 'a Malaysian EPF/KWSP MEMBER STATEMENT (Penyata Ahli KWSP) — KWSP letterhead, a '
                    'member number and a contribution/savings table (NOT a withdrawal/application form)'},
}
_DOC_GENUINENESS_SCHEMA = {'type': 'object', 'properties': {
    'is_official': {'type': 'boolean'}, 'is_expected_type': {'type': 'boolean'},
    'doc_seen': {'type': 'string'}, 'verdict': {'type': 'string'}, 'reason': {'type': 'string'}},
    'required': ['is_official', 'is_expected_type', 'doc_seen', 'verdict', 'reason']}
# Gemini verdict word → the CANONICAL outcome. 'wrong_type' becomes 'not_<doc_type>' (filled below).
_DOC_GENUINENESS_STATUS = {'genuine': 'genuine', 'suspect': 'suspect', 'wrong_type': 'not_type'}


def doc_genuineness(data: bytes, content_type: str, doc_type: str) -> dict:
    """Soft genuineness fingerprint for a standardised supporting document →
    ``{status, doc_seen, reason}`` or ``{}``. ``status`` ∈ canonical ``genuine`` /
    ``suspect`` / ``not_<doc_type>``. NEVER raises; an AI outage / unsupported type
    returns ``{}`` (no signal). The reviewer is the authority."""
    from apps.scholarship import vision   # lazy: avoids a circular import; keeps the patch seam
    cfg = _GENUINENESS_DOCS.get(doc_type)
    if not cfg:
        return {}
    img, mime = vision._as_image_for_gemini(data, content_type)
    if img is None:
        return {}
    ss = ('A genuine SCREENSHOT of the official MySTR app/portal IS acceptable as official — only a '
          'typed or fabricated text version is not. ' if cfg['screenshot_ok'] else
          'A typed sheet, a screenshot of typed text, or a hand-written/printed copy is NOT official. ')
    prompt = (f"This image was uploaded as {cfg['desc']}. {ss}Decide: is_official — is it a genuine "
              "official document of that kind (proper letterhead/format/seal/structure of the issuing "
              "authority)? is_expected_type — is it ACTUALLY that kind of document, or a DIFFERENT "
              "document (e.g. an identity card / MyKad, a payslip, the wrong form)? doc_seen — what the "
              "document actually appears to be (short). verdict — 'genuine' (a real official document of "
              "the expected type), 'suspect' (the right type but typed/printed/fabricated, not an official "
              "copy), or 'wrong_type' (a different document than expected). reason — one sentence.")
    r = vision._call_gemini_json(prompt, _DOC_GENUINENESS_SCHEMA, image=img, mime_type=mime)
    if not isinstance(r, dict) or r.get('_error'):
        return {}
    status = _DOC_GENUINENESS_STATUS.get((r.get('verdict') or '').strip().lower(), '')
    if status == 'not_type':                       # wrong document → not_<type> (e.g. not_str)
        status = 'not_' + doc_type
    return {
        'status': status,
        'doc_seen': (r.get('doc_seen') or '')[:80],
        'reason': (r.get('reason') or '')[:300],
    }
