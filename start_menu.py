import os

from pyrogram.types import InlineKeyboardMarkup, Message, MessageEntity
from pyrogram.enums import MessageEntityType

from button_styles import primary_button, success_button, danger_button

BANNER_PATH = os.path.join(os.path.dirname(__file__), "assets", "start_banner.jpg")

DEVELOPER_URL = "https://t.me/Avisha_Asstiant"
SUPPORT_URL = "https://t.me/Avisha_101"
SOURCE_URL = "https://t.me/Avisha_101"

EMOJI_DIAMOND = "5188375125552033525"   # 💎
EMOJI_HELP = "5190566778643702939"      # 📍
EMOJI_DEV = "5190850877845433996"       # 🎁
EMOJI_MUSIC = "5190849937247595090"     # 🎁


def build_entities(text: str, emoji_map: dict):
    """emoji_map: {emoji_char: custom_emoji_id}"""
    entities = []
    for emoji_char, emoji_id in emoji_map.items():
        idx = text.find(emoji_char)
        if idx != -1:
            entities.append(
                MessageEntity(
                    type=MessageEntityType.CUSTOM_EMOJI,
                    offset=idx,
                    length=len(emoji_char),
                    custom_emoji_id=emoji_id,
                )
            )
    return entities


async def send_dm_start(bot, message: Message):
    """Sends the photo-based welcome menu, used only in private chats (DM)."""
    caption = (
        f"Hey {message.from_user.mention}, 💎\n\n"
        "This is **Avisha** !\n\n"
        "A music player bot with some awesome and useful features.\n\n"
        "Click on the help button for more info."
    )

    entities = build_entities(caption, {"💎": EMOJI_DIAMOND})

    buttons = InlineKeyboardMarkup(
        [
            [primary_button("➕ Add me to your group", url=f"https://t.me/{bot.me.username}?startgroup=true")],
            [success_button("❓ Help", callback_data="show_help")],
            [
                primary_button("👨‍💻 Developer", url=DEVELOPER_URL),
                success_button("💬 Support", url=SUPPORT_URL),
            ],
            [danger_button("📢 Source", url=SOURCE_URL)],
        ]
    )

    if os.path.exists(BANNER_PATH):
        await message.reply_photo(BANNER_PATH, caption=caption, reply_markup=buttons, caption_entities=entities)
    else:
        await message.reply_text(caption, reply_markup=buttons, entities=entities)


HELP_TEXT = (
    "🎁 **Avisha Commands**\n\n"
    "**Music**\n"
    "/play <song> - play a song\n"
    "/vplay <song> - play a video\n"
    "/pause - pause playback\n"
    "/resume - resume playback\n"
    "/skip - skip current song\n"
    "/stop or /end - stop and clear queue\n"
    "/queue - view the queue\n"
    "/shuffle - shuffle the queue\n\n"
    "**Group Management**\n"
    "/authuser - grant/revoke permission (reply to a user)\n"
    "/vclogger - toggle VC join/leave logging\n\n"
    "**Moderation** (admins only)\n"
    "/mute /unmute - restrict/allow messages\n"
    "/ban /unban - remove/allow a user\n"
    "/promote /demote - manage admin status\n"
    "/warn /unwarn /warnings - warning system (3 warns = auto-ban)\n\n"
    "**Utility**\n"
    "/id - get numeric ID (reply or @username)\n"
    "/status - bot diagnostics (owner only)\n"
    "/restart - restart the bot (owner only)\n"
    "/broadcast - message all users/chats (owner only)"
)


async def send_help(bot, chat_id: int):
    entities = build_entities(HELP_TEXT, {"🎁": EMOJI_MUSIC})

    buttons = InlineKeyboardMarkup(
        [
            [
                primary_button("👨‍💻 Developer", url=DEVELOPER_URL),
                success_button("💬 Support", url=SUPPORT_URL),
            ]
        ]
    )
    await bot.send_message(chat_id, HELP_TEXT, reply_markup=buttons, entities=entities)
