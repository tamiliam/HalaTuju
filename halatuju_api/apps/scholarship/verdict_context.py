"""WHAT FED EACH DECISION (LL4): a PII-free record of the inputs, built when the reviewer records a verdict.

The decision row already says what the engine answered (`ai_verdict_snapshot`) and which engine
answered (`ai_verdict_engine_version`). It did not say WHAT EVIDENCE the engine was looking at, so a
later replay could not tell "same evidence, new engine" from "the evidence moved". This record
closes that gap. It holds, for one application at decision time:

* ``documents``: EVERY live document (one query), not only the ones a fact cited, because some
  engine helpers run their own queries and a "used" list would miss them. Per document: its id,
  type, household role, upload time, read state, officer verification, the stored genuineness
  status and every stored scorer / reader / parser version.
* ``models``: the version every model in the LL3 register (`model_registry.MODELS`) runs at now.
* ``fingerprint``: one keyed hash (HMAC-SHA256) over the documents (the fields above PLUS the stored
  read itself: `vision_fields` and the OCR columns) and the short fixed list `DECLARED_FIELDS` of
  what the student declared that the engine reads (plus the one fact the engine derives from the
  results notes: `moved_to_higher_ids`), `PROFILE_FIELDS`, the fields of her profile
  the engine reads (name, NRIC, results), `INTAKE_FIELDS`, the intake-year rules the engine reads
  (year, income ceilings), and the stage facts the engine derives from `STAGE_FIELDS` (submission
  year, status buckets: `stage_facts`). VALUES ENTER THE HASH ONLY, never the record.
* ``key_check``: 8 hex characters of the same keyed hash over a fixed constant. Two records with
  different ``key_check`` were hashed under different keys: their fingerprints cannot be compared,
  which is a key rotation, NOT evidence that moved.
* ``schema``: the shape of this record (`RECORD_SCHEMA`), so later readers can tell shapes apart.

THE KEY is derived from Django's ``SECRET_KEY`` with a fixed salt (`salted_hmac`): no new setting.
The fingerprint reads canonical JSON (sorted keys, ASCII, instants in UTC), so it is the same for
the same evidence in any process, on any machine, under any time zone or Python version, as long
as the key is the same.

PII RULE: the record holds ids, codes, versions, instants and hashes only. Names, NRIC, income
figures, addresses, contact details, free text, file names and storage paths never enter it. A
stored code that is not a plain code (`_CODE`, `_VERSION_TEXT`) is written as `NOT_A_CODE`, so a
malformed or free-text value cannot leak through a status or version slot.

`build_verdict_context` may raise. `verdict_context_or_empty` never does: it is what the decision
path calls, because a record that cannot be built must never stop a decision being saved.
"""
import datetime
import decimal
import importlib
import json
import logging
import re
import uuid

from django.utils.crypto import salted_hmac

from .genuineness.bands import stored_authenticity, stored_status
from .model_registry import MODELS
from .start_year import rule_on, stored_years

logger = logging.getLogger(__name__)

#: The shape of the record. Raise it (and the allow-list test) whenever a key is added or removed.
RECORD_SCHEMA = 1

#: The declared application fields the verdict engine reads that decide a fact, hashed into the
#: fingerprint (values only, never the record). Kept short on purpose: each one moves a verdict.
DECLARED_FIELDS = (
    'income_route',            # STR route or salary route (`_verdict_income`)
    'income_earner',           # whose income the documents must prove (`_verdict_income`, caps)
    'income_working_members',  # which family members' income documents are required
    'income_declared',         # the declared income figures (informal route, evidence gates)
    'income_nonearning',       # members declared not earning (occupation gaps)
    'other_family_members',    # the household the income documents are linked to
    'father_name',             # links an earner's documents to the student (identity checks)
    'mother_name',             # the same, for the mother
    'father_occupation',       # occupation decides which income proof is asked for
    'mother_occupation',
    'chosen_pathway',          # the offer letter is reconciled against these (`_verdict_pathway`)
    'intended_pathway',
    'chosen_programme',
    'pathway_confirmed_at',    # the student confirmed a different offer as final
    'requirements_snapshot',   # which documents this application is asked for (`requirements`)
    'reporting_date',          # course-start year fallback (`pathway_engine.course_start_year`)
)

#: The application's results notes column. Its raw value (dated free-form notes, some with the
#: team's text) is NOT hashed, only the one fact the engine derives from it (`moved_to_higher_ids`),
#: under the declared key `MOVED_TO_HIGHER`. Kept here so a renamed column fails the column test.
NOTES_FIELD = 'results_change_notes'
MOVED_TO_HIGHER = 'moved_to_higher_documents'

