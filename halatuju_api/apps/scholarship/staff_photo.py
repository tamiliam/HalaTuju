"""Staff photos and the Team page's contact line (common profile S2, 2026-10-31).

A staff member (or a source user) may put ONE photo on their own profile. It is seen by staff only:
the header, their own Profile page, and the Team (People) page — NEVER a student, sponsor or
source-console payload (`test_staff_photo.py` holds those serializers to it).

THE FILE. `POST admin/me/photo/` takes one image of at most `MAX_BYTES`. What it IS is decided by the
CONTENT (Pillow opens it and names its format), never by the file name or the browser's type: only
JPEG, PNG and WebP are accepted. It is then RE-ENCODED — turned upright by its EXIF orientation,
shrunk to fit `MAX_SIDE` x `MAX_SIDE`, and saved as WebP with NO metadata at all, so a phone photo's
GPS position and camera details never reach the bucket. What is stored is therefore always a small
WebP we made, never the upload.

THE KEY. `staff-photos/<partner_admin id>/<uuid>.webp` in the private `b40-documents` bucket. Three
segments, and the first is not a number or `requests`, so `storage.resolve_org_for_path` reads NO
organisation from it — it is not a tenant file and no document signing seam will ever sign it. A
fresh uuid per upload means a replaced photo is a new object (the old one is deleted) and a cached
signed URL can never show the new face under the old address.

WHO KNOWS THE KEY. `ReviewerProfile.photo_path` (one per person). The orphan sweep reads it
(`cleanup_orphan_blobs.known_paths`) or `--apply` would delete every photo; the off-platform backup
copies it like every other object. Deleting the profile row — `AdminDeleteView` deletes the
`PartnerAdmin`, which cascades — deletes the object too (`on_profile_deleted`, after the commit).
"""
import io
import logging
import uuid

from django.db import transaction

from . import storage

logger = logging.getLogger(__name__)

MAX_BYTES = 2 * 1024 * 1024
MAX_SIDE = 512
#: Pillow's format names for what we accept — read from the bytes, never from the name.
ACCEPTED_FORMATS = frozenset({'JPEG', 'PNG', 'WEBP'})
#: A decompression-bomb guard (review fix L1): a phone photo is ~12 MP; 16 MP of RGBA is ~64 MB
#: decoded, which a 1 GiB, 8-thread instance can afford, and a 2 MB PNG of one colour can claim far more.
#: Read from the HEADER, before any pixel is decoded.
MAX_PIXELS = 16_000_000
PREFIX = 'staff-photos'
SIGNED_FOR = 3600          # seconds a served photo URL lives (about an hour)


class PhotoError(Exception):
    """A refusal with a stable code: `no_file`, `too_large`, `not_an_image`, `unsupported_type`."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def key_for(admin_id):
    return f'{PREFIX}/{admin_id}/{uuid.uuid4().hex}.webp'


def is_photo_key(path):
    return (path or '').startswith(f'{PREFIX}/')


def reencode(data):
    """The upload's bytes → our own small WebP bytes, or `PhotoError`. Content decides the type."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not data:
        raise PhotoError('no_file')
    if len(data) > MAX_BYTES:
        raise PhotoError('too_large')
    try:
        with Image.open(io.BytesIO(data)) as probe:   # reads the HEADER only
            fmt = probe.format
            width, height = probe.size
            # Type and size come off the header: refused here, nothing has been decoded yet.
            if fmt not in ACCEPTED_FORMATS:
                raise PhotoError('unsupported_type')
            if width * height > MAX_PIXELS:
                raise PhotoError('too_large')
            probe.verify()                       # a truncated or corrupt file stops here
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise PhotoError('not_an_image')
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format == 'JPEG':
                # Let libjpeg decode at a reduced scale (1/2 … 1/8) still at least twice the target.
                img.draft('RGB', (MAX_SIDE * 2, MAX_SIDE * 2))
            img = ImageOps.exif_transpose(img)   # upright, before the orientation tag is dropped
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            img = img.convert('RGBA' if img.mode in ('RGBA', 'LA', 'P') else 'RGB')
            out = io.BytesIO()
            # No `exif=` and no `icc_profile=`: the saved file carries no metadata at all.
            img.save(out, format='WEBP', quality=85, method=4)
    except (OSError, ValueError, Image.DecompressionBombError):
        raise PhotoError('not_an_image')
    return out.getvalue()


