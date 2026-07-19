// Single home for the public field-artwork bucket used by the course selector AND the
// sponsor pool. The sponsor card carries a resolved `field_image_slug` from the backend,
// so pages build the URL directly from a slug (no taxonomy lookup needed).

export const FIELD_IMAGE_BASE =
  'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'

/** Generic fallback artwork when a field has no specific image. */
export const GENERIC_FIELD_SLUG = 'umum-kemanusiaan'

/** Bright flat-illustration alternative set (no people/faces/text), used ONLY in the tight
 *  spots — the sponsor detail-page strip and the email thumbnail — where the photographic
 *  field-images crop badly. Same slug filenames, a separate public bucket. The browse card
 *  and the course selector keep the photographic `field-images`. */
export const FIELD_IMAGE_CONCEPT_BASE =
  'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images-concept'

/** Build a bucket URL from a slug; empty/undefined → the generic image. */
export function fieldImageUrl(slug: string | null | undefined): string {
  const s = (slug || '').trim() || GENERIC_FIELD_SLUG
  return `${FIELD_IMAGE_BASE}/${s}.png`
}

/** Concept-set URL from a slug (tight-spot use); empty/undefined → the generic illustration. */
export function conceptFieldImageUrl(slug: string | null | undefined): string {
  const s = (slug || '').trim() || GENERIC_FIELD_SLUG
  return `${FIELD_IMAGE_CONCEPT_BASE}/${s}.png`
}
