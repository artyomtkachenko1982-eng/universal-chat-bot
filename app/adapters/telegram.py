"""
telegram.py — Telegram-адаптер (aiogram 3.x)

Запускает Telegram-бота с клавиатурой из 6 кнопок.
Команды обрабатываются так же, как в VK и Web-виджете.
"""

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
import asyncio

from app.core.config import settings
from app.handlers.commands import (
    handle_auth, handle_profile, handle_search,
    handle_clear_chat, handle_settings, handle_stats, handle_channels,
    handle_ad_prices, handle_ad_submit, handle_my_requests,
)
from app.core.database import async_session
from app.models.database import AdPrice
from sqlalchemy import select


# ============================================================
# 📋 Клавиатуры
# ============================================================

def get_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Постоянное меню (после авторизации).
    7 кнопок: Поиск | Профиль | Реклама | Очистить | Настройки | Статистика | Каналы
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            # Ряд 1: Поиск | Профиль | Реклама
            [
                KeyboardButton(text="🔍 Поиск"),
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="📢 Реклама"),
            ],
            # Ряд 2: Очистить | Настройки | Статистика
            [
                KeyboardButton(text="🧹 Очистить"),
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="📊 Статистика"),
            ],
            # Ряд 3: Каналы
            [
                KeyboardButton(text="📡 Каналы"),
            ],
        ],
        resize_keyboard=True,       # кнопки подгоняются под экран
        one_time_keyboard=False,    # клавиатура не исчезает после нажатия
    )
    return keyboard


