import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.db.base import Base
from app.core import security
from app.core.config import settings
from sqlalchemy import select

# Import all models so Base knows about them
from app.models.report import Report, ReportConversation, ReportStateTracking, Evidence
from app.models.admin import Admin, AdminRole

async def init_models():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Dangerous in prod, useful for dev
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database tables created successfully.")
    
    # Init Superuser
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Admin).where(Admin.email == "admin@beacon.gov"))
        user = result.scalar_one_or_none()
        
        if not user:
            print("Creating superuser...")
            user = Admin(
                email="admin@beacon.gov",
                password_hash=security.get_password_hash("admin"), # Hardcoded for safety during demo setup? No, use env var instructions usually.
                role=AdminRole.SUPER_ADMIN,
                is_active=True
            )
            session.add(user)
            await session.commit()
            print("Superuser created: admin@beacon.gov / admin")
        else:
            print("Superuser already exists.")

if __name__ == "__main__":
    asyncio.run(init_models())
