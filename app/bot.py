import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from storage import bind_chat, is_bound, log_message, load_chats, read_last_24h
from comet import CometClient
from config import (
    BOT_TOKEN,
    COMET_API_TOKEN,
    TZ as TZ_NAME,
    ALLOWED_CHAT_IDS,
    BOT_COOLDOWN_SECONDS,
    HUMOR_MODE,
)

TZ = ZoneInfo(TZ_NAME)

if not BOT_TOKEN or not COMET_API_TOKEN:
    raise RuntimeError("Set BOT_TOKEN and COMET_API_TOKEN in .env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("porfiriy")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
comet = CometClient(COMET_API_TOKEN)

MODE_PROMPTS = {
    "soft": "Лёгкий сарказм, больше иронии, меньше жести.",
    "hard": "Черный юмор, цинизм, жёсткие панчи, но без травли по защищённым признакам.",
    "insane": "Максимально безумный стендап-режим, абсурд и огонь, но без запрещёнки.",
}

SYSTEM_PROMPT = (
    "Ты Порфирий — комик-циник для закрытого чата. "
    f"Режим: {MODE_PROMPTS.get(HUMOR_MODE, MODE_PROMPTS['hard'])} "
    "Пиши кратко, дерзко, смешно. Никаких призывов к насилию, экстремизму, доксингу."
)

LAST_CALL: dict[int, float] = {}


@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Привязать чат", callback_data="bind_chat")
    ]])
    await message.answer(
        "Жми кнопку, потом перешли мне любое сообщение из нужной группы, где я уже админ.\nКоманда вызова в чате: /nax",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "bind_chat")
async def bind_button(callback: CallbackQuery):
    await callback.message.answer("Ок, теперь перешли мне сообщение из группы (forward).")
    await callback.answer()


@dp.message(F.forward_from_chat)
async def bind_by_forward(message: Message):
    if message.chat.type != ChatType.PRIVATE:
        return
    src = message.forward_from_chat
    if src.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        await message.answer("Нужен forward именно из группы.")
        return
    bind_chat(src.id, src.title)
    logger.info("Chat bound: %s (%s)", src.title, src.id)
    await message.answer(f"Готово. Привязал чат: {src.title} ({src.id})")


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_listener(message: Message):
    if ALLOWED_CHAT_IDS and message.chat.id not in ALLOWED_CHAT_IDS:
        return
    if not is_bound(message.chat.id):
        return

    text = message.text or message.caption or ""
    if text:
        user = message.from_user.full_name if message.from_user else "unknown"
        log_message(message.chat.id, user, text)

    if text.startswith("/nax"):
        now_ts = datetime.now().timestamp()
        last = LAST_CALL.get(message.chat.id, 0)
        if now_ts - last < BOT_COOLDOWN_SECONDS:
            wait_s = int(BOT_COOLDOWN_SECONDS - (now_ts - last))
            logger.info("Cooldown hit in chat %s, wait=%ss", message.chat.id, wait_s)
            await message.reply(f"Остынь. Следующий вызов через {wait_s} сек.")
            return
        LAST_CALL[message.chat.id] = now_ts

        target = text.replace("/nax", "", 1).strip()
        if not target and message.reply_to_message:
            target = message.reply_to_message.text or message.reply_to_message.caption or ""
        if not target:
            await message.reply("Дай текст после /nax или ответь реплаем на сообщение.")
            return
        prompt = f"Сообщение из чата:\n{target}\n\nОтветь в стиле Порфирия."
        try:
            logger.info("/nax called in chat %s by user %s", message.chat.id, message.from_user.id if message.from_user else "unknown")
            answer = await comet.chat(SYSTEM_PROMPT, prompt)
            await message.reply(answer[:4000])
        except Exception as e:
            logger.exception("/nax failed in chat %s", message.chat.id)
            await message.reply(f"Что-то пошло не так: {e}")


async def daily_digest():
    chats = load_chats()
    for cid_str, meta in chats.items():
        cid = int(cid_str)
        if ALLOWED_CHAT_IDS and cid not in ALLOWED_CHAT_IDS:
            continue
        rows = read_last_24h(cid)
        if not rows:
            continue
        sample = "\n".join([f"- {r['user']}: {r['text']}" for r in rows[-200:]])
        prompt = (
            "Сделай дневной разбор чата: ключевые темы, кто как себя ведет, "
            "смешные и циничные комментарии по личностям участников. "
            "Формат: 1) Итоги дня 2) Портреты персонажей 3) Прогноз на завтра.\n\n"
            f"Лог за сутки:\n{sample}"
        )
        try:
            logger.info("Daily digest for chat %s (%s messages)", cid, len(rows))
            text = await comet.chat(SYSTEM_PROMPT, prompt)
            await bot.send_message(cid, f"🕕 Дневной разбор Порфирия\n\n{text[:3900]}")
        except Exception as e:
            logger.exception("Daily digest failed for chat %s", cid)
            await bot.send_message(cid, f"Не смог собрать разбор: {e}")


async def main():
    logger.info("Starting Porfiriy bot...")
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(daily_digest, "cron", hour=18, minute=0)
    scheduler.start()
    logger.info("Scheduler started (daily digest at 18:00 %s)", TZ)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
