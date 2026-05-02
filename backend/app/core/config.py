from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Beacon AI"
    ENVIRONMENT: str = "production"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    ADMIN_PASSWORD_HASH: Union[str, None] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            return v
        if not isinstance(v, str) or not v.strip():
            return []
        raw = v.strip()
        # Handle JSON array: ["https://a.com","https://b.com"]
        if raw.startswith("["):
            import json
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(i).strip() for i in parsed]
            except json.JSONDecodeError:
                pass
            # Fallback: strip brackets and split
            raw = raw[1:-1] if raw.endswith("]") else raw[1:]
        # Comma-separated: https://a.com,https://b.com
        return [i.strip().strip('"').strip("'") for i in raw.split(",") if i.strip()]

    # Database
    DATABASE_URL: str
    
    # Supabase Storage & Client
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Union[str, None] = None

    # AI
    GEMINI_API_KEY: str
    GROQ_API_KEY: str = ""  # Deprecated - using Gemini instead

    # Logging
    LOG_LEVEL: str = "INFO"


    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file="backend_config.env",
        env_file_encoding="utf-8"
    )

settings = Settings()
