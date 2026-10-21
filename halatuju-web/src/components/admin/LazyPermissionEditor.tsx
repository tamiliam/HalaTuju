'use client'

/**
 * The permission editor (request #39 Sprint 4), fetched as its own chunk the first time a page shows
 * it. Same arrangement as `LazyMerchantFlagDialog.tsx`: the import is owned here, not by
 * `next/dynamic` (which re-throws a failed chunk load), and the specifier is a LITERAL so the bundler
 * emits a real chunk.
 *
 * WHY: the editor is for the organisation admin, a few times a year; the reviewer's page it sits on
 * is read far more often, and every route is budgeted against the median (`npm run bundle-budget`).
 *
 * ⚠ WHEN THE CHUNK FAILS (a tab held open across a deploy asks for a hash that is gone), it says so
 * in one line rather than leaving a hole where the card was.
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'
import type { PermissionEditorProps } from './PermissionEditor'

export default function LazyPermissionEditor(props: PermissionEditorProps) {
  const { t } = useT()
  const [Editor, setEditor] = useState<ComponentType<PermissionEditorProps> | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let live = true
    import('./PermissionEditor')
      .then((m) => { if (live) setEditor(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])
  if (Editor) return <Editor {...props} />
  if (!failed) return null
  return <p className="text-sm text-critical-600">{t('admin.permEditor.loadFailed', { name: props.name })}</p>
}
