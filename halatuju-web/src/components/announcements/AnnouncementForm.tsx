'use client'

import { useState } from 'react'
import Toggle from '@/components/Toggle'
import {
  createAnnouncement, updateAnnouncement,
  type AnnouncementAction, type AnnouncementAudience, type AnnouncementInput, type AnnouncementRow,
} from '@/lib/admin-api'

const K = 'admin.announcements'
/** The refusal codes the server sends that have their own words; anything else reads "could not save". */
const KNOWN = ['title_required', 'title_too_long', 'title_newline', 'body_required', 'body_too_long', 'bad_audience',
  'bad_publish_at', 'publish_at_past', 'published_locked', 'withdrawn']
const FIELD = 'w-full rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-ground-900 disabled:bg-ground-50 disabled:text-ground-500'
const LABEL = 'flex flex-col gap-1 text-sm font-medium text-ground-700'
const MYT = 'Asia/Kuala_Lumpur'

type T = (k: string, vars?: Record<string, string>) => string
export type Done = 'published' | 'scheduled' | 'draft' | 'saved'

/** A stored instant as the Malaysian date and 24-hour time the boxes show ('' when none). */
export function mytParts(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: '', time: '' }
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: MYT, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(iso))
  const v = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return { date: `${v('year')}-${v('month')}-${v('day')}`, time: `${v('hour')}:${v('minute')}` }
}

/** The boxes as one Malaysian instant for the server, or null when either box is not a valid value.
 *  ⚠ A TEXT box for the time, never `type="time"`: a 12-hour browser cannot take 21:30 there. */
export function mytInstant(date: string, time: string): string | null {
  const d = (date || '').trim().match(/^(\d{4})-(\d{2})-(\d{2})$/)
  const m = (time || '').trim().match(/^(\d{1,2}):(\d{2})$/)
  if (!d || !m) return null
  const h = parseInt(m[1], 10)
  const min = parseInt(m[2], 10)
  if (h > 23 || min > 59) return null
  return `${date.trim()}T${String(h).padStart(2, '0')}:${m[2]}:00+08:00`
}

/**
 * The New / Edit card on Programme → Announcements (the AnnouncementsAdmin board). One text for everyone:
 * a title and a plain-text message. Once an announcement is OUT (published), only the title, the message
 * and the pin can change — the audience, the timing and the email are shown but locked (the server refuses
 * them too, `published_locked`). An edit never emails again.
 */
