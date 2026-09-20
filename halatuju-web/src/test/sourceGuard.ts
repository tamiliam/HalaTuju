/**
 * EVERY GUARD THAT READS THE TREE MUST HAVE A FLOOR (TD-276, code health H16, 2026-09-20).
 *
 * **The shape this file exists to kill.** A guard walks the tree, finds N things, asserts
 * something about each one. Then the code moves — a module becomes a package, a folder is
 * renamed, a glob stops matching — and the walk finds ZERO things. Every assertion is now
 * vacuous and the guard goes on passing. Nothing goes red and the rule is simply gone.
 *
 * This arc has met that failure four times and every time it was SILENT:
 *
 * 1. `officerGateDrift.test.ts` read `views_admin.py` by path; H11 made it a package and the
 *    whole suite died at import — thirteen tests gone, unnoticed for two sprints.
 * 2. `test_verdict_item_i18n.py` used `glob` where a package needed `rglob`.
 * 3. `AuditLoggerNameTest` was hard-coded to one package; the bite came back SILENT at H15.
 * 4. `test_wallet_credit.py` allowlisted by bare filename, widening as the tree grew.
 *
 * **A guard that can pass while seeing nothing is not a guard.**
 *
 * `apiSource.ts` is the same idea pointed at the BACKEND's tree (`readApi`, `readApiTree`). This
 * file is its twin for the web's own tree and for anything else in the repository: read a path
 * through `readWeb`/`readRepo`, walk a directory through `walkFloor`. All of them throw LOUDLY —
 * naming the path, the number expected and the reason — instead of an `ENOENT` into a stdlib
 * frame, or worse, an empty array that asserts nothing.
 *
 * ⚠ A FLOOR IS A MINIMUM, NOT AN EQUALITY. It is the count the walk found on the day it was
 * written, usually rounded down a little, so adding a legitimate new file leaves the guard GREEN.
 * A floor that cries wolf teaches the next engineer to edit the number without reading it, and a
 * floor nobody believes is worse than none. A guard that genuinely needs a CLOSED set — one extra
 * file is itself the defect — asserts that equality itself, beside the reason it is closed; there
 * is no flag for it here, because a flag would let the choice be made without writing the reason.
 *
 * Jest runs these in the node environment, so `fs`/`path` are available.
 */
import * as fs from 'fs'
import * as path from 'path'

/** `halatuju-web/` — three levels up from `src/test/`. */
export const WEB_ROOT = path.resolve(__dirname, '..', '..')

/** The repository root, the parent of both `halatuju-web/` and `halatuju_api/`. */
export const REPO_ROOT = path.resolve(WEB_ROOT, '..')

/** Directories no source guard ever wants to read. */
export const SKIP_DIRS = ['node_modules', '.next', '.git', '__pycache__', 'coverage']

/** A path as a repo-relative POSIX string, so a message reads the same on every platform. */
function rel(full: string): string {
  return path.relative(REPO_ROOT, full).split(path.sep).join('/')
}

function readOrThrow(full: string, why: string): string {
  if (!fs.existsSync(full) || !fs.statSync(full).isFile()) {
    throw new Error(
      `SOURCE GUARD: ${rel(full)} is not there.\n`
      + `  This guard reads it because: ${why}\n`
      + '  The code it watches has MOVED or been renamed. Follow it and re-point this path — '
      + 'never delete the assertion, and never convert this into a skip.')
  }
  // ⚠ Line endings normalised to `\n`. The checkout is CRLF on Windows and LF in the Cloud Build
  // container, so a guard matching `\n\n` to find the end of a block would pass on one machine
  // and fail on the other — a drift test that depends on which machine ran it is worse than none.
  return fs.readFileSync(full, 'utf8').replace(/\r\n?/g, '\n')
}

/** Read a file by its path relative to `halatuju-web/`. Throws, named, if it has moved. */
export function readWeb(relpath: string, why: string): string {
  return readOrThrow(path.join(WEB_ROOT, ...relpath.split('/')), why)
}

/** Read a file by its path relative to the REPOSITORY root (either service, or `docs/`). */
export function readRepo(relpath: string, why: string): string {
  return readOrThrow(path.join(REPO_ROOT, ...relpath.split('/')), why)
}

export interface WalkOptions {
  /** Extensions to keep, with the dot (`['.ts', '.tsx']`). Omit to take every file. */
  exts?: string[]
  /** Directory names to skip, in addition to `SKIP_DIRS`. */
  skip?: string[]
}

/**
 * Every file under `dir` (absolute), recursively, sorted — with a FLOOR under the count.
 *
 * `floor` is the number the walk found when the floor was written. Fewer and this throws, naming
 * the shortfall, the directory and `why`, so a walk that has silently narrowed says what moved
 * rather than asserting nothing. More is fine and deliberately so.
 */
export function walkFloor(dir: string, floor: number, why: string, opts: WalkOptions = {}): string[] {
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
    throw new Error(
      `SOURCE GUARD: ${rel(dir)} is not a directory.\n`
      + `  This guard walks it because: ${why}\n`
      + '  The tree it watches has MOVED or been renamed. Follow it and re-point this walk — '
      + 'never delete the assertion, and never convert this into a skip.')
  }
  const skip = new Set([...SKIP_DIRS, ...(opts.skip ?? [])])
  const out: string[] = []
  const visit = (cur: string): void => {
    for (const entry of fs.readdirSync(cur, { withFileTypes: true })) {
      const full = path.join(cur, entry.name)
      if (entry.isDirectory()) {
        if (!skip.has(entry.name)) visit(full)
      } else if (!opts.exts || opts.exts.some((e) => entry.name.endsWith(e))) {
        out.push(full)
      }
    }
  }
  visit(dir)
  out.sort()
  if (out.length < floor) {
    throw new Error(
      `THE FLOOR: walking ${rel(dir)} found only ${out.length} file(s); this guard expects at `
      + `least ${floor}.\n  It walks that tree because: ${why}\n`
      + '  Either the tree MOVED (follow it and re-point this walk) or the filter stopped '
      + 'matching. Check before lowering the floor — a walk that finds nothing asserts nothing '
      + 'and passes for ever, which is the whole reason this number is here.')
  }
  return out
}

/**
 * The same floor, for a corpus a guard assembled itself (a scan's results, a parse's output).
 *
 * `walkFloor` floors the FILES; this floors the THINGS, which is the other half of the shape: a
 * walk can read every file and still find none of what it came for, because the marker it greps
 * was renamed.
 */
export function floorCount<T>(found: T[], floor: number, what: string, why: string): T[] {
  if (found.length < floor) {
    throw new Error(
      `THE FLOOR: the scan found only ${found.length} ${what}; this guard expects at least `
      + `${floor}.\n  It scans for them because: ${why}\n`
      + '  Either the marker it greps was RENAMED or the corpus narrowed. Check before lowering '
      + 'the floor — a scan that finds nothing asserts nothing.')
  }
  return found
}
