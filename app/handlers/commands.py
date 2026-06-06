"""
handlers/commands.py — Обработчики команд бота

Здесь логика всех команд: /start, /profile, /search и т.д.
Каждая функция = одна команда.

# DEPLOY_TEST: git-push-pull 2026-06-04 (тест симлинк-деплоя)
"""

from dataclasses import dataclass
from datetime import datetime

from app.core.dle_client import dle_client
from app.core.config import settings
from app.core.database import async_session
from app.models.database import AdminMessage, AdRequest, NewsSuggestion, BotUser
from app.schemas.user import AuthRequest, AuthResponse, UserProfile


@dataclass
class SearchResult:
    """
    Результат поиска: текст для показа + данные пагинации.

    text         — отформатированный текст с результатами
    has_more     — есть ли следующая страница
    current_page — текущая страница (1, 2, 3...)
    total_pages  — сколько всего страниц
    total_results — сколько всего найдено
    query        — поисковый запрос
    """
    text: str
    has_more: bool = False
    current_page: int = 1
    total_pages: int = 1
    total_results: int = 0
    query: str = ""
    items: list = None  # структурированные данные для карточек (фронт)


async def handle_start(platform: str, platform_user_id: str, message: str = "") -> str:
    """
    Команда /start или первое сообщение.
    Приветствует пользователя и просит авторизоваться.
    """
    greeting = (
        f"Приветствуем на turbinist.ru!\n\n"
        f"Для доступа к функциям бота необходимо авторизоваться.\n\n"
        f"Введите ваш логин (email или имя пользователя с сайта):"
    )
    return greeting


async def handle_auth(platform: str, platform_user_id: str, login: str, password: str, anon_name: str = "") -> AuthResponse:
    """
    Проверка логина/пароля через DLE API.
    anon_name — имя анонима (если логинится из анонимки), для привязки старых сообщений.
    """
    result = await dle_client.external_auth(login, password)

    # Мостик вернул: {"success": true, "data": true/false}
    # success — мостик отработал без ошибок
    # data — сам результат external_auth (true = верный пароль, false = неверный)
    if result.get("success") and result.get("data"):
        # Получаем данные пользователя
        user_info = await dle_client.take_user_by_name(login)
        user_data = user_info.get("data", {})

        if not user_data or user_data is False:
            return AuthResponse(
                success=False,
                message="Пользователь найден, но не удалось получить данные.",
            )

        # 🔒 Демо-режим: пускаем только из белого списка
        from app.core.config import settings
        if settings.DEMO_MODE:
            allowed = [int(x.strip()) for x in settings.ALLOWED_USERS.split(",") if x.strip()]
            user_id = int(user_data.get("user_id", 0))
            if user_id not in allowed:
                return AuthResponse(
                    success=False,
                    message="Бот в тестовом режиме. Доступ только для тестовых пользователей.",
                )

        # Привязываем старые анонимные сообщения к аккаунту
        user_id_val = int(user_data.get("user_id"))
        user_name_val = user_data.get("name")

        # 🔒 Админу анонимки не привязываем — это сообщения от других пользователей
        if user_id_val == settings.ADMIN_USER_ID:
            import logging
            logging.getLogger('uvicorn').info(f"🔒 Админ (user_id={user_id_val}) авторизован — пропускаем привязку анонимных сообщений")
        else:
            try:
                from app.models.database import AdminMessage
                from app.core.database import async_session
                from sqlalchemy import update
                import logging
                logger = logging.getLogger("uvicorn")
                async with async_session() as session:
                    # 1) Сначала пытаемся по platform_user_id (если аноним в той же сессии)
                    stmt = (
                        update(AdminMessage)
                        .where(AdminMessage.platform_user_id == platform_user_id)
                        .where(AdminMessage.dle_user_id.is_(None))
                        .values(dle_user_id=user_id_val, user_name=user_name_val)
                    )
                    r = await session.execute(stmt)
                    await session.commit()
                    linked = r.rowcount
                    logger.info(f"🔗 Привязка анонимных сообщений по platform_user_id={platform_user_id}: {linked} строк")

                    # 2) Если ничего не привязалось — пробуем по имени анонима
                    if linked == 0 and anon_name:
                        from sqlalchemy import func
                        stmt2 = (
                            update(AdminMessage)
                            .where(func.lower(AdminMessage.user_name) == func.lower(anon_name))
                            .where(AdminMessage.dle_user_id.is_(None))
                            .values(dle_user_id=user_id_val, user_name=user_name_val)
                        )
                        r2 = await session.execute(stmt2)
                        await session.commit()
                        linked2 = r2.rowcount
                        logger.info(f"🔗 Привязка анонимных сообщений по anon_name={anon_name}: {linked2} строк")
            except Exception as e:
                import logging
                logger = logging.getLogger("uvicorn")
                logger.warning(f"⚠️ Ошибка при привязке анонимных сообщений: {e}")

        return AuthResponse(
            success=True,
            message="Авторизация успешна!",
            dle_user_id=user_id_val,
            dle_username=user_name_val,
            dle_group=user_data.get("user_group"),
            dle_group_name=user_data.get("group_name", "Пользователь"),
        )

    return AuthResponse(
        success=False,
        message="Неверный логин или пароль. Попробуйте ещё раз.",
    )


async def handle_profile(platform: str, platform_user_id: str, dle_username: str) -> UserProfile:
    """
    Команда «Мой профиль».
    Показывает данные пользователя.
    """
    result = await dle_client.take_user_by_name(dle_username)
    data = result.get("data", {})

    from datetime import datetime

    # reg_date приходит как Unix timestamp -> переводим в дату
    reg_raw = data.get("reg_date")
    reg_date_formatted = ""
    if reg_raw:
        try:
            reg_ts = int(reg_raw)
            if reg_ts > 0:
                reg_date_formatted = datetime.fromtimestamp(reg_ts).strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            reg_date_formatted = str(reg_raw)

    return UserProfile(
        username=data.get("name", dle_username),
        user_id=data.get("user_id", 0),
        group_id=data.get("user_group", 0),
        group_name=data.get("group_name", "Гость"),
        email=data.get("email"),
        registration_date=reg_date_formatted,
    )


async def handle_search(
    platform: str, platform_user_id: str, query: str,
    page: int = 1, per_page: int = 5, smart: bool = False,
) -> SearchResult:
    """
    Команда «Поиск».
    Ищет новости по заголовку и тексту, выдаёт с пагинацией.

    page     — номер страницы (1, 2, 3...)
    per_page — сколько результатов на странице

    Возвращает SearchResult с текстом и данными пагинации.
    """
    import re
    offset = (page - 1) * per_page

    # Считаем общее количество и получаем данные (два запроса к DLE)
    total = await dle_client.search_news_count(query)
    news = await dle_client.search_news(query, limit=per_page, offset=offset)
    data = news.get("data", [])

    # Ничего не найдено
    if not data or total == 0:
        return SearchResult(
            text=f"🔍 По запросу «{query}» ничего не найдено.",
            has_more=False,
            current_page=page,
            total_pages=1,
            total_results=0,
            query=query,
        )

    # Если data — не список (один результат), оборачиваем в список
    if isinstance(data, dict):
        data = [data]

    # Границы показа
    first = offset + 1
    last = min(offset + len(data), total)
    separator = "\n─────────────────────\n"

    total_pages = (total + per_page - 1) // per_page

    # Заголовок
    lines = []
    lines.append(f"🔍━━━━━━━━━━━━━━━━━━")
    lines.append(f"⬥ ПОИСК: «{query}»")
    lines.append(f"━━━━━━━━━━━━━━━━━━🔍")
    lines.append(f"🏷 Найдено: {total} · стр. {page}/{total_pages}")
    lines.append("")

    for i, item in enumerate(data, start=first):
        news_id = item.get("id", "")
        title = item.get("title", "Без названия")
        alt_name = item.get("alt_name", "")
        short_story = item.get("short_story", "")
        full_story = item.get("full_story", "")
        date_raw = item.get("date", "")

        # Дата в читаемом формате
        date = _format_date(date_raw)

        # Превью: сначала краткий текст, если пусто — из полного
        raw_text = short_story if short_story else full_story
        clean_text = re.sub(r'<[^>]+>', '', raw_text)
        preview = clean_text[:100].strip()
        if len(clean_text) > 100:
            preview += "..."

        # Ссылка на полную новость
        link = f"https://www.turbinist.ru/{news_id}-{alt_name}.html"

        if i > first:
            lines.append("")

        lines.append(f"┌─ #{i} ──────────────────┐")
        lines.append(f"│ {title}")
        if preview:
            lines.append(f"│ 📝 {preview}")
        lines.append(f"│ 📅 {date}")
        lines.append(f"│ 🔗 {link}")
        lines.append("└────────────────────────┘")

    # Подсказка по пагинации
    has_more = last < total
    lines.append("")
    if has_more:
        lines.append(f"📄 Стр. {page} из {total_pages} | Всего: {total}")
    else:
        lines.append(f"📄 Стр. {page} из {total_pages} | Всего: {total} · Это всё")

    # Собираем структурированные данные для карточек на фронте
    items_data = []
    for item in data:
        news_id = item.get("id", "")
        title = item.get("title", "Без названия")
        alt_name = item.get("alt_name", "")
        short_story = item.get("short_story", "")
        full_story = item.get("full_story", "")
        date_raw = item.get("date", "")
        raw_text = short_story if short_story else full_story
        clean_text = re.sub(r'<[^>]+>', '', raw_text)
        preview = clean_text[:150].strip()
        if len(clean_text) > 150:
            preview += "..."
        items_data.append({
            "id": news_id,
            "title": title,
            "preview": preview,
            "link": f"https://www.turbinist.ru/{news_id}-{alt_name}.html",
            "date": _format_date(date_raw),
        })

    return SearchResult(
        text="\n".join(lines),
        has_more=has_more,
        current_page=page,
        total_pages=total_pages,
        total_results=total,
        query=query,
        items=items_data,
    )


