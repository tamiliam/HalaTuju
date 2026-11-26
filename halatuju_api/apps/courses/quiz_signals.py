"""A saved interest quiz is never wiped by an empty one (request #81, 27 Nov 2026).

⚠ THE WIPE THIS STOPS. The web caches the server's `student_signals` in the browser on every
profile load, and the sign-in sync sends that cache back up. A profile with no quiz yet is `{}`,
and `{}` is truthy in JavaScript, so a browser that signed in BEFORE the quiz cached `"{}"`. The
STPM quiz then saved its answers to the server but cached them under its OWN key, leaving `"{}"`
in place; the next sign-in on that browser sent `student_signals: {}` and the server stored it.
The scholarship completeness gate reads `bool(profile.student_signals)`, so a submitted case
(case 513) read "quiz not done" and Approve could no longer send it to QC.

The rule lives here, read by `ProfileUpdateSerializer.validate_student_signals`, which is the one
door for both `PUT /profile/` and `POST /profile/sync/`. The quiz endpoints save through
`views.quiz._persist_quiz_signals`, which never stores an empty set either, so a deliberate
retake (which always carries answers) still replaces the old one.
"""


def has_answers(signals):
    """True when ``signals`` holds at least one answered signal: `{}`, `None`, or a set whose every
    category is empty is NO answers (the quiz engines build every category, then fill some)."""
    return isinstance(signals, dict) and any(bool(v) for v in signals.values())


def keep_saved(saved, incoming):
    """What to store for ``incoming``: the ``saved`` set when ``incoming`` carries no answers and
    ``saved`` does, otherwise ``incoming``. A set WITH answers always wins (a retake, another
    device's newer quiz), so only an empty write over a real one is refused, silently."""
    if not has_answers(incoming) and has_answers(saved):
        return saved
    return incoming
