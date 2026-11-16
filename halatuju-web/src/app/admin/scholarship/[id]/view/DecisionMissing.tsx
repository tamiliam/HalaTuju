'use client'

/**
 * "STILL TO DO" — the list of exactly what is missing before Recommend or Decline can act (request #70).
 *
 * ⚠ THE RULE LIVES IN `decisionMissing` (`@/lib/cockpitStages`), NOT HERE. This file only words and links the items it
 * returns, so the list can never disagree with the gate. Each item is a button that scrolls to and focuses the place
 * the reviewer fixes it: the interview stage, the first unrated fact in Rate AI Prediction, the conclusion box.
 *
 * The same list serves the card (under the buttons) and, through `DECISION_ALERT_EVENT`, the phone's decision bar.
 * Shown as an alert (`role="alert"`, focused) after a press on a greyed Recommend / Decline; plain otherwise.
 */
import { useEffect, useRef } from 'react'
import type { DecisionMissingItem } from '@/lib/cockpitStages'

import type { T } from './shared'

/** The phone bar fires this on `document` when pressed while something is missing; the card answers with the alert. */
export const DECISION_ALERT_EVENT = 'decision-missing-alert'

/** Where each item is fixed: the id of the element to scroll to and focus. */
export function missingTarget(item: DecisionMissingItem): string {
  switch (item.kind) {
    case 'findings_not_submitted':
    case 'findings_unanswered': return 'interview-section'
    case 'facts_unrated': return `rate-fact-${item.facts[0]}-pass`
    case 'conclusion_empty': return 'verdict-reason'
  }
}

export function jumpTo(id: string): void {
  const el = document.getElementById(id)
  if (!el) return
  el.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  el.focus?.({ preventScroll: true })
}

function itemText(t: T, item: DecisionMissingItem): string {
  const k = 'admin.scholarship.recordVerdict.missing.'
  switch (item.kind) {
    case 'findings_not_submitted': return t(`${k}submit`)
    case 'findings_unanswered':
      return item.count === 1 ? t(`${k}answerOne`) : t(`${k}answerMany`, { count: String(item.count) })
    case 'facts_unrated':
      return t(`${k}rate`, { facts: item.facts.map((f) => t(`admin.scholarship.verdict.fact.${f}`)).join(', ') })
    case 'conclusion_empty': return t(`${k}conclusion`)
  }
}

export function DecisionMissingList({ t, items, alert }: { t: T; items: DecisionMissingItem[]; alert: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (alert) ref.current?.focus() }, [alert])
  return (
    <div ref={ref} id="decision-missing" tabIndex={-1} {...(alert ? { role: 'alert' } : {})}
      className="text-xs md:text-[11px] text-caution-700 focus:outline-none">
      <p className="font-medium">{t('admin.scholarship.recordVerdict.missing.heading')}</p>
      <ul className="list-disc pl-4">
        {items.map((it) => (
          <li key={it.kind}>
            <button type="button" onClick={() => jumpTo(missingTarget(it))}
              className="text-left underline underline-offset-2 max-md:min-h-11 max-md:py-1">
              {itemText(t, it)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