def _format_date(date_str: str) -> str:
    """Превращает '2008-10-18 06:22:25' в '18.10.2008'"""
    if not date_str:
        return "—"
    # Берём только часть до пробела (если время тоже есть)
    parts = date_str.split(" ")[0].split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str


async def handle_clear_chat(platform: str, platform_user_id: str) -> str:
    """Команда «Очистить чат»."""
    return "История чата очищена. Начнём заново! 🧹"


async def handle_settings(platform: str, platform_user_id: str) -> str:
    """
    Команда «Настройки».
    Показывает доступные настройки бота.
    """
    return (
        "⚙️ Настройки бота:\n\n"
        "1. Уведомления: вкл/выкл\n"
        "2. Язык поиска: русский\n"
        "3. AI-режим: обычный\n\n"
        "Выберите пункт для изменения:"
    )


async def handle_stats(platform: str, platform_user_id: str) -> str:
    """
    Команда «Статистика».
    Показывает статистику пользователя в боте.
    """
    return (
        "📊 Ваша статистика:\n\n"
        "🔍 Поисков: 0\n"
        "🤖 AI-вопросов: 0\n"
        "📥 Загрузок: 0\n"
        "📰 Предложено новостей: 0\n\n"
        "Статистика обновляется раз в час."
    )


async def handle_channels(platform: str, platform_user_id: str) -> str:
    """
    Команда «Наши каналы».
    Показывает ссылки на все соцсети.
    """
    return (
        "Наши каналы:\n\n"
        "📱 Telegram: t.me/turbinist_club\n"
        "🐻 VK: vk.com/turbinist_club\n"
        "🔷 MAX: (скоро)\n"
        "📺 YouTube: (скоро)\n"
        "🎯 Дзен: (скоро)\n"
        "📷 Instagram: (скоро)\n"
        "🎬 Rutub: (скоро)"
    )


# ============================================================
#  СООБЩЕНИЕ АДМИНУ
# ============================================================

async def handle_admin_message(
    platform: str, platform_user_id: str,
    user_name: str, text: str,
    dle_user_id: int = None,
) -> dict:
    """
    Пользователь написал сообщение админу.
    Сохраняет в таблицу admin_messages как sender_type="user".
    Возвращает словарь с id сообщения.
    """
    clean_text = text.strip()

    async with async_session() as session:
        msg = AdminMessage(
            platform=platform,
            platform_user_id=platform_user_id,
            dle_user_id=dle_user_id,
            user_name=user_name,
            sender_type="user",
            topic="question",
            text=clean_text,
            status="new",
        )
        session.add(msg)
        await session.commit()
        msg_id = msg.id

    return {
        "status": "ok",
        "message": "✅ Сообщение отправлено!",
        "id": msg_id,
    }


async def handle_get_chat(dle_user_id: int = 0, platform_user_id: str = "") -> dict:
    """
    Возвращает всю переписку юзера или анонима с админом.
    """
    if not dle_user_id and not platform_user_id:
        return {"error": "Нужен dle_user_id или platform_user_id", "messages": []}

    async with async_session() as session:
        from sqlalchemy import select, update

        stmt = select(AdminMessage)
        if platform_user_id:
            stmt = stmt.where(AdminMessage.platform_user_id == platform_user_id)
        else:
            stmt = stmt.where(AdminMessage.dle_user_id == dle_user_id)
        stmt = stmt.order_by(AdminMessage.created_at.asc()).limit(100)
        rows = (await session.execute(stmt)).scalars().all()

    messages = []
    for r in rows:
        messages.append({
            "id": r.id,
            "sender_type": r.sender_type,
            "text": r.text,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "time_ago": _time_ago(r.created_at),
        })

    return {"messages": messages, "total": len(messages)}


async def handle_mark_chat_read(dle_user_id: int) -> dict:
    """
    Помечает все непрочитанные сообщения юзера как "answered".
    Вызывается, когда юзер открывает чат в веб-виджете.
    """
    if not dle_user_id:
        return {"error": "Нужен dle_user_id"}

    async with async_session() as session:
        from sqlalchemy import update

        stmt = (
            update(AdminMessage)
            .where(AdminMessage.dle_user_id == dle_user_id)
            .where(AdminMessage.status == "new")
            .values(status="answered", answered_at=datetime.utcnow())
        )
        await session.execute(stmt)
        await session.commit()

    return {"status": "ok"}


async def handle_delete_chat(dle_user_id: int = 0, platform_user_id: str = "") -> dict:
    """
    Удаляет все сообщения пользователя или анонима из чата с админом.
    """
    if not dle_user_id and not platform_user_id:
        return {"error": "Нужен dle_user_id или platform_user_id"}

    async with async_session() as session:
        from sqlalchemy import delete, select
        from app.models.database import BotUser

        # Удаляем все сообщения — по platform_user_id или dle_user_id
        if platform_user_id:
            stmt = delete(AdminMessage).where(AdminMessage.platform_user_id == platform_user_id)
            await session.execute(stmt)
        else:
            stmt = delete(AdminMessage).where(AdminMessage.dle_user_id == dle_user_id)
            await session.execute(stmt)

            # Удаляем анонимные сообщения от тех же платформ (dle_user_id=None)
            stmt_bu = select(BotUser).where(BotUser.dle_user_id == dle_user_id)
            bot_users = (await session.execute(stmt_bu)).scalars().all()
            for bu in bot_users:
                stmt_anon = delete(AdminMessage).where(
                    AdminMessage.dle_user_id == None,
                    AdminMessage.platform == bu.platform,
                    AdminMessage.platform_user_id == bu.platform_user_id
                )
                await session.execute(stmt_anon)

        await session.commit()

    return {"status": "ok"}


async def handle_archive_chat(dle_user_id: int, archived: bool = True) -> dict:
    """
    Архивировать (archived=True) или разархивировать (archived=False) чат пользователя.
    Обновляет is_archived у ВСЕХ записей BotUser для данного dle_user_id (все платформы).
    Если записей нет — создаёт одну с platform="web".
    """
    if not dle_user_id:
        return {"error": "Нужен dle_user_id"}

    async with async_session() as session:
        from sqlalchemy import select, update

        # Ищем ВСЕ записи BotUser для этого dle_user_id
        stmt = select(BotUser).where(BotUser.dle_user_id == dle_user_id)
        bot_users = (await session.execute(stmt)).scalars().all()

        if bot_users:
            # Обновляем is_archived у ВСЕХ найденных записей
            for bu in bot_users:
                bu.is_archived = archived
        else:
            # Если нет записи — создаём одну
            bot_user = BotUser(
                platform="web",
                platform_user_id=str(dle_user_id),
                dle_user_id=dle_user_id,
                is_archived=archived,
            )
            session.add(bot_user)
        await session.commit()

    action = "архивирован" if archived else "разархивирован"
    return {"status": "ok", "message": f"Чат пользователя {dle_user_id} {action}"}


async def handle_get_archived_chats() -> dict:
    """
    Возвращает список архивных чатов (уникальные dle_user_id).
    Ищет dle_user_id с BotUser.is_archived == True,
    для каждого показывает последнее сообщение из AdminMessage.
    """
    async with async_session() as session:
        from sqlalchemy import select, func, desc

        # Берём уникальные dle_user_id у которых хотя бы одна запись архивная
        bu_stmt = (
            select(BotUser.dle_user_id)
            .where(BotUser.is_archived == True)
            .where(BotUser.dle_user_id.isnot(None))
            .distinct()
        )
        archived_ids = (await session.execute(bu_stmt)).scalars().all()

    chats = []
    for dle_user_id in archived_ids:
        if not dle_user_id:
            continue
        # Последнее сообщение для этого пользователя
        async with async_session() as session:
            last_stmt = (
                select(AdminMessage)
                .where(AdminMessage.dle_user_id == dle_user_id)
                .order_by(AdminMessage.created_at.desc())
                .limit(1)
            )
            last_msg = (await session.execute(last_stmt)).scalar_one_or_none()

        # Берём username из любой архивной записи BotUser (первая попавшаяся)
        async with async_session() as session:
            bu_stmt = (
                select(BotUser.dle_username)
                .where(BotUser.dle_user_id == dle_user_id)
                .where(BotUser.dle_username.isnot(None))
                .limit(1)
            )
            dle_username = (await session.execute(bu_stmt)).scalar_one_or_none()

        user_name = dle_username or (last_msg.user_name if last_msg else f"Юзер #{dle_user_id}")

        chats.append({
            "dle_user_id": dle_user_id,
            "user_name": user_name,
            "last_message_at": last_msg.created_at.isoformat() if last_msg else None,
        })

    return {"chats": chats}