#: The application's STAGE columns the engine reads. Their raw values are NOT hashed, only the facts
#: the engine derives from them (`stage_facts`), so the fingerprint moves when, and only when, one of
#: those facts moves. `status` changes through the normal workflow after the decision (to
#: 'interviewed' on verify-accept or submit-decline), and a resubmission re-stamps
#: `profile_completed_at`; hashing either raw would move the fingerprint where the engine sees no
#: change. Kept here so a renamed column fails the column test.
STAGE_FIELDS = ('profile_completed_at', 'status')

#: The fields of the application's INTAKE (`ScholarshipCohort`) the verdict engine reads, hashed with
#: the `cohort_id` (values only, never the record). An admin who changes a ceiling after the decision
#: moves the fingerprint. Fields only other surfaces read (name, dates, the QC's birth-state floor)
#: are left out on purpose.
INTAKE_FIELDS = (
    'year',                 # the STR year of an unstamped row (`str_this_year`); exam and offer years
    'income_ceiling',       # the means test (`income_engine.amounts`)
    'per_capita_ceiling',
    'min_stpm_pngk',        # does the intake ask for higher results (`results_route.gift_asks_higher`)
    'allowed_start_years',  # the course-start years the intake accepts (`start_year`)
)

#: The fields of the student's PROFILE (`courses.StudentProfile`) the verdict engine reads, hashed
#: into the fingerprint the same way (values only, never the record). Without them a changed NRIC or
#: changed grades after the decision would replay as "same evidence". Read off the engine's own
#: profile reads (identity, academic, pathway, income helpers); fields only other surfaces read
#: (contact details, address, school, interview inputs) are left out on purpose.
PROFILE_FIELDS = (
    'name',                      # identity: profile name vs the IC read; the parent-name link
    'nric',                      # identity: profile NRIC vs the IC read (the hard key)
    'exam_type',                 # results route: which results she is heading for (`results_held`)
    'results_exam_type',         # results route: the recorded completion wins
    'completed_qualifications',  # results route: the highest completed qualification
    'grades',                    # academic: SPM grades compared with the slip (`spm_grades_for`)
    'spm_prereq_grades',         # academic: a tertiary holder's SPM block, compared instead
    'stpm_grades',               # academic: STPM results compared with the higher results
    'stpm_cgpa',
    'stpm_koko',
    'higher_cgpa',               # academic: third-route CGPA compared with the transcript
    'higher_koko',
    'higher_institution_type',   # academic: which tertiary results page she holds
    'stream_subjects',           # pathway: the PISMP aliran hint (`infer_pismp_aliran`)
    'household_size',            # income: per-capita figures and the household-size check
)

#: One document row of the query: the columns the record shows and the read the hash takes in.
_DOC_COLUMNS = ('id', 'doc_type', 'household_member', 'results_kind', 'uploaded_at',
                'verification_status', 'read_state', 'vision_fields', 'vision_fields_run_at',
                'vision_run_at', 'vision_error', 'vision_nric', 'vision_name', 'vision_address',
                'vision_name_match', 'vision_address_match')
#: Of those, the ones that carry the stored read (may hold PII): they enter the hash only.
_HASH_ONLY = ('vision_fields', 'vision_fields_run_at', 'vision_run_at', 'vision_error',
              'vision_nric', 'vision_name', 'vision_address', 'vision_name_match',
              'vision_address_match')

#: The keys of each document in the record, in a fixed order (the allow-list test pins this set).
DOCUMENT_KEYS = ('id', 'doc_type', 'member', 'results_kind', 'uploaded_at', 'verification',
                 'read_state', 'genuineness', 'model_version', 'parser_version',
                 'offer_reader_version', 'sample_check_version')
#: The keys of a built record, and of the record the safe wrapper returns instead.
RECORD_KEYS = ('schema', 'documents', 'models', 'fingerprint', 'key_check')
FAILED_KEYS = ('schema', 'error')

#: What a value that is not a plain code is written as.
NOT_A_CODE = '?'
#: Reason codes of the safe wrapper.
NO_APPLICATION = 'no_application'
BUILD_FAILED = 'build_failed'

_KEY_SALT = 'halatuju.scholarship.verdict_context.evidence_fingerprint'
_KEY_CHECK_MESSAGE = 'verdict_context key check'
#: A plain code. It lets one word of up to 40 characters through, so it is a backstop, not the
#: protection: every slot it guards is filled from a fixed choice list or written by the engine.
_CODE = re.compile(r'[A-Za-z0-9_-]{1,40}')
#: A version: an optional lower-case reader name and one space, then a number (`spm_slip 1.1.0`).
#: It must hold a digit right after the optional name, so a person's name cannot pass for one.
_VERSION_TEXT = re.compile(r'(?:[a-z_]{1,30} )?v?[0-9][0-9A-Za-z.+_-]{0,30}')


