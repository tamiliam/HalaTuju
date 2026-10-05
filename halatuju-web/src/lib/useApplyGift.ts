'use client'

/**
 * WHICH GIFT THE APPLY FORM IS FOR — read from the URL, asked when ambiguous, named on the form.
 *
 * Lifted out of `/scholarship/apply` (2026-10-05, "apply gift clarity"), where it was a one-shot
 * effect that read `?p=` once and never asked the intake endpoint again. Three defects followed:
 *
 *   • D2 — after a pick in the chooser the page kept the PLATFORM's heading and criteria, because
 *     nothing re-read the intake for the chosen gift. The intake effect now follows the code in
 *     the URL, so a pick (or a "Change") asks again and gets that gift's own `apply_copy`.
 *
 * ⚠ A NAMED GIFT THAT IS CLOSED SAYS SO (owner's live test, 2026-10-05). It used to bounce silently
 * to `/scholarship`; now `closed` is set and the page shows a closed card on the gift's own page,
 * with `othersOpen` offering the bare apply page BY LINK — never a redirect, never a pre-selection.
 * `recheck` asks again after a refused submit, so a student midway through the form when the round
 * closed is told why. A BARE visit with nothing open anywhere sets `noneOpen`; the PAGE then sends
 * her to `/scholarship` (whose landing already says closed) — unless the apply gate says she has an
 * application in progress, which wins. This hook never redirects by itself (round 2 of TD-337: two
 * redirects raced, and the last one won).
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
  /** The intake has ANSWERED (or failed) for the code in force. Until then the page must draw no
   *  heading or criteria: the platform default would flash, then be replaced by the gift's own
   *  words or by the chooser — one gift's terms shown to a student who meant another. */
  settled: boolean
  /** The gift the URL (or a pick) named has CLOSED — the page shows the closed card. */
  closed: boolean
  /** Some OTHER round is open (the bare intake says so) — the closed card may link to it. */
  othersOpen: boolean
  /** A BARE visit and nothing is open anywhere. The page decides where that sends her. */
  noneOpen: boolean
  /** The code the URL (or a pick) names — '' on a bare visit, null until the address bar is read.
   *  What the apply gate asks about; the server resolves it exactly as the intake does. */
  named: string | null
  pick: (code: string) => void
  change: () => void
  /** Ask the intake again for the code in force; resolves true (and sets `closed`) if it closed. */
  recheck: () => Promise<boolean>
}

/** A submit the server refused because it could not tell which gift (PF-1's 409). The page answers
 *  it by asking again (`change`), keeping what she typed. */
export function isProgrammeRequired(err: unknown): boolean {
  // The server sends this code only with its 409 (`ApplicationListCreateView.post`).
  return (err as { bodyCode?: string } | null)?.bodyCode === 'programme_required'
}

/** Any OTHER 409 at submit — e.g. "no open round" once the gift closed mid-form. The page asks the
 *  intake again (`recheck`) before falling back to its generic error. */
export function isOtherConflict(err: unknown): boolean {
  return (err as { status?: number } | null)?.status === 409 && !isProgrammeRequired(err)
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
  const [settled, setSettled] = useState(false)
  const [closed, setClosed] = useState(false)
  const [othersOpen, setOthersOpen] = useState(false)
  const [noneOpen, setNoneOpen] = useState(false)
  // Bumped by `change` so the intake is asked again even when the URL code was already '' (a 409
  // on a bare visit) — setting '' to '' would not re-run the effect.
  const [asked, setAsked] = useState(0)

  // Capture the organisation's link (`?p=`) the moment the student ARRIVES, not at submit.
  useEffect(() => { setUrlCode(enterApplyPage(window.location.search)) }, [])

  // Intake gate: no NEW applications once the gift's round closes — a named gift that is closed
  // says so (`closed`); nothing open on a bare visit is `noneOpen`. Re-asked whenever the URL's
  // code changes.
  useEffect(() => {
    if (urlCode === null) return
    let active = true
    // Never show (or submit) one gift's name or code while another is in force.
    setCopy(undefined); setName(''); setServed(''); setChoices([]); setCanChange(false)
    setSettled(false); setClosed(false); setOthersOpen(false); setNoneOpen(false)
    // ⚠ THE GIFT'S CODE GOES WITH THE QUESTION. Without it this asks "is anything open ANYWHERE?"
    // — a student on a closed gift's poster was shown the whole form and refused only at submit.
    getScholarshipIntake(urlCode).then((r) => {
      if (!active) return
      // Set BEFORE the closed check: the closed card heads with the closed gift's own title.
      setCopy(r.apply_copy)
      setSettled(true)
      if (!r.open) {
        if (urlCode) setClosed(true)              // a NAMED gift: say so, on its own page
        else setNoneOpen(true)                    // nothing open anywhere: the PAGE decides
        return
      }
      setName(r.cohort_name || '')
      const resolved = (r.programme_code || '').trim()
      setServed(resolved)
      // Remembered so a detour / sign-in round trip comes back to THIS gift, not a fresh resolve.
      if (resolved) setApplyProgramme(resolved)
      // ⚠ ASK BEFORE THE FORM, NOT AT SUBMIT — `resolve_open_cohort` refuses to guess between two
      // open rounds, and that refusal used to arrive as a 409 after the whole form was filled in.
      if (needsProgrammeChoice(urlCode, r.choices)) setChoices(r.choices ?? [])
    }).catch(() => { if (active) setSettled(true) })   // a failure settles too: the page as before
    // "Change" only makes sense when another gift is open. A coded question never lists choices,
    // so ask the bare one for that alone — and whether ANY round is open, for the closed card.
    if (urlCode) {
      getScholarshipIntake().then((r) => {
        if (!active) return
        setCanChange((r.choices?.length ?? 0) > 1)
        setOthersOpen(!!r.open)
      }).catch(() => {})
    }
    return () => { active = false }
  }, [urlCode, asked])

  const pick = useCallback((picked: string) => {
    const clean = picked.trim()
    if (!clean) return
    // Stored through the SAME seam a `?p=` link writes, so submit cannot tell the two apart.
    setApplyProgramme(clean)
    setUrlCode(clean)
    setSettled(false)   // in the same render as the new code: no frame of the old gift's words
    router.replace(applyPagePath())
  }, [router])

  const change = useCallback(() => {
    clearApplyProgramme()
    setUrlCode('')
    setSettled(false)
    setAsked((n) => n + 1)
    router.replace(applyPagePath())
  }, [router])

  const code = served || (urlCode ?? '')

  // After a refused submit (a 409 that is not `programme_required`): has THIS gift closed since?
  // If so, the page shows the closed card instead of an error. A failed ask changes nothing.
  const recheck = useCallback(async () => {
    try {
      const r = await getScholarshipIntake(code)
      if (r.open) return false
      if (code) {
        const bare = await getScholarshipIntake().catch(() => null)
        setOthersOpen(!!bare?.open)
      }
      setClosed(true)
      return true
    } catch {
      return false
    }
  }, [code])

  return {
    code, copy, choices, name, canChange, settled, closed, othersOpen, noneOpen, pick, change, recheck,
    named: urlCode,
  }
}
