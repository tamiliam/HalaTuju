import { useEffect, useState } from 'react'

/**
 * The five section EDIT panels, fetched as ONE chunk (A3.9, SP-09 / CH-01).
 *
 * WHY: a student arrives on /profile to READ it; the forms (the school picker, the family roster
 * editor, the phone-verify flow, the IC claim wording) are paid for only when a section opens.
 * Keeping them out of the first load is what gives /profile its room under the budget in
 * `code-standards.json`. The fetch STARTS when the page mounts, alongside the profile request, so
 * it has almost always landed before a student can press Edit. If she is faster, the read-only
 * rows stay until it arrives: nothing blanks, and the page does not move.
 *
 * Same hand-owned import as `LazyGuardianContactSection` (no `next/dynamic`): the specifier is a
 * LITERAL so the bundler emits a real chunk. A failed fetch is reported (`failed`), never hidden.
 */
type Editors = typeof import('./sections/edit')

let loaded: Editors | null = null
let pending: Promise<Editors> | null = null

export function useProfileEditors(): { editors: Editors | null; failed: boolean } {
  const [editors, setEditors] = useState<Editors | null>(loaded)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (loaded) { setEditors(loaded); return }
    let live = true
    pending = pending ?? import(/* webpackChunkName: 'pe' */ './sections/edit').then(m => (loaded = m))
    pending.then(m => { if (live) setEditors(m) }).catch(() => { pending = null; if (live) setFailed(true) })
    return () => { live = false }
  }, [])
  return { editors, failed }
}
