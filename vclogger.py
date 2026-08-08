import asyncio
import logging
from typing import Dict

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from pytgcalls import filters as call_filters
from pytgcalls.types import UpdatedGroupCallParticipant, GroupCallParticipant

import config
import database as db

logger = logging.getLogger(__name__)

user_join_count: Dict[tuple, int] = {}
user_cache: Dict[tuple, tuple] = {}
DELETE_DELAY = 7


def setup_vc_logger(bot, assistant, call_py):
    """Call this once after call_py.start() to wire up join/leave notifications."""

    async def delete_message_after_delay(chat_id: int, message_id: int):
        try:
            await asyncio.sleep(DELETE_DELAY)
            await bot.delete_messages(chat_id, message_id)
        except Exception:
            pass

    async def get_user_info(chat_id: int, user_id: int) -> tuple:
        cache_key = (chat_id, user_id)
        if cache_key in user_cache:
            return user_cache[cache_key]

        name = None
        username = "Unknown"

        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member and member.user:
                user = member.user
                name = user.first_name or ""
                if user.last_name:
                    name += f" {user.last_name}"
                username = f"@{user.username}" if user.username else "Unknown"
        except Exception:
            pass

        user_cache[cache_key] = (name, username)
        return name, username

    async def send_join_notification(chat_id: int, user_id: int):
        key = (chat_id, user_id)
        user_join_count[key] = user_join_count.get(key, 0) + 1
        count = user_join_count[key]

        name, username = await get_user_info(chat_id, user_id)
        mention = f'<a href="tg://user?id={user_id}">{name or "User"}</a>'

        text = (
            "<b>#JoinVideoChat</b>\n\n"
            f"<b>● Name:</b> {mention}\n"
            f"<b>● ID:</b> <code>{user_id}</code>\n"
            f"<b>● Username:</b> {username}"
        )
        if count > 1:
            text += f"\n\n<b>🔁 Join count:</b> <code>{count}</code>"

        try:
            msg = await bot.send_message(chat_id, text)
            asyncio.create_task(delete_message_after_delay(chat_id, msg.id))
        except Exception as e:
            logger.error(f"send_join_notification failed: {e}")

    async def send_leave_notification(chat_id: int, user_id: int):
        name, username = await get_user_info(chat_id, user_id)
        mention = f'<a href="tg://user?id={user_id}">{name or "User"}</a>'

        text = (
            "<b>#LeaveVideoChat</b>\n\n"
            f"<b>● Name:</b> {mention}\n"
            f"<b>● ID:</b> <code>{user_id}</code>\n"
            f"<b>● Username:</b> {username}"
        )

        try:
            msg = await bot.send_message(chat_id, text)
            asyncio.create_task(delete_message_after_delay(chat_id, msg.id))
        except Exception as e:
            logger.error(f"send_leave_notification failed: {e}")

    def _extract_user_id(update: UpdatedGroupCallParticipant):
        if getattr(update, "participant", None):
            return update.participant.user_id
        return getattr(update, "user_id", None)

    @call_py.on_update(call_filters.call_participant(GroupCallParticipant.Action.JOINED))
    async def _on_join(_, update: UpdatedGroupCallParticipant):
        chat_id = update.chat_id
        user_id = _extract_user_id(update)
        if user_id is None:
            return
        if not await db.is_vc_logger(chat_id):
            return
        await send_join_notification(chat_id, user_id)

    @call_py.on_update(call_filters.call_participant(GroupCallParticipant.Action.LEFT))
    async def _on_left(_, update: UpdatedGroupCallParticipant):
        chat_id = update.chat_id
        user_id = _extract_user_id(update)
        if user_id is None:
            return
        if not await db.is_vc_logger(chat_id):
            return
        await send_leave_notification(chat_id, user_id)

    async def is_admin(chat_id: int, user_id: int) -> bool:
        if user_id == config.OWNER_ID:
            return True
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
        except Exception:
            return False

    @bot.on_message(filters.command(["vclogger", "vclog"]) & filters.group)
    async def vclogger_cmd(_, message: Message):
        chat_id = message.chat.id

        if message.from_user and not await is_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admin only!")

        if len(message.command) < 2:
            status = await db.is_vc_logger(chat_id)
            return await message.reply_text(
                f"📊 **VC Logger:** {'✅ ON' if status else '❌ OFF'}\n\n"
                "**Commands:**\n`/vclogger on`\n`/vclogger off`"
            )

        action = message.command[1].lower()

        if action == "on":
            await db.set_vc_logger(chat_id, True)
            await message.reply_text("✅ VC logger enabled!")
        elif action == "off":
            await db.set_vc_logger(chat_id, False)
            user_join_count.clear()
            await message.reply_text("🚫 VC logger disabled!")
        else:
            await message.reply_text("Use: `/vclogger on` or `/vclogger off`")

    logger.info("VC Logger handlers registered")
