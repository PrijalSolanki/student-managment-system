"""Reusable validators used across the project (backend validation)."""

from __future__ import annotations

import os
import re

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

PHONE_RE = re.compile(r"^\+?[0-9][0-9\-\s]{6,19}$")
PINCODE_RE = re.compile(r"^[0-9]{4,10}$")
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_./]{1,29}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._\-@]{3,150}$")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "doc",
    "docx",
    "xls",
    "xlsx",
}
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
DOCUMENT_MIME_TYPES = IMAGE_MIME_TYPES | {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def validate_phone(value):
    """Validate an Indian/international style phone number."""
    if value in (None, ""):
        return
    cleaned = re.sub(r"[\s\-()]", "", str(value))
    if not cleaned.isdigit():
        raise ValidationError("Enter a valid phone number (digits only).")
    if not (7 <= len(cleaned) <= 15):
        raise ValidationError("Phone number must contain between 7 and 15 digits.")


def validate_pincode(value):
    if value in (None, ""):
        return
    if not PINCODE_RE.match(str(value).strip()):
        raise ValidationError("Enter a valid PIN / ZIP code (4-10 digits).")


def validate_code(value):
    """Department / course / subject codes."""
    if value in (None, ""):
        return
    if not CODE_RE.match(str(value).strip()):
        raise ValidationError(
            "Code must be 2-30 characters and may contain letters, digits, "
            "hyphen, underscore, dot or slash."
        )


@deconstructible
class FileSizeValidator:
    message = "File is too large."
    code = "file_too_large"

    def __init__(self, max_size_mb=5):
        self.max_size = int(max_size_mb) * 1024 * 1024

    def __call__(self, value):
        size = getattr(value, "size", None)
        if size is not None and size > self.max_size:
            limit = self.max_size // (1024 * 1024)
            raise ValidationError(
                f"File is too large (max {limit} MB).", code=self.code
            )

    def __eq__(self, other):
        return isinstance(other, FileSizeValidator) and other.max_size == self.max_size


@deconstructible
class FileExtensionValidator:
    """Validate uploaded file extensions and (when available) MIME types."""

    message = "Unsupported file type."
    code = "invalid_file_type"

    def __init__(self, allowed_extensions, mime_types=None):
        self.allowed_extensions = {
            str(ext).lower().lstrip(".") for ext in allowed_extensions
        }
        self.mime_types = set(mime_types or ())

    def __call__(self, value):
        if value in (None, ""):
            return
        name = getattr(value, "name", str(value))
        extension = os.path.splitext(name)[1].lower().lstrip(".")
        if extension not in self.allowed_extensions:
            raise ValidationError(
                "Unsupported file type '.%(ext)s'. Allowed: %(allowed)s.",
                code=self.code,
                params={
                    "ext": extension or "unknown",
                    "allowed": ", ".join(sorted(self.allowed_extensions)),
                },
            )
        content_type = getattr(value, "content_type", None)
        if content_type and self.mime_types and content_type not in self.mime_types:
            raise ValidationError(
                "The uploaded file content type (%(ct)s) is not allowed.",
                code=self.code,
                params={"ct": content_type},
            )

    def __eq__(self, other):
        return (
            isinstance(other, FileExtensionValidator)
            and other.allowed_extensions == self.allowed_extensions
            and other.mime_types == self.mime_types
        )


validate_image = FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS, IMAGE_MIME_TYPES)
validate_document = FileExtensionValidator(ALLOWED_DOCUMENT_EXTENSIONS, DOCUMENT_MIME_TYPES)


def validate_positive(value, field_name="Amount"):
    if value in (None, ""):
        return
    if float(value) <= 0:
        raise ValidationError(f"{field_name} must be greater than zero.")


def validate_non_negative(value, field_name="Amount"):
    if value in (None, ""):
        return
    if float(value) < 0:
        raise ValidationError(f"{field_name} cannot be negative.")
