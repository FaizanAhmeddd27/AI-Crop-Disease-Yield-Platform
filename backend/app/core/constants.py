"""Constants shared across the API."""

from __future__ import annotations

# Image formats accepted by the disease endpoint (PRD F1 / FR-D-003).
SUPPORTED_IMAGE_MIME_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})
SUPPORTED_IMAGE_FORMATS: frozenset[str] = frozenset({"JPEG", "PNG", "WEBP"})

# Yield outputs are always expressed per hectare (ARCH §7.2).
YIELD_UNIT = "t/ha"

# Prediction status values (ARCH §7.2).
STATUS_OK = "ok"
STATUS_UNCERTAIN = "uncertain"
STATUS_NOT_A_LEAF = "not_a_leaf"
