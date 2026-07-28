'use client'

/**
 * The sandbox shell — a surface picker and the stubbed provider stack.
 *
 * ⚠ THIS FILE, AND EVERY `*.sandbox.tsx` UNDER IT, IS A MOUNT POINT AND NOTHING ELSE. It may
 * import a real component and render it. It may NOT contain a copy of one. The moment the sandbox
 * holds its own version of a screen, a designer approves something that does not exist and we have
 * built the exact drift the sandbox was supposed to prevent. `sandbox-safety.test.ts` enforces it.
 *
 * The chrome below is the ONE exception, and it is deliberately plain: a picker and a banner,
 * nothing that resembles a product surface.
 */
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'
import { SandboxProviders } from '@/sandbox/providers'
import { SURFACES } from '@/sandbox/surfaces'

export default function SandboxLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  return (
    <SandboxProviders>
      <div className="min-h-screen bg-gray-50">
        <header className="border-b border-amber-300 bg-amber-50">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
            <span className="rounded bg-amber-200 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-amber-900">
              Sandbox
            </span>
            <p className="text-sm text-amber-900">
              Real components, invented data. Nothing here is a person, and nothing you do is saved.
            </p>
          </div>
          <nav className="mx-auto flex max-w-6xl flex-wrap gap-1 px-4 pb-3">
            {SURFACES.map((s) => {
              const active = pathname === `/sandbox/${s.slug}`
              return (
                <Link
                  key={s.slug}
                  href={`/sandbox/${s.slug}`}
                  className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    active
                      ? 'bg-gray-900 font-semibold text-white'
                      : 'text-gray-700 hover:bg-white'
                  }`}
                >
                  {s.title}
                </Link>
              )
            })}
          </nav>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </div>
    </SandboxProviders>
  )
}
