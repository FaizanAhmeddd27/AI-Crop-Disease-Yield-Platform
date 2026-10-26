"""Local storage file serving endpoint (ARCH §7.2, DEV_PLAN Task 5.3).

- GET /storage/{bucket}/{path:path} – Serve files from local fallback storage
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.storage import local_storage_root

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/storage", tags=["storage"])

LOCAL_STORAGE_ROOT = local_storage_root()


@router.get(
    "/{bucket}/{file_path:path}",
    summary="Serve locally stored image files",
    responses={
        404: {"description": "File not found"},
    },
)
async def serve_storage_file(bucket: str, file_path: str) -> FileResponse:
    """Serve files from local fallback storage when Supabase is not configured."""
    full_path = LOCAL_STORAGE_ROOT / bucket / file_path

    # Security: prevent path traversal
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(LOCAL_STORAGE_ROOT)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid path") from exc

    if not full_path.exists() or not full_path.is_file():
        detail = f"File not found: {bucket}/{file_path}"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    # Determine media type
    suffix = full_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".json": "application/json",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(full_path, media_type=media_type)
