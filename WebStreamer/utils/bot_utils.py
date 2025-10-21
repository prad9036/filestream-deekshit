# This file is a part of FileStreamBot
# Restored helper functions and added gen_link to match other plugins' imports.
# Robust imports and fallbacks are used to avoid circular import issues.

import time
import logging
import urllib.parse
from typing import Optional, Tuple, List

from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.errors import UserNotParticipant

from WebStreamer.vars import Var
from WebStreamer.utils.database import Database
from WebStreamer.utils.Translation import Language
from WebStreamer.utils.human_readable import humanbytes

# Database instance (matches how other modules instantiate it)
db = Database(Var.DATABASE_URL, Var.SESSION_NAME)


async def is_user_exist(message: Message):
    """
    Ensure a user document exists in the DB. If not, create one and notify BIN_CHANNEL.
    """
    try:
        if not bool(await db.get_user(message.from_user.id)):
            await db.add_user(message.from_user.id)
            # Notify bin channel about new user (best-effort)
            try:
                await message._client.send_message(
                    Var.BIN_CHANNEL,
                    f"**Nᴇᴡ Usᴇʀ Jᴏɪɴᴇᴅ:** \n\n__Mʏ Nᴇᴡ Fʀɪᴇɴᴅ__ [{message.from_user.first_name}](tg://user?id={message.from_user.id}) __Sᴛᴀʀᴛᴇᴅ Yᴏᴜʀ Bᴏᴛ !!__",
                )
            except Exception:
                logging.debug("Could not notify BIN_CHANNEL about new user", exc_info=True)
    except Exception:
        logging.exception("Error in is_user_exist")


async def is_user_accepted_tos(message: Message) -> bool:
    """
    Check whether the user has accepted the Terms of Service.
    If not, prompt them with the TOS and a button to accept.
    """
    try:
        user = await db.get_user(message.from_user.id)
        if not user or not user.get("agreed_to_tos"):
            # Ask user to accept TOS
            await message.reply(
                f"Hi {message.from_user.mention},\nplease read and accept the Terms of Service to continue using the bot"
            )
            if Var.TOS:
                await message.reply_text(
                    Var.TOS,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("I accept the TOS", callback_data=f"accepttos_{message.from_user.id}")]]
                    ),
                    disable_web_page_preview=True,
                )
            return False
        return True
    except Exception:
        logging.exception("Error checking user TOS status")
        return False


async def is_allowed(message: Message) -> bool:
    """
    If ALLOWED_USERS is set, ensure the user is in that list.
    """
    try:
        if Var.ALLOWED_USERS:
            user_allowed = (str(message.from_user.id) in Var.ALLOWED_USERS) or (message.from_user.username in Var.ALLOWED_USERS)
            if not user_allowed:
                await message.reply("You are not in the allowed list of users who can use me.", quote=True)
                return False
        return True
    except Exception:
        logging.exception("Error checking allowed users")
        return False


async def is_user_banned(message: Message, lang: Optional[Language] = None) -> bool:
    """
    Check if user is banned via the blacklist collection.
    If banned, send a ban message (uses language object if provided).
    """
    try:
        banned = await db.is_user_banned(message.from_user.id)
        if banned:
            if not lang:
                lang = Language(message)
            await message.reply_text(
                text=lang.BAN_TEXT.format(Var.OWNER_ID),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            return True
        return False
    except Exception:
        logging.exception("Error checking if user is banned")
        return False


async def is_user_joined(message: Message, lang: Language) -> bool:
    """
    Ensure the user has joined the updates channel (if FORCE_UPDATES_CHANNEL is set).
    Returns False and prompts user to join if not a member.
    """
    try:
        # get_chat_member can raise UserNotParticipant or return a member object
        member = await message._client.get_chat_member(Var.UPDATES_CHANNEL, message.chat.id)
        if getattr(member, "status", "").upper() == "BANNED":
            await message.reply_text(
                text=lang.BAN_TEXT.format(Var.OWNER_ID),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            return False
        return True
    except UserNotParticipant:
        await message.reply_text(
            text="<i>Jᴏɪɴ ᴍʏ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ 🔐</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Jᴏɪɴ ɴᴏᴡ 🔓", url=f"https://t.me/{Var.UPDATES_CHANNEL}")]]),
            disable_web_page_preview=True,
        )
        return False
    except Exception:
        logging.exception("Error checking updates channel membership")
        return False


async def validate_user(message: Message, lang: Optional[Language] = None) -> bool:
    """
    Full validation chain used by command handlers:
      - allowed list
      - ensure user exists in DB
      - TOS acceptance (if configured)
      - not banned
      - joined updates channel (if configured)
    """
    try:
        if not await is_allowed(message):
            return False
        await is_user_exist(message)
        if Var.TOS:
            if not await is_user_accepted_tos(message):
                return False

        if not lang:
            lang = Language(message)
        if await is_user_banned(message, lang):
            return False
        if Var.FORCE_UPDATES_CHANNEL:
            if not await is_user_joined(message, lang):
                return False
        return True
    except Exception:
        logging.exception("Error validating user")
        return False


