import subprocess
import sys
import os

# ===== АВТОУСТАНОВКА БИБЛИОТЕК =====
def install_packages():
    """Автоматически устанавливает недостающие библиотеки"""
    required = {
        'discord': 'discord.py',
        'pytz': 'pytz'
    }
    
    for module, package in required.items():
        try:
            __import__(module)
            print(f"✅ {package} уже установлен")
        except ImportError:
            print(f"📦 Устанавливаю {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} установлен")

install_packages()
# ====================================

# Теперь импортируем библиотеки
import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import pytz
import random
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_CHANNELS = os.getenv('ALLOWED_CHANNELS', '').split(',')
ALLOWED_CHANNELS = [int(channel_id.strip()) for channel_id in ALLOWED_CHANNELS if channel_id.strip()]

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

if not ALLOWED_CHANNELS:
    logger.warning("⚠️ ALLOWED_CHANNELS не указаны! Бот будет работать во всех каналах.")
else:
    logger.info(f"✅ Разрешённые каналы: {ALLOWED_CHANNELS}")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Словарь для хранения активных меток
active_labels = {}

@bot.event
async def on_ready():
    logger.info(f'✅ Бот {bot.user} запущен!')
    logger.info(f'📊 Активен на {len(bot.guilds)} серверах')
    await bot.change_presence(activity=discord.Game(name="!список"))

@bot.event
async def on_raw_reaction_add(payload):
    """Отслеживает добавление реакций"""
    if payload.user_id == bot.user.id:
        return
    
    channel_id = payload.channel_id
    
    if channel_id not in active_labels:
        return
    
    label_data = active_labels[channel_id]
    if payload.message_id != label_data['message_id']:
        return
    
    user = await bot.fetch_user(payload.user_id)
    if user.id not in label_data['participants']:
        label_data['participants'][user.id] = user
        logger.info(f"➕ Участник {user.name} добавлен в метку канала {channel_id}")
    
    await update_label_message(channel_id)

@bot.event
async def on_raw_reaction_remove(payload):
    """Отслеживает удаление реакций"""
    channel_id = payload.channel_id
    
    if channel_id not in active_labels:
        return
    
    label_data = active_labels[channel_id]
    if payload.message_id != label_data['message_id']:
        return
    
    if payload.user_id in label_data['participants']:
        user = label_data['participants'][payload.user_id]
        del label_data['participants'][payload.user_id]
        logger.info(f"➖ Участник {user.name} удален из метки канала {channel_id}")
    
    await update_label_message(channel_id)

