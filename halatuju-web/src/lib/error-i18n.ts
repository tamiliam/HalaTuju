// Maps backend English error/success strings → i18n keys
export const ERROR_MAP: Record<string, string> = {
  'Course not found': 'apiErrors.courseNotFound',
  'Not found': 'apiErrors.notFound',
  'Course saved': 'apiErrors.courseSaved',
  'Course removed': 'apiErrors.courseRemoved',
  'Invalid status': 'apiErrors.invalidStatus',
  'Profile updated': 'apiErrors.profileUpdated',
  'Profile synced': 'apiErrors.profileSynced',
  'NRIC is required': 'apiErrors.nricRequired',
  'Invalid NRIC format': 'apiErrors.invalidNricFormat',
  'Invalid NRIC: date portion is not valid': 'apiErrors.invalidNricDate',
  'IC number must belong to a student aged 15-23': 'apiErrors.nricAgeRange',
  'Invalid state code in IC number': 'apiErrors.invalidStateCode',
  'Email is required': 'apiErrors.emailRequired',
  'Profile not found': 'apiErrors.profileNotFound',
  'Too many verification requests. Please try again later.': 'apiErrors.tooManyVerifications',
  'Invalid token': 'apiErrors.invalidToken',
  'Token already used': 'apiErrors.tokenUsed',
  'Token expired': 'apiErrors.tokenExpired',
  'course_id is required': 'apiErrors.courseIdRequired',
  'Outcome already exists for this course/institution': 'apiErrors.outcomeExists',
  'Outcome not found': 'apiErrors.outcomeNotFound',
  'Outcome created': 'apiErrors.outcomeCreated',
  'Outcome updated': 'apiErrors.outcomeUpdated',
  'Outcome deleted': 'apiErrors.outcomeDeleted',
  'Daily report limit reached (max 3 per day). Please try again tomorrow.': 'apiErrors.reportLimitReached',
  'Report not found': 'apiErrors.reportNotFound',
  'Course data not loaded': 'apiErrors.courseDataNotLoaded',
  'Status updated': 'apiErrors.statusUpdated',
  // Admin errors
  'Not a partner admin': 'apiErrors.notPartnerAdmin',
  'Super admin access required': 'apiErrors.superAdminRequired',
  'Student not found': 'apiErrors.studentNotFound',
  'Student deleted': 'apiErrors.studentDeleted',
  'Admin with this email already exists': 'apiErrors.adminExists',
  'Organisation not found': 'apiErrors.orgNotFound',
  'Failed to send invite email': 'apiErrors.inviteEmailFailed',
  'Admin not found': 'apiErrors.adminNotFound',
  'Cannot revoke super admin': 'apiErrors.cannotRevokeSuperAdmin',
  'Not an admin': 'apiErrors.notAdmin',
}

// Patterns for interpolated backend messages (f-strings with dynamic values)
const PATTERN_MAP: Array<[RegExp, string]> = [
  [/^Invite sent to /, 'apiErrors.inviteSent'],
  [/ access revoked$/, 'apiErrors.accessRevoked'],
  [/ access restored$/, 'apiErrors.accessRestored'],
]

/**
 * Translate a backend error/success message using the i18n system.
 * Checks exact matches first, then regex patterns for interpolated messages.
 * Falls back to the generic "Something went wrong" message for unknown strings.
 */
export function tError(
  t: (key: string, params?: Record<string, string>) => string,
  backendMessage: string | undefined | null
): string {
  if (!backendMessage) return t('errors.somethingWentWrong')
  const key = ERROR_MAP[backendMessage]
  if (key) return t(key)
  const pattern = PATTERN_MAP.find(([re]) => re.test(backendMessage))
  if (pattern) return t(pattern[1])
  return t('errors.somethingWentWrong')
}
