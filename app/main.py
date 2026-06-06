"""
main.py — Точка входа FastAPI

Запуск: uvicorn app.main:app --reload
"""

import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.security import create_jwt_token
from app.core.rate_limiter import check_rate_limit
from app.handlers.manage import router as manage_router
from app.handlers.commands import (
    handle_start, handle_auth, handle_profile, handle_search,
    handle_clear_chat, handle_settings, handle_stats, handle_channels,
    handle_admin_message, handle_ad_submit, handle_news_suggest,
    handle_admin_panel, handle_admin_list_messages,
    handle_admin_view_message, handle_admin_respond,
    # Админ-панель 2.0:
    handle_admin_welcome, handle_admin_panel_data,
    handle_admin_approve_ad, handle_admin_reject_ad,
    handle_admin_approve_news, handle_admin_reject_news,
    handle_admin_mark_viewed,
    # Мои обращения:
    handle_my_requests, handle_my_notifications, handle_my_stats,
    # Редактор цен:
    get_prices, update_prices,
    # Чат с админом:
    handle_get_chat, handle_get_chat_list, handle_admin_chat_reply,
    handle_mark_chat_read, handle_delete_chat, handle_user_search,
    handle_bot_users_stats,
    # Архивация чатов:
    handle_archive_chat, handle_get_archived_chats,
)
from app.schemas.user import (
    AuthRequest, AuthResponse, SearchRequest, AiQuestion, AiAnswer,
    AdOrderRequest, NewsSuggestionRequest,
)
from app.adapters.vk import start_vk_bot
from app.adapters.telegram import start_telegram_bot


# --------------------------------------------------
# Жизненный цикл приложения (запуск / остановка)
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Что делать при старте и остановке бота"""
    # >>> Старт <<<
    print(" Запуск Universal Chat Bot...")
    await init_db()
    print(" База данных готова")

    # Запускаем VK-бота в фоне
    vk_task = asyncio.create_task(start_vk_bot())

    # Запускаем Telegram-бота в фоне
    tg_task = asyncio.create_task(start_telegram_bot())

    yield  # здесь бот работает

    # >>> Стоп <<<
    print(" Остановка Universal Chat Bot...")
    vk_task.cancel()
    tg_task.cancel()
    await close_db()
    print(" Соединения закрыты")


# --------------------------------------------------
# Создаём приложение
# --------------------------------------------------

app = FastAPI(
    title="Universal Chat Bot",
    description="Мульти-платформенный бот для turbinist.ru",
    version="0.1.0",
    lifespan=lifespan,
)

# Разрешаем запросы с любого домена (чтобы чат-виджет работал)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Раздача загруженных файлов (картинки рекламы)
import os
uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=uploads_dir), name="static")

# Подключаем Deploy Bridge (manage.py — управление VPS)
app.include_router(manage_router)


# --------------------------------------------------
# Маршруты (API эндпоинты)
# --------------------------------------------------

@app.get("/widget")
async def widget():
    """Раздача чат-виджета."""
    widget_path = os.path.join(os.path.dirname(__file__), "widgets", "chat", "index.html")
    with open(widget_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/")
async def root():
    """Проверка: бот жив?"""
    return {"status": "ok", "bot": "Universal Chat Bot", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Проверка здоровья: работает ли БД, Redis и т.д."""
    return {"status": "healthy", "dle_api": settings.DLE_API_URL}


