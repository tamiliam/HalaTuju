"""The prompt TEXT of the AI sponsor profile: the shared style, privacy, coverage, assistance and
time rules, the draft (PROFILE_PROMPT) and final (REFINE_PROMPT) templates, and the two income
notes the final profile carries.

Moved verbatim out of `profile_engine.py` (audit sprint A3.6, a moves-only split: the file was a
ledgered 1043-line oversize file). `profile_engine.py` re-exports every name, so each
`from apps.scholarship.profile_engine import ...` is unchanged. Nothing here changed.

⚠ `PROMPT_VERSION` stays in `profile_engine.py`: BUMP it there on any meaningful change to the
text below (and ask the owner first - a bump re-drafts every assigned unedited profile through
the paid daily backfill).
"""

# Shared narrative + privacy instructions (the same single profile for reviewer + sponsor).
_STYLE = (
    "Write warm, factual, flowing prose: about three short paragraphs, roughly 220-320 "
    "words, with NO section headings and NO bullet lists. Tell the story so a reader "
    "understands, in turn: the family's situation and why the assistance is genuinely "
    "needed; the student's academic standing and the commitment and resilience behind it; "
    "and the pathway ahead, including the confirmed place, when the student is due to report, "
    "and how ready and committed they are to take it up. Refer to the student as 'he' or 'she' "
    "using the pronouns given "
    "below; NEVER use 'they' for the student (most people write he/she). Use em-dashes very "
    "sparingly, at most one in the whole profile; prefer commas, full stops or brackets. Let "
    "the facts carry the case: do NOT use fundraising clichés such as 'breaking the cycle', "
    "'ripple effect' or 'pioneering spirit', and do NOT invent specifics (an age, a "
    "relationship, a figure) not given below. Where a fact is missing, leave it out rather "
    "than guess. "
    "Do NOT state any monetary amount or recommended sum — that figure is shown separately to "
    "the reader; instead describe concretely and factually what the support would help the "
    "student with. Do NOT advocate or editorialise (no 'strongly recommended', 'a deserving "
    "candidate', 'we urge you to support'); the reader reviews many profiles, so let the facts "
    "speak for themselves."
)

_REDACTION = (
    "PRIVACY — this single profile is read by the reviewer AND, once the student is "
    "approved, by external sponsors, so it must never expose contact or identity details. "
    "Refer to the student ONLY by the alias \"{alias}\"; never invent or include a name. For "
    "the student AND any parent or guardian, NEVER include their name, NRIC/IC number, "
    "photograph, phone number, email address, or street address — if any appears in the "
    "inputs below, omit it. Everything else may be used: the school or college name, the "
    "town and state, the institution, and occupations. "
    "ETHNICITY — do NOT reveal or imply the student's ethnicity, race or religion, even when "
    "the student's own words do. KEEP the meaning but GENERALISE any ethnic/cultural specific: "
    "write \"her mother tongue\" or \"her community's language and culture\" rather than naming "
    "a language (e.g. Tamil, Mandarin/Chinese), and \"a teacher who inspired her\" rather than "
    "\"her Tamil teacher\". Never name a vernacular-language or literature subject. A culturally "
    "specific aspiration (e.g. to teach her mother tongue) is kept as a motivation, just "
    "without the ethnic label."
)

# The sponsor's three "need to know" areas — the same buckets gap_engine tags interview gaps
# with. The profile must answer all three; the refine groups interview findings under these so
# each lands in the matching part of the narrative. Output stays prose (no headings/lists) — this
# is a COVERAGE instruction, not a layout one.
_BUCKET_LABELS = {
    'financial_need': 'Financial need',
    'academic_resilience': 'Academic commitment & resilience',
    'pathway_confidence': 'Pathway & enrolment confidence',
    'other': 'Other points raised',
}
_BUCKET_ORDER = ['financial_need', 'academic_resilience', 'pathway_confidence', 'other']

