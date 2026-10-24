"""Test environment. Variables are set BEFORE any ``app`` module is imported, because
``app.core.config.settings`` is created at import time."""

import os
import shutil
from pathlib import Path

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "SECRET_KEY": "unit-test-secret-key-0123456789abcdef0123456789abcdef",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "GEMINI_API_KEY": "test-gemini-key",
        "GEMINI_AUTO_DISCOVER": "false",
        "ADMIN_PASSWORD": "correct horse battery staple",
        "ADMIN_PASSWORD_HASH": "",
        "RATE_LIMIT_ENABLED": "false",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": os.path.join(os.path.dirname(__file__), ".tmp_storage"),
        "LOG_LEVEL": "WARNING",
    }
)
# Never let a developer's local env file leak real credentials into the tests.
for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"):
    os.environ.pop(var, None)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tests.fake_ai import FakeAI  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _clean_storage_dir():
    root = Path(os.environ["LOCAL_STORAGE_DIR"])
    shutil.rmtree(root, ignore_errors=True)
    yield
    shutil.rmtree(root, ignore_errors=True)


@pytest_asyncio.fixture
async def fake_ai():
    """Scripted Gemini API wired into the application's shared client."""
    from app.services.gemini import gemini

    fake = FakeAI()
    fake.install()
    yield fake
    await gemini.aclose()
    gemini.__init__()  # type: ignore[misc]  # back to the real configuration


@pytest_asyncio.fixture
async def db_engine():
    from app.db.init_db import ensure_schema
    from app.db.session import dispose_engine, use_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    use_engine(engine)
    await ensure_schema(engine)
    yield engine
    await dispose_engine()


@pytest_asyncio.fixture
async def client(db_engine, fake_ai):
    """HTTP client talking to the real ASGI app (lifespan/maintenance loops are not started)."""
    from app.core import rate_limit
    from app.main import app

    rate_limit.reset_all()
    app.state.db_connected = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    rate_limit.reset_all()


@pytest.fixture
def enable_rate_limits(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)


@pytest.fixture
def png_bytes() -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(out, format="PNG")
    return out.getvalue()