# --- plain values -------------------------------------------------------------------------------

def _context_code(value):
    """A status / type / role code as stored, `''` when absent, `NOT_A_CODE` when it is not one."""
    if value is None or value == '':
        return ''
    return value if isinstance(value, str) and _CODE.fullmatch(value) else NOT_A_CODE


def _context_version(value):
    """A stored version string, `''` when absent, `NOT_A_CODE` when it is not shaped like one."""
    if value is None or value == '':
        return ''
    return value if isinstance(value, str) and _VERSION_TEXT.fullmatch(value) else NOT_A_CODE


def _context_instant(value):
    """An instant as fixed-width UTC text. A naive value (never stored with USE_TZ on) is written
    as it is, marked with no zone, rather than read in the process's own time zone."""
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.strftime('%Y-%m-%dT%H:%M:%S.%f')
        return value.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    if isinstance(value, datetime.date):
        return value.isoformat()
    raise TypeError('not an instant')


def _json_default(value):
    """The canonical JSON of the few non-JSON values a row can hold. Anything else raises."""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return _context_instant(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f'{type(value).__name__} has no canonical form in the evidence fingerprint')


def canonical_json(value):
    """Sorted keys, ASCII only, no spaces: the same text for the same value everywhere."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'),
                      allow_nan=False, default=_json_default)


# --- the parts ----------------------------------------------------------------------------------

def _keyed_hash(message):
    return salted_hmac(_KEY_SALT, message, algorithm='sha256').hexdigest()


def key_check():
    """8 hex characters that change when the key (``SECRET_KEY``) changes, and only then."""
    return _keyed_hash(_KEY_CHECK_MESSAGE)[:8]


def current_model_versions():
    """`{model key: version}` for every model in the LL3 register, read from the running code."""
    versions = {}
    for key, spec in MODELS.items():
        rel, name = spec['constant']
        module = importlib.import_module(rel[:-len('.py')].replace('/', '.'))
        versions[key] = _context_version(getattr(module, name))
    return versions


def _document_entry(row):
    """The record's view of one document row: codes, versions and instants only."""
    vf = row['vision_fields'] if isinstance(row['vision_fields'], dict) else {}
    auth = stored_authenticity(vf)
    return {
        'id': int(row['id']),
        'doc_type': _context_code(row['doc_type']),
        'member': _context_code(row['household_member']),
        'results_kind': _context_code(row['results_kind']),
        'uploaded_at': _context_instant(row['uploaded_at']),
        'verification': _context_code(row['verification_status']),
        'read_state': _context_code(row['read_state']),
        'genuineness': _context_code(stored_status(vf)),
        'model_version': _context_version(auth.get('model_version')),
        'parser_version': _context_version(vf.get('parser_version')),
        'offer_reader_version': _context_version(vf.get('offer_reader_version')),
        'sample_check_version': _context_version(
            vf.get('sample_check_version') or auth.get('sample_check_version')),
    }


def moved_to_higher_ids(notes):
    """The ids of the documents a `refiled_higher` note names, in order: the only thing the engine
    reads from the notes (`wrong_slip._moved_here`: a note of that kind whose `document_id` equals
    the document's id). Every other note, and every other key of a note (its time, its text, who
    wrote it), is ignored by the engine and so does not count here. An id the engine's `==` would
    never match to a document id (text, a fraction) is dropped, as it never matches there."""
    ids = set()
    for note in notes if isinstance(notes, list) else []:
        if not (isinstance(note, dict) and note.get('kind') == 'refiled_higher'):
            continue
        value = note.get('document_id')
        if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
            ids.add(int(value))
    return sorted(ids)


def declared_values(application):
    """`{field: value}` of `DECLARED_FIELDS`, plus the moved-to-higher fact (`MOVED_TO_HIGHER`)
    derived from `NOTES_FIELD`, for the hash only. A renamed field raises."""
    values = {name: getattr(application, name) for name in DECLARED_FIELDS}
    values[MOVED_TO_HIGHER] = moved_to_higher_ids(getattr(application, NOTES_FIELD))
    return values


def profile_values(application):
    """`{field: value}` of `PROFILE_FIELDS`, for the hash only; `None` when the application has no
    profile. Reading `application.profile` costs one query unless it is already loaded. A renamed
    field raises."""
    profile = application.profile
    if profile is None:
        return None
    return {name: getattr(profile, name) for name in PROFILE_FIELDS}


