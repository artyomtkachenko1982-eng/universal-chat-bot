# ============================================
# Dockerfile для Universal Chat Bot
# ============================================

# Берём Python
FROM python:3.11-slim

# Устанавливаем рабочую папку внутри контейнера
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Открываем порт для WebSocket (чат-виджет)
EXPOSE 8080

# Команда запуска
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
