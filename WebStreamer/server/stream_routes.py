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
    # ... existing status handler unchanged ...
    pass

@routes.get("/watch/{path}", allow_head=True)
async def stream_handler(request: web.Request):
    # ... existing watch handler unchanged ...
    pass

# Changed the download route to accept filename as an additional segment.
# The filename in the URL is used for friendly URLs and can be used by the streamer
# to set Content-Disposition; the actual lookup still uses the file id (path).
@routes.get("/dl/{path}/{filename}", allow_head=True)
async def download_handler(request: web.Request):
    db_id = request.match_info.get('path')
    # filename is available if needed:
    url_filename = request.match_info.get('filename')

    # Delegate to existing media streaming logic (media_streamer expects db_id)
    try:
        return await media_streamer(request, db_id)
    except Exception as e:
        logging.exception("Error in download handler: %s", e)
        raise

class_cache = {}

async def media_streamer(request: web.Request, db_id: str):
    # ... existing streaming implementation unchanged ...
    # Optionally: use the url_filename to set Content-Disposition when streaming
    pass