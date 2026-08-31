'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'

export interface PathwayTrack {
  id: string
  pathway: 'matric' | 'stpm'
  track: string
  meritScore?: number
  meritLabel?: 'High' | 'Fair' | 'Low'
  mataGred?: number
  collegeCount?: number
  schoolCount?: number
}

const SUPABASE_STORAGE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'

const TRACK_IMAGES: Record<string, Record<string, string>> = {
  matric: {
    sains: 'kimia-alam-sekitar',
    sains_komputer: 'it-perisian',
    kejuruteraan: 'kejuruteraan-am',
    perakaunan: 'perakaunan-kewangan',
  },
  stpm: {
    sains: 'sains-stem',
    sains_sosial: 'umum-kemanusiaan',
  },
}

/**
 * A CATEGORY PALETTE, on the `category-N` family (Layer 1 F2c, owner decision 2026-08-31).
 *
 * These five colours do not MEAN anything. They exist so a student can tell one field of study
 * from another at a glance, and their only requirement is to be DISTINCT from each other — which
 * is exactly why they are not tones. F2b measured what a tone rename would have done here:
 * `sains_komputer` (blue) and `sains_sosial` (sky) would BOTH have become `info`, rendering two
 * different fields identically, and it would have claimed Science is a "success".
 *
 * ⛔ NEVER put a tone in this table, and never put `category-N` on a state. The numbers are
 * arbitrary and carry no order — pick any unused one for a new field.
 */
const TRACK_COLORS: Record<string, string> = {
  sains: 'bg-category-6-surface text-category-6-ink',
  sains_komputer: 'bg-category-5-surface text-category-5-ink',
  kejuruteraan: 'bg-category-3-surface text-category-3-ink',
  perakaunan: 'bg-category-1-surface text-category-1-ink',
  sains_sosial: 'bg-category-2-surface text-category-2-ink',
}

const TRACK_I18N_KEYS: Record<string, string> = {
  sains: 'pathwayDetail.sains',
  sains_komputer: 'pathwayDetail.sainsKomputer',
  kejuruteraan: 'pathwayDetail.kejuruteraan',
  perakaunan: 'pathwayDetail.perakaunan',
  sains_sosial: 'pathwayDetail.sainsSosial',
}

function getTrackImageUrl(pathway: string, track: string): string {
  const slug = TRACK_IMAGES[pathway]?.[track] || 'umum-kemanusiaan'
  return `${SUPABASE_STORAGE}/${slug}.png`
}

interface PathwayTrackCardProps {
  track: PathwayTrack
}

export default function PathwayTrackCard({ track }: PathwayTrackCardProps) {
  const { t } = useT()

  const imageUrl = getTrackImageUrl(track.pathway, track.track)
  const isMatric = track.pathway === 'matric'

  const badgeLabel = isMatric ? 'Matriculation' : 'Form 6'

  const trackLabel = t(TRACK_I18N_KEYS[track.track] || track.track)

  const pathwayTitle = isMatric
    ? t('pathwayDetail.matricTitle')
    : t('pathwayDetail.stpmTitle')

  const title = `${pathwayTitle} \u2014 ${trackLabel}`

  const duration = isMatric ? '2 Semesters' : '3 Semesters'

  const href = isMatric
    ? `/pathway/matric?track=${track.track}`
    : `/pathway/stpm?stream=${track.track}`

  // Two categories (Matriculation / Form 6), so two swatches. Distinct from each other is all
  // that is required; they may reuse numbers the TRACK_COLORS table uses, because the two sets
  // are never compared against one another — only within themselves.
  const pathwayBadgeColor = isMatric
    ? 'bg-category-7-surface text-category-7-ink'
    : 'bg-category-8-surface text-category-8-ink'

  const trackBadgeColor = TRACK_COLORS[track.track] || 'bg-ground-100 text-ground-700'

  return (
    <Link
      href={href}
      className="bg-ground-0 rounded-xl border border-ground-200 overflow-hidden transition-all flex flex-col hover:border-primary-300 hover:shadow-sm"
    >
      {/* Image header */}
      <div className="relative h-36 bg-ground-100 flex-shrink-0">
        <Image
          src={imageUrl}
          alt={trackLabel}
          fill
          className="object-cover"
          unoptimized
        />
      </div>

      {/* Card body */}
      <div className="flex-1 p-4 flex flex-col">
        {/* Pathway badge */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${pathwayBadgeColor}`}>
            {badgeLabel}
          </span>
        </div>

        {/* Title */}
        <h3 className="text-sm font-semibold text-ground-900 mb-1 line-clamp-2">
          {title}
        </h3>

        {/* Duration + Fee */}
        <div className="flex items-center gap-3 text-xs text-ground-500 mb-1">
          <span>{duration} &bull; Free</span>
        </div>

        {/* Institution count */}
        {(isMatric ? track.collegeCount : track.schoolCount) != null && (
          <div className="flex items-center gap-1 text-xs text-ground-500 mb-1">
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3H21m-3.75 3H21" />
            </svg>
            <span>
              {isMatric
                ? `${track.collegeCount} ${t('pathwayDetail.colleges').toLowerCase()}`
                : `${track.schoolCount} ${t('pathwayDetail.schools').toLowerCase()}`
              }
            </span>
          </div>
        )}

        {/* Merit indicator (matric only) */}
        {isMatric && track.meritLabel && (
          <MeritIndicator label={track.meritLabel} score={track.meritScore} t={t} />
        )}
      </div>
    </Link>
  )
}

function MeritIndicator({
  label,
  score,
  t,
}: {
  label: 'High' | 'Fair' | 'Low'
  score?: number
  t: (key: string) => string
}) {
  const dotColor =
    label === 'High' ? 'bg-positive-500' :
    label === 'Fair' ? 'bg-caution-400' :
    'bg-critical-500'

  const textClass =
    label === 'High' ? 'text-positive-700' :
    label === 'Fair' ? 'text-caution-700' :
    'text-critical-700'

  const displayLabel =
    label === 'High' ? t('pathwayDetail.high') :
    label === 'Fair' ? t('pathwayDetail.fair') :
    t('pathwayDetail.low')

  return (
    <div className="flex items-center gap-1.5 mt-1">
      <span className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${dotColor}`} />
      <span className={`text-xs font-medium ${textClass}`}>{displayLabel}</span>
      {score != null && (
        <span className="text-xs text-ground-400 ml-1">
          {t('pathwayDetail.meritScore')}: {score}
        </span>
      )}
    </div>
  )
}
