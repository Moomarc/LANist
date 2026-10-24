import base64
import html
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, unquote_to_bytes, urlsplit

from .config import valid_token
from .store import Store, split_rel

CHUNK = 64 * 1024
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

LOGO_SVG = """<svg viewBox="0 0 1024 1024" width="64" height="64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><defs><linearGradient id="lanistTile" x1="0" y1="0" x2="0" y2="1024" gradientUnits="userSpaceOnUse"><stop stop-color="#1B2947"/><stop offset="1" stop-color="#09101E"/></linearGradient><linearGradient id="lanistModule" x1="543" y1="543" x2="747" y2="747" gradientUnits="userSpaceOnUse"><stop stop-color="#568CFF"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs><rect width="1024" height="1024" rx="228" fill="url(#lanistTile)"/><rect x="277" y="277" width="204" height="204" rx="58" fill="#F7F9FC"/><rect x="277" y="543" width="204" height="204" rx="58" fill="#F7F9FC"/><rect x="543" y="543" width="204" height="204" rx="58" fill="url(#lanistModule)"/></svg>"""
FAVICON = "data:image/svg+xml;base64," + base64.b64encode(
    LOGO_SVG.encode("utf-8")
).decode("ascii")

DOWNLOAD_ICON = """<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>"""
FOLDER_ICON = """<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.6l2 2.4h6.4A2.5 2.5 0 0 1 20 9.9v6.6a2.5 2.5 0 0 1-2.5 2.5h-12A2.5 2.5 0 0 1 3 16.5z"/></svg>"""
CHEVRON_ICON = """<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>"""
EMPTY_ICON = """<svg viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h4l2 2.5h7A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/></svg>"""

FONT_FILES = {
    "__FONT_500__": "space-grotesk-500.woff2",
    "__FONT_700__": "space-grotesk-700.woff2",
}

CSP = (
    "default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; "
    "script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; "
    "base-uri 'none'; frame-ancestors 'none'"
)

