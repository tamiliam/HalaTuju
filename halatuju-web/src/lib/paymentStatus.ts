// Payment-run status → pill classes (shared by the Payments landing + detail pages).
export const statusPill = (s: string) =>
  s === 'completed' ? 'bg-green-100 text-green-700'
  : s === 'admin_signed' ? 'bg-amber-100 text-amber-700'
  : s === 'cancelled' ? 'bg-gray-100 text-gray-500'
  : 'bg-blue-100 text-blue-700'   // draft
