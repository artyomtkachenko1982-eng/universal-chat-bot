@echo off
cd /d C:\Users\Артем\YandexDisk-turbinist-site\repository\Telegram-Dle-Post\universal_chat
git add -A
git commit -m "%*"
git push

docker restart uc_app
docker exec -d uc_app python /app/browser_agent.py
docker exec uc_redis redis-cli DEL "rate:auth:*" >nul 2>&1

echo ✅ Деплой: коммит + пуш + рестарт + браузер + рейт-лимиты