def get_search_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Inline-кнопки для пагинации поиска.
    Крепятся прямо к сообщению с результатами.
    """
    buttons = []

    # Кнопка «Назад» — если не первая страница
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"search_go:{current_page - 1}",
            )
        )

    # Кнопка «Ещё» — если есть следующая страница
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="▶️ Ещё",
                callback_data=f"search_go:{current_page + 1}",
            )
        )

    # Счётчик страниц (не нажимается)
    page_counter = InlineKeyboardButton(
        text=f"📄 {current_page}/{total_pages}",
        callback_data="search_noop",
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[buttons, [page_counter]],
    )
    return keyboard


def get_auth_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для неавторизованного (2 кнопки).
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Войти")],
            [KeyboardButton(text="📡 Каналы")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    return keyboard


# ============================================================
# 📋 Клавиатуры для рекламы
# ============================================================

def get_ad_type_keyboard(prices: dict = None) -> ReplyKeyboardMarkup:
    """Выбор типа рекламы с актуальными ценами."""
    feed = int((prices or {}).get("feed_site", {}).get("base_price", 0))
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"📢 Объявление (от {feed}₽")],
            [KeyboardButton(text="🎯 Баннер / Статья")],
            [KeyboardButton(text="↩ Отмена")],
        ],
        resize_keyboard=True,
    )


def get_banner_type_keyboard(prices: dict = None) -> ReplyKeyboardMarkup:
    """Баннер или статья с ценами из БД."""
    p = prices or {}
    banner_min = int(p.get("banner_in_news", {}).get("base_price", 0))
    article_base = int(p.get("article_base", {}).get("base_price", 0))
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"🖼 Баннер (от {banner_min}₽/мес)")],
            [KeyboardButton(text=f"📰 Статья (от {article_base}₽)")],
            [KeyboardButton(text="↩ Отмена")],
        ],
        resize_keyboard=True,
    )


def get_banner_size_keyboard(prices: dict = None) -> ReplyKeyboardMarkup:
    """Размер баннера — 5 вариантов."""
    p = prices or {}
    banner_all = int(p.get("banner_all_pages", {}).get("base_price", 0))
    banner_news = int(p.get("banner_in_news", {}).get("base_price", 0))
    min_price = min(banner_all, banner_news) if banner_all and banner_news else (banner_news or banner_all or 3000)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"728x90 (от {min_price}₽/мес)"),
             KeyboardButton(text=f"336x228 (от {min_price}₽/мес)")],
            [KeyboardButton(text=f"300x600 (от {min_price}₽/мес)"),
             KeyboardButton(text=f"300x250 (от {min_price}₽/мес)")],
            [KeyboardButton(text=f"468x60 (от {min_price}₽/мес)")],
            [KeyboardButton(text="↩ Отмена")],
        ],
        resize_keyboard=True,
    )


def get_banner_placement_keyboard(prices: dict = None) -> ReplyKeyboardMarkup:
    """Где показывать баннер — с ценами."""
    p = prices or {}
    all_pages = int(p.get("banner_all_pages", {}).get("base_price", 0))
    in_news = int(p.get("banner_in_news", {}).get("base_price", 0))
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"🌐 Сквозное ({all_pages}₽/мес)")],
            [KeyboardButton(text=f"📰 В новостях ({in_news}₽/мес)")],
            [KeyboardButton(text="↩ Отмена")],
        ],
        resize_keyboard=True,
    )


def get_article_options_keyboard(prices: dict = None) -> ReplyKeyboardMarkup:
    """Тип статьи — цены на кнопках."""
    p = prices or {}
    base = int(p.get("article_base", {}).get("base_price", 0))
    base_surch = p.get("article_base", {}).get("surcharge_pct", 0.3)
    eternal = int(p.get("article_eternal", {}).get("base_price", 0))
    eternal_surch = p.get("article_eternal", {}).get("surcharge_pct", 0.3)
    base_nr = round(base * (1 + base_surch))
    eternal_nr = round(eternal * (1 + eternal_surch))
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"Обычная ({base}₽)"),
             KeyboardButton(text=f"Обычная нерелев. ({base_nr}₽)")],
            [KeyboardButton(text=f"Вечная ({eternal}₽)"),
             KeyboardButton(text=f"Вечная нерелев. ({eternal_nr}₽)")],
            [KeyboardButton(text="↩ Отмена")],
        ],
        resize_keyboard=True,
    )


def get_preview_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура предпросмотра."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить")],
            [KeyboardButton(text="✏️ Редактировать")],
            [KeyboardButton(text="↩ Отмена")],
        ],
        resize_keyboard=True,
    )


# ============================================================
# 💰 Цены рекламы (из БД)
# ============================================================

async def _load_prices_from_db() -> dict:
    """Читает все цены из таблицы ad_prices."""
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


def _calc_ad_price(
    platforms: str, days: int, pin_days: int,
    prices: dict, pin_platforms: str = None,
) -> float:
    """Считает стоимость объявления в ленте."""
    site_price = prices.get("feed_site", {}).get("base_price", 0)
    pin_per_day = prices.get("feed_pin_single", {}).get("base_price", 0)

    plat_keys = ["site", "tg", "vk", "max"]
    if platforms == "all":
        num_plats = len(plat_keys)
    else:
        num_plats = len([p for p in platforms.split(",") if p.strip() in plat_keys])

    base = site_price * num_plats * days
    total = base

    if pin_days > 0:
        if pin_platforms:
            pin_count = len([p for p in pin_platforms.split(",") if p.strip()])
        else:
            pin_count = num_plats
        total += round(pin_per_day * pin_count * pin_days)

    return total


# ============================================================
# 🖼 Сохранение фото из Telegram
# ============================================================

async def _save_photo_from_tg(message: types.Message) -> str | None:
    """Скачивает фото из Telegram-сообщения и сохраняет в uploads/ad_images/.
    Возвращает путь типа /static/ad_images/xxx.jpg или None."""
    if not message.photo:
        return None

    import os
    import uuid
    import logging

    log = logging.getLogger("tg_bot")

    try:
        # Берём самый большой размер фото
        photo = message.photo[-1]
        log.info(f"_save_photo: file_id={photo.file_id}")

        # В aiogram 3.x: сначала получаем File, потом скачиваем по file_path
        file_info = await message.bot.get_file(photo.file_id)
        log.info(f"_save_photo: file_path={file_info.file_path}")
        file_bytes = await message.bot.download_file(file_info.file_path)

        # Сохраняем на диск
        filename = f"{uuid.uuid4().hex}.jpg"
        # Путь: app/adapters/telegram.py → app/ → uploads/ad_images/
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "ad_images")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, "wb") as f:
            f.write(file_bytes.read())

        log.info(f"_save_photo: SAVED → {filepath}")
        return f"/static/ad_images/{filename}"
    except Exception as e:
        log.error(f"_save_photo ERROR: {e}")
        return None


# ============================================================
# 🗑 Вспомогательные функции
# ============================================================

async def reply_and_clean(
    message: types.Message, state: FSMContext,
    text: str, save_as: str = "bot",
    bottom_kb: ReplyKeyboardMarkup | None = None,
    **kwargs,
) -> types.Message:
    """
    СНАЧАЛА отправляет новый ответ (чтобы клавиатура появилась),
    ПОТОМ удаляет старые сообщения (чтобы клавиатура не пропала).

    save_as="bot"    — сохраняет как last_bot_msg_id (будет удалён следующим ответом)
    save_as="search" — сохраняет как search_msg_id (будет удалён новым поиском или не-поисковым ответом)
    bottom_kb        — отдельная нижняя клавиатура (если в **kwargs уже есть reply_markup с inline-кнопками)

    Возвращает отправленное сообщение (чтобы можно было взять .message_id).
    """
    data = await state.get_data()

    # ===== 1. СНАЧАЛА отправляем новый ответ =====
    sent = await message.answer(text, **kwargs)

    # Сохраняем ID нового ответа
    if save_as == "search":
        await state.update_data(search_msg_id=sent.message_id)
    else:
        await state.update_data(last_bot_msg_id=sent.message_id)

    # Если нужна отдельная нижняя клавиатура (когда в основном ответе inline-кнопки)
    if bottom_kb:
        kb_msg = await message.answer("ㅤ", reply_markup=bottom_kb)
        await state.update_data(kb_msg_id=kb_msg.message_id)

    # ===== 2. ПОТОМ удаляем старые сообщения =====
    for key in ("last_bot_msg_id", "search_msg_id", "kb_msg_id"):
        old_id = data.get(key)
        if old_id:
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=old_id,
                )
            except Exception:
                pass

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception:
        pass

    return sent


# ============================================================
# 🔄 Состояния FSM (Finite State Machine)
# ============================================================

class AuthState(StatesGroup):
    """
    Состояния для процесса авторизации.
    aiogram сам запоминает, на каком шаге пользователь.
    """
    waiting_login = State()    # ждём логин,пароль
    main_menu = State()        # пользователь в главном меню
    search_mode = State()      # ждём поисковый запрос
    ad_menu = State()          # режим рекламы (шаг хранится в ad_step данных)


# ============================================================
# 🤖 Создаём бота и диспетчер
# ============================================================

# MemoryStorage — хранит FSM-состояния в оперативной памяти
# (позже можно заменить на RedisStorage)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Бота создадим позже (при запуске), потому что aiogram проверяет токен сразу
# и падает, если токен — заглушка
bot: Bot | None = None


# ============================================================
# 📨 Обработчики команд
# ============================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Реакция на /start — приветствие.
    """
    await state.set_state(AuthState.waiting_login)
    await reply_and_clean(
        message, state,
        "👋 Приветствуем на turbinist.ru!\n\n"
        "Для доступа к функциям бота необходимо авторизоваться.\n\n"
        "Нажмите «🔐 Войти» и введите логин и пароль через запятую.\n"
        "Пример: turbinist_user, мой_пароль",
        reply_markup=get_auth_keyboard(),
    )


@dp.message(F.text == "🔐 Войти")
async def btn_login(message: types.Message, state: FSMContext):
    """
    Нажата кнопка «Войти» — ждём логин и пароль.
    """
    await state.set_state(AuthState.waiting_login)
    await reply_and_clean(
        message, state,
        "Введите логин и пароль через запятую.\n"
        "Пример: turbinist_user, мой_пароль",
        reply_markup=get_auth_keyboard(),
    )


@dp.message(F.text == "📡 Каналы")
async def btn_channels(message: types.Message, state: FSMContext):
    """
    Показать ссылки на каналы.
    """
    uid = str(message.from_user.id)
    result = await handle_channels("telegram", uid)

    # Определяем, какую клавиатуру показать
    current_state = await state.get_state()
    if current_state == AuthState.main_menu.state:
        kb = get_menu_keyboard()
    else:
        kb = get_auth_keyboard()

    await reply_and_clean(message, state, result, reply_markup=kb)


