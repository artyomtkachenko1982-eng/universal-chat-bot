import asyncio
from app.core.database import async_session
from app.models.database import BotUser
from sqlalchemy import select

async def check():
    async with async_session() as session:
        result = await session.execute(select(BotUser).order_by(BotUser.dle_user_id))
        rows = result.scalars().all()
        print(f'Всего записей в BotUser: {len(rows)}')
        for r in rows:
            print(f'id={r.id} platform={r.platform} puid={r.platform_user_id} duid={r.dle_user_id} user={r.dle_username} grp={r.dle_group}')

asyncio.run(check())
