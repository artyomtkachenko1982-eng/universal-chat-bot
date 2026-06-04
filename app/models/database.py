"""
database.py — SQLAlchemy модели

Описывает таблицы в PostgreSQL.
Каждый класс = одна таблица.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Integer, DateTime, Text, Float, Boolean,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column,
    sessionmaker,
)

# --------------------------------------------------
# Базовая настройка
# --------------------------------------------------

class Base(DeclarativeBase):
    """Основа для всех моделей. Все таблицы наследуются от неё."""
    pass


# --------------------------------------------------
# Таблицы
# --------------------------------------------------

class BotUser(Base):
    """
    Пользователь бота.
    Храним связку: platform_user_id → dle_user_id.
    """
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))          # "telegram", "vk", "web"
    platform_user_id: Mapped[str] = mapped_column(String(100))  # ID в платформе
    dle_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dle_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dle_group: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    session_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)  # Архивирован ли чат пользователя
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserState(Base):
    """
    FSM — машина состояний.
    Храним на каком шаге находится пользователь (ввод логина, выбор тарифа...)
    """
    __tablename__ = "user_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))
    platform_user_id: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(50))   # "start", "waiting_login", "waiting_password"...
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # временные данные (JSON)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class AdRequest(Base):
    """
    Заявка на рекламу.
    Пользователь заполняет форму → сохраняется сюда → админ видит.
    """
    __tablename__ = "ad_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))
    platform_user_id: Mapped[str] = mapped_column(String(100))
    dle_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # связь с юзером DLE
    user_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # имя юзера (для админки)
    text: Mapped[str] = mapped_column(Text)
    ad_type: Mapped[str] = mapped_column(String(20), default="ad")  # "ad" (объявление) или "banner" (баннер)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # путь к загруженной картинке
    days: Mapped[int] = mapped_column(default=1)
    pin: Mapped[bool] = mapped_column(default=False)       # закрепление (есть/нет)
    pin_days: Mapped[int] = mapped_column(default=0)       # на сколько дней закрепление
    pin_platforms: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # площадки закрепления: "tg,vk,site" или null = все
    article_eternal: Mapped[bool] = mapped_column(default=False)  # вечная статья (без срока)
    article_opts: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # опции статьи: "not_relevant,exchange,fixation"
    article_fix_days: Mapped[int] = mapped_column(default=0)  # фиксация в ленте (дней)
    article_months: Mapped[int] = mapped_column(default=1)  # количество месяцев для обычной статьи
    banner_size: Mapped[str] = mapped_column(String(20), default="728x90")  # размер баннера
    banner_placement: Mapped[str] = mapped_column(String(20), default="in_news")  # "all_pages" или "in_news"
    banner_months: Mapped[int] = mapped_column(default=1)  # количество месяцев
    banner_opts: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # опции баннера: "home,not_relevant,custom"
    platform_target: Mapped[str] = mapped_column(String(100))  # "all", "site", "tg", "vk", "max"
    total_price: Mapped[float] = mapped_column(Float)
    corrected_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # если админ скорректировал
    admin_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(default="new")     # "new", "approved", "rejected", "paid", "done"
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NewsSuggestion(Base):
    """
    Предложенная новость.
    Пользователь может предложить новость админу.
    """
    __tablename__ = "news_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))
    platform_user_id: Mapped[str] = mapped_column(String(100))
    dle_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # связь с юзером DLE
    user_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # имя юзера (для админки)
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # путь к картинке
    admin_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(default="new")  # "new", "approved", "rejected"
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AdminMessage(Base):
    """
    Сообщение админу.
    Пользователь может написать вопрос / предложение напрямую админу.
    """
    __tablename__ = "admin_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))          # "vk", "telegram", "web"
    platform_user_id: Mapped[str] = mapped_column(String(100))  # ID отправителя
    dle_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # связь с юзером DLE
    user_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Имя с сайта
    sender_type: Mapped[str] = mapped_column(String(10), default="user")  # "user" или "admin"
    topic: Mapped[str] = mapped_column(String(50), default="question")  # "question", "ad", "news"
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="new")  # "new", "in_progress", "answered"
    admin_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Ответ админа
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)  # Архивирован ли чат


class AdPrice(Base):
    """
    Настраиваемые цены рекламы.
    Админ может менять цены через интерфейс.
    Каждая запись — одна ценовая позиция (price_key).
    """
    __tablename__ = "ad_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    price_key: Mapped[str] = mapped_column(String(50), unique=True)  # "feed_site", "banner_all_pages"...
    price_name: Mapped[str] = mapped_column(String(200))              # Человеческое название
    base_price: Mapped[float] = mapped_column(Float, default=0)       # Базовая цена в рублях
    surcharge_pct: Mapped[float] = mapped_column(Float, default=0)    # Доп. наценка (0.3 = 30%)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserStats(Base):
    """
    Статистика пользователя.
    Считаем что юзер делал в боте.
    """
    __tablename__ = "user_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))
    platform_user_id: Mapped[str] = mapped_column(String(100))
    total_searches: Mapped[int] = mapped_column(default=0)
    total_ai_questions: Mapped[int] = mapped_column(default=0)
    total_downloads: Mapped[int] = mapped_column(default=0)
    suggested_news: Mapped[int] = mapped_column(default=0)
    posts_count: Mapped[int] = mapped_column(default=0)
    comments_count: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