@dp.message(F.text == "📢 Реклама")
async def btn_ad(message: types.Message, state: FSMContext):
    """Нажата кнопка «Реклама» — показать цены и выбор типа."""
    prices = await _load_prices_from_db()
    price_text = await handle_ad_prices()
    uid = str(message.from_user.id)
    data = await state.get_data()
    dle_user_id = data.get("user_id")

    # Показываем историю заявок
    history_text = ""
    if dle_user_id:
        try:
            history = await handle_my_requests(dle_user_id)
            ads = [i for i in history.get("items", []) if i.get("type") == "ad"][-5:]
            if ads:
                lines = ["📋 Ваши последние заявки:"]
                for a in ads:
                    status = a.get("status", "?")
                    price = a.get("total_price", 0)
                    created = a.get("created_at", "")[:10]
                    lines.append(f"• {status} — {price}₽ ({created})")
                history_text = "\n\n" + "\n".join(lines)
        except Exception:
            pass

    await state.set_state(AuthState.ad_menu)
    await state.update_data(ad_step="ad_type")
    await reply_and_clean(
        message, state,
        f"📢 РЕКЛАМА\n\n{price_text}{history_text}",
        reply_markup=get_ad_type_keyboard(prices),
    )


@dp.message(F.text == "🔍 Поиск")
async def btn_search(message: types.Message, state: FSMContext):
    """Нажата кнопка «Поиск» — ждём запрос."""
    await state.set_state(AuthState.search_mode)
    await reply_and_clean(
        message, state, "🔍 Введите поисковый запрос:",
        reply_markup=get_menu_keyboard(),
    )


@dp.message(F.text == "👤 Профиль")
async def btn_profile(message: types.Message, state: FSMContext):
    """Нажата кнопка «Профиль» — показываем данные."""
    uid = str(message.from_user.id)
    # Получаем сохранённый username из FSM
    data = await state.get_data()
    username = data.get("username")

    if username:
        profile = await handle_profile("telegram", uid, username)
        await reply_and_clean(
            message, state,
            f"👤 Профиль:\nИмя: {profile.username}\n"
            f"Группа: {profile.group_name}\n"
            f"Email: {profile.email or '—'}",
            reply_markup=get_menu_keyboard(),
        )
    else:
        await reply_and_clean(
            message, state, "Сначала войдите в систему.",
            reply_markup=get_menu_keyboard(),
        )


@dp.message(F.text == "🧹 Очистить")
async def btn_clear(message: types.Message, state: FSMContext):
    """Очистка чата (просто приветствие)."""
    uid = str(message.from_user.id)
    await handle_clear_chat("telegram", uid)
    await reply_and_clean(
        message, state, "🧹 Чат очищен! Я вас слушаю.",
        reply_markup=get_menu_keyboard(),
    )


@dp.message(F.text == "⚙️ Настройки")
async def btn_settings(message: types.Message, state: FSMContext):
    """Настройки бота."""
    uid = str(message.from_user.id)
    result = await handle_settings("telegram", uid)
    await reply_and_clean(
        message, state, result,
        reply_markup=get_menu_keyboard(),
    )


@dp.message(F.text == "📊 Статистика")
async def btn_stats(message: types.Message, state: FSMContext):
    """Статистика пользователя."""
    uid = str(message.from_user.id)
    result = await handle_stats("telegram", uid)
    await reply_and_clean(
        message, state, result,
        reply_markup=get_menu_keyboard(),
    )


# ============================================================
# 🖼 Обработчик фото (должен быть ПЕРЕД главным, чтобы ловить фото раньше)
# ============================================================

