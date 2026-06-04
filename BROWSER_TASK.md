# 🎮 «Глаза и руки» для Claude — спецификация

> **Кому:** другому чату Claude  
> **Задача:** дать Claude возможность видеть и управлять чат-виджетом (кликать, вводить текст, делать скриншоты)  
> **Срок:** реализовать за 1 сессию

---

## 1. ЗАЧЕМ ЭТО НУЖНО

Claude работает в изолированной Linux VM без браузера. Он не может:
- Открыть `index.html` чат-виджета и посмотреть как он выглядит
- Нажать кнопки и проверить что они работают
- Увидеть результат своих правок в коде
- Оценить визуал: размеры, пропорции, цвета

**Решение:** Playwright + headless Chromium внутри Docker-контейнера. Claude через bash запускает команды и получает скриншоты.

---

## 2. ЧТО ИМЕЕМ СЕЙЧАС

### Проект
- FastAPI (Python) в Docker-контейнере `uc_app`
- PostgreSQL, Redis в соседних контейнерах
- Виджет: `app/widgets/chat/index.html` (React 18 + Tailwind, загружается через Babel CDN)
- Виджет подключается к API на `http://localhost:8080`

### Что уже работает
- Авторизация через DLE API (тестовый юзер: `test_login` / `1234567890`, DLE ID 286601)
- Главное меню (кнопки: Поиск, Профиль, Реклама, Новость, Админу, Настройки, Статистика, Каналы, Обращения)
- Три типа рекламы с калькуляторами (Объявление / Баннер / Статья)
- Загрузка картинок
- Админ-панель с разделами (Реклама, Новости, Сообщения, Архив)

### Что уже добавлено для раздачи виджета
- Роут `GET /widget` в `main.py` — отдаёт `index.html` как HTML
- `from fastapi.responses import HTMLResponse` уже импортирован

### Ограничения
- Браузер НЕДОСТУПЕН (Claude in Chrome расширение не работает)
- Все тесты только через `mcp__bash__run` (Windows bash, не Linux VM)
- Сервер перезапускается: `docker restart uc_app`
- Рейт-лимит сбрасывается: `docker exec uc_redis redis-cli DEL "rate:auth:<IP>"`

---

## 3. ТЕХНИЧЕСКОЕ РЕШЕНИЕ

### Архитектура

```
Claude (bash)
    │
    ├─ curl /api/browser/open       → открывает виджет в Playwright
    ├─ curl /api/browser/click      → кликает по кнопке
    ├─ curl /api/browser/type       → вводит текст
    ├─ curl /api/browser/screenshot → сохраняет скриншот
    └─ curl /api/browser/text       → читает текст со страницы
           │
           ▼
    Playwright (headless Chromium) внутри uc_app
           │
           ▼
    localhost:8080/widget
```

### Почему Playwright внутри uc_app (а не отдельный контейнер)?
- Виджет на `localhost:8080/widget` — доступен изнутри контейнера
- Не нужно настраивать сеть между контейнерами
- Меньше движущихся частей

### Файлы которые нужно создать/изменить

| Файл | Что |
|---|---|
| `app/services/browser_controller.py` | Новый модуль — управление Playwright |
| `app/main.py` | Добавить 5 эндпоинтов для браузера |
| `requirements.txt` | Добавить `playwright` |
| `Dockerfile` | Установить Chromium + зависимости |

---

## 4. КОНКРЕТНЫЕ ШАГИ РЕАЛИЗАЦИИ

### Шаг 1: Установка Playwright в Docker

**В Dockerfile добавить:**
```dockerfile
# Установка Chromium для Playwright
RUN pip install playwright --break-system-packages
RUN playwright install --with-deps chromium
```

**Или быстро (без пересборки):**
```bash
docker exec uc_app pip install playwright --break-system-packages
docker exec uc_app playwright install --with-deps chromium
```

Если `playwright install` не работает внутри контейнера, установи системные зависимости:
```bash
docker exec uc_app playwright install-deps chromium
docker exec uc_app playwright install chromium
```

### Шаг 2: Модуль browser_controller.py

Создать `app/services/browser_controller.py`:

```python
"""
Browser Controller — «глаза и руки» для Claude.
Управляет headless Chromium через Playwright.
"""
import os
import asyncio
from playwright.async_api import async_playwright

# Глобальные переменные (живут пока жив сервер)
_browser = None
_page = None
_screenshots_dir = None


def _get_screenshots_dir():
    """Папка для скриншотов — в проекте, доступна Claude."""
    global _screenshots_dir
    if _screenshots_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        _screenshots_dir = os.path.join(base, "screenshots")
        os.makedirs(_screenshots_dir, exist_ok=True)
    return _screenshots_dir


async def get_page():
    """Возвращает страницу виджета (создаёт при первом вызове)."""
    global _browser, _page
    if _page is None:
        p = await async_playwright().start()
        _browser = await p.chromium.launch(headless=True)
        _page = await _browser.new_page(viewport={"width": 420, "height": 700})
        await _page.goto("http://localhost:8080/widget", wait_until="networkidle")
    return _page


async def click_button(label: str) -> dict:
    """Кликает по кнопке с указанным текстом."""
    page = await get_page()
    try:
        # Ищем кнопку по тексту (точное совпадение или содержит)
        btn = page.locator(f"button:has-text('{label}')").first
        await btn.click(timeout=5000)
        await page.wait_for_timeout(500)  # Ждём реакцию React
        path = await take_screenshot()
        return {"status": "ok", "clicked": label, "screenshot": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def type_text(text: str) -> dict:
    """Вводит текст в активное поле ввода."""
    page = await get_page()
    try:
        # Ищем input или textarea
        field = page.locator('input[type="text"], input:not([type]), textarea').first
        await field.fill(text)
        path = await take_screenshot()
        return {"status": "ok", "typed": text, "screenshot": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def press_enter() -> dict:
    """Нажимает Enter (отправка текста)."""
    page = await get_page()
    try:
        field = page.locator('input[type="text"], input:not([type]), textarea').first
        await field.press("Enter")
        await page.wait_for_timeout(500)
        path = await take_screenshot()
        return {"status": "ok", "action": "enter", "screenshot": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def take_screenshot() -> str:
    """Делает скриншот и возвращает путь к файлу."""
    page = await get_page()
    import uuid
    filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(_get_screenshots_dir(), filename)
    await page.screenshot(path=filepath, full_page=False)
    return filepath


async def get_text() -> dict:
    """Читает весь текст со страницы."""
    page = await get_page()
    try:
        text = await page.locator("body").inner_text()
        return {"status": "ok", "text": text[:3000]}  # Ограничиваем
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def reset_browser():
    """Сбрасывает браузер (перезагружает страницу)."""
    global _browser, _page
    if _browser:
        await _browser.close()
    _browser = None
    _page = None
    return {"status": "ok", "message": "Браузер сброшен"}
```

### Шаг 3: Эндпоинты в main.py

Добавить в `app/main.py`:

```python
# Импорт в начале файла
from app.services.browser_controller import (
    click_button, type_text, press_enter, take_screenshot, get_text, reset_browser
)

# Эндпоинты
@app.get("/api/browser/open")
async def api_browser_open():
    """Открыть виджет (сбросить и загрузить заново)."""
    await reset_browser()
    from app.services.browser_controller import get_page
    await get_page()
    path = await take_screenshot()
    return {"status": "ok", "screenshot": path}

@app.get("/api/browser/click")
async def api_browser_click(label: str):
    """Кликнуть по кнопке."""
    return await click_button(label)

@app.get("/api/browser/type")
async def api_browser_type(text: str):
    """Ввести текст."""
    return await type_text(text)

@app.get("/api/browser/enter")
async def api_browser_enter():
    """Нажать Enter."""
    return await press_enter()

@app.get("/api/browser/screenshot")
async def api_browser_screenshot():
    """Только скриншот текущего состояния."""
    path = await take_screenshot()
    return {"status": "ok", "screenshot": path}

@app.get("/api/browser/text")
async def api_browser_text():
    """Прочитать текст на странице."""
    return await get_text()
```

### Шаг 4: requirements.txt

Добавить строку:
```
playwright>=1.40.0
```

---

## 5. КАК ЭТО БУДЕТ РАБОТАТЬ (пример сессии)

```bash
# 1. Открываем виджет
curl http://localhost:8080/api/browser/open
# → {"status":"ok","screenshot":"/path/to/screenshots/abc123.png"}

# 2. Claude читает скриншот: Read("abc123.png") → видит главное меню

# 3. Жмём «Реклама»
curl "http://localhost:8080/api/browser/click?label=Реклама"
# → скриншот экрана выбора типа рекламы

# 4. Жмём «Баннер»
curl "http://localhost:8080/api/browser/click?label=БАННЕР"
# → скриншот выбора размера баннера

# 5. Читаем текст (что бот написал)
curl http://localhost:8080/api/browser/text
# → {"text":"🖼 БАННЕР — выберите размер:\n..."}

# 6. Жмём размер
curl "http://localhost:8080/api/browser/click?label=728x90"
# → следующий шаг
```

---

## 6. ВОЗМОЖНЫЕ ПРОБЛЕМЫ

| Проблема | Решение |
|---|---|
| `playwright install` падает в Docker | `playwright install-deps chromium` сначала |
| Chromium не хватает памяти | Добавить `--disable-dev-shm-usage` в launch |
| Виджет долго грузится (Babel CDN) | `wait_until="networkidle"` уже учтено |
| Кнопка не найдена по тексту | Использовать `has-text()` и более точные селекторы |
| React не обновился после клика | `wait_for_timeout(500)` — пауза на рендер |

---

## 7. ПРОВЕРКА РЕЗУЛЬТАТА

После реализации Claude должен суметь:
1. ✅ Открыть виджет — увидеть скриншот главного меню
2. ✅ Пройти полный flow рекламы (нажимая кнопки) — видеть каждый шаг
3. ✅ Прочитать текст сообщений бота
4. ✅ Оценить визуал: размеры кнопок, цвета, расположение

---

**Конец спецификации.**