@app.post("/api/auth")
async def api_auth(auth_data: AuthRequest, req: Request):
    """
    Авторизация пользователя.
    Проверяет логин/пароль через DLE API.
    При успехе выдаёт JWT-токен для дальнейших запросов.
    🔒 Защита: не больше 5 попыток за 15 минут с одного IP.
    """
    # 🔒 Rate limiting: проверяем, не превышен ли лимит попыток
    client_ip = req.client.host if req.client else "unknown"
    allowed, remaining = await check_rate_limit(client_ip, "auth")
    if not allowed:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "message": f" Слишком много попыток входа. Подождите немного.",
            },
        )

    try:
        result = await handle_auth(
            auth_data.platform, auth_data.platform_user_id,
            auth_data.login, auth_data.password,
            anon_name=auth_data.anon_name or "",
        )

        # Если авторизация успешна — добавляем JWT-токен
        if result.success:
            jwt_token = create_jwt_token(
                user_id=str(result.dle_user_id),
                username=result.dle_username,
                platform=auth_data.platform,
            )
            result.access_token = jwt_token

        return result
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "message": f"⚠️ PHP-мостик недоступен (HTTP {e.response.status_code}). Сначала создай PHP-мостик на сервере.",
            },
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "message": "⚠️ Не могу соединиться с DLE. PHP-мостик не запущен или турбинист недоступен.",
            },
        )


@app.get("/api/profile/{username}")
async def api_profile(username: str, platform: str = "web", user_id: str = "0"):
    """Профиль пользователя"""
    return await handle_profile(platform, user_id, username)


@app.post("/api/search")
async def api_search(search_data: SearchRequest, req: Request):
    """
    Поиск по сайту.
    🔒 Защита: не больше 30 запросов в минуту с одного IP.
    """
    # 🔒 Rate limiting
    client_ip = req.client.host if req.client else "unknown"
    allowed, _ = await check_rate_limit(client_ip, "search")
    if not allowed:
        return JSONResponse(
            status_code=200,
            content={"results": "⚠️ Слишком много запросов. Подождите минуту."},
        )

    result = await handle_search(
        search_data.platform, search_data.platform_user_id,
        search_data.query,
        page=search_data.page,
        smart=search_data.smart,
    )
    return {"results": result.text, "items": result.items or [], "pagination": {
        "has_more": result.has_more,
        "current_page": result.current_page,
        "total_pages": result.total_pages,
        "total_results": result.total_results,
        "query": result.query,
    }}


@app.post("/api/ai")
async def api_ai(ai_data: AiQuestion, req: Request):
    """
    AI-вопрос через DeepSeek.
    🔒 Защита: не больше 10 вопросов в минуту с одного IP.
    """
    # 🔒 Rate limiting
    client_ip = req.client.host if req.client else "unknown"
    allowed, _ = await check_rate_limit(client_ip, "ai")
    if not allowed:
        return JSONResponse(
            status_code=200,
            content={"answer": "⚠️ Слишком много вопросов. Подождите минуту.", "warning": None},
        )

    return AiAnswer(
        answer=f"[Заглушка] Вы спросили: {ai_data.question}. AI-обработка будет добавлена позже.",
        warning="⚠️ AI-функция в разработке",
    )


@app.post("/api/ad")
async def api_ad(request: AdOrderRequest):
    """Оформление рекламы — сохраняет в БД"""
    result = await handle_ad_submit(
        request.platform, request.platform_user_id,
        request.text, request.platforms,
        request.days, request.pin, request.total_price,
        dle_user_id=request.dle_user_id,
        user_name=request.user_name,
        ad_type=request.ad_type,
        image_path=request.image_path,
        pin_days=request.pin_days,
        pin_platforms=request.pin_platforms,
        article_eternal=request.article_eternal,
        article_opts=request.article_opts,
        article_fix_days=request.article_fix_days,
        article_months=request.article_months,
        banner_size=request.banner_size,
        banner_placement=request.banner_placement,
        banner_months=request.banner_months,
        banner_opts=request.banner_opts,
    )
    return {"status": "ok", "message": result}


