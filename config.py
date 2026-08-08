import os

def _env(name, default=None, cast=str):
    val = os.environ.get(name, default)
    if val is None:
        return None
    return cast(val)

# ===================== Telegram =====================
API_ID = _env("API_ID", cast=int)
API_HASH = _env("API_HASH")
BOT_TOKEN = _env("BOT_TOKEN")
SESSION_STRING = _env("SESSION_STRING")
OWNER_ID = _env("OWNER_ID", cast=int)

# ===================== Database =====================
MONGO_URL = _env("MONGO_URL")

# ===================== Log Group =====================
LOG_GROUP_ID = _env("LOG_GROUP_ID", cast=int)

# ===================== BabyAPI (song/video fetch source) =====================
BASE_URL = _env("BASE_URL", "https://api.babiesiq.tech")
API_KEY = _env("API_KEY")

# ===================== Storage (Heroku dyno filesystem ephemeral hai!) =====================
STORAGE_DIR = _env("STORAGE_DIR", "/app/vps_songs")

# ===================== Limits =====================
DURATION_LIMIT = _env("DURATION_LIMIT", 18000, int)
QUEUE_LIMIT = _env("QUEUE_LIMIT", 30, int)

# ===================== Sanity check =====================
_required = {
    "API_ID": API_ID, "API_HASH": API_HASH, "BOT_TOKEN": BOT_TOKEN,
    "SESSION_STRING": SESSION_STRING, "OWNER_ID": OWNER_ID,
    "MONGO_URL": MONGO_URL, "LOG_GROUP_ID": LOG_GROUP_ID, "API_KEY": API_KEY,
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    raise RuntimeError("Missing required env vars: " + ", ".join(_missing))