async def handle_user_search(query: str, exclude_dle_user_id: int = None) -> list:
    """
    Ищет пользователей по имени (dle_username) в BotUser.
    Возвращает список: {dle_user_id, username, platforms: [str]}
    """
    if not query or len(query.strip()) < 2:
        return []

    async with async_session() as session:
        from sqlalchemy import select

        stmt = (
            select(BotUser)
            .where(BotUser.dle_username.ilike(f"%{query.strip()}%"))
            .where(BotUser.dle_user_id.isnot(None))
        )
        if exclude_dle_user_id:
            stmt = stmt.where(BotUser.dle_user_id != exclude_dle_user_id)

        result = await session.execute(stmt)
        rows = result.scalars().all()

    # Группируем по dle_user_id — один юзер может быть на нескольких платформах
    seen = {}
    for row in rows:
        uid = row.dle_user_id
        if uid not in seen:
            seen[uid] = {
                "dle_user_id": uid,
                "username": row.dle_username or f"user_{uid}",
                "platforms": [],
            }
        seen[uid]["platforms"].append(row.platform)

    return list(seen.values())


async def handle_admin_chat_reply(admin_dle_id: int, user_dle_id: int, text: str) -> dict:
    """
    Админ отвечает юзеру — создаёт новое сообщение sender_type="admin".
    """
    if admin_dle_id != settings.ADMIN_USER_ID:
        return {"error": "Только админ может отвечать."}

    clean_text = text.strip()
    if not clean_text:
        return {"error": "Текст ответа не может быть пустым."}

    async with async_session() as session:
        from sqlalchemy import select, update

        msg = AdminMessage(
            platform="web",
            platform_user_id=str(user_dle_id),
            dle_user_id=user_dle_id,
            user_name="Админ",
            sender_type="admin",
            topic="question",
            text=clean_text,
            status="new",
        )
        session.add(msg)
        await session.commit()
        msg_id = msg.id

    return {
        "status": "ok",
        "message": "✅ Ответ отправлен.",
        "id": msg_id,
    }


async def handle_get_chat_list(admin_dle_id: int) -> dict:
    """
    Для админа: список юзеров, у которых есть переписка.
    Группирует по dle_user_id, показывает последнее сообщение.
    Фильтрует по BotUser.is_archived — показывает только неархивные чаты.
    """
    if admin_dle_id != settings.ADMIN_USER_ID:
        return {"error": "Только админ."}

    async with async_session() as session:
        from sqlalchemy import select, func, case, join

        # Получаем уникальные dle_user_id у которых есть сообщения и чат не в архиве
        # Используем LEFT JOIN с BotUser для проверки is_archived
        stmt = (
            select(
                AdminMessage.dle_user_id,
                func.max(
                    case(
                        (AdminMessage.sender_type == "user", AdminMessage.user_name),
                        else_=None,
                    )
                ).label("user_name"),
                func.max(AdminMessage.created_at).label("last_at"),
                func.count().label("total"),
            )
            .where(AdminMessage.dle_user_id.isnot(None))
            .group_by(AdminMessage.dle_user_id)
            .order_by(func.max(AdminMessage.created_at).desc())
            .limit(50)
        )
        rows = (await session.execute(stmt)).all()

    chats = []
    for r in rows:
        # Проверяем не в архиве ли чат (если хотя бы одна запись архивная — считаем чат архивным)
        async with async_session() as session:
            bu_stmt = (
                select(BotUser.dle_user_id)
                .where(BotUser.dle_user_id == r.dle_user_id)
                .where(BotUser.is_archived == True)
                .limit(1)
            )
            archived_bot_user = (await session.execute(bu_stmt)).scalar_one_or_none()
        if archived_bot_user is not None:
            # Если чат в архиве — пропускаем
            continue

        # Определяем есть ли непрочитанные от юзера
        new_count_stmt = (
            select(func.count())
            .select_from(AdminMessage)
            .where(
                AdminMessage.dle_user_id == r.dle_user_id,
                AdminMessage.sender_type == "user",
                AdminMessage.status == "new",
            )
        )
        new_count = (await session.execute(new_count_stmt)).scalar() or 0

        chats.append({
            "dle_user_id": r.dle_user_id,
            "user_name": r.user_name or f"Юзер #{r.dle_user_id}",
            "last_at": r.last_at.isoformat(),
            "time_ago": _time_ago(r.last_at),
            "total_messages": r.total,
            "has_new": new_count > 0,
            "new_count": new_count,
        })


    # === Анонимные чаты (dle_user_id IS NULL) ===
    async with async_session() as session:
        anon_stmt = (
            select(
                AdminMessage.platform_user_id,
                func.max(
                    case(
                        (AdminMessage.sender_type == "user", AdminMessage.user_name),
                        else_=None,
                    )
                ).label("user_name"),
                func.max(AdminMessage.created_at).label("last_at"),
                func.count().label("total"),
            )
            .where(AdminMessage.dle_user_id.is_(None))
            .where(AdminMessage.platform_user_id.isnot(None))
            .group_by(AdminMessage.platform_user_id)
            .order_by(func.max(AdminMessage.created_at).desc())
            .limit(20)
        )
        anon_rows = (await session.execute(anon_stmt)).all()

    for r in anon_rows:
        if not r.platform_user_id:
            continue
        # Считаем непрочитанные от юзера
        new_count_stmt = (
            select(func.count())
            .select_from(AdminMessage)
            .where(
                AdminMessage.platform_user_id == r.platform_user_id,
                AdminMessage.dle_user_id.is_(None),
                AdminMessage.sender_type == "user",
                AdminMessage.status == "new",
            )
        )
        new_count = (await session.execute(new_count_stmt)).scalar() or 0

        chats.append({
            "dle_user_id": 0,
            "platform_user_id": r.platform_user_id,
            "user_name": (r.user_name or "Гость") + " (аноним)",
            "last_at": r.last_at.isoformat(),
            "time_ago": _time_ago(r.last_at),
            "total_messages": r.total,
            "has_new": new_count > 0,
            "new_count": new_count,
            "is_anonymous": True,
        })

    return {"chats": chats, "total": len(chats)}


# ============================================================
#  РЕКЛАМА
# ============================================================

# Таблица цен (из create_universal_chat_bot.txt)
AD_PRICES = {
    "site":   ("Сайт", 500),
    "tg":     ("Telegram", 500),
    "vk":     ("VK", 500),
    "max":    ("MAX", 500),
    "all":    ("Все площадки", 1500),
    "pin_single":  ("Закрепление (1 день)", 550),
}

async def handle_ad_prices() -> str:
    """Показать таблицу цен на рекламу (цены из БД)."""
    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.database import AdPrice

    async with async_session() as session:
        result = await session.execute(select(AdPrice).order_by(AdPrice.id))
        rows = result.scalars().all()
        prices = {row.price_key: {"base_price": row.base_price, "surcharge_pct": row.surcharge_pct} for row in rows}

    site = int(prices.get("feed_site", {}).get("base_price", 0))
    pin = int(prices.get("feed_pin_single", {}).get("base_price", 0))

    # Баннеры
    banner_all = int(prices.get("banner_all_pages", {}).get("base_price", 0))
    banner_all_nr = prices.get("banner_all_pages", {}).get("surcharge_pct", 0)  # float!
    banner_news = int(prices.get("banner_in_news", {}).get("base_price", 0))
    banner_news_nr = prices.get("banner_in_news", {}).get("surcharge_pct", 0)  # float!
    # Статьи
    article_base = int(prices.get("article_base", {}).get("base_price", 0))
    article_base_nr = prices.get("article_base", {}).get("surcharge_pct", 0)  # float!
    article_eternal = int(prices.get("article_eternal", {}).get("base_price", 0))
    article_eternal_nr = prices.get("article_eternal", {}).get("surcharge_pct", 0)  # float!
    article_fix = int(prices.get("article_fixation", {}).get("base_price", 0))

    # Формируем проценты для отображения
    banner_all_nr_pct = int(banner_all_nr * 100)
    banner_news_nr_pct = int(banner_news_nr * 100)
    article_base_nr_pct = int(article_base_nr * 100)
    article_eternal_nr_pct = int(article_eternal_nr * 100)

    lines = [
        "💰━━━━━━━━━━━━━━━━━━━━━",
        "⬥ РЕКЛАМА НА НАШИХ ПЛОЩАДКАХ",
        "━━━━━━━━━━━━━━━━━━━━━💰",
        "",
        "📢 Объявление в ленте:",
        f"  • 1 площадка — {site} ₽/день",
        f"  • Все 4 площадки — {site * 4} ₽/день",
        f"  • Закрепление — {pin} ₽/день за площадку",
        "",
        "🖼 Баннеры:",
        f"  • Сквозной — {banner_all} ₽/мес (нерелев. +{banner_all_nr_pct}%)",
        f"  • В новостях — {banner_news} ₽/мес (нерелев. +{banner_news_nr_pct}%)",
        "",
        "📰 Статьи:",
        f"  • Обычная — {article_base} ₽ (нерелев. +{article_base_nr_pct}%)",
        f"  • Вечная — {article_eternal} ₽ (нерелев. +{article_eternal_nr_pct}%)",
        f"  • Фиксация вверху — {article_fix} ₽/день",
        "",
        "Для заказа нажмите «Реклама» и следуйте инструкциям.",
    ]
    return "\n".join(lines)


