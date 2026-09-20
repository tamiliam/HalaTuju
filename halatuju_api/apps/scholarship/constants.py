"""The platform numbers `apps.courses` reads — the back-edge's one door (code health H16).

**Why this module exists.** `apps/courses/org_config.py` is the registry of tunable settings, and
for six of them the platform default is not a Django setting but a module constant that lives in
`apps.scholarship`. Reading those six meant `courses` importing `scholarship.services`,
`scholarship.check2_queries` and `scholarship.scheduling` — three behaviour-bearing modules, one
of them an eighteen-module package, fetched to read an integer. Every one of those imports had to
be lazy, and the comment beside each said why: importing at module load would be circular.

**This module has no imports of its own and never will.** That is the whole design: it is a leaf,
so nothing it is imported from can be circular, and `courses` reaches for six numbers instead of
for three engines.

⚠ NOTHING WAS RENAMED AND NO VALUE CHANGED (Phase 4 is moves only). Each constant is the same
name and the same number it was, with the comment it carried; its old home now imports it from
here and re-exports it, so `check2_queries.MAX_CLARIFY` and `scheduling.SLOT_STEP_MIN` still
answer exactly as they did and every existing reader is untouched.

⚠ THESE ARE PLATFORM DEFAULTS, NOT THE RULE. The rule is
`org_config.value(organisation, '<key>')`, which delegates here for an organisation that has
tuned nothing. Never read one of these names directly in a code path that serves an
organisation.
"""

# How long after submission to hold the "we have a few questions" email, so it reads as
# a human review rather than an instant bot reply (the owner's call). PLATFORM default —
# an organisation can tune its own delay via org_config `query_email_delay_hours`
# (Organisation → Settings → Configuration; Org Config Sprint B), whose registry default
# reads THIS constant, so this stays the one home for the platform number.
QUERY_EMAIL_DELAY_HOURS = 2

# The student is not the reviewer: a long list suppresses responses. Cap to the few
# most material (design §4). PLATFORM default — an organisation can tune its own cap via
# org_config `max_clarify_open` (Org Config Sprint B), whose registry default reads THIS
# constant; read the live cap through `max_clarify(application)`, never this name directly.
MAX_CLARIFY = 3

# ⚠ THESE FOUR CONSTANTS ARE THE PLATFORM DEFAULT, NOT THE RULE (Org Config Sprint D). The
# rule is `org_config.value(organisation, 'interview_window_start_min')` and friends, which
# DELEGATE here for an organisation that has tuned nothing. The browser no longer keeps a
# lock-step copy: `interview_schedule_payload` SERVES the resolved four to the picker, so
# there is nothing left to keep in step.
SLOT_WINDOW_START_MIN = 8 * 60        # 08:00
SLOT_WINDOW_END_MIN = 21 * 60 + 30    # 21:30 (latest start)
SLOT_STEP_MIN = 30
# Minimum scheduling notice: the earliest proposable slot is this far ahead, so the student
# has time to see + pick + prepare.
SLOT_MIN_LEAD_HOURS = 24