@app.post("/api/upload/ad-image")
async def api_upload_ad_image(
    file: UploadFile = File(...),
    dle_user_id: int = Form(0),
):
    """
    Загрузка картинки для рекламы.
    Сохраняет в uploads/ad_images/ и возвращает путь.
    """
    import os
    import uuid

    # Проверяем что это картинка (MIME + расширение)
    content_type = file.content_type or ""
    ext = os.path.splitext(file.filename or "image.png")[1].lower()
    allowed_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    if not content_type.startswith("image/") or ext not in allowed_exts:
        return JSONResponse(status_code=400, content={"error": "Только картинки (png, jpg, gif, webp). Получен: " + ext})

    # Создаём папку если нет
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "ad_images")
    os.makedirs(upload_dir, exist_ok=True)

    # Уникальное имя файла
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_dir, filename)

    # Сохраняем
    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    # Путь относительно папки uploads (для раздачи через /static)
    rel_path = f"/static/ad_images/{filename}"

    return {"status": "ok", "path": rel_path, "filename": filename}


@app.post("/api/news")
async def api_news(request: NewsSuggestionRequest):
    """Предложить новость админу — сохраняет в БД"""
    result = await handle_news_suggest(
        request.platform, request.platform_user_id,
        request.title, request.text,
        dle_user_id=request.dle_user_id,
        user_name=request.user_name,
    )
    return {"status": "ok", "message": result}


@app.post("/api/admin/message")
async def api_admin_message(request: Request):
    """
    Сообщение админу из веб-виджета.
    Сохраняет в таблицу admin_messages.
    """
    import json
    body = await request.json()
    user_name = body.get("user_name", "Гость")
    text = body.get("text", "")
    dle_user_id = body.get("dle_user_id")

    result = await handle_admin_message(
        "web", body.get("platform_user_id", "0"),
        user_name, text,
        dle_user_id=dle_user_id,
    )
    return result  # handle_admin_message уже возвращает {"status":"ok","message":"...","id":X}


@app.get("/api/admin/messages")
async def api_admin_messages_list(
    platform_user_id: str = "0",
    dle_user_id: int = 0,
    status: str = "new",
    limit: int = 10,
):
    """
    Админ-панель: список обращений.
    Только для админа (dle_user_id == ADMIN_USER_ID).
    """
    if dle_user_id != settings.ADMIN_USER_ID:
        return JSONResponse(
            status_code=403,
            content={"error": "Доступно только администратору."},
        )

    result = await handle_admin_list_messages(
        "web", platform_user_id, dle_user_id, status, limit,
    )
    return {"status": "ok", "data": result}


@app.get("/api/admin/messages/count")
async def api_admin_messages_count(dle_user_id: int = 0):
    """
    Количество обращений по статусам.
    Только для админа.
    """
    if dle_user_id != settings.ADMIN_USER_ID:
        return JSONResponse(
            status_code=403,
            content={"error": "Доступно только администратору."},
        )

    result = await handle_admin_panel("web", "0", dle_user_id)
    return {"status": "ok", "data": result}


@app.post("/api/admin/respond")
async def api_admin_respond(request: Request):
    """
    Ответ админа на обращение.
    """
    import json
    body = await request.json()
    message_id = body.get("message_id", 0)
    dle_user_id = body.get("dle_user_id", 0)
    reply_text = body.get("reply_text", "")

    if dle_user_id != settings.ADMIN_USER_ID:
        return JSONResponse(
            status_code=403,
            content={"error": "Доступно только администратору."},
        )

    result = await handle_admin_respond(
        "web", body.get("platform_user_id", "0"),
        dle_user_id, int(message_id), reply_text,
    )
    return {"status": "ok", "message": result}


# --------------------------------------------------
#  АДМИН-ПАНЕЛЬ 2.0 — новые эндпоинты
# --------------------------------------------------


@app.get("/api/admin/welcome")
async def api_admin_welcome(dle_user_id: int = 0):
    """
    Приветствие для админа — сколько новых заявок.
    """
    result = await handle_admin_welcome(dle_user_id)
    return result


@app.get("/api/admin/stats")
async def api_admin_stats(dle_user_id: int = 0):
    """
    Статистика для админа: доходы, принятые/отклонённые заявки, разбивка по типам.
    """
    from app.handlers.commands import handle_admin_stats
    result = await handle_admin_stats(dle_user_id)
    return result