async def handle_ad_submit(
    platform: str, platform_user_id: str,
    text: str, platforms: str, days: int,
    pin: bool, total_price: float,
    dle_user_id: int = None,
    user_name: str = None,
    ad_type: str = "feed",
    image_path: str = None,
    pin_days: int = 0,
    pin_platforms: str = None,  # площадки закрепления: "tg,vk" / null=все
    article_eternal: bool = False,
    article_opts: str = None,
    article_fix_days: int = 0,
    article_months: int = 1,
    banner_size: str = "728x90",
    banner_placement: str = "in_news",
    banner_months: int = 1,
    banner_opts: str = None,
) -> str:
    """
    Сохраняет заявку на рекламу в БД.
    ad_type: "feed" (объявление в ленте) или "banner" (баннер/статья)
    """
    async with async_session() as session:
        ad = AdRequest(
            platform=platform,
            platform_user_id=platform_user_id,
            dle_user_id=dle_user_id,
            user_name=user_name,
            text=text,
            ad_type=ad_type,
            image_path=image_path,
            days=days,
            pin=pin,
            pin_days=pin_days,
            pin_platforms=pin_platforms,
            article_eternal=article_eternal,
            article_opts=article_opts,
            article_fix_days=article_fix_days,
            article_months=article_months,
            banner_size=banner_size,
            banner_placement=banner_placement,
            banner_months=banner_months,
            banner_opts=banner_opts,
            platform_target=platforms,
            total_price=total_price,
            status="new",
        )
        session.add(ad)
        await session.commit()

    if ad_type == "article":
        type_label = "Статья"
        if article_eternal:
            type_label = "Статья (вечная)"
    elif ad_type == "banner":
        type_label = "Баннер"
    else:
        type_label = "Объявление в ленте"
    return (
        f"✅ Заявка на рекламу принята!\n\n"
        f"Тип: {type_label}\n"
        f"Площадки: {platforms}\n"
        f"Дней: {days}\n"
        f"Закрепление: {'да' if pin else 'нет'}\n"
        f"Сумма: {total_price} ₽\n\n"
        "Администратор свяжется с вами в ближайшее время."
    )


# ============================================================
#  ПРЕДЛОЖИТЬ НОВОСТЬ
# ============================================================

async def handle_news_suggest(
    platform: str, platform_user_id: str,
    title: str, text: str,
    dle_user_id: int = None,
    user_name: str = None,
    image_path: str = None,
) -> str:
    """
    Пользователь предлагает новость.
    Сохраняет в таблицу news_suggestions.
    """
    async with async_session() as session:
        news = NewsSuggestion(
            platform=platform,
            platform_user_id=platform_user_id,
            dle_user_id=dle_user_id,
            user_name=user_name,
            title=title,
            text=text,
            image_path=image_path,
            status="new",
        )
        session.add(news)
        await session.commit()

    return (
        "✅ Новость отправлена на рассмотрение!\n\n"
        f"Заголовок: {title}\n\n"
        "Администратор проверит её и, возможно, опубликует на сайте."
    )


# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ АДМИН-ПАНЕЛИ
# ============================================================

def _calc_ad_breakdown(platform_target: str, days: int, pin: bool, total_price: float, ad_type: str = "feed", pin_days: int = 0, article_eternal: bool = False, prices: dict = None, article_opts: str = None, article_fix_days: int = 0, article_months: int = 1, banner_size: str = "728x90", banner_placement: str = "in_news", banner_months: int = 1, banner_opts: str = None, pin_platforms: str = None) -> list:
    """Разбивка цены рекламы — список строк для показа админу."""
    lines = []

    if ad_type == "banner":
        lines.append(f"  Тип: Баннер")
        lines.append(f"  Размер: {banner_size}")
        placement_labels = {"all_pages": "Сквозное (все страницы)", "in_news": "В новостях"}
        lines.append(f"  Размещение: {placement_labels.get(banner_placement, banner_placement)}")
        lines.append(f"  Период: {banner_months} мес.")
        banner_base_price = prices.get("banner_" + banner_placement, {}).get("base_price", 0) if prices else 0
        if banner_base_price:
            lines.append(f"  База: {banner_base_price}₽/мес")
        if banner_opts:
            opt_labels = {"home": "🏠 Главная", "not_relevant": "📌 Нерелевантная", "custom": "✏️ Пожелания"}
            for opt in banner_opts.split(","):
                opt = opt.strip()
                if opt in opt_labels:
                    opt_extra = round(banner_base_price * 0.3 * banner_months)
                    lines.append(f"  {opt_labels[opt]}: {banner_base_price}₽/мес × 30% × {banner_months} мес. = +{opt_extra}₽")
        lines.append(f"  ─────────────────")
        lines.append(f"  ИТОГО: {total_price}₽")
        return lines

    if ad_type == "article":
        if article_eternal:
            article_base_price = prices.get("article_eternal", {}).get("base_price", 0) if prices else 0
            article_nr_pct = prices.get("article_eternal", {}).get("surcharge_pct", 0) if prices else 0
            lines.append(f"  Тип: Статья (ВЕЧНАЯ)")
            lines.append(f"  База: {article_base_price}₽")
            calc_total = article_base_price
            if article_opts and "not_relevant" in article_opts:
                nr_extra = round(article_base_price * article_nr_pct)
                calc_total = round(article_base_price * (1 + article_nr_pct))
                lines.append(f"  Нерелевантная: {article_base_price}₽ × ×{1 + article_nr_pct:.1f} = +{nr_extra}₽")
        else:
            article_base_price = prices.get("article_base", {}).get("base_price", 0) if prices else 0
            article_nr_pct = prices.get("article_base", {}).get("surcharge_pct", 0) if prices else 0
            lines.append(f"  Тип: Статья")
            lines.append(f"  База: {article_base_price}₽/мес × {article_months} мес. = {article_base_price * article_months}₽")
            calc_total = article_base_price * article_months
            if article_opts:
                for opt in article_opts.split(","):
                    opt = opt.strip()
                    if opt == "not_relevant":
                        nr_extra = round(article_base_price * article_nr_pct * article_months)
                        calc_total = round(article_base_price * (1 + article_nr_pct) * article_months)
                        lines.append(f"  Нерелевантная: {article_base_price}₽/мес × ×{1 + article_nr_pct:.1f} × {article_months} мес. = +{nr_extra}₽")
                    elif opt == "exchange":
                        lines.append(f"  Обмен ссылками: бесплатно")
                    elif opt == "fixation" and article_fix_days > 0:
                        fix_price = prices.get("article_fixation", {}).get("base_price", 0) if prices else 0
                        fix_total = fix_price * article_fix_days * article_months
                        calc_total += fix_total
                        lines.append(f"  Фиксация: {fix_price}₽/день × {article_fix_days} дн. × {article_months} мес. = +{fix_total}₽")
        lines.append(f"  ─────────────────")
        lines.append(f"  ИТОГО: {calc_total}₽")
        return lines

    # Для объявления в ленте — полная разбивка
    platform_names = {"site": "Сайт", "tg": "Telegram", "vk": "VK", "max": "MAX"}
    feed_site = prices.get("feed_site", {}).get("base_price", 0) if prices else 0
    pin_per_day = prices.get("feed_pin_single", {}).get("base_price", 0) if prices else 0

    # Разбираем платформы (может быть "all", "vk,tg", "site" и т.д.)
    if platform_target == "all":
        selected_platforms = list(platform_names.keys())
    else:
        selected_platforms = [p.strip() for p in platform_target.split(",") if p.strip() in platform_names]

    base = 0
    for key in selected_platforms:
        name = platform_names.get(key, key.upper())
        item_total = feed_site * days
        base += item_total
        lines.append(f"  {name}: {feed_site}₽ × {days} дн. = {item_total}₽")

    if pin and pin_days > 0:
        if pin_platforms:
            pin_plat_list = [p.strip() for p in pin_platforms.split(",") if p.strip() in platform_names]
        else:
            pin_plat_list = selected_platforms
        pin_plat_count = len(pin_plat_list)
        pin_total = pin_per_day * pin_plat_count * pin_days
        pin_plat_names = ", ".join(platform_names.get(p, p.upper()) for p in pin_plat_list)
        lines.append(f"  Закрепление: {pin_per_day}₽/день × {pin_plat_count} площ. ({pin_plat_names}) × {pin_days} дн. = +{pin_total}₽")

    lines.append(f"  ─────────────────")
    lines.append(f"  ИТОГО: {total_price}₽")

    return lines


# ============================================================
#  РЕДАКТОР ЦЕН
# ============================================================