async def update_label_message(channel_id):
    """Обновляет сообщение с меткой"""
    if channel_id not in active_labels:
        return
    
    label_data = active_labels[channel_id]
    channel = bot.get_channel(channel_id)
    
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(label_data['message_id'])
    except:
        return
    
    participants = list(label_data['participants'].values())
    target_count = label_data['target_count']
    
    # Формируем список участников
    participant_list = []
    for i, user in enumerate(participants[:target_count], 1):
        participant_list.append(f"{i}. {user.mention}")
    
    while len(participant_list) < target_count:
        participant_list.append(f"{len(participant_list) + 1}. @ожидание")
    
    end_time = label_data['end_time'].strftime("%H:%M")
    
    embed = discord.Embed(
        title=f"🏷️ Метка {target_count} x {target_count}",
        description=f"⏰ Итоги в {end_time} (МСК)",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="👥 Поставили реакции:",
        value="\n".join(participant_list),
        inline=False
    )
    
    remaining = label_data['end_time'] - datetime.now(pytz.timezone('Europe/Moscow'))
    minutes = int(remaining.total_seconds() // 60)
    seconds = int(remaining.total_seconds() % 60)
    
    embed.set_footer(text=f"⏳ Осталось {minutes} мин {seconds} сек | Нажмите ✅ чтобы участвовать")
    
    await message.edit(content=None, embed=embed)

@bot.command(name='список')
async def create_list(ctx, target_count: int, minutes: int):
    """Создает метку с указанным количеством участников и временем сбора"""
    
    # Проверка каналов
    if ALLOWED_CHANNELS and ctx.channel.id not in ALLOWED_CHANNELS:
        await ctx.send("❌ Эта команда доступна только в определенных каналах!")
        return
    
    if target_count < 1 or target_count > 100:
        await ctx.send("❌ Количество участников должно быть от 1 до 100!")
        return
    
    if minutes < 1 or minutes > 60:
        await ctx.send("❌ Время должно быть от 1 до 60 минут!")
        return
    
    if ctx.channel.id in active_labels:
        await ctx.send("❌ В этом канале уже есть активная метка! Дождитесь завершения.")
        return
    
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    end_time = now + timedelta(minutes=minutes)
    
    embed = discord.Embed(
        title=f"🏷️ Метка {target_count} x {target_count}",
        description=f"⏰ Итоги в {end_time.strftime('%H:%M')} (МСК)",
        color=discord.Color.blue()
    )
    
    participant_list = [f"{i}. @ожидание" for i in range(1, target_count + 1)]
    embed.add_field(
        name="👥 Поставили реакции:",
        value="\n".join(participant_list),
        inline=False
    )
    
    embed.set_footer(text=f"⏳ Нажмите ✅ чтобы участвовать! Осталось {minutes} мин.")
    
    message = await ctx.send(embed=embed)
    await message.add_reaction('✅')
    
    active_labels[ctx.channel.id] = {
        'message_id': message.id,
        'target_count': target_count,
        'end_time': end_time,
        'participants': {},
        'start_time': now
    }
    
    logger.info(f"📌 Создана метка в канале {ctx.channel.id}: {target_count} участников, {minutes} минут")
    
    await asyncio.sleep(minutes * 60)
    
    if ctx.channel.id not in active_labels:
        return
    
    await finish_label(ctx.channel.id)

async def finish_label(channel_id):
    """Завершает метку и подводит итоги"""
    if channel_id not in active_labels:
        return
    
    label_data = active_labels[channel_id]
    channel = bot.get_channel(channel_id)
    
    if not channel:
        del active_labels[channel_id]
        return
    
    try:
        message = await channel.fetch_message(label_data['message_id'])
    except:
        del active_labels[channel_id]
        return
    
    participants = list(label_data['participants'].values())
    target_count = label_data['target_count']
    start_time = label_data['start_time'].strftime("%H:%M")
    
    # Выбираем случайных участников
    if len(participants) > target_count:
        selected = random.sample(participants, target_count)
        not_selected = [p for p in participants if p not in selected]
    else:
        selected = participants
        not_selected = []
    
    result_lines = [
        f"🏷️ Метка {target_count} x {target_count} // Запрос в {start_time} (МСК)",
        "👥 Участники метки:"
    ]
    
    for i, user in enumerate(selected, 1):
        result_lines.append(f"{i}. {user.mention}")
    
    if len(selected) < target_count:
        for i in range(len(selected) + 1, target_count + 1):
            result_lines.append(f"{i}. @недостает")
    
    if not_selected:
        result_lines.append("----------------")
        result_lines.append("❌ Не вошли:")
        for i, user in enumerate(not_selected, 1):
            result_lines.append(f"{i}. {user.mention}")
    
    result_message = "\n".join(result_lines)
    
    await channel.send(result_message)
    
    del active_labels[channel_id]
    logger.info(f"✅ Метка в канале {channel_id} завершена")

@bot.command(name='стоп')
async def stop_label(ctx):
    """Принудительно останавливает метку в канале"""
    if ctx.channel.id not in active_labels:
        await ctx.send("❌ В этом канале нет активной метки!")
        return
    
    await ctx.send("⏹️ Метка остановлена досрочно!")
    await finish_label(ctx.channel.id)

@bot.command(name='статус')
async def status_label(ctx):
    """Показывает статус текущей метки"""
    if ctx.channel.id not in active_labels:
        await ctx.send("❌ В этом канале нет активной метки!")
        return
    
    label_data = active_labels[ctx.channel.id]
    remaining = label_data['end_time'] - datetime.now(pytz.timezone('Europe/Moscow'))
    minutes = int(remaining.total_seconds() // 60)
    seconds = int(remaining.total_seconds() % 60)
    
    await ctx.send(
        f"📊 **Статус метки:**\n"
        f"👥 Участников: {len(label_data['participants'])}/{label_data['target_count']}\n"
        f"⏳ Осталось времени: {minutes} мин {seconds} сек"
    )

@bot.command(name='очистить')
@commands.has_permissions(administrator=True)
async def clear_labels(ctx):
    """Очищает все активные метки (только для админов)"""
    if ctx.channel.id in active_labels:
        del active_labels[ctx.channel.id]
        await ctx.send("✅ Все метки в этом канале очищены!")
    else:
        await ctx.send("❌ В этом канале нет активных меток.")

# Запуск бота
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Неверный токен! Проверьте BOT_TOKEN в переменных окружения.")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
