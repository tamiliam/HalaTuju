'use client'

/**
 * WHICH GIFTS A REVIEWER COVERS (multi-gift tagging, owner design 2026-11-06).
 *
 * Three pieces, one look:
 *  - `GiftChips`     one grey chip per gift, or one soft blue "Every gift" chip (`[]`, the default);
 *  - `GiftTickList`  "Every gift" plus a tick per gift, the gifts greyed while "Every gift" is ticked
 *                    (the pencil pop-over below, the reviewer invite form and the sponsor invite form);
 *  - `ReviewerGiftsCell` the chips with a pencil beside them that opens the pop-over (Cancel / Save).
 *    Invitations I4 (2026-11-08): a MENTOR's gifts use the same cell (Team -> Mentors, the details box),
 *    passing their own `save` (`setMentorGifts`) and `errorOf` (the refusal that names a count).
 *
 * The tick rules are pure and tested in `lib/reviewerGifts`. The server is the authority: it refuses a
 * gift from another organisation (404) and blocks a new case outside these gifts (`gift_mismatch`).
 */
import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { setReviewerGifts, type AdminReviewerGift, type ReviewerGiftTag } from '@/lib/admin-api'
import {
  giftsForReviewer, idsToSave, tickEvery, tickGift, ticksFrom, type GiftTicks,
} from '@/lib/reviewerGifts'

/** The gifts as chips. `[]` is EVERY GIFT and reads as an answer, never as a blank. */
export function GiftChips({ gifts, testId }: { gifts: ReviewerGiftTag[]; testId?: string }) {
  const { t } = useT()
  return (
    <span className="inline-flex flex-wrap items-center gap-1" data-testid={testId}>
      {(gifts ?? []).length === 0 ? (
        <span className="rounded-full bg-info-100 px-2 py-0.5 text-xs font-semibold text-info-700">
          {t('admin.reviewers.gifts.every')}
        </span>
      ) : (gifts ?? []).map((g) => (
        <span key={g.id} className="rounded bg-ground-100 px-1.5 py-0.5 text-xs text-ground-600">
          {g.name}
        </span>
      ))}
    </span>
  )
}

/** "Every gift" and one tick per gift. Gifts are greyed (and cannot be ticked) while "Every gift" is on. */
export function GiftTickList({ ticks, options, onChange, everyLabel, testId, allowNone = false }: {
  ticks: GiftTicks
  /** `is_active: false` = a gift not open yet; it may still be staffed before it opens. */
  options: ReadonlyArray<{ id: number; name: string; is_active?: boolean }>
  onChange: (next: GiftTicks) => void
  everyLabel: string
  testId: string
  /** The sponsor invite (I3): clearing the last tick leaves NOTHING ticked, not "Every gift". */
  allowNone?: boolean
}) {
  const { t } = useT()
  const row = 'flex min-h-11 items-center gap-2.5 rounded-md px-1 text-sm'
  return (
    <div data-testid={testId}>
      <label className={`${row} font-semibold text-ground-900`}>
        <input type="checkbox" className="h-4 w-4 accent-primary-600" checked={ticks.every}
          data-testid={`${testId}-every`} onChange={(e) => onChange(tickEvery(ticks, e.target.checked))} />
        {everyLabel}
      </label>
      <div className="my-1 h-px bg-ground-200" />
      {options.map((g) => (
        <label key={g.id} className={`${row} ${ticks.every ? 'cursor-not-allowed text-ground-400' : 'text-ground-700'}`}>
          <input type="checkbox" className="h-4 w-4 accent-primary-600" disabled={ticks.every}
            checked={ticks.picked.includes(g.id)} data-testid={`${testId}-gift-${g.id}`}
            onChange={() => onChange(tickGift(ticks, g.id, allowNone))} />
          {g.name}
          {g.is_active === false && (
            <span className="text-xs text-ground-400">{t('admin.reviewers.detail.giftNotOpen')}</span>
          )}
        </label>
      ))}
    </div>
  )
}

/** The chips, and for someone who may change them a pencil that opens the pop-over. */
export default function ReviewerGiftsCell({ reviewer, options, token, canEdit, onSaved, save: saveIds, errorOf }: {
  reviewer: { id: number; name: string; gifts: ReviewerGiftTag[]; organisation_id?: number | null }
  options: AdminReviewerGift[]
  token: string | null
  canEdit: boolean
  onSaved: (gifts: ReviewerGiftTag[]) => void
  /** I4: who writes the ticks (default: the reviewer's `setReviewerGifts`). Answers the saved gifts. */
  save?: (ids: number[], token: string) => Promise<ReviewerGiftTag[]>
  /** I4: the words for a refusal (default: the generic "could not save"). */
  errorOf?: (err: unknown) => string
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const [ticks, setTicks] = useState<GiftTicks>(() => ticksFrom(reviewer.gifts ?? []))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const offered = giftsForReviewer(options, reviewer.organisation_id)

  const start = () => { setTicks(ticksFrom(reviewer.gifts ?? [])); setError(''); setOpen(true) }
  const save = async () => {
    if (!token) return
    setBusy(true); setError('')
    try {
      const gifts = saveIds
        ? await saveIds(idsToSave(ticks), token)
        : (await setReviewerGifts(reviewer.id, idsToSave(ticks), { token })).gifts
      onSaved(gifts); setOpen(false)
    } catch (err) {
      setError(errorOf ? errorOf(err) : t('admin.reviewers.detail.giftFailed'))
    } finally { setBusy(false) }
  }

  return (
    <span className="relative inline-flex flex-wrap items-center gap-1.5">
      <GiftChips gifts={reviewer.gifts ?? []} testId={`gifts-${reviewer.id}`} />
      {canEdit && (
        <button type="button" onClick={() => (open ? setOpen(false) : start())} aria-expanded={open}
          aria-label={t('admin.reviewers.gifts.edit', { name: reviewer.name })}
          data-testid={`gifts-edit-${reviewer.id}`}
          className={`inline-grid h-7 w-7 place-items-center rounded-md border bg-ground-0 max-md:min-h-11 max-md:min-w-11 ${
            open ? 'border-primary-600 text-primary-600'
                 : 'border-ground-200 text-ground-500 hover:border-primary-600 hover:text-primary-600'}`}>
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3.5 w-3.5">
            <path d="M13.6 2.6a2 2 0 0 1 2.8 2.8l-9 9-3.8 1 1-3.8 9-9z" />
          </svg>
        </button>
      )}
      {open && (
        <div role="dialog" aria-label={t('admin.reviewers.gifts.title', { name: reviewer.name })}
          data-testid={`gifts-pop-${reviewer.id}`}
          onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false) }}
          className="absolute left-0 top-full z-20 mt-1 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-ground-200 bg-ground-0 p-3 text-left shadow-lg">
          <p className="mb-1 text-sm font-semibold text-ground-900">
            {t('admin.reviewers.gifts.title', { name: reviewer.name })}
          </p>
          <GiftTickList ticks={ticks} options={offered} onChange={setTicks}
            everyLabel={t('admin.reviewers.gifts.everyDefault')} testId={`gifts-ticks-${reviewer.id}`} />
          {error && <p className="mt-2 text-xs text-critical-600" role="alert">{error}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setOpen(false)} disabled={busy}
              className="min-h-11 rounded-lg border border-ground-300 px-3.5 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
              {t('common.cancel')}
            </button>
            <button type="button" onClick={save} disabled={busy} data-testid={`gifts-save-${reviewer.id}`}
              className="min-h-11 rounded-lg bg-brand-fill px-3.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
              {t('common.save')}
            </button>
          </div>
        </div>
      )}
    </span>
  )
}