async def get_prices() -> dict:
    """Возвращает все цены из БД (для калькуляторов)."""
    from app.models.database import AdPrice
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(select(AdPrice).order_by(AdPrice.id))
        rows = result.scalars().all()
        prices = {}
        for row in rows:
            prices[row.price_key] = {
                "id": row.id,
                "price_key": row.price_key,
                "price_name": row.price_name,
                "base_price": row.base_price,
                "surcharge_pct": row.surcharge_pct,
            }
        return {"status": "ok", "prices": prices}


async def update_prices(dle_user_id: int, updates: dict) -> dict:
    """
    Админ обновляет цены.
    updates: {"feed_site": {"base_price": 600, "surcharge_pct": 0}, ...}
    """
    from app.models.database import AdPrice
    from sqlalchemy import select

    if dle_user_id != settings.ADMIN_USER_ID:
        return {"status": "error", "message": "Только админ может менять цены"}

    async with async_session() as session:
        for price_key, data in updates.items():
            result = await session.execute(
                select(AdPrice).where(AdPrice.price_key == price_key)
            )
            row = result.scalar_one_or_none()
            if row:
                if "base_price" in data:
                    row.base_price = data["base_price"]
                if "surcharge_pct" in data:
                    row.surcharge_pct = data["surcharge_pct"]
                from datetime import datetime
                row.updated_at = datetime.utcnow()
        await session.commit()

    return {"status": "ok", "message": "Цены обновлены"}


def _status_ru(status: str) -> str:
    """Перевод статуса на русский."""
    labels = {"new": "Новая", "in_progress": "На рассмотрении", "approved": "Выполнена", "rejected": "Отклонена", "done": "Выполнена", "paid": "Оплачена"}
    return labels.get(status, status)


def _time_ago(dt: datetime) -> str:
    """Человеческий формат «только что», «2 ч. назад» и т.д."""
    now = datetime.utcnow()
    diff = now - dt
    if diff.days > 365:
        return f"{diff.days // 365} г. назад"
    if diff.days > 30:
        return f"{diff.days // 30} мес. назад"
    if diff.days > 7:
        return f"{diff.days // 7} нед. назад"
    if diff.days > 0:
        return f"{diff.days} дн. назад"
    if diff.seconds > 3600:
        return f"{diff.seconds // 3600} ч. назад"
    if diff.seconds > 60:
        return f"{diff.seconds // 60} мин. назад"
    return "только что"


def _platform_icon(platform: str) -> str:
    """Иконка для платформы."""
    icons = {"vk": "🐻", "telegram": "📱", "tg": "📱", "web": "🌐", "max": "🔷"}
    return icons.get(platform, "💬")


def _type_icon(item_type: str) -> str:
    """Иконка для типа заявки."""
    icons = {"ad": "📢", "news": "📰", "message": "💬"}
    return icons.get(item_type, "📩")


# ============================================================
#  АДМИН-ПАНЕЛЬ — НОВАЯ ЛОГИКА (разделы + архив)
# ============================================================

def _is_admin(dle_user_id: int) -> bool:
    """Проверка: является ли пользователь админом."""
    return dle_user_id == settings.ADMIN_USER_ID


async def handle_admin_panel(platform: str, platform_user_id: str, dle_user_id: int) -> str:
    """
    Админ-панель: старая версия (текстовая).
    Оставлена для обратной совместимости.
    """
    if not _is_admin(dle_user_id):
        return "⛔ Эта функция доступна только администратору."

    counts = await _get_admin_counts()

    return (
        "📩 АДМИН-ПАНЕЛЬ\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"📢 Реклама: {counts['new_ads']}   📰 Новости: {counts['new_news']}   💬 Сообщения: {counts['new_messages']}\n"
        f"📦 Архив: {counts['archive_ads'] + counts['archive_news']}\n"
        "━━━━━━━━━━━━━━━━━"
    )


async def _get_admin_counts() -> dict:
    """Подсчёт заявок по категориям."""
    from sqlalchemy import select, func

    async with async_session() as session:
        def cnt(table, *filters):
            stmt = select(func.count()).select_from(table)
            for f in filters:
                stmt = stmt.where(f)
            return session.execute(stmt)

        new_ads = (await cnt(AdRequest, AdRequest.status.in_(["new", "in_progress"]))).scalar() or 0
        new_news = (await cnt(NewsSuggestion, NewsSuggestion.status.in_(["new", "in_progress"]))).scalar() or 0
        new_messages = (await cnt(AdminMessage, AdminMessage.sender_type == "user", AdminMessage.status == "new", AdminMessage.dle_user_id != None)).scalar() or 0

        archive_ads = (await cnt(AdRequest, AdRequest.status.in_(["approved", "rejected", "done"]))).scalar() or 0
        archive_news = (await cnt(NewsSuggestion, NewsSuggestion.status.in_(["approved", "rejected"]))).scalar() or 0

    return {
        "new_ads": new_ads,
        "new_news": new_news,
        "new_messages": new_messages,
        "archive_ads": archive_ads,
        "archive_news": archive_news,
    }


async def handle_admin_welcome(dle_user_id: int) -> dict:
    """
    Приветствие при входе админа — возвращает счётчики.
    """
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    counts = await _get_admin_counts()
    return counts


async def handle_admin_stats(dle_user_id: int) -> dict:
    """
    Статистика для админа: доходы, принятые/отклонённые, разбивка по типам.
    """
    from app.models.database import AdRequest
    from sqlalchemy import select, func

    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        # Все заявки
        all_ads = (await session.execute(select(AdRequest))).scalars().all()

        total_income = 0
        approved = 0
        rejected = 0
        total_requests = len(all_ads)

        approved_feed = 0
        approved_banner = 0
        approved_article = 0
        rejected_feed = 0
        total_feed = 0
        total_banner = 0
        total_article = 0

        for ad in all_ads:
            price = ad.corrected_price if ad.corrected_price else ad.total_price
            ad_type = ad.ad_type or "feed"

            # Считаем по типам
            if ad_type == "feed":
                total_feed += 1
            elif ad_type == "banner":
                total_banner += 1
            elif ad_type == "article":
                total_article += 1

            # Считаем по статусам
            if ad.status in ("approved", "done"):
                approved += 1
                total_income += (price or 0)
                if ad_type == "feed":
                    approved_feed += 1
                elif ad_type == "banner":
                    approved_banner += 1
                elif ad_type == "article":
                    approved_article += 1
            elif ad.status == "rejected":
                rejected += 1
                if ad_type == "feed":
                    rejected_feed += 1

        avg_check = round(total_income / approved) if approved > 0 else 0

    return {
        "total_income": total_income,
        "avg_check": avg_check,
        "total_requests": total_requests,
        "approved": approved,
        "rejected": rejected,
        "approved_feed": approved_feed,
        "approved_banner": approved_banner,
        "approved_article": approved_article,
        "rejected_feed": rejected_feed,
        "total_feed": total_feed,
        "total_banner": total_banner,
        "total_article": total_article,
    }


async def handle_bot_users_stats(dle_user_id: int) -> dict:
    """
    Статистика пользователей бота по платформам.
    Для админа: сколько юзеров на веб, TG, VK, MAXX (заглушка) и всего.
    """
    from sqlalchemy import select, func

    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        result = await session.execute(
            select(BotUser.platform, func.count(BotUser.id))
            .group_by(BotUser.platform)
        )
        platform_counts = dict(result.all())
        total = sum(platform_counts.values())

    return {
        "web": platform_counts.get("web", 0),
        "telegram": platform_counts.get("telegram", 0),
        "vk": platform_counts.get("vk", 0),
        "maxx": 0,  # заглушка — пока нет интеграции с MAXX
        "total": total,
    }


