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

/**
 * Read a file by its path relative to `halatuju_api/`. Throws (loudly) if it has moved.
 *
 * ⚠ LINE ENDINGS ARE NORMALISED TO `\n`. The api sources are CRLF on a Windows checkout and LF in
 * the Cloud Build container, so a caller matching `\n\n` to find the end of a block would pass on
 * one machine and fail on the other — a drift test that depends on which machine ran it is worse
 * than none. Every caller sees `\n`.
 */
export function readApi(relpath: string): string {
  const full = path.join(API_ROOT, ...relpath.split('/'))
  if (!fs.existsSync(full)) {
    throw new Error(
      `drift test: ${relpath} is not in halatuju_api. The rule it guards has MOVED — `
      + 'find its new home and update the path here, never delete the assertion.')
  }
  return fs.readFileSync(full, 'utf8').replace(/\r\n/g, '\n')
}

/**
 * Read a whole api PACKAGE as one string — every `.py` in the folder, joined.
 *
 * ⚠ WHY A WALK AND NOT A LIST OF FILES (code health H15, 2026-09-20). `models.py` (4,756 lines)
 * and `services.py` (2,946) became packages, and several guards here scan the WHOLE of one of
 * them to assert that exactly ONE block matches a shape — "exactly one `KIND_CHOICES` containing
 * `weekly_summary`", say. Re-pointing such a guard at the single module that holds the block it
 * wants would still pass, while quietly giving up the half of the rule that says no SECOND one
 * exists anywhere else. A walk keeps reading the same surface the one file used to be.
 *
 * `minFiles` is the floor, and it is the whole reason this is safe: if the package is ever
 * flattened, renamed, or the glob stops matching, the guard goes RED instead of scanning nothing
 * and passing for ever. (H6/H11's lesson, and `test_the_scan_actually_found_some`'s.)
 *
 * Files are joined in ASCII order of their names, which is deterministic but is NOT the order the
 * original file declared things in — so a caller that wants a specific block must select it BY
 * CONTENT, never by taking the first match.
 */
export function readApiTree(relDir: string, minFiles: number): string {
  const full = path.join(API_ROOT, ...relDir.split('/'))
  if (!fs.existsSync(full) || !fs.statSync(full).isDirectory()) {
    throw new Error(
      `drift test: ${relDir} is not a package in halatuju_api. The rules it guards have MOVED — `
      + 'find their new home and update the path here, never delete the assertion.')
  }
  const files = fs.readdirSync(full).filter((f) => f.endsWith('.py')).sort()
  if (files.length < minFiles) {
    throw new Error(
      `drift test: ${relDir} has ${files.length} modules, fewer than the ${minFiles} this guard `
      + 'expects. Either the package was split differently or the walk stopped working — check '
      + 'before lowering this floor, because a guard that reads nothing passes for ever.')
  }
  return files.map((f) => readApi(`${relDir}/${f}`)).join('\n')
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
export function pySeq(src: string, name: string, indented = false): string[] {
  const text = assignment(src, name, indented)
  const out: string[] = []
  for (const part of text.split('+')) {
    const named = part.trim().match(/^([A-Z][A-Z0-9_]*)$/)
    if (named) { out.push(...pySeq(src, named[1], indented)); continue }
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
