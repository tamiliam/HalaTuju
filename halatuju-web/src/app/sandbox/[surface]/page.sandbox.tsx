'use client'

/** Mounts one real surface. A mount point — see the rule in `layout.sandbox.tsx`. */
import Link from 'next/link'
import { surfaceBySlug } from '@/sandbox/surfaces'

export default function SandboxSurfacePage({ params }: { params: { surface: string } }) {
  const surface = surfaceBySlug(params.surface)

  if (!surface) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <p className="text-gray-900">No sandbox surface called “{params.surface}”.</p>
        <Link href="/sandbox" className="mt-2 inline-block text-blue-600 hover:underline">
          Back to the sandbox
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">{surface.title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-600">{surface.note}</p>
      </div>
      {surface.render()}
    </div>
  )
}
