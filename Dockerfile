FROM python:3.10-slim

# Указываем рабочую директорию
WORKDIR /app

# Копируем файл requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install alembic

# Копируем все остальные файлы
COPY . .

# Указываем порт для приложения
EXPOSE 8000

# Запускаем приложение с uvicorn
CMD ["uvicorn", "main.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "3", "--reload"]
