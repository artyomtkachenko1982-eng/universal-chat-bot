# Server Reminder — DLE-PWA

> Этот файл показывет на каких серверах находится основной сайт DLE и второй сервер где будет лежать чат, это не основа будущего ат бота, а небольшая шпаргалка, на основе ее сделаешь то, что будет актуально текущему проекту


---

## Серверы

### 1. turbinist.ru (основной DLE сайт)
- **IP:** 185.87.196.222
- **Панель:** ISPmanager (isp2)
- **Пользователь:** p607930
- **Веб-сервер:** LiteSpeed + PHP 7.1.33
- **Роль:** Хостит DLE сайт и PHP-прокси для PWA

### 2. PWA сервер (отдельный VPS)
- **IP:** 95.181.224.7
- **Хост:** p918511
- **SSH:** `ssh root@95.181.224.7`
- **Пароль:** в секретах `SSH_PASSWORD` = `9ACPBD2Q4e`
- **Путь приложения:** `/var/www/pwa`
- **Роль:** Node.js сервер с PWA приложением

---

## Окружение PWA сервера (95.181.224.7)

| Компонент | Версия |
|-----------|--------|
| OS | Ubuntu 24.x |
| Node.js | v20.20.0 |
| npm | 10.2.0 |
| PM2 | 6.0.14 |
| Nginx | 1.24.0 |

---

## Схема работы

```
Пользователь
    ↓
https://pwa.turbinist.ru (DNS → 185.87.196.222)
    ↓
/home/p607930/www/pwa.turbinist.ru/index.php (PHP прокси)
    ↓ curl
http://95.181.224.7:5000 (Node.js + PM2)
    ↓
PWA приложение
```

---

## PHP прокси (на turbinist.ru)

**Путь:** `/home/p607930/www/pwa.turbinist.ru/index.php`

> **ВАЖНО (30.01.2026):** Исправлена критическая ошибка — прокси не передавал POST-запросы.
> Без этого исправления авторизация по логину/паролю НЕ работает!

```php
<?php
$targetBase = 'http://95.181.224.7:5000';
$path = $_SERVER['REQUEST_URI'];
$target = $targetBase . $path;

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $target);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);

// Передаём метод запроса (GET, POST, PUT, etc.)
$method = $_SERVER['REQUEST_METHOD'];
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);

// Передаём тело запроса для POST/PUT/PATCH
if (in_array($method, ['POST', 'PUT', 'PATCH'])) {
    $body = file_get_contents('php://input');
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

// Передаём заголовки
$headers = [];
if (isset($_SERVER['CONTENT_TYPE'])) {
    $headers[] = 'Content-Type: ' . $_SERVER['CONTENT_TYPE'];
}
if (isset($_SERVER['HTTP_AUTHORIZATION'])) {
    $headers[] = 'Authorization: ' . $_SERVER['HTTP_AUTHORIZATION'];
}
if (!empty($headers)) {
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
}

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
$contentType = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
curl_close($ch);

$body = substr($response, $headerSize);

http_response_code($httpCode);
if ($contentType) {
    header('Content-Type: ' . $contentType);
}
echo $body;
```

**.htaccess** (там же):
```apache
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^(.*)$ index.php [L,QSA]
```

---

## Команды управления PWA

```bash
# Подключение к PWA серверу
ssh root@95.181.224.7

# Перейти в папку
cd /var/www/pwa

# PM2 команды
pm2 status              # Статус
pm2 logs pwa            # Логи
pm2 restart pwa         # Перезапуск
pm2 stop pwa            # Остановка

# Первый запуск (если PM2 пустой)
pm2 start npm --name "pwa" -- run dev && pm2 save
```

---

## API конфигурация

| Параметр | Значение |
|----------|----------|
| API токен | `tPWA_x7Kq9mN2wL5rT8vB3` |
| api-bridge.php | корень сайта turbinist.ru |
| Конфиг PWA | `/var/www/pwa/pwa-config.json` |

**Важно:** Токен должен совпадать в `pwa-config.json` и `api-bridge.php`!

---

## Обновление PWA на продакшене

```bash
# 1. Загрузить файлы с Replit на сервер
scp -r dle-pwa/* root@95.181.224.7:/var/www/pwa/

# 2. Перезапустить PM2
ssh root@95.181.224.7 "cd /var/www/pwa && pm2 restart pwa"
```

Или одной командой:
```bash
scp -r dle-pwa/* root@95.181.224.7:/var/www/pwa/ && ssh root@95.181.224.7 "pm2 restart pwa"
```

---

## Важные файлы проекта

| Файл | Назначение |
|------|------------|
| `pwa-config.json` | Главный конфиг приложения |
| `api-bridge.php` | PHP мост для DLE (лежит на turbinist.ru) |
| `server/routes.ts` | API маршруты бэкенда |
| `server/storage.ts` | Хранилище сессий |
| `client/src/pages/` | Страницы приложения |
| `DEPLOY.md` | Инструкция по установке для клиентов |
| `PROJECT-GUIDE.md` | Документация проекта |

---

## Теги контента [hide] и [payhide]

- `[hide]...[/hide]` — для зарегистрированных пользователей
- `[payhide]...[/payhide]` — для подписчиков (группы 1-5 или time_limit)

Обработка происходит в `api-bridge.php` на сервере DLE.
Настройка групп: строка ~305 в api-bridge.php.

---

## Безопасность

- **user_id** получается из сессии на сервере PWA (не от клиента!)
- Клиент передает токен в заголовке `Authorization: Bearer <token>`
- Сервер проверяет токен через `storage.getSession()`
- Только после этого user_id передается в api-bridge.php

---

## Известные особенности

1. **PHP прокси добавляет задержку** — каждый запрос идет через curl
2. **SSL на pwa.turbinist.ru** — настроен через ISPmanager (Let's Encrypt)
3. **Порт 5000** — должен быть открыт на PWA сервере
4. **PM2 режим dev** — используется `npm run dev`, не production build

---

## Контакты

- **Telegram:** @turbinist_club
- **Сайт:** https://turbinist.ru
- **PWA:** https://pwa.turbinist.ru

---

> Последнее обновление: 2026-01-29