def signed_url(path):
    """A ~1-hour signed URL for one photo key, or None (no photo, or Storage could not sign)."""
    if not is_photo_key(path):
        return None
    return storage.create_signed_download_url(path, expires_in=SIGNED_FOR)


def _profiles_of(admins):
    """`{admin_id: profile}` — the profiles a list already JOINED (`select_related('reviewer_profile')`,
    as the reviewers list does: its query budget allows no extra query) are read from the row; the
    rest are fetched in ONE query."""
    from .models import StaffProfile
    out, missing = {}, []
    for a in admins:
        if type(a).reviewer_profile.is_cached(a):
            profile = getattr(a, 'reviewer_profile', None)
            if profile is not None:
                out[a.id] = profile
        else:
            missing.append(a.id)
    if missing:
        out.update({p.partner_admin_id: p for p in StaffProfile.objects.filter(partner_admin_id__in=missing)
                    .only('partner_admin_id', 'photo_path', 'phone', 'share_phone_with_team')})
    return out


def team_cards(admins):
    """`{admin_id: {'photo_url', 'phone'}}` for the Team (People) page — ONE query for the profiles
    and ONE batch signing call for every photo on the page, never one per row.

    ⚠ `phone` is the owner's number ONLY when they switched "show my phone to my team" on, else None
    (owner, 2026-10-31: this revises "a reviewer's phone is exposed by no other serializer" for the
    phone only). The address is never here."""
    ids = [a.id for a in admins]
    profiles = _profiles_of(admins)
    urls = storage.create_signed_download_urls(
        [p.photo_path for p in profiles.values() if is_photo_key(p.photo_path)], expires_in=SIGNED_FOR)
    out = {}
    for admin_id in ids:
        p = profiles.get(admin_id)
        out[admin_id] = {
            'photo_url': urls.get(p.photo_path) if p is not None and p.photo_path else None,
            'phone': (p.phone or None) if p is not None and p.share_phone_with_team else None,
        }
    return out


def phones_of(admins):
    """`{admin_id: phone or None}` — a SOURCE user's own phone, for the organisation that invited it
    (the Invitations → Source roster). Shown whatever the team switch says: a source has no team,
    and the owner's rule is that its inviting organisation sees the number (2026-10-31)."""
    profiles = _profiles_of(admins)
    return {a.id: ((profiles[a.id].phone or None) if a.id in profiles else None) for a in admins}


def replace(profile, data):
    """Re-encode and store a new photo for `profile`, then delete the old object. Returns the new key,
    or raises `PhotoError` (a refusal) / returns None (Storage could not take the file)."""
    encoded = reencode(data)
    key = key_for(profile.partner_admin_id)
    if not storage.upload_object(key, encoded, 'image/webp'):
        return None
    old = profile.photo_path
    profile.photo_path = key
    profile.save(update_fields=['photo_path', 'updated_at'])
    if is_photo_key(old) and old != key:
        storage.delete_objects([old])            # best effort: a leftover is the sweep's to find
    return key


def remove(profile):
    """Delete the stored photo (object first, then the path). True when nothing is left behind."""
    old = profile.photo_path
    if not old:
        return True
    if is_photo_key(old) and not storage.delete_objects([old]):
        return False
    profile.photo_path = ''
    profile.save(update_fields=['photo_path', 'updated_at'])
    return True


def on_profile_deleted(sender, instance, **kwargs):
    """`post_delete` of a profile row (a staff account deleted → CASCADE): its photo goes too, once
    the delete has COMMITTED — a rolled-back delete must not leave a row naming a deleted object."""
    path = getattr(instance, 'photo_path', '')
    if is_photo_key(path):
        transaction.on_commit(lambda: storage.delete_objects([path]))
