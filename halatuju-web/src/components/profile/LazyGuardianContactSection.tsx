'use client'

/**
 * The profile's parent/guardian contact (request #26), fetched as its own chunk.
 *
 * WHY: `/profile` sits within a kilobyte of its first-load-JS budget (`code-standards.json`,
 * `first_load_js`), and this section is drawn only for the minority of students who have applied.
 * The budget is never raised; the weight is paid for here. Same arrangement as
 * `scholarship/LazyStpmSchoolPicker.tsx`: the import is owned here, not by `next/dynamic`.
 *
 * Nothing is drawn while the chunk is in the air, and nothing if it fails — the section is
 * supplementary, and the rest of the card must never wait on it or break with it.
 * The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState, type ComponentType } from 'react'

export default function LazyGuardianContactSection() {
  const [Section, setSection] = useState<ComponentType | null>(null)
  useEffect(() => {
    let live = true
    import('./GuardianContactSection')
      .then(m => { if (live) setSection(() => m.default) })
      .catch(() => { /* supplementary — draw nothing */ })
    return () => { live = false }
  }, [])
  return Section ? <Section /> : null
}