@app.get("/api/admin/bot-users")
async def api_admin_bot_users(dle_user_id: int = 0):
    """
    Статистика пользователей бота по платформам.
    Сколько юзеров на веб, TG, VK, MAXX (заглушка) и всего.
    """
    result = await handle_bot_users_stats(dle_user_id)
    return result


@app.get("/api/admin/panel")
async def api_admin_panel(
    dle_user_id: int = 0,
    section: str = "ads",
    page: int = 1,
    limit: int = 10,
):
    """
    Админ-панель с разделами: all, ads, news, messages, archive.
    Возвращает JSON со счётчиками и элементами.
    """
    result = await handle_admin_panel_data(dle_user_id, section, page, limit)
    return result


@app.post("/api/admin/ad/approve")
async def api_admin_ad_approve(request: Request):
    """
    Админ подтверждает рекламу.
    """
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    ad_id = body.get("ad_id", 0)
    corrected_price = body.get("corrected_price")

    result = await handle_admin_approve_ad(dle_user_id, ad_id, corrected_price)
    return result


@app.post("/api/admin/ad/reject")
async def api_admin_ad_reject(request: Request):
    """
    Админ отклоняет рекламу.
    """
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    ad_id = body.get("ad_id", 0)

    result = await handle_admin_reject_ad(dle_user_id, ad_id)
    return result


@app.post("/api/admin/news/approve")
async def api_admin_news_approve(request: Request):
    """
    Админ утверждает новость.
    """
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    news_id = body.get("news_id", 0)

    result = await handle_admin_approve_news(dle_user_id, news_id)
    return result


@app.post("/api/admin/news/reject")
async def api_admin_news_reject(request: Request):
    """
    Админ отклоняет новость.
    """
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    news_id = body.get("news_id", 0)

    result = await handle_admin_reject_news(dle_user_id, news_id)
    return result


@app.post("/api/admin/mark-viewed")
async def api_admin_mark_viewed(request: Request):
    """
    Помечает заявку как просмотренную админом (⏳ На рассмотрении).
    Вызывается фронтом при открытии деталей заявки.
    """
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    item_type = body.get("item_type", "")
    item_id = body.get("item_id", 0)

    result = await handle_admin_mark_viewed(dle_user_id, item_type, item_id)
    return result


# --------------------------------------------------
#  РЕДАКТОР ЦЕН
# --------------------------------------------------


@app.get("/api/prices")
async def api_get_prices():
    """Получить все цены (публичный)."""
    result = await get_prices()
    return result


@app.post("/api/admin/prices")
async def api_update_prices(request: Request):
    """Админ обновляет цены."""
    import json
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    updates = body.get("updates", {})
    result = await update_prices(dle_user_id, updates)
    return result


# --------------------------------------------------
#  МОИ ОБРАЩЕНИЯ — юзер видит свои заявки и ответы
# --------------------------------------------------


@app.get("/api/my/requests")
async def api_my_requests(dle_user_id: int = 0):
    """
    Возвращает все обращения пользователя:
    реклама, предложенные новости, сообщения админу.
    С статусами и ответами админа.
    """
    if not dle_user_id:
        return {"error": "Не указан dle_user_id"}
    return await handle_my_requests(dle_user_id)


@app.get("/api/my/notifications")
async def api_my_notifications(dle_user_id: int = 0):
    """
    Количество уведомлений для пользователя.
    Показывает сколько заявок получили ответ.
    """
    if not dle_user_id:
        return {"has_notifications": False, "total_new": 0}
    return await handle_my_notifications(dle_user_id)


@app.get("/api/my/stats")
async def api_my_stats(dle_user_id: int = 0):
    """
    Личная статистика пользователя.
    Группа из DLE + счётчики из БД бота.
    """
    return await handle_my_stats(dle_user_id)


# --------------------------------------------------
#  ЧАТ С АДМИНОМ
# --------------------------------------------------


