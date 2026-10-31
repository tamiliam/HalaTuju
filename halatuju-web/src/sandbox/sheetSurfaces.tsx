'use client'

/**
 * The shared `Sheet`, mounted three ways for the owner's phone review (Mobile M1b, part 1).
 *
 * Kept out of `surfaces.tsx` (that file is on the oversize ledger and may not grow); `SURFACES`
 * spreads these in. Each surface opens its sheet at once, and a button reopens it after a close,
 * so a designer can try every way out: ×, backdrop, Escape, and the footer's own buttons.
 *
 * The words are the product's own strings (the award's guardian form, the decline confirm, the
 * course page's remove), so the Tamil and Malay screenshots show real Tamil and Malay at their
 * real lengths. The sheet is the real component; the data is invented, as everywhere here.
 */
import { useState, type ReactNode } from 'react'
import Sheet from '@/components/Sheet'
import { useT } from '@/lib/i18n'
/**
 * The shape `SURFACES` takes, written out here rather than imported: `surfaces.tsx` imports THIS
 * module, so importing its `Surface` type back would close an import loop (`importCycles.test.ts`).
 * The two shapes must agree, and the spread into `SURFACES` is what checks it.
 */
interface Surface { slug: string; title: string; note: string; render: () => ReactNode }

/** Opens on mount; "Open again" brings it back after any close. */
function Reopen({ children }: { children: (open: boolean, close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="space-y-3">
      {/* Sandbox chrome, so English like the rest of the picker. */}
      <button type="button" className="btn-secondary" onClick={() => setOpen(true)}>Open it again</button>
      {children(open, () => setOpen(false))}
    </div>
  )
}

function ShortSheet() {
  const { t } = useT()
  return (
    <Reopen>{(open, close) => (
      <Sheet open={open} onClose={close} title={t('courseDetail.removeFromSaved')} size="sm"
        footer={<>
          <button type="button" onClick={close}
            className="h-11 rounded-lg px-4 text-sm font-medium text-ground-600 hover:text-ground-900">
            {t('common.cancel')}
          </button>
          <button type="button" onClick={close}
            className="h-11 rounded-lg bg-critical-fill px-4 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover">
            {t('common.remove')}
          </button>
        </>}>
        <p className="text-sm text-ground-700">Diploma Kejuruteraan Mekanikal · Politeknik Teladan</p>
      </Sheet>
    )}</Reopen>
  )
}

function LongFormSheet() {
  const { t } = useT()
  const label = 'block text-sm font-medium text-ground-700 mb-1'
  const field = 'w-full rounded-lg border border-ground-300 px-3 py-2.5 text-sm focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none'
  return (
    <Reopen>{(open, close) => (
      <Sheet open={open} onClose={close} size="lg"
        title={t('scholarship.award.guardian.title')}
        description={t('scholarship.award.guardian.intro')}
        onSubmit={(e) => { e.preventDefault(); close() }}
        footer={<>
          <button type="button" onClick={close}
            className="h-11 rounded-lg px-4 text-sm font-medium text-ground-600 hover:text-ground-900">
            {t('scholarship.award.guardian.cancel')}
          </button>
          <button type="submit" className="btn-primary h-11 py-0">{t('scholarship.award.guardian.submit')}</button>
        </>}>
        <div className="space-y-4">
          <div>
            <label htmlFor="sg-name" className={label}>{t('scholarship.award.guardian.name')}</label>
            <input id="sg-name" autoComplete="name" className={field}
              placeholder={t('scholarship.award.guardian.namePlaceholder')} />
          </div>
          <div>
            <label htmlFor="sg-rel" className={label}>{t('scholarship.award.guardian.relationship')}</label>
            <select id="sg-rel" className={field} defaultValue="">
              <option value="" disabled>{t('scholarship.award.guardian.relationshipPlaceholder')}</option>
              <option value="mother">Ibu</option>
              <option value="father">Bapa</option>
              <option value="guardian">Penjaga</option>
            </select>
          </div>
          <div>
            <label htmlFor="sg-ic" className={label}>{t('scholarship.award.guardian.nric')}</label>
            <input id="sg-ic" inputMode="numeric" className={field} placeholder="XXXXXX-XX-XXXX" />
          </div>
          <div>
            <label htmlFor="sg-phone" className={label}>{t('profile.contactPhone')}</label>
            <input id="sg-phone" type="tel" autoComplete="tel-national" className={field} placeholder="012-345 6789" />
          </div>
          <div>
            <label htmlFor="sg-address" className={label}>{t('profile.address')}</label>
            <textarea id="sg-address" rows={3} autoComplete="street-address" className={field} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="sg-post" className={label}>{t('profile.postalCode')}</label>
              <input id="sg-post" inputMode="numeric" autoComplete="postal-code" className={field} placeholder="08000" />
            </div>
            <div>
              <label htmlFor="sg-city" className={label}>{t('profile.city')}</label>
              <input id="sg-city" autoComplete="address-level2" className={field} />
            </div>
          </div>
          <div>
            <label htmlFor="sg-note" className={label}>{t('contactForm.message')}</label>
            <textarea id="sg-note" rows={4} className={field} placeholder={t('contactForm.messagePlaceholder')} />
          </div>
        </div>
      </Sheet>
    )}</Reopen>
  )
}

function LockedConfirmSheet() {
  const { t } = useT()
  return (
    <Reopen>{(open, close) => (
      <Sheet open={open} onClose={close} dismissible={false} size="sm"
        title={t('scholarship.award.confirmed.decline')}
        footer={<>
          <button type="button" onClick={close} className="btn-secondary h-11 py-0">
            {t('common.cancel')}
          </button>
          <button type="button" onClick={close}
            className="h-11 rounded-lg bg-critical-fill px-4 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover">
            {t('scholarship.award.confirmed.decline')}
          </button>
        </>}>
        <p className="text-sm text-ground-700">{t('scholarship.award.declineConfirm')}</p>
      </Sheet>
    )}</Reopen>
  )
}

export const SHEET_SURFACES: Surface[] = [
  {
    slug: 'sheet-short',
    title: 'Sheet — a short confirm',
    note: 'The shared Sheet at its smallest: a title, one line and two actions. A bottom sheet on a '
      + 'phone, a centred dialog from md up. Closes by ×, backdrop, Escape or either button.',
    render: () => <ShortSheet />,
  },
  {
    slug: 'sheet-long-form',
    title: 'Sheet — a long form that scrolls',
    note: 'Seven fields: only the body scrolls, the title row and the footer stay put, and the '
      + 'footer clears the home bar. Every field is 16 px on a phone. Enter submits.',
    render: () => <LongFormSheet />,
  },
  {
    slug: 'sheet-locked-confirm',
    title: 'Sheet — must not vanish by accident',
    note: 'dismissible={false}: no ×, the backdrop and Escape do nothing. Only the two buttons '
      + 'close it — the shape for consent and sign-in steps.',
    render: () => <LockedConfirmSheet />,
  },
]
