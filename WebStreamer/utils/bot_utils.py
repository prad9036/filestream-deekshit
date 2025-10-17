# This file is a part of FileStreamBot

import urllib.parse
from WebStreamer.utils.Translation import Language
from WebStreamer.utils.file_properties import get_name, get_file_ids
from WebStreamer.utils.human_readable import humanbytes
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

async def gen_link(m: Message, _id, name: list) -> tuple[InlineKeyboardMarkup, str]:
    """Generate Text for Stream Link, Reply Text and reply_markup"""
    lang = Language(m)
    file_name = get_name(m)
    file_size = humanbytes(get_media_file_size(m))

    page_link = f"{Var.URL}watch/{_id}"
    # include filename, URL-encoded
    safe_filename = urllib.parse.quote(file_name)
    stream_link = f"{Var.URL}dl/{_id}/{safe_filename}"

    Stream_Text = lang.STREAM_MSG_TEXT.format(file_name, file_size, stream_link, page_link, name[0], name[1])
    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🖥STREAM", url=page_link), InlineKeyboardButton("Dᴏᴡɴʟᴏᴀᴅ 📥", url=stream_link)]
        ]
    )

    return reply_markup, Stream_Text