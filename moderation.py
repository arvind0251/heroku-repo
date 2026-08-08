from datetime import timedelta

from pyrogram import filters
from pyrogram.types import Message, ChatPrivileges, ChatPermissions
from pyrogram.enums import ChatMemberStatus

import config
import database as db

WARN_LIMIT = 3  # after this many warns, the user is auto-banned


def setup_moderation(bot):
    """Call this once after bot.start() to register all moderation commands."""

    async def is_group_admin(chat_id: int, user_id: int) -> bool:
        if user_id == config.OWNER_ID:
            return True
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
        except Exception:
            return False

    async def get_target(message: Message):
        """Extracts the target user from a reply or @username/id argument."""
        if message.reply_to_message and message.reply_to_message.from_user:
            return message.reply_to_message.from_user
        if len(message.command) > 1:
            try:
                return await bot.get_users(message.command[1])
            except Exception:
                return None
        return None

    def get_reason(message: Message, skip_args: int = 1) -> str:
        if message.reply_to_message and len(message.command) > skip_args:
            return " ".join(message.command[skip_args:])
        if not message.reply_to_message and len(message.command) > skip_args + 1:
            return " ".join(message.command[skip_args + 1:])
        return "No reason provided"

    # ---------------- Mute / Unmute ----------------

    @bot.on_message(filters.command("mute") & filters.group)
    async def mute_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/mute <user_id>`.")

        try:
            await bot.restrict_chat_member(chat_id, target.id, ChatPermissions())
            await message.reply_text(f"🔇 {target.mention} has been muted.")
        except Exception as e:
            await message.reply_text(f"❌ Couldn't mute: {e}")

    @bot.on_message(filters.command("unmute") & filters.group)
    async def unmute_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/unmute <user_id>`.")

        try:
            await bot.restrict_chat_member(
                chat_id,
                target.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            await message.reply_text(f"🔊 {target.mention} has been unmuted.")
        except Exception as e:
            await message.reply_text(f"❌ Couldn't unmute: {e}")

    # ---------------- Ban / Unban ----------------

    @bot.on_message(filters.command("ban") & filters.group)
    async def ban_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/ban <user_id>`.")

        reason = get_reason(message)
        try:
            await bot.ban_chat_member(chat_id, target.id)
            await message.reply_text(f"🚫 {target.mention} has been banned.\nReason: {reason}")
        except Exception as e:
            await message.reply_text(f"❌ Couldn't ban: {e}")

    @bot.on_message(filters.command("unban") & filters.group)
    async def unban_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/unban <user_id>`.")

        try:
            await bot.unban_chat_member(chat_id, target.id)
            await message.reply_text(f"✅ {target.mention} has been unbanned.")
        except Exception as e:
            await message.reply_text(f"❌ Couldn't unban: {e}")

    # ---------------- Promote / Demote ----------------

    @bot.on_message(filters.command("promote") & filters.group)
    async def promote_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/promote <user_id>`.")

        try:
            await bot.promote_chat_member(
                chat_id,
                target.id,
                privileges=ChatPrivileges(
                    can_manage_chat=True,
                    can_delete_messages=True,
                    can_restrict_members=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                ),
            )
            await message.reply_text(f"⭐ {target.mention} has been promoted to admin.")
        except Exception as e:
            await message.reply_text(f"❌ Couldn't promote: {e}")

    @bot.on_message(filters.command("demote") & filters.group)
    async def demote_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/demote <user_id>`.")

        try:
            await bot.promote_chat_member(chat_id, target.id, privileges=ChatPrivileges())
            await message.reply_text(f"⬇️ {target.mention} has been demoted.")
        except Exception as e:
            await message.reply_text(f"❌ Couldn't demote: {e}")

    # ---------------- Warn system ----------------

    @bot.on_message(filters.command("warn") & filters.group)
    async def warn_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/warn <user_id>`.")

        reason = get_reason(message)
        count = await db.add_warn(chat_id, target.id)

        if count >= WARN_LIMIT:
            try:
                await bot.ban_chat_member(chat_id, target.id)
                await db.reset_warns(chat_id, target.id)
                await message.reply_text(
                    f"🚫 {target.mention} reached {WARN_LIMIT} warns and has been banned."
                )
            except Exception as e:
                await message.reply_text(f"❌ Couldn't auto-ban: {e}")
        else:
            await message.reply_text(
                f"⚠️ {target.mention} has been warned ({count}/{WARN_LIMIT}).\nReason: {reason}"
            )

    @bot.on_message(filters.command("unwarn") & filters.group)
    async def unwarn_cmd(_, message: Message):
        chat_id = message.chat.id
        if not await is_group_admin(chat_id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")

        target = await get_target(message)
        if not target:
            return await message.reply_text("Reply to a user, or use `/unwarn <user_id>`.")

        await db.reset_warns(chat_id, target.id)
        await message.reply_text(f"✅ Warnings cleared for {target.mention}.")

    @bot.on_message(filters.command("warnings") & filters.group)
    async def warnings_cmd(_, message: Message):
        chat_id = message.chat.id
        target = await get_target(message) or message.from_user

        count = await db.get_warns(chat_id, target.id)
        await message.reply_text(f"⚠️ {target.mention} has {count}/{WARN_LIMIT} warnings.")