def intake_values(application):
    """`{field: value}` of `INTAKE_FIELDS` plus `cohort_id`, for the hash only; `None` when the
    application has no intake. Reading `application.cohort` costs one query unless it is already
    loaded. A renamed field raises.

    `allowed_start_years` is hashed as the engine reads it (`start_year.reading`): None while the
    rule is off (`rule_on`), else its years in order (`stored_years`). So a different stored order
    or a repeated year does not count, and a list of junk (rule on, no year) differs from none."""
    if application.cohort_id is None:   # the column is required; only an unsaved row lacks it
        return None
    cohort = application.cohort
    values = dict({name: getattr(cohort, name) for name in INTAKE_FIELDS},
                  cohort_id=application.cohort_id)
    years = values['allowed_start_years']
    values['allowed_start_years'] = stored_years(years) if rule_on(years) else None
    return values


def stage_facts(application):
    """The facts the engine derives from `STAGE_FIELDS`, for the hash only (no query). Each one is
    read with the engine's own constant, so a bucket the engine changes moves here too:

    * ``submitted_year``: the Malaysian year of the Submit stamp, or None (unsubmitted). The engine
      reads only whether the stamp is there (`requirements`, `higher_owed`, `results_route`) and its
      year (`str_route.str_this_year`), never the instant.
    * ``pre_submit_status``: `str_this_year` asks it only of a row with no stamp; None otherwise.
    * ``in_review_status``: a Singapore salary is converted only while in review (`amounts._to_myr`).
    * ``decided_status``: Recommended or later switches off the owed-higher-results arms
      (`higher_owed._too_late`). This one DOES flip after the decision, at the QC step: the engine
      reads it, so a replay on today's row must use the stage as it stood (see the LL5 note)."""
    from django.utils import timezone

    from .family import DECIDED_STATUSES
    from .income_engine.amounts import _INCOME_CONVERT_STATUSES
    from .income_engine.str_route import _PRE_SUBMIT_STATUSES
    submitted_at = application.profile_completed_at
    status = application.status or ''
    return {
        'submitted_year': timezone.localtime(submitted_at).year if submitted_at else None,
        'pre_submit_status': None if submitted_at else status in _PRE_SUBMIT_STATUSES,
        'in_review_status': status in _INCOME_CONVERT_STATUSES,
        'decided_status': status in DECIDED_STATUSES,
    }


def evidence_fingerprint(rows, declared, profile, intake, stage):
    """HMAC-SHA256 (hex) over the document rows, sorted by id, the declared values, the profile
    values, the intake values and the stage facts. Each row is hashed as its record entry plus its
    stored read (`_HASH_ONLY`), so a re-read under the same id and the same versions still moves the
    fingerprint. Row order does not count. The stage is an argument on purpose: a replay can hash a
    row under the stage it had at the decision."""
    documents = [dict(_document_entry(row), read={k: row[k] for k in _HASH_ONLY})
                 for row in sorted(rows, key=lambda r: int(r['id']))]
    payload = {'schema': RECORD_SCHEMA, 'documents': documents, 'declared': declared,
               'profile': profile, 'intake': intake, 'stage': stage}
    return _keyed_hash(canonical_json(payload))


def _live_document_rows(application):
    """Every live document of the application: ONE query, as plain dicts."""
    from .models import ApplicantDocument
    qs = ApplicantDocument.live(ApplicantDocument.objects.filter(application_id=application.pk))
    return list(qs.order_by('id').values(*_DOC_COLUMNS))


# --- the record ---------------------------------------------------------------------------------

def build_verdict_context(application):
    """The PII-free record of what fed this application's decision (see the module docstring).
    At most three queries: the documents, and the profile and the intake when they are not already
    loaded (the record-verdict view loads both, so there it costs one). MAY RAISE: the decision path
    calls `verdict_context_or_empty`."""
    rows = _live_document_rows(application)
    return {
        'schema': RECORD_SCHEMA,
        'documents': [_document_entry(row) for row in rows],
        'models': current_model_versions(),
        'fingerprint': evidence_fingerprint(rows, declared_values(application),
                                            profile_values(application),
                                            intake_values(application), stage_facts(application)),
        'key_check': key_check(),
    }


def failed_record(reason):
    """The record stored when none could be built: the schema and a reason code, nothing else."""
    return {'schema': RECORD_SCHEMA, 'error': reason}


def verdict_context_or_empty(application):
    """`build_verdict_context`, but NEVER raises: on any failure it returns `failed_record` and logs
    one line holding the application id and the exception's class name only (an exception's text
    can carry the values it choked on, so it is never logged)."""
    pk = getattr(application, 'pk', None)
    if not isinstance(pk, int) or isinstance(pk, bool):
        return failed_record(NO_APPLICATION)
    try:
        return build_verdict_context(application)
    except Exception as exc:  # the decision must save whatever went wrong here
        logger.warning('verdict_context: record not built for application %s (%s)',
                       pk, type(exc).__name__)
        return failed_record(BUILD_FAILED)
