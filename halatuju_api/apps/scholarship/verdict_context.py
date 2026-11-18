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
  what the student declared that the engine reads. VALUES ENTER THE HASH ONLY, never the record.
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


def declared_values(application):
    """`{field: value}` of `DECLARED_FIELDS`, for the hash only. A renamed field raises."""
    return {name: getattr(application, name) for name in DECLARED_FIELDS}


def evidence_fingerprint(rows, declared):
    """HMAC-SHA256 (hex) over the document rows, sorted by id, and the declared values. Each row is
    hashed as its record entry plus its stored read (`_HASH_ONLY`), so a re-read under the same id
    and the same versions still moves the fingerprint. Row order does not count."""
    documents = [dict(_document_entry(row), read={k: row[k] for k in _HASH_ONLY})
                 for row in sorted(rows, key=lambda r: int(r['id']))]
    payload = {'schema': RECORD_SCHEMA, 'documents': documents, 'declared': declared}
    return _keyed_hash(canonical_json(payload))


def _live_document_rows(application):
    """Every live document of the application: ONE query, as plain dicts."""
    from .models import ApplicantDocument
    qs = ApplicantDocument.live(ApplicantDocument.objects.filter(application_id=application.pk))
    return list(qs.order_by('id').values(*_DOC_COLUMNS))


# --- the record ---------------------------------------------------------------------------------

def build_verdict_context(application):
    """The PII-free record of what fed this application's decision (see the module docstring).
    One query (the documents). MAY RAISE: the decision path calls `verdict_context_or_empty`."""
    rows = _live_document_rows(application)
    return {
        'schema': RECORD_SCHEMA,
        'documents': [_document_entry(row) for row in rows],
        'models': current_model_versions(),
        'fingerprint': evidence_fingerprint(rows, declared_values(application)),
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
