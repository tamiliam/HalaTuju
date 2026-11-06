'use client'

/** Mounts one real surface. A mount point — see the rule in `layout.sandbox.tsx`. */
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { surfaceBySlug } from '@/sandbox/surfaces'
import { setSurfaceRoutes } from '@/sandbox/stubFetch'

export default function SandboxSurfacePage() {
  // Next 15: a page's `params` prop is a Promise; a client page reads the segment with useParams.
  const params = useParams<{ surface: string }>()
  const surface = surfaceBySlug(params.surface)

  // During RENDER, not in an effect: the mounted screen fetches on mount, and this component's
  // effect would run after its children's. Set unconditionally so leaving a surface with
  // overrides clears them rather than carrying them into the next one.
  setSurfaceRoutes(surface?.routes)

  if (!surface) {
    return (
      <div className="rounded-xl border border-ground-200 bg-ground-0 p-6">
        <p className="text-ground-900">No sandbox surface called “{params.surface}”.</p>
        <Link href="/sandbox" className="mt-2 inline-block text-primary-600 hover:underline">
          Back to the sandbox
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ground-900">{surface.title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-ground-600">{surface.note}</p>
      </div>
      {surface.render()}
    </div>
  )
}
