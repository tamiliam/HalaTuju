"""Document promotion decision — owner 2026-07-09: **stage → judge → promote-only-if-better**.

A KEY NAMED document uploaded via the Action Centre is STAGED (created not-live), read + judged, and
only PROMOTED into the live/prime slot when it is USABLE **and** at least as good as the doc already
there. Otherwise it stays staged (filed under Old / Replaced) and the existing proof keeps its slot —
so a worse or wrong re-upload can never bury a good live document. This generalises the former
STR-only keep-better guard to every key doc type.

PURE by design: every function operates on the doc objects it is handed and NEVER queries
``.documents`` — so this module carries no superseded-read obligation and stays out of
``tests.test_superseded_documents.TestStaticReadGuard``. ``resolution``, ``income_engine`` and
``pathway_engine`` are imported lazily inside the functions to avoid the
``resolution → income_engine`` import cycle. The per-type quality signals it reads
(``offer_official_status`` / ``offer_reporting_bonus`` / ``_dedup_clean_rank`` / ``student_str_check``)
are all themselves pure doc-local reads.
"""

# Phase 3 — per-type quality (owner 2026-07-09). The generic proxy below is sharpened for the doc
# types where "which copy is better" has a decisive, already-computed axis:
#   * offer_letter — OFFICIALNESS. An offer is the one KEY NAMED type with NO downstream dedup
#     safety net (it is not in ``income_engine._DEDUP_DOC_TYPES``, so ``dedupe_income_proof`` never
#     re-collapses live offers to the best). So this promote decision is the ONLY keep-better for
#     offers, and a genuine OFFICIAL public offer must outrank a conditional / private / pemakluman
#     one that happens to be uploaded later — otherwise the newer-id tiebreak would bury the good
#     offer. `unknown` (not scored yet) sits between the two so a fresh unscored offer still replaces
#     a known-bad one but never buries a confirmed-official live offer. NON-signature: it reads the
#     already-stored ``authenticity`` (computed on the forced upload extraction), so NO
#     ``MODEL_VERSION`` bump and no re-run needed.
# str / salary_slip / epf / water_bill / electricity_bill already keep the best live copy via
# ``dedupe_income_proof`` AFTER promotion, so the generic proxy is sufficient for them here.
_OFFER_OFFICIAL_RANK = {'genuine': 2, 'unknown': 1, 'not_genuine': 0}

# results_slip / semester_result are ALSO un-deduped (not in `_DEDUP_DOC_TYPES`), so promotion is
# their only keep-better. Phase 2's usable-gate already keeps a live slip when a re-upload is
# unreadable (its name / subject table / CGPA didn't read → `doc_match_verdict` unreadable/pending →
# not usable). This axis handles the NARROWER case the gate misses: TWO both-usable slips where one
# captured MORE of the document — so a fuller live slip isn't silently displaced by a thinner (e.g.
# cropped) but still-usable re-upload on the id tiebreak. NON-signature (field counts), so no
# MODEL_VERSION bump. Caveat to watch in practice: a noisy OCR read could inflate the subject count,
# so this is a soft tiebreak within usable+genuine, never a gate — the officer still overrides.


def _slip_completeness(doc):
    """Field-completeness for a results/semester slip (HIGHER = more of the document captured).
    Sits in the recency slot of the generic proxy (slips have no billing date). Pure — reads the
    stored extraction only (``read_slip`` / ``semester_check`` never query ``.documents``)."""
    dt = getattr(doc, 'doc_type', '')
    if dt == 'results_slip':
        from .academic_engine import read_slip
        s = read_slip(doc)
        return (len(s.get('names') or []), len(s.get('grades') or {}))   # subjects read, then graded
    if dt == 'semester_result':
        from .academic_engine import semester_check
        c = semester_check(doc) or {}
        return (sum(1 for k in ('name', 'nric', 'cgpa') if (c.get(k) or '').strip()),)  # of 3 core fields
    return (0,)


def _offer_quality(doc):
    """Quality axis for an offer letter (HIGHER better): officialness first, then a validated
    reporting summons, then the latest upload. Pure — reads stored ``authenticity``/fields only."""
    from .pathway_engine import offer_official_status, offer_reporting_bonus
    official = _OFFER_OFFICIAL_RANK.get(offer_official_status(doc), 1)
    bonus = 1 if offer_reporting_bonus(doc) else 0
    return (official, bonus, getattr(doc, 'id', 0) or 0)


