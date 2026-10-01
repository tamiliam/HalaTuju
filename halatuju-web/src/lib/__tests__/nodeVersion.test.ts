/**
 * TD-255 — ONE Node major, in the four places that name it.
 *
 * The story this guards. Production built on `node:18-alpine` while every dev box ran Node 24 and
 * nothing pinned either. A test using the global `File` (Node 20+) was green on every dev machine
 * and red the first time it ran where the app is built (code health H2, 2026-09-18). Then the
 * runtime itself went past end of life with nobody noticing, because nothing compared the two.
 *
 * The four homes, and why each matters:
 *   1. `Dockerfile` `FROM node:N-alpine` — what production RUNS (and what `next build` runs on).
 *   2. `cloudbuild.yaml` test step `name: node:N-alpine` — what the deploy GATE runs jest on.
 *      If it differs from (1) the gate proves the suite on a runtime production does not use.
 *   3. `.nvmrc` — what a developer's machine is told to use.
 *   4. `package.json` `engines.node` — what npm warns about on install.
 *
 * Source-level on purpose: nothing here needs Docker. CRLF is normalised at the seam (H10).
 *
 * ⚠ WHAT THIS DOES NOT SEE: the Node the dev box ACTUALLY runs (a developer can ignore `.nvmrc`),
 * and whether the tag exists on Docker Hub — the deploy gate's first pull is the oracle for that.
 */
import fs from 'fs'
import path from 'path'

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..')

/** The oldest major this project accepts: Node 22 is the oldest LTS still in maintenance on
 *  2026-10-01. Raising the four homes past it is fine; dropping below it re-opens TD-255. */
const FLOOR = 22

function read(rel: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, rel), 'utf8').replace(/\r\n?/g, '\n')
}

function majorsIn(text: string, pattern: RegExp): number[] {
  return Array.from(text.matchAll(pattern), (m) => Number(m[1]))
}

const dockerMajors = majorsIn(read('Dockerfile'), /^FROM\s+node:(\d+)[^\s]*/gm)
const gateMajors = majorsIn(read('cloudbuild.yaml'), /^\s*name:\s*node:(\d+)[^\s]*/gm)
const nvmrc = read('.nvmrc').trim()
const engines = (JSON.parse(read('package.json')) as { engines?: { node?: string } }).engines?.node

describe('TD-255: the Node major is one number in four places', () => {
  it('finds every home (a floor: a renamed line must not make this vacuous)', () => {
    expect(dockerMajors.length).toBeGreaterThanOrEqual(1)
    expect(gateMajors.length).toBeGreaterThanOrEqual(1)
    expect(nvmrc).toMatch(/^v?\d+$/)
    expect(engines).toMatch(/^>=\s*\d+(\.\d+){0,2}$/)
  })

  it('names the SAME major in the Dockerfile, the gate, .nvmrc and engines', () => {
    const nvmrcMajor = Number(nvmrc.replace(/^v/, ''))
    const enginesMajor = Number((engines ?? '').replace(/^>=\s*/, '').split('.')[0])
    const all = {
      Dockerfile: dockerMajors,
      'cloudbuild.yaml test step': gateMajors,
      '.nvmrc': [nvmrcMajor],
      'package.json engines': [enginesMajor],
    }
    const distinct = new Set(Object.values(all).flat())
    if (distinct.size !== 1) {
      throw new Error(
        'The Node major has drifted between its homes (TD-255): ' + JSON.stringify(all) +
        '. Change all four together — the gate must run the suite on the runtime production uses.',
      )
    }
  })

  it(`is at or above the supported floor (Node ${FLOOR})`, () => {
    for (const major of [...dockerMajors, ...gateMajors]) {
      expect(major).toBeGreaterThanOrEqual(FLOOR)
    }
  })
})
