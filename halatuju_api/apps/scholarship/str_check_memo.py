"""TD-308 (2026-10-04): ONE reading of the household's STR for the length of ONE Check-2 gap pass.

``check2_queries._gap_sets`` asks a dozen income helpers their question, and two or three of them
(``str_owner_ic_asks``, ``has_valid_str`` behind the declared-wage ask and the high-utility
wording) each took ``income_engine.student_str_check`` of the SAME STR — one IC lookup per
household member every time, about seven queries a reading, on every sync: the student's Action
Centre read, ``confirm_profile`` and the hourly query-email sweep. Nothing counted it.

``one_str_reading`` wraps ``_gap_sets``: inside it, ``student_str_check`` answers a document it has
already read from this memo. Outside it, nothing changes — ``student_str_check`` reads as before.

⚠ WHY THIS IS SAFE, AND WHERE IT WOULD NOT BE. The memo lives for one call of a function whose
docstring promises it is side-effect free: no document, IC or application field is written between
the first reading and the last, so a second reading could only repeat the first. Never widen it
around code that WRITES a document or an application field and then reads the STR back — it would
answer from before the write. (The same rule as ``document_snapshot``; this is the narrow tool for
the one write path the snapshot may not enter.)

It is a ``ContextVar``, never a module global, so two requests on two threads never share a reading,
and it is reset from its token in a ``finally``. Each answer is a deep copy, so a caller that edits
its reading cannot edit the next caller's.
"""
import contextvars
import copy
import functools

_MEMO = contextvars.ContextVar('str_check_memo', default=None)


def one_str_reading(fn):
    """Decorator: ``student_str_check`` reads each STR at most once while ``fn`` runs."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _MEMO.set({})
        try:
            return fn(*args, **kwargs)
        finally:
            _MEMO.reset(token)
    return wrapper


def remembered(doc, compute):
    """``compute(doc)``, taken once per saved document while a memo is open; else every time."""
    memo, pk = _MEMO.get(), getattr(doc, 'pk', None)
    if memo is None or pk is None:
        return compute(doc)
    key = (type(doc), pk)
    if key not in memo:
        memo[key] = compute(doc)
    return copy.deepcopy(memo[key])
