"""
dependencies.py — FastAPI-зависимости для безопасности

Что такое «зависимость» (dependency) в FastAPI?
Это функция, которая выполняется ПЕРЕД каждым запросом.
Например: «прежде чем показать профиль — проверь, что у пользователя есть токен».

Здесь живут:
- get_current_user — проверка JWT-токена (для веб-виджета)
- rate_limit — ограничение частоты запросов
"""

from fastapi import Request, HTTPException, Header, Depends
from app.core.security import verify_jwt_token
from app.core.rate_limiter import check_rate_limit


# --------------------------------------------------
# JWT-зависимость: проверка токена
# --------------------------------------------------


async def get_current_user(
    request: Request,
    authorization: str = Header(None),
) -> dict:
    """
    Проверяет JWT-токен из заголовка Authorization.

    Как это работает:
    1. Читает заголовок "Authorization: Bearer eyJhbGci..."
    2. Достаёт токен
    3. Проверяет через verify_jwt_token()
    4. Если токен ОК — возвращает данные пользователя
    5. Если нет — ошибка 401 «Не авторизован»

    Использование в маршрутах:
        @app.get("/api/profile")
        async def profile(user=Depends(get_current_user)):
            # user = {"user_id": "123", "username": "turbinist_user", ...}
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Формат: "Bearer eyJhbGciOi..."
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Неверный формат токена")

    token = parts[1]
    user = verify_jwt_token(token)

    if user is None:
        raise HTTPException(status_code=401, detail="Токен недействителен или просрочен")

    return user


# --------------------------------------------------
# Rate Limiting зависимость
# --------------------------------------------------

# Словарь: тип запроса → соответствующий лимит
LIMIT_MAP = {
    "/api/auth": "auth",
    "/api/search": "search",
    "/api/ai": "ai",
}


async def rate_limit(
    request: Request,
    limit_type: str = None,
):
    """
    Ограничивает частоту запросов.

    Если лимит превышен — выбрасывает ошибку 429 «Слишком много запросов».

    Использование:
        @app.post("/api/auth")
        async def auth(request: Request, _=Depends(lambda: rate_limit(request, "auth"))):
            ...
    """
    # Определяем тип лимита: либо задан явно, либо по URL
    if limit_type is None:
        limit_type = LIMIT_MAP.get(request.url.path, "global")

    # Ключ: IP-адрес пользователя
    client_ip = request.client.host if request.client else "unknown"

    allowed, remaining = await check_rate_limit(client_ip, limit_type)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Подождите немного и попробуйте снова.",
        )

    # Добавляем заголовки в ответ (для информации)
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_type = limit_type
