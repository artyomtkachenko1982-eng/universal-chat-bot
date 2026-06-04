"""
vk.py — VK-адаптер (vkbottle 4.x)

Запускает VK-бота с клавиатурой из 9 кнопок.
Команды обрабатываются так же, как в Web-виджете.
"""

import asyncio
import logging
import sys
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor
from vkbottle.tools.keyboard.action import Text
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.database import AdPrice

# Настройка логгера: выводим INFO и выше в stdout (попадает в docker logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s| %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("vk_adapter")
from app.handlers import (
    handle_auth, handle_profile, handle_search,
    handle_clear_chat, handle_settings, handle_stats, handle_channels,
    # Новые обработчики
    handle_admin_message, handle_ad_prices, handle_ad_submit,
    handle_news_suggest, handle_admin_panel,
    handle_admin_list_messages, handle_admin_view_message, handle_admin_respond,
    handle_my_requests, handle_get_chat,
)


# --------------------------------------------------
# Сохранение фото из VK-сообщения
# --------------------------------------------------

MAX_TEXT_LENGTH = 4000  # лимит VK на одно сообщение


async def _save_photo_from_vk(attachments: list) -> tuple[str | None, str | None]:
    """Скачивает самую большую фото из вложений VK и сохраняет в uploads/ad_images/.
    Возвращает (относительный_путь_для_БД, vk_attachment_строка_для_показа).
    Оба могут быть None если фото нет."""
    import os
    import uuid
    import httpx

    if not attachments:
        logger.info("_save_photo: no attachments")
        return None, None

    logger.info(f"_save_photo: {len(attachments)} attachments")
    for att in attachments:
        photo = getattr(att, "photo", None) if hasattr(att, "photo") else None
        if not photo:
            logger.info(f"_save_photo: att has no photo, type={type(att)}")
            continue

        # VK-строка вложения (для показа в превью без перезаливки)
        owner_id = getattr(photo, "owner_id", 0) or 0
        photo_id = getattr(photo, "id", 0) or 0
        access_key = getattr(photo, "access_key", "") or ""
        if owner_id and photo_id:
            vk_att_str = f"photo{owner_id}_{photo_id}"
            if access_key:
                vk_att_str += f"_{access_key}"
        else:
            vk_att_str = None
        logger.info(f"_save_photo: vk attachment string = {vk_att_str}")

        # Ищем самый большой размер
        sizes = getattr(photo, "sizes", None) or []
        logger.info(f"_save_photo: photo sizes={len(sizes)}")
        best_url = None
        best_w = 0
        for sz in sizes:
            w = getattr(sz, "width", 0) or 0
            u = getattr(sz, "url", None)
            if u and w > best_w:
                best_w = w
                best_url = u

        if not best_url:
            logger.info("_save_photo: no URL found in sizes")
            return None, vk_att_str  # файла нет, но VK-строка есть

        logger.info(f"_save_photo: best size={best_w}px url={best_url[:80]}...")

        # Определяем расширение
        ext = ".jpg"
        if ".png" in best_url:
            ext = ".png"
        elif ".gif" in best_url:
            ext = ".gif"
        elif ".webp" in best_url:
            ext = ".webp"

        filename = f"{uuid.uuid4().hex}{ext}"
        # Путь: app/adapters/vk.py → app/ → uploads/ad_images/
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "ad_images")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)

        # Скачиваем
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(best_url)
                content_type = resp.headers.get("content-type", "")
                logger.info(f"_save_photo: download status={resp.status_code} type={content_type[:50]}")
                if resp.status_code == 200 and "image" in content_type:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"_save_photo: SAVED → {filepath}")
                    return f"/static/ad_images/{filename}", vk_att_str
                else:
                    logger.info(f"_save_photo: bad response ({resp.status_code}) or not image ({content_type[:50]})")
        except Exception as e:
            logger.info(f"_save_photo: download ERROR: {e}")

    return None, None


# --------------------------------------------------
# Клавиатура (3×3 кнопок под чатом)
# --------------------------------------------------

def get_menu_keyboard(is_admin: bool = False) -> str:
    """Постоянное меню: 8 кнопок (3x3) для юзера, 6 кнопок (2x3) для админа"""
    keyboard = Keyboard(inline=False)

    if is_admin:
        # Админ: 2 ряда по 3 кнопки
        # Ряд 1: Поиск | Админка | Статистика
        keyboard.add(Text("Поиск"), color=KeyboardButtonColor.PRIMARY)
        keyboard.add(Text("Админка"), color=KeyboardButtonColor.PRIMARY)
        keyboard.add(Text("Статистика"), color=KeyboardButtonColor.SECONDARY)
        keyboard.row()

        # Ряд 2: Профиль | Настройки | Каналы
        keyboard.add(Text("Профиль"), color=KeyboardButtonColor.SECONDARY)
        keyboard.add(Text("Настройки"), color=KeyboardButtonColor.SECONDARY)
        keyboard.add(Text("Каналы"), color=KeyboardButtonColor.PRIMARY)
    else:
        # Обычный юзер: 3 ряда: 3 + 3 + 2 кнопки = 8
        # Ряд 1: Поиск | Профиль | Реклама
        keyboard.add(Text("Поиск"), color=KeyboardButtonColor.PRIMARY)
        keyboard.add(Text("Профиль"), color=KeyboardButtonColor.SECONDARY)
        keyboard.add(Text("Реклама"), color=KeyboardButtonColor.SECONDARY)
        keyboard.row()

        # Ряд 2: Новость | Админу | Настройки
        keyboard.add(Text("Новость"), color=KeyboardButtonColor.SECONDARY)
        keyboard.add(Text("Админу"), color=KeyboardButtonColor.SECONDARY)
        keyboard.add(Text("Настройки"), color=KeyboardButtonColor.SECONDARY)
        keyboard.row()

        # Ряд 3: Статистика | Каналы
        keyboard.add(Text("Статистика"), color=KeyboardButtonColor.SECONDARY)
        keyboard.add(Text("Каналы"), color=KeyboardButtonColor.PRIMARY)

    return keyboard.get_json()


