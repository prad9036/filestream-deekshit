# This file is a part of FileStreamBot
from urllib import request
from os import environ
from dotenv import load_dotenv

load_dotenv()


class Var(object):
    MULTI_CLIENT = False
    API_ID = int(environ.get("API_ID"))
    API_HASH = str(environ.get("API_HASH"))
    BOT_TOKEN = str(environ.get("BOT_TOKEN"))
    SLEEP_THRESHOLD = int(environ.get("SLEEP_THRESHOLD", "60"))
    WORKERS = int(environ.get("WORKERS", "6"))
    BIN_CHANNEL = int(environ.get("BIN_CHANNEL", None))
    PORT = int(environ.get("PORT", 8080))
    BIND_ADDRESS = str(environ.get("WEB_SERVER_BIND_ADDRESS", "0.0.0.0"))
    PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))
    HAS_SSL = str(environ.get("HAS_SSL", "0").lower()) in ("1", "true", "t", "yes", "y")
    NO_PORT = str(environ.get("NO_PORT", "0").lower()) in ("1", "true", "t", "yes", "y")
    FQDN = str(environ.get("FQDN", BIND_ADDRESS))

    # --- cloudflared auto-tunnel support ---
    try:
        _fqdn_trigger = FQDN.strip().lower()
        if _fqdn_trigger in ("{cloudflare_url}", "cloudflare", "cloudflared"):
            import os
            import subprocess
            import time
            import re

            _cwd = os.getcwd()
            _cloudflared_path = os.path.join(_cwd, "cloudflared")
            if not os.path.isfile(_cloudflared_path):
                _dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                try:
                    request.urlretrieve(_dl_url, _cloudflared_path)
                    os.chmod(_cloudflared_path, 0o755)
                except Exception:
                    pass

            _tunnel_url = None
            if os.path.isfile(_cloudflared_path):
                _cmd = [_cloudflared_path, "tunnel", "--url", f"http://localhost:{PORT}"]
                try:
                    _proc = subprocess.Popen(
                        _cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    _deadline = time.time() + 15
                    _url_re = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
                    while time.time() < _deadline:
                        _line = _proc.stdout.readline()
                        if not _line:
                            time.sleep(0.1)
                            continue
                        m = _url_re.search(_line)
                        if m:
                            _tunnel_url = m.group(0)
                            break
                except Exception:
                    _tunnel_url = None

            if _tunnel_url:
                FQDN = _tunnel_url[len("https://") : ].rstrip("/")
                URL = f"https://{FQDN}/"
            else:
                URL = "http{}://{}{}/".format(
                    "s" if HAS_SSL else "", FQDN, "" if NO_PORT else ":" + str(PORT)
                )
        else:
            URL = "http{}://{}{}/".format(
                "s" if HAS_SSL else "", FQDN, "" if NO_PORT else ":" + str(PORT)
            )
    except Exception:
        URL = "http{}://{}{}/".format(
            "s" if HAS_SSL else "", FQDN, "" if NO_PORT else ":" + str(PORT)
        )
    # --- end cloudflared support ---

    DATABASE_URL = str(environ.get('DATABASE_URL'))
    UPDATES_CHANNEL = str(environ.get('UPDATES_CHANNEL', "Telegram"))
    OWNER_ID = [int(x.strip()) for x in environ.get('OWNER_ID', '777000').split(',')]
    SESSION_NAME = str(environ.get('SESSION_NAME', 'F2LxBot'))
    FORCE_UPDATES_CHANNEL = environ.get('FORCE_UPDATES_CHANNEL', False)
    FORCE_UPDATES_CHANNEL = True if str(FORCE_UPDATES_CHANNEL).lower() == "true" else False
    ALLOWED_USERS = [x.strip("@ ") for x in str(environ.get("ALLOWED_USERS", "") or "").split(",") if x.strip("@ ")]

    KEEP_ALIVE = str(environ.get("KEEP_ALIVE", "0").lower()) in  ("1", "true", "t", "yes", "y")
    IMAGE_FILEID = environ.get('IMAGE_FILEID', "https://deekshith.eu.org/static/MyFiles.png")
    TOS = environ.get("TOS", None)
    if TOS:
        response = request.urlopen(TOS)
        data = response.read().decode('utf-8')
        TOS = data.strip()

    MODE = environ.get("MODE", "primary")
    SECONDARY = True if MODE.lower() == "secondary" else False
    LINK_LIMIT = int(environ.get("LINK_LIMIT")) if "LINK_LIMIT" in environ else None
