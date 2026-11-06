/**
 * The Content-Type to send when PUTting a file to a signed Storage URL.
 * Some browsers give a .heic file an empty type; the bucket's type list would then refuse it,
 * so fall back to the file extension before giving up and sending octet-stream.
 *
 * The table is INSIDE the function on purpose: a top-level const makes this module count as having side
 * effects, so the `@/lib/api` barrel can no longer drop the documents client from pages that never use it
 * (+2.8 kB on the median route, G3 bundle gate).
 */
export function uploadContentType(file: { type?: string; name?: string }): string {
  const BY_EXTENSION: Record<string, string> = {
    pdf: 'application/pdf',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    webp: 'image/webp',
    heic: 'image/heic',
    heif: 'image/heif',
    gif: 'image/gif',
    bmp: 'image/bmp',
    tif: 'image/tiff',
    tiff: 'image/tiff',
  }
  if (file.type) return file.type
  const name = file.name || ''
  const dot = name.lastIndexOf('.')
  const ext = dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
  return BY_EXTENSION[ext] || 'application/octet-stream'
}
