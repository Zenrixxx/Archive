FROM python:3.11-slim

WORKDIR /app

# Копируем файл бота
COPY discord-bot/bot.py .

# Устанавливаем зависимости напрямую
RUN pip install discord.py pytz

# Запускаем бота
CMD ["python", "bot.py"]
