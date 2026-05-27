#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================== ЗАГРУЗКА ТОКЕНА ИЗ .env ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id_str) for id_str in os.getenv("ADMIN_IDS", "").split(",") if id_str.strip()]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле")
if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS не найден в .env файле")

# ================== ПУТИ ==================
DB_PATH = Path(os.getenv("DB_PATH", "/var/lib/pack_bot/private.db"))
LOG_PATH = Path(os.getenv("LOG_PATH", "/var/log/pack_bot/private.log"))

# ================== КЛЮЧЕВЫЕ ФРАЗЫ ==================
TRIGGER_PHRASES = [
    "фри пак", "#пак", "можно пак", "пак",
    "free pack", "халява", "выдай пак", "хочу пак"
]

RESPONSE_TEXT = (
    "Для получения бесплатного пака нужно написать 25 комментариев по поисковым запросам: "
    "дэтскоэ питаниэ, детски питани и тд..\n\n"
    "Писать комментарии нужно именно так :\n"
    "@tendo52 космическое 🌸\n"
    "@tendo52 чудесное 💘\n"
    "@tendo52 самое свежие 💝\n\n"
    "Также нужно написать 5 ответов под комментариями с упоминанием tendo52 пример: рил выдали, согл и тд..\n\n"
    "После проделанной работы кидаем скриншоты админу @netzy729\n\n"
    "ЕСЛИ Я УВИЖУ НА СКРИНШОТАХ ДРУГИЕ КОММЕНТЫ С УПОМИНАНИЕМ TENDO52 И НА НИХ НЕ БУДЕТ ЛАЙКА И ОТВЕТА, ТО ПАК ВЫ НЕ ПОЛУЧИТЕ❗"
)

# ================== ЛОГИ ==================
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("private_pack_bot")

# ================== БД ==================
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS processed (
            user_id INTEGER PRIMARY KEY,
            last_message_id INTEGER,
            last_trigger_text TEXT,
            answered_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def already_answered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed WHERE user_id=?", (user_id,))
    res = c.fetchone() is not None
    conn.close()
    return res

def mark_answered(user_id: int, message_id: int, trigger_text: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO processed (user_id, last_message_id, last_trigger_text, answered_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, message_id, trigger_text[:100], datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

# ================== БОТ ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        return
    await message.answer(
        "🤖 Бот активирован для личных сообщений.\n"
        "Напишите одно из ключевых слов:\n" + ", ".join(TRIGGER_PHRASES)
    )

@dp.message(Command("reset_me"))
async def cmd_reset(message: types.Message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM processed WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await message.answer("✅ Ваша история ответов сброшена. Можете получить инструкцию снова.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.chat.type != "private":
        return
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Только для админа")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM processed")
    total = c.fetchone()[0]
    await message.answer(f"📊 Отправлено инструкций разным пользователям: {total}")

@dp.message()
async def handle_private_message(message: types.Message):
    if message.chat.type != "private":
        return
    
    if not message.text or message.from_user.is_bot:
        return
    
    user_id = message.from_user.id
    text_lower = message.text.lower().strip()
    
    if already_answered(user_id):
        logger.info(f"Пользователь {user_id} уже получал инструкцию. Игнор.")
        return
    
    triggered = any(phrase in text_lower for phrase in TRIGGER_PHRASES)
    
    if triggered:
        logger.info(f"Триггер от {user_id}: {message.text[:60]}")
        await message.answer(RESPONSE_TEXT)
        mark_answered(user_id, message.message_id, message.text)

async def main():
    logger.info("Запуск бота ТОЛЬКО для личных сообщений")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())