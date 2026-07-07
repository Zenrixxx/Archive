FROM python:3.11-slim

WORKDIR /app

# Копируем файл бота
COPY discord-bot/bot.py .

# Устанавливаем pip и базовые зависимости
RUN pip install --upgrade pip

# Запускаем бота (библиотеки установятся автоматически при запуске)
CMD ["python", "bot.py"]
