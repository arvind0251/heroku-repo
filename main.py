import asyncio
import os
import sys
import time
from datetime import datetime

import psutil

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, UserAlreadyParticipant, FloodWait, UserBannedInChannel
from pytgcalls import PyTgCalls, filters as call_filters
from pytgcalls.types import MediaStream

import config
import database as db
import musicqueue as q
from youtube import YouTube
from vclogger import setup_vc_logger
from moderation import setup_moderation
from button_styles import primary_button, success_button, danger_button
from start_menu import send_dm_start, send_help, default_button

# ===================== Clients =====================
bot = Client(
    "musicbot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

assistant = Client(
    "assistant",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.SESSION_STRING,
)

call_py = PyTgCalls(assistant)

ASSISTANT_ID = None  # set at startup after assistant.start()
ASSISTANT_USERNAME = None  # set at startup after assistant.start()
START_TIME = time.time()


# ===================== Helpers =====================

async def log(text: str):
    if config.LOG_GROUP_ID:
        try:
            await bot.send_message(config.LOG_GROUP_ID, text)
        except Exception:
            pass


async def is_authorized(chat_id: int, user_id: int) -> bool:
    if user_id == config.OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return True
    except Exception:
        pass
    return await db.is_auth_user(chat_id, user_id)


async def track_served(message: Message):
    await db.add_served_user(message.from_user.id)
    if message.chat.type != "private":
        await db.add_served_chat(message.chat.id)


async def ensure_assistant_in_chat(chat_id: int) -> bool:
    """Checks if the assistant is already in the group; if not, joins via invite link.
    If the assistant is banned, notifies the group with its username."""
    try:
        member = await bot.get_chat_member(chat_id, ASSISTANT_ID)
        if member.status == ChatMemberStatus.BANNED:
            await bot.send_message(
                chat_id,
                f"❌ My assistant (@{ASSISTANT_USERNAME}) is banned from this group. "
                f"Please unban @{ASSISTANT_USERNAME}, then play the song again.",
            )
            return False
        if member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return True
        # status LEFT or RESTRICTED -> fall through and try to join
    except UserNotParticipant:
        pass
    except Exception:
        pass

    try:
        invite_link = await bot.export_chat_invite_link(chat_id)
    except Exception as e:
        await bot.send_message(
            chat_id,
            "❌ I need the **'Invite Users via Link'** permission so I can add my assistant "
            "to this group. Please make me admin with this permission, then play the song again.",
        )
        await log(f"⚠️ Couldn't create invite link for `{chat_id}` (missing permission): {e}")
        return False

    try:
        await assistant.join_chat(invite_link)
        await log(f"✅ Assistant joined chat `{chat_id}` via invite link.")
        return True
    except UserAlreadyParticipant:
        return True
    except UserBannedInChannel:
        await bot.send_message(
            chat_id,
            f"❌ My assistant (@{ASSISTANT_USERNAME}) is banned from this group. "
            f"Please unban @{ASSISTANT_USERNAME}, then play the song again.",
        )
        return False
    except FloodWait as e:
        await log(f"⚠️ FloodWait while joining `{chat_id}`: wait {e.value}s")
        return False
    except Exception as e:
        await log(f"⚠️ Assistant couldn't join chat `{chat_id}`: {e}")
        return False


async def start_playback(chat_id: int, song: dict):
    """Downloads (or fetches from cache) and starts streaming a song."""
    joined = await ensure_assistant_in_chat(chat_id)
    if not joined:
        return

    local_path = await YouTube.get_playable(song["vidid"], video=song["video"])
    if not local_path:
        await bot.send_message(chat_id, f"❌ Couldn't fetch '{song['title']}'. Try again later.")
        return await play_next(chat_id)

    await call_py.play(chat_id, MediaStream(local_path))
    q.set_current(chat_id, song)
    q.set_paused(chat_id, False)

    buttons = InlineKeyboardMarkup(
        [
            [
                default_button("⏭", callback_data="ctl_skip"),
                default_button("⏹", callback_data="ctl_stop"),
                default_button("⏸", callback_data="ctl_pause"),
            ],
            [
                primary_button("➕", callback_data="ctl_queue"),
                danger_button("Close", callback_data="ctl_close"),
            ],
        ]
    )
    text = (
        "🎵 **Now Playing**\n\n"
        f"**Title:** {song['title']}\n"
        f"**Duration:** {song['duration']}\n"
        f"**Requested by:** {song['requested_by']}"
    )
    await bot.send_message(chat_id, text, reply_markup=buttons)
    await log(
        f"🎵 Song played\nChat: `{chat_id}`\nTitle: {song['title']}\n"
        f"Requested by: {song['requested_by']}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


async def play_next(chat_id: int):
    next_song = q.pop_next(chat_id)
    if next_song:
        await start_playback(chat_id, next_song)
    else:
        q.clear_current(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


@call_py.on_update(call_filters.stream_end())
async def stream_end_handler(_, update):
    await play_next(update.chat_id)


# ===================== Commands =====================

@bot.on_message(filters.new_chat_members)
async def welcome_cmd(_, message: Message):
    for member in message.new_chat_members:
        await message.reply_text(f"💓 welcome {member.mention}")


@bot.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await track_served(message)

    if message.chat.type.name == "PRIVATE":
        return await send_dm_start(_, message)

    buttons = InlineKeyboardMarkup(
        [
            [
                primary_button("👨‍💻 Developer", url="https://t.me/Avisha_Asstiant"),
                success_button("💬 Support", url="https://t.me/Avisha_101"),
            ]
        ]
    )
    await message.reply_text(
        "Hi! I'm Avisha, a music bot. Use /help to see all commands.",
        reply_markup=buttons,
    )


@bot.on_message(filters.command("help"))
async def help_cmd(_, message: Message):
    await send_help(_, message.chat.id)


@bot.on_callback_query(filters.regex("^show_help$"))
async def show_help_cb(_, cq: CallbackQuery):
    await cq.answer()
    await send_help(_, cq.message.chat.id)


async def _play_handler(_, message: Message, video: bool):
    await track_served(message)
    chat_id = message.chat.id

    if len(message.command) < 2:
        return await message.reply_text("Give me a song name or link. Example: `/play tum hi ho`")

    query = message.text.split(None, 1)[1]
    searching = await message.reply_text("🔎 Searching...")

    details, vidid = await YouTube.track(query, videoid=False)
    if not vidid:
        return await searching.edit_text("❌ Nothing found for that.")

    if details["duration_sec"] and details["duration_sec"] > config.DURATION_LIMIT:
        return await searching.edit_text(
            f"❌ This song is too long ({details['duration_min']}). "
            f"Max allowed: {config.DURATION_LIMIT // 60} min."
        )

    song = {
        "title": details["title"],
        "vidid": vidid,
        "duration": details["duration_min"],
        "requested_by": message.from_user.mention,
        "video": video,
    }

    if q.is_active(chat_id):
        added = q.add_to_queue(chat_id, song)
        if not added:
            return await searching.edit_text(f"❌ Queue is full (max {config.QUEUE_LIMIT}).")

        position = len(q.get_queue(chat_id))
        text = (
            f"✅ **Added to queue: {position}**\n\n"
            f"**Title:** {song['title']}\n"
            f"**Duration:** {song['duration']}\n"
            f"**Requested by:** {song['requested_by']}"
        )
        buttons = InlineKeyboardMarkup(
            [
                [
                    danger_button("▶️ Play Now", callback_data=f"ctl_playnow:{song['vidid']}"),
                    danger_button("Close", callback_data="ctl_close"),
                ]
            ]
        )
        await searching.delete()
        await bot.send_message(chat_id, text, reply_markup=buttons)
        try:
            await message.delete()
        except Exception:
            pass
        return

    q.add_to_queue(chat_id, song)
    await searching.delete()
    first_song = q.pop_next(chat_id)
    await start_playback(chat_id, first_song)
    try:
        await message.delete()
    except Exception:
        pass


@bot.on_message(filters.command("play"))
async def play_cmd(client, message: Message):
    await _play_handler(client, message, video=False)


@bot.on_message(filters.command("vplay"))
async def vplay_cmd(client, message: Message):
    await _play_handler(client, message, video=True)


@bot.on_callback_query(filters.regex("^ctl_"))
async def control_buttons_cb(_, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    action = cq.data.split("_", 1)[1]

    if not await is_authorized(chat_id, cq.from_user.id):
        return await cq.answer("❌ Only admins/authorized users can do this.", show_alert=True)

    if action.startswith("playnow:"):
        vidid = action.split(":", 1)[1]
        moved = q.move_to_front(chat_id, vidid)
        if not moved:
            return await cq.answer("Song not found in queue.", show_alert=True)
        await cq.answer("▶️ Playing now...")
        try:
            await cq.message.delete()
        except Exception:
            pass
        await play_next(chat_id)

    elif action == "pause":
        if q.is_paused(chat_id):
            await call_py.resume(chat_id)
            q.set_paused(chat_id, False)
            await cq.answer("▶️ Resumed.")
            new_buttons = InlineKeyboardMarkup(
                [
                    [
                        default_button("⏭", callback_data="ctl_skip"),
                        default_button("⏹", callback_data="ctl_stop"),
                        default_button("⏸", callback_data="ctl_pause"),
                    ],
                    [
                        primary_button("➕", callback_data="ctl_queue"),
                        danger_button("Close", callback_data="ctl_close"),
                    ],
                ]
            )
        else:
            await call_py.pause(chat_id)
            q.set_paused(chat_id, True)
            await cq.answer("⏸ Paused.")
            new_buttons = InlineKeyboardMarkup(
                [
                    [
                        default_button("⏭", callback_data="ctl_skip"),
                        default_button("⏹", callback_data="ctl_stop"),
                        default_button("▶️", callback_data="ctl_pause"),
                    ],
                    [
                        primary_button("➕", callback_data="ctl_queue"),
                        danger_button("Close", callback_data="ctl_close"),
                    ],
                ]
            )
        try:
            await cq.message.edit_reply_markup(new_buttons)
        except Exception:
            pass

    elif action == "skip":
        await cq.answer("⏭ Skipped.")
        await play_next(chat_id)

    elif action == "stop":
        q.clear_queue(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass
        await cq.answer("⏹ Stopped.")
        try:
            await cq.message.delete()
        except Exception:
            pass

    elif action == "queue":
        songs = q.get_queue(chat_id)
        if not songs:
            await cq.answer("Queue is empty.", show_alert=True)
        else:
            preview = "\n".join(f"{i}. {s['title']}" for i, s in enumerate(songs[:10], 1))
            await cq.answer(preview, show_alert=True)

    elif action == "close":
        await cq.answer()
        try:
            await cq.message.delete()
        except Exception:
            pass


@bot.on_message(filters.command("pause"))
async def pause_cmd(_, message: Message):
    if not await is_authorized(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins/authorized users can do this.")
    await call_py.pause(message.chat.id)
    await message.reply_text("⏸ Paused.")


@bot.on_message(filters.command("resume"))
async def resume_cmd(_, message: Message):
    if not await is_authorized(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins/authorized users can do this.")
    await call_py.resume(message.chat.id)
    await message.reply_text("▶️ Resumed.")


@bot.on_message(filters.command("skip"))
async def skip_cmd(_, message: Message):
    if not await is_authorized(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins/authorized users can do this.")
    await message.reply_text("⏭ Skipped.")
    await play_next(message.chat.id)
    try:
        await message.delete()
    except Exception:
        pass


@bot.on_message(filters.command(["stop", "end"]))
async def stop_cmd(_, message: Message):
    if not await is_authorized(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins/authorized users can do this.")
    q.clear_queue(message.chat.id)
    q.clear_current(message.chat.id)
    try:
        await call_py.leave_call(message.chat.id)
    except Exception:
        pass
    await message.reply_text("⏹ Stopped and cleared the queue.")
    try:
        await message.delete()
    except Exception:
        pass


@bot.on_message(filters.command("queue"))
async def queue_cmd(_, message: Message):
    songs = q.get_queue(message.chat.id)
    if not songs:
        return await message.reply_text("Queue is empty.")
    text = "📋 **Queue:**\n\n"
    for i, s in enumerate(songs, 1):
        text += f"{i}. {s['title']} — {s['requested_by']}\n"
    await message.reply_text(text)


@bot.on_message(filters.command("shuffle"))
async def shuffle_cmd(_, message: Message):
    if not await is_authorized(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins/authorized users can do this.")
    if q.shuffle_queue(message.chat.id):
        await message.reply_text("🔀 Queue shuffled.")
    else:
        await message.reply_text("Need at least 2 songs in the queue to shuffle.")


@bot.on_message(filters.command("authuser"))
async def authuser_cmd(_, message: Message):
    chat_id = message.chat.id
    if not await is_authorized(chat_id, message.from_user.id):
        return await message.reply_text("❌ Only admins can manage authorized users.")

    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target = await bot.get_users(message.command[1])
        except Exception:
            return await message.reply_text("❌ User not found.")

    if not target:
        return await message.reply_text("Reply to a member's message, or use `/authuser <user_id>`.")

    already = await db.is_auth_user(chat_id, target.id)
    if already:
        await db.remove_auth_user(chat_id, target.id)
        await message.reply_text(f"🚫 Removed {target.mention}'s authorized access.")
    else:
        await db.add_auth_user(chat_id, target.id)
        await message.reply_text(f"✅ {target.mention} is now an authorized user.")


@bot.on_message(filters.command("id"))
async def id_cmd(_, message: Message):
    target = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        query = message.command[1].lstrip("@")
        try:
            target = await bot.get_users(query)
        except Exception:
            return await message.reply_text("❌ User not found.")
    else:
        return await message.reply_text("Reply to a message, or use `/id @username`.")

    await message.reply_text(
        f"👤 **User Info**\nName: {target.first_name}\nUsername: @{target.username or 'N/A'}\nID: `{target.id}`"
    )


@bot.on_message(filters.command("status") & filters.user(config.OWNER_ID))
async def status_cmd(_, message: Message):
    process = psutil.Process(os.getpid())

    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    bot_ram_mb = process.memory_info().rss / 1024 / 1024

    ffmpeg_count = sum(1 for p in psutil.process_iter(["name"]) if p.info["name"] and "ffmpeg" in p.info["name"].lower())

    disk = psutil.disk_usage(config.STORAGE_DIR)
    storage_used_gb = disk.used / 1024 / 1024 / 1024
    storage_total_gb = disk.total / 1024 / 1024 / 1024

    try:
        calls_dict = await call_py.calls
        active_calls = len(calls_dict or {})
    except Exception:
        active_calls = "N/A"

    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    thread_count = process.num_threads()
    open_files = len(process.open_files())

    text = (
        "📊 **Bot Status**\n\n"
        f"**Uptime:** {hours}h {minutes}m {seconds}s\n\n"
        f"**System CPU:** {cpu_percent}%\n"
        f"**System RAM:** {ram.percent}% ({ram.used / 1024 / 1024 / 1024:.1f}GB / {ram.total / 1024 / 1024 / 1024:.1f}GB)\n\n"
        f"**Bot process RAM:** {bot_ram_mb:.1f} MB\n"
        f"**Bot threads:** {thread_count}\n"
        f"**Bot open files/sockets:** {open_files}\n\n"
        f"**Active ffmpeg processes:** {ffmpeg_count}\n"
        f"**Active VC calls:** {active_calls}\n\n"
        f"**Storage:** {storage_used_gb:.1f}GB / {storage_total_gb:.1f}GB used"
    )
    await message.reply_text(text)


@bot.on_message(filters.command("restart") & filters.user(config.OWNER_ID))
async def restart_cmd(_, message: Message):
    msg = await message.reply_text("🔄 Restarting bot...")
    with open("/tmp/musicbot_restart.txt", "w") as f:
        f.write(f"{msg.chat.id}\n{msg.id}")
    await log(f"🔄 Bot restarting (triggered by owner)\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    os.execl(sys.executable, sys.executable, *sys.argv)


@bot.on_message(filters.command("broadcast") & filters.user(config.OWNER_ID))
async def broadcast_cmd(_, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text("Give some text to broadcast, or reply to a message with `/broadcast`.")

    sent, failed = 0, 0
    users = await db.get_served_users()
    chats = await db.get_served_chats()

    status = await message.reply_text("📢 Starting broadcast...")

    for uid in users:
        try:
            if message.reply_to_message:
                await message.reply_to_message.copy(uid)
            else:
                await bot.send_message(uid, message.text.split(None, 1)[1])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.1)

    for cid in chats:
        try:
            if message.reply_to_message:
                await message.reply_to_message.copy(cid)
            else:
                await bot.send_message(cid, message.text.split(None, 1)[1])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.1)

    await status.edit_text(f"✅ Broadcast complete.\nSent: {sent} | Failed: {failed}")


# ===================== Startup =====================

async def main():
    global ASSISTANT_ID, ASSISTANT_USERNAME
    await bot.start()
    await assistant.start()
    me = await assistant.get_me()
    ASSISTANT_ID = me.id
    ASSISTANT_USERNAME = me.username
    await call_py.start()
    setup_vc_logger(bot, assistant, call_py)
    setup_moderation(bot)

    restart_file = "/tmp/musicbot_restart.txt"
    if os.path.exists(restart_file):
        try:
            with open(restart_file) as f:
                chat_id_str, msg_id_str = f.read().strip().split("\n")
            await bot.edit_message_text(int(chat_id_str), int(msg_id_str), "✅ Bot restarted successfully!")
        except Exception as e:
            print(f"[restart] Couldn't edit restart confirmation: {e}")
        finally:
            os.remove(restart_file)

    await log(f"✅ Bot start ho gaya!\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Bot started.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
