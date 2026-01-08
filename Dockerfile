FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости по-минимуму (для PostgreSQL и SSL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Зависимости Python
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Исходники приложения
COPY bot.py ./
COPY main.py ./
COPY service_factory.py ./
COPY src ./src


# Wrapper скрипт для запуска с диагностикой
COPY start_server.py ./
RUN chmod +x /app/start_server.py

# Запуск через wrapper скрипт для гарантированного логирования
# Порт 8080 захардкожен (cloud.ru автоматически определит)
CMD ["python", "/app/start_server.py"]