def get_auth_keyboard() -> str:
    """Клавиатура для неавторизованного пользователя (2 кнопки)"""
    keyboard = Keyboard(inline=False)
    keyboard.add(Text("Войти"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Каналы"), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def get_chat_nav_keyboard() -> str:
    """Клавиатура для навигации по чату: ← назад, далее →, меню"""
    keyboard = Keyboard(inline=False)
    # Ряд 1: навигация
    keyboard.add(Text("← Назад"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Далее →"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    # Ряд 2: выход в меню
    keyboard.add(Text("↩ Меню"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


# --- Клавиатуры для шагов рекламы (цены из БД) ---

def get_ad_type_keyboard(prices: dict = None) -> str:
    """Выбор типа рекламы с актуальными ценами"""
    feed = int((prices or {}).get("feed_site", {}).get("base_price", 0))
    keyboard = Keyboard(inline=False)
    keyboard.add(Text(f"📢 Объявление (от {feed}₽)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("🎯 Баннер / Статья"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def get_banner_type_keyboard(prices: dict = None) -> str:
    """Баннер или статья — цены из БД"""
    p = prices or {}
    banner_min = int(p.get("banner_in_news", {}).get("base_price", 0))
    article_base = int(p.get("article_base", {}).get("base_price", 0))
    article_eternal = int(p.get("article_eternal", {}).get("base_price", 0))
    keyboard = Keyboard(inline=False)
    keyboard.add(Text(f"🖼 Баннер (от {banner_min}₽/мес)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text(f"📰 Статья (от {article_base}₽)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def get_banner_size_keyboard(prices: dict = None) -> str:
    """Размер баннера: 5 вариантов + минимальная цена"""
    p = prices or {}
    # Минимальная цена баннера (из двух вариантов размещения)
    banner_all = int(p.get("banner_all_pages", {}).get("base_price", 0))
    banner_news = int(p.get("banner_in_news", {}).get("base_price", 0))
    min_price = min(banner_all, banner_news) if banner_all and banner_news else (banner_news or banner_all or 3000)
    keyboard = Keyboard(inline=False)
    keyboard.add(Text(f"728×90 (от {min_price}₽/мес)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text(f"336×228 (от {min_price}₽/мес)"), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text(f"300×600 (от {min_price}₽/мес)"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text(f"300×250 (от {min_price}₽/мес)"), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text(f"468×60 (от {min_price}₽/мес)"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def get_banner_placement_keyboard(prices: dict = None) -> str:
    """Где показывать баннер — с ценами"""
    p = prices or {}
    all_pages = int(p.get("banner_all_pages", {}).get("base_price", 0))
    in_news = int(p.get("banner_in_news", {}).get("base_price", 0))
    keyboard = Keyboard(inline=False)
    keyboard.add(Text(f"🌐 Сквозное ({all_pages}₽/мес)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text(f"📰 В новостях ({in_news}₽/мес)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def get_article_options_keyboard(prices: dict = None) -> str:
    """Тип статьи — цены на кнопках"""
    p = prices or {}
    base = int(p.get("article_base", {}).get("base_price", 0))
    base_surch = p.get("article_base", {}).get("surcharge_pct", 0.3)
    eternal = int(p.get("article_eternal", {}).get("base_price", 0))
    eternal_surch = p.get("article_eternal", {}).get("surcharge_pct", 0.3)
    base_nr = round(base * (1 + base_surch))
    eternal_nr = round(eternal * (1 + eternal_surch))

    keyboard = Keyboard(inline=False)
    keyboard.add(Text(f"Обычная ({base}₽)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text(f"Обычная нерелев. ({base_nr}₽)"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text(f"Вечная ({eternal}₽)"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text(f"Вечная нерелев. ({eternal_nr}₽)"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def get_preview_keyboard() -> str:
    """Клавиатура предпросмотра: Отправить / Редактировать"""
    keyboard = Keyboard(inline=False)
    keyboard.add(Text("✅ Отправить"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("✏️ Редактировать"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def _get_pin_platforms_keyboard(current_platforms: set, available_keys: list = None) -> str:
    """
    Клавиатура для шага ad_pin_platforms.
    Показывает площадки с галочками (☑/☐) и кнопку «✅ Готово».
    current_platforms — set выбранных площадок (например {"site", "vk"}).
    available_keys — список площадок, которые показывать (те, что выбрал пользователь для публикации).
    Если None — показывает все 4 (старое поведение).
    """
    plat_labels = {"site": "Сайт", "tg": "Telegram", "vk": "VK", "max": "MAX"}
    if available_keys is None:
        available_keys = ["site", "tg", "vk", "max"]

    keyboard = Keyboard(inline=False)
    for key in available_keys:
        checked = "☑" if key in current_platforms else "☐"
        label = f"{checked} {plat_labels.get(key, key)}"
        keyboard.add(Text(label), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()
    keyboard.add(Text("✅ Готово"), color=KeyboardButtonColor.POSITIVE)
    keyboard.row()
    keyboard.add(Text("↩ Отмена"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


# --------------------------------------------------
# Хранилище состояний (FSM) — пока в памяти
# --------------------------------------------------

user_sessions = {}
# Формат: { "user_id": {"step": "...", "username": "...", "user_id": 1, ...} }


# --------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------

def _is_admin(session: dict) -> bool:
    """Проверка: админ ли текущий пользователь."""
    return session.get("user_id") == settings.ADMIN_USER_ID


def _status_label(status: str) -> str:
    """Перевод статуса на русский."""
    labels = {
        "new": "🆕 Новая",
        "in_progress": "⏳ На рассмотрении",
        "approved": "✅ Выполнена",
        "rejected": "❌ Отклонена",
        "done": "✅ Выполнена",
    }
    return labels.get(status, status)


def _format_chat_messages(messages: list, page: int = 1, per_page: int = 5) -> str:
    """Форматирует историю чата: сообщения с отступами + пагинация.

    Страница 1 = самые новые сообщения (конец переписки).
    «назад» = более старые, «далее» = более новые.
    """
    total = len(messages)
    if total == 0:
        return "📩 Пока сообщений нет. Напишите первый вопрос администратору!"

    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    # Режем массив: последняя страница = самые новые
    start = total - (page * per_page)
    end = total - ((page - 1) * per_page)
    if start < 0:
        start = 0
    page_msgs = messages[start:end]

    lines = []
    lines.append("━━━━━━━━━ 📩 ПЕРЕПИСКА С АДМИНОМ ━━━━━━━━━")
    lines.append("")

    for m in page_msgs:
        is_user = m.get("sender_type") == "user"
        who = "👤 Вы" if is_user else "👑 Админ"
        time_ago = m.get("time_ago", "")
        text = m.get("text", "")

        # Обрезаем длинные сообщения
        if len(text) > 250:
            text = text[:247] + "..."

        lines.append(f"  {who}  •  {time_ago}")

        if is_user:
            # Юзер — сдвиг влево
            lines.append(f"  ▸ {text}")
        else:
            # Админ — сдвиг вправо
            lines.append(f"       ▸ {text}")

        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📄 Страница {page} из {total_pages}")

    if total_pages > 1:
        nav = []
        if page < total_pages:
            nav.append('👉 «далее» — старее')
        if page > 1:
            nav.append('👈 «назад» — новее')
        lines.append("  |  ".join(nav))

    return "\n".join(lines)


def _get_kb_for_session(session: dict) -> str:
    """Возвращает клавиатуру с учётом роли пользователя."""
    if session.get("step") == "main":
        return get_menu_keyboard(is_admin=_is_admin(session))
    return get_menu_keyboard()


def _get_search_keyboard() -> str:
    """Клавиатура для навигации по результатам поиска."""
    kb = Keyboard(inline=False)
    kb.add(Text("👈 Назад"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("👉 Вперёд"), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("🚪 Выйти"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


# --------------------------------------------------
# Создаём VK-бота
# --------------------------------------------------

bot = Bot(token=settings.VK_BOT_TOKEN or "")


# --------------------------------------------------
# Загрузка цен из БД (общая с веб-админкой)
# --------------------------------------------------

async def _load_prices_from_db() -> dict:
    """
    Читает все цены из таблицы ad_prices.
    Возвращает словарь: {"feed_site": {"base_price": 500, ...}, ...}
    """
    async with async_session() as session:
        result = await session.execute(select(AdPrice).order_by(AdPrice.id))
        rows = result.scalars().all()
        prices = {}
        for row in rows:
            prices[row.price_key] = {
                "base_price": row.base_price,
                "surcharge_pct": row.surcharge_pct,
            }
        return prices


# ==================================================
# Обработчики команд
# ==================================================

@bot.on.message(text=["/start", "Начать", "Старт"])
async def start_handler(message: Message):
    """Приветствие при первом запуске"""
    uid = str(message.from_id)
    user_sessions[uid] = {"step": "start"}

    await message.answer(
        "👋 Приветствуем на turbinist.ru!\n\n"
        "Для доступа к функциям бота необходимо авторизоваться.\n\n"
        "Нажмите «Войти» и введите логин и пароль через запятую.\n"
        "Пример: turbinist_user, мой_пароль",
        keyboard=get_auth_keyboard(),
    )


@bot.on.message(text=["Войти"])
async def auth_start_handler(message: Message):
    """Начало авторизации"""
    uid = str(message.from_id)
    user_sessions[uid] = {"step": "waiting_login"}

    await message.answer(
        "Введите логин и пароль через запятую.\n"
        "Пример: turbinist_user, мой_пароль"
    )


@bot.on.message(text=["Каналы"])
async def channels_handler(message: Message):
    """Показать ссылки на каналы"""
    uid = str(message.from_id)
    session = user_sessions.get(uid, {})
    result = await handle_channels("vk", uid)
    kb = _get_kb_for_session(session)
    await message.answer(result, keyboard=kb)


# ==================================================
# Навигация по страницам поиска (отдельные обработчики)
# ==================================================

@bot.on.message(text=["Ещё", "ещё", "еще", "дальше", "next", "Next"])
async def search_next_handler(message: Message):
    """Следующая страница результатов поиска"""
    uid = str(message.from_id)
    session = user_sessions.get(uid, {})

    if session.get("step") != "search":
        await message.answer("Сначала выполните поиск.", keyboard=_get_kb_for_session(session))
        return

    query = session.get("search_query", "")
    page = session.get("search_page", 1) + 1

    if not query:
        await message.answer("Сначала выполните поиск.", keyboard=_get_kb_for_session(session))
        return

    result = await handle_search("vk", uid, query, page=page)
    user_sessions[uid] = {**session, "search_query": query, "search_page": page}
    await message.answer(result.text, keyboard=_get_kb_for_session(session))


@bot.on.message(text=["В начало", "в начало", "сначала", "first", "First"])
async def search_first_handler(message: Message):
    """Первая страница результатов поиска"""
    uid = str(message.from_id)
    session = user_sessions.get(uid, {})

    if session.get("step") != "search":
        await message.answer("Сначала выполните поиск.", keyboard=_get_kb_for_session(session))
        return

    query = session.get("search_query", "")
    page = 1

    if not query:
        await message.answer("Сначала выполните поиск.", keyboard=_get_kb_for_session(session))
        return

    result = await handle_search("vk", uid, query, page=page)
    user_sessions[uid] = {**session, "search_query": query, "search_page": page}
    await message.answer(result.text, keyboard=_get_kb_for_session(session))


# ==================================================
# Обработка любого текста
# ==================================================

# Список ключевых слов меню (для проверки: не перепутать кнопку с поиском)
MENU_KEYWORDS = [
    "профиль", "поиск", "очист", "настройк", "статистик",
    "каналы", "реклам", "новост", "админк", "админу", "отмена",
]


@bot.on.message()
async def message_handler(message: Message):
    """Обрабатывает любой текст от пользователя"""
    uid = str(message.from_id)
    text = message.text.strip()
    session = user_sessions.get(uid, {"step": "start"})
    peer_id = message.peer_id
    current_step = session.get("step", "start")

    # Отладка: логируем вложения
    atts = message.attachments
    if atts:
        logger.info(f"MSG_HANDLER uid={uid}: {len(atts)} attachments")
        for i, att in enumerate(atts):
            logger.info(f"  att[{i}]: type={att.type}, has_photo={att.photo is not None}")
    else:
        if any(kw in text for kw in ("📸", "фото", "картинк", "изображен")):
            logger.info(f"MSG_HANDLER uid={uid}: NO attachments but text suggests photo: '{text[:80]}'")
    # Конец отладки

    # --- Авторизация: ждём логин,пароль ---
    if session.get("step") == "waiting_login":
        if "," in text:
            parts = text.split(",", 1)
            login = parts[0].strip()
            password = parts[1].strip()

            await message.answer("⏳ Проверяю данные...")

            result = await handle_auth("vk", uid, login, password)

            if result.success:
                user_sessions[uid] = {
                    "step": "main",
                    "username": result.dle_username,
                    "group": result.dle_group_name,
                    "user_id": result.dle_user_id,
                }
                kb = get_menu_keyboard(is_admin=result.dle_user_id == settings.ADMIN_USER_ID)
                await message.answer(
                    f"✅ Авторизация успешна!\n"
                    f"Пользователь: {result.dle_username}\n"
                    f"Статус: {result.dle_group_name}",
                    keyboard=kb,
                )
            else:
                await message.answer(
                    f"❌ {result.message}\nПопробуйте ещё раз: логин, пароль"
                )
        else:
            await message.answer(
                "Нужно ввести логин и пароль через запятую.\n"
                "Пример: turbinist_user, мой_пароль"
            )
        return

    # ============================================================
    #  ВЫХОД ИЗ ЛЮБОГО РЕЖИМА: если нажали кнопку меню — сброс на главную
    #  Используется ТОЧНОЕ совпадение, чтобы не перехватить обычный текст
    # ============================================================
    BTN_EXIT = {
        "профиль", "поиск", "очистить", "отмена", "настройки",
        "статистика", "каналы", "реклама", "новость", "админка", "админу",
        "↩ отмена", "↩ меню",
    }
    if session.get("step") not in ("main", "waiting_login", "start"):
        if text.lower().strip() in BTN_EXIT:
            session = {k: v for k, v in session.items() if k != "step"}
            session["step"] = "main"
            session["ad_pin_platforms"] = None
            user_sessions[uid] = session
            # fall through — главное меню обработает команду

    # ============================================================
    #  ШАГИ С НОВЫМ ТЕКСТОМ (админ_ответ, сообщение админу, и т.д.)
    # ============================================================

    # --- Админ отвечает на обращение ---
    if session.get("step") == "admin_respond":
        msg_id = session.get("respond_to_msg_id", 0)
        result = await handle_admin_respond(
            "vk", uid, session.get("user_id", 0), msg_id, text,
        )
        user_sessions[uid] = {**session, "step": "main"}
        await message.answer(result, keyboard=get_menu_keyboard(is_admin=True))
        return

    # --- Сообщение админу (ввод текста, постоянный чат) ---
    if session.get("step") == "admin_message_text":
        dle_id = session.get("user_id", 0)
        user_name = session.get("username", "Гость")
        result = await handle_admin_message(
            "vk", uid, user_name, text,
            dle_user_id=dle_id,
        )
        user_sessions[uid] = {**session, "step": "main"}
        kb = _get_kb_for_session(session)
        await message.answer(
            f"✅ Сообщение отправлено!\n\n"
            "Напишите «Админу» чтобы продолжить переписку.",
            keyboard=kb,
        )
        return

    # --- Просмотр чата с пагинацией (редактируем одно сообщение) ---
    if session.get("step") == "chat_view":
        cmd = text.lower().strip()
        chat_msgs = session.get("chat_messages", [])
        chat_page = session.get("chat_page", 1)
        chat_cmid = session.get("chat_view_cmid")  # ID сообщения для редактирования
        total_pages = max(1, (len(chat_msgs) + 4) // 5)  # per_page = 5
        peer_id = message.peer_id

        # Навигация (кнопки или текст)
        if cmd in ("далее", "далее →", "вперёд", "next", ">"):
            if chat_page < total_pages:
                chat_page += 1
        elif cmd in ("назад", "← назад", "prev", "<"):
            if chat_page > 1:
                chat_page -= 1
        elif cmd in ("меню", "↩ меню"):
            # Удаляем сообщение с чатом, показываем главное меню
            user_sessions[uid] = {**session, "step": "main"}
            if chat_cmid:
                try:
                    await bot.api.messages.delete(
                        cmids=[chat_cmid],
                        peer_id=peer_id,
                        delete_for_all=True,
                    )
                except Exception:
                    pass
            await message.answer(
                "📋 Главное меню:",
                keyboard=_get_kb_for_session(session),
            )
            return
        else:
            # Отправляем текст админу, удаляем чат-вью, показываем подтверждение
            dle_id = session.get("user_id", 0)
            user_name = session.get("username", "Гость")
            result = await handle_admin_message(
                "vk", uid, user_name, text,
                dle_user_id=dle_id,
            )
            user_sessions[uid] = {**session, "step": "main"}
            if chat_cmid:
                try:
                    await bot.api.messages.delete(
                        cmids=[chat_cmid],
                        peer_id=peer_id,
                        delete_for_all=True,
                    )
                except Exception:
                    pass
            kb = _get_kb_for_session(session)
            await message.answer(
                f"✅ Сообщение отправлено!\n\n"
                "Напишите «Админу» чтобы продолжить переписку.",
                keyboard=kb,
            )
            return

        # Обновляем СУЩЕСТВУЮЩЕЕ сообщение (edit, не новое!)
        user_sessions[uid] = {**session, "chat_page": chat_page}
        formatted = _format_chat_messages(chat_msgs, chat_page)
        new_text = formatted + "\n\n✏️ Напишите сообщение или используйте кнопки:"
        if chat_cmid:
            try:
                await bot.api.messages.edit(
                    peer_id=peer_id,
                    cmid=chat_cmid,
                    message=new_text,
                    keyboard=get_chat_nav_keyboard(),
                )
            except Exception:
                # Если edit не сработал — шлём новое
                result = await message.answer(new_text, keyboard=get_chat_nav_keyboard())
                if result:
                    user_sessions[uid]["chat_view_cmid"] = result[0].conversation_message_id
        else:
            # Первый показ — отправляем и запоминаем ID
            result = await message.answer(new_text, keyboard=get_chat_nav_keyboard())
            if result:
                user_sessions[uid]["chat_view_cmid"] = result[0].conversation_message_id
        return

    # --- Предложить новость: ввод заголовка ---
    if session.get("step") == "news_title":
        user_sessions[uid] = {**session, "step": "news_text", "news_title": text}
        await message.answer("📝 Напишите текст новости:\n📸 Можно прикрепить картинку (отправьте фото вместе с текстом)")
        return

    # --- Предложить новость: ввод текста ---
    if session.get("step") == "news_text":
        # Проверка длины
        if len(text) > MAX_TEXT_LENGTH:
            await message.answer(
                f"⚠️ Текст слишком длинный ({len(text)} символов, максимум {MAX_TEXT_LENGTH}).\n\n"
                "Вы можете:\n"
                "• Сократить текст\n"
                "• Прикрепить файл (отправьте документом)\n"
                "• Скинуть ссылку на текст (Google Docs, Яндекс.Диск и т.п.)"
            )
            return

        # Картинка (новая — если прислали, иначе — старая из сессии)
        new_image, new_vk_att = await _save_photo_from_vk(message.attachments)
        old_image = session.get("news_image_path")
        old_vk_att = session.get("news_vk_attachment")
        image_path = new_image if new_image else old_image
        vk_attachment = new_vk_att if new_image else old_vk_att
        title = session.get("news_title", "Без названия")

        user_sessions[uid] = {
            **session, "step": "news_preview",
            "news_text": text, "news_image_path": image_path,
            "news_vk_attachment": vk_attachment,
        }

        # Предпросмотр
        preview = text if len(text) <= 3500 else text[:3500] + "\n\n... (текст обрезан для предпросмотра)"

        await message.answer(
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⬥ ПРЕДПРОСМОТР НОВОСТИ\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📰 {title.upper()}\n"
            f"{preview}\n\n"
            f"✅ Всё верно?",
            keyboard=get_preview_keyboard(),
            attachment=vk_attachment,
        )
        return

    # --- Предпросмотр новости (отправить / редактировать) ---
    if session.get("step") == "news_preview":
        choice = text.strip().lower()
        title = session.get("news_title", "Без названия")
        news_text = session.get("news_text", "")
        image_path = session.get("news_image_path")

        if "отправить" in choice:
            result = await handle_news_suggest(
                "vk", uid, title, news_text,
                dle_user_id=session.get("user_id"),
                user_name=session.get("username"),
                image_path=image_path,
            )
            user_sessions[uid] = {**session, "step": "main"}
            kb = _get_kb_for_session(session)
            await message.answer(result, keyboard=kb)
        elif "редактировать" in choice:
            # Сохраняем картинку и VK-вложение при редактировании
            img_text = "📸 Картинка сохранена (пришлите новую чтобы заменить)" if image_path else "📸 Можно прикрепить картинку (отправьте фото вместе с текстом)"
            user_sessions[uid] = {
                **session, "step": "news_text", "news_title": title,
                "news_image_path": image_path,
                "news_vk_attachment": session.get("news_vk_attachment"),
            }
            await message.answer(f"📝 Напишите текст новости заново:\n{img_text}")
        else:
            await message.answer("Выберите действие:", keyboard=get_preview_keyboard())
        return

    # --- Реклама: выбор типа (кнопки с ценами или цифры) ---
    if session.get("step") == "ad_type":
        prices = await _load_prices_from_db()
        choice = text.strip().lower()
        # Кнопки содержат цены: «📢 Объявление (от 800₽)» — ищем по ключевым словам
        if choice in ("1",) or "объявление" in choice:
            user_sessions[uid] = {**session, "step": "ad_text", "ad_calc_flow": "feed"}
            await message.answer("📢 ОБЪЯВЛЕНИЕ В ЛЕНТЕ\n\n📝 Напишите текст объявления:\n📸 Можно прикрепить картинку (отправьте фото вместе с текстом)")
        elif choice in ("2",) or "баннер" in choice or "статья" in choice:
            user_sessions[uid] = {**session, "step": "banner_type"}
            await message.answer(
                "🎯 БАННЕР ИЛИ СТАТЬЯ",
                keyboard=get_banner_type_keyboard(prices),
            )
        else:
            await message.answer(
                "Выберите тип рекламы:",
                keyboard=get_ad_type_keyboard(prices),
            )
        return

    # --- Реклама: выбор баннер/статья (кнопки с ценами) ---
    if session.get("step") == "banner_type":
        prices = await _load_prices_from_db()
        choice = text.strip().lower()
        if choice in ("1",) or "баннер" in choice:
            user_sessions[uid] = {**session, "step": "banner_size", "ad_calc_flow": "banner"}
            await message.answer(
                "🖼 БАННЕР\n\nВыберите размер:",
                keyboard=get_banner_size_keyboard(prices),
            )
        elif choice in ("2",) or "статья" in choice:
            user_sessions[uid] = {**session, "step": "article_options", "ad_calc_flow": "article"}
            await message.answer(
                f"📰 СТАТЬЯ\n\nВыберите тип:",
                keyboard=get_article_options_keyboard(prices),
            )
        else:
            await message.answer(
                "🖼 Баннер или 📰 Статья?",
                keyboard=get_banner_type_keyboard(prices),
            )
        return

    # --- Реклама: ввод текста объявления ---
    if session.get("step") == "ad_text":
        # Картинка (новая — если прислали, иначе — старая из сессии)
        new_image, new_vk_att = await _save_photo_from_vk(message.attachments)
        old_image = session.get("ad_image_path")
        old_vk_att = session.get("ad_vk_attachment")
        image_path = new_image if new_image else old_image
        vk_attachment = new_vk_att if new_image else old_vk_att
        user_sessions[uid] = {
            **session, "step": "ad_platforms", "ad_text": text,
            "ad_image_path": image_path,
            "ad_vk_attachment": vk_attachment,
        }
        prices = await _load_prices_from_db()
        sp = int(prices.get("feed_site", {}).get("base_price", 0))
        await message.answer(
            f"🌍 ВЫБОР ПЛОЩАДОК (по {sp}₽/день каждая):\n\n"
            f"• сайт — {sp}₽/день\n"
            f"• tg — {sp}₽/день\n"
            f"• vk — {sp}₽/день\n"
            f"• max — {sp}₽/день\n"
            f"• все — {sp * 4}₽/день (все 4)\n\n"
            "Введите через запятую (например: сайт, tg, vk)\n"
            "Или одно слово: все"
        )
        return

    # --- Реклама: выбор площадок (текст, можно через запятую) ---
    if session.get("step") == "ad_platforms":
        raw = text.lower().strip()
        # Карта переводов: русский → английский
        name_map = {
            "сайт": "site", "site": "site",
            "tg": "tg", "telegram": "tg", "телеграм": "tg",
            "vk": "vk", "вк": "vk",
            "max": "max", "макс": "max",
            "все": "all", "all": "all",
        }
        # Если одно слово — проверяем прямо
        if raw in ("все", "all"):
            platforms_en = "all"
        else:
            # Разбиваем по запятой и переводим каждую площадку
            parts = [p.strip() for p in raw.replace(",", " ").split()]
            translated = []
            for p in parts:
                eng = name_map.get(p, p)
                if eng in ("site", "tg", "vk", "max"):
                    translated.append(eng)
            if not translated:
                await message.answer(
                    "Не понял площадки. Введите через запятую:\n"
                    "сайт, tg, vk, max\n"
                    "Или «все» для всех."
                )
                return
            platforms_en = ",".join(translated)

        user_sessions[uid] = {**session, "step": "ad_days", "ad_platforms": platforms_en}
        await message.answer("На сколько дней разместить рекламу?\nВведите число (1, 2, 3...):")
        return

    # --- Реклама: ввод дней ---
    if session.get("step") == "ad_days":
        try:
            days = int(text)
            if days < 1:
                raise ValueError
        except ValueError:
            await message.answer("Введите целое число дней (например: 3):")
            return

        user_sessions[uid] = {**session, "step": "ad_pin", "ad_days": days}
        await message.answer(
            "📌 ЗАКРЕПЛЕНИЕ ОБЪЯВЛЕНИЯ\n\n"
            "На сколько дней закрепить?\n"
            "Введите число (например: 1, 2, 5)\n"
            "Или 0 — без закрепления:"
        )
        return

    # --- Реклама: закрепление ---
    if session.get("step") == "ad_pin":
        try:
            pin_days = int(text)
            if pin_days < 0:
                raise ValueError
        except ValueError:
            await message.answer("Введите целое число. Например: 0 (без закрепления), 2, 5.")
            return

        platforms = session.get("ad_platforms", "all")

        # Если закрепление нужно И площадок > 1 → выбор на каких площадках закрепить
        if pin_days > 0:
            plat_keys = ["site", "tg", "vk", "max"]
            plat_list = platforms.split(",") if platforms != "all" else plat_keys
            if len(plat_list) > 1:
                user_sessions[uid] = {
                    **session, "step": "ad_pin_platforms",
                    "ad_pin_days": pin_days,
                    "ad_pin_platforms": None,  # None = все площадки (потом уточнит)
                }
                keyboard = _get_pin_platforms_keyboard(set(), plat_list)
                await message.answer(
                    "📌 На каких площадках закрепить объявление?\n\n"
                    "Нажмите на площадку чтобы выбрать ☐→☑.\n"
                    "Пока ничего не выбрано (будет закреплено на всех площадках)\n"
                    "Нажмите «✅ Готово» когда закончите.",
                    keyboard=keyboard,
                )
                return

        # Без закрепления или 1 площадка → сразу в превью
        ad_text = session.get("ad_text", "")
        days_val = session.get("ad_days", 1)
        ad_image_path = session.get("ad_image_path")
        vk_attachment = session.get("ad_vk_attachment")

        # Загружаем цены из БД
        prices = await _load_prices_from_db()

        # Считаем цену (pin_platforms=None = все площадки)
        total_price = _calc_ad_price(platforms, days_val, pin_days, prices, None)

        user_sessions[uid] = {
            **session, "step": "ad_preview",
            "ad_pin_days": pin_days, "ad_total_price": total_price,
        }

        # Предпросмотр
        platform_labels = {"site": "Сайт", "tg": "Telegram", "vk": "VK", "max": "MAX"}
        plat_list = platforms.split(",") if platforms != "all" else ["сайт", "tg", "vk", "max"]
        plat_names = ", ".join(platform_labels.get(p, p) for p in plat_list)
        preview = ad_text if len(ad_text) <= 2000 else ad_text[:2000] + "\n..."

        pin_info = f"да ({pin_days} дн.)" if pin_days > 0 else "нет"
        await message.answer(
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⬥ ПРЕДПРОСМОТР ОБЪЯВЛЕНИЯ\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📝 {preview}\n\n"
            f"📍 Площадки: {plat_names}\n"
            f"📅 Дней: {days_val}\n"
            f"📌 Закрепление: {pin_info}\n\n"
            f"━━ 💰 {total_price} ₽ ━━\n\n"
            f"✅ Всё верно?",
            keyboard=get_preview_keyboard(),
            attachment=vk_attachment,
        )
        return

    # --- Реклама: выбор площадок закрепления ---
    if session.get("step") == "ad_pin_platforms":
        choice = text.strip().lower()
        platforms = session.get("ad_platforms", "all")
        plat_labels = {"site": "Сайт", "tg": "Telegram", "vk": "VK", "max": "MAX"}
        all_plat_keys = ["site", "tg", "vk", "max"]
        plat_list = platforms.split(",") if platforms != "all" else all_plat_keys

        # Текущие выбранные (None = ещё не выбирал)
        current_raw = session.get("ad_pin_platforms")
        if current_raw is None:
            current = set()  # по умолчанию — ничего (Готово = все площадки)
        else:
            current = set(p.strip() for p in current_raw.split(",") if p.strip())

        if "готово" in choice or choice == "готово":
            # Сохраняем и переходим к расчёту + превью
            pin_platforms_str = ",".join(sorted(current)) if current else None
            pin_days = session.get("ad_pin_days", 0)
            ad_text = session.get("ad_text", "")
            days_val = session.get("ad_days", 1)
            ad_image_path = session.get("ad_image_path")
            vk_attachment = session.get("ad_vk_attachment")

            prices = await _load_prices_from_db()
            total_price = _calc_ad_price(platforms, days_val, pin_days, prices, pin_platforms_str)

            pin_label = ", ".join(plat_labels.get(p, p) for p in (current if current else ["все"]))

            user_sessions[uid] = {
                **session, "step": "ad_preview",
                "ad_total_price": total_price,
                "ad_pin_platforms": pin_platforms_str,
            }

            plat_names = ", ".join(plat_labels.get(p, p) for p in plat_list)
            preview = ad_text if len(ad_text) <= 2000 else ad_text[:2000] + "\n..."

            pin_info = f"да ({pin_days} дн.) на [{pin_label}]" if pin_days > 0 else "нет"
            await message.answer(
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"⬥ ПРЕДПРОСМОТР ОБЪЯВЛЕНИЯ\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📝 {preview}\n\n"
                f"📍 Площадки: {plat_names}\n"
                f"📅 Дней: {days_val}\n"
                f"📌 Закрепление: {pin_info}\n\n"
                f"━━ 💰 {total_price} ₽ ━━\n\n"
                f"✅ Всё верно?",
                keyboard=get_preview_keyboard(),
                attachment=vk_attachment,
            )
            return

        # Проверяем — нажата ли кнопка площадки
        matched_key = None
        for key in plat_list:
            if choice in key or plat_labels.get(key, "").lower() in choice or key in choice:
                matched_key = key
                break

        if matched_key:
            if matched_key in current:
                current.discard(matched_key)
            else:
                current.add(matched_key)

            pin_platforms_str = ",".join(sorted(current)) if current else None
            user_sessions[uid] = {**session, "ad_pin_platforms": pin_platforms_str}

            # Формируем сообщение с текущим выбором
            if current:
                selected_names = ", ".join(plat_labels.get(p, p) for p in current)
                count_text = f"📌 Выбрано площадок для закрепления: {len(current)}\n👉 {selected_names}"
            else:
                count_text = "📌 Пока ничего не выбрано (будет на всех площадках)"
            keyboard = _get_pin_platforms_keyboard(current, plat_list)
            await message.answer(
                f"{count_text}\n\n"
                "Нажмите на площадку чтобы изменить.\n"
                "Нажмите «✅ Готово» когда закончите.",
                keyboard=keyboard,
            )
            return

        # Непонятный ввод — показываем клавиатуру снова
        if current:
            current_names = ", ".join(plat_labels.get(p, p) for p in current)
        else:
            current_names = "пока ничего (будет на всех площадках)"
        await message.answer(
            f"📌 Выбрано: {current_names}\n\n"
            "Используйте кнопки ниже для выбора.\n"
            "Нажмите «✅ Готово» когда закончите.",
            keyboard=_get_pin_platforms_keyboard(current, plat_list),
        )

    # --- Предпросмотр объявления (отправить / редактировать) ---
    if session.get("step") == "ad_preview":
        choice = text.strip().lower()
        ad_image_path = session.get("ad_image_path")
        if "отправить" in choice:
            ad_text = session.get("ad_text", "")
            platforms = session.get("ad_platforms", "all")
            days_val = session.get("ad_days", 1)
            pin_days = session.get("ad_pin_days", 0)
            total_price = session.get("ad_total_price", 0)

            result = await handle_ad_submit(
                "vk", uid, ad_text, platforms, days_val, pin_days > 0, total_price,
                pin_days=pin_days, image_path=ad_image_path,
                pin_platforms=session.get("ad_pin_platforms"),
                dle_user_id=session.get("user_id"),
                user_name=session.get("username"),
            )
            user_sessions[uid] = {**session, "step": "main"}
            kb = _get_kb_for_session(session)
            await message.answer(result, keyboard=kb)
        elif "редактировать" in choice:
            # Сохраняем картинку и VK-вложение при редактировании
            img_text = "📸 Картинка сохранена (пришлите новую чтобы заменить)" if ad_image_path else "📸 Можно прикрепить картинку (отправьте фото вместе с текстом)"
            user_sessions[uid] = {
                **session, "step": "ad_text", "ad_calc_flow": "feed",
                "ad_image_path": ad_image_path,
                "ad_vk_attachment": session.get("ad_vk_attachment"),
            }
            await message.answer(f"📝 Напишите текст объявления заново:\n{img_text}")
        else:
            await message.answer("Выберите действие:", keyboard=get_preview_keyboard())
        return

    # --- Баннер: выбор размера (кнопки) ---
    if session.get("step") == "banner_size":
        # Ищем размер в тексте кнопки (кнопки содержат цены: «728×90 (от 3000₽/мес)»)
        txt = text.strip()
        size = None
        for s in ("728×90", "336×228", "300×600", "300×250", "468×60"):
            if s in txt:
                size = s
                break
        if not size:
            prices = await _load_prices_from_db()
            await message.answer("Выберите размер кнопкой:", keyboard=get_banner_size_keyboard(prices))
            return
        prices = await _load_prices_from_db()
        user_sessions[uid] = {**session, "step": "banner_placement", "banner_size": size}
        await message.answer(
            f"Размер: {size}\n\nГде показывать?",
            keyboard=get_banner_placement_keyboard(prices),
        )
        return

    # --- Баннер: размещение (кнопки с ценами) ---
    if session.get("step") == "banner_placement":
        prices = await _load_prices_from_db()
        choice = text.strip().lower()
        if choice in ("1",) or "сквозное" in choice:
            placement = "all_pages"
            label = "Сквозное (все страницы)"
        elif choice in ("2",) or "в новостях" in choice:
            placement = "in_news"
            label = "В указанных новостях"
        else:
            await message.answer("Где показывать баннер?", keyboard=get_banner_placement_keyboard(prices))
            return
        user_sessions[uid] = {**session, "step": "banner_options", "banner_placement": placement}
        await message.answer(
            f"Размещение: {label}\n\n"
            "Доп. опции (+30% каждая):\n"
            "1️⃣ Главная страница\n"
            "2️⃣ Нерелевантная тематика\n"
            "3️⃣ Индивидуальные пожелания\n\n"
            "Введите номера через запятую (1,3) или 0:"
        )
        return

    # --- Баннер: опции ---
    if session.get("step") == "banner_options":
        nums = [n.strip() for n in text.replace(" ", "").split(",")]
        opt1 = "1" in nums
        opt2 = "2" in nums
        opt3 = "3" in nums
        user_sessions[uid] = {
            **session, "step": "banner_months",
            "banner_opt_home": opt1,
            "banner_opt_not_relevant": opt2,
            "banner_opt_custom": opt3,
        }
        opts = []
        if opt1: opts.append("Главная")
        if opt2: opts.append("Нерелевантная")
        if opt3: opts.append("Пожелания")
        opt_text = ", ".join(opts) if opts else "Без опций"
        await message.answer(
            f"Опции: {opt_text}\n\n"
            "На сколько месяцев разместить баннер?\n"
            "Введите число (1, 2, 3...):"
        )
        return

    # --- Баннер: месяцы + расчёт ---
    if session.get("step") == "banner_months":
        try:
            months = int(text)
            if months < 1:
                raise ValueError
        except ValueError:
            await message.answer("Введите целое число месяцев (например: 1, 3, 6):")
            return

        prices = await _load_prices_from_db()
        placement = session.get("banner_placement", "in_news")
        base_key = "banner_all_pages" if placement == "all_pages" else "banner_in_news"
        base = int(prices.get(base_key, {}).get("base_price", 0))
        # Берём наценку за нерелевантность из БД (surcharge_pct)
        nr_surcharge = prices.get(base_key, {}).get("surcharge_pct", 0.3)

        surcharge = 1.0
        if session.get("banner_opt_home"): surcharge += 0.3
        if session.get("banner_opt_not_relevant"): surcharge += nr_surcharge
        if session.get("banner_opt_custom"): surcharge += 0.3

        total = round(base * surcharge * months)

        user_sessions[uid] = {
            **session, "step": "banner_text",
            "banner_months": months, "banner_calc_price": total,
        }
        await message.answer(
            f"💰 Расчёт:\n"
            f"База: {base}₽/мес × {months} мес."
            f"{' × ' + str(surcharge) + ' (надбавки)' if surcharge > 1 else ''}\n"
            f"Итого: {total}₽\n\n"
            "📝 Опишите ваш баннер (содержание, ссылка):\n"
            "📸 Можно прикрепить картинку баннера (отправьте фото вместе с текстом)"
        )
        return

    # --- Баннер: текст + предпросмотр ---
    if session.get("step") == "banner_text":
        # Картинка (новая — если прислали, иначе — старая из сессии)
        new_image, new_vk_att = await _save_photo_from_vk(message.attachments)
        old_image = session.get("banner_image_path")
        old_vk_att = session.get("banner_vk_attachment")
        image_path = new_image if new_image else old_image
        vk_attachment = new_vk_att if new_image else old_vk_att

        banner_size = session.get("banner_size", "728x90")
        banner_months = session.get("banner_months", 1)
        total = session.get("banner_calc_price", 0)
        placement = session.get("banner_placement", "in_news")
        placement_label = "сквозное" if placement == "all_pages" else "в новостях"

        user_sessions[uid] = {
            **session, "step": "banner_preview",
            "banner_text": text, "banner_image_path": image_path,
            "banner_vk_attachment": vk_attachment,
        }

        # Предпросмотр
        preview = text if len(text) <= 2000 else text[:2000] + "\n..."

        await message.answer(
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⬥ ПРЕДПРОСМОТР БАННЕРА\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📐 Размер: {banner_size}\n"
            f"📍 Размещение: {placement_label}\n"
            f"📅 Срок: {banner_months} мес.\n"
            f"📝 {preview}\n\n"
            f"━━ 💰 {total} ₽ ━━\n\n"
            f"✅ Всё верно?",
            keyboard=get_preview_keyboard(),
            attachment=vk_attachment,
        )
        return

    # --- Предпросмотр баннера (отправить / редактировать) ---
    if session.get("step") == "banner_preview":
        choice = text.strip().lower()
        image_path = session.get("banner_image_path")
        if "отправить" in choice:
            banner_text = session.get("banner_text", "")
            banner_size = session.get("banner_size", "728x90")
            banner_months = session.get("banner_months", 1)
            total = session.get("banner_calc_price", 0)
            placement = session.get("banner_placement", "in_news")
            placement_label = "сквозное" if placement == "all_pages" else "в новостях"

            full_text = (
                f"[БАННЕР {banner_size}] "
                f"Размещение: {placement_label}, {banner_months} мес.\n"
                f"Описание: {banner_text}"
            )

            # Собираем опции баннера из флагов
            banner_opts_parts = []
            if session.get("banner_opt_home"): banner_opts_parts.append("home")
            if session.get("banner_opt_not_relevant"): banner_opts_parts.append("not_relevant")
            if session.get("banner_opt_custom"): banner_opts_parts.append("custom")
            banner_opts = ",".join(banner_opts_parts) or None
            result = await handle_ad_submit(
                "vk", uid, full_text, "site", banner_months, False, total,
                ad_type="banner", image_path=image_path,
                dle_user_id=session.get("user_id"),
                user_name=session.get("username"),
                banner_size=banner_size,
                banner_placement=placement,
                banner_months=banner_months,
                banner_opts=banner_opts,
            )
            user_sessions[uid] = {**session, "step": "main"}
            kb = _get_kb_for_session(session)
            await message.answer(result, keyboard=kb)
        elif "редактировать" in choice:
            # Сохраняем картинку и VK-вложение при редактировании
            img_text = "📸 Картинка сохранена (пришлите новую чтобы заменить)" if image_path else "📸 Можно прикрепить картинку баннера (отправьте фото вместе с текстом)"
            user_sessions[uid] = {
                **session, "step": "banner_text", "ad_calc_flow": "banner",
                "banner_image_path": image_path,
                "banner_vk_attachment": session.get("banner_vk_attachment"),
            }
            await message.answer(f"📝 Опишите баннер заново:\n{img_text}")
        else:
            await message.answer("Выберите действие:", keyboard=get_preview_keyboard())
        return

    # --- Статья: выбор опций (кнопки с ценами) ---
    if session.get("step") == "article_options":
        choice = text.strip().lower()
        prices = await _load_prices_from_db()
        article_base = int(prices.get("article_base", {}).get("base_price", 0))
        article_eternal = int(prices.get("article_eternal", {}).get("base_price", 0))
        article_base_surcharge = prices.get("article_base", {}).get("surcharge_pct", 0.3)
        article_eternal_surcharge = prices.get("article_eternal", {}).get("surcharge_pct", 0.3)
        fix_per_day = int(prices.get("article_fixation", {}).get("base_price", 0))

        # Кнопки содержат цены: «Обычная (2950₽)» — ищем по ключевым словам
        is_eternal = "вечная" in choice
        is_nr = "нерелев" in choice

        if choice in ("1", "2", "3", "4"):  # цифры для совместимости
            if choice == "1":
                eternal, not_relevant = False, False
            elif choice == "2":
                eternal, not_relevant = False, True
            elif choice == "3":
                eternal, not_relevant = True, False
            elif choice == "4":
                eternal, not_relevant = True, True
        elif "обычная" in choice or "вечная" in choice:
            eternal, not_relevant = is_eternal, is_nr
        else:
            await message.answer("Выберите тип статьи:", keyboard=get_article_options_keyboard(prices))
            return

        if eternal:
            price = round(article_eternal * (1 + article_eternal_surcharge)) if not_relevant else article_eternal
            user_sessions[uid] = {
                **session, "step": "article_text",
                "article_eternal": True, "article_not_relevant": not_relevant,
                "article_calc_price": price, "article_fix_days": 0,
            }
            await message.answer(
                f"📰 СТАТЬЯ ВЕЧНАЯ{' (нерелевантная)' if not_relevant else ''}\n"
                f"💰 Цена: {price}₽\n\n"
                "📝 Опишите вашу статью (тема, содержание, ссылки):\n📸 Можно прикрепить картинку (отправьте фото вместе с текстом)"
            )
        else:
            price = round(article_base * (1 + article_base_surcharge)) if not_relevant else article_base
            user_sessions[uid] = {
                **session, "step": "article_fixation",
                "article_eternal": False, "article_not_relevant": not_relevant,
                "article_calc_price": price,
            }
            await message.answer(
                f"📌 Фиксация в ленте — {fix_per_day}₽/день\n\n"
                "На сколько дней зафиксировать?\n"
                "Введите число (0 — без фиксации):"
            )
        return

    # --- Статья: фиксация ---
    if session.get("step") == "article_fixation":
        try:
            fix_days = int(text)
            if fix_days < 0:
                raise ValueError
        except ValueError:
            await message.answer("Введите целое число (0 — без фиксации):")
            return

        prices = await _load_prices_from_db()
        fix_per_day = int(prices.get("article_fixation", {}).get("base_price", 0))
        price = session.get("article_calc_price", 0)

        if fix_days > 0:
            price += fix_days * fix_per_day

        user_sessions[uid] = {
            **session, "step": "article_text",
            "article_fix_days": fix_days, "article_calc_price": price,
        }
        await message.answer(
            f"{'Фиксация: ' + str(fix_days) + ' дн.' if fix_days > 0 else 'Без фиксации'}\n"
            f"💰 Итого: {price}₽\n\n"
            "📝 Опишите вашу статью (тема, содержание, ссылки):\n📸 Можно прикрепить картинку (отправьте фото вместе с текстом)"
        )
        return

    # --- Статья: текст + предпросмотр ---
    if session.get("step") == "article_text":
        # Проверка длины
        if len(text) > MAX_TEXT_LENGTH:
            await message.answer(
                f"⚠️ Текст слишком длинный ({len(text)} символов, максимум {MAX_TEXT_LENGTH}).\n\n"
                "Вы можете:\n"
                "• Сократить текст\n"
                "• Прикрепить файл (отправьте документом)\n"
                "• Скинуть ссылку на текст (Google Docs, Яндекс.Диск и т.п.)"
            )
            return

        # Картинка (новая — если прислали, иначе — старая из сессии)
        new_image, new_vk_att = await _save_photo_from_vk(message.attachments)
        old_image = session.get("article_image_path")
        old_vk_att = session.get("article_vk_attachment")
        image_path = new_image if new_image else old_image
        vk_attachment = new_vk_att if new_image else old_vk_att

        eternal = session.get("article_eternal", False)
        not_relevant = session.get("article_not_relevant", False)
        fix_days = session.get("article_fix_days", 0)
        total = session.get("article_calc_price", 0)

        user_sessions[uid] = {
            **session, "step": "article_preview",
            "article_text": text, "article_image_path": image_path,
            "article_vk_attachment": vk_attachment,
        }

        # Предпросмотр
        opts = []
        if not_relevant: opts.append("нерелевантная")
        if eternal: opts.append("вечная")
        if fix_days > 0: opts.append(f"фиксация {fix_days}дн.")
        preview = text if len(text) <= 3000 else text[:3000] + "\n..."

        type_label = "Вечная" if eternal else "Обычная"
        if not_relevant:
            type_label += " (нерелевантная)"
        opts_str = ", ".join(opts) if opts else "базовая"
        await message.answer(
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⬥ ПРЕДПРОСМОТР СТАТЬИ\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📰 Тип: {type_label}\n"
            f"🔧 Опции: {opts_str}\n"
            f"📝 {preview}\n\n"
            f"━━ 💰 {total} ₽ ━━\n\n"
            f"✅ Всё верно?",
            keyboard=get_preview_keyboard(),
            attachment=vk_attachment,
        )
        return

    # --- Предпросмотр статьи (отправить / редактировать) ---
    if session.get("step") == "article_preview":
        choice = text.strip().lower()
        image_path = session.get("article_image_path")
        if "отправить" in choice:
            article_text = session.get("article_text", "")
            eternal = session.get("article_eternal", False)
            not_relevant = session.get("article_not_relevant", False)
            fix_days = session.get("article_fix_days", 0)
            total = session.get("article_calc_price", 0)

            opts = []
            if not_relevant: opts.append("нерелевантная")
            if eternal: opts.append("вечная")
            if fix_days > 0: opts.append(f"фиксация {fix_days}дн.")
            full_text = (
                f"[СТАТЬЯ{' ВЕЧНАЯ' if eternal else ''}] "
                f"Опции: {', '.join(opts) if opts else 'базовая'}\n"
                f"Текст: {article_text}"
            )

            # Собираем опции статьи из флагов
            article_opts_parts = []
            if not_relevant: article_opts_parts.append("not_relevant")
            if fix_days > 0: article_opts_parts.append("fixation")
            article_opts = ",".join(article_opts_parts) or None
            result = await handle_ad_submit(
                "vk", uid, full_text, "site", 0, False, total,
                ad_type="article", article_eternal=eternal,
                article_opts=article_opts,
                article_fix_days=fix_days,
                image_path=image_path,
                dle_user_id=session.get("user_id"),
                user_name=session.get("username"),
            )
            user_sessions[uid] = {**session, "step": "main"}
            kb = _get_kb_for_session(session)
            await message.answer(result, keyboard=kb)
        elif "редактировать" in choice:
            # Сохраняем картинку и VK-вложение при редактировании
            img_text = "📸 Картинка сохранена (пришлите новую чтобы заменить)" if image_path else "📸 Можно прикрепить картинку (отправьте фото вместе с текстом)"
            user_sessions[uid] = {
                **session, "step": "article_text", "ad_calc_flow": "article",
                "article_image_path": image_path,
                "article_vk_attachment": session.get("article_vk_attachment"),
            }
            await message.answer(f"📝 Опишите статью заново:\n{img_text}")
        else:
            await message.answer("Выберите действие:", keyboard=get_preview_keyboard())
        return

    # --- Админка: ввод номера обращения ---
    if session.get("step") == "admin_view_message":
        cmd = text.lower().strip()
        if cmd.startswith("взять") or cmd.startswith("#"):
            try:
                msg_id = int(cmd.replace("взять", "").replace("#", "").strip())
            except ValueError:
                await message.answer("Напишите «взять #» с номером (например: «взять 5»).")
                return
            result = await handle_admin_view_message(
                "vk", uid, session.get("user_id", 0), msg_id,
            )
            user_sessions[uid] = {**session, "step": "main"}
            await message.answer(result, keyboard=get_menu_keyboard(is_admin=True))
            return

        if cmd in ("меню", "назад"):
            user_sessions[uid] = {**session, "step": "main"}
            await message.answer("📋 Главное меню:", keyboard=get_menu_keyboard(is_admin=True))
            return

        await message.answer(
            "Напишите «взять #» с номером обращения (например: «взять 5»)\n"
            "Или «меню» для возврата."
        )
        return

    # ============================================================
    #  ОСНОВНОЕ МЕНЮ (после авторизации)
    # ============================================================

    if session.get("step") == "main":
        cmd = text.lower()
        if "профиль" in cmd:
            if session.get("username"):
                profile = await handle_profile("vk", uid, session["username"])
                await message.answer(
                    f"👤 Профиль:\nИмя: {profile.username}\n"
                    f"Группа: {profile.group_name}\n"
                    f"Email: {profile.email or '—'}"
                )
            else:
                await message.answer("Сначала войдите в систему.")

        elif "поиск" in cmd:
            user_sessions[uid] = {**session, "step": "search_query"}
            await message.answer("🔍 Введите поисковый запрос:")

        elif "очист" in cmd:
            await handle_clear_chat("vk", uid)
            await message.answer("🧹 Чат очищен! Начнём заново.")

        elif "отмена" in cmd:
            # Пользователь нажал «↩ Отмена» — просто показываем меню
            await message.answer("📋 Главное меню:", keyboard=_get_kb_for_session(session))

        elif "настройк" in cmd:
            result = await handle_settings("vk", uid)
            await message.answer(result)

        elif "статистик" in cmd:
            result = await handle_stats("vk", uid)
            await message.answer(result)

        elif "каналы" in cmd:
            result = await handle_channels("vk", uid)
            await message.answer(result)

        elif "реклам" in cmd:
            result = await handle_ad_prices()
            prices = await _load_prices_from_db()
            user_sessions[uid] = {**session, "step": "ad_type"}
            await message.answer(result)

            # Загружаем историю реклам юзера
            dle_id = session.get("user_id", 0)
            if dle_id:
                try:
                    my_data = await handle_my_requests(dle_id)
                    my_ads = [i for i in my_data.get("items", []) if i.get("type") == "ad"]
                    if my_ads:
                        history = "\n📋 ВАШИ ЗАЯВКИ НА РЕКЛАМУ:\n"
                        for i, ad in enumerate(my_ads[:5]):
                            if i > 0:
                                history += "  ──────────────────\n"
                            st = _status_label(ad.get("status", "new"))
                            history += f"  📢 #{ad['id']} — {st}\n"
                            history += f"     🕐 {ad.get('time_ago', '')}\n"
                            # Превью текста
                            ad_text = ad.get("text", "")
                            if ad_text:
                                history += f"     📝 {ad_text[:60]}\n"
                            # Цена
                            total = ad.get("total_price", 0)
                            corrected = ad.get("corrected_price")
                            if corrected and corrected < total:
                                history += f"     🎉 Цена снижена: {total}₽ → {corrected}₽\n"
                            elif corrected and corrected > total:
                                history += f"     ⚠️ Цена: {corrected}₽ (было {total}₽)\n"
                            elif corrected:
                                history += f"     💰 {corrected}₽\n"
                            else:
                                history += f"     💰 {total}₽\n"
                        await message.answer(history)
                except Exception:
                    pass

            await asyncio.sleep(0.3)
            await message.answer(
                "Выберите тип рекламы:",
                keyboard=get_ad_type_keyboard(prices),
            )

        elif "новост" in cmd:
            user_sessions[uid] = {**session, "step": "news_title"}

            # Загружаем историю новостей юзера
            dle_id = session.get("user_id", 0)
            if dle_id:
                try:
                    my_data = await handle_my_requests(dle_id)
                    my_news = [i for i in my_data.get("items", []) if i.get("type") == "news"]
                    if my_news:
                        history = "\n📋 ВАШИ ПРЕДЛОЖЕННЫЕ НОВОСТИ:\n"
                        for n in my_news[:5]:
                            st = _status_label(n.get("status", "new"))
                            history += f"  📰 #{n['id']} — {st} ({n.get('time_ago', '')})\n"
                            history += f"     {n.get('title', '')[:50]}\n"
                        await message.answer(history)
                except Exception:
                    pass

            await message.answer("📰 Предложить новость!\n\nНапишите заголовок новости:")

        elif "админк" in cmd:
            if not _is_admin(session):
                await message.answer("⛔ Эта функция доступна только администратору.")
                return
            result = await handle_admin_panel("vk", uid, session.get("user_id", 0))
            user_sessions[uid] = {**session, "step": "admin_view_message"}
            await message.answer(result)
            await asyncio.sleep(0.3)
            await message.answer(
                "Напишите «новые» или «все обращения» для просмотра списка,\n"
                "или сразу «взять #» с номером обращения.",
                keyboard=get_menu_keyboard(is_admin=True),
            )

        elif "сообщение" in cmd or "админу" in cmd:
            # Загружаем историю чата и сохраняем в сессию
            dle_id = session.get("user_id", 0)
            chat_msgs = []
            if dle_id:
                try:
                    chat_data = await handle_get_chat(dle_id)
                    chat_msgs = chat_data.get("messages", [])
                except Exception:
                    pass

            if chat_msgs:
                formatted = _format_chat_messages(chat_msgs, page=1)
                result = await message.answer(
                    formatted + "\n\n✏️ Напишите сообщение или используйте кнопки:",
                    keyboard=get_chat_nav_keyboard(),
                )
            else:
                result = await message.answer(
                    "📩 Пока сообщений нет.\n\n"
                    "✏️ Напишите ваш вопрос администратору:",
                    keyboard=get_chat_nav_keyboard(),
                )

            # Запоминаем ID сообщения чтобы потом редактировать, а не плодить новые
            cmid = result[0].conversation_message_id if result else None
            user_sessions[uid] = {
                **session,
                "step": "chat_view",
                "chat_messages": chat_msgs,
                "chat_page": 1,
                "chat_view_cmid": cmid,
            }

        else:
            # Возможно пользователь ввёл номер обращения из админки
            if cmd.startswith("взять") or cmd.startswith("#"):
                try:
                    msg_id = int(cmd.replace("взять", "").replace("#", "").strip())
                except ValueError:
                    await message.answer("Выберите действие из меню.", keyboard=_get_kb_for_session(session))
                    return
                result = await handle_admin_view_message(
                    "vk", uid, session.get("user_id", 0), msg_id,
                )
                await message.answer(result, keyboard=_get_kb_for_session(session))
                return

            await message.answer("Выберите действие из меню.", keyboard=_get_kb_for_session(session))
        return

    # --- Ввод поискового запроса ---
    if session.get("step") == "search_query":
        cmd = text.lower()

        # Проверка: если пользователь нажал кнопку меню — отменяем поиск
        # Сравниваем ТОЛЬКО полный текст (не вхождение), чтобы запрос
        # «как сделать поиск» не отменял поиск
        _btn_labels = {"поиск", "профиль", "реклама", "новость", "админу",
                       "настройки", "статистика", "каналы", "админка",
                       "очистить", "отмена"}
        if cmd.strip() in _btn_labels:
            user_sessions[uid] = {**session, "step": "main"}
            await message.answer(
                "🔍 Поиск отменён. Выберите действие из меню:",
                keyboard=_get_kb_for_session(session),
            )
            return

        # Это настоящий поисковый запрос — выполняем поиск
        user_sessions[uid] = {
            **session,
            "step": "search",
            "search_query": text,
            "search_page": 1,
        }
        result = await handle_search("vk", uid, text, page=1)
        await message.answer(result.text, keyboard=_get_search_keyboard())
        return

    # --- Режим поиска (просмотр результатов) с кнопками навигации ---
    if session.get("step") == "search":
        cmd = text.lower().strip()

        # 👉 Вперёд — следующая страница
        if cmd in ("👉 вперёд", "вперёд", "дальше", "ещё"):
            query = session.get("search_query", "")
            page = session.get("search_page", 1) + 1
            result = await handle_search("vk", uid, query, page=page)
            user_sessions[uid] = {
                **session,
                "search_query": query,
                "search_page": page,
            }
            await message.answer(result.text, keyboard=_get_search_keyboard())
            return

        # 👈 Назад — предыдущая страница
        if cmd in ("👈 назад", "назад", "предыдущая", "в начало", "сначала"):
            query = session.get("search_query", "")
            page = session.get("search_page", 1)
            if page > 1:
                page -= 1
            result = await handle_search("vk", uid, query, page=page)
            user_sessions[uid] = {
                **session,
                "search_query": query,
                "search_page": page,
            }
            await message.answer(result.text, keyboard=_get_search_keyboard())
            return

        # 🚪 Выйти — выход из поиска
        if cmd in ("🚪 выйти", "выйти", "выход"):
            user_sessions[uid] = {**session, "step": "main"}
            await message.answer("🔍 Поиск завершён. Выберите действие:", keyboard=_get_kb_for_session(session))
            return

        # Любая кнопка меню или другое слово — выходим из поиска
        user_sessions[uid] = {**session, "step": "main"}
        await message.answer("🔍 Поиск завершён. Выберите действие:", keyboard=_get_kb_for_session(session))
        return

    # --- Неавторизованный пользователь ---
    # Если ввели логин,пароль — пробуем сразу авторизовать
    if "," in text:
        parts = text.split(",", 1)
        login = parts[0].strip()
        password = parts[1].strip()
        if login and password:
            await message.answer("⏳ Проверяю данные...")
            result = await handle_auth("vk", uid, login, password)
            if result.success:
                is_admin = result.dle_user_id == settings.ADMIN_USER_ID
                user_sessions[uid] = {
                    "step": "main",
                    "username": result.dle_username,
                    "group": result.dle_group_name,
                    "user_id": result.dle_user_id,
                }
                await message.answer(
                    f"✅ Авторизация успешна!\n"
                    f"Пользователь: {result.dle_username}\n"
                    f"Статус: {result.dle_group_name}",
                    keyboard=get_menu_keyboard(is_admin=is_admin),
                )
            else:
                await message.answer(
                    f"❌ {result.message}\nПопробуйте ещё раз или нажмите «Войти».",
                    keyboard=get_auth_keyboard(),
                )
            return

    await message.answer(
        "👋 Нажмите «Войти» для авторизации или «Каналы» для ссылок.",
        keyboard=get_auth_keyboard(),
    )


# ==================================================
#  Подсчёт цены рекламы
# ==================================================

def _calc_ad_price(platforms: str, days: int, pin_days: int, prices: dict, pin_platforms: str = None) -> float:
    """
    Считает стоимость объявления в ленте по формуле из веб-версии.
    Цены берутся из БД (таблица ad_prices).

    Формула: site_price × кол-во_площадок × дни + pinPerDay × кол-во_площадок_закрепления × pin_дни
    Если pin_platforms=None — закрепление на всех площадках (старое поведение).
    """
    site_price = prices.get("feed_site", {}).get("base_price", 0)
    pin_per_day = prices.get("feed_pin_single", {}).get("base_price", 0)

    # Сколько площадок выбрано
    plat_keys = ["site", "tg", "vk", "max"]
    if platforms == "all":
        num_plats = len(plat_keys)
    else:
        num_plats = len([p for p in platforms.split(",") if p.strip() in plat_keys])

    base = site_price * num_plats * days
    total = base

    if pin_days > 0:
        # Если pin_platforms указаны — используем их количество
        # Если None — закрепляем на всех площадках
        if pin_platforms:
            pin_count = len([p for p in pin_platforms.split(",") if p.strip()])
        else:
            pin_count = num_plats
        total += round(pin_per_day * pin_count * pin_days)

    return total


# ==================================================
# Запуск VK-бота
# ==================================================

async def start_vk_bot():
    """
    Запускает VK-бота в фоне.
    Вызывается из main.py при старте приложения.
    """
    if not settings.VK_BOT_TOKEN or "your_vk_" in settings.VK_BOT_TOKEN:
        print("⚠️ VK токен не задан или стоит заглушка — VK-бот не запущен")
        print("   Заполни VK_BOT_TOKEN в .env настоящим токеном")
        return

    print("✅ VK-бот запущен!")

    try:
        # Подключаемся к уже работающему event loop'у Uvicorn'а
        # иначе vkbottle попытается создать свой loop и упадёт
        bot.loop_wrapper.loop = asyncio.get_running_loop()
        bot.loop_wrapper._running = True
        await bot.run_polling()
    except Exception as e:
        print(f"❌ Ошибка VK-бота: {e}")
        print("   Проверь VK_BOT_TOKEN в .env")
