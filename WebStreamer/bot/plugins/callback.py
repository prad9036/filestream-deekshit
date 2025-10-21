# This file is a part of FileStreamBot
# Adjusted to avoid ImportError by importing file_format inside the function to prevent circular imports.
# Keeps corrected indentation and filename-in-url support for download links.

import datetime
import urllib.parse
import logging

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from WebStreamer.utils.database import Database
from WebStreamer.utils.human_readable import humanbytes
from WebStreamer.vars import Var
from WebStreamer.server.exceptions import FIleNotFound

# Initialize DB instance (match how other modules do it)
db = Database(Var.DATABASE_URL, Var.SESSION_NAME)


async def gen_file_menu(_id, update):
    """
    Build and edit the message caption / reply markup for a file.
    This function fetches file info from DB and edits the callback message.
    Import file_format locally to avoid circular imports at module import time.
    """
    try:
        myfile_info = await db.get_file(_id)
    except FIleNotFound:
        await update.answer("File Not Found")
        return

    # Import here to avoid circular import issues during module import
    try:
        from WebStreamer.utils.bot_utils import file_format
    except Exception as e:
        logging.exception("Failed to import file_format: %s", e)
        # fallback: set a generic type
        def file_format(_): 
            return "Unknown"

    file_type = file_format(myfile_info["file_id"])

    # Build links. Include filename in the dl URL (URL-encoded).
    safe_filename = urllib.parse.quote(myfile_info.get("file_name", "file"))
    page_link = f"{Var.URL}watch/{myfile_info['_id']}"
    stream_link = f"{Var.URL}dl/{myfile_info['_id']}/{safe_filename}"

    TiMe = myfile_info.get("time")
    if isinstance(TiMe, float):
        date = datetime.datetime.fromtimestamp(TiMe)
        created_date = date.date()
        created_time = date.time().strftime("%I:%M:%S %p %Z")
    else:
        # If time is stored as string or not set
        created_date = TiMe if isinstance(TiMe, str) else "N/A"
        created_time = "N/A"

    try:
        caption = "Name: {}\nFile Size: {}\nType: {}\nCreated at: {}\nTime: {}".format(
            myfile_info.get("file_name", "N/A"),
            humanbytes(int(myfile_info.get("file_size", 0))),
            file_type,
            created_date,
            created_time,
        )

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🖥STREAM", url=page_link),
                    InlineKeyboardButton("Dᴏᴡɴʟᴏᴀᴅ 📥", url=stream_link),
                ]
            ]
        )

        # Edit the message caption and reply markup (pyrogram CallbackQuery.edit_message_caption)
        await update.edit_message_caption(caption=caption, reply_markup=reply_markup)
    except Exception as e:
        logging.exception("Failed to edit message for file %s: %s", _id, e)
        # try to answer the callback so UI isn't left hanging
        try:
            await update.answer("An error occurred while processing the request.")
        except Exception:
            pass


# Small dispatcher for callback data. Integrate this with your existing callback handler.
async def callback_query_handler(update: CallbackQuery):
    """
    A small dispatcher that parses callback data and routes to appropriate handlers.
    Expects callback.data like: "myfile:<id>" or "sendfile:<id>" etc.
    """
    data = update.data or ""
    parts = data.split(":")
    cmd = parts[0] if parts else ""
    args = parts[1:] if len(parts) > 1 else []

    try:
        if cmd == "myfile" and len(args) >= 1:
            await gen_file_menu(args[0], update)
            return
        elif cmd == "sendfile" and len(args) >= 1:
            myfile = await db.get_file(args[0])
            await update.answer(f"Sending File {myfile['file_name']}")
            await update.message.reply_cached_media(myfile["file_id"])
            return
        elif cmd == "accepttos" and len(args) >= 1:
            # Mark user as accepted TOS
            await db.agreed_tos(int(args[0]))
            await update.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✅ I accepted the TOS", callback_data="N/A")]]
                )
            )
            return
        # add other callback commands handling here as needed

    except FIleNotFound:
        await update.answer("File Not Found")
        return
    except Exception as e:
        logging.exception("Error handling callback query: %s", e)
        try:
            await update.answer("An internal error occurred.")
        except Exception:
            pass