@dp.message(F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Ловит фото от пользователя в режиме рекламы.
    Скачивает картинку, сохраняет путь в FSM.
    Если есть подпись (caption) — отправляет текст в handle_ad_message."""
    uid = str(message.from_user.id)
    current_state = await state.get_state()

    # Работаем только в режиме рекламы
    if current_state != AuthState.ad_menu.state:
        return

    data = await state.get_data()
    ad_step = data.get("ad_step")

    # Определяем ключ для сохранения в зависимости от шага
    if ad_step in ("ad_text", "ad_preview"):
        image_key = "ad_image_path"
    elif ad_step in ("banner_text", "banner_preview"):
        image_key = "banner_image_path"
    elif ad_step in ("article_text", "article_preview"):
        image_key = "article_image_path"
    else:
        return  # не наш шаг — игнорируем

    image_path = await _save_photo_from_tg(message)
    if not image_path:
        await message.answer("❌ Не удалось скачать фото.")
        return

    await state.update_data(**{image_key: image_path})

    caption = (message.caption or "").strip()
    if caption:
        # Есть подпись — обрабатываем текст как обычно
        await handle_ad_message(message, state, uid)
    else:
        await message.answer("📸 Фото сохранил ✅. Теперь напиши текст.")


# ============================================================
# ✍️ Обработка произвольного текста (главный обработчик)
# ============================================================

@dp.message()
async def handle_text(message: types.Message, state: FSMContext):
    """
    Главный обработчик всех сообщений.
    Проверяет состояние (FSM) и перенаправляет в нужный режим.
    """
    uid = str(message.from_user.id)

    # Если фото — берём текст из подписи (caption)
    if message.photo and message.caption:
        text = message.caption.strip()
    elif message.text:
        text = message.text.strip()
    else:
        # Просто фото без текста — обработаем в нужном режиме
        text = ""

    current_state = await state.get_state()

    # --------------------------------------------------
    # 🔐 Состояние: ждём логин и пароль
    # --------------------------------------------------
    if current_state == AuthState.waiting_login.state:
        if "," in text:
            parts = text.split(",", 1)
            login = parts[0].strip()
            password = parts[1].strip()

            # Показываем «часики», старый ответ бота удалится автоматически
            await reply_and_clean(
                message, state, "⏳ Проверяю данные...",
                reply_markup=get_auth_keyboard(),
            )

            result = await handle_auth("telegram", uid, login, password)

            if result.success:
                # Сохраняем данные в FSM
                await state.update_data(
                    username=result.dle_username,
                    group=result.dle_group_name,
                    user_id=result.dle_user_id,
                )
                await state.set_state(AuthState.main_menu)

                await reply_and_clean(
                    message, state,
                    f"✅ Авторизация успешна!\n"
                    f"Пользователь: {result.dle_username}\n"
                    f"Статус: {result.dle_group_name}",
                    reply_markup=get_menu_keyboard(),
                )
            else:
                await reply_and_clean(
                    message, state,
                    f"❌ {result.message}\nПопробуйте ещё раз: логин, пароль",
                    reply_markup=get_auth_keyboard(),
                )
        else:
            await reply_and_clean(
                message, state,
                "Нужно ввести логин и пароль через запятую.\n"
                "Пример: turbinist_user, мой_пароль",
                reply_markup=get_auth_keyboard(),
            )

    # --------------------------------------------------
    # 📢 Состояние: режим рекламы
    # --------------------------------------------------
    elif current_state == AuthState.ad_menu.state:
        await handle_ad_message(message, state, uid)
        return

    # --------------------------------------------------
    # 🔍 Состояние: режим поиска
    # --------------------------------------------------
    elif current_state == AuthState.search_mode.state:
        # Выполняем поиск (всегда с page=1, новый запрос)
        search_result = await handle_search("telegram", uid, text, page=1)

        # Сохраняем данные поиска в FSM (для пагинации)
        await state.update_data(
            search_query=text,
            search_page=search_result.current_page,
            search_total_pages=search_result.total_pages,
        )

        # Отправляем результат — reply_and_clean удалит старый ответ + подсказку
        await reply_and_clean(
            message, state,
            search_result.text,
            save_as="search",
            bottom_kb=get_menu_keyboard(),
            reply_markup=get_search_keyboard(
                search_result.current_page,
                search_result.total_pages,
            ),
        )

        # Остаёмся в main_menu (следующий текст = обычное сообщение)
        await state.set_state(AuthState.main_menu)

    # --------------------------------------------------
    # ❓ Всё остальное
    # --------------------------------------------------
    else:
        await reply_and_clean(
            message, state,
            "Выберите действие из меню или введите команду.",
            reply_markup=(
                get_menu_keyboard()
                if current_state == AuthState.main_menu.state
                else get_auth_keyboard()
            ),
        )


# ============================================================
# 📢 Обработка всех шагов рекламы
# ============================================================

PLATFORM_NAMES = {
    "сайт": "site", "site": "site",
    "tg": "tg", "telegram": "tg", "телеграм": "tg",
    "vk": "vk", "вк": "vk",
    "max": "max", "макс": "max",
    "все": "all", "all": "all",
}

PLATFORM_LABELS = {"site": "Сайт", "tg": "Telegram", "vk": "VK", "max": "MAX"}


async def handle_ad_message(
    message: types.Message, state: FSMContext,
    uid: str,
):
    """
    Обрабатывает все шаги рекламы.
    Текст берётся из message.text или message.caption (для фото с подписью).
    """
    data = await state.get_data()
    ad_step = data.get("ad_step", "ad_type")
    prices = await _load_prices_from_db()

    text = (message.text or message.caption or "").strip()

    # ===== ОТМЕНА — выход из рекламы =====
    if text == "↩ Отмена":
        await state.set_state(AuthState.main_menu)
        # Очищаем данные рекламы
        for k in list(data.keys()):
            if k.startswith("ad_"):
                del data[k]
        await reply_and_clean(
            message, state, "❌ Реклама отменена.",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # Шаг: выбор типа (ad_type)
    # ========================================================
    if ad_step == "ad_type":
        choice = text.strip().lower()
        if "объявление" in choice:
            await state.update_data(ad_step="ad_text", ad_calc_flow="feed", ad_image_path=None)
            await reply_and_clean(
                message, state,
                "📢 ОБЪЯВЛЕНИЕ В ЛЕНТЕ\n\n"
                "📝 Напишите текст объявления:\n"
                "📸 Можно прикрепить картинку (отправьте фото вместе с текстом)",
                reply_markup=get_menu_keyboard(),
            )
        elif "баннер" in choice or "статья" in choice:
            await state.update_data(ad_step="banner_type")
            await reply_and_clean(
                message, state,
                "🎯 БАННЕР ИЛИ СТАТЬЯ",
                reply_markup=get_banner_type_keyboard(prices),
            )
        else:
            await reply_and_clean(
                message, state,
                "Выберите тип рекламы кнопкой:",
                reply_markup=get_ad_type_keyboard(prices),
            )
        return

    # ========================================================
    # Шаг: выбор баннер/статья (banner_type)
    # ========================================================
    if ad_step == "banner_type":
        choice = text.strip().lower()
        if "баннер" in choice:
            await state.update_data(ad_step="banner_size", ad_calc_flow="banner")
            await reply_and_clean(
                message, state,
                "🖼 БАННЕР\n\nВыберите размер:",
                reply_markup=get_banner_size_keyboard(prices),
            )
        elif "статья" in choice:
            await state.update_data(ad_step="article_options", ad_calc_flow="article")
            await reply_and_clean(
                message, state,
                "📰 СТАТЬЯ\n\nВыберите тип:",
                reply_markup=get_article_options_keyboard(prices),
            )
        else:
            await reply_and_clean(
                message, state,
                "🖼 Баннер или 📰 Статья?",
                reply_markup=get_banner_type_keyboard(prices),
            )
        return

    # ========================================================
    # 🖼 Баннер: выбор размера (banner_size)
    # ========================================================
    if ad_step == "banner_size":
        size = None
        for s in ("728x90", "336x228", "300x600", "300x250", "468x60"):
            if s in text:
                size = s
                break
        if not size:
            await reply_and_clean(
                message, state,
                "Выберите размер кнопкой:",
                reply_markup=get_banner_size_keyboard(prices),
            )
            return
        await state.update_data(ad_step="banner_placement", banner_size=size)
        await reply_and_clean(
            message, state,
            f"Размер: {size}\n\nГде показывать?",
            reply_markup=get_banner_placement_keyboard(prices),
        )
        return

    # ========================================================
    # 🖼 Баннер: размещение (banner_placement)
    # ========================================================
    if ad_step == "banner_placement":
        choice = text.strip().lower()
        if "сквозное" in choice:
            placement = "all_pages"
            label = "Сквозное (все страницы)"
        elif "в новостях" in choice or "новост" in choice:
            placement = "in_news"
            label = "В указанных новостях"
        else:
            await reply_and_clean(
                message, state,
                "Где показывать баннер?",
                reply_markup=get_banner_placement_keyboard(prices),
            )
            return
        await state.update_data(ad_step="banner_options", banner_placement=placement)
        await reply_and_clean(
            message, state,
            f"Размещение: {label}\n\n"
            "Доп. опции (+30% каждая):\n"
            "1. Главная страница\n"
            "2. Нерелевантная тематика\n"
            "3. Индивидуальные пожелания\n\n"
            "Введите номера через запятую (1,3) или 0 — без опций:",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 🖼 Баннер: доп. опции (banner_options)
    # ========================================================
    if ad_step == "banner_options":
        opts = []
        raw = text.strip().lower()
        if "1" in raw:
            opts.append("main")
        if "2" in raw or "нерелев" in raw:
            opts.append("not_relevant")
        if "3" in raw or "пожелан" in raw:
            opts.append("custom")
        opts_str = ",".join(opts) if opts else None
        await state.update_data(ad_step="banner_months", banner_opts=opts_str)
        sp = int(prices.get("banner_in_news", {}).get("base_price", 0))
        await reply_and_clean(
            message, state,
            f"На сколько месяцев?\n"
            f"(цена от {sp}₽/мес)\n"
            "Введите число (1, 2, 3...):",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 🖼 Баннер: количество месяцев (banner_months)
    # ========================================================
    if ad_step == "banner_months":
        try:
            months = int(text.strip())
            if months < 1:
                raise ValueError
        except ValueError:
            await reply_and_clean(
                message, state,
                "Введите целое число месяцев (1, 2, 3...):",
                reply_markup=get_menu_keyboard(),
            )
            return
        await state.update_data(ad_step="banner_text", banner_months=months)

        # Считаем цену
        placement = data.get("banner_placement", "in_news")
        price_key = f"banner_{placement}"
        base_price = int(prices.get(price_key, {}).get("base_price", 0)) * months
        opts = data.get("banner_opts", "")
        if opts:
            surcharge = prices.get(price_key, {}).get("surcharge_pct", 0.3)
            opts_count = len(opts.split(","))
            base_price = round(base_price * (1 + surcharge * opts_count))

        await reply_and_clean(
            message, state,
            f"💰 Цена: {base_price}₽ за {months} мес.\n\n"
            "📝 Опишите баннер (текст, ссылки, пожелания):\n"
            "📸 Можно прикрепить картинку:",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 🖼 Баннер: текст баннера (banner_text) / 📢 Объявление: текст (ad_text)
    #   → сразу сохраняем и переходим на след. шаг
    # ========================================================
    if ad_step == "banner_text" or ad_step == "banner_preview":
        if ad_step == "banner_text":
            await state.update_data(
                ad_step="banner_preview",
                banner_text=text,
            )
        data = await state.get_data()
        b_size = data.get("banner_size", "728x90")
        b_placement = data.get("banner_placement", "in_news")
        b_months = data.get("banner_months", 1)
        b_opts = data.get("banner_opts", "")
        b_text = data.get("banner_text", text)
        b_image = data.get("banner_image_path")

        # Финальная цена
        price_key = f"banner_{b_placement}"
        base_price = int(prices.get(price_key, {}).get("base_price", 0)) * b_months
        if b_opts:
            surcharge = prices.get(price_key, {}).get("surcharge_pct", 0.3)
            opts_count = len(b_opts.split(","))
            base_price = round(base_price * (1 + surcharge * opts_count))

        # Формируем предпросмотр
        placement_label = "Сквозное" if b_placement == "all_pages" else "В новостях"
        img_note = "\n📸 Фото прикреплено ✅" if b_image else ""
        preview = (
            f"🖼 БАННЕР — ПРЕДПРОСМОТР{img_note}\n\n"
            f"Размер: {b_size}\n"
            f"Размещение: {placement_label}\n"
            f"Месяцев: {b_months}\n"
            f"Опции: {b_opts or 'нет'}\n"
            f"💰 Цена: {base_price}₽\n\n"
            f"📝 {b_text}"
        )
        await reply_and_clean(
            message, state,
            preview,
            reply_markup=get_preview_keyboard(),
        )
        return

    # ========================================================
    # 📰 Статья: выбор опций (article_options)
    # ========================================================
    if ad_step == "article_options":
        choice = text.strip().lower()
        article_base = int(prices.get("article_base", {}).get("base_price", 0))
        article_eternal = int(prices.get("article_eternal", {}).get("base_price", 0))
        article_base_surch = prices.get("article_base", {}).get("surcharge_pct", 0.3)
        article_eternal_surch = prices.get("article_eternal", {}).get("surcharge_pct", 0.3)

        is_eternal = "вечная" in choice
        is_nr = "нерелев" in choice

        if choice in ("1", "2", "3", "4"):
            eternal, not_relevant = {
                "1": (False, False), "2": (False, True),
                "3": (True, False), "4": (True, True),
            }[choice]
        elif "обычная" in choice or "вечная" in choice:
            eternal, not_relevant = is_eternal, is_nr
        else:
            await reply_and_clean(
                message, state,
                "Выберите тип статьи кнопкой:",
                reply_markup=get_article_options_keyboard(prices),
            )
            return

        if eternal:
            price = round(article_eternal * (1 + article_eternal_surch)) if not_relevant else article_eternal
            await state.update_data(
                ad_step="article_text",
                article_eternal=True, article_not_relevant=not_relevant,
                article_calc_price=price, article_fix_days=0,
            )
            await reply_and_clean(
                message, state,
                f"📰 СТАТЬЯ ВЕЧНАЯ{' (нерелевантная)' if not_relevant else ''}\n"
                f"💰 Цена: {price}₽\n\n"
                "📝 Опишите вашу статью (тема, содержание, ссылки):\n"
                "📸 Можно прикрепить картинку:",
                reply_markup=get_menu_keyboard(),
            )
        else:
            price = round(article_base * (1 + article_base_surch)) if not_relevant else article_base
            await state.update_data(
                ad_step="article_fixation",
                article_eternal=False, article_not_relevant=not_relevant,
                article_calc_price=price,
            )
            fix_per_day = int(prices.get("article_fixation", {}).get("base_price", 0))
            await reply_and_clean(
                message, state,
                f"📌 Фиксация в ленте — {fix_per_day}₽/день\n\n"
                "На сколько дней зафиксировать?\n"
                "Введите число (0 — без фиксации):",
                reply_markup=get_menu_keyboard(),
            )
        return

    # ========================================================
    # 📰 Статья: дни фиксации (article_fixation)
    # ========================================================
    if ad_step == "article_fixation":
        try:
            fix_days = int(text.strip())
            if fix_days < 0:
                raise ValueError
        except ValueError:
            await reply_and_clean(
                message, state,
                "Введите целое число (0 — без фиксации):",
                reply_markup=get_menu_keyboard(),
            )
            return

        fix_per_day = int(prices.get("article_fixation", {}).get("base_price", 0))
        price = data.get("article_calc_price", 0)
        if fix_days > 0:
            price += fix_days * fix_per_day

        await state.update_data(
            ad_step="article_text",
            article_fix_days=fix_days, article_calc_price=price,
        )
        await reply_and_clean(
            message, state,
            f"{'Фиксация: ' + str(fix_days) + ' дн.' if fix_days > 0 else 'Без фиксации'}\n"
            f"💰 Итого: {price}₽\n\n"
            "📝 Опишите вашу статью (тема, содержание, ссылки):\n"
            "📸 Можно прикрепить картинку:",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 📰 Статья: текст статьи (article_text) / предпросмотр
    # ========================================================
    if ad_step == "article_text" or ad_step == "article_preview":
        if ad_step == "article_text":
            await state.update_data(
                ad_step="article_preview",
                article_text=text,
            )
        data = await state.get_data()
        eternal = data.get("article_eternal", False)
        fix_days = data.get("article_fix_days", 0)
        calc_price = data.get("article_calc_price", 0)
        a_text = data.get("article_text", text)
        art_image = data.get("article_image_path")

        img_note = "\n📸 Фото прикреплено ✅" if art_image else ""
        preview = (
            f"📰 СТАТЬЯ{' ВЕЧНАЯ' if eternal else ''} — ПРЕДПРОСМОТР{img_note}\n\n"
            f"{'Фиксация: ' + str(fix_days) + ' дн.' if fix_days > 0 else 'Без фиксации'}\n"
            f"💰 Цена: {calc_price}₽\n\n"
            f"📝 {a_text}"
        )
        await reply_and_clean(
            message, state,
            preview,
            reply_markup=get_preview_keyboard(),
        )
        return

    # ========================================================
    # 📢 Объявление: текст объявления (ad_text)
    # ========================================================
    if ad_step == "ad_text":
        await state.update_data(
            ad_step="ad_platforms",
            ad_text=text,
        )
        sp = int(prices.get("feed_site", {}).get("base_price", 0))
        ad_image_path = data.get("ad_image_path")
        img_note = "\n📸 Фото прикреплено ✅" if ad_image_path else ""
        await reply_and_clean(
            message, state,
            f"🌍 ВЫБОР ПЛОЩАДОК (по {sp}₽/день каждая):{img_note}\n\n"
            f"• сайт — {sp}₽/день\n"
            f"• tg — {sp}₽/день\n"
            f"• vk — {sp}₽/день\n"
            f"• max — {sp}₽/день\n"
            f"• все — {sp * 4}₽/день (все 4)\n\n"
            "Введите через запятую (например: сайт, tg, vk)\n"
            "Или одно слово: все",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 📢 Объявление: выбор площадок (ad_platforms)
    # ========================================================
    if ad_step == "ad_platforms":
        raw = text.lower().strip()
        if raw in ("все", "all"):
            platforms_en = "all"
        else:
            parts = [p.strip() for p in raw.replace(",", " ").split()]
            translated = []
            for p in parts:
                eng = PLATFORM_NAMES.get(p, p)
                if eng in ("site", "tg", "vk", "max"):
                    translated.append(eng)
            if not translated:
                await reply_and_clean(
                    message, state,
                    "Не понял площадки. Введите через запятую:\n"
                    "сайт, tg, vk, max\n"
                    "Или «все» для всех.",
                    reply_markup=get_menu_keyboard(),
                )
                return
            platforms_en = ",".join(translated)

        await state.update_data(ad_step="ad_days", ad_platforms=platforms_en)
        await reply_and_clean(
            message, state,
            "На сколько дней разместить рекламу?\n"
            "Введите число (1, 2, 3...):",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 📢 Объявление: количество дней (ad_days)
    # ========================================================
    if ad_step == "ad_days":
        try:
            days = int(text.strip())
            if days < 1:
                raise ValueError
        except ValueError:
            await reply_and_clean(
                message, state,
                "Введите целое число дней (например: 3):",
                reply_markup=get_menu_keyboard(),
            )
            return
        await state.update_data(ad_step="ad_pin", ad_days=days)
        await reply_and_clean(
            message, state,
            "📌 ЗАКРЕПЛЕНИЕ ОБЪЯВЛЕНИЯ\n\n"
            "На сколько дней закрепить?\n"
            "Введите число (например: 1, 2, 5)\n"
            "Или 0 — без закрепления:",
            reply_markup=get_menu_keyboard(),
        )
        return

    # ========================================================
    # 📢 Объявление: дни закрепления (ad_pin)
    # ========================================================
    if ad_step == "ad_pin":
        try:
            pin_days = int(text.strip())
            if pin_days < 0:
                raise ValueError
        except ValueError:
            await reply_and_clean(
                message, state,
                "Введите целое число (0 — без закрепления):",
                reply_markup=get_menu_keyboard(),
            )
            return

        platforms = data.get("ad_platforms", "site")
        if pin_days > 0:
            # Проверяем, сколько площадок — если 1, идём к предпросмотру
            # Если > 1, предлагаем выбрать площадки для закрепления
            plat_keys_count = 4 if platforms == "all" else len(platforms.split(","))
            if plat_keys_count > 1:
                # Показываем клавиатуру выбора площадок
                available = ["site", "tg", "vk", "max"] if platforms == "all" else platforms.split(",")
                pin_kb = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text=f"☐ {PLATFORM_LABELS.get(k, k)}")]
                        for k in available
                    ] + [[KeyboardButton(text="✅ Далее")], [KeyboardButton(text="↩ Отмена")]],
                    resize_keyboard=True,
                )
                await state.update_data(
                    ad_step="ad_pin_platforms", ad_pin_days=pin_days,
                    ad_pin_selected=set(),
                    ad_pin_available=available,
                )
                await reply_and_clean(
                    message, state,
                    "Выберите площадки для закрепления:\n"
                    "Нажимайте на кнопки, чтобы отметить.\n"
                    "Потом нажмите «✅ Далее»:",
                    reply_markup=pin_kb,
                )
                return

        # Если 0 дней или 1 площадка — сразу предпросмотр
        await state.update_data(ad_step="ad_preview", ad_pin_days=pin_days, ad_pin_platforms=None)
        await _show_feed_preview(message, state, data, prices)
        return

    # ========================================================
    # 📢 Объявление: выбор площадок закрепления (ad_pin_platforms)
    # ========================================================
    if ad_step == "ad_pin_platforms":
        selected = set(data.get("ad_pin_selected", set()))
        available = data.get("ad_pin_available", ["site", "tg", "vk", "max"])

        # Нажатие на площадку — переключаем
        for name, eng in PLATFORM_NAMES.items():
            if text.strip() == f"☐ {PLATFORM_LABELS.get(eng, eng)}" and eng in available:
                selected.add(eng)
                break
            if text.strip() == f"☑ {PLATFORM_LABELS.get(eng, eng)}" and eng in available:
                selected.discard(eng)
                break

        if text.strip() == "✅ Далее":
            pin_platforms = ",".join(sorted(selected)) if selected else None
            await state.update_data(
                ad_step="ad_preview", ad_pin_platforms=pin_platforms,
            )
            await _show_feed_preview(message, state, data, prices)
            return

        await state.update_data(ad_pin_selected=selected)
        # Обновляем клавиатуру
        pin_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(
                    text=f"☑ {PLATFORM_LABELS.get(k, k)}" if k in selected
                    else f"☐ {PLATFORM_LABELS.get(k, k)}"
                )]
                for k in available
            ] + [[KeyboardButton(text="✅ Далее")], [KeyboardButton(text="↩ Отмена")]],
            resize_keyboard=True,
        )
        await reply_and_clean(
            message, state,
            "Выберите площадки для закрепления, затем «✅ Далее»:",
            reply_markup=pin_kb,
        )
        return

    # ========================================================
    # 📢 Объявление: предпросмотр (ad_preview)
    # ========================================================
    if ad_step == "ad_preview":
        if text.strip() == "✅ Отправить":
            await _submit_ad(message, state, data, prices, uid)
        elif text.strip() == "✏️ Редактировать":
            img_saved = "📸 Картинка сохранена ✅. Пришлите новую чтобы заменить.\n" if data.get("ad_image_path") else ""
            await state.update_data(ad_step="ad_text")
            await reply_and_clean(
                message, state,
                f"📝 Введите новый текст объявления:\n{img_saved}",
                reply_markup=get_menu_keyboard(),
            )
        else:
            # Показываем предпросмотр ещё раз
            await _show_feed_preview(message, state, data, prices)
        return

    # Если шаг не распознан — показываем предпросмотр (для кнопок отправить/редактировать)
    # Или для баннера/статьи:
    if ad_step == "banner_preview":
        if text.strip() == "✅ Отправить":
            await _submit_ad(message, state, data, prices, uid)
        elif text.strip() == "✏️ Редактировать":
            img_saved = "📸 Картинка сохранена ✅. Пришлите новую чтобы заменить.\n" if data.get("banner_image_path") else ""
            await state.update_data(ad_step="banner_text")
            await reply_and_clean(
                message, state,
                f"📝 Опишите баннер заново:\n{img_saved}",
                reply_markup=get_menu_keyboard(),
            )
        else:
            # Повторный показ
            await handle_ad_message(message, state, uid)
        return

    if ad_step == "article_preview":
        if text.strip() == "✅ Отправить":
            await _submit_ad(message, state, data, prices, uid)
        elif text.strip() == "✏️ Редактировать":
            img_saved = "📸 Картинка сохранена ✅. Пришлите новую чтобы заменить.\n" if data.get("article_image_path") else ""
            await state.update_data(ad_step="article_text")
            await reply_and_clean(
                message, state,
                f"📝 Опишите статью заново:\n{img_saved}",
                reply_markup=get_menu_keyboard(),
            )
        else:
            await handle_ad_message(message, state, uid)
        return


async def _show_feed_preview(
    message: types.Message, state: FSMContext,
    data: dict, prices: dict,
):
    """Показывает предпросмотр объявления в ленте."""
    text_ad = data.get("ad_text", "")
    platforms = data.get("ad_platforms", "site")
    days = data.get("ad_days", 1)
    pin_days = data.get("ad_pin_days", 0)
    pin_platforms = data.get("ad_pin_platforms")
    total = _calc_ad_price(platforms, days, pin_days, prices, pin_platforms)

    await state.update_data(ad_total_price=total)

    plat_label = "все" if platforms == "all" else platforms.replace(",", ", ")
    pin_label = f"{pin_days} дн." if pin_days > 0 else "нет"
    pin_plat_label = pin_platforms.replace(",", ", ") if pin_platforms else (
        plat_label if pin_days > 0 else "-"
    )

    img_note = "\n📸 Фото прикреплено ✅" if data.get("ad_image_path") else ""
    preview = (
        f"📢 ОБЪЯВЛЕНИЕ — ПРЕДПРОСМОТР\n\n"
        f"{text_ad}{img_note}\n\n"
        f"Площадки: {plat_label}\n"
        f"Дней: {days}\n"
        f"Закрепление: {pin_label}\n"
        f"Площадки закрепления: {pin_plat_label}\n"
        f"💰 Итого: {total}₽"
    )
    await reply_and_clean(
        message, state,
        preview,
        reply_markup=get_preview_keyboard(),
    )


async def _submit_ad(
    message: types.Message, state: FSMContext,
    data: dict, prices: dict, uid: str,
):
    """Отправляет заявку в БД через handle_ad_submit."""
    data = await state.get_data()
    dle_user_id = data.get("user_id")
    user_name = data.get("username", "Telegram user")
    calc_flow = data.get("ad_calc_flow", "feed")

    if calc_flow == "feed":
        platforms = data.get("ad_platforms", "site")
        days = data.get("ad_days", 1)
        pin_days = data.get("ad_pin_days", 0)
        pin_platforms = data.get("ad_pin_platforms")
        total_price = data.get("ad_total_price", 0) or _calc_ad_price(
            platforms, days, pin_days, prices, pin_platforms,
        )
        result = await handle_ad_submit(
            platform="telegram",
            platform_user_id=uid,
            text=data.get("ad_text", ""),
            platforms=platforms,
            days=days,
            pin=pin_days > 0,
            total_price=total_price,
            dle_user_id=dle_user_id,
            user_name=user_name,
            ad_type="feed",
            image_path=data.get("ad_image_path"),
            pin_days=pin_days,
            pin_platforms=pin_platforms,
        )
    elif calc_flow == "banner":
        placement = data.get("banner_placement", "in_news")
        price_key = f"banner_{placement}"
        months = data.get("banner_months", 1)
        opts = data.get("banner_opts", "")
        base_price = int(prices.get(price_key, {}).get("base_price", 0)) * months
        if opts:
            surcharge = prices.get(price_key, {}).get("surcharge_pct", 0.3)
            opts_count = len(opts.split(","))
            base_price = round(base_price * (1 + surcharge * opts_count))

        result = await handle_ad_submit(
            platform="telegram",
            platform_user_id=uid,
            text=data.get("banner_text", ""),
            platforms="site",
            days=0,
            pin=False,
            total_price=base_price,
            dle_user_id=dle_user_id,
            user_name=user_name,
            ad_type="banner",
            image_path=data.get("banner_image_path"),
            banner_size=data.get("banner_size", "728x90"),
            banner_placement=placement,
            banner_months=months,
            banner_opts=opts,
        )
    else:  # article
        fix_days = data.get("article_fix_days", 0)
        total_price = data.get("article_calc_price", 0)
        result = await handle_ad_submit(
            platform="telegram",
            platform_user_id=uid,
            text=data.get("article_text", ""),
            platforms="site",
            days=0,
            pin=False,
            total_price=total_price,
            dle_user_id=dle_user_id,
            user_name=user_name,
            ad_type="article",
            image_path=data.get("article_image_path"),
            article_eternal=data.get("article_eternal", False),
            article_opts="not_relevant" if data.get("article_not_relevant") else None,
            article_fix_days=fix_days,
        )

    await state.set_state(AuthState.main_menu)
    await reply_and_clean(
        message, state,
        f"✅ {result}",
        reply_markup=get_menu_keyboard(),
    )


# ============================================================
# 🔄 Обработчик кнопок пагинации поиска
# ============================================================

@dp.callback_query(F.data.startswith("search_go:"))
async def search_pagination(callback: CallbackQuery, state: FSMContext):
    """
    Пользователь нажал «◀️ Назад» или «▶️ Ещё» на результатах поиска.
    Редактируем то же самое сообщение (не создаём новое).
    """
    # Какую страницу запросил пользователь
    page = int(callback.data.split(":")[1])

    # Достаём данные поиска из FSM
    data = await state.get_data()
    query = data.get("search_query", "")
    total_pages = data.get("search_total_pages", 1)

    if not query:
        await callback.answer("❌ Поисковый запрос не найден. Начните заново.")
        return

    # Выполняем поиск с новой страницей
    search_result = await handle_search(
        "telegram", str(callback.from_user.id), query, page=page,
    )

    # Обновляем страницу в FSM
    await state.update_data(search_page=search_result.current_page)

    # Редактируем то же сообщение (вместо отправки нового)
    await callback.message.edit_text(
        search_result.text,
        reply_markup=get_search_keyboard(
            search_result.current_page,
            search_result.total_pages,
        ),
    )

    # Убираем «часики» на кнопке
    await callback.answer()


@dp.callback_query(F.data == "search_noop")
async def search_noop(callback: CallbackQuery):
    """
    Кнопка-счётчик страниц — ничего не делает.
    Просто убираем часики.
    """
    await callback.answer()


# ============================================================
# 🚀 Запуск бота
# ============================================================


async def start_telegram_bot():
    """
    Запускает Telegram-бота.
    Вызывается из main.py при старте приложения.

    Важно: бот создаётся здесь (а не при импорте), потому что aiogram
    проверяет токен сразу и падает, если токен — заглушка.
    """
    import logging
    log = logging.getLogger('tg_bot')

    global bot

    if not settings.TELEGRAM_BOT_TOKEN or "your_telegram" in settings.TELEGRAM_BOT_TOKEN:
        log.warning("Токен не задан или заглушка")
        print("⚠️ Telegram токен не задан или стоит заглушка — Telegram-бот не запущен")
        print("   Заполни TELEGRAM_BOT_TOKEN в .env настоящим токеном от @BotFather")
        return

    # Создаём бота с AiohttpSession (через SOCKS5 прокси)
    proxy = settings.TELEGRAM_PROXY or None
    log.info(f"Создаю бота, proxy={proxy}")
    if proxy:
        session = AiohttpSession(proxy=proxy)
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, session=session)
    else:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    log.info("Бот создан, проверяю get_me...")
    print("✅ Telegram-бот запущен!")
    if proxy:
        print(f"   Прокси: {proxy}")
    try:
        # get_me с тайм-аутом 15 сек
        me = await asyncio.wait_for(bot.get_me(), timeout=15)
        log.info(f"get_me OK: @{me.username}")
        print(f"   Юзернейм: @{me.username}")
    except asyncio.TimeoutError:
        log.error("get_me тайм-аут (15 сек)")
        print("❌ Ошибка get_me: тайм-аут 15 сек")
    except Exception as e:
        log.error(f"get_me ошибка: {e}")
        print(f"❌ Ошибка get_me: {e}")

    log.info("Запускаю polling...")
    try:
        # Удаляем старые вебхуки и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        # polling с тайм-аутом не сделать (он бесконечный)
        await dp.start_polling(bot, handle_signals=False)
    except Exception as e:
        log.error(f"Polling ошибка: {e}")
        print(f"❌ Ошибка Telegram-бота: {e}")
        print("   Проверь TELEGRAM_BOT_TOKEN в .env")
