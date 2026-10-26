"""Object storage service: Supabase Storage with local fallback (ARCH §7, Task 5.3)."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import httpx
from PIL import Image

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def local_storage_root() -> Path:
    """Local fallback storage directory, anchored to the backend package.

    Resolved from this file's location (backend/app/services/storage.py →
    backend/data/storage) so it is independent of the process working
    directory — the previous CWD-relative path created a nested
    `backend/backend/...` tree whenever uvicorn ran from `backend/`.
    """
    return (Path(__file__).resolve().parents[2] / "data" / "storage").resolve()


class StorageService:
    """Manages secure image uploads, EXIF data stripping, and URL generation."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.local_storage_dir = local_storage_root()
        self.local_storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_remote_configured(self) -> bool:
        return bool(self.settings.supabase_url and self.settings.supabase_service_role_key)

    def _storage_headers(self, content_type: str | None = None) -> dict[str, str]:
        """Build headers for both Supabase secret keys and legacy JWT keys."""
        key = self.settings.supabase_service_role_key
        headers = {"apikey": key}
        if key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def strip_exif_and_prepare_jpeg(self, image_bytes: bytes) -> tuple[bytes, int, int]:
        """Strip sensitive GPS/device EXIF metadata and re-encode to clean RGB JPEG."""
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size

        # Create clean RGB image discarding all EXIF info
        clean_img = Image.new("RGB", (width, height))
        clean_img.paste(image.convert("RGB"))

        out_io = io.BytesIO()
        clean_img.save(out_io, format="JPEG", quality=90)
        return out_io.getvalue(), width, height

    async def upload_file(
        self,
        file_bytes: bytes,
        destination_path: str,
        bucket_name: str = "agri-uploads",
        content_type: str = "image/jpeg",
    ) -> str:
        """Upload file bytes to Supabase Storage or local storage, returning access URL."""
        if self.is_remote_configured:
            try:
                object_url = (
                    f"{self.settings.supabase_url}/storage/v1/object/"
                    f"{bucket_name}/{destination_path}"
                )
                headers = self._storage_headers(content_type)
                headers["x-upsert"] = "true"
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(object_url, content=file_bytes, headers=headers)
                    if resp.status_code in (200, 201):
                        signed_url = await self.create_signed_url(
                            bucket_name,
                            destination_path,
                        )
                        if signed_url:
                            return signed_url
                        return (
                            f"{self.settings.supabase_url}/storage/v1/object/public/"
                            f"{bucket_name}/{destination_path}"
                        )
                    logger.warning(
                        f"Supabase upload status {resp.status_code}: {resp.text}, "
                        "using local storage"
                    )
            except Exception as e:
                logger.warning(f"Supabase upload exception: {e}, falling back to local storage")

        # Local fallback
        bucket_dir = self.local_storage_dir / bucket_name
        bucket_dir.mkdir(parents=True, exist_ok=True)
        local_file = bucket_dir / destination_path
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(file_bytes)

        return f"/api/v1/storage/{bucket_name}/{destination_path}"

    async def delete_file(self, bucket_name: str, destination_path: str) -> bool:
        """Delete an object from remote storage and the local fallback.

        Returns True when at least the remote copy was removed (or nothing
        existed remotely and the local copy was removed).
        """
        remote_deleted = False
        if self.is_remote_configured:
            try:
                url = (
                    f"{self.settings.supabase_url}/storage/v1/object/"
                    f"{bucket_name}/{destination_path}"
                )
                headers = self._storage_headers()
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.delete(url, headers=headers)
                if resp.status_code in (200, 204):
                    remote_deleted = True
                elif resp.status_code not in (404, 400):
                    logger.warning(f"Supabase delete status {resp.status_code}: {resp.text}")
            except Exception as e:  # noqa: BLE001 - deletion must never raise
                logger.warning(f"Supabase delete exception: {e}")

        try:
            local_file = self.local_storage_dir / bucket_name / destination_path
            local_file.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Local delete failed for {bucket_name}/{destination_path}: {e}")

        if not self.is_remote_configured:
            local_file = self.local_storage_dir / bucket_name / destination_path
            return not local_file.exists()
        return remote_deleted

    async def create_signed_url(
        self,
        bucket_name: str,
        destination_path: str,
        expires_in_seconds: int = 900,
    ) -> str | None:
        """Signed read URL for a private bucket object (≤15 min, ARCH §9).

        Only available when the remote is configured; returns None otherwise
        so callers can serve the object through the local storage endpoint.
        """
        if not self.is_remote_configured:
            return None
        url = (
            f"{self.settings.supabase_url}/storage/v1/object/sign/{bucket_name}/{destination_path}"
        )
        headers = self._storage_headers("application/json")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    url, json={"expiresIn": expires_in_seconds}, headers=headers
                )
            if resp.status_code == 200:
                signed = resp.json().get("signedURL") or resp.json().get("signedUrl")
                if signed:
                    if signed.startswith("/"):
                        prefix = "" if signed.startswith("/storage/v1/") else "/storage/v1"
                        signed = f"{self.settings.supabase_url.rstrip('/')}{prefix}{signed}"
                    return signed
            logger.warning(f"Supabase sign status {resp.status_code}: {resp.text}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Supabase sign exception: {e}")
        return None
