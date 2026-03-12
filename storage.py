import json
import os

SEEN_FILE = "seen_ads.json"       # уже отправленные объявления (по chat_id)
USER_DATA_FILE = "user_data.json"  # ссылки и статус пользователей


# ──────────────────────────────────────────
# Отправленные объявления (по пользователям)
# ──────────────────────────────────────────

def _load_all_seen() -> dict:
    if not os.path.exists(SEEN_FILE):
        return {}
    with open(SEEN_FILE, "r") as f:
        return json.load(f)


def _save_all_seen(data: dict):
    with open(SEEN_FILE, "w") as f:
        json.dump(data, f)


def load_seen(chat_id: int) -> set:
    """Возвращает множество уже отправленных ссылок для конкретного пользователя."""
    all_seen = _load_all_seen()
    return set(all_seen.get(str(chat_id), []))


def save_seen(chat_id: int, seen: set):
    """Сохраняет отправленные ссылки для конкретного пользователя."""
    all_seen = _load_all_seen()
    all_seen[str(chat_id)] = list(seen)
    _save_all_seen(all_seen)


# ──────────────────────────────────────────
# Данные пользователей (ссылка + статус)
# ──────────────────────────────────────────

def load_user_data() -> dict:
    """Загружает данные всех пользователей (url, active)."""
    if not os.path.exists(USER_DATA_FILE):
        return {}
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)


def save_user_data(data: dict):
    """Сохраняет данные всех пользователей."""
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
