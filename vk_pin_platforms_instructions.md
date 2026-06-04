# Инструкция для агента: PRO mode (выбор площадок закрепления) в VK-адаптере

## Файл: `app/adapters/vk.py`

## Что уже сделано в веб-версии (как образец)
- Новое поле `pin_platforms` в БД (`ad_requests.pin_platforms VARCHAR(100)`)
- Новое поле в схеме `AdOrderRequest` и в `handle_ad_submit()`
- Новый шаг `ad_pin_platforms` во фронте — пользователь выбирает на каких площадках закрепить
- Калькулятор `calcAdPrice` учитывает частичное закрепление
- `_calc_ad_breakdown` показывает детали в отчёте админа

## Что нужно сделать в VK-адаптере

### 1. Новый шаг `ad_pin_platforms` (между `ad_pin` и `ad_preview`)

**Где:** после строки ~917 (сейчас `user_sessions[uid] = {**session, "step": "ad_preview", ...}`)

**Логика:**
- Если `pin_days > 0` и площадок выбрано больше 1 И это не "all" → показываем клавиатуру с кнопками площадок для выбора закрепления
- Если `pin_days == 0` или площадка 1 → сразу в `ad_preview` (как сейчас)

**Обработчик шага `ad_pin_platforms`:**
Пользователь нажимает кнопку с названием площадки → добавляем/убираем из `ad_pin_platforms` (список строк).
Кнопка "Готово" → переход в `ad_preview`.

**Пример сообщения:**
```
📌 На каких площадках закрепить объявление?
Выберите нужные площадки ниже.
```

**Клавиатура:**
- Кнопки для каждой площадки из `ad_platforms` (тоггл: ☑/☐ + название)
- Кнопка «Готово»

### 2. Новый ключ в сессии: `ad_pin_platforms`

Хранить как строку: `"tg,vk"` или `None` (все площадки).

### 3. Обновить `handle_ad_submit` вызов

В строке ~951 добавить параметр:
```python
pin_platforms=session.get("ad_pin_platforms"),
```

### 4. Обновить `_calc_ad_price`

Добавить параметр `pin_platforms: str = None`:
```python
def _calc_ad_price(platforms: str, days: int, pin_days: int, prices: dict, pin_platforms: str = None) -> float:
```

В расчёте закрепления (строка ~1671):
```python
if pin_days > 0:
    if pin_platforms:
        pin_count = len([p for p in pin_platforms.split(",") if p.strip()])
    else:
        pin_count = num_plats
    total += round(pin_per_day * pin_count * pin_days)
```

### 5. Обновить вызов `_calc_ad_price` в шаге `ad_pin`

Сейчас (строка ~913): `total_price = _calc_ad_price(platforms, days_val, pin_days, prices)`

Изменить на: `total_price = _calc_ad_price(platforms, days_val, pin_days, prices, session.get("ad_pin_platforms"))`

### 6. Сброс при отмене

При возврате в главное меню или отмене — сбрасывать `ad_pin_platforms: None`.

### 7. Тексты для баннера и статьи

Баннер и статья НЕ используют закрепление — для них pin_platforms всегда None. Ничего менять не надо.

---

## Файлы, которые НЕ трогать
- `app/widgets/chat/index.html` — уже сделано
- `app/handlers/commands.py` — уже сделано
- `app/main.py` — уже сделано
- `app/models/database.py` — уже сделано
- `app/schemas/user.py` — уже сделано
- `app/core/database.py` — уже сделано
