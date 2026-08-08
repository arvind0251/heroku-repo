from pyrogram.types import InlineKeyboardButton
from pyrogram.enums import ButtonStyle


def primary_button(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """Blue button — for main/neutral actions."""
    return InlineKeyboardButton(text, callback_data=callback_data, url=url, style=ButtonStyle.PRIMARY)


def success_button(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """Green button — for positive actions."""
    return InlineKeyboardButton(text, callback_data=callback_data, url=url, style=ButtonStyle.SUCCESS)


def danger_button(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """Red button — for destructive/closing actions."""
    return InlineKeyboardButton(text, callback_data=callback_data, url=url, style=ButtonStyle.DANGER)


def default_button(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    """No color — app-default style."""
    return InlineKeyboardButton(text, callback_data=callback_data, url=url)
  
