// Payment-run status → pill classes (shared by the Payments landing + detail pages).
export const statusPill = (s: string) =>
  s === 'completed' ? 'bg-green-100 text-green-700'
  : s === 'admin_signed' ? 'bg-amber-100 text-amber-700'
  : s === 'cancelled' ? 'bg-gray-100 text-gray-500'
  : 'bg-blue-100 text-blue-700'   // draft

// The month a run pays for, e.g. '2026-07-01' → 'Jul 2026'. Hand-formatted (deterministic,
// hydration-safe — never toLocaleDateString, whose locale differs on the server).
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const monthLabel = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const [y, m] = iso.split('-')
  const i = Number(m) - 1
  return MONTHS[i] ? `${MONTHS[i]} ${y}` : iso
}
