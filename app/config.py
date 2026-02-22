import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
COMET_API_TOKEN = os.getenv("COMET_API_TOKEN", "")
TZ = os.getenv("TZ", "Europe/Moscow")

# Optional hardening/tuning
ALLOWED_CHAT_IDS = [int(x.strip()) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()]
BOT_COOLDOWN_SECONDS = int(os.getenv("BOT_COOLDOWN_SECONDS", "20"))
HUMOR_MODE = os.getenv("HUMOR_MODE", "hard")  # soft|hard|insane
