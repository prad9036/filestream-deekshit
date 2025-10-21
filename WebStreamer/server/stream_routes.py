# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import time
import math
import logging
import mimetypes
import traceback
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from WebStreamer.bot import multi_clients, work_loads, StreamBot
from WebStreamer.vars import Var
from WebStreamer.server.exceptions import FIleNotFound, InvalidHash
from WebStreamer import utils, StartTime, __version__
from WebStreamer.utils.render_template import render_page


routes = web.RouteTableDef()


@routes.get("/status", allow_head=True)
async def root_route_handler(_):
    """
    Return a simple JSON status payload.
    """
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username,
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": __version__,
        }
    )


@routes.get("/watch/{path}", allow_head=True)
async def watch_handler(request: web.Request):
    """
    Serve the watch/watch page (HTML). Properly return an HTTP response or raise
    the appropriate HTTP error so aiohttp does not get a None return.
    """
    try:
        path = request.match_info["path"]
        html = await render_page(path)
        return web.Response(text=html, content_type="text/html")
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.exception("Error while handling /watch: %s", e)
        raise web.HTTPInternalServerError(text=str(e))
    except Exception as e:
        logging.critical(e.with_traceback(None))
        logging.debug(traceback.format_exc())
        raise web.HTTPInternalServerError(text=str(e))


@routes.get("/dl/{path}", allow_head=True)
async def download_handler_short(request: web.Request):
    """
    Backwards-compatible download route that accepts only the file id/path.
    Delegates to media_streamer.
    """
    try:
        db_id = request.match_info.get("path")
        return await media_streamer(request, db_id, url_filename=None)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.exception("Error while handling /dl (short): %s", e)
        raise web.HTTPInternalServerError(text=str(e))
    except Exception as e:
        logging.critical(e.with_traceback(None))
        logging.debug(traceback.format_exc())
        raise web.HTTPInternalServerError(text=str(e))


@routes.get("/dl/{path}/{filename}", allow_head=True)
async def download_handler(request: web.Request):
    """
    Download route that accepts an additional filename segment for friendly URLs.
    The url-provided filename will be used for Content-Disposition if present.
    """
    try:
        db_id = request.match_info.get("path")
        url_filename = request.match_info.get("filename")
        return await media_streamer(request, db_id, url_filename=url_filename)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.exception("Error while handling /dl (with filename): %s", e)
        raise web.HTTPInternalServerError(text=str(e))
    except Exception as e:
        logging.critical(e.with_traceback(None))
        logging.debug(traceback.format_exc())
        raise web.HTTPInternalServerError(text=str(e))


class_cache = {}


async def media_streamer(request: web.Request, db_id: str, url_filename: str | None = None):
    """
    Core streaming logic. If url_filename is provided, use it for Content-Disposition
    (so the download filename in the browser matches the friendly URL). Otherwise
    fall back to the stored file name.
    """
    range_header = request.headers.get("Range", 0)

    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]

    if Var.MULTI_CLIENT:
        logging.info(
            f"Client {index} is now serving {request.headers.get('X-FORWARDED-FOR', request.remote)}"
        )

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect

    logging.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(db_id, multi_clients)
    logging.debug("after calling get_file_properties")

    file_size = file_id.file_size

    if range_header:
        try:
            from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
        except Exception:
            # Malformed Range header; return 416
            return web.Response(
                status=416,
                body="416: Range not satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    mime_type = file_id.mime_type
    # if a URL filename is provided, prefer it for Content-Disposition; otherwise use stored name
    file_name = url_filename or utils.get_name(file_id)
    disposition = "attachment"

    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    # Uncomment to allow inline disposition for media types
    # if "video/" in mime_type or "audio/" in mime_type:
    #     disposition = "inline"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            # Ensure filename is quoted to handle spaces/special chars
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )
