'use client'

// Programme → Intake years (Sabah S2b, 2026-09-02). Fills the slot the programme-layer roadmap
// reserved and left as a "Soon" placeholder.
//
// One round of students per year, beneath a gift that never lapses. Two things here are deliberate
// and must not be "simplified":
//
// ⚠ CREATING NEVER OPENS. The button says so. `is_open` defaults to TRUE on the model, so a form
// that just created a row would let real students in with the same press. Opening is the moment an
// intake becomes real, and it gets its own action.
//
// ⚠ ONE OPEN ROUND PER ORGANISATION, and the server refuses the second. `resolve_open_cohort`
// already RAISES on two open rounds — because picking one files a student under the wrong fence
// (PF-1) — but that refusal reaches the STUDENT at the moment they press Apply. This screen shows
// which round is open before the admin creates the ambiguity.

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import InfoBox from '@/components/InfoBox'
import {
  getAdminProgrammes, getAdminIntakeYears, createAdminIntakeYear, updateAdminIntakeYear,
  type AdminIntakeYear, type AdminProgramme,
} from '@/lib/admin-api'
// ⚠ In `lib`, not beside this page: a page module may carry NO export beyond its default, and
// `next build` is the only gate that says so (Layer 1 F7c, three times).
import {
  draftToRequirements, EMPTY_REQUIREMENTS, type RequirementDraft,
} from '@/lib/intakeYears'

const CODE_OK = /^[a-z0-9][a-z0-9-]{1,49}$/