_COVERAGE = (
    "WHAT A SPONSOR NEEDS TO KNOW — this profile must answer, across its flowing paragraphs "
    "(still NO headings and NO lists), the three things a sponsor weighs. Give EACH its due and "
    "weave it into the story rather than labelling it:\n"
    "1. FINANCIAL NEED — the family's circumstances and why the assistance genuinely matters: who "
    "earns and who does not, the reported and any documented household income, the dependants, and "
    "the specific costs the support would meet.\n"
    "2. ACADEMIC COMMITMENT & RESILIENCE — how the student has performed and persevered: the "
    "results, the effort and obstacles behind them, and the drive they show.\n"
    "3. PATHWAY & ENROLMENT CONFIDENCE — that the next step is clear and within reach: the "
    "programme and institution, whether a place is held, the reporting date if known, and how ready "
    "and committed the student is to take it up.\n"
    "Where the inputs leave one area thin, state honestly what IS known and do not invent — but do "
    "not silently drop a whole area the sponsor is counting on."
)

# Owner 2026-07-08 (#110) — the profile must not imply our assistance buys a laptop / covers fees.
_ASSISTANCE_NATURE = (
    "WHAT THE ASSISTANCE IS — the support is a MODEST, FIXED monthly living-cost bursary (a small "
    "top-up toward the student's living costs), NOT a fund that buys equipment or pays fees, and its "
    "amount is fixed. You MAY describe the student's needs and circumstances (for example that they "
    "lack a laptop, or face accommodation and transport costs) as CONTEXT for why support matters. "
    "But NEVER state or imply that the assistance will BUY, SECURE, or PAY FOR a laptop or any other "
    "item, or COVER fees or the full cost of study — do not write that the support 'enables her to "
    "secure a laptop' or 'is needed for a laptop'. Frame the support as easing / contributing toward "
    "the student's living costs, never as funding a specific purchase in full."
)

# Owner 2026-07-21 — the profile must not go STALE as months pass (a sponsor may read it long after
# it was written). Gemini has no innate sense of "now" — it read mid-2026 as the future and wrote a
# live countdown + wrong relative timing ("is due to report on 12 July 2026"; "applications open only
# after her course begins"). So (a) we give it TODAY'S date to fix tense/ordering, and (b) require
# evergreen phrasing. Templated on {today}.
_EVERGREEN = (
    "TIME & DATES — write so this profile does NOT age; a sponsor may read it months after it was "
    "written. Today's date is {today}; use it ONLY to keep your tenses and any before/after reasoning "
    "correct — never quote it, and never say how long until or since something happens. State a "
    "confirmed reporting or intake date as a plain fact of WHEN the place begins (for example 'with a "
    "confirmed place beginning in July 2026'), NOT as a live countdown ('is due to report on 12 July "
    "2026') and NOT as still-upcoming or already-past. Do NOT reason about the timing of one event "
    "relative to another (avoid 'applications open only after her course begins') — state each plainly "
    "(for example 'plans to apply for a PTPTN loan once applications open'). Do NOT anchor the reader "
    "to 'this year' or 'next month'. Prefer evergreen, tenseless phrasing that stays true whenever it "
    "is read."
)


