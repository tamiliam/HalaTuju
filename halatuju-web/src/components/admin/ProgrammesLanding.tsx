'use client'

// Organisation → Programmes — everyone's front door on the partner login (T5c P5, owner 2026-11-04).
//
// TWO DRAWINGS, ONE PAGE:
//  * whoever may step INTO a gift (`hasGiftDoor`: the served `programmes.edit` key, TD-623 — not a role label)
//    gets the full card grid they already know (`GiftProgrammes.tsx` — reused, not copied), with its New / Change code / Delete;
//  * everyone else gets the narrowed `my-programmes` cards: the programmes where THEY have work, each with
//    only the counts the server chose to send for this caller.
//
// ⚠ A MISSING COUNT MEANS "DO NOT SHOW", NEVER ZERO. The server decides which counts a caller may see (an admin
// keeps today's three; a reviewer sees "Cases assigned to you"; a mentor "Scholars you mentor"). Printing 0 for
// an absent key would state a fact the server never stated.
//
// ⚠ THE FENCE IS THE ENDPOINT. The card list and its links are what the server returned; opening a card only
// takes the reader to a page that checks again.

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { hasGiftDoor } from '@/lib/navigation'
import { useProgrammeScope } from '@/lib/programmeScope'
import { withGift } from '@/lib/giftHref'
import { PHONE_CARD_XL } from '@/lib/phoneConsole'
import { PHONE_PILL_SM } from '@/lib/phonePill'
import { getMyProgrammes, type MyProgramme } from '@/lib/admin-api/myProgrammes'
import { getVerdictMetrics, type VerdictMetrics } from '@/lib/admin-api/verdict'
import GiftProgrammes from './GiftProgrammes'
import { AiPredictionBlock } from './overview/AiPredictionSection'
import PendingCards from './PendingCards'

/** The counts a card may carry, in reading order, with the label each one wears. */
const COUNTS = [
  ['intake_years', 'admin.programmes.col.years'],
  ['applications', 'admin.programmes.col.applications'],
  ['awarded', 'admin.programmes.col.awarded'],
  ['cases', 'admin.programmes.landing.cases'],
  ['scholars', 'admin.programmes.landing.scholars'],
] as const

/** Where a card opens: the gift's Overview, or the mentor's own students narrowed to this gift. */
export function cardHref(p: MyProgramme): string {
  return p.opens === 'my_students'
    ? `/admin/my-students?programme=${p.id}`
    : withGift('/admin/programme/overview', p.code)
}

export default function ProgrammesLanding() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  // ⚠ T5c P5b (owner 2026-11-05): ONE page called Overview — the caller's pending cards on top, the programme
  // cards below. The pending strip is drawn in THIS chunk (no new async chunk: the bundle median has no room).
  return (
    <div data-testid="overview">
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.orgPage.nav')}</h1>
      <PendingCards token={token} />
      {hasGiftDoor(role?.page_keys) ? <GiftProgrammes token={token} /> : <MyProgrammesCards token={token} />}
      <OrganisationAiPrediction token={token} />
    </div>
  )
}

/**
 * LL1: the AI prediction block for ALL programmes together, at the foot of the page.
 *
 * ⚠ THE SERVER DECIDES WHO MAY SEE IT. A 403 (or any other failure) draws NOTHING: no banner, no console
 * noise. A reader the server refuses simply has no such block, and a page that apologised for a thing
 * that reader never had would be the noise.
 */
function OrganisationAiPrediction({ token }: { token: string | null }) {
  const { t } = useT()
  const [ai, setAi] = useState<VerdictMetrics | null>(null)

  useEffect(() => {
    if (!token) return
    let live = true
    getVerdictMetrics({ token })
      .then((d) => { if (live) setAi(d) })
      .catch(() => { /* a refusal or a failure draws nothing */ })
    return () => { live = false }
  }, [token])

  if (!ai) return null
  return (
    <div className="mt-8">
      <AiPredictionBlock ai={ai} t={t} note={t('admin.programmeOverview.aiPrediction.allProgrammes')} />
    </div>
  )
}

function MyProgrammesCards({ token }: { token: string | null }) {
  const { t, locale } = useT()
  const { select } = useProgrammeScope()
  const [data, setData] = useState<{ every_gift: boolean; programmes: MyProgramme[] } | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    getMyProgrammes({ token })
      .then((d) => { if (live) setData(d) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [token])

  const nameOf = (p: MyProgramme) =>
    (p as unknown as Record<string, string | undefined>)[`name_${locale}`] || p.name_en

  return (
    <section data-testid="my-programmes" className="mt-8">
      <h2 className="text-lg font-semibold text-ground-900">{t('admin.programmes.landing.title')}</h2>
      {data && (
        <p className="mt-0.5 text-sm text-ground-600">
          {data.every_gift ? t('admin.programmes.subtitle') : t('admin.programmes.landing.workSub')}
        </p>
      )}

      {failed && <p className="mt-4 text-sm text-critical-600">{t('admin.programmes.loadFailed')}</p>}
      {!data && !failed && <p className="mt-4 text-sm text-ground-400">{t('common.loading')}</p>}

      {data && data.programmes.length === 0 && (
        <div data-testid="my-programmes-empty"
          className="mt-6 rounded-2xl border border-dashed border-ground-300 px-4 py-10 text-center">
          <p className="text-base font-semibold text-ground-900">{t('admin.programmes.landing.emptyTitle')}</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-ground-600">{t('admin.programmes.landing.emptyBody')}</p>
          <p className="mt-4 text-xs text-ground-500">{t('admin.programmes.landing.emptyFoot')}</p>
        </div>
      )}

      {data && data.programmes.length > 0 && (
        <ul className="mt-4 grid sm:grid-cols-2 sm:gap-3">
          {data.programmes.map((p) => (
            <li key={p.id}>
              <Link href={cardHref(p)} data-testid={`my-programme-${p.code}`}
                onClick={p.opens === 'overview'
                  // An ARCHIVED gift is not in the scopes list (active only): the card vouches for it.
                  ? () => (p.archived ? select(p.code, { code: p.code, name: nameOf(p), isActive: false }) : select(p.code))
                  : undefined}
                className={`block ${PHONE_CARD_XL} transition-colors md:shadow-sm md:hover:border-primary-300`}>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-ground-900">{nameOf(p)}</h2>
                  {p.archived && (
                    <span data-testid="archived-pill"
                      className={`rounded-full bg-ground-100 px-2 py-0.5 text-xs font-medium text-ground-600 ${PHONE_PILL_SM}`}>
                      {t('admin.programmes.lifecycle.archived')}
                    </span>
                  )}
                </div>
                <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
                  {COUNTS.filter(([k]) => typeof p[k] === 'number').map(([k, label]) => (
                    <div key={k} data-testid={`count-${k}`}>
                      <dt className="text-xs font-semibold uppercase tracking-wider text-ground-400 md:text-[10px]">
                        {t(label)}
                      </dt>
                      <dd className="mt-0.5 text-sm font-semibold tabular-nums text-ground-700">{p[k]}</dd>
                    </div>
                  ))}
                </dl>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
