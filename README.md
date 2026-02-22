# Porfiriy Telegram Bot

Юмористический бот для закрытой группы на aiogram + CometAPI (ChatGPT 5.1).

## Что умеет
- Ответ по команде `/nax` (текст после команды или reply-сообщение).
- Привязка группы через inline-кнопку в личке (`/start` -> "Привязать чат" -> forward сообщения из группы).
- Раз в сутки в 18:00 (Europe/Moscow по умолчанию) делает разбор чата за 24 часа.
- Локально сохраняет логи сообщений и список привязанных чатов.

## Переменные `.env`
Обязательные:
- `BOT_TOKEN=`
- `COMET_API_TOKEN=`

Опциональные:
- `TZ=Europe/Moscow`
- `ALLOWED_CHAT_IDS=` (через запятую, например `-100123,-100456`)
- `BOT_COOLDOWN_SECONDS=20`
- `HUMOR_MODE=hard` (`soft|hard|insane`)

## Запуск
```bash
cd /home/claw/porfiriy
docker compose up -d --build
```

## Данные
- `data/chats.json` — привязанные чаты
- `data/messages.jsonl` — лог сообщений
