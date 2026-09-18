'use client'
/**
 * Programme Overview — the page you land on inside a gift, and the answer to "how is this doing?".
 *
 * ⚠⚠ **THE PAGE RENDERS WHAT ARRIVED, NEVER WHAT A ROLE "SHOULD" SEE.** `SECTIONS_BY_ROLE` on the
 * server chooses the key set before anything is serialised, so a reviewer's payload has no `money`
 * key at all and a finance admin's has no `funnel`. Every block is gated on `has(data, …)` and on
 * nothing else. There is deliberately no `if (role === …)` in this file: a page that fetched
 * everything and drew a subset would be a side door into Payments and Spending for the two roles
 * the menu already withholds them from, and a client-side gate is one edit away from being wrong.
 *
 * ⚠⚠ **`sections` IS AN ORDER, NOT A SET** (phase 2). The server narrows the role's sections by the
 * organisation's saved layout and sends them arranged; this page maps that list through
 * `SECTION_RENDERERS` and draws nothing of its own accord. A run of fixed JSX here would be a
 * second spelling of the order — and the one that silently won.
 *
 * ⚠⚠ **THE CUSTOMISE BUTTON IS SHOWN BY THE PRESENCE OF `data.layout`, NEVER BY A ROLE CHECK.**
 * The server sends `layout` to an org_admin and a super and to nobody else; asking "did it arrive?"
 * is the same doctrine as `has()`, for the same reason.
 *
 * ⚠ **MONEY IS A STRING FROM THE SERVER TO THE SCREEN** (`OverviewSections.tsx`). Nothing parsed
 * is ever displayed.
 *
 * ⚠ **THE REPORT DATE SITS AT THE TOP, ONCE** — the same rule the Spending page follows. It is a
 * fact about the WHOLE page (every spending figure stops there), not about one section, and it is
 * derived from the newest transaction we hold rather than written down anywhere.
 *
 * ⚠ **AN INTAKE IS A FILTER ON EVERYTHING, OR ON NOTHING.** Choosing a round narrows every figure
 * on the page — the money strip and the report date included — because a page where half the
 * panels answered about one year and half about all of them would be unreadable. A stale round id
 * (the gift changed underneath it, or somebody pasted a URL) answers 404, and the page CLEARS the
 * round and reads again rather than showing an error nobody can act on.
 *
 * ⚠ **SEVERAL GIFTS AND NONE CHOSEN IS A REAL STATE, AND IT GETS A NEUTRAL HEADING** — never
 * `ChooseProgramme`. This page READS; with nothing chosen it describes everything the organisation
 * fence allows, which is a true answer, just a less specific one. That is the line the Applications
 * and Payments pages already draw (`NavItem.needsProgramme`), and it is why this row carries no
 * `needsProgramme` of its own.
 */

import { useCallback, useEffect, useState } from 'react'

import CustomiseLayout from '@/components/admin/overview/CustomiseLayout'
import IntakePicker from '@/components/admin/overview/IntakePicker'
import { SECTION_RENDERERS } from '@/components/admin/overview/OverviewSections'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getProgrammeOverview, type ProgrammeOverview } from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { has } from '@/lib/programmeOverview'
import { useProgrammeParam } from '@/lib/programmeScope'

const K = 'admin.programmeOverview'

