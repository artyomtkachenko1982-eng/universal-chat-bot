"""
browser_test.py — автоматическое тестирование виджета через браузерный агент.

Запуск внутри контейнера:
    python /app/browser_test.py

Запуск через батник (с хоста):
    docker exec uc_app python /app/browser_test.py

Результаты сохраняются в папку:
    /app/screenshots/test_{дата}/
"""

import os
import json
import http.client
import urllib.parse
import urllib.request
from datetime import datetime
import time
import sys
import traceback

HOST = "localhost"
PORT = 8081
API_PORT = 8080
ADMIN_ID = 1
TEST_LOGIN = "test_login"
TEST_PASS = "1234567890"

# === Утилиты ===

def get(path, timeout=20):
    """GET-запрос к браузерному агенту."""
    c = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read().decode()
    try:
        return r.status, json.loads(body)
    except:
        return r.status, body


def get_raw(path, timeout=30):
    """GET-запрос к браузерному агенту, сырой ответ."""
    c = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read()
    return r.status, body


def api_get(endpoint, params=""):
    """GET-запрос к основному API (проверка данных)."""
    url = f"http://localhost:{API_PORT}{endpoint}?{params}"
    try:
        r = urllib.request.urlopen(url, timeout=10)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def q(text):
    """URL-encode для кириллических параметров."""
    return urllib.parse.quote(text)


def save(filename, content, outdir):
    """Сохранить файл."""
    path = os.path.join(outdir, filename)
    mode = "w" if isinstance(content, str) else "wb"
    with open(path, mode, encoding="utf-8" if mode == "w" else None) as f:
        f.write(content)
    return path


# === Тесты ===

def test_open(outdir):
    """1. Открыть виджет с нуля."""
    print("\n  🔄 Открытие виджета...", end=" ", flush=True)
    try:
        status, data = get("/open", timeout=30)
        if status == 200:
            print(f"✅ (скриншот: {data.get('screenshot', '?')})")
            return True, data
        else:
            print(f"❌ {status}: {data}")
            return False, data
    except Exception as e:
        print(f"❌ {e}")
        return False, str(e)


def test_screenshot(outdir):
    """2. Скриншот."""
    print("  📸 Скриншот...", end=" ", flush=True)
    try:
        status, data = get("/screenshot", timeout=20)
        if status == 200:
            spath = data.get("screenshot", "")
            # Копируем в папку отчёта
            if spath and os.path.exists(spath):
                import shutil
                shutil.copy2(spath, os.path.join(outdir, "01_screenshot.png"))
            print(f"✅ {spath}")
            return True, data
        else:
            print(f"❌ {status}")
            return False, data
    except Exception as e:
        print(f"❌ {e}")
        return False, str(e)


def test_layout(outdir):
    """3. SVG-раскладка страницы (может «видеть» UI)."""
    print("  📐 SVG-раскладка...", end=" ", flush=True)
    try:
        status, data = get("/layout", timeout=30)
        if status == 200:
            lpath = data.get("layout", "")
            if lpath and os.path.exists(lpath):
                import shutil
                shutil.copy2(lpath, os.path.join(outdir, "02_layout.svg"))
            print(f"✅ ({data.get('elements', '?')} элементов)")
            return True, data
        else:
            print(f"❌ {status}")
            return False, data
    except Exception as e:
        print(f"❌ {e}")
        return False, str(e)


def test_analyze(outdir):
    """4. Анализ страницы (кнопки, инпуты, цвета, контраст)."""
    print("  🔍 Анализ интерфейса...", end=" ", flush=True)
    try:
        status, data = get("/analyze", timeout=30)
        if status == 200 and data.get("status") == "ok":
            analysis = data.get("analysis", {})
            buttons = len(analysis.get("buttons", []))
            inputs = len(analysis.get("inputs", []))
            texts = len(analysis.get("texts", []))
            warnings = len(analysis.get("warnings", []))
            save("03_analyze.json", json.dumps(analysis, indent=2, ensure_ascii=False), outdir)
            print(f"✅ кнопок={buttons} полей={inputs} текстов={texts} предупреждений={warnings}")
            if warnings:
                for w in analysis.get("warnings", []):
                    print(f"    ⚠️ {w}")
            return True, analysis
        else:
            print(f"❌ {status}")
            return False, data
    except Exception as e:
        print(f"❌ {e}")
        return False, str(e)


