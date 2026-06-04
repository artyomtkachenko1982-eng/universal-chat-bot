"""
schemas/user.py — Pydantic схемы

Pydantic проверяет данные: кто что прислал, правильный ли формат.
Это как «фильтр» на входе и «шаблон» на выходе.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# --------------------------------------------------
# Авторизация
# --------------------------------------------------

class AuthRequest(BaseModel):
    """Что присылает пользователь для входа"""
    platform: str        # "telegram", "vk", "web"
    platform_user_id: str  # его ID в платформе
    login: str           # логин на turbinist.ru
    password: str         # пароль
    anon_name: Optional[str] = None  # имя анонима (для привязки сообщений)


class AuthResponse(BaseModel):
    """Что бот отвечает после проверки логина"""
    success: bool
    message: str
    dle_user_id: Optional[int] = None
    dle_username: Optional[str] = None
    dle_group: Optional[int] = None
    dle_group_name: Optional[str] = None  # "Гость", "Инженер", "VIP", "ПРЕМИУМ"
    access_token: Optional[str] = None   # JWT-токен для дальнейших запросов


# --------------------------------------------------
# Профиль
# --------------------------------------------------

class UserProfile(BaseModel):
    """Профиль пользователя (показываем в боте)"""
    username: str
    user_id: int
    group_id: int
    group_name: str
    email: Optional[str] = None
    registration_date: Optional[str] = None


# --------------------------------------------------
# Поиск
# --------------------------------------------------

class SearchRequest(BaseModel):
    """Что прислал пользователь для поиска"""
    platform: str
    platform_user_id: str
    query: str           # что ищем
    page: int = 1        # номер страницы (для пагинации)
    smart: bool = False  # поиск с AI или обычный


class SearchResult(BaseModel):
    """Один результат поиска"""
    title: str
    description: Optional[str] = None
    url: str
    category: Optional[str] = None


class SearchResponse(BaseModel):
    """Ответ на поиск — несколько результатов"""
    query: str
    count: int
    results: list[SearchResult]
    has_access: bool     # есть ли у юзера доступ к результатам


# --------------------------------------------------
# AI вопросы (DeepSeek)
# --------------------------------------------------

class AiQuestion(BaseModel):
    """Вопрос к AI"""
    platform: str
    platform_user_id: str
    document_id: Optional[int] = None  # если вопрос по конкретному документу
    question: str


class AiAnswer(BaseModel):
    """Ответ от AI"""
    answer: str
    warning: Optional[str] = None  # предупреждение об оплате
    tokens_used: Optional[int] = None


# --------------------------------------------------
# Реклама
# --------------------------------------------------

class AdOrderRequest(BaseModel):
    """Заявка на рекламу"""
    platform: str
    platform_user_id: str
    dle_user_id: Optional[int] = None  # связь с юзером DLE
    user_name: Optional[str] = None  # имя юзера для отображения
    text: str
    ad_type: str = "feed"  # "feed" (объявление в ленте) или "banner" (баннер/статья)
    image_path: Optional[str] = None  # путь к загруженной картинке (если приложили)
    days: int = 1
    pin: bool = False
    pin_days: int = 0
    pin_platforms: Optional[str] = None  # площадки для закрепления: "tg,vk" / "site" / null=все
    article_eternal: bool = False  # вечная статья
    article_opts: Optional[str] = None  # опции статьи: "not_relevant,exchange,fixation"
    article_fix_days: int = 0  # фиксация в ленте (дней)
    article_months: int = 1  # количество месяцев для обычной статьи
    banner_size: str = "728x90"  # размер баннера
    banner_placement: str = "in_news"  # "all_pages" или "in_news"
    banner_months: int = 1  # количество месяцев
    banner_opts: Optional[str] = None  # опции баннера: "home,not_relevant,custom"
    platforms: str = "all"  # "site", "tg", "vk", "max", "all"
    total_price: float = 0.0


class AdPriceItem(BaseModel):
    """Одна строка из таблицы цен"""
    name: str
    price: float


# --------------------------------------------------
# Предложить новость
# --------------------------------------------------

class NewsSuggestionRequest(BaseModel):
    """Предложение новости от пользователя"""
    platform: str
    platform_user_id: str
    dle_user_id: Optional[int] = None  # связь с юзером DLE
    user_name: Optional[str] = None  # имя юзера для отображения
    title: str
    text: str


# --------------------------------------------------
# Статистика
# --------------------------------------------------

class UserStatsResponse(BaseModel):
    """Статистика пользователя"""
    total_searches: int = 0
    total_ai_questions: int = 0
    total_downloads: int = 0
    suggested_news: int = 0
    posts_count: int = 0
    comments_count: int = 0
