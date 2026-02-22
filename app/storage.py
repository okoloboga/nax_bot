import json
from pathlib import Path
from datetime import datetime, timezone

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
CHATS_FILE = DATA / "chats.json"
LOG_FILE = DATA / "messages.jsonl"


def load_chats() -> dict:
    if not CHATS_FILE.exists():
        return {}
    return json.loads(CHATS_FILE.read_text(encoding="utf-8"))


def save_chats(chats: dict) -> None:
    CHATS_FILE.write_text(json.dumps(chats, ensure_ascii=False, indent=2), encoding="utf-8")


def bind_chat(chat_id: int, title: str | None) -> None:
    chats = load_chats()
    chats[str(chat_id)] = {"title": title or str(chat_id), "bound_at": datetime.now(timezone.utc).isoformat()}
    save_chats(chats)


def is_bound(chat_id: int) -> bool:
    return str(chat_id) in load_chats()


def log_message(chat_id: int, user: str, text: str) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat_id,
        "user": user,
        "text": text[:2000],
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_last_24h(chat_id: int) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    now = datetime.now(timezone.utc)
    out = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("chat_id") != chat_id:
            continue
        ts = datetime.fromisoformat(row["ts"])
        if (now - ts).total_seconds() <= 86400:
            out.append(row)
    return out
