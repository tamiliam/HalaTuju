'use client'

/**
 * The flag dialog (request #28 follow-up), fetched as its own chunk the first time somebody presses
 * a flag. Same arrangement as `profile/LazyGuardianContactSection.tsx`: the import is owned here,
 * not by `next/dynamic` (which re-throws a failed chunk load), and the specifier is a LITERAL so the
 * bundler emits a real chunk.
 *
 * WHY: most visits to the spending screen never open a flag, and the screen sits near the median
 * every route is budgeted against (`npm run bundle-budget`). The weight is paid for by whoever
 * presses the button.
 *
 * ⚠ WHEN THE CHUNK FAILS (a tab held open across a deploy asks for a hash that is gone), the person
 * pressed a button and must be told — a small alert with a way out, never a silent nothing.
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'
import type { MerchantFlagDialogProps } from './MerchantFlagDialog'
import Sheet from '@/components/Sheet'

export default function LazyMerchantFlagDialog(props: MerchantFlagDialogProps) {
  const { t } = useT()
  const [Dialog, setDialog] = useState<ComponentType<MerchantFlagDialogProps> | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let live = true
    import(/* webpackChunkName: 'ad' */ './MerchantFlagDialog')
      .then((m) => { if (live) setDialog(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])
  if (Dialog) return <Dialog {...props} />
  if (!failed) return null
  return (
    <Sheet open role="alertdialog" size="sm" onClose={props.onClose} title={props.merchant}
      label={props.merchant} footer={
        <button type="button" onClick={props.onClose}
          className="rounded-md border border-ground-300 px-3 py-1.5 text-xs font-medium text-ground-700">
          {t('common.cancel')}
        </button>
      }>
      <p className="text-sm text-critical-600">{t('errors.somethingWentWrong')}</p>
    </Sheet>
  )
}
