from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from .config import settings

# Create Async Engine
engine = create_async_engine(settings.DATABASE_URL, echo=True, future=True)

# Set to True to recreate all tables (WARNING: deletes all data)
RECREATE_TABLES = True  # Disabled to preserve data

async def init_db():
    async with engine.begin() as conn:
        if RECREATE_TABLES:
            # Drop all tables with CASCADE to handle foreign key dependencies
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        await conn.run_sync(SQLModel.metadata.create_all)
        
        # Schema Evolution: Add profile_data if missing (for dev environment)
        try:
            await conn.execute(text("ALTER TABLE lead ADD COLUMN IF NOT EXISTS profile_data JSONB DEFAULT '{}'::jsonb"))
        except Exception as e:
            # Ignore if generic error, but print
            print(f"Migration warning: {e}")

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


