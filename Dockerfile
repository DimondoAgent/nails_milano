# Dockerfile для nails_milano Flask app
FROM python:3.11-slim

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Устанавливаем зависимости (отдельным слоем — кешируется)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаём папки для данных и загрузок (монтируются как volumes)
RUN mkdir -p /app/data /app/static/images

# Пользователь без root прав
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Порт приложения
EXPOSE 5001

# Запуск через gunicorn (production WSGI сервер)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5001", \
     "--workers", "2", \
     "--timeout", "120", \
     "--no-sendfile", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]