@app.get("/api/chat")
async def api_get_chat(dle_user_id: int = 0, platform_user_id: str = ""):
    """Вся переписка юзера или анонима с админом."""
    if platform_user_id:
        return await handle_get_chat(0, platform_user_id)
    if not dle_user_id:
        return {"error": "Нужен dle_user_id или platform_user_id"}
    return await handle_get_chat(dle_user_id)


@app.post("/api/chat/read")
async def api_mark_chat_read(request: Request):
    """Пометить все сообщения юзера как прочитанные."""
    import json
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    platform_user_id = body.get("platform_user_id", "")
    if not dle_user_id and not platform_user_id:
        return {"error": "Нужен dle_user_id или platform_user_id"}
    return await handle_mark_chat_read(dle_user_id, platform_user_id)

@app.post("/api/chat/delete")
async def api_delete_chat(request: Request):
    """Удалить все сообщения юзера или анонима из чата с админом."""
    import json
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    platform_user_id = body.get("platform_user_id", "")
    if platform_user_id:
        return await handle_delete_chat(0, platform_user_id)
    if not dle_user_id:
        return {"error": "Нужен dle_user_id или platform_user_id"}
    return await handle_delete_chat(dle_user_id)


@app.post("/api/chat/archive")
async def api_archive_chat(request: Request):
    """Архивировать чат пользователя."""
    import json
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    if not dle_user_id:
        return {"error": "Нужен dle_user_id"}
    return await handle_archive_chat(dle_user_id, archived=True)


@app.post("/api/chat/unarchive")
async def api_unarchive_chat(request: Request):
    """Разархивировать чат пользователя."""
    import json
    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    if not dle_user_id:
        return {"error": "Нужен dle_user_id"}
    return await handle_archive_chat(dle_user_id, archived=False)


@app.get("/api/admin/chats/archived")
async def api_get_archived_chats():
    """Список архивных чатов (для админ-панели)."""
    return await handle_get_archived_chats()


@app.get("/api/chat/exists")
async def api_chat_exists(dle_user_id: int = 0):
    """Есть ли хоть одно сообщение у юзера в чате с админом."""
    if not dle_user_id:
        return {"exists": False}
    from app.core.database import async_session
    from app.models.database import AdminMessage
    from sqlalchemy import select, func
    async with async_session() as session:
        cnt = await session.execute(
            select(func.count()).select_from(AdminMessage).where(AdminMessage.dle_user_id == dle_user_id)
        )
        return {"exists": cnt.scalar() > 0}


@app.get("/api/users/search")
async def api_user_search(q: str = "", dle_user_id: int = 0):
    """Поиск пользователей по имени для создания нового чата."""
    if not q or len(q.strip()) < 2:
        return {"users": []}
    users = await handle_user_search(q, exclude_dle_user_id=dle_user_id or None)
    return {"users": users}


@app.get("/api/admin/chats")
async def api_get_chat_list(dle_user_id: int = 0):
    """Список чатов для админа (по юзерам)."""
    if not dle_user_id:
        return {"error": "Нужен dle_user_id"}
    return await handle_get_chat_list(dle_user_id)


@app.post("/api/admin/chat/reply")
async def api_admin_chat_reply(request: Request):
    """Админ отвечает юзеру в чате."""
    import json
    body = await request.json()
    admin_id = body.get("admin_dle_id", 0)
    user_id = body.get("user_dle_id", 0)
    text = body.get("text", "")
    return await handle_admin_chat_reply(admin_id, user_id, text)


