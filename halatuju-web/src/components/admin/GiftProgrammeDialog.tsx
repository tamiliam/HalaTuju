'use client'

// The three write dialogs of the gift cards — delete, change code, create — moved out of `GiftProgrammes.tsx`
// (T5c P5, moves only) so they arrive as their OWN chunk the first time somebody presses one
// (`LazyGiftProgrammeDialog.tsx`). The Programmes landing is everyone's front door now, and most visits never
// open a dialog. Each dialog owns the text typed into it; the card grid owns the write and its error.
//
// ⚠ THE FENCE IS THE ENDPOINT. Every check here (the typed phrase, the code shape) explains a server rule;
// the server checks it again.

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import InfoBox from '@/components/InfoBox'
import Sheet from '@/components/Sheet'
import type { AdminProgramme } from '@/lib/admin-api'

export const CODE_OK = /^[a-z0-9][a-z0-9-]{1,49}$/

export type GiftProgrammeDialogProps = { busy: boolean; error: string; onClose: () => void } & (
  | { kind: 'delete'; programme: AdminProgramme; onConfirm: (phrase: string) => void }
  | { kind: 'rename'; programme: AdminProgramme; onConfirm: (code: string) => void }
  | { kind: 'create'; onConfirm: (code: string, nameEn: string) => void }
)

const inputCls = 'w-full rounded-lg border border-ground-300 px-3 py-2 text-sm'
  + ' focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'

export default function GiftProgrammeDialog(props: GiftProgrammeDialogProps) {
  if (props.kind === 'delete') return <DeleteDialog {...props} />
  if (props.kind === 'rename') return <RenameDialog {...props} />
  return <CreateDialog {...props} />
}

function DeleteDialog({ programme: deleting, busy, onClose, onConfirm }:
  Extract<GiftProgrammeDialogProps, { kind: 'delete' }>) {
  const { t } = useT()
  const [confirmText, setConfirmText] = useState('')
  // Whitespace-collapsed + lower-cased to match the server's own comparison exactly,
  // so the button is never asleep on a difference the server would have accepted.
  const phrase = confirmText.trim().replace(/\s+/g, ' ').toLowerCase()
  /* ⚠ THE TYPED CODE IS THE POINT. A second "are you sure?" is answered by the same reflex
     that pressed the first button; typing the gift's own code cannot be. The SERVER checks it
     too — this dialog explains the guard, it is not the guard. */
  return (
    <Sheet open onClose={onClose} busy={busy} tone="critical"
      title={t('admin.programmes.deleteTitle', { name: deleting.name_en })}
      footer={<>
        <button type="button" onClick={onClose} disabled={busy}
          className="rounded-lg px-4 py-2 text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
          {t('common.cancel')}
        </button>
        <button type="button" data-testid="delete-confirm"
          disabled={busy || phrase !== `delete ${deleting.code}`.toLowerCase()}
          onClick={() => onConfirm(phrase)}
          className="rounded-lg bg-critical-fill px-4 py-2 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
          {t('admin.programmes.deleteCta')}
        </button>
      </>}>
        <p className="text-sm text-ground-700">{t('admin.programmes.deleteBody')}</p>
        {/* ⚠ SAY THAT THE YEARS GO, AND SAY HOW MANY. The years are the one thing being
            removed that the person cannot see from this dialog, and since 2026-09-07 they no
            longer block the delete — so silence here would mean somebody presses Delete on a
            gift and quietly loses three years of rules they had set up. Shown only when there
            is at least one; a gift with none needs no sentence about none. */}
        {deleting.intake_years > 0 && (
          <p className="mt-2 text-sm text-ground-700" data-testid="delete-years-note">
            {t('admin.programmes.deleteYears', { count: String(deleting.intake_years) })}
          </p>
        )}
        <div className="mt-3">
          <InfoBox kind="warning">{t('admin.programmes.deleteKeeps')}</InfoBox>
        </div>

        {/* ⚠ THE PHRASE CARRIES THE VERB — `delete <code>`, not the bare code (owner,
            2026-09-07). The code is printed on the card AND in this very label, so typing it
            alone is closer to copying what is on screen than to stating an intention. */}
        <label htmlFor="p-confirm" className="mt-4 block text-sm font-medium text-ground-700">
          {t('admin.programmes.deleteConfirmLabel', { phrase: `delete ${deleting.code}` })}
        </label>
        <input id="p-confirm" value={confirmText} autoComplete="off"
          onChange={(e) => setConfirmText(e.target.value)}
          className={`mt-1 ${inputCls}`} />
    </Sheet>
  )
}

