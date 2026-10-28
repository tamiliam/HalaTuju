'use client'

/**
 * /profile's "My Course Interests" (`CourseInterestsSection`), fetched as its own chunk.
 *
 * WHY: `/profile` sits at its first-load-JS budget (`code-standards.json`, `first_load_js`) and the
 * budget is never raised; the Bumiputera field (Bumi coverage Sprint B, 2026-10-28) needed room.
 * This section is the last card on the page, below the fold, so it pays for its own weight here —
 * the same arrangement as `LazyGuardianContactSection`. Nothing is drawn while the chunk is in the
 * air, and nothing if it fails: the rest of the page never waits on it or breaks with it.
 */
import { useEffect, useState, type ComponentProps, type ComponentType } from 'react'
import type CourseInterestsSection from './CourseInterestsSection'

type Props = ComponentProps<typeof CourseInterestsSection>

export default function LazyCourseInterestsSection(props: Props) {
  const [Section, setSection] = useState<ComponentType<Props> | null>(null)
  useEffect(() => {
    let live = true
    import('./CourseInterestsSection')
      .then(m => { if (live) setSection(() => m.default) })
      .catch(() => { /* supplementary — draw nothing */ })
    return () => { live = false }
  }, [])
  return Section ? <Section {...props} /> : null
}
