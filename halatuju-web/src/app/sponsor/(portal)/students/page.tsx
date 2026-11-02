'use client'

import '@/lib/messagesSponsor'   // TD-416: this page's sponsor* words (their own slice)
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import { fieldImageUrl } from '@/lib/fieldImage'
import { FundingBar } from '@/components/FundingBar'
import { countdown, rmWhole } from '@/lib/poolCard'
import SponsorFilterSheet, { type SponsorFacet } from '@/components/sponsor/SponsorFilterSheet'
import type { SponsorPoolCard } from '@/lib/api'

// Distinct amount → its whole-ringgit key ("2000.00" -> "2000"); '' when not numeric.
const amtKey = (v: string | null | undefined) =>
  v != null && Number.isFinite(Number(v)) ? String(Math.round(Number(v))) : ''

/**
 * Students — the anonymised marketplace (image-led cards). Browse + filter the pool
 * (client-side over the already-fetched cards) and open a student to fund them. Anonymity
 * is inviolate: the card shows field artwork + region + programme, never an identity.
 */
export default function StudentsPage() {
  const { t, locale } = useT()
  const { getFieldName } = useFieldTaxonomy(locale)
  const { pool } = useSponsorPortal()

  const [field, setField] = useState('')
  const [state, setState] = useState('')
  const [amount, setAmount] = useState('')
  // '' = all; 'open' = still open for sponsorship (unfunded); 'sponsored' = just-sponsored cards.
  const [status, setStatus] = useState('')
  // Phones (Mobile M5): the four selects become one "Filters" button and a Sheet of chips — the SAME state.
  const [sheetOpen, setSheetOpen] = useState(false)

  const rows = pool || []
  const facets = useMemo(() => {
    const uniq = (xs: string[]) => Array.from(new Set(xs.filter(Boolean)))
    return {
      fields: uniq(rows.map((r) => r.field)).sort(),
      states: uniq(rows.map((r) => r.state)).sort(),
      // Only the amounts actually present (currently RM1,000 / RM2,000 / RM3,000).
      amounts: uniq(rows.map((r) => amtKey(r.award_amount))).sort((a, b) => Number(a) - Number(b)),
    }
  }, [rows])
  const shown = useMemo(
    () => rows.filter((r) =>
      (!field || r.field === field) &&
      (!state || r.state === state) &&
      (!amount || amtKey(r.award_amount) === amount) &&
      (!status || (status === 'sponsored' ? r.funded : !r.funded))),
    [rows, field, state, amount, status],
  )

  const selectCls = 'text-sm border border-ground-200 rounded-lg pl-3.5 pr-9 py-2.5 bg-ground-0 min-w-[10rem] cursor-pointer'

  // The phone's chips read the SAME facets and write the SAME state as the desktop selects.
  const groups: SponsorFacet[] = [
    { key: 'status', title: t('sponsorPortal.students.facetStatus'), value: status, onChange: setStatus,
      options: [{ value: 'open', label: t('sponsorPortal.students.openForSponsorship') },
        { value: 'sponsored', label: t('sponsorPortal.students.sponsored') }] },
    { key: 'field', title: t('sponsorPortal.students.facetField'), value: field, onChange: setField,
      options: facets.fields.map((f) => ({ value: f, label: getFieldName(f) || f })) },
    { key: 'state', title: t('sponsorPortal.students.facetState'), value: state, onChange: setState,
      options: facets.states.map((x) => ({ value: x, label: x })) },
    { key: 'amount', title: t('sponsorPortal.students.facetAmount'), value: amount, onChange: setAmount,
      options: facets.amounts.map((a) => ({ value: a, label: `RM${rmWhole(a)}` })) },
  ]
  const picked = groups.filter((g) => g.value).length
  const clearAll = () => { setField(''); setState(''); setAmount(''); setStatus('') }

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2 pt-3 md:pt-0">
        <h1 className="text-2xl font-bold text-ground-900">{t('sponsorPortal.students.title')}</h1>
        <span className="text-xs text-ground-400">{t('sponsorPortal.students.shown').replace('{count}', String(shown.length))}</span>
      </div>
      <p className="text-sm text-ground-600 mt-1 max-w-2xl">{t('sponsorPortal.students.intro')}</p>

      {/* Phones: one Filters button (the count of facets in use) and a Sheet of chips. */}
      <div className="mt-4 flex items-center justify-between gap-3 md:hidden">
        <button type="button" onClick={() => setSheetOpen(true)} aria-haspopup="dialog" data-testid="sponsor-filters-button"
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm font-semibold text-ground-700">
          <svg aria-hidden className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" d="M4 6h16M7 12h10M10 18h4" /></svg>
          {t('sponsorPortal.students.filters')}{picked > 0 ? ` · ${picked}` : ''}
        </button>
      </div>
      <SponsorFilterSheet open={sheetOpen} onClose={() => setSheetOpen(false)} groups={groups}
        count={shown.length} onClear={clearAll} />

      {/* From md: the row of selects — field / state / amount / status */}
      <div className="hidden md:flex flex-wrap gap-2 mt-5">
        <select value={field} onChange={(e) => setField(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPortal.students.allFields')}</option>
          {facets.fields.map((f) => <option key={f} value={f}>{getFieldName(f) || f}</option>)}
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPortal.students.allStates')}</option>
          {facets.states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={amount} onChange={(e) => setAmount(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPool.allAmounts')}</option>
          {facets.amounts.map((a) => <option key={a} value={a}>RM{rmWhole(a)}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectCls}>
          <option value="">{t('sponsorPortal.students.allStudents')}</option>
          <option value="open">{t('sponsorPortal.students.openForSponsorship')}</option>
          <option value="sponsored">{t('sponsorPortal.students.sponsored')}</option>
        </select>
      </div>

      {/* Anonymity note */}
      <div className="mt-4 rounded-lg bg-info-50 border border-info-100 px-4 py-2.5 text-xs text-info-800">
        {t('sponsorPool.anonymityNote')}
      </div>

      {/* Grid / empty states */}
      {pool === null ? (
        <p className="text-center text-ground-500 mt-12">{t('common.loading')}</p>
      ) : rows.length === 0 ? (
        <div className="text-center text-ground-500 mt-8 py-6 md:rounded-xl md:bg-ground-0 md:border md:border-dashed md:px-6 md:py-10">
          {t('sponsorPool.empty')}
        </div>
      ) : shown.length === 0 ? (
        <div className="text-center text-ground-500 mt-8 py-6 md:rounded-xl md:bg-ground-0 md:border md:border-dashed md:px-6 md:py-10">
          {t('sponsorPortal.students.filteredEmpty')}
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 md:mt-5 md:gap-5 lg:grid-cols-3">
          {shown.map((s) => <PoolCard key={s.id} s={s} />)}
        </div>
      )}
    </div>
  )
}

function PoolCard({ s }: { s: SponsorPoolCard }) {
  const { t } = useT()
  const cd = countdown(s.reporting_date)
  // Institution only — the home state next to it misleads (it's not where the institution is).
  const institutionLine = s.institution

  return (
    <Link href={`/sponsor/students/${s.id}`}
      className="flex flex-col overflow-hidden rounded-2xl border bg-ground-0 hover:border-info-300 hover:shadow-md transition">
      {/* Banner: field artwork + badges + ref pill */}
      <div className="relative h-[150px]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={fieldImageUrl(s.field_image_slug)} alt="" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/10 to-transparent" />
        <span className="absolute top-2 right-2 inline-flex items-center gap-1 rounded-full bg-ground-0/90 px-2 py-0.5 text-xs font-semibold text-positive-700 shadow-sm">
          🛡️ {t('sponsorPool.verified')}
        </span>
        {s.enrolment_verified && (
          <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-brand-fill/90 px-2 py-0.5 text-xs font-semibold text-brand-fill-ink shadow-sm">
            ✓ {t('sponsorPool.enrolmentVerified')}
          </span>
        )}
        <span className="absolute bottom-2 left-2 rounded-md bg-ground-0/90 px-2.5 py-0.5 text-xs font-bold text-ground-900 shadow-sm">
          {s.ref}
        </span>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-4 md:p-5">
        {(s.course || s.field) && (
          <p className="text-[15px] font-semibold text-ground-900 leading-snug">{s.course || s.field}</p>
        )}
        {institutionLine && <p className="text-xs text-ground-500 mt-0.5">{institutionLine}</p>}

        <div className="mt-3 flex flex-wrap gap-1.5">
          {s.academic && <span className="rounded-md bg-ground-100 px-2 py-0.5 text-xs font-medium text-ground-700">{s.academic}</span>}
          {s.funding_categories.slice(0, 3).map((c) => (
            <span key={c} className="rounded-md bg-info-50 px-2 py-0.5 text-xs font-medium text-info-700">{c}</span>
          ))}
        </div>

        {cd && (
          <p className="mt-3 text-xs font-medium text-caution-700">
            ⏳ {cd.kind === 'today' ? t('sponsorPool.startsToday')
              : cd.kind === 'one' ? t('sponsorPool.oneDayAway')
              : t('sponsorPool.daysAway').replace('{days}', String(cd.days))}
          </p>
        )}

        {s.blurb && <p className="mt-3 text-sm italic text-ground-600 leading-relaxed">{s.blurb}</p>}

        {/* Footer: pinned to the bottom so it aligns across cards of different heights.
            The funding bar doubles as the divider (no border-t), with symmetric spacing. */}
        <div className="mt-auto pt-3">
          <FundingBar funded={s.funded_amount} award={s.award_amount} />
          <div className="mt-3 flex items-center justify-between gap-2">
            {s.award_amount ? <span className="text-xl font-bold text-ground-900">RM{rmWhole(s.award_amount)}</span> : <span />}
            {s.funded
              ? <span className="rounded-md bg-ground-100 px-3 py-2 text-xs font-semibold text-ground-500">✓ {t('sponsorPool.funded')}</span>
              : <span className="rounded-md bg-brand-fill px-3 py-2 text-xs font-semibold text-brand-fill-ink">{t('sponsorPool.fullyFund')}</span>}
          </div>
        </div>
      </div>
    </Link>
  )
}
