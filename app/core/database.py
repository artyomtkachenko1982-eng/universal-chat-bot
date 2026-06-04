"""
database.py — Подключение к PostgreSQL и Redis

Этот файл настраивает соединения с базами данных.
Используется в main.py при запуске и остановке бота.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import settings
from app.models.database import Base

# --------------------------------------------------
# PostgreSQL
# --------------------------------------------------

# Асинхронный движок SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # если DEBUG=true — показывать SQL запросы в логах
)

# Фабрика сессий (каждый запрос получает свою сессию)
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """
    Создаёт все таблицы в БД (если их ещё нет).
    Вызывается при старте приложения.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Добавляем новые колонки для баннера/статьи (если ещё нет)
        await conn.execute(text("""
            ALTER TABLE ad_requests
            ADD COLUMN IF NOT EXISTS article_opts VARCHAR(100),
            ADD COLUMN IF NOT EXISTS article_fix_days INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS banner_size VARCHAR(20) DEFAULT '728x90',
            ADD COLUMN IF NOT EXISTS banner_placement VARCHAR(20) DEFAULT 'in_news',
            ADD COLUMN IF NOT EXISTS banner_months INTEGER DEFAULT 1,
            ADD COLUMN IF NOT EXISTS banner_opts VARCHAR(100),
            ADD COLUMN IF NOT EXISTS pin_platforms VARCHAR(100)
        """))


async def get_session() -> AsyncSession:
    """
    Выдаёт сессию для одного запроса.
    Использовать как зависимость в FastAPI:
        @router.get("/something")
        async def handler(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session() as session:
        yield session


async def close_db():
    """Закрывает соединение с БД. Вызывается при остановке."""
    await engine.dispose()
