'use client'

import Link from 'next/link'
import type { EligibleCourse, RankedCourse } from '@/lib/api'

const SUPABASE_STORAGE = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'

/** Check if text contains any of the keywords (case-insensitive). */
function matchAny(text: string, keywords: string[]): boolean {
  return keywords.some(kw => text.includes(kw))
}

/**
 * Map a course's field + name to one of 37 image slugs.
 * Uses keyword matching: umbrella fields sub-route by course name,
 * specific fields match by keyword, "Umum" catch-all routes by course name.
 */
function getImageSlug(field: string, courseName: string): string {
  const f = field.toLowerCase()
  const c = courseName.toLowerCase()

  // ── PENDIDIKAN — sub-route by course name ──
  if (f === 'pendidikan') {
    if (matchAny(c, ['bahasa', 'pengajaran'])) return 'pendidikan-bahasa'
    if (matchAny(c, ['matematik', 'sains', 'reka bentuk dan teknologi'])) return 'pendidikan-stem'
    if (matchAny(c, ['seni visual', 'muzik'])) return 'pendidikan-seni'
    if (matchAny(c, ['sejarah', 'islam', 'kaunseling', 'bimbingan'])) return 'pendidikan-kemanusiaan'
    if (matchAny(c, ['khas', 'kanak-kanak', 'jasmani'])) return 'pendidikan-khas'
    return 'pendidikan-stem'
  }

  // ── MEKANIKAL & PEMBUATAN — sub-route by course name ──
  if (f === 'mekanikal & pembuatan') {
    if (matchAny(c, ['kimpalan', 'boilermaker'])) return 'mekanikal-kimpalan'
    if (matchAny(c, ['mekatronik'])) return 'mekanikal-mekatronik'
    if (matchAny(c, ['pemesinan', 'perkakasan', 'die', 'mould', 'dai', 'cadd'])) return 'mekanikal-pemesinan'
    return 'mekanikal-am'
  }

  // ── ELEKTRIK & ELEKTRONIK — sub-route by course name ──
  if (f === 'elektrik & elektronik') {
    if (matchAny(c, ['elektronik industri', 'instrumen perindustrian'])) return 'elektronik-kawalan'
    if (matchAny(c, ['elektronik', 'mikroelektronik', 'telekomunikasi'])) return 'elektronik-telekom'
    return 'elektrik-kuasa'
  }

  // ── TEKNOLOGI MAKLUMAT — sub-route by course name ──
  if (f === 'teknologi maklumat') {
    if (matchAny(c, ['networking', 'security', 'data', 'rangkaian'])) return 'it-rangkaian'
    return 'it-perisian'
  }

  // ── ICT & MULTIMEDIA ──
  if (f === 'ict & multimedia') return 'it-rangkaian'

  // ── AERO & MARIN — split by course name ──
  if (f === 'aero & marin') {
    if (matchAny(c, ['marin', 'kapal', 'perkapalan'])) return 'marin-perkapalan'
    return 'aero-penerbangan'
  }

  // ── HOSPITALITI & GAYA HIDUP — sub-route by course name ──
  if (f === 'hospitaliti & gaya hidup') {
    if (matchAny(c, ['fesyen', 'pakaian', 'jahitan'])) return 'senireka-fesyen'
    if (matchAny(c, ['kulinari', 'culinary', 'pastri', 'patisserie', 'makanan', 'food', 'roti'])) return 'kulinari-makanan'
    if (matchAny(c, ['dandanan', 'kecantikan', 'terapi', 'spa', 'kosmetologi', 'rambut'])) return 'kecantikan-gayahidup'
    return 'hospitaliti-pelancongan'
  }

  // ── FIELD KEYWORD MATCHING (specific first) ──

  // Automotif
  if (matchAny(f, ['automotif', 'kenderaan', 'motosikal'])) return 'automotif'

  // Mekanikal sub-fields
  if (matchAny(f, ['kimpalan'])) return 'mekanikal-kimpalan'
  if (matchAny(f, ['mekatronik'])) return 'mekanikal-mekatronik'
  if (f.startsWith('kejuruteraan mekanikal')) {
    if (matchAny(f, ['automasi'])) return 'mekanikal-mekatronik'
    if (matchAny(f, ['automotif'])) return 'automotif'
    if (matchAny(f, ['pembuatan', 'produk', 'pembungkusan', 'plastik'])) return 'mekanikal-pemesinan'
    if (matchAny(f, ['petrokimia'])) return 'minyak-gas'
    return 'mekanikal-am'
  }
  if (matchAny(f, ['kejuruteraan pembuatan', 'teknologi pembuatan', 'mechanical design'])) return 'mekanikal-pemesinan'
  if (matchAny(f, ['penyejukan', 'penyamanan udara', 'kejuruteraan bahan', 'berasaskan kayu', 'penyenggaraan industri', 'perabot'])) return 'mekanikal-am'

  // Elektrik sub-fields
  if (f.startsWith('kejuruteraan elektrik')) {
    if (matchAny(f, ['elektronik'])) return 'elektronik-telekom'
    if (matchAny(f, ['instrumentasi'])) return 'elektronik-telekom'
    return 'elektrik-kuasa'
  }
  if (f.startsWith('kejuruteraan elektronik')) {
    if (matchAny(f, ['kawalan'])) return 'elektronik-kawalan'
    if (matchAny(f, ['perubatan', 'komputer'])) return 'elektronik-kawalan'
    return 'elektronik-telekom'
  }
  if (matchAny(f, ['teknologi elektrik', 'solar fotovoltan'])) return 'elektrik-kuasa'
  if (matchAny(f, ['telekomunikasi', 'telecommunication', 'rail signalling', 'electronics instrumentation'])) return 'elektronik-telekom'

  // IT
  if (matchAny(f, ['kejuruteraan komputer', 'sistem maklumat', 'mobile technology', 'peranti mudah alih'])) return 'it-perisian'

  // Sivil
  if (matchAny(f, ['sivil', 'kejuruteraan awam', 'penyeliaan tapak'])) return 'sivil-struktur'
  if (matchAny(f, ['penyelenggaraan bangunan', 'perkhidmatan bangunan', 'teknologi pembinaan', 'ukur bahan'])) return 'sivil-bangunan'

  // Architecture & Landscape (but NOT 'senibina kapal' which is naval architecture)
  if (f.includes('senibina kapal')) return 'marin-perkapalan'
  if (matchAny(f, ['seni bina', 'senibina', 'architectural', 'landskap', 'hortikultur', 'rekabentuk dalaman', 'perancangan bandar', 'geomatik'])) return 'senibina-landskap'

  // Chemical engineering (before oil/gas to avoid 'teknologi kimia (lemak dan minyak)' misroute)
  if (matchAny(f, ['kejuruteraan kimia', 'teknologi kimia', 'kejuruteraan alam sekitar', 'kejuruteraan proses'])) return 'kimia-alam-sekitar'

  // Oil & Gas
  if (matchAny(f, ['minyak', 'gas'])) return 'minyak-gas'

  // Hospitality cluster
  if (matchAny(f, ['hospitaliti', 'hotel', 'pelancongan', 'resort', 'pengurusan acara', 'pengendalian acara', 'recreational tourism'])) return 'hospitaliti-pelancongan'
  if (matchAny(f, ['kulinari', 'culinary', 'patisserie', 'pastri', 'food', 'makanan', 'seni kulinari'])) return 'kulinari-makanan'
  if (matchAny(f, ['dandanan', 'kecantikan', 'terapi', 'spa', 'kecergasan'])) return 'kecantikan-gayahidup'

  // Business cluster
  if (matchAny(f, ['perniagaan', 'keusahawanan', 'pemasaran', 'e-commerce', 'pengoperasian'])) return 'perniagaan'
  if (matchAny(f, ['perakaunan', 'kewangan', 'insurans'])) return 'perakaunan-kewangan'
  if (matchAny(f, ['pengurusan', 'logistik', 'peruncitan', 'retail'])) return 'pengurusan-logistik'

  // Agriculture & Agro
  if (matchAny(f, ['pertanian', 'agroteknologi', 'akuakultur', 'kesihatan haiwan', 'bioteknologi', 'teknologi pertanian'])) return 'pertanian-agro'

  // Science & Health
  if (matchAny(f, ['perubatan', 'kesihatan', 'fisioterapi'])) return 'perubatan-kesihatan'
  if (matchAny(f, ['sains', 'stem'])) return 'sains-stem'

  // Design & Fashion
  if (matchAny(f, ['seni reka', 'rekabentuk grafik', 'rekabentuk industri', 'fesyen', 'seni visual', 'media cetak', 'reka bentuk kraf', 'sound & lighting'])) return 'senireka-fesyen'

  // Multimedia & Animation
  if (matchAny(f, ['animasi', '3d animation', 'games art', 'teknologi kreatif digital', 'multimedia kreatif'])) return 'multimedia-animasi'

  // Aero & Marine (specific fields)
  if (matchAny(f, ['aero', 'penerbangan', 'pesawat'])) return 'aero-penerbangan'
  if (matchAny(f, ['marin', 'perkapalan', 'kapal'])) return 'marin-perkapalan'

  // General Engineering
  if (matchAny(f, ['kejuruteraan'])) return 'kejuruteraan-am'

  // Law & Pharmacy (future STPM)
  if (matchAny(f, ['undang-undang', 'law'])) return 'undang-undang'
  if (matchAny(f, ['farmasi', 'pharmacy'])) return 'farmasi'

  // Humanities
  if (matchAny(f, ['bahasa', 'pengajian islam', 'sains sosial', 'kesetiausahaan'])) return 'umum-kemanusiaan'

  // ── UMUM catch-all — route by course name ──
  if (f === 'umum') {
    if (matchAny(c, ['perikanan', 'perhutanan', 'pertanian'])) return 'pertanian-agro'
    if (matchAny(c, ['bank', 'insurans'])) return 'perakaunan-kewangan'
    if (matchAny(c, ['radiografi'])) return 'perubatan-kesihatan'
    if (matchAny(c, ['makmal'])) return 'sains-stem'
    if (matchAny(c, ['animasi', 'tari', 'teater', 'muzik'])) return 'multimedia-animasi'
    if (matchAny(c, ['pembuatan'])) return 'mekanikal-pemesinan'
    if (matchAny(c, ['rekabentuk'])) return 'senireka-fesyen'
    if (matchAny(c, ['kanak-kanak'])) return 'pendidikan-khas'
    if (matchAny(c, ['tahfiz'])) return 'umum-kemanusiaan'
    return 'umum-kemanusiaan'
  }

  return 'umum-kemanusiaan'
}