def build_system_prompt() -> str:
    """Собрать system prompt из knowledge_base файлов."""
    import os
    kb = "/opt/chat/knowledge_base"
    parts = []
    
    parts.append("Ты - ИИ-агент сайта turbinist.ru. Ты отвечаешь анонимным посетителям сайта.")
    parts.append("")
    
    for fname, label in [
        ("access/tariffs.md", "=== ТАРИФЫ ДОСТУПА ==="),
        ("access/faq.md", "=== FAQ (частые вопросы) ==="),
        ("access/status-groups.md", "=== ГРУППЫ ПОЛЬЗОВАТЕЛЕЙ ==="),
        ("access/how-to-buy.md", "=== КАК ОПЛАТИТЬ ==="),
        ("access/contacts.md", "=== КОНТАКТЫ АДМИНИСТРАТОРА ==="),
    ]:
        fpath = os.path.join(kb, fname)
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                parts.append(label)
                parts.append(f.read())
    
    parts.append("")
    parts.append("ПРАВИЛА ОТВЕТОВ:")
    parts.append("- Отвечай кратко (2-4 предложения)")
    parts.append("- Не выдумывай характеристики, не обещай того чего нет")
    parts.append("- Если вопрос сложный - предложи написать админу")
    parts.append("- Не выходи за темы сайта")
    parts.append("- Будь дружелюбным, называй пользователя по имени")
    parts.append("- Если пользователь хочет зарегистрироваться — используй информацию из status-groups.md: регистрация повышает статус с Безработного до Работника, это бесплатно и доступно всем")
    parts.append("- Ты НЕ можешь никого регистрировать, менять статусы или группы доступа. Предлагай пользователю зарегистрироваться самостоятельно на сайте или написать админу.")
    
    return "\n".join(parts)

system_prompt = build_system_prompt()

@app.post("/api/chat/anonymous-send")
async def api_anonymous_send(request: Request):
    """Аноним отправляет сообщение - ИИ-агент отвечает (DeepSeek)."""
    from app.models.database import AdminMessage
    from app.core.database import async_session
    from app.core.config import settings
    from sqlalchemy import select
    from datetime import datetime
    import logging
    log = logging.getLogger("ai_agent")

    body = await request.json()
    platform_user_id = body.get("platform_user_id", "")
    user_name = body.get("user_name", "Гость")
    text = body.get("text", "").strip()
    if not text:
        return {"error": "Пустое сообщение"}

    # Сохраняем сообщение юзера
    async with async_session() as session:
        msg = AdminMessage(
            platform="web",
            platform_user_id=platform_user_id,
            dle_user_id=None,
            user_name=user_name,
            sender_type="user",
            topic="question",
            text=text,
            status="new",
        )
        session.add(msg)
        await session.commit()

    # === ИИ-агент отвечает ===
    ai_reply = None
    if settings.DEEPSEEK_API_KEY:
        try:
            # Собираем историю диалога (последние 20 сообщений)
            async with async_session() as session:
                stmt = (
                    select(AdminMessage)
                    .where(AdminMessage.platform_user_id == platform_user_id)
                    .order_by(AdminMessage.created_at.asc())
                    .limit(20)
                )
                rows = (await session.execute(stmt)).scalars().all()

            messages = [{"role": "system", "content": system_prompt}]
            for r in rows:
                role = "user" if r.sender_type == "user" else "assistant"
                messages.append({"role": role, "content": r.text})

            # Запрос к DeepSeek
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    settings.DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 300,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ai_reply = data["choices"][0]["message"]["content"].strip()
                else:
                    log.error(f"DeepSeek API error: {resp.status_code}")

            # Сохраняем ответ ИИ
            if ai_reply:
                async with async_session() as session:
                    ai_msg = AdminMessage(
                        platform="web",
                        platform_user_id=platform_user_id,
                        dle_user_id=None,
                        user_name="ИИ-агент",
                        sender_type="admin",
                        topic="answer",
                        text=ai_reply,
                        status="sent",
                    )
                    session.add(ai_msg)
                    await session.commit()

                    # Помечаем все user-сообщения анонима как answered
                    from sqlalchemy import update
                    stmt = (
                        update(AdminMessage)
                        .where(AdminMessage.platform_user_id == platform_user_id)
                        .where(AdminMessage.sender_type == "user")
                        .where(AdminMessage.status == "new")
                        .values(status="answered", answered_at=datetime.utcnow())
                    )
                    await session.execute(stmt)
                    await session.commit()
        except Exception as e:
            log.error(f"AI agent error: {e}")

    return {"status": "ok", "id": msg.id, "ai_reply": ai_reply}