def file_format(file_id) -> str:
    """
    Lightweight fallback to determine a friendly file type name.
    The original repo maps FileId / file_type to a label; here we implement a robust fallback
    that avoids importing pyrogram internals at module import time.

    This returns one of: 'Photo', 'Voice', 'Video', 'Document', 'Sticker', 'Audio', or 'Unknown'.
    It's intentionally conservative to avoid import-time failures.
    """
    try:
        # If file_id is a dict-like or object with file_type attribute, try to inspect it.
        ft = None
        if isinstance(file_id, str):
            # decoding Telethon-style/pyrogram FileId isn't done here; fall back to Unknown.
            return "Unknown"
        # object-like file_id
        ft = getattr(file_id, "file_type", None)
        # Some objects expose a .file_type.name (enum)
        if ft and hasattr(ft, "name"):
            name = ft.name.lower()
            if "photo" in name:
                return "Photo"
            if "voice" in name:
                return "Voice"
            if name in ("video", "animation", "video_note"):
                return "Video"
            if name == "document":
                return "Document"
            if name == "sticker":
                return "Sticker"
            if name == "audio":
                return "Audio"
        # If file_id exposes .media or .mime_type, use that
        mime = getattr(file_id, "mime_type", None) or getattr(file_id, "media", None)
        if isinstance(mime, str):
            if mime.startswith("image/"):
                return "Photo"
            if mime.startswith("video/"):
                return "Video"
            if mime.startswith("audio/"):
                return "Audio"
        return "Unknown"
    except Exception:
        logging.exception("Error determining file format")
        return "Unknown"


# --------------------------------------------------------------------
# gen_link: generate stream/download links and reply markup + message text
# --------------------------------------------------------------------
async def gen_link(m: Message, _id: str, name: List[str]) -> Tuple[InlineKeyboardMarkup, str]:
    """
    Generate Text for Stream Link, Reply Text and reply_markup

    Args:
      m: pyrogram.types.Message (the message containing the media or context)
      _id: database id / hash for the file
      name: list [uploader_name, uploader_mention] or similar used in STREAM_MSG_TEXT formatting

    Returns:
      (reply_markup, Stream_Text)
    """
    try:
        lang = Language(m)
        # Prefer using a repository helper get_name if available
        try:
            from WebStreamer.utils.file_properties import get_name, get_media_file_size
        except Exception:
            # Fallback helpers if the imports are not available
            def get_name(msg: Message) -> str:
                # try common places for filename
                try:
                    if hasattr(msg, "media") and msg.media and hasattr(msg.media, "file_name"):
                        return getattr(msg.media, "file_name") or "file"
                    if getattr(msg, "document", None):
                        return getattr(msg.document, "file_name", "file")
                    if getattr(msg, "photo", None):
                        return "photo.jpg"
                except Exception:
                    pass
                return "file"

            def get_media_file_size(msg: Message) -> int:
                try:
                    # try common attributes
                    if getattr(msg, "document", None):
                        return int(getattr(msg.document, "file_size", 0) or 0)
                    if getattr(msg, "photo", None):
                        # photos may have sizes array; fallback to 0
                        return 0
                    return int(getattr(msg, "file_size", 0) or 0)
                except Exception:
                    return 0

        file_name = get_name(m)
        file_size_bytes = get_media_file_size(m)
        file_size = humanbytes(file_size_bytes)

        page_link = f"{Var.URL}watch/{_id}"
        safe_filename = urllib.parse.quote(file_name)
        stream_link = f"{Var.URL}dl/{_id}/{safe_filename}"

        # STREAM_MSG_TEXT expected placeholders: (file_name, file_size, stream_link, page_link, name[0], name[1])
        Stream_Text = lang.STREAM_MSG_TEXT.format(file_name, file_size, stream_link, page_link, name[0], name[1])

        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🖥STREAM", url=page_link), InlineKeyboardButton("Dᴏᴡɴʟᴏᴀᴅ 📥", url=stream_link)]
            ]
        )

        return reply_markup, Stream_Text
    except Exception:
        logging.exception("Error generating links")
        # Return minimal fallback
        page_link = f"{Var.URL}watch/{_id}"
        stream_link = f"{Var.URL}dl/{_id}"
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🖥STREAM", url=page_link), InlineKeyboardButton("Dᴏᴡɴʟᴏᴀᴅ 📥", url=stream_link)]]
        )
        lang = Language(m)
        Stream_Text = lang.STREAM_MSG_TEXT.format("file", "N/A", stream_link, page_link, "", "")
        return reply_markup, Stream_Text