/* ⚠ THE LINK IS SHOWN WHERE THE CODE IS SET (owner's choice, 2026-09-08). A code changed
   without seeing the link it drives is a change made blind — this is the one screen where
   the two facts have to sit together. */
function RenameDialog({ programme: renaming, busy, error, onClose, onConfirm }:
  Extract<GiftProgrammeDialogProps, { kind: 'rename' }>) {
  const { t } = useT()
  const [newCode, setNewCode] = useState(renaming.code)
  const wanted = newCode.trim().toLowerCase()
  return (
    <Sheet open onClose={onClose} busy={busy}
      title={t('admin.programmes.renameTitle', { name: renaming.name_en })}
      footer={<>
        <button type="button" onClick={onClose} disabled={busy}
          className="rounded-lg px-4 py-2 text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
          {t('common.cancel')}
        </button>
        <button type="button" data-testid="rename-confirm"
          // Asleep on an unchanged code as well as a malformed one: the server treats the
          // same code as a no-op, so offering the press would promise a change that is not one.
          disabled={busy || !CODE_OK.test(wanted) || wanted === renaming.code}
          onClick={() => onConfirm(wanted)}
          className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.programmes.renameCta')}
        </button>
      </>}>
        <p className="text-sm font-medium text-ground-700">
          {t('admin.programmes.applyLinkLabel')}
        </p>
        <p data-testid="rename-apply-url"
          className="mt-1 break-all rounded-lg bg-ground-50 px-3 py-2 font-mono text-xs text-ground-700">
          {renaming.apply_url}
        </p>

        <label htmlFor="p-newcode" className="mt-4 block text-sm font-medium text-ground-700">
          {t('admin.programmes.field.newCode')}
        </label>
        <input id="p-newcode" value={newCode} autoComplete="off"
          onChange={(e) => setNewCode(e.target.value)} className={`mt-1 ${inputCls}`} />
        <p className="mt-1 text-xs text-ground-500">{t('admin.programmes.field.codeHint')}</p>

        {/* ⚠ SAY THAT THE OLD CODE KEEPS WORKING. Without this sentence the honest reader
            assumes every poster already printed is about to stop working, and does not rename
            a code they should. It is also true: the server writes the old code as an alias. */}
        <div className="mt-4">
          <InfoBox kind="info">{t('admin.programmes.renameKeeps')}</InfoBox>
        </div>
        {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}
    </Sheet>
  )
}

function CreateDialog({ busy, error, onClose, onConfirm }: Extract<GiftProgrammeDialogProps, { kind: 'create' }>) {
  const { t } = useT()
  const [code, setCode] = useState('')
  const [nameEn, setNameEn] = useState('')
  return (
    <Sheet open onClose={onClose} busy={busy} title={t('admin.programmes.new')}
      footer={<>
        <button type="button" onClick={onClose} disabled={busy}
          className="text-sm font-medium text-ground-500 hover:text-ground-700">
          {t('common.cancel')}
        </button>
        <button type="button" onClick={() => onConfirm(code.trim().toLowerCase(), nameEn.trim())}
          disabled={busy || !nameEn.trim() || !CODE_OK.test(code.trim().toLowerCase())}
          className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.programmes.create')}
        </button>
      </>}>
        <label htmlFor="p-name" className="block text-sm font-medium text-ground-700">
          {t('admin.programmes.field.name')}
        </label>
        <input id="p-name" value={nameEn} onChange={(e) => setNameEn(e.target.value)}
          className={`mt-1 ${inputCls}`} />

        <label htmlFor="p-code" className="mt-4 block text-sm font-medium text-ground-700">
          {t('admin.programmes.field.code')}
        </label>
        <input id="p-code" value={code} onChange={(e) => setCode(e.target.value)}
          className={`mt-1 ${inputCls}`} />
        <p className="mt-1 text-xs text-ground-500">{t('admin.programmes.field.codeHint')}</p>

        <div className="mt-4">
          <InfoBox kind="warning">{t('admin.programmes.codeWarning')}</InfoBox>
        </div>
        {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}
    </Sheet>
  )
}