async def handle_admin_panel_data(
    dle_user_id: int, section: str = "ads", page: int = 1, limit: int = 10,
) -> dict:
    """
    Админ-панель: возвращает структурированные данные (JSON).
    section: "ads", "news", "archive"
    Сообщения — в отдельном разделе через handle_get_chat_list.
    """
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    counts = await _get_admin_counts()
    items = []
    has_more = False
    offset = (page - 1) * limit

    # Загружаем цены из БД для разбивки
    db_prices = {}
    try:
        prices_result = await get_prices()
        db_prices = prices_result.get("prices", {})
    except Exception:
        pass  # fallback — хардкод внутри _calc_ad_breakdown

    async with async_session() as session:
        from sqlalchemy import select

        def build_ad_item(ad) -> dict:
            return {
                "id": ad.id,
                "type": "ad",
                "user_name": ad.user_name or ad.platform,
                "dle_user_id": ad.dle_user_id,
                "platform": ad.platform,
                "text": ad.text,
                "preview": ad.text[:80] + ("..." if len(ad.text) > 80 else ""),
                "ad_type": ad.ad_type or "feed",  # "feed" или "banner"
                "image_path": ad.image_path,
                "status": _status_ru(ad.status),
                "created_at": ad.created_at.isoformat(),
                "time_ago": _time_ago(ad.created_at),
                "days": ad.days,
                "pin": ad.pin,
                "pin_days": ad.pin_days or 0,
                "pin_platforms": ad.pin_platforms,
                "platform_target": ad.platform_target,
                "total_price": ad.total_price,
                "corrected_price": ad.corrected_price,
                "article_eternal": ad.article_eternal,
                "article_opts": ad.article_opts,
                "article_fix_days": ad.article_fix_days or 0,
                "article_months": ad.article_months or 1,
                "banner_size": ad.banner_size or "728x90",
                "banner_placement": ad.banner_placement or "in_news",
                "banner_months": ad.banner_months or 1,
                "banner_opts": ad.banner_opts,
                "breakdown": _calc_ad_breakdown(ad.platform_target, ad.days, ad.pin, ad.total_price, ad.ad_type or "feed", ad.pin_days or 0, ad.article_eternal, db_prices, ad.article_opts, ad.article_fix_days or 0, ad.article_months or 1, ad.banner_size or "728x90", ad.banner_placement or "in_news", ad.banner_months or 1, ad.banner_opts, ad.pin_platforms),
                "admin_reply": ad.admin_reply,
                "answered_at": ad.answered_at.isoformat() if ad.answered_at else None,
                "answered_time_ago": _time_ago(ad.answered_at) if ad.answered_at else None,
            }

        def build_news_item(news) -> dict:
            return {
                "id": news.id,
                "type": "news",
                "user_name": news.user_name or news.platform,
                "dle_user_id": news.dle_user_id,
                "platform": news.platform,
                "text": f"{news.title}\n{news.text}",
                "preview": news.title[:80] + ("..." if len(news.title) > 80 else ""),
                "title": news.title,
                "image_path": news.image_path,
                "status": _status_ru(news.status),
                "created_at": news.created_at.isoformat(),
                "time_ago": _time_ago(news.created_at),
                "admin_reply": news.admin_reply,
                "answered_at": news.answered_at.isoformat() if news.answered_at else None,
                "answered_time_ago": _time_ago(news.answered_at) if news.answered_at else None,
            }

        # Собираем элементы в зависимости от секции
        ad_filter = None
        news_filter = None

        if section == "ads":
            ad_filter = AdRequest.status.in_(["new", "in_progress"])
        elif section == "news":
            news_filter = NewsSuggestion.status.in_(["new", "in_progress"])
        elif section == "archive":
            ad_filter = AdRequest.status.in_(["approved", "rejected", "done"])
            news_filter = NewsSuggestion.status.in_(["approved", "rejected"])

        # Запрашиваем из БД
        raw_items = []

        if ad_filter is not None:
            stmt = select(AdRequest).where(ad_filter).order_by(AdRequest.created_at.desc()).limit(limit).offset(offset)
            for ad in (await session.execute(stmt)).scalars().all():
                raw_items.append(build_ad_item(ad))

        if news_filter is not None:
            stmt = select(NewsSuggestion).where(news_filter).order_by(NewsSuggestion.created_at.desc()).limit(limit).offset(offset)
            for news in (await session.execute(stmt)).scalars().all():
                raw_items.append(build_news_item(news))

    # Сортируем все вместе по дате (новые сверху)
    raw_items.sort(key=lambda x: x["created_at"], reverse=True)

    # Берём только нужное количество
    items = raw_items[:limit]
    has_more = len(raw_items) > limit or len(raw_items) == limit

    return {
        "counts": counts,
        "section": section,
        "page": page,
        "has_more": has_more,
        "items": items,
    }


async def handle_admin_approve_ad(
    dle_user_id: int, ad_id: int, corrected_price: float = None,
) -> dict:
    """Админ подтверждает рекламу."""
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        from sqlalchemy import select, update

        stmt = select(AdRequest).where(AdRequest.id == ad_id)
        result = await session.execute(stmt)
        ad = result.scalar_one_or_none()

        if not ad:
            return {"error": f"❌ Заявка #{ad_id} не найдена."}

        values = {
            "status": "approved",
            "answered_at": datetime.utcnow(),
        }
        if corrected_price is not None:
            values["corrected_price"] = corrected_price

        await session.execute(
            update(AdRequest).where(AdRequest.id == ad_id).values(**values)
        )
        await session.commit()

    msg = f"✅ Реклама #{ad_id} подтверждена!"
    if corrected_price:
        msg += f" Скорректированная цена: {corrected_price}₽"
    msg += "\n\nПользователь получит уведомление."

    return {"status": "ok", "message": msg}


async def handle_admin_reject_ad(dle_user_id: int, ad_id: int) -> dict:
    """Админ отклоняет рекламу."""
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        from sqlalchemy import select, update

        stmt = select(AdRequest).where(AdRequest.id == ad_id)
        result = await session.execute(stmt)
        ad = result.scalar_one_or_none()

        if not ad:
            return {"error": f"❌ Заявка #{ad_id} не найдена."}

        await session.execute(
            update(AdRequest).where(AdRequest.id == ad_id).values(
                status="rejected",
                answered_at=datetime.utcnow(),
            )
        )
        await session.commit()

    return {"status": "ok", "message": f"❌ Реклама #{ad_id} отклонена."}


async def handle_admin_approve_news(dle_user_id: int, news_id: int) -> dict:
    """Админ утверждает новость."""
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        from sqlalchemy import select, update

        stmt = select(NewsSuggestion).where(NewsSuggestion.id == news_id)
        result = await session.execute(stmt)
        news = result.scalar_one_or_none()

        if not news:
            return {"error": f"❌ Новость #{news_id} не найдена."}

        await session.execute(
            update(NewsSuggestion).where(NewsSuggestion.id == news_id).values(
                status="approved",
                answered_at=datetime.utcnow(),
            )
        )
        await session.commit()

    return {"status": "ok", "message": f"✅ Новость #{news_id} утверждена!\n\nПользователю засчитано как предложенная новость."}


async def handle_admin_reject_news(dle_user_id: int, news_id: int) -> dict:
    """Админ отклоняет новость."""
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        from sqlalchemy import select, update

        stmt = select(NewsSuggestion).where(NewsSuggestion.id == news_id)
        result = await session.execute(stmt)
        news = result.scalar_one_or_none()

        if not news:
            return {"error": f"❌ Новость #{news_id} не найдена."}

        await session.execute(
            update(NewsSuggestion).where(NewsSuggestion.id == news_id).values(
                status="rejected",
                answered_at=datetime.utcnow(),
            )
        )
        await session.commit()

    return {"status": "ok", "message": f"❌ Новость #{news_id} отклонена."}


async def handle_admin_mark_viewed(dle_user_id: int, item_type: str, item_id: int) -> dict:
    """
    Помечает заявку как «просмотрено админом» (⏳ На рассмотрении).
    Вызывается когда админ открывает детали заявки.
    Меняет статус только если он был "new" → "in_progress".
    Архивные (approved/rejected) не трогаем.
    """
    if not _is_admin(dle_user_id):
        return {"error": "⛔ Доступно только администратору."}

    async with async_session() as session:
        if item_type == "ad":
            ad = await session.get(AdRequest, item_id)
            if ad and ad.status == "new":
                ad.status = "in_progress"
                await session.commit()
                return {"ok": True, "new_status": "in_progress"}
        elif item_type == "news":
            ns = await session.get(NewsSuggestion, item_id)
            if ns and ns.status == "new":
                ns.status = "in_progress"
                await session.commit()
                return {"ok": True, "new_status": "in_progress"}

    return {"ok": False}


# ============================================================
#  МОИ ОБРАЩЕНИЯ (для обычного юзера)
# ============================================================

