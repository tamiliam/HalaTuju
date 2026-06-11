"""HEIC → JPEG conversion.

iPhone photos upload as ``image/heic``, which no browser can render inline (the officer's "View"
silently downloads them) and Cloud Vision can't OCR. We convert them to JPEG server-side at upload
(and via the ``convert_heic_documents`` command for any already stored), replacing the stored
object in place so the cockpit viewer, Vision OCR, and the download URL all see a JPEG.

Soft by construction: any failure (library missing, fetch/decode error) leaves the original
untouched — the viewer still offers "open the original" and nothing breaks.
"""
import io
import logging
import re

logger = logging.getLogger(__name__)

_HEIC_TYPES = ('image/heic', 'image/heif')


def is_heic(doc) -> bool:
    """True if the document is a HEIC/HEIF image (by content-type or filename extension)."""
    ct = (getattr(doc, 'content_type', '') or '').lower()
    fn = (getattr(doc, 'original_filename', '') or '').lower()
    return ct in _HEIC_TYPES or fn.endswith('.heic') or fn.endswith('.heif')


def convert_heic_to_jpeg(doc) -> bool:
    """If ``doc`` is HEIC/HEIF, convert the stored object to JPEG in place and update the row
    (content_type → image/jpeg, filename → .jpg). Returns True iff a conversion happened; a no-op
    (False) for a non-HEIC doc or on any failure — the original is always left intact."""
    if not is_heic(doc):
        return False
    try:
        from PIL import Image
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        logger.warning('pillow-heif/Pillow not installed — cannot convert HEIC %s',
                       getattr(doc, 'storage_path', ''))
        return False

    from .storage import upload_object
    from .vision import _fetch_image_bytes

    raw = _fetch_image_bytes(doc.storage_path)
    if raw is None:
        return False
    try:
        out = io.BytesIO()
        Image.open(io.BytesIO(raw)).convert('RGB').save(out, format='JPEG', quality=90)
        jpeg = out.getvalue()
    except Exception:
        logger.warning('HEIC decode/convert failed for %s', doc.storage_path, exc_info=True)
        return False

    if not upload_object(doc.storage_path, jpeg, 'image/jpeg'):
        return False

    doc.content_type = 'image/jpeg'
    fn = getattr(doc, 'original_filename', '') or ''
    if fn and not fn.lower().endswith(('.jpg', '.jpeg')):
        doc.original_filename = re.sub(r'\.(heic|heif)$', '.jpg', fn, flags=re.IGNORECASE)
        if not doc.original_filename.lower().endswith(('.jpg', '.jpeg')):
            doc.original_filename = doc.original_filename + '.jpg'
    doc.save(update_fields=['content_type', 'original_filename'])
    logger.info('Converted HEIC → JPEG for document %s', getattr(doc, 'id', '?'))
    return True
