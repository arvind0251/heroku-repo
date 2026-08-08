from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from config import MONGO_URL

_client = AsyncIOMotorClient(MONGO_URL)
_db = _client["musicbot"]

users_col = _db["users"]          # served users -> for broadcast
chats_col = _db["chats"]          # served chats -> for broadcast
authuser_col = _db["authusers"]   # per-chat authorized users


# ---------------- Served users / chats (for /broadcast) ----------------

async def add_served_user(user_id: int):
    if not await users_col.find_one({"user_id": user_id}):
        await users_col.insert_one({"user_id": user_id})


async def get_served_users():
    return [doc["user_id"] async for doc in users_col.find({})]


async def add_served_chat(chat_id: int):
    if not await chats_col.find_one({"chat_id": chat_id}):
        await chats_col.insert_one({"chat_id": chat_id})


async def get_served_chats():
    return [doc["chat_id"] async for doc in chats_col.find({})]


# ---------------- Per-chat authorized users (for /authuser) ----------------

async def add_auth_user(chat_id: int, user_id: int):
    await authuser_col.update_one(
        {"chat_id": chat_id},
        {"$addToSet": {"users": user_id}},
        upsert=True,
    )


async def remove_auth_user(chat_id: int, user_id: int):
    await authuser_col.update_one(
        {"chat_id": chat_id},
        {"$pull": {"users": user_id}},
    )


async def get_auth_users(chat_id: int):
    doc = await authuser_col.find_one({"chat_id": chat_id})
    return doc["users"] if doc and "users" in doc else []


async def is_auth_user(chat_id: int, user_id: int) -> bool:
    doc = await authuser_col.find_one({"chat_id": chat_id, "users": user_id})
    return doc is not None


# ---------------- VC Join/Leave Logger (per-chat toggle) ----------------

async def set_vc_logger(chat_id: int, enabled: bool):
    await chats_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"vc_logger": enabled}},
        upsert=True,
    )


async def is_vc_logger(chat_id: int) -> bool:
    doc = await chats_col.find_one({"chat_id": chat_id})
    return bool(doc and doc.get("vc_logger", False))


# ---------------- Warns (moderation) ----------------

warns_col = _db["warns"]


async def add_warn(chat_id: int, user_id: int) -> int:
    """Increments the warn count and returns the new count."""
    result = await warns_col.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["count"] if result else 1


async def get_warns(chat_id: int, user_id: int) -> int:
    doc = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return doc["count"] if doc else 0


async def reset_warns(chat_id: int, user_id: int):
    await warns_col.delete_one({"chat_id": chat_id, "user_id": user_id})
