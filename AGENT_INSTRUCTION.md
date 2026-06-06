# 🤖 ИНСТРУКЦИЯ: подключить ИИ-агента (DeepSeek) к чату universal-chat-bot

## Важно: анонимное общение УЖЕ работает!

НЕ переписывай чат с нуля. Уже реализовано:
- Аноним заходит → вводит имя → попадает в чат
- Пишет сообщение → `handleAnonSend()` отправляет в `/api/chat/anonymous-send` и сохраняет в БД
- Фронтенд опрашивает `/api/chat/anonymous-get` каждые4 сек — ждёт ответов
- Админ видит чаты в комнате 💬 → может войти → ответить через `/api/admin/chat/reply`
- Если юзер регистрируется/авторизуется — сессия сохраняется, чат переносится

Твоя задача: **добавить** вызов DeepSeek после сохранения сообщения юзера. Не сломать существующее.

## Где лежит код

**Сервер:** 95.181.224.7, **SSH:** root / 9ACPBD2Q4e
**Путь:** /opt/chat/

### Файлы, которые трогаем:

| Файл | Что в нём |
|------|-----------|
| `/opt/chat/app/main.py` | Бэкенд (FastAPI), строка684 — `api_anonymous_send` |
| `/opt/chat/app/core/config.py` | Ключ DeepSeek и URL |
| `/opt/chat/app/models/database.py` | Модель AdminMessage |
| `/opt/chat/app/widgets/chat/index.html` | Фронтенд (~301КБ), строка ~2690 — `handleAnonSend`, строка ~2710 — опрос |
| `/opt/chat/AI-AGENT-CONCEPT.md` | Концепция: рамки, тон, сценарии общения ИИ |

## Что сделать (3 шага)

### Шаг 1. Бэкенд: main.py, `api_anonymous_send` (строка684)

Сейчас эндпоинт делает: сохраняет сообщение → возвращает `{"status":"ok"}`.

Добавить ПОСЛЕ сохранения (НЕ вместо):

a) Собрать последние 10-15 сообщений с этим `platform_user_id`

b) Вызвать DeepSeek:
   - URL: settings.DEEPSEEK_API_URL (уже в конфиге)
   - Ключ: settings.DEEPSEEK_API_KEY (уже в .env)
   - Модель: deepseek-chat
   - Системный промпт: краткая выжимка из AI-AGENT-CONCEPT.md (ИИ — первая линия поддержки turbinist.ru, три направления, рамки, тон)

c) Сохранить ответ как AdminMessage:
   - sender_type="ai"
   - platform_user_id тот же
   - status="new"

d) Вернуть в ответе: `{"status":"ok", "user_msg":{...}, "ai_msg":{...}}`

### Шаг 2. Фронтенд: index.html

В `handleAnonSend()` (строка ~2690): после `fetch POST` получить `data.ai_msg.text` → показать через `addBotMessage()`.

В опросе (интервал4 сек, строка ~2710): заменить фильтр `m.sender_type === "admin"` на `m.sender_type === "admin" || m.sender_type === "ai"`.

### Шаг 3. Админ (опционально, можно вторым заходом)

После ответа админа через `/api/admin/chat/reply` — ставить флаг в чате, чтобы ИИ больше не отвечал.

## Как проверить

1. `http://95.181.224.7:8081/widget` → зайти как аноним (или инкогнито)
2. Написать "Привет" → должен прийти ответ от 🤖 через 2-5 сек
3. Залогиниться как admin (admin / temius1982) → 💬 → чат с анонимом виден
4. Войти в чат → видна переписка (юзер + ИИ)

## Деплой

```bash
cd /opt/chat && git add -A && git commit -m "ai-agent: deepseek integration" && git push origin main
docker restart uc_app
```
Ждать ~15 сек.

