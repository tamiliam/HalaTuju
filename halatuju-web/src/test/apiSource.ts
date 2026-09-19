/**
 * READ THE BACKEND'S OWN SOURCE, FROM A WEB TEST — the shared half of every drift test.
 *
 * **Why this file exists.** Code health H4 measured 60 front-end rules whose comments say they
 * mirror a backend rule, 58 of them with nothing enforcing it. A comment asking two files to stay
 * in step is a request; only a test is a rule (`SOFT_EVIDENCE` rotted for exactly that reason).
 * H9 converts the decision gates, and every one of them needs the same three lines: find
 * `halatuju_api`, read a `.py`, and lift a Python literal out of it.
 *
 * **What it deliberately is NOT.** Not a Python parser. It reads the small, stable shapes the
 * rules are actually written in — a tuple/list of string literals, and a `CHOICES` list of
 * `(value, label)` pairs — and it THROWS when it cannot find the name or cannot read the shape.
 * That is the point: a refactor on the api side that moves a constant must turn a web test RED,
 * never make it silently assert nothing. Every caller additionally asserts a minimum size, the
 * same parse-sanity guard `soft-evidence-drift.test.ts` and `test_subject_drift.py` carry.
 *
 * Jest runs in the node environment here, so `fs`/`path` are available.
 */
import * as fs from 'fs'
import * as path from 'path'

/** `halatuju_api/` — the sibling of `halatuju-web/` in the repository root. */
export const API_ROOT = path.resolve(__dirname, '..', '..', '..', 'halatuju_api')

/** Read a file by its path relative to `halatuju_api/`. Throws (loudly) if it has moved. */
export function readApi(relpath: string): string {
  const full = path.join(API_ROOT, ...relpath.split('/'))
  if (!fs.existsSync(full)) {
    throw new Error(
      `drift test: ${relpath} is not in halatuju_api. The rule it guards has MOVED — `
      + 'find its new home and update the path here, never delete the assertion.')
  }
  return fs.readFileSync(full, 'utf8')
}

/** Strip a trailing `# comment` that is outside quotes, so a `#` inside a string survives. */
function stripComment(line: string): string {
  let quote: string | null = null
  for (let i = 0; i < line.length; i += 1) {
    const c = line[i]
    if (quote) {
      if (c === '\\') { i += 1; continue }
      if (c === quote) quote = null
    } else if (c === "'" || c === '"') {
      quote = c
    } else if (c === '#') {
      return line.slice(0, i)
    }
  }
  return line
}

/**
 * The text of `NAME = …`, from the `=` to the end of the balanced bracket it opens. Module level
 * only by default; `indented` finds a class attribute (`STATUS_CHOICES` lives inside the model).
 * Comments are stripped first, so a `# TODO ('x', 'y')` in the middle cannot be read as data.
 */
function assignment(src: string, name: string, indented: boolean): string {
  const lines = src.split(/\r?\n/)
  const head = indented
    ? new RegExp(`^\\s+${name}\\s*=\\s*(.*)$`)
    : new RegExp(`^${name}\\s*=\\s*(.*)$`)
  for (let i = 0; i < lines.length; i += 1) {
    const m = stripComment(lines[i]).match(head)
    if (!m) continue
    let text = m[1]
    let depth = 0
    const count = (s: string) => {
      for (const c of s) {
        if ('([{'.includes(c)) depth += 1
        else if (')]}'.includes(c)) depth -= 1
      }
    }
    count(text)
    let j = i
    while (depth > 0 && j + 1 < lines.length) {
      j += 1
      const next = stripComment(lines[j])
      text += `\n${next}`
      count(next)
    }
    return text
  }
  throw new Error(
    `drift test: no ${indented ? 'class attribute' : 'module-level'} \`${name} = …\` found. `
    + 'The backend rule has been RENAMED or moved; follow it and fix this path.')
}

const STRING_LITERAL = /'([^'\\]*(?:\\.[^'\\]*)*)'|"([^"\\]*(?:\\.[^"\\]*)*)"/g

function literalsIn(text: string): string[] {
  return [...text.matchAll(STRING_LITERAL)].map((m) => (m[1] !== undefined ? m[1] : m[2]))
}

/**
 * A module-level tuple/list of string literals, e.g. `ORG_REJECT_FROM = ('shortlisted',)`.
 *
 * Resolves ONE level of `A + ('b',)` concatenation, because that is how the api composes a band
 * out of a narrower one (`STR_COACH_STATES = STR_RED_STATES + ('unreadable', 'unconfirmed')`) —
 * reading only the literal half would pin a SUBSET and pass while the real set drifted.
 */
export function pySeq(src: string, name: string): string[] {
  const text = assignment(src, name, false)
  const out: string[] = []
  for (const part of text.split('+')) {
    const named = part.trim().match(/^([A-Z][A-Z0-9_]*)$/)
    if (named) { out.push(...pySeq(src, named[1])); continue }
    out.push(...literalsIn(part))
  }
  return out
}

/**
 * The VALUES of a Django `*_CHOICES` list of `(value, label)` pairs — the first literal of each
 * pair, so a label containing a comma or an apostrophe cannot shift the reading.
 * `indented` because these live inside the model class.
 */
export function pyChoiceValues(src: string, name: string, indented = true): string[] {
  const text = assignment(src, name, indented)
  const pair = /\(\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*,/g
  return [...text.matchAll(pair)].map((m) => m[1].slice(1, -1))
}

/**
 * A `{action: (from_statuses, to_status|None)}` table — `org_requests.TRANSITIONS`, the api's own
 * "single source of truth for which status an action moves a request out of".
 * Returns `action -> the statuses it may be applied FROM`.
 */
export function pyTransitionTable(src: string, name: string): Record<string, string[]> {
  const text = assignment(src, name, false)
  const out: Record<string, string[]> = {}
  const row = /(['"])([a-z_]+)\1\s*:\s*\(\s*\(([^)]*)\)/g
  for (const m of text.matchAll(row)) out[m[2]] = literalsIn(m[3])
  return out
}
