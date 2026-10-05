'use client'

/**
 * WHICH GIFT THE APPLY FORM IS FOR — read from the URL, asked when ambiguous, named on the form.
 *
 * Lifted out of `/scholarship/apply` (2026-10-05, "apply gift clarity"), where it was a one-shot
 * effect that read `?p=` once and never asked the intake endpoint again. Three defects followed:
 *
 *   • D2 — after a pick in the chooser the page kept the PLATFORM's heading and criteria, because
 *     nothing re-read the intake for the chosen gift. The intake effect now follows the code in
 *     the URL, so a pick (or a "Change") asks again and gets that gift's own `apply_copy` — and its
 *     closed bounce.
 *   • D3 — a bare visit reused whatever code an earlier visit in the tab had stored. Arrival now goes
 *     through `enterApplyPage`: the URL is the only thing that names a gift, and the two legitimate
 *     round trips come back carrying `?p=` (`applyPagePath`).
 *   • D4 — the form never said which gift it was for. `name` is the intake's `cohort_name`.
 *
 * ⚠ THE CODE SUBMITTED IS THE ONE THE SHOWN NAME WAS RESOLVED FROM. `code` is the intake's own
 * `programme_code` — the canonical code of the round it named — whenever the api sends one, and the
 * URL's code only when it does not (an older api, or a round with no programme). Without it, a bare
 * visit with one gift open named that round but submitted NO code, so if the round closed and
 * another opened while she typed, the server filed her under the other gift. Now that submit is
 * refused (closed round) instead of re-routed.
 *
 * ⚠ THE PICK GOES INTO THE URL (`router.replace`), so a refresh keeps it — a query param, not a
 * persistent flag. `replace`, not `push`: Back leaves the form, it does not replay the chooser.
 * The page component is NOT remounted by a search-param change, so typed form state survives a
 * "Change" and a re-pick.
 *
 * ⚠ IT OFFERS; IT NEVER PRE-SELECTS. Nothing here chooses a gift for the student.
 *
 * `window.location`, not `useSearchParams` — a page file would need a Suspense boundary for it.
 */
import { useCallback, useEffect, useState } from 'react'

import { getScholarshipIntake, type IntakeChoice } from '@/lib/api'
import type { ServedCopy } from '@/lib/applyCopy'
import { applyPagePath } from '@/lib/applyPagePath'
import {
  clearApplyProgramme, enterApplyPage, needsProgrammeChoice, setApplyProgramme,
} from '@/lib/applyProgramme'

// Re-exported for the page's submit, which forgets the code once the application is filed.
export { clearApplyProgramme } from '@/lib/applyProgramme'

export interface ApplyGift {
  /** The programme code to submit as `programme_code`. '' = none can be named. */
  code: string
  /** That gift's own apply-page copy. Undefined/empty ⇒ the platform default. */
  copy: ServedCopy
  /** Populated ONLY when several gifts are open and nothing named one: the chooser's options. */
  choices: IntakeChoice[]
  /** The open round's name for the code in force ('' until known, or when none can be named). */
  name: string
  /** More than one gift is open and one is in force — the form may offer "Change". */
  canChange: boolean
  pick: (code: string) => void
  change: () => void
}

/** A submit the server refused because it could not tell which gift (PF-1's 409). The page answers
 *  it by asking again (`change`), keeping what she typed. */
export function isProgrammeRequired(err: unknown): boolean {
  // The server sends this code only with its 409 (`ApplicationListCreateView.post`).
  return (err as { bodyCode?: string } | null)?.bodyCode === 'programme_required'
}

export function useApplyGift(router: { replace: (href: string) => void }): ApplyGift {
  // The code the URL names; null until the address bar has been read — nothing is asked before.
  const [urlCode, setUrlCode] = useState<string | null>(null)
  // The code the intake answered with for it ('' = it sent none).
  const [served, setServed] = useState('')
  const [copy, setCopy] = useState<ServedCopy>(undefined)
  const [choices, setChoices] = useState<IntakeChoice[]>([])
  const [name, setName] = useState('')
  const [canChange, setCanChange] = useState(false)
  // Bumped by `change` so the intake is asked again even when the URL code was already '' (a 409
  // on a bare visit) — setting '' to '' would not re-run the effect.
  const [asked, setAsked] = useState(0)

  // Capture the organisation's link (`?p=`) the moment the student ARRIVES, not at submit.
  useEffect(() => { setUrlCode(enterApplyPage(window.location.search)) }, [])

  // Intake gate: no NEW applications once the gift's round closes — a bookmarked or just-picked
  // gift that is closed bounces to the landing. Re-asked whenever the URL's code changes.
  useEffect(() => {
    if (urlCode === null) return
    let active = true
    // Never show (or submit) one gift's name or code while another is in force.
    setCopy(undefined); setName(''); setServed(''); setChoices([]); setCanChange(false)
    // ⚠ THE GIFT'S CODE GOES WITH THE QUESTION. Without it this asks "is anything open ANYWHERE?"
    // — a student on a closed gift's poster was shown the whole form and refused only at submit.
    getScholarshipIntake(urlCode).then((r) => {
      if (!active) return
      // Set BEFORE the closed-bounce so a screen that shows a closed gift still has its words.
      setCopy(r.apply_copy)
      if (!r.open) { router.replace('/scholarship'); return }
      setName(r.cohort_name || '')
      const resolved = (r.programme_code || '').trim()
      setServed(resolved)
      // Remembered so a detour / sign-in round trip comes back to THIS gift, not a fresh resolve.
      if (resolved) setApplyProgramme(resolved)
      // ⚠ ASK BEFORE THE FORM, NOT AT SUBMIT — `resolve_open_cohort` refuses to guess between two
      // open rounds, and that refusal used to arrive as a 409 after the whole form was filled in.
      if (needsProgrammeChoice(urlCode, r.choices)) setChoices(r.choices ?? [])
    }).catch(() => {})
    // "Change" only makes sense when another gift is open. A coded question never lists choices,
    // so ask the bare one for that alone.
    if (urlCode) {
      getScholarshipIntake().then((r) => {
        if (active) setCanChange((r.choices?.length ?? 0) > 1)
      }).catch(() => {})
    }
    return () => { active = false }
  }, [urlCode, asked, router])

  const pick = useCallback((picked: string) => {
    const clean = picked.trim()
    if (!clean) return
    // Stored through the SAME seam a `?p=` link writes, so submit cannot tell the two apart.
    setApplyProgramme(clean)
    setUrlCode(clean)
    router.replace(applyPagePath())
  }, [router])

  const change = useCallback(() => {
    clearApplyProgramme()
    setUrlCode('')
    setAsked((n) => n + 1)
    router.replace(applyPagePath())
  }, [router])

  return { code: served || (urlCode ?? ''), copy, choices, name, canChange, pick, change }
}
