'use client'

/** The sandbox index. A mount point and a signpost — see the rule in `layout.sandbox.tsx`. */
import Link from 'next/link'
import { SURFACES } from '@/sandbox/surfaces'

export default function SandboxIndexPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Design sandbox</h1>
        <p className="mt-2 max-w-2xl text-gray-600">
          These are the real components from the live application, rendered against invented data.
          Changing something here changes nothing anywhere — there is no database behind it and no
          account signed in.
        </p>
      </div>

      <ul className="grid gap-3 sm:grid-cols-2">
        {SURFACES.map((s) => (
          <li key={s.slug}>
            <Link
              href={`/sandbox/${s.slug}`}
              className="block rounded-xl border border-gray-200 bg-white p-4 transition-colors hover:border-gray-400"
            >
              <span className="font-semibold text-gray-900">{s.title}</span>
              <span className="mt-1 block text-sm text-gray-600">{s.note}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
