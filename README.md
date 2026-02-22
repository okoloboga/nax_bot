# Porfiriy Bot

Юмористический Telegram-бот для закрытых групп на aiogram + CometAPI.

## Что умеет
- Реагирует на `/bot` в привязанной группе
- Можно отвечать на сообщение реплаем (`/bot` в reply)
- Пишет дневной разбор чата в 18:00 (Europe/Moscow)
- Привязка чата через кнопку в личке (`/start` -> `Привязать чат` -> forward из группы)

## Обязательные переменные `.env`
- `BOT_TOKEN=`
- `COMET_API_TOKEN=`

## Опционально
- `TZ=Europe/Moscow`
- `ALLOWED_CHAT_IDS=-100123,-100456`
- `BOT_COOLDOWN_SECONDS=20`
- `HUMOR_MODE=hard` (`soft|hard|insane`)

## Запуск
```bash
docker compose up -d --build
```
