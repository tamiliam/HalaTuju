/**
 * Pathway eligibility engine for Matriculation and STPM (Form 6).
 *
 * Runs entirely on the frontend. No backend calls needed.
 * Input: student's SPM grades + CoQ score.
 * Output: eligibility + merit/score per pathway track.
 */

// --- Grade Point Scales ---

// Matriculation merit scale (from matrikulasi.moe.gov.my calculator)
const MATRIC_GRADE_POINTS: Record<string, number> = {
  'A+': 25, 'A': 24, 'A-': 23, 'B+': 22, 'B': 21,
  'C+': 20, 'C': 19, 'D': 18, 'E': 17, 'G': 0,
}

// STPM (Form 6) mata gred scale — lower is better
const STPM_MATA_GRED: Record<string, number> = {
  'A+': 1, 'A': 1, 'A-': 2, 'B+': 3, 'B': 4,
  'C+': 5, 'C': 6, 'D': 7, 'E': 8, 'G': 9,
}

// Credit = C or better (mata gred <= 6)
function isCredit(grade: string): boolean {
  const mg = STPM_MATA_GRED[grade]
  return mg !== undefined && mg <= 6
}

// Grade meets minimum threshold
function meetsMin(grade: string, minGrade: string): boolean {
  const order = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']
  const gradeIdx = order.indexOf(grade)
  const minIdx = order.indexOf(minGrade)
  if (gradeIdx === -1 || minIdx === -1) return false
  return gradeIdx <= minIdx // lower index = better grade
}

// --- Matriculation ---

export interface MatricTrack {
  id: string
  name: string
  nameMs: string
  nameTa: string
}

export const MATRIC_TRACKS: MatricTrack[] = [
  { id: 'sains', name: 'Science', nameMs: 'Sains', nameTa: 'அறிவியல்' },
  { id: 'kejuruteraan', name: 'Engineering', nameMs: 'Kejuruteraan', nameTa: 'பொறியியல்' },
  { id: 'sains_komputer', name: 'Computer Science', nameMs: 'Sains Komputer', nameTa: 'கணினி அறிவியல்' },
  { id: 'perakaunan', name: 'Accounting', nameMs: 'Perakaunan', nameTa: 'கணக்கியல்' },
]

interface MatricRequirement {
  subjectId: string
  minGrade: string
  alternatives?: string[] // alternative subject IDs (pick one)
}

// Subject requirements per track
// Subject IDs match the grades page: MAT, AMT, CHE, PHY, BIO, COMP_SCI, ACC, etc.
const MATRIC_REQUIREMENTS: Record<string, MatricRequirement[]> = {
  sains: [
    { subjectId: 'MAT', minGrade: 'B' },
    { subjectId: 'AMT', minGrade: 'C' },
    { subjectId: 'CHE', minGrade: 'C' },
    { subjectId: 'PHY', minGrade: 'C', alternatives: ['BIO'] },
  ],
  kejuruteraan: [
    { subjectId: 'MAT', minGrade: 'B' },
    { subjectId: 'AMT', minGrade: 'C' },
    { subjectId: 'PHY', minGrade: 'C' },
    // 4th: any elective with min C — handled separately
  ],
  sains_komputer: [
    { subjectId: 'MAT', minGrade: 'C' },
    { subjectId: 'AMT', minGrade: 'C' },
    { subjectId: 'COMP_SCI', minGrade: 'C' },
    // 4th: any elective with min C — handled separately
  ],
  perakaunan: [
    { subjectId: 'MAT', minGrade: 'C' },
    // 3 electives with min C — handled separately
  ],
}

export interface PathwayResult {
  pathway: 'matric' | 'stpm'
  trackId: string
  trackName: string
  trackNameMs: string
  trackNameTa: string
  eligible: boolean
  merit?: number         // Matric merit score (0-100)
  mataGred?: number      // STPM total mata gred
  maxMataGred?: number   // STPM threshold
  reason?: string        // Why not eligible (i18n key)
  reasonParams?: Record<string, string>
}

function findBestElective(
  grades: Record<string, string>,
  excludeIds: Set<string>,
  minGrade: string
): { id: string; grade: string } | null {
  let best: { id: string; grade: string; pts: number } | null = null
  for (const [id, grade] of Object.entries(grades)) {
    if (excludeIds.has(id)) continue
    if (!meetsMin(grade, minGrade)) continue
    const pts = MATRIC_GRADE_POINTS[grade] || 0
    if (!best || pts > best.pts) {
      best = { id, grade, pts }
    }
  }
  return best ? { id: best.id, grade: best.grade } : null
}

