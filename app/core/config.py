"""
config.py — Все настройки бота

Этот файл читает переменные из .env и собирает их в один объект.
В коде везде используем `settings.DLE_API_URL`, `settings.POSTGRES_HOST` и т.д.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Главный класс настроек. Каждое поле = одна переменная из .env"""

    # --- DLE API ---
    DLE_API_URL: str = "https://www.turbinist.ru/api-bot-bridge.php"
    DLE_API_TOKEN: str = ""

    # --- PostgreSQL ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "universal_chat"
    POSTGRES_USER: str = "bot_user"
    POSTGRES_PASSWORD: str = "change_me_please"

    @property
    def DATABASE_URL(self) -> str:
        """Собирает полную строку подключения к PostgreSQL"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    @property
    def REDIS_URL(self) -> str:
        """Собирает полную строку подключения к Redis"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_PROXY: Optional[str] = None  # socks5://host:port (для РФ)

    # --- VK ---
    VK_BOT_TOKEN: Optional[str] = None
    VK_GROUP_ID: Optional[int] = None

    # --- WebSocket (чат-виджет) ---
    WS_HOST: str = "0.0.0.0"
    WS_PORT: int = 8080

    # --- DeepSeek AI ---
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/v1/chat/completions"

    # --- Администратор ---
    ADMIN_USER_ID: int = 1  # Твой dle_user_id на сайте (супер-админ)
    ADMIN_VK_ID: Optional[int] = None  # Твой VK user_id для уведомлений
    ADMIN_TELEGRAM_ID: Optional[int] = None  # Твой Telegram chat_id для уведомлений
    ADMIN_NOTIFY_CHANNEL: str = "vk"  # "vk" или "telegram" — куда слать уведомления

    # --- Режим демо (только тестовые пользователи) ---
    DEMO_MODE: bool = False
    ALLOWED_USERS: str = "286601,1"  # dle_user_id через запятую

    # --- Управление через API (Deploy Bridge) ---
    MANAGE_TOKEN: str = "d8p0BxQ38oxGkrN2Ab918qj7ph1hDbxP"

    # --- Безопасность ---
    SECRET_KEY: str = "dev_secret_change_me"
    DEBUG: bool = True

    class Config:
        # Говорим pydantic читать настройки из файла .env
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Названия в .env могут быть любым регистром
        case_sensitive = False


# Создаём один экземпляр — будем его импортировать везде
settings = Settings()
