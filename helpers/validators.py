import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
DOCUMENT_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}

def validate_pan(pan: str) -> bool:
    """Validate Indian PAN number format: AAAAA9999A"""
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan.upper()))

def validate_gstin(gstin: str) -> bool:
    """Validate Indian GSTIN format: 22AAAAA0000A1Z5"""
    return bool(re.match(
        r'^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$',
        gstin.upper()
    ))

def validate_ifsc(ifsc: str) -> bool:
    """Validate IFSC code format: AAAA0NNNNNN"""
    return bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc.upper()))


def validate_uploaded_file(upload, *, allowed_extensions, allowed_content_types, max_size_mb, label="file"):
    if not upload:
        raise ValueError(f"{label.capitalize()} is required.")

    max_size = max_size_mb * 1024 * 1024
    if getattr(upload, "size", 0) > max_size:
        raise ValueError(f"{label.capitalize()} must be {max_size_mb}MB or smaller.")

    suffix = Path(getattr(upload, "name", "")).suffix.lower()
    if suffix not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"{label.capitalize()} must use one of these file types: {allowed}.")

    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type and content_type not in allowed_content_types:
        raise ValueError(f"{label.capitalize()} content type is not allowed.")

    return upload


def validate_image_upload(upload, *, max_size_mb=5, label="image"):
    validate_uploaded_file(
        upload,
        allowed_extensions=IMAGE_EXTENSIONS,
        allowed_content_types=IMAGE_CONTENT_TYPES,
        max_size_mb=max_size_mb,
        label=label,
    )

    current_position = upload.tell() if hasattr(upload, "tell") else None
    try:
        image = Image.open(upload)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"{label.capitalize()} must be a valid image.") from exc
    finally:
        if current_position is not None and hasattr(upload, "seek"):
            upload.seek(current_position)

    return upload


def validate_document_upload(upload, *, max_size_mb=10, label="document"):
    validate_uploaded_file(
        upload,
        allowed_extensions=DOCUMENT_EXTENSIONS,
        allowed_content_types=DOCUMENT_CONTENT_TYPES,
        max_size_mb=max_size_mb,
        label=label,
    )

    suffix = Path(getattr(upload, "name", "")).suffix.lower()
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if suffix in IMAGE_EXTENSIONS or content_type in IMAGE_CONTENT_TYPES:
        return validate_image_upload(upload, max_size_mb=max_size_mb, label=label)

    current_position = upload.tell() if hasattr(upload, "tell") else None
    try:
        header = upload.read(5)
        if header != b"%PDF-":
            raise ValueError(f"{label.capitalize()} must be a valid PDF or image.")
    finally:
        if current_position is not None and hasattr(upload, "seek"):
            upload.seek(current_position)

    return upload
