import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from storage import bind_chat, is_bound, log_message, load_chats, read_last_24h
from comet import CometClient

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
COMET_API_TOKEN = os.getenv("COMET_API_TOKEN", "")
TZ = ZoneInfo(os.getenv("TZ", "Europe/Moscow"))

if not BOT_TOKEN or not COMET_API_TOKEN:
    raise RuntimeError("Set BOT_TOKEN and COMET_API_TOKEN in .env")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
comet = CometClient(COMET_API_TOKEN)

SYSTEM_PROMPT = (
    "Ты Порфирий — черный юмор, сарказм, цинизм. Пиши кратко и смешно. "
    "Никаких призывов к насилию, экстремизму, доксингу, травле по защищённым признакам. "
    "Подкалывай по-дружески, как стендап-комик в закрытом чате."
)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Привязать чат", callback_data="bind_chat")
    ]])
    await message.answer(
        "Жми кнопку, потом перешли мне любое сообщение из нужной группы, где я уже админ.",
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
    await message.answer(f"Готово. Привязал чат: {src.title} ({src.id})")


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_listener(message: Message):
    if not is_bound(message.chat.id):
        return

    text = message.text or message.caption or ""
    if text:
        user = message.from_user.full_name if message.from_user else "unknown"
        log_message(message.chat.id, user, text)

    if text.startswith("/bot"):
        target = text.replace("/bot", "", 1).strip()
        if not target and message.reply_to_message:
            target = message.reply_to_message.text or message.reply_to_message.caption or ""
        if not target:
            await message.reply("Дай текст после /bot или ответь реплаем на сообщение.")
            return
        prompt = f"Сообщение из чата:\n{target}\n\nОтветь в стиле Порфирия."
        try:
            answer = await comet.chat(SYSTEM_PROMPT, prompt)
            await message.reply(answer[:4000])
        except Exception as e:
            await message.reply(f"Что-то пошло не так: {e}")


async def daily_digest():
    chats = load_chats()
    for cid_str, meta in chats.items():
        cid = int(cid_str)
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
            text = await comet.chat(SYSTEM_PROMPT, prompt)
            await bot.send_message(cid, f"🕕 Дневной разбор Порфирия\n\n{text[:3900]}")
        except Exception as e:
            await bot.send_message(cid, f"Не смог собрать разбор: {e}")


async def main():
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(daily_digest, "cron", hour=18, minute=0)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