PROFILE_PROMPT = """You are writing the profile of a B40 student applying for education \
financial assistance in Malaysia. It is read first by the reviewer assessing the application, \
and later by a prospective sponsor.

{redaction}

LANGUAGE — the student's own words below may be in Malay, English, or Tamil (or a mix); \
understand their meaning whichever language they are in, and write the profile in {target_language}.

{style}

{evergreen}

{coverage}

{assistance_nature}

VERIFICATION — do not over-claim:
- Some fields are marked "{do_not_claim}" — NOT verified. Do not assert them; omit them.
- ACADEMICS — give a brief SUMMARY only, never a list. State the number of A-grade subjects, the \
band mix, and the broad subject GROUPS they span exactly as provided below (e.g. "ten A-grade \
subjects across A+/A/A−, spanning the sciences, mathematics and languages"). Do NOT enumerate \
individual subjects or per-subject grades — a reader skips a long list. NEVER name a specific \
language or literature subject (e.g. Bahasa Tamil, Bahasa Cina, Kesusasteraan Tamil/Cina), and do \
NOT state or imply the student's ethnicity or race. Never round up or imply a uniform top grade. If \
a merit score is given, you may cite it.
- INCOME & WELFARE — DOCUMENTED is certain; everything self-reported is a CLAIM. If "Documented \
income (payslip/EPF)" below lists one or more figures, you MUST state them AUTHORITATIVELY as the \
documented income, naming the document and whose income it is — do NOT omit a documented figure or \
bury it behind the softer reported household figure. EVERY other income figure — including the \
household income below — is only what the family REPORTS: present it as such (e.g. "the family \
reports about RM…") and you MAY give it as context alongside the documented figure (e.g. base pay \
vs a month with overtime), but never as "confirmed", and do NOT attribute a reported figure to a \
specific earner or invent a breakdown. STR/JKM are gated the SAME way: a value of "yes" means a welfare DOCUMENT is on file, so \
you MAY state the family receives it (this confirms B40 status, NOT an income figure). Any other \
value ("no" or "not established — do not claim") means there is NO proof on file — do NOT mention \
STR/JKM at all and do NOT use it to affirm B40 status. If who earns what is unclear, describe the \
situation (a single earner, a parent unable to work) without inventing numbers. Do not make up a \
story to reconcile the figures.

THE STUDENT (alias {alias})
Pronouns (use these for the student, never "they"): {pronouns}
School / college: {school}
Qualification: {qualification}    Merit score (out of 100): {merit}
SPM grades: {grades_summary}    STPM PNGK: {stpm_pngk}
Home town / state: {region}
Household income (RM/month, as reported): {household_income}    Household size: {household_size}
Documented income (payslip/EPF — use authoritatively if present): {income_evidence}
Receives STR ('yes' only when a current STR document is on file; else do not claim): {receives_str}    Receives JKM (same rule): {receives_jkm}
First in family to university: {first_in_family}
Parents'/guardians' occupation: {parents_occupation}
Siblings currently studying: {siblings_studying}

Pathway / programme (use the confirmed place when present): {pathway}
Reporting / enrolment date (WHEN the place begins — if given, state it as a plain fact per the TIME & DATES rule, never as a countdown): {reporting_date}
Top course choices (student's ranking): {top_choices}
While still deciding (student's words): {deliberation}
Other scholarships applied for / held: {other_scholarships}
Help the student asked us for: {help_wanted}
Interest-quiz signals (the student's strongest interests + work style): {quiz_interests}

Aspirations (student's words): {aspirations}
Plan to get there (student's words): {plans}
Why assistance is needed (student's words): {justification}
Worries / concerns (student's words): {fears}
Family situation (student's words): {family_context}
Daily life & responsibilities (student's words): {daily_life}
Anything else the student wants us to know (student's words): {anything_else}
Statement of Intent letter (student's uploaded letter, OCR'd — distil its substance): {statement_of_intent}

Funding — what the support would help with: {funding_categories}
Anything else about funding (student's words): {funding_note}

The student's answers to our clarifying questions:
{qa}

Draw on ALL of the student's own words above and distil them into the narrative where they add \
meaning — their aspirations, plan, reasons, worries, deliberation and anything-else. Do not ignore \
a field the student took the trouble to fill in; equally, do not pad with a field left blank \
("not provided"/"none"/"not applicable" means say nothing about it).

The interest-quiz signals are ACCRETIVE ONLY: use them to add positive colour about the student's \
interests and strengths (e.g. how their pathway plays to what energises them). NEVER use the quiz to \
question, doubt, cast as a mismatch, or otherwise weaken the student's chosen pathway or case. If the \
quiz does not obviously add something supportive, simply leave it out.
"""


