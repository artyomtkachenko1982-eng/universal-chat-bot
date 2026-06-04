@echo off
chcp 65001 >nul
title 🧪 Universal Chat — Browser Test

echo ============================================
echo  🧪 Universal Chat — Browser Test Suite
echo ============================================
echo.

REM 1. Запускаем браузерный агент (если ещё не запущен)
echo [1/3] Запуск браузерного агента...
docker exec -d uc_app python /app/browser_agent.py 2>nul
if %errorlevel% equ 0 ( echo   ✅ Готово ) else ( echo   ⚠️ Не удалось - возможно уже запущен )
timeout /t 2 /nobreak >nul

REM 2. Копируем свежий тестовый скрипт в контейнер
echo [2/3] Копирование тестового скрипта...
docker cp "%~dp0app\browser_test.py" uc_app:/app/app/browser_test.py
echo   ✅ Готово

REM 3. Запускаем тесты
echo [3/3] Запуск тестов...
echo.
docker exec uc_app python /app/app/browser_test.py
echo.

REM 4. Удаляем мусорные скриншоты (оставляем только папки test_*)
echo [4/4] Очистка мусора...
docker exec uc_app python -c "import os,glob; [os.remove(f) for f in glob.glob('/app/screenshots/screenshot_*.png')+glob.glob('/app/screenshots/layout_*.svg')]"
echo   ✅ Готово

if %errorlevel% equ 0 (
    echo ============================================
    echo  ✅ ТЕСТЫ ЗАВЕРШЕНЫ
    echo  Открой Claude и скажи: "проверь тесты"
    echo ============================================
) else (
    echo ============================================
    echo  ❌ ОШИБКА при выполнении тестов
    echo ============================================
)

pause
