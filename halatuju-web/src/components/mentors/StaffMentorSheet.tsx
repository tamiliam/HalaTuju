'use client'

import { useEffect, useMemo, useState } from 'react'
import Sheet from '@/components/Sheet'
import { addStaffMentor, getStaffMentorCandidates, mentorAction, type MentorRow, type StaffCandidate } from '@/lib/admin-api'

type T = (k: string, vars?: Record<string, string>) => string

const K = 'admin.mentors'
const REFUSALS = ['not_eligible', 'already_mentor', 'not_found', 'active', 'not_staff']

/** One line of the sheet: a staff member who never mentored (`addStaffMentor`, keyed by login id), or one
 *  removed from Mentors (`returning`: their own mentor row, brought back by `resume`, keyed by mentor id). */
type Option = { key: string; name: string; email: string; role: string; before: boolean; run: (token: string) => Promise<MentorRow> }

/**
 * "Add a staff member as mentor" (student maintenance S7d, 2026-11-01; the MentorsAddStaff board). The
 * shared Sheet: a search box over the organisation's ELIGIBLE staff who are not mentors yet (name, email,
 * role chip — `GET admin/mentors/staff/`, the server's list), one pick, one button. NO EMAIL is sent:
 * the sheet says so ("tell them yourself"). The server re-checks everything (`staff_mentor.add`).
 * Super and org_admin only — the page opens it for them alone.
 *
 * `returning`: staff mentors removed from Mentors (Team -> Mentors no longer lists them; owner ruling
 * 2026-11-08: Add Mentor brings them back). They keep their mentor record, so the server's list never
 * offers them and `add` would refuse `already_mentor`: they are offered here and brought back with the
 * existing `resume` door (`staff_mentor.resume`, which re-checks eligibility). Tagged "Mentored before".
 */
export default function StaffMentorSheet({ open, token, t, onClose, onAdded, returning = [] }: {
  returning?: MentorRow[]
  open: boolean
  token: string | null
  t: T
  onClose: () => void
  /** `back`: a removed staff mentor brought back (`resume`), not a first-time add. */
  onAdded: (row: MentorRow, back: boolean) => void
}) {
  const [staff, setStaff] = useState<StaffCandidate[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !token) return
    let live = true
    setStaff(null); setFailed(false); setQuery(''); setPicked(null); setError(null)
    getStaffMentorCandidates({ token })
      .then((d) => { if (live) setStaff(d.staff) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [open, token])

  const options = useMemo<Option[] | null>(() => {
    if (!staff) return null
    const fresh = staff.map((s): Option => ({ key: `s-${s.id}`, name: s.name, email: s.email, role: s.role,
      before: false, run: (tk) => addStaffMentor(s.id, { token: tk }) }))
    const back = returning.map((m): Option => ({ key: `m-${m.id}`, name: m.name, email: m.email,
      role: m.staff_role ?? '', before: true, run: (tk) => mentorAction(m.id, 'resume', { token: tk }) }))
    return [...fresh, ...back].sort((a, b) => a.name.localeCompare(b.name))
  }, [staff, returning])
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (options ?? []).filter((s) => !q || s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q))
  }, [options, query])
  const chosen = (options ?? []).find((s) => s.key === picked) ?? null

  const add = async () => {
    if (!token || !chosen) return
    setBusy(true); setError(null)
    try {
      const row = await chosen.run(token)
      onAdded({ ...row, name: row.name || chosen.name }, chosen.before)
    } catch (err) {
      const code = (err as { code?: string })?.code ?? ''
      setError(t(`${K}.error.${REFUSALS.includes(code) ? code : 'generic'}`))
    } finally { setBusy(false) }
  }

  return (
    <Sheet open={open} onClose={onClose} busy={busy} title={t(`${K}.staffSheet.title`)}
      description={t(`${K}.staffSheet.intro`)} size="lg" testId="staff-mentor-sheet"
      footer={(
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={add} disabled={!chosen || busy} data-testid="staff-mentor-add"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {chosen ? t(`${K}.staffSheet.add`, { name: chosen.name }) : t(`${K}.staffSheet.choose`)}
          </button>
          <button type="button" onClick={onClose} disabled={busy}
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-700 hover:bg-ground-50">
            {t('common.cancel')}
          </button>
        </div>
      )}>
      <div className="space-y-3">
        <label className="block text-sm text-ground-600">
          {t(`${K}.staffSheet.search`)}
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2 focus:border-info-500 focus:ring-2 focus:ring-info-500" />
        </label>
        {failed && <p className="text-sm text-critical-600" role="alert">{t(`${K}.staffSheet.loadError`)}</p>}
        {!staff && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}
        {staff && (shown.length === 0 ? (
          <p className="text-sm text-ground-500" data-testid="staff-mentor-none">
            {t(options?.length ? `${K}.staffSheet.noMatch` : `${K}.staffSheet.none`)}
          </p>
        ) : (
          <div role="listbox" aria-label={t(`${K}.staffSheet.search`)}
            className="divide-y rounded-lg border border-ground-200">
            {shown.map((s) => (
              <button key={s.key} type="button" role="option" aria-selected={picked === s.key}
                onClick={() => setPicked(s.key)} data-testid={s.before ? `staff-returning-${s.key.slice(2)}` : `staff-candidate-${s.key.slice(2)}`}
                className={`flex min-h-11 w-full flex-wrap items-center justify-between gap-2 px-3 py-2 text-left text-sm ${picked === s.key
                  ? 'bg-info-50 text-info-900' : 'text-ground-800 hover:bg-ground-50'}`}>
                <span className="min-w-0 break-words"><strong>{s.name}</strong> · {s.email}</span>
                <span className="flex flex-wrap gap-1">
                  {s.before && (
                    <span className="rounded-full bg-info-50 px-2.5 py-0.5 text-xs text-info-800">
                      {t(`${K}.staffSheet.before`)}
                    </span>
                  )}
                  <span className="rounded-full bg-ground-100 px-2.5 py-0.5 text-xs text-ground-700">
                    {t(`admin.role.${s.role}`)}
                  </span>
                </span>
              </button>
            ))}
          </div>
        ))}
        <p className="text-xs text-ground-500">{t(`${K}.staffSheet.shown`)}</p>
        {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      </div>
    </Sheet>
  )
}
