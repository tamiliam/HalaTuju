/**
 * TOGGLES: HalaTuju uses toggles, not tick boxes (owner ruling, 2026-11-16).
 *
 * Every on/off choice and every pick-several list is the `Toggle` component (role="switch"). The ONLY tick boxes
 * left are statements a person agrees to or confirms; they are listed below with their exact counts. A new
 * `type="checkbox"` in any non-test .tsx under `src/` fails here: use `components/Toggle.tsx`, or, if it really is
 * an agreement, add an entry with a reason a reviewer will accept.
 */
import * as fs from 'fs'
import * as path from 'path'

const SRC = path.join(__dirname, '..', '..')

const AGREEMENTS: Record<string, number> = {
  'app/scholarship/award/page.tsx': 2,            // studentAgreed, guarantorAgreed
  'app/sponsor/register/page.tsx': 1,             // consent
  'components/SponsorDetailsForm.tsx': 1,         // consent
  'components/source/SourceWitness.tsx': 1,       // confirmed
  'components/scholarship/PostAwardTasks.tsx': 1, // installed
  'components/ScholarshipNextSteps.tsx': 1,       // the checklist
}

function walk(dir: string, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name)
    if (e.isDirectory()) { if (e.name !== 'node_modules') walk(full, out) }
    else if (/\.(tsx|ts|jsx|js)$/.test(e.name) && !/\.test\.(tsx|ts|jsx|js)$/.test(e.name) && !full.includes(`${path.sep}__tests__${path.sep}`)) out.push(full)
  }
  return out
}

describe('no tick boxes outside the agreements', () => {
  const found: Record<string, number> = {}
  for (const f of walk(SRC)) {
    const n = (fs.readFileSync(f, 'utf8').match(/type\s*[=:]\s*\{?\s*[`"']checkbox[`"']/g) ?? []).length
    if (n) found[path.relative(SRC, f).split(path.sep).join('/')] = n
  }

  it('finds tick boxes in exactly the agreement files, with exact counts', () => {
    expect(found).toEqual(AGREEMENTS)
  })
})