@app.get("/api/chat/anonymous-get")
async def api_anonymous_get(platform_user_id: str = ""):
    """История сообщений анонима по platform_user_id."""
    from app.models.database import AdminMessage
    from app.core.database import async_session

    if not platform_user_id:
        return {"messages": []}
    async with async_session() as session:
        from sqlalchemy import select
        stmt = (
            select(AdminMessage)
            .where(AdminMessage.platform_user_id == platform_user_id)
            .order_by(AdminMessage.created_at.asc())
            .limit(100)
        )
        rows = (await session.execute(stmt)).scalars().all()
    messages = []
    for r in rows:
        messages.append({
            "id": r.id,
            "sender_type": r.sender_type,
            "text": r.text,
            "user_name": r.user_name,
            "created_at": r.created_at.isoformat(),
        })
    return {"messages": messages}


@app.post("/api/chat/admin-reply")
async def api_admin_anon_reply(request: Request):
    """Админ отвечает анонимному пользователю (по platform_user_id)."""
    from app.models.database import AdminMessage
    from app.core.database import async_session
    body = await request.json()
    platform_user_id = body.get("platform_user_id", "")
    text = body.get("text", "").strip()
    admin_id = body.get("admin_dle_id", 0)
    if admin_id != settings.ADMIN_USER_ID:
        return {"error": "Только админ."}
    if not platform_user_id or not text:
        return {"error": "Не хватает данных"}
    async with async_session() as session:
        msg = AdminMessage(
            platform="web",
            platform_user_id=platform_user_id,
            dle_user_id=None,
            user_name="Администратор",
            sender_type="admin",
            topic="question",
            text=text,
            status="answered",
        )
        session.add(msg)
        await session.commit()
    return {"status": "ok", "id": msg.id}


@app.get("/api/chat/anonymous-recent")
async def api_anonymous_recent(dle_user_id: int = 0):
    """Последние анонимные чаты (для админа)."""
    from app.models.database import AdminMessage
    from app.core.database import async_session
    from sqlalchemy import select, func
    if dle_user_id != settings.ADMIN_USER_ID:
        return {"error": "Только админ."}
    async with async_session() as session:
        stmt = (
            select(AdminMessage.platform_user_id, AdminMessage.user_name,
                   func.max(AdminMessage.created_at).label("last_at"),
                   func.count().label("total"))
            .where(AdminMessage.dle_user_id == None)
            .group_by(AdminMessage.platform_user_id, AdminMessage.user_name)
            .order_by(func.max(AdminMessage.created_at).desc())
            .limit(10)
        )
        rows = (await session.execute(stmt)).all()
    chats = []
    for r in rows:
        if not r.platform_user_id:
            continue
        chats.append({
            "platform_user_id": r.platform_user_id,
            "user_name": r.user_name or "Гость",
            "last_at": r.last_at.isoformat() if r.last_at else "",
            "total": r.total,
        })
    return {"chats": chats}


@app.get("/api/stats/{platform}/{user_id}")
async def api_stats(platform: str, user_id: str):
    """Статистика пользователя"""
    return await handle_stats(platform, user_id)


@app.get("/api/channels")
async def api_channels(platform: str = "web", user_id: str = "0"):
    """Наши каналы"""
    return {"channels": await handle_channels(platform, user_id)}


# --------------------------------------------------
# 🟢 Онлайн-статус
# --------------------------------------------------

