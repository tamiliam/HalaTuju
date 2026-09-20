/**
 * THE DRIFT TEST for `applicationStatus.ts` — named by its `drift-test:` marker (code health H9).
 *
 * `APPLICATION_STATUSES` said it mirrored `ScholarshipApplication.STATUS_CHOICES` and nothing
 * checked. The list is not decoration: it drives the applicant list's filter dropdown, so a status
 * added in Django and forgotten here becomes a cohort of students **no filter can reach** — which
 * is how `withdrawn` and `expired` were silently missing once before (the module docblock says so).
 *
 * Characterised before anything was written (the H8 rule): the two sides were compared row by row
 * on the untouched tree and they AGREE on all thirteen. The ORDER differs on purpose — Django
 * lists them in the order they were added, the web in FUNNEL order — so membership is what is
 * pinned here, in both directions, and the funnel order stays the web's own decision.
 */
import {
  APPLICATION_STATUSES, SYNTHETIC_STATUSES, hasStatusTone,
} from '@/lib/applicationStatus'
import { pyChoiceValues, readApi } from '@/test/apiSource'

// ⚠ `models.py` became the PACKAGE `models/` at code health H15 (2026-09-20); the path follows
// the code, and the assertion is never deleted. `STATUS_CHOICES` is a class attribute on nine
// models, and `pyChoiceValues` takes the FIRST — so this names the one module that holds
// `ScholarshipApplication` rather than walking the package, which would make the answer depend on
// the order the files happen to sort in. `readApi` throws if that module ever moves again.
const MODELS = 'apps/scholarship/models/applications.py'
const backend = pyChoiceValues(readApi(MODELS), 'STATUS_CHOICES')
const web = [...APPLICATION_STATUSES] as string[]

describe('APPLICATION_STATUSES vs ScholarshipApplication.STATUS_CHOICES', () => {
  test('the parse found a real status list (parse sanity — never a 0-assert no-op)', () => {
    // `STATUS_CHOICES` is the FIRST such attribute in models.py (ScholarshipApplication). If a
    // refactor moves it, or another model shadows it, this count is what notices.
    expect(backend.length).toBe(13)
    expect(backend).toContain('submitted')
    expect(backend).toContain('rejected')
  })

  test('every DB status the api offers is in the web list (else no filter can reach it)', () => {
    expect(backend.filter((s) => !web.includes(s))).toEqual([])
  })

  test('every web status is a real DB status (no invented stage in the dropdown)', () => {
    expect(web.filter((s) => !backend.includes(s))).toEqual([])
  })

  test('every DB status carries an explicit tone — a new stage cannot ship colourless', () => {
    expect(backend.filter((s) => !hasStatusTone(s))).toEqual([])
  })

  test('the synthetic statuses are NOT DB values — that split is the point of the second list', () => {
    // `reopened` is rendered from `decision_reopened_at`; if it ever became a stored status the
    // override in `displayStatus` would start hiding a real one.
    expect([...SYNTHETIC_STATUSES].filter((s) => backend.includes(s))).toEqual([])
  })
})
