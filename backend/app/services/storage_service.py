import os
import aiofiles
from pathlib import Path
from fastapi import UploadFile

class StorageService:
    UPLOAD_DIR = "uploads"

    @classmethod
    async def save_file(cls, content: bytes, filename: str) -> str:
        """
        Save file to local storage (or S3).
        Returns the relative path/key.
        """
        # Ensure directory exists
        Path(cls.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        
        file_path = os.path.join(cls.UPLOAD_DIR, filename)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
            
        return filename
