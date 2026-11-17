'use client'

import { useT } from '@/lib/i18n'

/**
 * The two ways to send a document from the Action Centre (H5): the normal Upload (gallery, files,
 * PDF) and "Take a photo" (`capture="environment"` opens the back camera on a phone; a desktop browser
 * just opens its file picker). Both hand the chosen file to `onFile`. `sr-only` inputs, never `hidden`:
 * several Android browsers refuse to open the picker for a display:none input behind a label.
 */
export function UploadButtons({ busy, onFile, uploadKey = 'scholarship.actionCentre.upload' }: {
  busy: boolean; onFile: (file: File) => void
  /** The first button's words: `Upload` by default, `Replace` on a sent / done document (H6). */
  uploadKey?: string
}) {
  const { t } = useT()
  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) onFile(f)
    e.target.value = ''
  }
  const face = 'flex min-h-11 w-full cursor-pointer items-center justify-center rounded-xl px-3 py-2.5 text-center text-sm font-semibold transition-colors focus-within:ring-2 focus-within:ring-info-500 focus-within:ring-offset-2'
  return (
    <div className="grid grid-cols-2 gap-2">
      <label className={`${face} bg-brand-fill text-brand-fill-ink hover:bg-brand-fill-hover ${busy ? 'opacity-50' : ''}`}>
        {busy ? t('scholarship.actionCentre.uploading') : t(uploadKey)}
        <input type="file" accept="image/*,.pdf" className="sr-only" disabled={busy} onChange={pick} />
      </label>
      <label className={`${face} border border-brand-shape text-primary-600 hover:bg-primary-50 ${busy ? 'opacity-50' : ''}`}>
        {t('documentsTab.actionCentre.takePhoto')}
        <input type="file" accept="image/*" capture="environment" className="sr-only" disabled={busy} onChange={pick} />
      </label>
    </div>
  )
}