def test_text(outdir):
    """5. Прочитать текст со страницы."""
    print("  📝 Текст страницы...", end=" ", flush=True)
    try:
        status, data = get("/text", timeout=20)
        if status == 200:
            text = data.get("text", "")
            save("04_page_text.txt", text[:5000], outdir)
            print(f"✅ {len(text)} символов")
            return True, text
        else:
            print(f"❌ {status}")
            return False, data
    except Exception as e:
        print(f"❌ {e}")
        return False, str(e)


def test_login(outdir):
    """6. Логин test_login."""
    print("\n  🔑 Логин test_login...")

    # Вводим логин в первое поле
    print("    Ввод логина...", end=" ", flush=True)
    try:
        status, data = get(f"/type?text={TEST_LOGIN}&index=0", timeout=15)
        print(f"{'✅' if status==200 else '❌'}")
    except Exception as e:
        print(f"❌ {e}")

    # Ждём
    time.sleep(0.3)

    # Вводим пароль во второе поле
    print("    Ввод пароля...", end=" ", flush=True)
    try:
        status, data = get(f"/type?text={TEST_PASS}&index=1", timeout=15)
        print(f"{'✅' if status==200 else '❌'}")
    except Exception as e:
        print(f"❌ {e}")

    time.sleep(0.3)

    # Клик по кнопке «Войти»
    print("    Клик «Войти»...", end=" ", flush=True)
    try:
        status, data = get(f"/click?label={q('Войти')}", timeout=20)
        print(f"{'✅' if status==200 else '❌'}")
        if status == 200 and data.get("warning"):
            print(f"    ⚠️ {data['warning']}")
    except Exception as e:
        print(f"❌ {e}")

    # Ждём React-рендер
    print("    Ожидание загрузки...", end=" ", flush=True)
    try:
        status, data = get("/wait?ms=3000", timeout=15)
        print("✅")
    except:
        print("(пропущено)")

    # Скриншот и раскладка после логина
    print("    Снимок после входа...", flush=True)
    test_layout(outdir)
    test_analyze(outdir)
    test_text(outdir)

    # Скриншот
    try:
        status, data = get("/screenshot", timeout=20)
        if status == 200:
            spath = data.get("screenshot", "")
            if spath and os.path.exists(spath):
                import shutil
                shutil.copy2(spath, os.path.join(outdir, "05_after_login.png"))
                print("    ✅ Скриншот сохранён")
    except:
        pass


def test_api_checks(outdir):
    """7. Проверка API (данные для админа)."""
    print("\n  🌐 Проверка API...")

    checks = {
        "admin_panel": api_get("/api/admin/panel", "dle_user_id=1&section=ads&page=1&limit=1"),
        "admin_welcome": api_get("/api/admin/welcome", "dle_user_id=1"),
        "admin_stats": api_get("/api/admin/stats", "dle_user_id=1"),
    }

    save("06_api_checks.json", json.dumps(checks, indent=2, ensure_ascii=False), outdir)

    for name, data in checks.items():
        if "error" in data:
            print(f"    ❌ {name}: {data['error']}")
        else:
            counts = data.get("counts", data)
            if isinstance(counts, dict):
                items = ", ".join(f"{k}={v}" for k, v in counts.items() if not isinstance(v, (dict, list)))
                print(f"    ✅ {name}: {items}")
            else:
                print(f"    ✅ {name}: OK")


# === Запуск ===

def main():
    print("🧪 Browser Agent Test Suite")
    print("=" * 50)

    # Папка для результатов
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = f"/app/screenshots/test_{date_str}"
    os.makedirs(outdir, exist_ok=True)
    print(f"📁 Результаты: {outdir}")

    # Проверка коннекта к агенту
    print("\n🔌 Проверка связи...", end=" ", flush=True)
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect((HOST, PORT))
        s.close()
        print("✅ агент отвечает")
    except Exception as e:
        print(f"❌ {e}")
        save("00_error.txt", f"Браузерный агент недоступен на {HOST}:{PORT}\n{e}", outdir)
        print("\n📁 Результаты сохранены в:", outdir)
        return

    # === Тесты ===
    test_open(outdir)
    time.sleep(1)
    test_screenshot(outdir)
    test_layout(outdir)
    test_analyze(outdir)
    test_text(outdir)
    test_login(outdir)
    test_api_checks(outdir)

    # === Итог ===
    print("\n" + "=" * 50)
    print(f"✅ Все тесты выполнены!")
    print(f"📁 Результаты: {outdir}")

    # Список файлов
    files = sorted(os.listdir(outdir))
    for f in files:
        fpath = os.path.join(outdir, f)
        size = os.path.getsize(fpath)
        print(f"   📄 {f} ({size:,} байт)")


if __name__ == "__main__":
    import socket
    main()
