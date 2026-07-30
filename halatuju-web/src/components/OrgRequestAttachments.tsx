'use client'

// Screenshot attachments on the Requests DETAIL page (Sprint 15.1). Renders the request's images as
// inline thumbnails (signed URL) with a filename + size caption, and — while the request is
// non-terminal and the caller may act — an add/remove control. Each add runs the sign → PUT → record
// chain (admin-api.uploadOrgRequestAttachment); the server re-gates everything (images-only, ≤5,
// non-terminal, org-fence), so this only decides what to SHOW.
import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatFileSize } from '@/lib/scholarship'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import {
  uploadOrgRequestAttachment, deleteOrgRequestAttachment,
  type OrgRequestAttachment, type OrgRequestDetail,
} from '@/lib/admin-api'
// Shared with the CREATE form's screenshot block — one home for "which files count and what do we
// call a pasted one", because these two surfaces cannot share a component (see screenshotInput.ts).
import { imagesFrom } from '@/lib/screenshotInput'

const MAX_ATTACHMENTS = 5

export default function OrgRequestAttachments({
  requestId, attachments, editable, token, onChange,
}: {
  requestId: number
  attachments: OrgRequestAttachment[]
  editable: boolean
  token: string | null
  onChange: (req: OrgRequestDetail) => void
}) {
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [viewing, setViewing] = useState<ViewerDoc | null>(null)
  const [dragging, setDragging] = useState(false)

  /** The ONE upload path — the file picker, a paste and a drop all funnel through here, so the
   *  cap, the error handling and the refresh cannot diverge between them. Uploads sequentially:
   *  a drop or paste can carry several images and each needs its own sign → PUT → record chain. */
  const upload = async (files: File[]) => {
    if (!files.length || !token) return
    let room = MAX_ATTACHMENTS - attachments.length
    if (room <= 0) {
      setError(t('admin.requests.attachments.limitReached')); return
    }
    setBusy(true); setError('')
    try {
      for (const file of files) {
        if (room <= 0) {
          setError(t('admin.requests.attachments.limitReached')); break
        }
        onChange(await uploadOrgRequestAttachment(requestId, file, { token }))
        room -= 1
      }
    } catch {
      setError(t('admin.requests.attachments.uploadFailed'))
    } finally {
      setBusy(false)
    }
  }

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = imagesFrom(e.target.files)
    e.target.value = ''   // let the same file be re-picked after a failure
    await upload(files)
  }

  // Win+Shift+S then Ctrl+V — the way a screenshot actually reaches a form. Scoped to this
  // panel (not the document) so pasting elsewhere on the page is unaffected.
  const onPaste = async (e: React.ClipboardEvent) => {
    if (!editable) return
    const files = imagesFrom(e.clipboardData?.files)
    if (!files.length) return
    e.preventDefault()
    await upload(files)
  }

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (!editable) return
    await upload(imagesFrom(e.dataTransfer?.files))
  }

  const remove = async (attId: number) => {
    if (!token) return
    setBusy(true); setError('')
    try {
      onChange(await deleteOrgRequestAttachment(requestId, attId, { token }))
    } catch {
      setError(t('admin.requests.attachments.uploadFailed'))
    } finally {
      setBusy(false)
    }
  }

  // Nothing to show and nothing to add → render nothing (keeps the page clean on old requests).
  if (!editable && attachments.length === 0) return null

  return (
    <div className="bg-white rounded-xl border p-5 mb-4"
      onPaste={onPaste}
      onDragOver={(e) => { if (editable) { e.preventDefault(); setDragging(true) } }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}>
      <DocViewer doc={viewing} onClose={() => setViewing(null)} />
      <h2 className="text-sm font-semibold text-gray-500 mb-3">{t('admin.requests.attachments.title')}</h2>
      {attachments.length === 0 ? (
        <p className="text-sm text-gray-400">{t('admin.requests.attachments.none')}</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {attachments.map((a) => (
            <figure key={a.id} className="border rounded-lg overflow-hidden">
              {a.download_url ? (
                // The thumbnail was ALREADY the full-size original, just cropped to h-32 — so
                // opening it needs no extra fetch, only somewhere to put it.
                <button type="button" className="block w-full cursor-zoom-in"
                  onClick={() => setViewing({
                    label: a.original_filename || t('admin.requests.attachments.image'),
                    filename: a.original_filename || '',
                    url: a.download_url as string,
                    kind: 'image',
                  })}
                  title={t('admin.requests.attachments.view')}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={a.download_url} alt={a.original_filename}
                    className="w-full h-32 object-cover bg-gray-50" />
                </button>
              ) : (
                <div className="w-full h-32 bg-gray-100 flex items-center justify-center text-xs text-gray-400">—</div>
              )}
              <figcaption className="p-2 text-xs text-gray-600 truncate" title={a.original_filename}>
                {a.original_filename || t('admin.requests.attachments.image')} · {formatFileSize(a.size)}
              </figcaption>
              {a.download_url && (
                <a href={a.download_url} target="_blank" rel="noreferrer"
                  className="block px-2 pb-2 text-xs text-primary-600 hover:underline">
                  {t('admin.requests.attachments.openTab')}
                </a>
              )}
              {editable && (
                <button type="button" disabled={busy} onClick={() => remove(a.id)}
                  className="w-full text-xs text-red-600 hover:text-red-800 py-1 border-t disabled:opacity-50">
                  {t('admin.requests.attachments.remove')}
                </button>
              )}
            </figure>
          ))}
        </div>
      )}
      {editable && attachments.length < MAX_ATTACHMENTS && (
        <div className="mt-3">
          <label className="inline-block text-sm font-medium text-blue-600 hover:text-blue-800 cursor-pointer">
            {busy ? t('admin.requests.attachments.uploading') : `+ ${t('admin.requests.attachments.add')}`}
            <input type="file" accept="image/*" multiple className="hidden" disabled={busy} onChange={onFile} />
          </label>
          <p className="text-xs text-gray-400 mt-1">
            {t('admin.requests.attachments.hint')} {t('admin.requests.attachments.pasteHint')}
          </p>
          {dragging && (
            <p className="mt-2 rounded-lg border-2 border-dashed border-primary-300 bg-primary-50 px-3 py-2 text-xs text-primary-700">
              {t('admin.requests.attachments.dropHere')}
            </p>
          )}
        </div>
      )}
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  )
}
