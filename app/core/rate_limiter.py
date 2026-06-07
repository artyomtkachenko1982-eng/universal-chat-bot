"""
rate_limiter.py — Ограничение частоты запросов (Rate Limiting)

Что делает этот файл:
1. Считает запросы от каждого пользователя/IP
2. Блокирует, если слишком много запросов за короткое время
3. Использует Redis для хранения счётчиков

Зачем это нужно:
- Защита от перебора паролей (brute force)
- Защита от DDoS (лавина запросов)
- Защита от накрутки (спам поисковыми запросами)

Как работает:
Представь, что Redis — это доска с записями мелом.
Каждый раз, когда кто-то делает запрос, мы ставим палочку напротив его IP.
Если палочек больше, чем разрешено — отказ.
Через N секунд палочки стираются.
"""

import time
import redis.asyncio as aioredis
from app.core.config import settings

# --------------------------------------------------
# Правила (лимиты)
# --------------------------------------------------

# Ключ: название правила
# Значение: (макс_запросов, за_сколько_секунд)
RULES = {
    # 🔐 АВТОРИЗАЦИЯ — не больше 5 попыток за 15 минут
    "auth": (5, 15 * 60),
    # 🔍 ПОИСК — не больше 30 запросов в минуту
    "search": (30, 60),
    # 🤖 AI — не больше 10 вопросов в минуту
    "ai": (10, 60),
    # Регистрация — не больше 3 за час
    "register": (3, 3600),
    # 📊 ВСЕ ЗАПРОСЫ — не больше 100 в минуту с одного IP
    "global": (100, 60),
}


# --------------------------------------------------
# Подключение к Redis
# --------------------------------------------------


async def _get_redis() -> aioredis.Redis:
    """Создаёт или возвращает подключение к Redis."""
    return aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


# --------------------------------------------------
# Основная функция: проверка лимита
# --------------------------------------------------


async def check_rate_limit(
    key: str,
    limit_type: str = "global",
) -> tuple[bool, int]:
    """
    Проверяет: превышен ли лимит запросов?

    Аргументы:
        key: уникальный идентификатор (например IP-адрес или user_id)
        limit_type: тип лимита ("auth", "search", "ai", "global")

    Возвращает:
        (разрешено_ли, сколько_осталось_попыток)
        — (True, 5) — можно, осталось 5 попыток
        — (False, 0) — нельзя, лимит исчерпан
    """
    max_requests, window_seconds = RULES.get(limit_type, RULES["global"])

    try:
        redis = await _get_redis()
    except Exception:
        # Если Redis не доступен — пропускаем запрос (не блокируем работу)
        return True, max_requests

    # Уникальное имя ключа в Redis
    redis_key = f"rate:{limit_type}:{key}"

    try:
        current = await redis.get(redis_key)

        if current is None:
            # Первый запрос за период
            await redis.setex(redis_key, window_seconds, 1)
            return True, max_requests - 1

        current = int(current)

        if current >= max_requests:
            # Лимит превышен
            ttl = await redis.ttl(redis_key)
            return False, 0

        # Всё ок, увеличиваем счётчик
        await redis.incr(redis_key)
        remaining = max_requests - current - 1
        return True, remaining

    except Exception:
        # Ошибка Redis — не блокируем пользователя
        return True, max_requests


# --------------------------------------------------
# Сброс лимита (для админа или тестов)
# --------------------------------------------------


async def reset_rate_limit(key: str, limit_type: str = "global"):
    """Сбрасывает счётчик для конкретного пользователя/IP."""
    try:
        redis = await _get_redis()
        redis_key = f"rate:{limit_type}:{key}"
        await redis.delete(redis_key)
    except Exception:
        pass
