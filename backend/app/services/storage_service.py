import base64
from typing import Optional, Dict
from supabase import create_client, Client
from app.core.config import settings
import structlog
import uuid

logger = structlog.get_logger()

class StorageService:
    """
    Service for interacting with Supabase Storage.
    """
    
    _client: Optional[Client] = None
    BUCKET_NAME = "evidence"

    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in config.")
            cls._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return cls._client

    @classmethod
    async def upload_file(cls, file_bytes: bytes, file_name: str, mime_type: str) -> Dict[str, str]:
        """
        Uploads a file to Supabase Storage.
        Returns dict with 'path', 'full_url', 'bucket'.
        """
        try:
            client = cls.get_client()
            
            # Generate a unique path to avoid collisions
            # structure: <year>/<month>/<uuid>_<filename>
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            unique_name = f"{uuid.uuid4()}_{file_name}"
            file_path = f"{now.year}/{now.month}/{unique_name}"
            
            bucket = client.storage.from_(cls.BUCKET_NAME)

            # Upload
            res = bucket.upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": mime_type}
            )
            
            # Get Public URL
            public_url = bucket.get_public_url(file_path)
            
            return {
                "bucket": cls.BUCKET_NAME,
                "path": file_path,
                "full_url": public_url,
                "file_name": file_name,
                "mime_type": mime_type,
                "size_bytes": len(file_bytes)
            }
            
        except Exception as e:
            logger.error("storage_upload_failed", error=str(e), file_name=file_name)
            # Retain original behavior if upload fails? Or re-raise?
            # For now, log and re-raise so we know it failed.
            raise e