@app.get("/api/online/{dle_user_id}")
async def api_online(dle_user_id: int):
    """
    Проверяет, онлайн ли пользователь.
    Возвращает: {"online": true/false, "last_active": "X мин. назад"}
    Онлайн = был активен в последние 3 минуты.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.models.database import BotUser
    from app.core.database import async_session

    async with async_session() as session:
        stmt = select(BotUser).where(BotUser.dle_user_id == dle_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.last_active:
            return {"online": False, "last_active": None}

        now = datetime.utcnow()
        diff = now - user.last_active
        is_online = diff < timedelta(minutes=3)

        # Формат «был X мин. назад»
        if diff.seconds < 60:
            time_ago = "только что"
        elif diff.seconds < 3600:
            time_ago = f"{diff.seconds // 60} мин. назад"
        elif diff.days < 1:
            time_ago = f"{diff.seconds // 3600} ч. назад"
        else:
            time_ago = f"{diff.days} дн. назад"

        return {"online": is_online, "last_active": time_ago}


@app.post("/api/ping")
async def api_ping(request: Request):
    """
    Обновляет last_active пользователя.
    Вызывается с фронтенда каждые 30 секунд.
    """
    from datetime import datetime
    from sqlalchemy import select, update
    from app.models.database import BotUser
    from app.core.database import async_session

    body = await request.json()
    dle_user_id = body.get("dle_user_id", 0)
    username = body.get("username", "")

    if not dle_user_id:
        return {"status": "ok"}

    async with async_session() as session:
        stmt = select(BotUser).where(BotUser.dle_user_id == dle_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.last_active = datetime.utcnow()
        else:
            # Создаём запись если её нет
            new_user = BotUser(
                platform="web",
                platform_user_id=str(dle_user_id),
                dle_user_id=dle_user_id,
                dle_username=username,
                last_active=datetime.utcnow(),
            )
            session.add(new_user)
        await session.commit()

    return {"status": "ok"}


# --------------------------------------------------
# WebSocket эндпоинт (для чат-виджета — позже)
# --------------------------------------------------

@app.get("/ws/test")
async def ws_info():
    """Информация о WebSocket"""
    return {
        "message": "WebSocket сервер работает",
        "connect_to": f"ws://{settings.WS_HOST}:{settings.WS_PORT}/ws/chat",
    }


# --------------------------------------------------
# Тестовый эндпоинт (DLE подключение)
# --------------------------------------------------

@app.get("/api/dle/test")
async def test_dle():
    """Проверка связи с DLE (без авторизации)"""
    return {
        "dle_url": settings.DLE_API_URL,
        "has_token": bool(settings.DLE_API_TOKEN),
        "message": "DLE API настроен" if settings.DLE_API_TOKEN else "Токен DLE API не задан!",
    }


# --------------------------------------------------
# 🔒 Защищённые маршруты (требуют JWT-токен)
# --------------------------------------------------


@app.get("/api/me")
async def api_me(req: Request):
    """
    Возвращает профиль текущего пользователя по JWT-токену.
    Используется веб-виджетом после авторизации.

    🔒 Требует заголовок: Authorization: Bearer <токен>
    """
    # Проверяем JWT-токен вручную (без Depends для простоты)
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Требуется авторизация"})

    token = auth_header[7:]  # убираем "Bearer "
    from app.core.security import verify_jwt_token
    user = verify_jwt_token(token)

    if user is None:
        return JSONResponse(status_code=401, content={"error": "Токен недействителен"})

    # Получаем профиль
    profile = await handle_profile("web", user["user_id"], user["username"])
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "profile": {
            "group_name": profile.group_name,
            "email": profile.email,
        },
    }


@app.get("/api/me/stats")
async def api_my_stats(req: Request):
    """
    Статистика текущего пользователя по JWT-токену.
    🔒 Требует заголовок: Authorization: Bearer <токен>
    """
    from app.core.security import verify_jwt_token

    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Требуется авторизация"})

    token = auth_header[7:]
    user = verify_jwt_token(token)

    if user is None:
        return JSONResponse(status_code=401, content={"error": "Токен недействителен"})

    stats = await handle_stats("web", user["user_id"])
    return {"user_id": user["user_id"], "username": user["username"], "stats": stats}