export default function ProgrammeOverviewPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = canAccess('/admin/programme/overview', effectiveRole(role))
  // ⚠ WHICH GIFT — from the breadcrumb, sent as an EXPLICIT value the server re-fences on the
  // caller's own organisation (TD-241). `undefined` when several gifts exist and none is chosen;
  // the scope refuses to guess and the server then answers with everything the fence allows.
  const programme = useProgrammeParam()

  const [data, setData] = useState<ProgrammeOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [customising, setCustomising] = useState(false)

  /**
   * ⚠ THE CHOSEN ROUND IS REMEMBERED **WITH THE GIFT IT BELONGS TO**, and the filter is derived
   * from the pair rather than cleared by an effect. A round belongs to one gift, so the moment the
   * breadcrumb moves, last gift's round is not a stale value to tidy up later — it is already not
   * a round of this gift. Clearing it in a `useEffect` would let one render (and therefore one
   * fetch) go out carrying the wrong id, which is the 404 this page then has to recover from.
   */
  const [chosenIntake, setChosenIntake] = useState<{ gift?: string; id?: number }>({})
  const intake = chosenIntake.gift === programme ? chosenIntake.id : undefined

  const load = useCallback(() => {
    if (!token || !allowed) { setLoading(false); return }
    setLoading(true)
    setError('')
    getProgrammeOverview({ programme, intake }, { token })
      .then(setData)
      .catch((e) => {
        // ⚠ A 404 IS THE FENCE'S OWN ANSWER ABOUT THE ROUND — "there is no such thing", never
        // "you may not" (`_gift_narrowing`). Dropping the round and reading again puts the person
        // back on a page that works; an error message about a cohort id would not.
        const err = e as Error & { status?: number }
        if (err.status === 404 && intake !== undefined) {
          setChosenIntake({ gift: programme, id: undefined })
          return
        }
        setError(t(`${K}.error`))
      })
      .finally(() => setLoading(false))
    // ⚠ `programme` AND `intake` ARE DEPENDENCIES. Switching gift in the breadcrumb, or picking a
    // round, must re-read — or the crumb would name one gift while the figures described another.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed, programme, intake])

  useEffect(() => { load() }, [load])

  if (role && !allowed) {
    return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const layout = data?.layout
  const editing = customising && layout !== undefined

  return (
    <div data-testid="programme-overview">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-ground-900">
            {data?.programme
              ? t(`${K}.titleFor`, { name: data.programme.name })
              : t(`${K}.title`)}
          </h1>
          <p className="mt-1 text-sm text-ground-600">{t(`${K}.subtitle`)}</p>
          {/* ⚠ THE ROUND IS NAMED BESIDE THE TITLE when one is chosen. Every figure below is
              narrowed to it, so a page that showed the narrowed numbers under the gift's own
              heading would be quietly answering a different question from the one it printed. */}
          {data?.intake && (
            <p className="mt-1 text-sm text-ground-600" data-testid="overview-describing">
              {t(`${K}.intakes.describing`, { name: data.intake.name })}
            </p>
          )}
          {data?.data_to && (
            <p className="mt-1 text-sm text-ground-500" data-testid="overview-data-to">
              {t(`${K}.asAt`, { date: formatDate(data.data_to) })}
            </p>
          )}
          {!editing && (
            <IntakePicker intakes={data?.intakes ?? []} value={intake}
              onChange={(id) => setChosenIntake({ gift: programme, id })} />
          )}
        </div>

        {layout && !editing && (
          <button type="button" data-testid="customise-button"
            onClick={() => setCustomising(true)}
            className="rounded-lg border border-ground-300 bg-ground-0 px-3 py-1.5 text-sm font-medium text-ground-700 hover:bg-ground-50">
            {t(`${K}.customise.button`)}
          </button>
        )}
      </div>

      {error && <p className="mt-4 text-sm text-critical-600" role="alert">{error}</p>}
      {loading && !data && <p className="mt-4 text-sm text-ground-500">{t(`${K}.loading`)}</p>}

      {editing && layout && (
        <CustomiseLayout
          initial={layout}
          onSaved={() => { setCustomising(false); load() }}
          onCancel={() => setCustomising(false)}
        />
      )}

      {/* ⚠ THE ORDER IS THE SERVER'S. An unknown key is SKIPPED rather than drawn as an error: the
          API ships separately from this bundle, so a widget added on the Python side arrives here
          before the renderer map knows it exists. */}
      {!editing && data && data.sections.map((key) => {
        const Section = SECTION_RENDERERS[key]
        if (!Section || !has(data, key)) return null
        return <Section key={key} data={data} t={t} />
      })}

      {/* ⚠ AN EMPTY OVERVIEW IS A 200, AND IT IS SOMEBODY'S OWN DOING. An organisation that
          switched off every panel a finance admin can see gets this notice — not a refusal, which
          would claim an entitlement problem that does not exist. */}
      {!editing && data && data.sections.length === 0 && (
        <p className="mt-6 text-sm text-ground-500" data-testid="overview-all-hidden">
          {t(`${K}.allHidden`)}
        </p>
      )}
    </div>
  )
}
