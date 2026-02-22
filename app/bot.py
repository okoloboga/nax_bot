import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ChatMemberUpdated,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from storage import bind_chat, is_bound, log_message, load_chats, read_last_24h, read_last_n
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


# ---------------------------------------------------------------------------
# Личка — команды
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Привязать чат", callback_data="bind_chat")
    ]])
    await message.answer(
        "Добавь меня в группу как администратора, затем напиши /bind прямо в той группе.\n"
        "Или нажми кнопку и перешли сообщение из группы сюда (работает только если "
        "у отправителя открытая пересылка).\n\nКоманда вызова в чате: /nax",
        reply_markup=kb,
    )


@dp.callback_query(F.data == "bind_chat")
async def bind_button(callback: CallbackQuery):
    await callback.message.answer(
        "Перешли мне любое сообщение из группы.\n"
        "Если не работает — напиши /bind прямо в той группе."
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Авто-привязка при добавлении бота в группу
# ---------------------------------------------------------------------------

@dp.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    new_status = event.new_chat_member.status
    logger.info(
        "my_chat_member: chat=%s (%s) new_status=%s",
        chat.id, chat.title, new_status,
    )
    if new_status in {"member", "administrator"}:
        if ALLOWED_CHAT_IDS and chat.id not in ALLOWED_CHAT_IDS:
            logger.warning("my_chat_member: chat %s not in ALLOWED_CHAT_IDS, skip", chat.id)
            return
        bind_chat(chat.id, chat.title)
        logger.info("Auto-bound chat %s (%s) via my_chat_member", chat.id, chat.title)
        try:
            await bot.send_message(
                chat.id,
                f"Привязан. chat_id={chat.id}. Зови через /nax."
            )
        except Exception:
            logger.exception("Failed to send welcome to chat %s", chat.id)
    elif new_status in {"left", "kicked", "restricted"}:
        logger.info("Bot removed from chat %s (%s)", chat.id, chat.title)


# ---------------------------------------------------------------------------
# Привязка через /bind прямо в группе
# ---------------------------------------------------------------------------

@dp.message(Command("bind"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_bind_in_group(message: Message):
    chat = message.chat
    logger.info("cmd_bind_in_group: chat=%s (%s)", chat.id, chat.title)
    if ALLOWED_CHAT_IDS and chat.id not in ALLOWED_CHAT_IDS:
        logger.warning("cmd_bind_in_group: chat %s not in ALLOWED_CHAT_IDS", chat.id)
        await message.reply("Этот чат не в списке разрешённых.")
        return
    bind_chat(chat.id, chat.title)
    await message.reply(f"Привязан. chat_id={chat.id}. Зови через /nax.")


# ---------------------------------------------------------------------------
# Привязка через forward в личке (legacy + новый API)
# ---------------------------------------------------------------------------

async def _bind_chat_from_forward(message: Message, chat_id: int, title: str | None):
    bind_chat(chat_id, title)
    logger.info("Chat bound via forward: %s (%s)", title, chat_id)
    await message.answer(f"Готово. Привязал чат: {title or chat_id} ({chat_id})")


@dp.message(F.forward_from_chat)
async def bind_by_forward_legacy(message: Message):
    if message.chat.type != ChatType.PRIVATE:
        return
    try:
        src = message.forward_from_chat
        logger.info(
            "bind_by_forward_legacy: src.id=%s src.type=%s src.title=%r",
            src.id, src.type, src.title,
        )
        if src.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            await message.answer("Нужен forward именно из группы.")
            return
        await _bind_chat_from_forward(message, src.id, src.title)
    except Exception:
        logger.exception("bind_by_forward_legacy failed")
        await message.answer("Ошибка при обработке forward (legacy). Смотри логи.")


@dp.message(F.chat.type == ChatType.PRIVATE)
async def bind_by_forward_new(message: Message):
    try:
        origin = getattr(message, "forward_origin", None)
        logger.info(
            "bind_by_forward_new: has_origin=%s origin_type=%s msg_text=%r",
            origin is not None,
            type(origin).__name__ if origin else "—",
            (message.text or "")[:80],
        )
        if not origin:
            return

        src_chat = getattr(origin, "chat", None)
        logger.info(
            "bind_by_forward_new: src_chat=%s src_chat_type=%s",
            getattr(src_chat, "id", None),
            getattr(src_chat, "type", None),
        )
        if src_chat and src_chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
            await _bind_chat_from_forward(message, src_chat.id, src_chat.title)
            return

        # MessageOriginHiddenUser или MessageOriginUser — chat_id не доступен
        logger.warning(
            "bind_by_forward_new: origin_type=%s — cannot extract chat_id",
            type(origin).__name__,
        )
        await message.answer(
            f"Не могу получить chat_id из этого forward (тип: {type(origin).__name__}).\n"
            "Telegram скрывает источник из-за настроек приватности отправителя.\n\n"
            "Используй команду /bind прямо в группе — это надёжнее."
        )
    except Exception:
        logger.exception("bind_by_forward_new failed")
        await message.answer("Ошибка при обработке forward. Смотри логи.")


@dp.message(F.chat.type == ChatType.PRIVATE)
async def private_fallback(message: Message):
    logger.info(
        "private_fallback (unhandled): text=%r has_forward_origin=%s "
        "has_forward_from_chat=%s forward_origin_type=%s",
        (message.text or "")[:80],
        getattr(message, "forward_origin", None) is not None,
        message.forward_from_chat is not None,
        type(getattr(message, "forward_origin", None)).__name__,
    )


# ---------------------------------------------------------------------------
# Групповой слушатель — /nax и логирование
# ---------------------------------------------------------------------------

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

    is_nax = text.startswith("/nax")
    is_reply_to_bot = (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id == bot.id
        and bool(text)
    )

    if not is_nax and not is_reply_to_bot:
        return

    now_ts = datetime.now().timestamp()
    last = LAST_CALL.get(message.chat.id, 0)
    if now_ts - last < BOT_COOLDOWN_SECONDS:
        wait_s = int(BOT_COOLDOWN_SECONDS - (now_ts - last))
        logger.info("Cooldown hit in chat %s, wait=%ss", message.chat.id, wait_s)
        await message.reply(f"Остынь. Следующий вызов через {wait_s} сек.")
        return
    LAST_CALL[message.chat.id] = now_ts

    recent = read_last_n(message.chat.id, n=10)
    context_block = ""
    if recent:
        lines = "\n".join(f"  {r['user']}: {r['text']}" for r in recent)
        context_block = f"Последние сообщения в чате:\n{lines}\n\n"

    if is_nax:
        target = text.replace("/nax", "", 1).strip()
        if not target and message.reply_to_message:
            target = message.reply_to_message.text or message.reply_to_message.caption or ""
        if not target:
            await message.reply("Дай текст после /nax или ответь реплаем на сообщение.")
            return
        prompt = f"{context_block}Сообщение из чата:\n{target}\n\nОтветь в стиле Порфирия."
    else:
        bot_msg = message.reply_to_message.text or message.reply_to_message.caption or ""
        prompt = (
            f"{context_block}"
            f"Предыдущее сообщение Порфирия:\n{bot_msg}\n\n"
            f"Пользователь отвечает:\n{text}\n\n"
            "Продолжи в стиле Порфирия."
        )

    try:
        logger.info(
            "reply triggered in chat %s by user %s (nax=%s, reply_to_bot=%s)",
            message.chat.id,
            message.from_user.id if message.from_user else "unknown",
            is_nax,
            is_reply_to_bot,
        )
        answer = await comet.chat(SYSTEM_PROMPT, prompt)
        await message.reply(answer[:4000])
    except Exception as e:
        logger.exception("reply handler failed in chat %s", message.chat.id)
        await message.reply(f"Что-то пошло не так: {e}")


# ---------------------------------------------------------------------------
# Ежедневный дайджест
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

async def main():
    logger.info("Starting Porfiriy bot...")
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(daily_digest, "cron", hour=18, minute=0)
    scheduler.start()
    logger.info("Scheduler started (daily digest at 18:00 %s)", TZ)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