function checkMatricTrack(
  trackId: string,
  grades: Record<string, string>,
  coqScore: number
): PathwayResult {
  const track = MATRIC_TRACKS.find(t => t.id === trackId)!
  const reqs = MATRIC_REQUIREMENTS[trackId]
  const usedSubjects: { id: string; grade: string }[] = []
  const usedIds = new Set<string>()

  // Check fixed requirements
  for (const req of reqs) {
    const candidates = [req.subjectId, ...(req.alternatives || [])]
    let found = false
    for (const subjId of candidates) {
      const grade = grades[subjId]
      if (grade && meetsMin(grade, req.minGrade)) {
        usedSubjects.push({ id: subjId, grade })
        usedIds.add(subjId)
        found = true
        break
      }
    }
    if (!found) {
      // Check if student has the subject but grade too low
      const hasSubject = candidates.some(id => grades[id])
      const subjectName = candidates[0]
      return {
        pathway: 'matric',
        trackId,
        trackName: track.name,
        trackNameMs: track.nameMs,
        trackNameTa: track.nameTa,
        eligible: false,
        reason: hasSubject ? 'pathways.gradeTooLow' : 'pathways.subjectMissing',
        reasonParams: { subject: subjectName, minGrade: req.minGrade },
      }
    }
  }

  // Fill remaining slots with best electives (for tracks that need them)
  const slotsNeeded = 4 - usedSubjects.length
  for (let i = 0; i < slotsNeeded; i++) {
    const minGrade = 'C'
    const elective = findBestElective(grades, usedIds, minGrade)
    if (!elective) {
      return {
        pathway: 'matric',
        trackId,
        trackName: track.name,
        trackNameMs: track.nameMs,
        trackNameTa: track.nameTa,
        eligible: false,
        reason: 'pathways.notEnoughElectives',
      }
    }
    usedSubjects.push(elective)
    usedIds.add(elective.id)
  }

  // Calculate merit
  const subjectPoints = usedSubjects.reduce(
    (sum, s) => sum + (MATRIC_GRADE_POINTS[s.grade] || 0), 0
  )
  const academic = (subjectPoints / 100) * 90
  const coq = Math.min(Math.max(coqScore, 0), 10)
  const merit = Math.min(academic + coq, 100)

  return {
    pathway: 'matric',
    trackId,
    trackName: track.name,
    trackNameMs: track.nameMs,
    trackNameTa: track.nameTa,
    eligible: true,
    merit: Math.round(merit * 100) / 100,
  }
}

// --- STPM (Form 6) ---

// Subject groups for STPM Science bidang
// Student must have credits from 3 DIFFERENT groups
const STPM_SCIENCE_GROUPS: string[][] = [
  ['MAT', 'AMT'],
  ['PHY'],
  ['CHE'],
  ['BIO'],
  ['ENG_DRAW', 'ENG_MECH', 'ENG_CIVIL', 'ENG_ELEC', 'REKA_CIPTA',
   'SPORTS_SCI', 'SRT', 'COMP_SCI', 'GKT'],
]

// Subject groups for STPM Social Science bidang
const STPM_SOCSCI_GROUPS: string[][] = [
  ['BM'],
  ['BI'],
  ['SEJ'],
  ['GEO', 'PSV'],
  ['PI', 'PM'],
  ['MAT', 'AMT'],
  ['ACC'],
  ['SN', 'ADDSCI'],
  ['ECO', 'BUS', 'KEUSAHAWANAN', 'SPORTS_SCI', 'SRT', 'COMP_SCI',
   'GKT', 'PERTANIAN'],
]

export interface StpmBidang {
  id: string
  name: string
  nameMs: string
  nameTa: string
  maxMataGred: number
}

export const STPM_BIDANGS: StpmBidang[] = [
  { id: 'sains', name: 'Science', nameMs: 'Sains', nameTa: 'அறிவியல்', maxMataGred: 18 },
  { id: 'sains_sosial', name: 'Social Science', nameMs: 'Sains Sosial', nameTa: 'சமூக அறிவியல்', maxMataGred: 12 },
]

