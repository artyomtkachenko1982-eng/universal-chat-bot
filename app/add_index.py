import asyncio
from app.core.database import engine
from sqlalchemy import text

async def main():
    async with engine.connect() as conn:
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ad_status_created ON ad_requests(status, created_at DESC)"))
            await conn.commit()
            print("OK: ad index")
        except Exception as e:
            print(f"ad: {e}")
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_news_status_created ON news_suggestions(status, created_at DESC)"))
            await conn.commit()
            print("OK: news index")
        except Exception as e:
            print(f"news: {e}")

asyncio.run(main())