def doc_quality(doc):
    """A comparable quality for a KEY NAMED doc — HIGHER is better; ``None`` means 'news, always
    replace' (mirrors ``income_engine.str_proof_quality`` returning None for a rejected STR).
    Quality is only ever compared WITHIN one ``doc_type``, so the heterogeneous tuple shapes below
    never meet.
      * STR → the currency/source ladder (``str_proof_quality``).
      * offer_letter → ``(usable, official_rank, reporting_bonus, id)`` — a genuine OFFICIAL offer
        beats a conditional/private/pemakluman one (``_offer_quality``); see the note above.
      * results_slip / semester_result → ``(usable, genuine, completeness, id)`` — a fuller slip
        (more subjects/grades, or more of name/nric/cgpa) beats a thinner but equally usable+genuine
        one (``_slip_completeness``); see the note above.
      * every other type → a proxy ``(usable, genuine, recency, id)``: a readable + correct +
        right-person doc (``doc_match_verdict == 'ok'``) beats an unreadable/wrong one; a genuine
        beats a suspect (``_doc_genuine_rank``); a newer dated income/utility doc breaks the tie
        (``_income_doc_recency``); else the latest upload (``id``, monotonic → newer). Every element
        is an int / int-tuple, so the comparison is always well-defined.
    ``usable`` leads every proxy so a usable new doc always beats a not-usable live one (and vice
    versa) before any type-specific axis is consulted."""
    from . import income_engine
    from .resolution import doc_match_verdict
    dt = getattr(doc, 'doc_type', '')
    if dt == 'str':
        return income_engine.str_proof_quality(doc)
    usable = 1 if doc_match_verdict(doc) == 'ok' else 0
    if dt == 'offer_letter':
        return (usable,) + _offer_quality(doc)
    genuine = income_engine._doc_genuine_rank(doc)
    if dt in ('results_slip', 'semester_result'):
        return (usable, genuine, _slip_completeness(doc), getattr(doc, 'id', 0) or 0)
    recency = income_engine._income_doc_recency(doc) or (0, 0)
    return (usable, genuine, recency, getattr(doc, 'id', 0) or 0)


def _offer_programme(doc):
    """The programme named on an offer letter, normalised for comparison (blank when unread)."""
    vf = getattr(doc, 'vision_fields', None)
    fields = vf.get('fields') if isinstance(vf, dict) else None
    raw = (fields or {}).get('programme') if isinstance(fields, dict) else ''
    return ' '.join((raw or '').strip().lower().split())


def is_pathway_switch(new_doc, existing_doc):
    """Do these two offer letters describe DIFFERENT programmes — i.e. the student switched?

    The discriminator is the PROGRAMME, deliberately not the institution. Both real cases prove
    why: #13 (a genuine switch) reads "FTV - ASASI TEKNOLOGI KEJURUTERAAN" against "DSPD - DIPLOMA
    SAINS KOMPUTER" — clearly different. #107 (a re-scan of ONE letter) extracted the institution
    as "INSTITUT PENDIDIKAN GURU MALAYSIA" on one pass and "INSTITUT PENDIDIKAN GURU KAMPUS KOTA
    BHARU" on the other — the letterhead body vs the campus, from the same document — so comparing
    institutions would have called that a switch. Its programme string is identical on both passes.

    Returns False unless BOTH programmes read: an unread programme is not evidence of a switch, and
    defaulting to False keeps the ordinary quality comparison in charge.
    """
    if getattr(new_doc, 'doc_type', '') != 'offer_letter':
        return False
    new_prog, old_prog = _offer_programme(new_doc), _offer_programme(existing_doc)
    return bool(new_prog and old_prog and new_prog != old_prog)


def should_promote(new_doc, existing_doc, *, usable):
    """Should ``new_doc`` take the live slot from ``existing_doc``?
      * empty slot → promote.
      * ``doc_quality(new) is None`` (NEWS — e.g. a genuine Ditolak STR) → promote, checked BEFORE
        ``usable`` (a rejected STR reads not-usable via ``doc_match_verdict``, yet a real negative
        status must still replace — load-bearing; see ``test_recognised_new_doc_still_replaces``).
      * not usable → keep the existing live doc (the new one stays staged; the circuit-breaker owns
        the escalation after repeated tries).
      * ``doc_quality(existing) is None`` → promote (the live doc is itself 'news' / rejected).
      * else promote iff ``quality(new) >= quality(existing)`` (equal ties promote — the fresher copy).
    """
    if existing_doc is None:
        return True
    qn = doc_quality(new_doc)
    if qn is None:
        return True
    if not usable:
        return False
    qe = doc_quality(existing_doc)
    if qe is None:
        return True
    # A PATHWAY SWITCH is news, not a better copy of the same news (owner 2026-07-23). The
    # quality bar below assumes both documents describe the SAME fact — true for a re-scan of one
    # offer, false when the student has changed course. #13 switched from Asasi Teknologi
    # (Politeknik Nilai) to Diploma Sains Komputer and the new letter READ WORSE (its institution
    # extracted as bare "KUALA LUMPUR"); it promoted only because it still cleared the bar. Had it
    # not, the old letter would have kept the live slot and every downstream verdict would have
    # described a course the student had left. `usable` above still applies — an unreadable upload
    # can never displace a good one; this bypasses the COMPARISON, not the floor.
    if is_pathway_switch(new_doc, existing_doc):
        return True
    return qn >= qe
