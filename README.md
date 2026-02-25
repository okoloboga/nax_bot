# Porfiriy Telegram Bot

A Telegram bot for private group chats built with `aiogram` and CometAPI.

## Features
- Responds to `/nax` (text after command or message reply target).
- Manual web search with `/find <query>`.
- Chat binding from private chat (`/start` -> "Bind chat" flow) and `/bind` inside group.
- Daily classic digest at `18:00` (default timezone: `Europe/Moscow`).
- Daily web digest at `12:00`: extracts hot themes from chat and adds web-based context.
- Stores chat bindings and message logs locally.

## Environment Variables (`.env`)
Required:
- `BOT_TOKEN=`
- `COMET_API_TOKEN=`

Optional:
- `TZ=Europe/Moscow`
- `COMET_MODEL=gpt-5.1`
- `ALLOWED_CHAT_IDS=` (comma-separated, for example `-100123,-100456`)
- `BOT_COOLDOWN_SECONDS=20`
- `HUMOR_MODE=hard` (`soft|hard|insane`)
- `WEB_DIGEST_HOUR=12`
- `WEB_DIGEST_MINUTE=0`

## Run
```bash
docker compose up -d --build
```

## CI/CD (GitHub Actions)
- `CI` ([`.github/workflows/ci.yml`](/Users/core/code/nax_bot/.github/workflows/ci.yml)): runs on every push/PR, installs dependencies, and validates syntax (`python -m compileall app`).
- `CD` ([`.github/workflows/cd.yml`](/Users/core/code/nax_bot/.github/workflows/cd.yml)): runs on push to `main`, builds and publishes Docker image to `ghcr.io/<owner>/<repo>`.
- Optional SSH deployment: if deploy secrets are present, the workflow updates the server and runs `docker compose up -d --build`.

## Deploy Secrets (Optional)
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PATH`
- `DEPLOY_PORT` (optional, default `22`)

## Data Files
- `data/chats.json` - bound chats metadata
- `data/messages.jsonl` - message log
