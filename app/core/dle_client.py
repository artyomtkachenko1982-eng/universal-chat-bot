"""
dle_client.py — HTTP-клиент для общения с PHP-мостиком DLE

Делает запросы к api-bot-bridge.php на turbinist.ru.
Мостик уже вызывает DLE API и возвращает JSON.
"""

import httpx
from app.core.config import settings


class DLEClient:
    """Клиент для DLE API через PHP-мостик"""

    def __init__(self):
        # Базовый URL мостика (из .env)
        self.base_url = settings.DLE_API_URL
        # Токен для проверки, что это наш бот стучится
        self.token = settings.DLE_API_TOKEN
        # Таймаут запроса (секунды)
        self.timeout = 10.0

    def _headers(self) -> dict:
        """Собираем заголовки для каждого запроса"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _post(self, action: str, params: list) -> dict:
        """
        Отправляет POST-запрос к мостику.

        action — что мы хотим сделать (external_auth, take_user_by_name, ...)
        params — список аргументов [как в DLE API]
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.base_url,
                json={"action": action, "params": params},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    # --------------------------------------------------
    # Основные методы (соответствуют функциям DLE API)
    # --------------------------------------------------

    async def external_auth(self, login: str, password: str) -> dict:
        """
        Проверка логина/пароля.
        DLE API: external_auth(login, password)
        """
        return await self._post("external_auth", [login, password])

    async def take_user_by_name(self, name: str) -> dict:
        """
        Получить данные пользователя по логину.
        DLE API: take_user_by_name(name)
        """
        return await self._post("take_user_by_name", [name])

    async def take_user_by_email(self, email: str) -> dict:
        """
        Получить данные пользователя по email.
        DLE API: take_user_by_email(email)
        """
        return await self._post("take_user_by_email", [email])

    async def take_user_by_id(self, user_id: int) -> dict:
        """
        Получить данные пользователя по ID.
        DLE API: take_user_by_id(user_id)
        Передаём "*" как select_list, чтобы получить ВСЕ поля (включая expire).
        """
        return await self._post("take_user_by_id", [user_id, "*"])

    async def external_register(
        self, login: str, password: str, email: str, group: int,
        reg_date=None, catlist=0, question=0, answer=1
    ) -> dict:
        """
        Зарегистрировать нового пользователя.
        DLE API: external_register(login, password, email, group, reg_date, catlist, question, answer)
        """
        return await self._post("external_register", [login, password, email, group, reg_date, catlist, question, answer])

    async def take_news(self, cat: str = "", limit: int = 10, start: int = 0) -> dict:
        """
        Получить новости по категориям.
        DLE API: take_news(cat, fields, start, limit)
        """
        return await self._post("take_news", [cat, '*', start, limit])

    async def send_pm_to_user(
        self, user_id: int, subject: str, text: str, from_user: str
    ) -> dict:
        """
        Отправить личное сообщение пользователю на сайте.
        DLE API: send_pm_to_user(user_id, subject, text, from)
        """
        return await self._post("send_pm_to_user", [user_id, subject, text, from_user])

    def _where(self, query: str) -> str:
        """Собирает WHERE-условие для поиска по заголовку и тексту"""
        safe = str(query).replace("'", "\\'")
        return f"title LIKE '%{safe}%' OR short_story LIKE '%{safe}%' OR full_story LIKE '%{safe}%'"

    async def search_news_count(self, query: str) -> int:
        """
        Точное количество новостей по запросу.
        DLE API: load_table("dle_post", "COUNT(*)", "WHERE")
        """
        result = await self._post(
            "load_table",
            ["dle_post", "COUNT(*)", self._where(query)],
        )
        data = result.get("data", {})
        if isinstance(data, dict):
            return int(data.get("COUNT(*)", 0))
        return 0

    async def search_news(
        self, query: str, limit: int = 5, offset: int = 0
    ) -> dict:
        """
        Поиск новостей по заголовку и краткому тексту.
        DLE API: load_table("dle_post", "поля", "WHERE", "сортировка", offset, limit)

        query  — поисковый запрос
        limit  — сколько результатов вернуть
        offset — смещение (для стр.2: offset=5, для стр.3: offset=10)
        """
        return await self._post(
            "load_table",
            [
                "dle_post",                          # таблица новостей
                "id,title,alt_name,short_story,full_story,date",  # нужные поля
                self._where(query),                 # условие поиска
                "date DESC",                        # сортировка: новые сверху
                str(offset),                        # смещение
                str(limit),                         # сколько вернуть
            ],
        )


    async def call(self, action: str, params: list) -> dict:
        """Универсальный вызов любого DLE API метода"""
        return await self._post(action, params)


# Один экземпляр на всё приложение
dle_client = DLEClient()