async def handle_my_requests(dle_user_id: int) -> dict:
    """
    Возвращает все заявки пользователя:
    - Реклама (статус + ответ админа + цена)
    - Предложенные новости (статус + ответ)
    - Сообщения админу (статус + ответ)

    Параметр: dle_user_id — ID юзера из DLE.
    """
    if not dle_user_id:
        return {"error": "Нужен dle_user_id"}

    async with async_session() as session:
        from sqlalchemy import select

        ads = []
        news = []
        messages = []

        # Реклама
        stmt = (
            select(AdRequest)
            .where(AdRequest.dle_user_id == dle_user_id)
            .order_by(AdRequest.created_at.desc())
            .limit(50)
        )
        for ad in (await session.execute(stmt)).scalars().all():
            ads.append({
                "id": ad.id,
                "type": "ad",
                "ad_type": ad.ad_type or "feed",
                "text": ad.text[:100] + ("..." if len(ad.text) > 100 else ""),
                "full_text": ad.text,
                "image_path": ad.image_path,
                "platform_target": ad.platform_target,
                "days": ad.days,
                "pin": ad.pin,
                "pin_days": ad.pin_days or 0,
                "pin_platforms": ad.pin_platforms,
                "total_price": ad.total_price,
                "corrected_price": ad.corrected_price,
                "status": ad.status,
                "admin_reply": ad.admin_reply,
                "created_at": ad.created_at.isoformat(),
                "answered_at": ad.answered_at.isoformat() if ad.answered_at else None,
                "time_ago": _time_ago(ad.created_at),
                "answered_time_ago": _time_ago(ad.answered_at) if ad.answered_at else None,
                "banner_size": ad.banner_size or "728x90",
                "banner_placement": ad.banner_placement or "in_news",
                "banner_months": ad.banner_months or 1,
                "banner_opts": ad.banner_opts,
                "article_eternal": ad.article_eternal,
                "article_opts": ad.article_opts,
                "article_fix_days": ad.article_fix_days or 0,
                "article_months": ad.article_months or 1,
            })

        # Новости
        stmt = (
            select(NewsSuggestion)
            .where(NewsSuggestion.dle_user_id == dle_user_id)
            .order_by(NewsSuggestion.created_at.desc())
            .limit(50)
        )
        for ns in (await session.execute(stmt)).scalars().all():
            news.append({
                "id": ns.id,
                "type": "news",
                "title": ns.title,
                "image_path": ns.image_path,
                "text": ns.text[:100] + ("..." if len(ns.text) > 100 else ""),
                "full_text": ns.text,
                "status": ns.status,
                "admin_reply": ns.admin_reply,
                "created_at": ns.created_at.isoformat(),
                "answered_at": ns.answered_at.isoformat() if ns.answered_at else None,
                "time_ago": _time_ago(ns.created_at),
                "answered_time_ago": _time_ago(ns.answered_at) if ns.answered_at else None,
            })

        # Сообщения админу
        stmt = (
            select(AdminMessage)
            .order_by(AdminMessage.created_at.desc())
            .limit(50)
        )
        if platform_user_id:
            stmt = stmt.where(AdminMessage.platform_user_id == platform_user_id)
        else:
            stmt = stmt.where(AdminMessage.dle_user_id == dle_user_id)
        for msg in (await session.execute(stmt)).scalars().all():
            messages.append({
                "id": msg.id,
                "type": "message",
                "text": msg.text[:100] + ("..." if len(msg.text) > 100 else ""),
                "full_text": msg.text,
                "status": msg.status,
                "admin_reply": msg.admin_reply,
                "created_at": msg.created_at.isoformat(),
                "answered_at": msg.answered_at.isoformat() if msg.answered_at else None,
                "time_ago": _time_ago(msg.created_at),
            })

    # Сортируем всё вместе
    all_items = ads + news + messages
    all_items.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "items": all_items,
        "total": len(all_items),
        "by_type": {
            "ads": len(ads),
            "news": len(news),
            "messages": len(messages),
        },
    }


async def handle_my_notifications(dle_user_id: int) -> dict:
    """
    Считает уведомления для юзера:
    - Сколько заявок получили ответ (статус изменился с "new")
    - Новые ответы админа

    Параметр: dle_user_id — ID юзера из DLE.
    """
    if not dle_user_id:
        return {"has_notifications": False, "total_new": 0}

    async with async_session() as session:
        from sqlalchemy import select, func

        def cnt(table, *filters):
            stmt = select(func.count()).select_from(table)
            for f in filters:
                stmt = stmt.where(f)
            return session.execute(stmt)

        # Сколько заявок получили ответ (статус ≠ "new")
        ads_answered = (await cnt(
            AdRequest,
            AdRequest.dle_user_id == dle_user_id,
            AdRequest.status.in_(["approved", "rejected", "paid", "done"]),
        )).scalar() or 0

        news_answered = (await cnt(
            NewsSuggestion,
            NewsSuggestion.dle_user_id == dle_user_id,
            NewsSuggestion.status.in_(["approved", "rejected"]),
        )).scalar() or 0

        msgs_answered = (await cnt(
            AdminMessage,
            AdminMessage.dle_user_id == dle_user_id,
            AdminMessage.status == "answered",
        )).scalar() or 0

        # Новые ответы (answered_at не пустой + admin_reply не пустой)
        # Это грубый подсчёт — в будущем можно добавить флаг «прочитано»
        ads_with_reply = (await cnt(
            AdRequest,
            AdRequest.dle_user_id == dle_user_id,
            AdRequest.admin_reply.isnot(None),
        )).scalar() or 0

        news_with_reply = (await cnt(
            NewsSuggestion,
            NewsSuggestion.dle_user_id == dle_user_id,
            NewsSuggestion.admin_reply.isnot(None),
        )).scalar() or 0

        msgs_with_reply = (await cnt(
            AdminMessage,
            AdminMessage.dle_user_id == dle_user_id,
            AdminMessage.admin_reply.isnot(None),
        )).scalar() or 0

    total_answered = ads_answered + news_answered + msgs_answered
    total_with_reply = ads_with_reply + news_with_reply + msgs_with_reply

    return {
        "has_notifications": total_with_reply > 0,
        "total_answered": total_answered,
        "total_with_reply": total_with_reply,
        "by_type": {
            "ads_answered": ads_answered,
            "news_answered": news_answered,
            "messages_answered": msgs_answered,
            "ads_with_reply": ads_with_reply,
            "news_with_reply": news_with_reply,
            "messages_with_reply": msgs_with_reply,
        },
    }


# ============================================================
#  СТАРЫЕ ФУНКЦИИ АДМИН-ПАНЕЛИ (для VK-адаптера — пока)
# ============================================================

