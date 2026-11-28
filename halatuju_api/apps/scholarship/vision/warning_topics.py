"""Topic-coded warnings (case 1048, owner 2026-11-28): the salary-slip read tags each free-text warning.

The salary-slip read (`gemini_read.extract_document_fields`) writes its free-text ``warnings`` in new words on
every Re-run, so a word list could never reliably say which ones only make sense on a real payslip. The read
now also returns ``warning_topics``: one code per warning, in the same order, from ``TOPICS`` below (the
schema's enum, `schemas._FIELD_SCHEMAS['salary_slip']`). The display (`income_engine.declaration_name.
shown_warnings`) hides the payslip-only topics on a document seen as a declaration, by CODE.

Display only: no verdict, chip, genuineness, score or money reads a topic (a guard test pins the modules that
may name them). The schema, the prompt, the clean-up and the display all import from here, so the lists
cannot drift apart.
"""

#: The key the topics are stored under, beside ``warnings`` on the read (``vision_fields``).
KEY = 'warning_topics'

#: The notes that only make sense on a real payslip: a declaration has none of these by design.
PAYSLIP_ONLY_TOPICS = frozenset({
    'employer_missing', 'pay_period_missing', 'take_home_missing', 'gross_missing', 'not_a_payslip',
})
#: The notes every document keeps.
KEPT_TOPICS = frozenset({
    'altered', 'name_or_ic_mismatch', 'unreadable', 'signature_or_stamp_missing', 'other',
})
#: Every code, in a fixed order (the schema's enum).
TOPICS = (
    'employer_missing', 'pay_period_missing', 'take_home_missing', 'gross_missing', 'not_a_payslip',
    'altered', 'name_or_ic_mismatch', 'unreadable', 'signature_or_stamp_missing', 'other',
)

#: The prompt line (salary slip only), added after the slip's own hint.
PROMPT_LINE = (' For EACH warning, also give its topic in "warning_topics", in the SAME order (one topic per '
               'warning); use "other" when none fits.')


def valid_topics(warnings, topics) -> bool:
    """True only when ``topics`` is a list of the SAME length as ``warnings`` (a list) and every code is
    in ``TOPICS``. Anything else (missing, wrong length, an unknown code, a non-list) is False: the
    display then falls back to the word filter for the WHOLE list."""
    if not isinstance(warnings, list) or not isinstance(topics, list) or len(topics) != len(warnings):
        return False
    return all(isinstance(t, str) and t in TOPICS for t in topics)


def keep_aligned(warnings, topics, kept_indexes):
    """``(warnings, topics)`` cut to ``kept_indexes`` together, so each warning keeps its own topic. Topics
    that were not valid on arrival are returned as they came while no warning is dropped (the display falls
    back on them); once one is dropped they become None (missing), since a cut list could line up by
    accident (3 warnings, 2 topics, one warning dropped) and pass as valid."""
    kept = [warnings[i] for i in kept_indexes]
    if valid_topics(warnings, topics):
        return kept, [topics[i] for i in kept_indexes]
    return kept, (topics if len(kept) == len(warnings) else None)