ERROR_PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>__TITLE__ · LANist</title>
<style>
:root{color-scheme:light dark}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f3f6fb;color:#0f172a;
font-family:"Segoe UI","Microsoft YaHei UI",system-ui,sans-serif}
.box{max-width:420px;padding:34px 30px;border:1px solid #e7ecf4;border-radius:20px;background:#fff;
box-shadow:0 22px 48px -24px rgba(15,23,42,.22);text-align:center}
h1{margin:0 0 8px;font-size:19px}p{margin:0;color:#5c6879;font-size:14px;line-height:1.7}
@media (prefers-color-scheme:dark){
body{background:#0a0f18;color:#e6ecf7}
.box{background:#101827;border-color:#1e2b40;box-shadow:0 22px 48px -24px rgba(0,0,0,.9)}
p{color:#9fb0c7}
}
</style></head><body><div class="box"><h1>__TITLE__</h1><p>__MESSAGE__</p></div></body></html>"""

BADGE_CATS = {
    "pdf": ("PDF", "pdf"),
    "doc": ("DOC", "doc"),
    "docx": ("DOC", "doc"),
    "odt": ("DOC", "doc"),
    "rtf": ("DOC", "doc"),
    "wps": ("DOC", "doc"),
    "xls": ("XLS", "xls"),
    "xlsx": ("XLS", "xls"),
    "csv": ("XLS", "xls"),
    "ods": ("XLS", "xls"),
    "ppt": ("PPT", "ppt"),
    "pptx": ("PPT", "ppt"),
    "odp": ("PPT", "ppt"),
    "png": ("IMG", "img"),
    "jpg": ("IMG", "img"),
    "jpeg": ("IMG", "img"),
    "gif": ("IMG", "img"),
    "webp": ("IMG", "img"),
    "bmp": ("IMG", "img"),
    "svg": ("IMG", "img"),
    "tif": ("IMG", "img"),
    "tiff": ("IMG", "img"),
    "heic": ("IMG", "img"),
    "ico": ("IMG", "img"),
    "zip": ("ZIP", "zip"),
    "rar": ("ZIP", "zip"),
    "7z": ("ZIP", "zip"),
    "tar": ("ZIP", "zip"),
    "gz": ("ZIP", "zip"),
    "tgz": ("ZIP", "zip"),
    "bz2": ("ZIP", "zip"),
    "xz": ("ZIP", "zip"),
    "txt": ("TXT", "txt"),
    "md": ("TXT", "txt"),
    "log": ("TXT", "txt"),
    "ini": ("TXT", "txt"),
    "cfg": ("TXT", "txt"),
    "conf": ("TXT", "txt"),
    "mp3": ("AUD", "aud"),
    "wav": ("AUD", "aud"),
    "flac": ("AUD", "aud"),
    "m4a": ("AUD", "aud"),
    "aac": ("AUD", "aud"),
    "ogg": ("AUD", "aud"),
    "mp4": ("VID", "vid"),
    "mkv": ("VID", "vid"),
    "avi": ("VID", "vid"),
    "mov": ("VID", "vid"),
    "wmv": ("VID", "vid"),
    "webm": ("VID", "vid"),
    "flv": ("VID", "vid"),
    "exe": ("APP", "app"),
    "msi": ("APP", "app"),
    "bat": ("APP", "app"),
    "cmd": ("APP", "app"),
    "lnk": ("APP", "app"),
    "py": ("PY", "code"),
    "js": ("JS", "code"),
    "ts": ("TS", "code"),
    "html": ("WEB", "code"),
    "css": ("CSS", "code"),
    "json": ("JSON", "code"),
    "xml": ("XML", "code"),
    "sh": ("SH", "code"),
    "java": ("JAVA", "code"),
    "cs": ("CS", "code"),
    "go": ("GO", "code"),
    "rs": ("RS", "code"),
    "php": ("PHP", "code"),
    "sql": ("SQL", "code"),
    "yml": ("YML", "code"),
    "yaml": ("YML", "code"),
}

logger = logging.getLogger("lanist")


def file_badge(name):
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    label, cat = BADGE_CATS.get(ext, (None, None))
    if label is None:
        clean = re.sub(r"[^A-Za-z0-9]", "", ext)[:4].upper()
        label = clean or "FILE"
        cat = "file"
    return label, cat


def human_size(n):
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return "{} B".format(int(size)) if unit == "B" else "{:.1f} {}".format(size, unit)
        size /= 1024


def _usable_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if ip.version != 4:
        return False
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
    )


def lan_ipv4s():
    """All usable IPv4 addresses, default-route interface first."""
    found = []

    def add(value):
        if value and _usable_ip(value) and value not in found:
            found.append(value)

    # UDP connect only asks the OS for the default-route interface; no packet is sent.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        add(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()

    try:
        for info in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM
        ):
            add(info[4][0])
    except OSError:
        pass
    return found


def urls_for(port, token, ips=None):
    ips = ips if ips is not None else lan_ipv4s()
    return ["http://{}:{}/{}/".format(ip, port, token) for ip in ips]


def _font_uri(filename):
    path = os.path.join(WEB_DIR, "fonts", filename)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise RuntimeError("读不到字体文件 {}：{}".format(path, e)) from e
    return "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")


def load_template():
    path = os.path.join(WEB_DIR, "index.html")
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise RuntimeError("读不到网页模板 {}：{}".format(path, e)) from e
    raw = raw.replace("__FAVICON__", FAVICON).replace("__LOGO__", LOGO_SVG)
    for placeholder, filename in FONT_FILES.items():
        raw = raw.replace(placeholder, _font_uri(filename))
    return raw


def error_page(title, message):
    return (
        ERROR_PAGE.replace("__TITLE__", html.escape(title))
        .replace("__MESSAGE__", html.escape(message))
    )


class MultipartError(Exception):
    pass


def discard(_):
    pass


class MultipartStream:
    # Python 3.13 removed cgi, so multipart bodies are parsed by hand.
    def __init__(self, rfile, boundary, length):
        self.rfile = rfile
        self.delim = b"--" + boundary
        self.remaining = length
        self.buf = bytearray()
        self.started = False

    def _fill(self):
        if self.remaining <= 0:
            return False
        chunk = self.rfile.read(min(CHUNK, self.remaining))
        if not chunk:
            self.remaining = 0
            return False
        self.remaining -= len(chunk)
        self.buf.extend(chunk)
        return True

    def _ensure(self, n):
        while len(self.buf) < n:
            if not self._fill():
                raise MultipartError("上传数据提前结束")

    def _read_until(self, marker, sink=None, limit=None):
        # Keep len(marker)-1 bytes so a marker split across chunks is still found.
        keep = len(marker) - 1
        collected = None if sink is not None else bytearray()
        while True:
            idx = self.buf.find(marker)
            if idx != -1:
                data = bytes(self.buf[:idx])
                del self.buf[: idx + len(marker)]
                if sink is None:
                    collected.extend(data)
                    return bytes(collected)
                sink(data)
                return None
            if len(self.buf) > keep:
                cut = len(self.buf) - keep
                data = bytes(self.buf[:cut])
                del self.buf[:cut]
                if sink is None:
                    collected.extend(data)
                    if limit is not None and len(collected) > limit:
                        raise MultipartError("分段头过长")
                else:
                    sink(data)
            if not self._fill():
                raise MultipartError("上传数据提前结束")

    def next_part(self):
        if not self.started:
            self._read_until(self.delim, sink=discard)
            self.started = True
        self._ensure(2)
        if self.buf[:2] == b"--":
            del self.buf[:2]
            return None
        if self.buf[:2] != b"\r\n":
            raise MultipartError("分段边界格式不正确")
        del self.buf[:2]
        return self._read_until(b"\r\n\r\n", limit=65536)

    def read_body(self, sink):
        self._read_until(b"\r\n" + self.delim, sink=sink)

    def drain(self):
        while self.remaining > 0:
            if not self._fill():
                break
            self.buf.clear()


def decode_name(raw):
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def part_filename(headers):
    if b"filename*" in headers.lower():
        m = re.search(rb"filename\*\s*=\s*UTF-8''([^;\r\n]+)", headers, re.I)
        if m:
            raw = unquote_to_bytes(m.group(1))
            if raw:
                return decode_name(raw)
    m = re.search(rb'filename\s*=\s*"([^"]*)"', headers, re.I)
    if m and m.group(1):
        return decode_name(m.group(1))
    return None


class Throttle:
    """Limit wrong-token attempts per client address."""

    def __init__(self, limit=10, window=60.0, block=60.0, max_entries=4096):
        self.limit = limit
        self.window = window
        self.block = block
        self.max_entries = max_entries
        self._fails = {}
        self._blocked = {}
        self._lock = threading.Lock()

    def _prune(self, now):
        if len(self._fails) <= self.max_entries:
            return
        for ip in list(self._fails):
            if not self._fails[ip] or now - self._fails[ip][-1] > self.window:
                self._fails.pop(ip, None)
                self._blocked.pop(ip, None)

    def retry_after(self, ip):
        now = time.monotonic()
        with self._lock:
            until = self._blocked.get(ip, 0)
            if until > now:
                return max(1, int(until - now + 0.999))
            if until:
                self._blocked.pop(ip, None)
                self._fails.pop(ip, None)
            return 0

    def fail(self, ip):
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            fails = self._fails.setdefault(ip, [])
            fails.append(now)
            cutoff = now - self.window
            while fails and fails[0] < cutoff:
                fails.pop(0)
            if len(fails) >= self.limit:
                self._blocked[ip] = now + self.block
                return int(self.block)
            return 0

    def clear(self, ip):
        with self._lock:
            self._fails.pop(ip, None)
            self._blocked.pop(ip, None)


class State:
    def __init__(self, store, token, template):
        self.store = store
        self.token = token
        self.template = template
        self.throttle = Throttle()

    def page(self, content, summary=""):
        return self.template.replace("__COUNT__", summary).replace(
            "<!--CONTENT-->", content
        )


class LANistServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, address, handler, state):
        self.state = state
        super().__init__(address, handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "LANist"
    protocol_version = "HTTP/1.0"

    def version_string(self):
        return self.server_version

    def log_message(self, fmt, *args):
        pass

    @property
    def state(self):
        return self.server.state

    def _headers(self, code, ctype, length):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Frame-Options", "DENY")

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self._headers(code, ctype, len(data))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code, title, message, retry_after=None):
        if self.wants_json():
            self._send_json({"ok": False, "error": message}, code)
            return
        body = error_page(title, message)
        data = body.encode("utf-8")
        self._headers(code, "text/html; charset=utf-8", len(data))
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.end_headers()
        self.wfile.write(data)

    def _safe_error(self, code, title, message):
        try:
            self._error(code, title, message)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            logger.exception("failed to send error response")

    def _redirect(self, location):
        self.send_response(301)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def wants_json(self):
        value = self.headers.get("X-Requested-With", "")
        return value.strip().lower() == "xmlhttprequest"

    def _client_ip(self):
        return self.client_address[0] if self.client_address else "?"

    def _authorized(self, value):
        try:
            ok = secrets.compare_digest(
                value.encode("utf-8"), self.state.token.encode("utf-8")
            )
        except Exception:
            ok = False
        return ok

    def _drain_body(self, limit=1024 * 1024):
        # Closing with unread request bytes makes Windows send RST instead of
        # the error page, so eat small bodies before answering a rejected POST.
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        remaining = min(max(length, 0), limit)
        while remaining > 0:
            chunk = self.rfile.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    def _check_token(self, value):
        ip = self._client_ip()
        wait = self.state.throttle.retry_after(ip)
        if wait:
            self._drain_body()
            self._error(
                429,
                "稍后再试",
                "尝试次数过多，请 {} 秒后再打开链接。".format(wait),
                retry_after=wait,
            )
            return False
        if self._authorized(value):
            self.state.throttle.clear(ip)
            return True
        self._drain_body()
        block = self.state.throttle.fail(ip)
        if block:
            self._error(
                429,
                "稍后再试",
                "尝试次数过多，请 {} 秒后再打开链接。".format(block),
                retry_after=block,
            )
        else:
            self._not_found()
        return False

    def _not_found(self):
        self._error(
            404,
            "找不到这个地址",
            "链接不完整，或者共享已经停止。请向主机重新要一次访问链接。",
        )

    def do_GET(self):
        try:
            self._get()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            logger.exception("GET failed")
            self._safe_error(500, "服务器错误", "服务端处理这个请求时出错了。")

    def do_POST(self):
        try:
            self._post()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except MultipartError as e:
            self._safe_error(400, "上传没有完成", "上传数据不完整：{}".format(e))
        except Exception:
            logger.exception("POST failed")
            self._safe_error(500, "服务器错误", "服务端处理这个上传时出错了。")

    def _get(self):
        split = urlsplit(self.path)
        parts = split.path.split("/")
        if len(parts) < 2 or not parts[1]:
            self._not_found()
            return
        if not self._check_token(parts[1]):
            return
        if len(parts) == 2:
            self._redirect("/{}/".format(parts[1]))
            return
        if len(parts) == 3 and parts[2] == "":
            rel = parse_qs(split.query).get("p", [""])[0]
            self._listing(rel)
            return
        if len(parts) >= 4 and parts[2] == "d":
            self._download(parts[3:])
            return
        self._not_found()

    def _crumbs(self, parts):
        if not parts:
            return '<nav class="crumbs" aria-label="当前位置"><span class="crumb-here">共享目录</span></nav>'
        items = ['<a href="?p=">共享目录</a>']
        for index, name in enumerate(parts):
            if index == len(parts) - 1:
                items.append(
                    '<span class="crumb-here">{}</span>'.format(html.escape(name))
                )
            else:
                sub = "/".join(parts[: index + 1])
                items.append(
                    '<a href="?p={}">{}</a>'.format(
                        html.escape(quote(sub, safe=""), quote=True),
                        html.escape(name),
                    )
                )
        return (
            '<nav class="crumbs" aria-label="当前位置">'
            + '<span class="crumb-sep">/</span>'.join(items)
            + "</nav>"
        )

    def _listing(self, rel):
        parts = split_rel(rel)
        if parts is None or self.state.store.resolve_dir(rel) is None:
            self._not_found()
            return
        entries = self.state.store.list(rel)
        files = [e for e in entries if not e.is_dir]
        folders = [e for e in entries if e.is_dir]
        rows = []
        for index, entry in enumerate(entries):
            depth = min(index, 10)
            if entry.is_dir:
                child = "/".join(parts + [entry.name])
                href = "?p={}".format(quote(child, safe=""))
                href_attr = html.escape(href, quote=True)
                name_attr = html.escape(entry.name, quote=True)
                rows.append(
                    '<tr class="row-folder" style="--i:{}">'
                    '<td class="cell-name"><div class="name">'
                    '<span class="badge cat-folder">{}</span>'
                    '<a class="folder-link" href="{}">{}/</a></div></td>'
                    '<td class="size">&mdash;</td>'
                    '<td class="time">&mdash;</td>'
                    '<td class="act"><a class="icon-btn" href="{}" '
                    'title="进入 {}" aria-label="进入 {}">{}</a></td>'
                    "</tr>".format(
                        depth,
                        FOLDER_ICON,
                        href_attr,
                        html.escape(entry.name),
                        href_attr,
                        name_attr,
                        name_attr,
                        CHEVRON_ICON,
                    )
                )
                continue
            href = "d/{}".format(
                "/".join(quote(part, safe="") for part in parts + [entry.name])
            )
            href_attr = html.escape(href, quote=True)
            name_attr = html.escape(entry.name, quote=True)
            badge, cat = file_badge(entry.name)
            rows.append(
                '<tr style="--i:{}">'
                '<td class="cell-name"><div class="name">'
                '<span class="badge cat-{}">{}</span>'
                '<a href="{}">{}</a></div></td>'
                '<td class="size">{}</td>'
                '<td class="time">{}</td>'
                '<td class="act"><a class="icon-btn" href="{}" download '
                'title="下载 {}" aria-label="下载 {}">{}</a></td>'
                "</tr>".format(
                    depth,
                    cat,
                    html.escape(badge),
                    href_attr,
                    html.escape(entry.name),
                    human_size(entry.size),
                    datetime.fromtimestamp(entry.mtime).strftime("%Y-%m-%d %H:%M"),
                    href_attr,
                    name_attr,
                    name_attr,
                    DOWNLOAD_ICON,
                )
            )

        if files and folders:
            summary = "{} 个文件夹 · {} 个文件".format(len(folders), len(files))
        elif folders:
            summary = "{} 个文件夹".format(len(folders))
        elif files:
            summary = "{} 个文件".format(len(files))
        else:
            summary = "空"

        if rows:
            table = (
                "<table><thead><tr>"
                '<th>文件</th><th class="size">大小</th><th class="time">修改时间</th>'
                '<th class="act"><span class="sr-only">操作</span></th>'
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            )
        else:
            table = (
                '<div class="empty"><div class="empty-ico">'
                + EMPTY_ICON
                + "</div><p>{}</p>"
                '<p class="muted">{}</p></div>'.format(
                    "这个文件夹是空的" if parts else "共享目录还是空的",
                    "文件由主机放进来；你的上传会出现在共享目录根目录"
                    if parts
                    else "把文件拖到上面，或点一下选择文件",
                )
            )

        content = self._crumbs(parts) + table
        if parse_qs(urlsplit(self.path).query).get("fragment") == ["1"]:
            self._send_json(
                {"count": len(files), "summary": summary, "html": content}
            )
            return
        self._send(200, self.state.page(content, summary))

    def _download(self, raw_parts):
        name = "/".join(
            unquote(part, encoding="utf-8", errors="replace") for part in raw_parts
        )
        target = self.state.store.resolve(name)
        if target is None:
            self._not_found()
            return
        try:
            f = open(target, "rb")
        except OSError:
            self._not_found()
            return

        with f:
            size = os.fstat(f.fileno()).st_size
            base = name.rsplit("/", 1)[-1]
            ascii_name = re.sub(r"[^\x20-\x7e]", "_", base)
            ascii_name = ascii_name.replace('"', "_").replace("\\", "_").replace(";", "_")
            if not ascii_name.strip():
                ascii_name = "download"
            disposition = (
                'attachment; filename="{}"; filename*=UTF-8\'\'{}'.format(
                    ascii_name, quote(base, safe="")
                )
            )
            self._headers(200, "application/octet-stream", size)
            self.send_header("Content-Disposition", disposition)
            self.end_headers()
            try:
                while True:
                    chunk = f.read(CHUNK)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

    def _post(self):
        path = urlsplit(self.path).path
        parts = path.split("/")
        if len(parts) != 3 or not parts[1] or parts[2] != "u":
            self._not_found()
            return
        if not self._check_token(parts[1]):
            return

        boundary = self._boundary()
        if boundary is None:
            self._error(
                400, "上传请求不对", "这个请求不是 multipart/form-data，缺少 boundary。"
            )
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._error(411, "上传请求不完整", "请求里缺少 Content-Length。")
            return
        if length <= 0:
            self._error(400, "没有收到文件", "上传内容是空的。")
            return

        parser = MultipartStream(self.rfile, boundary, length)
        uploaded = []
        part = parser.next_part()
        while part is not None:
            filename = part_filename(part)
            if filename is None:
                parser.read_body(discard)
            else:
                self._store_part(parser, filename, uploaded)
            part = parser.next_part()
        parser.drain()

        if not uploaded:
            self._error(400, "没有收到文件", "请选择一个文件再上传。")
            return
        if self.wants_json():
            self._send_json({"ok": True, "files": uploaded})
            return
        self._redirect("./")

    def _store_part(self, parser, filename, uploaded):
        tmp = self.state.store.new_temp()
        try:
            with open(tmp, "wb") as f:
                parser.read_body(f.write)
            uploaded.append(self.state.store.commit(tmp, filename))
        except Exception:
            self.state.store.discard(tmp)
            raise

    def _boundary(self):
        ctype = self.headers.get("Content-Type", "")
        if not ctype.lower().startswith("multipart/form-data"):
            return None
        m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', ctype, re.I)
        if not m:
            return None
        value = (m.group(1) or m.group(2) or "").strip()
        if not value:
            return None
        return value.encode("latin-1", "replace")


def create_server(share, token, host="0.0.0.0", port=0):
    if not valid_token(token):
        raise ValueError("访问口令格式不对。")
    store = Store(share)
    store.ensure()
    state = State(store, token, load_template())

    candidates = [port] if port else list(range(8000, 8011)) + [0]
    errors = []
    for candidate in candidates:
        try:
            server = LANistServer((host, candidate), Handler, state)
        except OSError as e:
            if port:
                raise RuntimeError(
                    "端口 {} 用不了：{}".format(port, e)
                ) from e
            errors.append(str(e))
            continue
        return server, server.server_address[1]

    raise RuntimeError("没有可用端口：{}".format("; ".join(errors[-3:])))