export default function AdminIntakeYearsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const params = useSearchParams()
  const mayView = canAccess('/admin/programme/years', effectiveRole(role))

  const [programmes, setProgrammes] = useState<AdminProgramme[]>([])
  const [programmeId, setProgrammeId] = useState<number | null>(null)
  const [years, setYears] = useState<AdminIntakeYear[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ year: '', code: '', name: '' })
  const [draft, setDraft] = useState<RequirementDraft>(EMPTY_REQUIREMENTS)

  // Which gift are we looking at? The breadcrumb switcher is a DISPLAY preference and does not
  // drive page content (its own docstring says so), so the programme is named in the URL, or
  // resolved when the organisation runs exactly one — the same shape the Layer 0 config screen uses.
  useEffect(() => {
    if (!token || !mayView) { setLoading(false); return }
    getAdminProgrammes({ token })
      .then((d) => {
        setProgrammes(d.programmes)
        const asked = Number(params?.get('programme') || '')
        const found = d.programmes.find((p) => p.id === asked)
        setProgrammeId(found ? found.id : (d.programmes.length === 1 ? d.programmes[0].id : null))
      })
      .catch(() => setError(t('admin.years.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, mayView])

  const load = useCallback(async () => {
    if (!token || programmeId === null) return
    try {
      setYears((await getAdminIntakeYears(programmeId, { token })).years)
      setError('')
    } catch {
      setError(t('admin.years.loadFailed'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, programmeId])

  useEffect(() => { void load() }, [load])

  const programme = useMemo(
    () => programmes.find((p) => p.id === programmeId) ?? null, [programmes, programmeId])
  const openElsewhere = useMemo(() => years.find((y) => y.is_open) ?? null, [years])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const errKey = (c?: string) =>
    c === 'bad_code' ? 'badCode'
      : c === 'code_taken' ? 'codeTaken'
        : c === 'bad_year' ? 'badYear'
          : c === 'another_year_open' ? 'anotherOpen'
            : c === 'programme_not_active' ? 'notActive'
              : c === 'name_required' ? 'nameRequired' : 'generic'

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try { await fn(); await load(); return true } catch (e) {
      setError(t(`admin.years.error.${errKey((e as { code?: string })?.code)}`)); return false
    } finally { setBusy(false) }
  }

  const create = async () => {
    if (programmeId === null) return
    const ok = await run(() => createAdminIntakeYear(programmeId, {
      code: form.code.trim().toLowerCase(), name: form.name.trim(), year: Number(form.year),
      ...draftToRequirements(draft),
    }, { token: token! }))
    if (ok) { setOpen(false); setForm({ year: '', code: '', name: '' }); setDraft(EMPTY_REQUIREMENTS) }
  }

  const inputCls = 'w-full rounded-lg border border-ground-300 px-3 py-2 text-sm'
    + ' focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'
  const miniCls = 'w-24 rounded-lg border border-ground-300 px-2.5 py-1.5 text-sm text-right'
    + ' tabular-nums focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'

  /** One requirement: a tick box that writes a value, and clearing the value unticks it. There is
   *  deliberately no separate on/off state to hold — the value IS the switch (S2a). */
  const Req = ({ id, label, hint, value, onChange }: {
    id: string; label: string; hint?: string; value: string; onChange: (v: string) => void
  }) => (
    <label htmlFor={id} className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${
      value.trim() ? 'border-primary-200 bg-primary-50/50' : 'border-ground-200 bg-ground-0'}`}>
      <input type="checkbox" checked={value.trim() !== ''} aria-label={label}
        onChange={(e) => onChange(e.target.checked ? '0' : '')}
        className="h-4 w-4 shrink-0 accent-primary-600" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-ground-900">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-ground-500">{hint}</span>}
      </span>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder="—" inputMode="decimal" className={miniCls} />
    </label>
  )

  return (
    <div className="max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t('admin.years.title')}</h1>
          <p className="mt-1 text-sm text-ground-600">
            {programme ? `${programme.name_en} — ` : ''}{t('admin.years.subtitle')}
          </p>
        </div>
        {programme && (
          <button type="button" onClick={() => { setError(''); setOpen(true) }}
            className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
            + {t('admin.years.new')}
          </button>
        )}
      </div>

      {error && <div className="mt-4"><InfoBox kind="block">{error}</InfoBox></div>}

      {!loading && programme === null && (
        <div className="mt-6 rounded-xl border border-ground-200 bg-ground-0 p-4">
          <p className="text-sm font-medium text-ground-800">{t('admin.years.chooseProgramme')}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {programmes.map((p) => (
              <button key={p.id} type="button" onClick={() => setProgrammeId(p.id)}
                className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm hover:bg-ground-50">
                {p.name_en}
              </button>
            ))}
            {programmes.length === 0 && (
              <Link href="/admin/organisation/programmes"
                className="text-sm font-medium text-primary-600 hover:underline">
                {t('admin.years.noProgrammes')}
              </Link>
            )}
          </div>
        </div>
      )}

      {programme && (
        <>
          <div className="mt-6 overflow-hidden rounded-2xl border border-ground-200 bg-ground-0 shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b border-ground-200 bg-ground-50">
                <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
                  {(['year', 'name', 'applications', 'status'] as const).map((k) => (
                    <th key={k} className="px-4 py-3 font-semibold">{t(`admin.years.col.${k}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ground-100">
                {years.map((y) => (
                  <tr key={y.id} data-testid={`year-${y.code}`}>
                    <td className="px-4 py-3 tabular-nums text-ground-700">{y.year}</td>
                    <td className="px-4 py-3 text-ground-700">{y.name}</td>
                    <td className="px-4 py-3 tabular-nums text-ground-700">{y.applications}</td>
                    <td className="px-4 py-3">
                      <span className="flex flex-wrap items-center gap-3">
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          y.is_open ? 'bg-positive-100 text-positive-800' : 'bg-ground-100 text-ground-600'}`}>
                          {t(y.is_open ? 'admin.years.open' : 'admin.years.closed')}
                        </span>
                        <button type="button" disabled={busy}
                          onClick={() => run(() => updateAdminIntakeYear(
                            y.id, { is_open: !y.is_open }, { token: token! }))}
                          className="text-xs font-medium text-primary-600 hover:underline disabled:opacity-50">
                          {t(y.is_open ? 'admin.years.close' : 'admin.years.openIt')}
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
                {years.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-ground-400">
                    {t('admin.years.empty')}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4">
            <InfoBox kind="warning">
              {openElsewhere
                ? t('admin.years.oneOpenNamed', { code: openElsewhere.name })
                : t('admin.years.oneOpen')}
            </InfoBox>
          </div>
        </>
      )}

      {open && programme && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4"
          onClick={() => !busy && setOpen(false)}>
          <div className="my-8 w-full max-w-lg rounded-2xl bg-ground-0 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.years.new')}</h2>

            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="y-year" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.year')}
                </label>
                <input id="y-year" inputMode="numeric" value={form.year}
                  onChange={(e) => setForm({ ...form, year: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
              <div>
                <label htmlFor="y-code" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.code')}
                </label>
                <input id="y-code" value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
            </div>
            <div className="mt-4">
              <label htmlFor="y-name" className="block text-sm font-medium text-ground-700">
                {t('admin.years.field.name')}
              </label>
              <input id="y-name" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={`mt-1 ${inputCls}`} />
            </div>

            <hr className="mt-5 border-ground-100" />
            <p className="mt-4 text-sm font-semibold text-ground-700">{t('admin.years.reqTitle')}</p>
            <p className="mt-0.5 text-xs text-ground-500">{t('admin.years.reqHint')}</p>

            <div className="mt-3 space-y-2">
              <Req id="r-a" label={t('admin.years.req.spmA')} value={draft.aCount}
                onChange={(v) => setDraft({ ...draft, aCount: v })} />
              <Req id="r-b" label={t('admin.years.req.spmB')} hint={t('admin.years.req.spmBHint')}
                value={draft.spmExtra} onChange={(v) => setDraft({ ...draft, spmExtra: v })} />
              <Req id="r-p" label={t('admin.years.req.pngk')} value={draft.pngk}
                onChange={(v) => setDraft({ ...draft, pngk: v })} />
              <Req id="r-m" label={t('admin.years.req.merit')} hint={t('admin.years.req.meritHint')}
                value={draft.merit} onChange={(v) => setDraft({ ...draft, merit: v })} />
              <Req id="r-i" label={t('admin.years.req.income')} value={draft.income}
                onChange={(v) => setDraft({ ...draft, income: v })} />
              <Req id="r-c" label={t('admin.years.req.perPerson')} hint={t('admin.years.req.perPersonHint')}
                value={draft.perPerson} onChange={(v) => setDraft({ ...draft, perPerson: v })} />
            </div>

            {error && <p className="mt-3 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setOpen(false)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              {/* The label carries the promise: creating never opens. */}
              <button type="button" onClick={create}
                disabled={busy || !form.name.trim() || !form.year.trim()
                  || !CODE_OK.test(form.code.trim().toLowerCase())}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.years.createClosed')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
