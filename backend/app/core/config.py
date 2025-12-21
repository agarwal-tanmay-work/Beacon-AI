from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Beacon AI"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip("[").strip("]").strip('"').strip("'")
            if not v:
                return []
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError(v)

    # Database - should be provided via DATABASE_URL env var
    DATABASE_URL: str
    
    # Supabase Storage & Client
    SUPABASE_URL: str = "https://myvmzqrkitrqxummzhjw.supabase.co"
    SUPABASE_KEY: str

    # AI
    # AI
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str
    # IMPORTANT: Ensure this is set in backend_config.env or replaced here

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file="backend_config.env",
        env_file_encoding="utf-8"
    )

settings = Settings()
