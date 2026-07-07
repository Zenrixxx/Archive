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

import discord
from discord.ext import commands
from discord import app_commands
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
    
    # Смена статуса на "Играет в (VZP / CAPT / BIZ)"
    await bot.change_presence(activity=discord.Game(name="VZP / CAPT / BIZ"))
    
    # Синхронизация слэш-команд
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Синхронизировано {len(synced)} слэш-команд")
        for cmd in synced:
            logger.info(f"   /{cmd.name} - {cmd.description}")
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")

@bot.event
async def on_raw_reaction_add(payload):
    """Отслеживает добавление реакций - ПОКАЗЫВАЕТ ВСЕХ УЧАСТНИКОВ"""
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
    """Обновляет сообщение с меткой - ПОКАЗЫВАЕТ ВСЕХ УЧАСТНИКОВ"""
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
    
    # ПОКАЗЫВАЕМ ВСЕХ УЧАСТНИКОВ (всех, кто поставил реакцию)
    participant_list = []
    
    if participants:
        # Показываем ВСЕХ участников, кто поставил реакцию
        for i, user in enumerate(participants, 1):
            participant_list.append(f"{i}. {user.mention}")
        
        # Если участников больше, чем нужно - показываем всех
        if len(participants) > target_count:
            # Добавляем предупреждение, но показываем всех
            participant_list.append(f"⚠️ Всего {len(participants)} участников (нужно {target_count})")
    else:
        # Если нет участников - показываем ожидание
        for i in range(1, target_count + 1):
            participant_list.append(f"{i}. @ожидание")
    
    end_time = label_data['end_time'].strftime("%H:%M")
    
    embed = discord.Embed(
        title=f"🛑 Метка {target_count} x {target_count}",
        description=f"⏳ Итоги в {end_time} (МСК)",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name=f"👥 Поставили реакции ({len(participants)} чел.):",
        value="\n".join(participant_list) if participant_list else "⏳ Ожидание...",
        inline=False
    )
    
    remaining = label_data['end_time'] - datetime.now(pytz.timezone('Europe/Moscow'))
    minutes = int(remaining.total_seconds() // 60)
    seconds = int(remaining.total_seconds() % 60)
    
    embed.set_footer(text=f"⏳ Осталось {minutes} мин {seconds} сек | Нажмите ✅ чтобы участвовать")
    
    await message.edit(content=None, embed=embed)

# ===== СЛЭШ-КОМАНДЫ =====

@bot.tree.command(name="список", description="📃 Создать список")
@app_commands.describe(
    участников="Количество участников для метки (от 1 до 50)",
    минут="Время на сбор реакций в минутах (от 1 до 60)"
)
async def slash_list(interaction: discord.Interaction, участников: int, минут: int):
    """Создаёт метку с участниками"""
    
    # Проверка каналов
    if ALLOWED_CHANNELS and interaction.channel_id not in ALLOWED_CHANNELS:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="Эта команда доступна только в определенных каналах!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if участников < 1 or участников > 50:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="Количество участников должно быть от 1 до 50!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if минут < 1 or минут > 60:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="Время должно быть от 1 до 60 минут!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if interaction.channel_id in active_labels:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="В этом канале уже есть активная метка! Дождитесь завершения.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    end_time = now + timedelta(minutes=минут)
    
    # Начальное сообщение с ожиданием
    participant_list = [f"{i}. @ожидание" for i in range(1, участников + 1)]
    
    embed = discord.Embed(
        title=f"🛑 Метка {участников} x {участников}",
        description=f"⏳ Итоги в {end_time.strftime('%H:%M')} (МСК)",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="👥 Поставили реакции (0 чел.):",
        value="\n".join(participant_list),
        inline=False
    )
    
    embed.set_footer(text=f"⏳ Нажмите ✅ чтобы участвовать! Осталось {минут} мин.")
    
    # Отправляем сообщение с меткой
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    await message.add_reaction('✅')
    
    # Добавляем скрытое упоминание @everyone
    try:
        await interaction.channel.send("||@everyone||")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке @everyone: {e}")
    
    active_labels[interaction.channel_id] = {
        'message_id': message.id,
        'target_count': участников,
        'end_time': end_time,
        'participants': {},
        'start_time': now
    }
    
    logger.info(f"📌 Создана метка в канале {interaction.channel_id}: {участников} участников, {минут} минут")
    
    await asyncio.sleep(минут * 60)
    
    if interaction.channel_id not in active_labels:
        return
    
    await finish_label(interaction.channel_id)

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
    
    # Формируем итоговое сообщение в коробочке
    result_lines = [
        f"🛑 Метка {target_count} x {target_count} // Запрос в {start_time} (МСК)",
        f"👥 Участники метки ({len(selected)}/{target_count}):"
    ]
    
    for i, user in enumerate(selected, 1):
        result_lines.append(f"{i}. {user.mention}")
    
    if len(selected) < target_count:
        for i in range(len(selected) + 1, target_count + 1):
            result_lines.append(f"{i}. @недостает")
    
    if not_selected:
        result_lines.append("----------------")
        result_lines.append(f"❌ Не вошли ({len(not_selected)} чел.):")
        for i, user in enumerate(not_selected, 1):
            result_lines.append(f"{i}. {user.mention}")
    
    result_message = "\n".join(result_lines)
    
    # Отправляем итоговое сообщение в коробочке
    embed_result = discord.Embed(
        description=result_message,
        color=discord.Color.green()
    )
    await channel.send(embed=embed_result)
    
    del active_labels[channel_id]
    logger.info(f"✅ Метка в канале {channel_id} завершена")

@bot.tree.command(name="стоп", description="⏹️ Остановить текущую метку досрочно")
async def slash_stop(interaction: discord.Interaction):
    """Останавливает метку досрочно"""
    
    if interaction.channel_id not in active_labels:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="В этом канале нет активной метки!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⏹️ Остановка",
        description="Метка остановлена досрочно!",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)
    await finish_label(interaction.channel_id)

@bot.tree.command(name="статус", description="📊 Показать статус текущей метки")
async def slash_status(interaction: discord.Interaction):
    """Показывает статус текущей метки"""
    
    if interaction.channel_id not in active_labels:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="В этом канале нет активной метки!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    label_data = active_labels[interaction.channel_id]
    remaining = label_data['end_time'] - datetime.now(pytz.timezone('Europe/Moscow'))
    minutes = int(remaining.total_seconds() // 60)
    seconds = int(remaining.total_seconds() % 60)
    
    embed = discord.Embed(
        title="📊 Статус метки",
        color=discord.Color.blue()
    )
    embed.add_field(name="👥 Участников", value=f"{len(label_data['participants'])}/{label_data['target_count']}", inline=True)
    embed.add_field(name="⏳ Осталось времени", value=f"{minutes} мин {seconds} сек", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="очистить", description="🧹 Очистить все активные метки")
async def slash_clear(interaction: discord.Interaction):
    """Очищает все активные метки (только для админов)"""
    
    # Проверка прав администратора
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="У вас нет прав администратора для этой команды!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if interaction.channel_id in active_labels:
        del active_labels[interaction.channel_id]
        embed = discord.Embed(
            title="✅ Очищено",
            description="Все метки в этом канале очищены!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Ошибка",
            description="В этом канале нет активных меток.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Запуск бота
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Неверный токен! Проверьте BOT_TOKEN в переменных окружения.")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
