'use client'

/**
 * The award page's agreement reader and its decline question (Mobile M4, owner-approved mock).
 *
 * THE CONTRACT TEXT IS NEVER CHANGED. The server renders the agreement for PRINT (11 px body, 9 px
 * notes, two-column tables), which in a phone-width box is unreadable. `phoneContractHtml` only
 * PREPENDS a stylesheet that applies inside a narrow frame (16 px, wrapping tables); every byte of the
 * server's HTML follows it unchanged (tested). What is signed is still re-rendered, hashed and stamped
 * on the server at the moment of signing (`bursary.sign_agreement`) — this preview is never the record.
 *
 * Phones: a "Read the full agreement" button opens the text in a tall sheet — no 448 px scroll box
 * trapping the thumb inside the page. From `md` the inline frame stays as it was. The frame keeps
 * `sandbox=""`: the document cannot run script or reach the page.
 */
import { useRef, useState } from 'react'
import Sheet from '@/components/Sheet'
import { useT } from '@/lib/i18n'

/** Applies only inside a narrow frame (the phone reader); a desktop-width frame is untouched. */
export const PHONE_CONTRACT_CSS = '<style data-phone-reader>@media (max-width: 640px){'
  + 'body{font-size:16px!important;line-height:1.55!important;margin:16px!important;overflow-wrap:anywhere}'
  + 'body *{font-size:inherit!important;max-width:100%}'
  + 'h1{font-size:20px!important}h2,h3{font-size:17px!important}'
  + 'table{width:100%!important;table-layout:fixed}td,th{display:block;width:auto!important}'
  + '}</style>'

/** The server's agreement HTML with the phone stylesheet in FRONT of it — the HTML itself unchanged. */
export function phoneContractHtml(html: string): string {
  return PHONE_CONTRACT_CSS + html
}

export function AwardContractReader({ html }: { html: string }) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const title = t('scholarship.award.bursary.documentTitle')
  const doc = phoneContractHtml(html)
  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-ground-500">{title}</h2>
      {/* Phones: one big button → the reader sheet. */}
      <button type="button" onClick={() => setOpen(true)} data-testid="award-read-agreement"
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-brand-shape bg-ground-0 px-4 font-semibold text-primary-600 hover:bg-primary-50 md:hidden">
        <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 3h7l5 5v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1zM9 13h6M9 17h6" />
        </svg>
        {t('scholarship.award.bursary.readFull')}
      </button>
      {/* From md: the inline frame, as before. */}
      <iframe title={title} sandbox="" srcDoc={doc}
        className="hidden h-[28rem] w-full rounded-2xl border bg-ground-0 shadow-inner md:block" />
      {open && (
        <Sheet open size="xl" title={title} onClose={() => setOpen(false)} testId="award-reader"
          footer={<button type="button" onClick={() => setOpen(false)} className="btn-primary min-h-12 w-full">
            {t('scholarship.actionCentre.done')}</button>}>
          {/* min-h: a browser without dvh still gets a tall frame. */}
          <iframe title={title} sandbox="" srcDoc={doc} className="h-[70dvh] min-h-[24rem] w-full rounded-lg border-0 bg-ground-0" />
        </Sheet>
      )}
    </div>
  )
}

/** "Not right now?" — the decline question in a sheet (was the browser's own `confirm`). Not
 *  swipe-away while it is being answered (`busy`); Cancel is the first focus, the safe answer. */
export function AwardDeclineSheet({ busy, onCancel, onConfirm }: {
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const { t } = useT()
  const cancel = useRef<HTMLButtonElement>(null)
  return (
    <Sheet open size="sm" role="alertdialog" busy={busy} onClose={onCancel} testId="award-decline" initialFocus={cancel}
      title={t('scholarship.award.confirmed.decline')}
      footer={<>
        <button type="button" onClick={onConfirm} disabled={busy}
          className="min-h-12 w-full rounded-xl border border-critical-200 px-4 font-semibold text-critical-600 hover:bg-critical-50 disabled:opacity-50">
          {t('scholarship.award.confirmed.decline')}
        </button>
        <button ref={cancel} type="button" onClick={onCancel} disabled={busy} className="btn-primary min-h-12 w-full">
          {t('scholarship.award.guardian.cancel')}
        </button>
      </>}>
      <p className="text-ground-700">{t('scholarship.award.declineConfirm')}</p>
    </Sheet>
  )
}
