'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { useFieldTaxonomy } from '@/hooks/useFieldTaxonomy'
import { fieldImageUrl } from '@/lib/fieldImage'
import { FundingBar } from '@/components/FundingBar'
import { countdown, rmWhole } from '@/lib/poolCard'
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
      (!amount || amtKey(r.award_amount) === amount)),
    [rows, field, state, amount],
  )

  const selectCls = 'text-sm border border-gray-200 rounded-lg pl-3.5 pr-9 py-2.5 bg-white min-w-[10rem] cursor-pointer'

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold text-gray-900">{t('sponsorPortal.students.title')}</h1>
        <span className="text-xs text-gray-400">{t('sponsorPortal.students.shown').replace('{count}', String(shown.length))}</span>
      </div>
      <p className="text-sm text-gray-600 mt-1 max-w-2xl">{t('sponsorPortal.students.intro')}</p>

      {/* Filters: field / state / amount */}
      <div className="flex flex-wrap gap-2 mt-5">
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
      </div>

      {/* Anonymity note */}
      <div className="mt-4 rounded-lg bg-blue-50 border border-blue-100 px-4 py-2.5 text-xs text-blue-800">
        {t('sponsorPool.anonymityNote')}
      </div>

      {/* Grid / empty states */}
      {pool === null ? (
        <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
      ) : rows.length === 0 ? (
        <div className="text-center text-gray-500 mt-8 rounded-xl bg-white border border-dashed px-6 py-10">
          {t('sponsorPool.empty')}
        </div>
      ) : shown.length === 0 ? (
        <div className="text-center text-gray-500 mt-8 rounded-xl bg-white border border-dashed px-6 py-10">
          {t('sponsorPortal.students.filteredEmpty')}
        </div>
      ) : (
        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
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
      className="flex flex-col overflow-hidden rounded-2xl border bg-white hover:border-blue-300 hover:shadow-md transition">
      {/* Banner: field artwork + badges + ref pill */}
      <div className="relative h-[150px]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={fieldImageUrl(s.field_image_slug)} alt="" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/10 to-transparent" />
        <span className="absolute top-2 right-2 inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-semibold text-green-700 shadow-sm">
          🛡️ {t('sponsorPool.verified')}
        </span>
        {s.enrolment_verified && (
          <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-blue-600/90 px-2 py-0.5 text-[11px] font-semibold text-white shadow-sm">
            ✓ {t('sponsorPool.enrolmentVerified')}
          </span>
        )}
        <span className="absolute bottom-2 left-2 rounded-md bg-white/90 px-2.5 py-0.5 text-xs font-bold text-gray-900 shadow-sm">
          {s.ref}
        </span>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-5">
        {(s.course || s.field) && (
          <p className="text-[15px] font-semibold text-gray-900 leading-snug">{s.course || s.field}</p>
        )}
        {institutionLine && <p className="text-xs text-gray-500 mt-0.5">{institutionLine}</p>}

        <div className="mt-3 flex flex-wrap gap-1.5">
          {s.academic && <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700">{s.academic}</span>}
          {s.funding_categories.slice(0, 3).map((c) => (
            <span key={c} className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">{c}</span>
          ))}
        </div>

        {cd && (
          <p className="mt-3 text-xs font-medium text-amber-700">
            ⏳ {cd.kind === 'today' ? t('sponsorPool.startsToday')
              : cd.kind === 'one' ? t('sponsorPool.oneDayAway')
              : t('sponsorPool.daysAway').replace('{days}', String(cd.days))}
          </p>
        )}

        {s.blurb && <p className="mt-3 text-sm italic text-gray-600 leading-relaxed">{s.blurb}</p>}

        {/* Footer: pinned to the bottom so it aligns across cards of different heights.
            The funding bar doubles as the divider (no border-t), with symmetric spacing. */}
        <div className="mt-auto pt-3">
          <FundingBar funded={s.funded_amount} award={s.award_amount} />
          <div className="mt-3 flex items-center justify-between gap-2">
            {s.award_amount ? <span className="text-xl font-bold text-gray-900">RM{rmWhole(s.award_amount)}</span> : <span />}
            {s.funded
              ? <span className="rounded-md bg-gray-100 px-3 py-2 text-xs font-semibold text-gray-500">✓ {t('sponsorPool.funded')}</span>
              : <span className="rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white">{t('sponsorPool.fullyFund')}</span>}
          </div>
        </div>
      </div>
    </Link>
  )
}
