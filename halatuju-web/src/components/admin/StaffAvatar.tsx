'use client'

import { useEffect, useState } from 'react'

/**
 * A staff member's round photo, or their initials when there is none (common profile S2). Used by
 * the header, the Profile page and the Team (People) lists. Staff screens only — a staff photo is
 * never shown to a student, a sponsor or a source.
 *
 * The URL is a ~1-hour signed link; one that has expired (a tab left open) fails to load, and the
 * initials take its place rather than a broken image.
 */
export function initialsOf(name: string | null | undefined): string {
  return (name ?? '?').split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join('').toUpperCase() || '?'
}

export default function StaffAvatar({ name, photoUrl, size = 32, alt = '' }: {
  name: string | null | undefined
  photoUrl?: string | null
  size?: number
  /** Empty (decorative) beside a visible name; the Profile page names it. */
  alt?: string
}) {
  const [broken, setBroken] = useState(false)
  useEffect(() => { setBroken(false) }, [photoUrl])
  const box = { width: size, height: size }
  if (photoUrl && !broken) {
    // A plain <img>, not next/image: a signed, expiring private URL must not be proxied or cached.
    return <img src={photoUrl} alt={alt} style={box} onError={() => setBroken(true)}
      className="shrink-0 rounded-full object-cover" data-testid="staff-avatar-photo" />
  }
  return (
    <span aria-hidden={alt ? undefined : true} role={alt ? 'img' : undefined} aria-label={alt || undefined}
      style={{ ...box, fontSize: Math.max(10, Math.round(size * 0.38)) }}
      className="grid shrink-0 place-items-center rounded-full bg-brand-fill font-bold text-brand-fill-ink"
      data-testid="staff-avatar-initials">
      {initialsOf(name)}
    </span>
  )
}
