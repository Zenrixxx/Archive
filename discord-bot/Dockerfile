FROM python:3.11-slim

WORKDIR /app

# Копируем файлы ИЗ ПАПКИ discord-bot
COPY discord-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY discord-bot/bot.py .

CMD ["python", "bot.py"]