function getFieldImageUrl(field: string, courseName: string): string {
  const slug = getImageSlug(field, courseName)
  return `${SUPABASE_STORAGE}/${slug}.png`
}

const TYPE_LABELS: Record<string, string> = {
  poly: 'Polytechnic',
  tvet: 'TVET',
  ua: 'University',
  pismp: 'Teacher Training',
}

const TYPE_COLORS: Record<string, string> = {
  poly: 'bg-blue-100 text-blue-700',
  tvet: 'bg-green-100 text-green-700',
  ua: 'bg-purple-100 text-purple-700',
  pismp: 'bg-amber-100 text-amber-700',
}

const LEVEL_COLORS: Record<string, string> = {
  'Diploma': 'bg-blue-50 text-blue-600',
  'Sijil': 'bg-green-50 text-green-600',
  'Sarjana Muda': 'bg-purple-50 text-purple-600',
  'Asasi': 'bg-orange-50 text-orange-600',
}

function isRankedCourse(course: EligibleCourse | RankedCourse): course is RankedCourse {
  return 'fit_score' in course
}

interface CourseCardProps {
  course: EligibleCourse | RankedCourse
  rank?: number
  isSaved: boolean
  onToggleSave?: (courseId: string) => void
}

export default function CourseCard({ course, rank, isSaved, onToggleSave }: CourseCardProps) {
  const imageUrl = getFieldImageUrl(course.field, course.course_name || '')
  const isLowMerit = course.merit_label === 'Low'

  return (
    <div
      className={`bg-white rounded-xl border overflow-hidden transition-all flex flex-col ${
        rank
          ? 'border-2 border-primary-100 hover:border-primary-300'
          : 'border-gray-200 hover:border-primary-300'
      } hover:shadow-sm ${isLowMerit ? 'opacity-60' : ''}`}
    >
      {/* Field image header */}
      <div className="relative h-36 bg-gray-100 flex-shrink-0">
        <img
          src={imageUrl}
          alt={course.field}
          className="w-full h-full object-cover"
        />

        {/* Rank badge overlay */}
        {rank && (
          <div className="absolute top-2 left-2 w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center shadow">
            <span className="text-white text-sm font-bold">#{rank}</span>
          </div>
        )}

        {/* Save button overlay */}
        {onToggleSave && (
          <button
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onToggleSave(course.course_id)
            }}
            className="absolute top-2 right-2 p-1.5 bg-white/80 backdrop-blur-sm rounded-full hover:bg-white transition-colors"
            aria-label={isSaved ? 'Remove from saved' : 'Save course'}
          >
            <svg
              className={`w-4 h-4 ${isSaved ? 'text-primary-500 fill-primary-500' : 'text-gray-500'}`}
              viewBox="0 0 24 24"
              fill={isSaved ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Card body */}
      <Link href={`/course/${course.course_id}`} className="flex-1 p-4 flex flex-col">
        {/* Type + Level badges */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              TYPE_COLORS[course.source_type] || 'bg-gray-100 text-gray-700'
            }`}
          >
            {TYPE_LABELS[course.source_type] || course.source_type}
          </span>
          {course.level && (
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                LEVEL_COLORS[course.level] || 'bg-gray-50 text-gray-600'
              }`}
            >
              {course.level}
            </span>
          )}
        </div>

        {/* Course name */}
        <h3 className="text-sm font-semibold text-gray-900 mb-1 line-clamp-2">
          {course.course_name || course.course_id}
        </h3>

        {/* Field */}
        <p className="text-gray-500 text-xs mb-2">
          {course.field || 'View course details'}
        </p>

        {/* Merit traffic light */}
        <MeritIndicator label={course.merit_label} color={course.merit_color} />

        {/* Fit reasons (ranked courses only) */}
        {isRankedCourse(course) && course.fit_reasons && course.fit_reasons.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {course.fit_reasons.slice(0, 2).map((reason, i) => (
              <span
                key={i}
                className="inline-block px-2 py-0.5 bg-primary-50 text-primary-700 text-xs rounded-full"
              >
                {reason}
              </span>
            ))}
          </div>
        )}
      </Link>
    </div>
  )
}

function MeritIndicator({ label, color }: { label: string | null; color: string | null }) {
  if (!label) return null

  const textClass =
    label === 'High' ? 'text-green-700' :
    label === 'Fair' ? 'text-amber-700' :
    'text-red-700'

  const displayLabel =
    label === 'High' ? 'High Chance' :
    label === 'Fair' ? 'Fair Chance' :
    'Low Chance'

  return (
    <div className="flex items-center gap-1.5">
      <span
        className="w-2 h-2 rounded-full inline-block flex-shrink-0"
        style={{ backgroundColor: color || '#95a5a6' }}
      />
      <span className={`text-xs font-medium ${textClass}`}>
        {displayLabel}
      </span>
    </div>
  )
}
