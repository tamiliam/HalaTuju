'use client'

/**
 * THE PATHWAY CHECKLISTS — the offer letter's clinical facts, and the soft chip a supporting
 * document earns from the name/address read.
 *
 * ⚠ THE SAME MOVE AS `./checklists.tsx` (code health H14) and split off it only because one file
 * holding both would have been 615 lines, over the 600-line standard a NEW file may not cross.
 * The badge vocabulary (`ICCheckKind`) is shared and comes from there.
 */
import type { ReactNode } from 'react'
import type { ApplicantDocument } from '@/lib/api'

import type { ICCheckKind } from './checklists'

// ── Offer-letter clinical facts (Check-1 Pathway) ────────────────────────
// Mirrors the IC / slip checklists. Two real identity checks — Name and IC (the
// IC is the strong one) — then the offer's facts as soft data points: programme,
// institution, who issued it (tells the pathway type), the date, and address.

type PathStatus = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'uncertain' | 'pending'

function pathBadgeKind(s: PathStatus): ICCheckKind {
  if (s === 'match') return 'match'
  if (s === 'partial' || s === 'uncertain') return 'partial'
  if (s === 'mismatch') return 'mismatch'
  if (s === 'unreadable') return 'unreadable'
  return 'none' // pending
}

export function OfferLetterChecklist({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const chk = doc.pathway_check
  if (!chk) return null

  const badge = (s: PathStatus) => {
    const kind = pathBadgeKind(s)
    const cls: Record<ICCheckKind, string> = {
      match: 'bg-positive-50 text-positive-700 ring-positive-200',
      partial: 'bg-caution-50 text-caution-700 ring-caution-200',
      mismatch: 'bg-critical-50 text-critical-700 ring-critical-200',
      unreadable: 'bg-ground-50 text-ground-600 ring-ground-200',
      none: 'bg-ground-50 text-ground-500 ring-ground-200',
    }
    return (
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${cls[kind]}`}>
        {t(`scholarship.docs.pathwayCheck.status.${s}`)}
      </span>
    )
  }
  const fromLetter = (
    <span className="shrink-0 rounded-full bg-ground-50 px-2 py-0.5 text-[10px] text-ground-500 ring-1 ring-ground-200">
      {t('scholarship.docs.pathwayCheck.fromLetter')}
    </span>
  )
  const row = (label: string, value: string, right: ReactNode) => (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <p className="min-w-0 text-xs text-ground-700">
        <span className="font-medium text-ground-600">{label}: </span>
        <span className="break-words">{value || '—'}</span>
      </p>
      {right}
    </div>
  )
  // Soft data point — only shown when the field was actually read.
  const dataRow = (labelKey: string, value: string) =>
    value ? row(t(`scholarship.docs.pathwayCheck.${labelKey}`), value, fromLetter) : null

  // The offer is for a genuinely different college/programme than declared. We mark
  // the two rows red (Check 1) — but it is NEVER a block: Cikgu Gopal reassures, and
  // the student confirms which is final when they submit (Check 2).
  const isMismatch = chk.pathway === 'mismatch'
  const pathRow = (labelKey: string, value: string) =>
    value
      ? row(
          t(`scholarship.docs.pathwayCheck.${labelKey}`),
          value,
          isMismatch ? badge('mismatch') : fromLetter,
        )
      : null

  return (
    <div className="mt-2 rounded-xl border border-ground-100 bg-ground-50/60 px-3 divide-y divide-ground-100">
      {row(t('scholarship.docs.pathwayCheck.name'), chk.candidate_name, badge(chk.name))}
      {row(t('scholarship.docs.pathwayCheck.ic'), chk.candidate_nric, badge(chk.ic))}
      {pathRow('programme', chk.programme)}
      {pathRow('institution', chk.institution)}
      {dataRow('issuer', chk.issuer)}
      {dataRow('date', chk.offer_date || chk.intake)}
      {dataRow('address', chk.address)}
      {isMismatch && (chk.declared_programme || chk.declared_institution) ? (
        <p className="py-1.5 text-xs text-caution-700">
          {t('scholarship.docs.pathwayCheck.declaredNote')}{' '}
          <span className="font-medium">
            {[chk.declared_programme, chk.declared_institution].filter(Boolean).join(' · ')}
          </span>
        </p>
      ) : null}
    </div>
  )
}

// ── Supporting-doc soft chip (name/address presence, S) ──────────────────

function supportingChipVariant(doc: ApplicantDocument): 'good' | 'name-missing' | 'address-missing' | 'unreadable' | null {
  const nm = doc.vision_name_match
  if (!nm) return null   // not a checked supporting doc, or Vision hasn't run
  const am = doc.vision_address_match
  if (nm === 'unreadable' || am === 'unreadable') return 'unreadable'
  if (nm === 'not_found') return 'name-missing'
  if (am === 'not_found') return 'address-missing'
  return 'good'   // name found; address found or not applicable
}

// Document-assist verdict (Gemini extraction) takes precedence over the
// deterministic presence chip when it has run — it's richer + more specific.
function assistTone(verdict: string): 'good' | 'warn' | 'info' {
  if (verdict === 'ok') return 'good'
  if (verdict === 'unreadable' || verdict === 'review_manually') return 'info'
  return 'warn'   // name_mismatch / address_mismatch / wrong_doc
}

export function SupportingDocChip({ doc, t }: { doc: ApplicantDocument; t: (key: string) => string }) {
  const palette: Record<string, string> = {
    good: 'bg-positive-50 text-positive-800 ring-positive-200',
    warn: 'bg-caution-50 text-caution-800 ring-caution-200',
    info: 'bg-ground-50 text-ground-700 ring-ground-200',
    'name-missing': 'bg-caution-50 text-caution-800 ring-caution-200',
    'address-missing': 'bg-caution-50 text-caution-800 ring-caution-200',
    unreadable: 'bg-ground-50 text-ground-700 ring-ground-200',
  }
  const chip = (tone: string, icon: string, text: string) => (
    <div className="mt-2">
      <span className={`inline-flex items-start gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 ${palette[tone]}`}>
        <span aria-hidden>{icon}</span>
        <span>{text}</span>
      </span>
      <p className="mt-1 text-xs text-ground-400">{t('scholarship.docs.vision.note')}</p>
    </div>
  )
  // Prefer the Gemini doc-assist verdict when it ran.
  const av = doc.vision_fields?.student_verdict
  if (av) {
    const tone = assistTone(av)
    return chip(tone, tone === 'good' ? '✓' : tone === 'info' ? 'ⓘ' : '⚠', t(`scholarship.docs.assist.${av}`))
  }
  // Fallback: the deterministic name/address presence chip.
  const variant = supportingChipVariant(doc)
  if (!variant) return null
  return chip(variant, variant === 'good' ? '✓' : variant === 'unreadable' ? 'ⓘ' : '⚠',
    t(`scholarship.docs.match.${variant}`))
}