async def handle_admin_list_messages(
    platform: str, platform_user_id: str, dle_user_id: int,
    status_filter: str = "new", limit: int = 5,
) -> str:
    """
    Показывает последние обращения указанного статуса.
    """
    if not _is_admin(dle_user_id):
        return "⛔ Доступно только администратору."

    async with async_session() as session:
        from sqlalchemy import select

        stmt = (
            select(AdminMessage)
            .where(AdminMessage.status == status_filter)
            .order_by(AdminMessage.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

    if not messages:
        status_labels = {
            "new": "новых",
            "in_progress": "в работе",
            "answered": "отвеченных",
        }
        label = status_labels.get(status_filter, status_filter)
        return f"📭 Нет {label} обращений."

    status_emojis = {"new": "🔴", "in_progress": "🟡", "answered": "🟢"}
    sep = "─────────────────────"
    lines = [f"📩 Обращения ({status_filter}):", ""]

    for msg in messages:
        lines.append(
            f"[#{msg.id}] {status_emojis.get(msg.status, '⚪')} "
            f"{msg.user_name or 'Гость'} ({msg.platform})"
        )
        lines.append(f"   {msg.text[:80]}{'...' if len(msg.text) > 80 else ''}")
        lines.append(f"   📅 {msg.created_at.strftime('%d.%m.%Y %H:%M')}")
        lines.append(sep)

    lines.append(
        f'Для просмотра напишите «взять #» (например: «взять 1»).'
    )
    return "\n".join(lines)


async def handle_admin_view_message(
    platform: str, platform_user_id: str, dle_user_id: int, message_id: int,
) -> str:
    """
    Показывает одно обращение полностью.
    """
    if not _is_admin(dle_user_id):
        return "⛔ Доступно только администратору."

    async with async_session() as session:
        from sqlalchemy import select
        stmt = select(AdminMessage).where(AdminMessage.id == message_id)
        result = await session.execute(stmt)
        msg = result.scalar_one_or_none()

    if not msg:
        return f"❌ Обращение #{message_id} не найдено."

    # Меняем на «в работе», если было «новое»
    if msg.status == "new":
        async with async_session() as session:
            from sqlalchemy import select, update
            stmt = (
                update(AdminMessage)
                .where(AdminMessage.id == message_id)
                .values(status="in_progress")
            )
            await session.execute(stmt)
            await session.commit()

    status_labels = {"new": "🔴 Новое", "in_progress": "🟡 В работе", "answered": "🟢 Отвечено"}

    lines = [
        f"📩 Обращение #{msg.id}",
        f"От: {msg.user_name or 'Гость'}",
        f"Канал: {msg.platform}",
        f"Статус: {status_labels.get(msg.status, msg.status)}",
        f"Дата: {msg.created_at.strftime('%d.%m.%Y %H:%M')}",
        "─────────────────────",
        msg.text,
        "─────────────────────",
    ]

    if msg.admin_reply:
        lines.append(msg.admin_reply)
        lines.append("─────────────────────")

    if msg.status != "answered":
        lines.append("Напишите «ответ #ТЕКСТ» (например: «ответ 1 Спасибо, принято!»).")

    return "\n".join(lines)


async def handle_admin_respond(
    platform: str, platform_user_id: str, dle_user_id: int,
    message_id: int, reply_text: str,
) -> str:
    """
    Админ отвечает на обращение.
    Сохраняет ответ в БД и меняет статус на «отвечено».
    """
    if not _is_admin(dle_user_id):
        return "⛔ Доступно только администратору."

    async with async_session() as session:
        from sqlalchemy import select, update

        stmt = select(AdminMessage).where(AdminMessage.id == message_id)
        result = await session.execute(stmt)
        msg = result.scalar_one_or_none()

        if not msg:
            return f"❌ Обращение #{message_id} не найдено."

        # Сохраняем ответ
        update_stmt = (
            update(AdminMessage)
            .where(AdminMessage.id == message_id)
            .values(
                admin_reply=reply_text,
                status="answered",
                answered_at=datetime.utcnow(),
            )
        )
        await session.execute(update_stmt)
        await session.commit()

    return (
        f"✅ Ответ на обращение #{message_id} сохранён.\n\n"
        f"Пользователь получит ответ в {msg.platform.upper()}."
    )


async def handle_my_stats(dle_user_id: int) -> dict:
    """
    Личная статистика пользователя.
    Группа из DLE + счётчики из БД бота + данные подписки из webcash.
    """
    if not dle_user_id:
        return {"error": "Не указан ID пользователя."}

    from sqlalchemy import select, func
    import re
    from datetime import datetime

    # Данные из DLE
    dle_data = {}
    try:
        dle_raw = await dle_client.take_user_by_id(dle_user_id)
        if isinstance(dle_raw, dict) and "data" in dle_raw:
            dle_data = dle_raw["data"] if dle_raw["data"] else {}
        else:
            dle_data = dle_raw
    except Exception:
        pass

    # Статистика из БД бота
    ads_count = 0
    news_count = 0
    msgs_count = 0

    async with async_session() as session:
        ads_count = (await session.execute(
            select(func.count(AdRequest.id)).where(AdRequest.dle_user_id == dle_user_id)
        )).scalar() or 0
        news_count = (await session.execute(
            select(func.count(NewsSuggestion.id)).where(NewsSuggestion.dle_user_id == dle_user_id)
        )).scalar() or 0
        msgs_count = (await session.execute(
            select(func.count(AdminMessage.id)).where(AdminMessage.dle_user_id == dle_user_id)
        )).scalar() or 0

    # Платные группы
    paid_groups = {
        6: {"name": "Временщики", "label": "Временный доступ"},
        7: {"name": "Премиум", "label": "ПРЕМИУМ"},
        8: {"name": "VIP", "label": "VIP"},
    }
    group_id = int(dle_data.get("user_group", 0)) if dle_data else 0
    paid_info = paid_groups.get(group_id)

    # Планы по ценам
    PLANS_BY_AMOUNT = {
        6: {
            "195":  {"name": "1 день",  "hours": 24},
            "455":  {"name": "5 дней",  "hours": 120},
            "1330": {"name": "31 день",  "hours": 744},
            "2200": {"name": "181 день", "hours": 4344},
        },
        8: {
            "2550": {"name": "365 дней", "hours": 8760},
            "4990": {"name": "Навсегда", "hours": 0},
        },
    }

    # Дата окончания (поле time_limit — Unix timestamp)
    raw_time_limit = dle_data.get("time_limit", 0) if dle_data else 0
    time_limit_ts = 0
    if raw_time_limit:
        try:
            time_limit_ts = int(raw_time_limit)
        except (ValueError, TypeError):
            time_limit_ts = 0
    expires_at = None
    days_left = 0
    hours_left = 0
    plan_name = None
    plan_hours = 0
    purchased_at = None
    sub_source = "Покупка"
    is_permanent = False

    if time_limit_ts > 0:
        expire_dt = datetime.fromtimestamp(time_limit_ts)
        now = datetime.now()
        expires_at = expire_dt.strftime("%d.%m.%Y %H:%M")
        if expire_dt > now:
            diff = expire_dt - now
            days_left = diff.days
            hours_left = diff.seconds // 3600
        else:
            days_left = 0
            hours_left = 0

    # Ищем последнюю покупку в webcash
    if paid_info:
        try:
            webcash = await dle_client.call("load_table", [
                "dle_webcash_gateway_invoices",
                "id,created,checkout_store",
                f"user_id={dle_user_id} AND area_alias='changegroup'",
                1, 0, 1, "id", "DESC"
            ])
            if webcash and webcash.get("data"):
                raw_data = webcash["data"]
                if isinstance(raw_data, list) and len(raw_data) > 0:
                    inv = raw_data[0]
                elif isinstance(raw_data, dict):
                    inv = raw_data
                else:
                    inv = None
                if inv:
                    purchased_at = inv.get("created", "")
                    store = inv.get("checkout_store", "")

                    m_amount = re.search(r's:6:"amount";s:\d+:"(\d+)";', store)
                    if m_amount:
                        amount = m_amount.group(1)
                        group_plans = PLANS_BY_AMOUNT.get(group_id, {})
                        if amount in group_plans:
                            plan = group_plans[amount]
                            plan_name = plan["name"]
                            plan_hours = plan["hours"]
                            is_permanent = (plan_hours == 0)
        except Exception:
            pass

        # Определяем план по длительности, если не нашли по цене
        if not plan_name and time_limit_ts > 0:
            try:
                if purchased_at:
                    purchase_dt = datetime.strptime(purchased_at, "%Y-%m-%d %H:%M:%S")
                    duration_days = (expire_dt - purchase_dt).days if expire_dt else 0
                else:
                    duration_days = days_left

                if duration_days >= 365:
                    plan_name = "365 дней"; plan_hours = 8760
                elif duration_days >= 180:
                    plan_name = "181 день"; plan_hours = 4344
                elif duration_days >= 30:
                    plan_name = "31 день"; plan_hours = 744
                elif duration_days >= 4:
                    plan_name = "5 дней"; plan_hours = 120
                elif duration_days >= 1:
                    plan_name = "1 день"; plan_hours = 24
                else:
                    plan_name = "1 день"; plan_hours = 24
            except Exception:
                plan_name = "1 день"; plan_hours = 24

        if not plan_name:
            plan_name = "1 день"
            plan_hours = 24

        # Если нет webcash-записи — админ назначил
        if not purchased_at:
            sub_source = "Назначен админом"

    # --- Список всех платежей пользователя ---
    payments_list = []
    try:
        all_invoices = await dle_client.call("load_table", [
            "dle_webcash_gateway_invoices",
            "id,created,area_alias,checkout_store",
            f"user_id={dle_user_id}",
            1, 0, 50, "id", "DESC"
        ])
        if all_invoices and all_invoices.get("data"):
            raw = all_invoices["data"]
            rows = raw if isinstance(raw, list) else [raw]
            for inv in rows:
                if not isinstance(inv, dict):
                    continue
                store = inv.get("checkout_store", "")
                amount = ""
                target_group = ""
                m_amount = re.search(r's:6:"amount";s:\d+:"(\d+)";', store)
                if m_amount:
                    amount = m_amount.group(1)
                m_group = re.search(r's:15:"target_group_id";i:(\d+);', store)
                if m_group:
                    gid = int(m_group.group(1))
                    g_info = paid_groups.get(gid, {})
                    target_group = g_info.get("label", f"Группа {gid}") if g_info else f"Группа {gid}"
                payments_list.append({
                    "date": inv.get("created", ""),
                    "amount": amount,
                    "group": target_group,
                })
    except Exception:
        pass

    # --- Разбивка рекламы по типам и статусам ---
    ads_by_type = {}
    ads_finance = {"approved": {"count": 0, "sum": 0}, "rejected": {"count": 0, "sum": 0},
                   "in_progress": {"count": 0, "sum": 0}, "new": {"count": 0, "sum": 0}}
    news_by_status = {}

    try:
        async with async_session() as session2:
            # Реклама: группировка по ad_type + status
            rows = await session2.execute(
                select(AdRequest.ad_type, AdRequest.status,
                       func.count(AdRequest.id), func.sum(AdRequest.total_price))
                .where(AdRequest.dle_user_id == dle_user_id)
                .group_by(AdRequest.ad_type, AdRequest.status)
            )
            temp = {}
            for row in rows:
                t, s, cnt, total = row
                total = total or 0
                if t not in temp:
                    temp[t] = {}
                temp[t][s] = {"count": cnt, "sum": float(total)}
                # копим finance
                if s in ads_finance:
                    ads_finance[s]["count"] += cnt
                    ads_finance[s]["sum"] += float(total)
                else:
                    ads_finance[s] = {"count": cnt, "sum": float(total)}
            ads_by_type = temp

            # Новости: группировка по status
            rows2 = await session2.execute(
                select(NewsSuggestion.status, func.count(NewsSuggestion.id))
                .where(NewsSuggestion.dle_user_id == dle_user_id)
                .group_by(NewsSuggestion.status)
            )
            for row in rows2:
                news_by_status[row[0]] = row[1]

            # Общая сумма всех заявок
            total_sum_row = await session2.execute(
                select(func.sum(AdRequest.total_price))
                .where(AdRequest.dle_user_id == dle_user_id)
            )
            ads_finance["total_sum"] = float(total_sum_row.scalar() or 0)
    except Exception:
        pass

    return {
        "group_id": group_id,
        "group_name": dle_data.get("group_name", "Неизвестно") if dle_data else "Неизвестно",
        "username": dle_data.get("name", "") if dle_data else "",
        "email": dle_data.get("email", "") if dle_data else "",
        "registration_date": dle_data.get("reg_date", dle_data.get("registration_date", "")) if dle_data else "",
        "is_paid": paid_info is not None,
        "paid_label": paid_info["label"] if paid_info else None,
        "expires_at": expires_at,
        "days_left": days_left,
        "hours_left": hours_left,
        "plan_name": plan_name,
        "plan_hours": plan_hours,
        "purchased_at": purchased_at,
        "sub_source": sub_source,
        "is_permanent": is_permanent,
        "total_ads": ads_count,
        "total_news": news_count,
        "total_messages": msgs_count,
        "payments": payments_list,
        "ads_by_type": ads_by_type,
        "ads_finance": ads_finance,
        "news_by_status": news_by_status,
    }
