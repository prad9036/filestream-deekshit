# This file is a part of FileStreamBot

from __future__ import annotations
import logging
from datetime import datetime
from pyrogram import Client
from typing import Any, Optional
from pyrogram.types import Message
from pyrogram.file_id import FileId
from WebStreamer.bot import StreamBot
from WebStreamer.utils.database import Database
from WebStreamer.vars import Var

db = Database(Var.DATABASE_URL, Var.SESSION_NAME)


async def get_file_ids(
    message: Message | None,
    client: Client | bool,
    db_id: str,
    multi_clients,
) -> Optional[FileId]:
    """
    message: original incoming pyrogram Message (or None). If provided, the function
             will try to forward the original message into Var.BIN_CHANNEL so the
             channel message shows "Forwarded from <chat name>".
    client: pyrogram Client object for which to return the FileId (or False to skip)
    db_id: database id of the file record
    multi_clients: dict of client instances used to extract per-client file_ids
    """
    logging.debug("Starting of get_file_ids")
    file_info = await db.get_file(db_id)

    def _get_msg_id(msg: Message) -> Optional[int]:
        # Support both pyrogram versions that use `id` or `message_id`
        if not msg:
            return None
        return getattr(msg, "message_id", None) or getattr(msg, "id", None)

    def _get_from_chat_id(msg: Message) -> Optional[int]:
        # Prefer chat.id, fallback to chat or from_user id
        if not msg:
            return None
        chat = getattr(msg, "chat", None)
        if chat:
            return getattr(chat, "id", None) or getattr(chat, "chat_id", None)
        from_user = getattr(msg, "from_user", None)
        if from_user:
            return getattr(from_user, "id", None)
        # As last resort, try msg.chat_id or msg.sender_chat id attributes
        return getattr(msg, "chat_id", None) or getattr(msg, "sender_chat", None)

    # If there are no file_ids stored yet or client is False, store a copy/log message in BIN_CHANNEL
    if (not "file_ids" in file_info) or not client:
        logging.debug("Storing file_id of all clients in DB")

        # Try forwarding the original incoming message so it appears as "Forwarded from ..."
        log_msg = None
        if message is not None:
            try:
                msg_id = _get_msg_id(message)
                from_chat = _get_from_chat_id(message)
                if not msg_id:
                    logging.warning("Original message has no id; cannot forward by id, will fallback to send_cached_media")
                else:
                    forwarded = await StreamBot.forward_messages(
                        chat_id=Var.BIN_CHANNEL,
                        from_chat_id=from_chat,
                        message_ids=msg_id,
                    )
                    # forward_messages can return a Message or a list of Messages
                    if isinstance(forwarded, list):
                        log_msg = forwarded[0] if forwarded else None
                    else:
                        log_msg = forwarded
            except Exception as e:
                logging.exception("Forward to BIN_CHANNEL failed, falling back to send_cached_media: %s", e)

        # If forwarding didn't produce a log message, fallback to the existing cached-send behavior
        if not log_msg:
            try:
                log_msg = await send_file(StreamBot, file_info["file_id"])
            except Exception:
                logging.exception("Fallback send_cached_media also failed")

        if log_msg:
            # update file_ids for all multi_clients using the created log message id
            await db.update_file_ids(db_id, await update_file_id(log_msg.id, multi_clients))
            logging.debug("Stored file_id of all clients in DB")
        else:
            logging.warning("No log message created in BIN_CHANNEL; skipping update_file_ids")

        if not client:
            return

        # re-fetch file_info after storing
        file_info = await db.get_file(db_id)

    file_id_info = file_info.setdefault("file_ids", {})

    # If current client doesn't have a stored file_id, create one by ensuring there's a BIN_CHANNEL message
    if not str(client.id) in file_id_info:
        logging.debug("Storing file_id in DB")
        log_msg = None

        if message is not None:
            try:
                msg_id = _get_msg_id(message)
                from_chat = _get_from_chat_id(message)
                if not msg_id:
                    logging.warning("Original message has no id; cannot forward by id for per-client step, will fallback to send_cached_media")
                else:
                    forwarded = await StreamBot.forward_messages(
                        chat_id=Var.BIN_CHANNEL,
                        from_chat_id=from_chat,
                        message_ids=msg_id,
                    )
                    if isinstance(forwarded, list):
                        log_msg = forwarded[0] if forwarded else None
                    else:
                        log_msg = forwarded
            except Exception as e:
                logging.exception("Forward to BIN_CHANNEL failed (per-client step), falling back: %s", e)

        if not log_msg:
            try:
                log_msg = await send_file(StreamBot, file_info["file_id"])
            except Exception:
                logging.exception("Fallback send_cached_media also failed (per-client step)")

        if not log_msg:
            logging.warning("No BIN_CHANNEL message available to extract file_id for client %s", getattr(client, "id", "unknown"))
            # continue; will likely raise/return later

        # fetch message as seen by the target client to extract that client's file_id
        try:
            msg = await client.get_messages(Var.BIN_CHANNEL, log_msg.id)
            media = get_media_from_message(msg)
            file_id_info[str(client.id)] = getattr(media, "file_id", "")
            await db.update_file_ids(db_id, file_id_info)
            logging.debug("Stored file_id in DB")
        except Exception:
            logging.exception("Failed to get_messages from client %s when updating file_id", getattr(client, "id", None))

    logging.debug("Middle of get_file_ids")
    file_id = FileId.decode(file_id_info[str(client.id)])
    setattr(file_id, "file_size", file_info["file_size"])
    setattr(file_id, "mime_type", file_info["mime_type"])
    setattr(file_id, "file_name", file_info["file_name"])
    setattr(file_id, "unique_id", file_info["file_unique_id"])
    logging.debug("Ending of get_file_ids")
    return file_id


def get_media_from_message(message: "Message") -> Any:
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


def get_media_file_size(m):
    media = get_media_from_message(m)
    return getattr(media, "file_size", "None")


def get_name(media_msg: Message | FileId) -> str:

    if isinstance(media_msg, Message):
        media = get_media_from_message(media_msg)
        file_name = getattr(media, "file_name", "")

    elif isinstance(media_msg, FileId):
        file_name = getattr(media_msg, "file_name", "")

    if not file_name:
        if isinstance(media_msg, Message) and media_msg.media:
            media_type = media_msg.media.value
        elif media_msg.file_type:
            media_type = media_msg.file_type.name.lower()
        else:
            media_type = "file"

        formats = {
            "photo": "jpg", "audio": "mp3", "voice": "ogg",
            "video": "mp4", "animation": "mp4", "video_note": "mp4",
            "sticker": "webp"
        }

        ext = formats.get(media_type)
        ext = "." + ext if ext else ""

        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{media_type}-{date}{ext}"

    return file_name


def get_file_info(message):
    media = get_media_from_message(message)
    return {
            "user_id": message.from_user.id,
            "file_id": getattr(media, "file_id", ""),
            "file_unique_id":getattr(media, "file_unique_id", ""),
            "file_name": get_name(message),
            "file_size":getattr(media, "file_size", 0),
            "mime_type": getattr(media, "mime_type", "None/unknown")
        }


async def update_file_id(msg_id, multi_clients):
    file_ids={}
    for client_id, client in multi_clients.items():
        log_msg=await client.get_messages(Var.BIN_CHANNEL, msg_id)
        media = get_media_from_message(log_msg)
        file_ids[str(client.id)]=getattr(media, "file_id", "")

    return file_ids


async def send_file(client: Client, file_id: str):
    return await client.send_cached_media(Var.BIN_CHANNEL, file_id)
