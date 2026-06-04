import asyncio
from app.core.database import async_session
from sqlalchemy import select, func, delete
from app.models.database import AdminMessage

async def reset():
    async with async_session() as session:
        cnt = await session.execute(select(func.count()).select_from(AdminMessage).where(AdminMessage.dle_user_id == 286601))
        before = cnt.scalar()
        print(f"До удаления: {before} сообщений")

        stmt = delete(AdminMessage).where(AdminMessage.dle_user_id == 286601)
        await session.execute(stmt)
        await session.commit()

        cnt2 = await session.execute(select(func.count()).select_from(AdminMessage).where(AdminMessage.dle_user_id == 286601))
        after = cnt2.scalar()
        print(f"После удаления: {after} сообщений")
        print("OK")

asyncio.run(reset())
