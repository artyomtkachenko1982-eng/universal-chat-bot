"""
security.py — Безопасность: ключи, токены, хеши, JWT

Отвечает за:
- Создание случайных токенов (сессии)
- JWT-токены (для веб-виджета)
- Кеширование сессий в Redis
- Проверку что user_id пришёл не от клиента, а из нашей сессии
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from app.core.config import settings


def generate_token(length: int = 32) -> str:
    """
    Генерирует случайный токен.
    Используется для сессий пользователей (каждый заход в бота — новый токен).
    """
    return secrets.token_hex(length)


def hash_password(password: str) -> str:
    """
    Хеширует пароль перед отправкой в DLE.
    Используем SHA-256 с солью из секретного ключа.
    """
    salted = password + settings.SECRET_KEY
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_signature(payload: str, signature: str) -> bool:
    """
    Проверяет, что данные не были подменены.
    payload — строка данных
    signature — подпись, которую прислал клиент
    """
    expected = hmac.new(
        key=settings.SECRET_KEY.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def make_signature(payload: str) -> str:
    """
    Создаёт подпись для payload.
    Чтобы мостик знал, что запрос от нас.
    """
    return hmac.new(
        key=settings.SECRET_KEY.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


# ============================================================
# JWT-токены (для веб-виджета и API-запросов)
# ============================================================

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


def create_jwt_token(
    user_id: str,
    username: str,
    platform: str = "web",
    expires_hours: int = JWT_EXPIRE_HOURS,
) -> str:
    """
    Создаёт JWT-токен для пользователя веб-виджета.

    Что такое JWT?
    Это «пропуск» в виде длинной строки. Сервер его создал, сервер его и проверяет.
    Подделать нельзя — подпись создаётся нашим секретным ключом SECRET_KEY.

    Аргументы:
        user_id: ID пользователя в DLE (например "12345")
        username: Логин (например "turbinist_user")
        platform: Платформа (web, telegram, vk)
        expires_hours: Через сколько часов токен протухнет (по умолчанию 24)

    Возвращает:
        Строка-токен (например "eyJhbGciOi...")
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=expires_hours)

    # Данные, которые мы запаковываем в токен
    payload = {
        "sub": user_id,                       # кто владелец токена
        "username": username,                 # для удобства
        "platform": platform,                 # откуда пришёл
        "iat": int(now.timestamp()),          # когда создан
        "exp": int(expire.timestamp()),       # когда протухнет
    }

    secret = settings.SECRET_KEY or "dev-secret-change-me"
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[dict]:
    """
    Проверяет JWT-токен.

    Возвращает:
        Словарь {"user_id": ..., "username": ..., "platform": ...} — если токен ОК
        None — если токен просрочен, подделан или битый
    """
    secret = settings.SECRET_KEY or "dev-secret-change-me"

    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "platform": payload.get("platform"),
        }
    except JWTError:
        return None
