"""
Browser Controller — «глаза и руки» для Claude.
Управляет headless Chromium через Playwright.

Этот модуль НЕ зависит от FastAPI бота.
Используется скриптом browser_agent.py.
"""
import os
import asyncio
import uuid
from playwright.async_api import async_playwright

# Глобальные переменные (живут пока запущен browser_agent.py)
_browser = None
_page = None
_screenshots_dir = None


def _get_screenshots_dir():
    """Папка для скриншотов — внутри контейнера, монтируется с хоста."""
    global _screenshots_dir
    if _screenshots_dir is None:
        # /app = корень проекта (монтируется docker-compose)
        base = os.environ.get("PROJECT_ROOT", "/app")
        _screenshots_dir = os.path.join(base, "screenshots")
        os.makedirs(_screenshots_dir, exist_ok=True)
    return _screenshots_dir


async def get_page():
    """Возвращает страницу виджета (создаёт при первом вызове)."""
    global _browser, _page
    if _page is None:
        p = await async_playwright().start()
        _browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        _page = await _browser.new_page(viewport={"width": 420, "height": 700})
        await _page.goto("http://localhost:8080/widget", wait_until="networkidle")
        # Ждём загрузку React (Babel CDN может быть медленным)
        await _page.wait_for_timeout(4000)
        # Дополнительно: ждём появления хотя бы одной кнопки
        try:
            await _page.locator("button").first.wait_for(state="visible", timeout=10000)
        except:
            pass
    return _page


async def click_button(label: str) -> dict:
    """Кликает по кнопке с указанным текстом."""
    page = await get_page()
    try:
        # Ищем кнопку: сначала точное совпадение, потом contains
        btn = page.locator(f"button:has-text('{label}')").first
        await btn.click(timeout=5000)
        await page.wait_for_timeout(800)  # Ждём рендер React
        path = await take_screenshot()
        return {"status": "ok", "clicked": label, "screenshot": path}
    except Exception as e:
        # Пробуем скриншот даже при ошибке
        try:
            path = await take_screenshot()
            return {"status": "ok", "clicked": label, "screenshot": path, "warning": str(e)}
        except:
            return {"status": "error", "message": str(e)}


async def type_text(text: str, index: int = 0) -> dict:
    """Вводит текст в поле ввода (index: 0=первое, 1=второе...)."""
    page = await get_page()
    try:
        # Ищем любое текстовое поле, берём по индексу
        field = page.locator('input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="hidden"]), textarea').nth(index)
        await field.fill(text)
        path = await take_screenshot()
        return {"status": "ok", "typed": text, "screenshot": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def press_enter() -> dict:
    """Нажимает Enter (отправка текста)."""
    page = await get_page()
    try:
        field = page.locator('input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):not([type="hidden"]), textarea').first
        await field.press("Enter")
        await page.wait_for_timeout(800)
        path = await take_screenshot()
        return {"status": "ok", "action": "enter", "screenshot": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def take_screenshot() -> str:
    """Делает скриншот и возвращает путь к файлу."""
    page = await get_page()
    filename = f"screenshot_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(_get_screenshots_dir(), filename)
    await page.screenshot(path=filepath, full_page=False)
    return filepath


async def get_text() -> dict:
    """Читает весь текст со страницы."""
    page = await get_page()
    try:
        text = await page.locator("body").inner_text()
        return {"status": "ok", "text": text[:5000]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def execute_js(code: str) -> dict:
    """
    Выполняет произвольный JavaScript в контексте страницы.
    Только для разработчика (порт 8081 не exposed наружу).
    """
    page = await get_page()
    try:
        result = await page.evaluate(code)
        path = await take_screenshot()
        return {"status": "ok", "result": str(result)[:2000], "screenshot": path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def reset_browser():
    """Сбрасывает браузер (закрывает и открывает заново)."""
    global _browser, _page
    if _browser:
        try:
            await _browser.close()
        except:
            pass
    _browser = None
    _page = None
    return {"status": "ok", "message": "Браузер сброшен"}