function checkStpmBidang(
  bidangId: string,
  grades: Record<string, string>
): PathwayResult {
  const bidang = STPM_BIDANGS.find(b => b.id === bidangId)!
  const groups = bidangId === 'sains' ? STPM_SCIENCE_GROUPS : STPM_SOCSCI_GROUPS

  // General requirement: credit in BM
  const bmGrade = grades['BM']
  if (!bmGrade || !isCredit(bmGrade)) {
    return {
      pathway: 'stpm',
      trackId: bidangId,
      trackName: bidang.name,
      trackNameMs: bidang.nameMs,
      trackNameTa: bidang.nameTa,
      eligible: false,
      maxMataGred: bidang.maxMataGred,
      reason: 'pathways.bmCreditRequired',
    }
  }

  // Find best 3 credits from different groups
  // Greedy: try each group, pick the subject with lowest mata gred
  type Pick = { groupIdx: number; subjectId: string; mataGred: number }
  const candidates: Pick[] = []

  for (let gi = 0; gi < groups.length; gi++) {
    let bestInGroup: Pick | null = null
    for (const subjId of groups[gi]) {
      const grade = grades[subjId]
      if (!grade || !isCredit(grade)) continue
      const mg = STPM_MATA_GRED[grade]
      if (!bestInGroup || mg < bestInGroup.mataGred) {
        bestInGroup = { groupIdx: gi, subjectId: subjId, mataGred: mg }
      }
    }
    if (bestInGroup) candidates.push(bestInGroup)
  }

  // Sort by mata gred (lowest first = best)
  candidates.sort((a, b) => a.mataGred - b.mataGred)

  if (candidates.length < 3) {
    return {
      pathway: 'stpm',
      trackId: bidangId,
      trackName: bidang.name,
      trackNameMs: bidang.nameMs,
      trackNameTa: bidang.nameTa,
      eligible: false,
      maxMataGred: bidang.maxMataGred,
      reason: 'pathways.notEnoughCredits',
      reasonParams: { needed: '3', have: String(candidates.length) },
    }
  }

  // Take best 3
  const best3 = candidates.slice(0, 3)
  const totalMataGred = best3.reduce((sum, p) => sum + p.mataGred, 0)

  if (totalMataGred > bidang.maxMataGred) {
    return {
      pathway: 'stpm',
      trackId: bidangId,
      trackName: bidang.name,
      trackNameMs: bidang.nameMs,
      trackNameTa: bidang.nameTa,
      eligible: false,
      mataGred: totalMataGred,
      maxMataGred: bidang.maxMataGred,
      reason: 'pathways.mataGredTooHigh',
      reasonParams: { total: String(totalMataGred), max: String(bidang.maxMataGred) },
    }
  }

  return {
    pathway: 'stpm',
    trackId: bidangId,
    trackName: bidang.name,
    trackNameMs: bidang.nameMs,
    trackNameTa: bidang.nameTa,
    eligible: true,
    mataGred: totalMataGred,
    maxMataGred: bidang.maxMataGred,
  }
}

// --- Prestige Scoring ---
// Pre-university pathways get a prestige bonus + academic bonus
// so they compete fairly with quiz-boosted courses (max 120).

const PRESTIGE_BONUS = 8
const BASE_SCORE = 100

function matricAcademicBonus(merit: number): number {
  if (merit >= 92) return 8
  if (merit >= 87) return 5
  if (merit >= 82) return 3
  return 0 // below 82 = not eligible (shouldn't reach here)
}

function stpmAcademicBonus(mataGred: number, bidangId: string): number {
  if (bidangId === 'sains') {
    if (mataGred <= 6) return 8
    if (mataGred <= 10) return 5
    if (mataGred <= 14) return 3
    if (mataGred <= 18) return 1
    return 0
  }
  // sains_sosial
  if (mataGred <= 4) return 8
  if (mataGred <= 7) return 5
  if (mataGred <= 10) return 3
  if (mataGred <= 12) return 1
  return 0
}

export function getPathwayFitScore(result: PathwayResult): number {
  if (!result.eligible) return 0
  if (result.pathway === 'matric' && result.merit !== undefined) {
    return BASE_SCORE + PRESTIGE_BONUS + matricAcademicBonus(result.merit)
  }
  if (result.pathway === 'stpm' && result.mataGred !== undefined) {
    return BASE_SCORE + PRESTIGE_BONUS + stpmAcademicBonus(result.mataGred, result.trackId)
  }
  return BASE_SCORE + PRESTIGE_BONUS
}

// --- Public API ---

export function checkAllPathways(
  grades: Record<string, string>,
  coqScore: number
): PathwayResult[] {
  const results: PathwayResult[] = []

  // Matriculation tracks
  for (const track of MATRIC_TRACKS) {
    results.push(checkMatricTrack(track.id, grades, coqScore))
  }

  // STPM bidang
  for (const bidang of STPM_BIDANGS) {
    results.push(checkStpmBidang(bidang.id, grades))
  }

  return results
}
