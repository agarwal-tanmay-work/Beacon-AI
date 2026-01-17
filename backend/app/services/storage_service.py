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
        Uploads a file to Supabase Storage using Direct HTTP API to ensure Service Role Key is used.
        Directly bypasses RLS policies if the Service Role Key is correct.
        """
        import httpx
        from datetime import datetime, timezone
        
        try:
            # Prefer Service Role Key for backend operations
            api_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
            base_url = settings.SUPABASE_URL
            
            if not api_key:
                raise ValueError("Missing Supabase API Key")

            # Generate path
            now = datetime.now(timezone.utc)
            unique_name = f"{uuid.uuid4()}_{file_name}"
            file_path = f"{now.year}/{now.month}/{unique_name}"
            
            # Direct API Endpoint: {supabase_url}/storage/v1/object/{bucket}/{path}
            url = f"{base_url}/storage/v1/object/{cls.BUCKET_NAME}/{file_path}"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "apikey": api_key,
                "Content-Type": mime_type,
                "x-upsert": "true" 
            }
            
            # Determine timeout (usually longer for uploads)
            timeout = httpx.Timeout(60.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, content=file_bytes, headers=headers)
                
                if response.status_code not in range(200, 300):
                    # Try to parse error
                    error_text = response.text
                    logger.error("storage_upload_http_error", status=response.status_code, response=error_text)
                    raise Exception(f"Supabase Upload Failed: {response.status_code} - {error_text}")

            # Construct Public URL
            # Format: {supabase_url}/storage/v1/object/public/{bucket}/{path}
            public_url = f"{base_url}/storage/v1/object/public/{cls.BUCKET_NAME}/{file_path}"
            
            return {
                "bucket": cls.BUCKET_NAME,
                "path": file_path,
                "full_url": public_url,
                "file_name": file_name,
                "mime_type": mime_type,
                "size_bytes": len(file_bytes),
                "storage_provider": "supabase"
            }
            
        except Exception as e:
            logger.error("storage_upload_failed", error=str(e), file_name=file_name)
            raise e

    @classmethod
    def download_file(cls, bucket_name: str, path: str) -> bytes:
        """
        Downloads a file from Supabase Storage (Synchronous for use in threadpools).
        """
        try:
            client = cls.get_client()
            return client.storage.from_(bucket_name).download(path)
        except Exception as e:
            logger.error("storage_download_failed", error=str(e), path=path)
            raise e
