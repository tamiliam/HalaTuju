"""Document promotion decision — owner 2026-07-09: **stage → judge → promote-only-if-better**.

A KEY NAMED document uploaded via the Action Centre is STAGED (created not-live), read + judged, and
only PROMOTED into the live/prime slot when it is USABLE **and** at least as good as the doc already
there. Otherwise it stays staged (filed under Old / Replaced) and the existing proof keeps its slot —
so a worse or wrong re-upload can never bury a good live document. This generalises the former
STR-only keep-better guard to every key doc type.

PURE by design: every function operates on the doc objects it is handed and NEVER queries
``.documents`` — so this module carries no superseded-read obligation and stays out of
``tests.test_superseded_documents.TestStaticReadGuard``. ``resolution`` and ``income_engine`` are
imported lazily inside the functions to avoid the ``resolution → income_engine`` import cycle.
"""


def doc_quality(doc):
    """A comparable quality for a KEY NAMED doc — HIGHER is better; ``None`` means 'news, always
    replace' (mirrors ``income_engine.str_proof_quality`` returning None for a rejected STR).
    Quality is only ever compared WITHIN one ``doc_type``, so the heterogeneous tuple shapes below
    never meet.
      * STR → the currency/source ladder (``str_proof_quality``).
      * every other type → a proxy ``(usable, genuine, recency, id)``: a readable + correct +
        right-person doc (``doc_match_verdict == 'ok'``) beats an unreadable/wrong one; a genuine
        beats a suspect (``_doc_genuine_rank``); a newer dated income/utility doc breaks the tie
        (``_income_doc_recency``); else the latest upload (``id``, monotonic → newer). Every element
        is an int / int-tuple, so the comparison is always well-defined.
    """
    from . import income_engine
    from .resolution import doc_match_verdict
    if getattr(doc, 'doc_type', '') == 'str':
        return income_engine.str_proof_quality(doc)
    usable = 1 if doc_match_verdict(doc) == 'ok' else 0
    genuine = income_engine._doc_genuine_rank(doc)
    recency = income_engine._income_doc_recency(doc) or (0, 0)
    return (usable, genuine, recency, getattr(doc, 'id', 0) or 0)


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
    return qn >= qe