export default function AnnouncementForm({ row, audiences, emailOn, limits, programme, token, t, onCancel, onSaved }: {
  row: AnnouncementRow | null
  audiences: AnnouncementAudience[]
  emailOn: boolean
  limits: { title: number; body: number }
  programme?: string
  token: string | null
  t: T
  onCancel: () => void
  onSaved: (row: AnnouncementRow, done: Done) => void
}) {
  const out = row?.status === 'published'
  const start = mytParts(row?.publish_at ?? null)
  const [title, setTitle] = useState(row?.title ?? '')
  const [body, setBody] = useState(row?.body ?? '')
  const [audience, setAudience] = useState(row?.programme?.code ?? '')
  const [later, setLater] = useState(!!row?.publish_at && !out)
  const [date, setDate] = useState(start.date)
  const [time, setTime] = useState(start.time)
  const [pinned, setPinned] = useState(row?.pinned ?? false)
  const [email, setEmail] = useState(row?.email_requested ?? false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async (action: AnnouncementAction | 'edit') => {
    if (!token) return
    setError('')
    const when = later ? mytInstant(date, time) : null
    if (action !== 'edit' && later && !when && (action === 'schedule' || date || time)) {
      setError(t(`${K}.error.badTime`)); return
    }
    let payload: Partial<AnnouncementInput>
    if (action === 'edit') {
      payload = { title, body, pinned }
    } else {
      payload = { title, body, pinned, email, programme: audience || null, action }
      if (when && action !== 'publish') payload.publish_at = when
    }
    setBusy(true)
    try {
      const saved = row
        ? await updateAnnouncement(row.id, payload, { token })
        : await createAnnouncement(payload as AnnouncementInput, programme, { token })
      onSaved(saved, action === 'edit' ? 'saved' : action === 'publish' ? 'published'
        : action === 'schedule' ? 'scheduled' : 'draft')
    } catch (err) {
      const code = (err as { code?: string })?.code ?? ''
      setError(t(`${K}.error.${KNOWN.includes(code) ? code : 'generic'}`))
    } finally { setBusy(false) }
  }

  const primary: AnnouncementAction = later ? 'schedule' : 'publish'
  return (
    <section className="max-w-3xl space-y-4 rounded-xl border-2 border-info-500 bg-ground-0 p-5" data-testid="announcement-form">
      <h2 className="text-base font-semibold text-ground-900">{t(row ? `${K}.form.editTitle` : `${K}.form.newTitle`)}</h2>
      <label className={LABEL}>{t(`${K}.form.title`)}
        <input value={title} maxLength={limits.title} onChange={(e) => setTitle(e.target.value)}
          data-testid="announcement-title" className={FIELD} />
      </label>
      <label className={LABEL}>{t(`${K}.form.body`)}
        <textarea value={body} maxLength={limits.body} rows={6} onChange={(e) => setBody(e.target.value)}
          data-testid="announcement-body" className={FIELD} />
      </label>
      <p className="text-xs text-ground-600">
        {t(`${K}.form.bodyHint`)} {t(`${K}.form.count`, { n: String(body.length), max: String(limits.body) })}
      </p>

      <div className="flex flex-wrap gap-4">
        <label className={`${LABEL} min-w-[16rem] flex-1`}>{t(`${K}.form.for`)}
          <select value={audience} disabled={out} onChange={(e) => setAudience(e.target.value)}
            data-testid="announcement-audience" className={FIELD}>
            {audiences.map((a) => (
              <option key={a.programme ?? ''} value={a.programme ?? ''}>
                {a.programme ? t(`${K}.forGift`, { name: a.name, count: String(a.count) })
                  : t(`${K}.forAll`, { count: String(a.count) })}
              </option>
            ))}
          </select>
        </label>
        {!out && (
          <label className={`${LABEL} min-w-[16rem] flex-1`}>{t(`${K}.form.when`)}
            <select value={later ? 'later' : 'now'} onChange={(e) => setLater(e.target.value === 'later')}
              data-testid="announcement-when" className={FIELD}>
              <option value="now">{t(`${K}.form.now`)}</option>
              <option value="later">{t(`${K}.form.later`)}</option>
            </select>
          </label>
        )}
      </div>
      {!out && later && (
        <div className="flex flex-wrap gap-4">
          <label className={LABEL}>{t(`${K}.form.date`)}
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
              data-testid="announcement-date" className={FIELD} />
          </label>
          <label className={LABEL}>{t(`${K}.form.time`)}
            <input value={time} inputMode="numeric" placeholder="09:30" onChange={(e) => setTime(e.target.value)}
              data-testid="announcement-time" className={`${FIELD} w-28`} />
          </label>
        </div>
      )}

      <div className="flex items-center gap-3">
        <Toggle on={pinned} onChange={setPinned} label={t(`${K}.form.pin`)} />
        <span className="text-sm text-ground-800">{t(`${K}.form.pin`)}</span>
      </div>
      <div className="flex items-start gap-3">
        <Toggle on={email} onChange={setEmail} disabled={out} label={t(`${K}.form.email`)} />
        <span className="text-sm text-ground-800">
          {t(`${K}.form.email`)}
          <span className="block text-xs text-ground-600">{t(emailOn ? `${K}.form.emailNote` : `${K}.form.emailOff`)}</span>
        </span>
      </div>

      {error && <p className="text-sm text-critical-600" role="alert" data-testid="announcement-error">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {out ? (
          <button type="button" disabled={busy} onClick={() => save('edit')} data-testid="announcement-save"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">
            {t(`${K}.btn.save`)}
          </button>
        ) : (<>
          <button type="button" disabled={busy} onClick={() => save(primary)} data-testid="announcement-primary"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">
            {t(`${K}.btn.${primary}`)}
          </button>
          <button type="button" disabled={busy} onClick={() => save('draft')} data-testid="announcement-draft"
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800 disabled:opacity-60">
            {t(`${K}.btn.draft`)}
          </button>
        </>)}
        <button type="button" disabled={busy} onClick={onCancel}
          className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-800">
          {t('common.cancel')}
        </button>
      </div>
      <p className="text-xs text-ground-600">{t(out ? `${K}.form.lockedNote` : `${K}.form.editNote`)}</p>
    </section>
  )
}
