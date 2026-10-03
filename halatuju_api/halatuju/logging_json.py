"""One JSON line per log record, carrying the `severity` Cloud Logging reads (TD-290, 2026-10-03).

**Why this exists.** Cloud Run hands every stdout line to Cloud Logging, and a line that is a JSON
object is stored as `jsonPayload` with its special fields lifted out — `severity` above all
(https://cloud.google.com/run/docs/logging#special-fields). Until 2026-10-03 our console formatter
was a JSON-SHAPED format STRING: it named the level `level`, never `severity`, so every one of our
own `logger.warning` / `logger.exception` lines landed at DEFAULT severity and no
`severity>=WARNING` filter or log-based alert could ever see one. And because the string did no
escaping, a message holding a quote — or the traceback `logger.exception` appends on new lines —
was not JSON at all, and arrived as loose `textPayload` lines with no severity either.

**What it writes.** The same four keys the old format string wrote, in the same order —
`timestamp` (the same `asctime` text), `level`, `logger`, `message` — plus `severity`, and
`stack_trace` when the record carries an exception or a stack (Error Reporting reads that field).

⚠ **`message` IS BYTE-FOR-BYTE `record.getMessage()`**, exactly what `%(message)s` produced. The
`applicant_record_reads` log-based metric (docs/security/monitoring/applicant-reads-metric.yaml)
matches `jsonPayload.message=~"^AUDIT applicant_detail_read"` and extracts `admin_id=` from it; the
traceback goes to `stack_trace`, never into `message`, so no audit line changes shape.
"""
import json
import logging

#: Python's level names → Cloud Logging's LogSeverity names. Identical today except for the
#: catch-all: a custom level number with no name of ours is reported as DEFAULT, never dropped.
_SEVERITY = {'DEBUG': 'DEBUG', 'INFO': 'INFO', 'WARNING': 'WARNING', 'ERROR': 'ERROR',
             'CRITICAL': 'CRITICAL'}


class CloudRunJsonFormatter(logging.Formatter):
    """`logging.Formatter` that renders a record as one JSON object on one line."""

    def format(self, record):
        payload = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'severity': _SEVERITY.get(record.levelname, 'DEFAULT'),
        }
        trace = []
        if record.exc_info:
            trace.append(self.formatException(record.exc_info))
        elif record.exc_text:
            trace.append(record.exc_text)
        if record.stack_info:
            trace.append(self.formatStack(record.stack_info))
        if trace:
            payload['stack_trace'] = '\n'.join(trace)
        return json.dumps(payload, ensure_ascii=False, default=str)