REFINE_PROMPT = """You are writing the FINAL profile of a B40 student applying for education \
financial assistance in Malaysia — the conclusive version a sponsor will read.

You are given (1) a DRAFT written from the application, (2) the student's answers to our \
clarifying questions, (3) the officer's interview findings, and (4) the officer's decision. \
Produce ONE coherent final profile that folds them all together.

{redaction}

LANGUAGE — the inputs may be in Malay, English, or Tamil (or a mix); understand their meaning \
and write the profile in {target_language}.

{style}

{evergreen}

{coverage}

{assistance_nature}

Pronouns (use these for the student, never "they"): {pronouns}

Rules:
- INCOME: documented = certain, self-reported = a claim. When the draft or the officer's findings
state a DOCUMENTED income (payslip/EPF), keep it and state it as documented — do not soften it into a
mere report. State any OTHER income figure as confirmed ONLY if the officer's verdict verified it;
otherwise present it as what the family reports, and never invent who earns what. Do NOT assert the
family receives STR/JKM unless the DRAFT or the officer's findings establish it from a document —
never re-introduce a welfare claim the draft omitted.
- Fold in what the student's answers and the interview CONFIRMED or CLARIFIED; reflect any NEW \
CONCERN honestly and proportionately — do not hide it, do not exaggerate it. The interview findings \
below are grouped under the three sponsor areas (financial need / academic commitment & resilience / \
pathway & enrolment confidence) — weave each finding into the matching part of the narrative.
- The officer's decision is the considered outcome of a real review. Present each area with \
confidence matching the four-fact verdict; weave the officer's written conclusion into the close. \
Do NOT state any monetary amount or recommended sum — that figure is shown separately to the sponsor; \
instead describe concretely what the support would help the student with. Do NOT advocate or use \
recommendation language ("strongly recommended", "a deserving candidate"). Do NOT print a raw \
pass/fail list and never contradict the verdict.
- If the draft states a reporting / enrolment date, keep it in the pathway part — but as a plain \
fact of when the place begins, per the TIME & DATES rule (never a live countdown or relative timing).
- Use ONLY the inputs below; do not invent facts. It must read as one final profile, not a draft \
with notes bolted on.

{income_context}

=== DRAFT PROFILE ===
{draft}

=== THE STUDENT'S ANSWERS TO OUR QUESTIONS ===
{qa}

=== OFFICER'S INTERVIEW FINDINGS ===
{findings}
Interviewer's rubric scores (1-5): {rubric}
Interviewer's overall note: {overall_note}

=== OFFICER'S DECISION ===
{officer_decision}
"""


# When the deterministic verdict flags household income ABOVE the B40 line yet the officer has
# recommended the student anyway, the FINAL profile must not read cut-and-dry: it should
# acknowledge the income honestly and foreground the EXTENUATING CIRCUMSTANCES that make the case
# exceptional — grounded ONLY in the officer's written conclusion + the student's own account,
# never invented (owner decision 2026-07-08). The QC's own note is deliberately NOT relied upon
# here: a QC often simply endorses the reviewer's view without adding detail.
_BELOW_LINE_AFFIRM = (
    "NOTE ON INCOME — this household has been VERIFIED as B40-eligible under the programme's means "
    "test; its income is WITHIN the B40 range. Do NOT claim or imply the income is ABOVE the B40 "
    "threshold, do NOT call the case borderline or exceptional on income grounds, and do NOT invent a "
    "threshold comparison (you are not given the cut-off figure). Present the reported / documented "
    "income plainly as a B40 household's income."
)

_ABOVE_LINE_EMPHASIS = (
    "NOTE ON INCOME — this household's income reads ABOVE the usual B40 line, yet the officer has "
    "recommended the student. Do NOT present this as a clean-cut B40 case and do NOT hide or "
    "contradict the income. Acknowledge it honestly, then FOREGROUND the extenuating circumstances "
    "that make the case exceptional — drawing ONLY on the officer's conclusion and the student's own "
    "account below (e.g. a large household, a single or irregular earner, medical or caregiving "
    "costs, recent loss of income, debt). Explain, grounded in those inputs, why the support still "
    "matters here. Invent nothing: if the inputs give no such circumstances, state the position "
    "plainly without embellishment."
)
