import ctypes
import math
import os
import shutil
import sys
import threading
from ctypes import wintypes
from datetime import datetime


def _enable_dpi_awareness():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


# Must run before Tk creates any window, otherwise Windows bitmap-stretches it.
_enable_dpi_awareness()

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from . import server as srv

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.isdir(_VENDOR):
    sys.path.insert(0, _VENDOR)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:
    DND_FILES = None
    TkinterDnD = None

try:
    from qrcodegen import QrCode
except Exception:
    QrCode = None

REFRESH_MS = 2000
CF_HDROP = 15
FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400

_user32 = ctypes.windll.user32
_shell32 = ctypes.windll.shell32

_user32.OpenClipboard.argtypes = [wintypes.HWND]
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
_user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = [wintypes.UINT]
_user32.GetClipboardData.restype = wintypes.HANDLE
_shell32.DragQueryFileW.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.LPWSTR,
    wintypes.UINT,
]
_shell32.DragQueryFileW.restype = wintypes.UINT


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


_shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
_shell32.SHFileOperationW.restype = ctypes.c_int

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PNG = os.path.join(APP_DIR, "assets", "icon.png")

BG = "#eef2f8"
CARD = "#ffffff"
LINE = "#e4eaf3"
TEXT = "#0f172a"
MUTED = "#5b6779"
SOFT = "#8d99ab"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_PRESS = "#1e40af"
GHOST_HOVER = "#f2f6fc"
OK = "#16a34a"
ERR = "#dc2626"
DARK = "#101b30"
DARK_FIELD = "#18253d"
DARK_LINE = "#253552"
DARK_TEXT = "#eef3ff"
DARK_MUTED = "#93a6c6"

SCALE = 1.0


def px(value):
    return max(1, int(round(value * SCALE)))


def _hex_rgb(value):
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def rounded_image(
    w, h, radius, fill, border=None, bg=None, border_width=1, master=None
):
    """Opaque rounded rectangle with 4x4 supersampled corners.

    Tk's smooth polygons are not antialiased, so crisp corners have to be
    rendered pixel by pixel. The image is composited on `bg`.
    """
    w, h = max(1, int(w)), max(1, int(h))
    r = max(0, min(int(radius), w // 2, h // 2))
    bw = min(max(1, int(border_width)), r) if border else 0
    if bg is None:
        bg = fill
    img = tk.PhotoImage(master=master, width=w, height=h)
    img.put(bg, to=(0, 0, w, h))
    if h - r > r:
        img.put(fill, to=(bw, r, w - bw, h - r))
    if w - r > r:
        img.put(fill, to=(r, bw, w - r, h - bw))
    if border:
        if w - r > r:
            img.put(border, to=(r, 0, w - r, bw))
            img.put(border, to=(r, h - bw, w - r, h))
        if h - r > r:
            img.put(border, to=(0, r, bw, h - r))
            img.put(border, to=(w - bw, r, w, h - r))
    if not r:
        return img
    fill_rgb = _hex_rgb(fill)
    bg_rgb = _hex_rgb(bg)
    bd_rgb = _hex_rgb(border) if border else fill_rgb
    inner2 = (r - bw) ** 2
    outer2 = r * r
    samples = (0.125, 0.375, 0.625, 0.875)
    for qx in (0, 1):
        x0 = 0 if qx == 0 else w - r
        for qy in (0, 1):
            y0 = 0 if qy == 0 else h - r
            rows = []
            for py in range(r):
                row = []
                for pxx in range(r):
                    acc_r = acc_g = acc_b = 0.0
                    for sy in samples:
                        gy = y0 + py + sy
                        dy = (r - gy) if qy == 0 else (gy - (h - r))
                        dy2 = dy * dy
                        for sx in samples:
                            gx = x0 + pxx + sx
                            dx = (r - gx) if qx == 0 else (gx - (w - r))
                            d2 = dx * dx + dy2
                            if d2 <= inner2:
                                cr, cg, cb = fill_rgb
                            elif d2 <= outer2:
                                cr, cg, cb = bd_rgb
                            else:
                                cr, cg, cb = bg_rgb
                            acc_r += cr
                            acc_g += cg
                            acc_b += cb
                    row.append(_rgb_hex(acc_r / 16, acc_g / 16, acc_b / 16))
                rows.append(row)
            img.put(rows, to=(x0, y0, x0 + r, y0 + r))
    return img


def ellipsize(font, text, max_width):
    if font.measure(text) <= max_width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid] + "…") <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + "…"


def qr_photo(url, target_px=220, master=None):
    if QrCode is None:
        raise RuntimeError("二维码组件没有加载。")
    qr = QrCode.encode_text(url, QrCode.Ecc.MEDIUM)
    n = qr.get_size()
    quiet = 4
    total = n + quiet * 2
    rows = []
    for y in range(total):
        if quiet <= y < quiet + n:
            cells = [
                "#000000" if qr.get_module(x - quiet, y - quiet) else "#ffffff"
                for x in range(total)
            ]
        else:
            cells = ["#ffffff"] * total
        rows.append("{" + " ".join(cells) + "}")
    img = tk.PhotoImage(master=master, width=total, height=total)
    img.put(" ".join(rows))
    scale = max(2, px(target_px) // total)
    return img.zoom(scale) if scale > 1 else img


def pick_display_font(root):
    families = set(tkfont.families(root))
    for name in (
        "Segoe UI Variable Display Semib",
        "Segoe UI Semibold",
        "Segoe UI",
    ):
        if name in families:
            return name
    return "Segoe UI"


class RoundedCard(tk.Canvas):
    def __init__(
        self,
        parent,
        height,
        fill=CARD,
        border=LINE,
        radius=18,
        bg=BG,
        inset=12,
        width=None,
    ):
        opts = {
            "bg": bg,
            "highlightthickness": 0,
            "bd": 0,
            "height": px(height),
        }
        if width is not None:
            opts["width"] = px(width)
        super().__init__(parent, **opts)
        self._fill = fill
        self._border = border
        self._border_width = 1
        self._bg = bg
        self._radius = px(radius)
        self._inset = px(inset)
        self._img = None
        self._size = None
        self.body = tk.Frame(self, bg=fill)
        self._card_win = self.create_window(
            self._inset, self._inset, anchor="nw", window=self.body
        )
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if (w, h) == self._size or w < 4 or h < 4:
            return
        self._size = (w, h)
        self._img = rounded_image(
            w,
            h,
            self._radius,
            self._fill,
            self._border,
            self._bg,
            self._border_width,
            master=self,
        )
        self.delete("cardbg")
        self.create_image(0, 0, anchor="nw", image=self._img, tags="cardbg")
        self.tag_lower("cardbg")
        self.itemconfigure(
            self._card_win,
            width=max(1, w - 2 * self._inset),
            height=max(1, h - 2 * self._inset),
        )

    def set_border(self, color, width=1):
        width = max(1, int(width))
        if self._border == color and self._border_width == width:
            return
        self._border = color
        self._border_width = width
        self._size = None
        self._redraw()


BUTTON_KINDS = {
    "primary": {
        "fill": ACCENT,
        "fg": "#ffffff",
        "hover": ACCENT_HOVER,
        "press": ACCENT_PRESS,
        "border": None,
        "disabled_fill": "#c7d2fe",
        "disabled_fg": "#f4f7ff",
    },
    "secondary": {
        "fill": CARD,
        "fg": "#36445a",
        "hover": "#f7faff",
        "press": "#eef4fb",
        "border": LINE,
        "disabled_fill": "#f6f8fc",
        "disabled_fg": "#b8c2d0",
    },
    "ghost": {
        "fill": None,
        "fg": "#51607a",
        "hover": "#f1f5fb",
        "press": "#e8eef8",
        "border": None,
        "disabled_fill": None,
        "disabled_fg": "#b8c2d0",
    },
    "danger": {
        "fill": None,
        "fg": ERR,
        "hover": "#fef2f2",
        "press": "#fee2e2",
        "border": None,
        "disabled_fill": None,
        "disabled_fg": "#e4b4b4",
    },
    "on_dark": {
        "fill": "#f7fafe",
        "fg": "#101b30",
        "hover": "#e8effb",
        "press": "#dbe6f8",
        "border": None,
        "disabled_fill": "#2a3852",
        "disabled_fg": "#7f90ac",
    },
    "on_dark_ghost": {
        "fill": None,
        "fg": "#c2d1e8",
        "hover": "#1a2740",
        "press": "#22314c",
        "border": DARK_LINE,
        "disabled_fill": None,
        "disabled_fg": "#6d7e9a",
    },
}


class RoundButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text,
        command=None,
        kind="secondary",
        icon=None,
        bg=CARD,
        height=34,
        padx=14,
        min_width=0,
        fixed_width=None,
        font_size=10,
        radius=9,
    ):
        self._parent_bg = bg
        self._kind = kind
        self._command = command
        self._text = text or ""
        self._icon = icon
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._focused = False
        self._font = tkfont.Font(family="Microsoft YaHei UI", size=font_size)
        self._icon_font = tkfont.Font(family="Segoe MDL2 Assets", size=12)
        self._h = px(height)
        self._pad = px(padx)
        self._gap = px(6)
        self._radius = px(radius)
        self._min_w = px(min_width)
        self._fixed_w = px(fixed_width) if fixed_width else None
        self._cache = {}
        self._width = self._measure_width()
        super().__init__(
            parent,
            width=self._width,
            height=self._h,
            bg=bg,
            highlightthickness=0,
            bd=0,
            takefocus=1,
            cursor="hand2",
        )
        self._img = None
        self._bg_item = self.create_image(0, 0, anchor="nw")
        self._icon_item = None
        if self._icon:
            self._icon_item = self.create_text(
                0, 0, text=self._icon, font=self._icon_font, anchor="w"
            )
        self._text_item = self.create_text(
            0, 0, text=self._text, font=self._font, anchor="w"
        )
        self._place_items()
        self._render()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._on_key)
        self.bind("<space>", self._on_key)

    def _measure_width(self):
        text_w = self._font.measure(self._text) if self._text else 0
        icon_w = self._icon_font.measure(self._icon) if self._icon else 0
        inner = text_w + icon_w
        if text_w and icon_w:
            inner += self._gap
        w = max(self._min_w, self._pad * 2 + inner)
        return self._fixed_w or w

    def _place_items(self):
        text_w = self._font.measure(self._text) if self._text else 0
        icon_w = self._icon_font.measure(self._icon) if self._icon else 0
        inner = text_w + icon_w + (self._gap if text_w and icon_w else 0)
        x = (self._width - inner) / 2
        y = self._h / 2
        if self._icon_item is not None:
            self.coords(self._icon_item, x, y)
            x += icon_w + self._gap
        self.coords(self._text_item, x, y)

    def _render(self):
        style = BUTTON_KINDS[self._kind]
        if not self._enabled:
            fill = style["disabled_fill"] or self._parent_bg
            fg = style["disabled_fg"]
            border, bw = style["border"], 1
        else:
            if self._pressed:
                fill = style["press"]
            elif self._hover:
                fill = style["hover"]
            else:
                fill = style["fill"] or self._parent_bg
            fg = style["fg"]
            border, bw = style["border"], 1
        if self._focused and self._enabled:
            border = "#93c5fd" if self._kind == "primary" else ACCENT
            bw = px(2)
        key = (fill, border, bw)
        img = self._cache.get(key)
        if img is None:
            img = rounded_image(
                self._width,
                self._h,
                self._radius,
                fill,
                border,
                self._parent_bg,
                bw,
                master=self,
            )
            self._cache[key] = img
        self._img = img
        self.itemconfigure(self._bg_item, image=img)
        self.itemconfigure(self._text_item, fill=fg)
        if self._icon_item is not None:
            self.itemconfigure(self._icon_item, fill=fg)

    def _on_enter(self, _event):
        if not self._enabled:
            return
        self._hover = True
        self._render()

    def _on_leave(self, _event):
        self._hover = False
        self._pressed = False
        self._render()

    def _on_press(self, _event):
        if not self._enabled:
            return
        self.focus_set()
        self._pressed = True
        self._render()

    def _on_release(self, event):
        if not self._enabled:
            return
        fire = self._pressed
        self._pressed = False
        self._hover = 0 <= event.x < self._width and 0 <= event.y < self._h
        self._render()
        if fire and self._hover and self._command:
            self._command()

    def _on_focus_in(self, _event):
        self._focused = True
        self._render()

    def _on_focus_out(self, _event):
        self._focused = False
        self._render()

    def _on_key(self, _event):
        if self._enabled and self._command:
            self._command()
        return "break"

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self._hover = False
        self._pressed = False
        self.configure(
            cursor="hand2" if self._enabled else "arrow",
            takefocus=1 if self._enabled else 0,
        )
        self._render()

    def set_button(self, text=None, kind=None, icon=None):
        if text is not None:
            self._text = text
            self.itemconfigure(self._text_item, text=text)
        if kind is not None:
            self._kind = kind
        if icon is not None:
            self._icon = icon
            if self._icon_item is None:
                self._icon_item = self.create_text(
                    0, 0, text=icon, font=self._icon_font, anchor="w"
                )
            else:
                self.itemconfigure(self._icon_item, text=icon)
        new_w = self._measure_width()
        if new_w != self._width:
            self._width = new_w
            self.configure(width=new_w)
        self._cache.clear()
        self._place_items()
        self._render()


class StatusPill(tk.Canvas):
    PALETTE = {
        "idle": ("#f3f6fb", "#e2e8f2", "#9aa8bc", "#5b6779"),
        "run": ("#edfdf4", "#c8f1dc", "#22c55e", "#047857"),
        "busy": ("#eff6ff", "#d2e2fd", "#2563eb", "#1d4ed8"),
        "error": ("#fef2f2", "#fecaca", "#ef4444", "#b91c1c"),
    }

    def __init__(self, parent, bg=BG):
        self._bg = bg
        self._font = tkfont.Font(
            family="Microsoft YaHei UI", size=9, weight="bold"
        )
        self._h = px(26)
        self._pad = px(10)
        self._dot = px(7)
        self._gap = px(6)
        self._kind = "idle"
        self._text = "未启动"
        self._width = 0
        self._img = None
        super().__init__(
            parent, height=self._h, bg=bg, highlightthickness=0, bd=0
        )
        self._bg_item = self.create_image(0, 0, anchor="nw")
        self._dot_item = self.create_oval(0, 0, 0, 0, outline="")
        self._text_item = self.create_text(
            0, 0, text=self._text, font=self._font, anchor="w"
        )
        self._layout()

    def _layout(self):
        fill, border, dot, fg = self.PALETTE[self._kind]
        text_w = self._font.measure(self._text)
        w = self._pad * 2 + self._dot + self._gap + text_w
        if w != self._width:
            self._width = w
            self.configure(width=w)
        self._img = rounded_image(
            w, self._h, self._h // 2, fill, border, self._bg, 1, master=self
        )
        self.itemconfigure(self._bg_item, image=self._img)
        y = (self._h - self._dot) / 2
        self.coords(self._dot_item, self._pad, y, self._pad + self._dot, y + self._dot)
        self.itemconfigure(self._dot_item, fill=dot)
        self.coords(
            self._text_item, self._pad + self._dot + self._gap, self._h / 2
        )
        self.itemconfigure(self._text_item, text=self._text, fill=fg)

    def set(self, kind, text):
        if kind not in self.PALETTE:
            kind = "idle"
        self._kind = kind
        self._text = text
        self._layout()


class TokenChip(tk.Canvas):
    def __init__(self, parent, text, bg=DARK):
        self._font = tkfont.Font(family="Consolas", size=10)
        shown = ellipsize(self._font, text, px(118))
        w = self._font.measure(shown) + px(18)
        h = px(24)
        super().__init__(
            parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0
        )
        self._img = rounded_image(
            w, h, px(7), "#1b2946", None, bg, 1, master=self
        )
        self.create_image(0, 0, anchor="nw", image=self._img)
        self.create_text(
            w / 2, h / 2, text=shown, font=self._font, fill="#dbe6f7"
        )


class UrlBox(tk.Canvas):
    def __init__(self, parent, width, command, bg=DARK):
        self._bg = bg
        self._command = command
        self._width = px(width)
        self._h = px(40)
        self._url = ""
        self._hover = False
        self._pad = px(12)
        self._gap = px(8)
        self._font = tkfont.Font(family="Consolas", size=9)
        self._icon_font = tkfont.Font(family="Segoe MDL2 Assets", size=10)
        self._img = None
        super().__init__(
            parent,
            width=self._width,
            height=self._h,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self._bg_item = self.create_image(0, 0, anchor="nw")
        self._text_item = self.create_text(
            self._pad, self._h / 2, anchor="w", font=self._font
        )
        self._icon_item = self.create_text(
            self._width - self._pad,
            self._h / 2,
            anchor="e",
            text="\ue8c8",
            font=self._icon_font,
            fill="#8aa1c6",
        )
        self._render()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _render(self):
        fill = "#1d2c49" if (self._hover and self._url) else DARK_FIELD
        self._img = rounded_image(
            self._width,
            self._h,
            px(10),
            fill,
            "#2b3b59",
            self._bg,
            1,
            master=self,
        )
        self.itemconfigure(self._bg_item, image=self._img)

    def _on_enter(self, _event):
        self._hover = True
        self._render()
        if self._url:
            self.configure(cursor="hand2")

    def _on_leave(self, _event):
        self._hover = False
        self._render()
        self.configure(cursor="hand2" if self._url else "arrow")

    def _on_click(self, _event):
        if self._url and self._command:
            self._command()

    def set_url(self, url):
        self._url = url
        shown = url
        if shown.startswith("http://"):
            shown = shown[len("http://"):]
        if shown.endswith("/"):
            shown = shown[:-1]
        text = shown or "启动后显示"
        avail = (
            self._width
            - self._pad * 2
            - self._icon_font.measure("\ue8c8")
            - self._gap
        )
        self.itemconfigure(
            self._text_item,
            text=ellipsize(self._font, text, avail),
            fill="#e9efff" if url else "#7d90b0",
        )
        self.configure(cursor="hand2" if url else "arrow")
        self._render()


class GlyphBadge(tk.Canvas):
    def __init__(self, parent, glyph, bg=CARD, fill="#eef4ff", fg=ACCENT, size=26):
        s = px(size)
        self._img = rounded_image(
            s, s, px(7), fill, None, bg, 1, master=parent
        )
        super().__init__(
            parent,
            width=s,
            height=s,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self.create_image(0, 0, anchor="nw", image=self._img)
        self.create_text(
            s / 2,
            s / 2,
            text=glyph,
            font=("Segoe MDL2 Assets", 10),
            fill=fg,
        )


def clipboard_files():
    if not _user32.OpenClipboard(None):
        raise RuntimeError("剪贴板正被其他程序占用，稍后再试。")
    try:
        if not _user32.IsClipboardFormatAvailable(CF_HDROP):
            return []
        handle = _user32.GetClipboardData(CF_HDROP)
        if not handle:
            return []
        count = _shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        buf = ctypes.create_unicode_buffer(32768)
        paths = []
        for i in range(count):
            length = _shell32.DragQueryFileW(handle, i, buf, len(buf))
            if length:
                paths.append(buf.value)
        return paths
    finally:
        _user32.CloseClipboard()


def recycle_paths(paths):
    items = "\0".join(os.path.abspath(p) for p in paths) + "\0\0"
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = items
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    result = _shell32.SHFileOperationW(ctypes.byref(op))
    if result != 0:
        raise OSError(f"移到回收站失败，系统返回 {result}。")
    if op.fAnyOperationsAborted:
        raise OSError("删除被取消。")
    left = [os.path.basename(p) for p in paths if os.path.exists(p)]
    if left:
        raise OSError("这些文件没有删掉，可能正被占用：" + "、".join(left[:5]))


def unique_in_dir(folder, name):
    target = os.path.join(folder, name)
    if not os.path.exists(target):
        return target
    stem, ext = os.path.splitext(name)
    i = 1
    while True:
        target = os.path.join(folder, f"{stem} ({i}){ext}")
        if not os.path.exists(target):
            return target
        i += 1


def copy_into_share(store, paths, rel=""):
    added, skipped, errors = [], [], []
    try:
        store.ensure()
    except RuntimeError as e:
        return [], [], [str(e)]

    target_dir = store.resolve_dir(rel) or store.root
    target_real = os.path.normcase(os.path.realpath(target_dir))
    for src in paths:
        tmp = None
        try:
            if not os.path.isfile(src):
                skipped.append(f"{os.path.basename(src)}（不是文件）")
                continue
            src_real = os.path.realpath(src)
            if os.path.normcase(os.path.dirname(src_real)) == target_real:
                skipped.append(f"{os.path.basename(src)}（已在这个文件夹）")
                continue
            tmp = store.new_temp()
            shutil.copy2(src, tmp)
            final = store.commit(tmp, os.path.basename(src), rel)
            tmp = None
            added.append(final)
        except Exception as e:
            errors.append(f"{os.path.basename(src)}：{e}")
        finally:
            if tmp:
                store.discard(tmp)
    return added, skipped, errors


def export_files(store, names, dest_dir, rel=""):
    copied, errors = [], []
    for name in names:
        src = store.resolve("/".join(part for part in (rel, name) if part))
        if src is None:
            errors.append(f"{name}：源文件不存在")
            continue
        try:
            target = unique_in_dir(dest_dir, name)
            shutil.copy2(src, target)
            copied.append(os.path.basename(target))
        except Exception as e:
            errors.append(f"{name}：{e}")
    return copied, errors


class App:
    def __init__(self, root, share, token, port=0, host="0.0.0.0"):
        self.root = root
        self.share = share
        self.token = token
        self.host = host
        self.preferred_port = port
        self.store = srv.Store(share)
        self.ips = srv.lan_ipv4s()
        self.ip_index = 0
        self.port = 0
        self.server = None
        self.server_thread = None
        self.url = ""
        self.signature = None
        self.cwd = ""
        self.display_font = pick_display_font(root)
        self.icon_img = None
        self.icon_head = None
        self.icon_empty = None
        self._hover_row = None
        self._rows = {}
        self._tick_job = None
        self._qr_win = None
        self._qr_img = None
        self._drop_hot = False
        self._drop_saved_msg = None
        self._drop_leave_job = None
        self._load_icon()
        self.root.title("LANist · 局域网传文件")
        width, height = px(960), px(720)
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(px(900), px(640))
        self._build()
        self._enable_dnd(self.files_card)
        self.refresh_files(force=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()

    def _load_icon(self):
        try:
            self.icon_img = tk.PhotoImage(master=self.root, file=ICON_PNG)
        except Exception:
            self.icon_img = None
        if self.icon_img is None:
            return
        try:
            self.root.iconphoto(True, self.icon_img)
        except Exception:
            pass
        self.icon_head = self._icon_at(40)
        self.icon_empty = self._icon_at(64)

    def _icon_at(self, logical):
        factor = max(1, int(round(256 / (logical * SCALE))))
        if factor <= 1:
            return self.icon_img
        try:
            return self.icon_img.subsample(factor, factor)
        except Exception:
            return self.icon_img

    def _build(self):
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=px(20), pady=px(18))

        header = tk.Frame(outer, bg=BG, height=px(56))
        header.pack(fill="x")
        header.pack_propagate(False)
        if self.icon_head is not None:
            tk.Label(header, image=self.icon_head, bg=BG).pack(
                side="left", padx=(0, px(13))
            )
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(side="left")
        tk.Label(
            title_row,
            text="LANist",
            bg=BG,
            fg=TEXT,
            font=(self.display_font, 24),
        ).pack(side="left")
        self.status_pill = StatusPill(header, bg=BG)
        self.status_pill.pack(side="right")

        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True, pady=(px(14), 0))

        left = tk.Frame(content, bg=BG, width=px(320))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        service = RoundedCard(
            left,
            height=560,
            fill=DARK,
            border=DARK_LINE,
            radius=18,
            bg=BG,
            inset=12,
        )
        service.pack(fill="both", expand=True)
        inside = tk.Frame(service.body, bg=DARK)
        inside.pack(fill="both", expand=True, padx=px(12), pady=px(14))

        sfoot = tk.Frame(inside, bg=DARK)
        sfoot.pack(side="bottom", fill="x")
        tk.Frame(sfoot, bg=DARK_LINE, height=1).pack(fill="x", pady=(0, px(10)))
        tk.Label(
            sfoot,
            text="\ue72e",
            bg=DARK,
            fg="#7d90b0",
            font=("Segoe MDL2 Assets", 9),
        ).pack(side="left")
        tk.Label(
            sfoot,
            text="只在局域网内传输，不经过外网",
            bg=DARK,
            fg="#7d90b0",
            font=("Microsoft YaHei UI", 8),
        ).pack(side="left", padx=(px(6), 0))

        addr_row = tk.Frame(inside, bg=DARK)
        addr_row.pack(fill="x")
        tk.Label(
            addr_row,
            text="访问地址",
            bg=DARK,
            fg=DARK_MUTED,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")
        self.qr_btn = RoundButton(
            addr_row,
            "二维码",
            command=self.show_qr,
            kind="on_dark_ghost",
            bg=DARK,
            height=24,
            fixed_width=76,
        )
        self.qr_btn.pack(side="right")
        self.qr_btn.set_enabled(False)
        self.url_box = UrlBox(inside, 272, self.copy_url, bg=DARK)
        self.url_box.set_url("")
        self.url_box.pack(anchor="w", pady=(px(8), 0))
        token_row = tk.Frame(inside, bg=DARK)
        token_row.pack(fill="x", pady=(px(10), 0))
        tk.Label(
            token_row,
            text="口令",
            bg=DARK,
            fg=DARK_MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")
        TokenChip(token_row, self.token, bg=DARK).pack(
            side="left", padx=(px(8), 0)
        )
        if len(self.ips) > 1:
            self.alt_btn = RoundButton(
                token_row,
                "换地址",
                command=self._cycle_ip,
                kind="on_dark_ghost",
                bg=DARK,
                height=24,
                fixed_width=76,
            )
            self.alt_btn.pack(side="right")
        else:
            self.alt_btn = None
        self.action_btn = RoundButton(
            inside,
            "启动服务",
            command=self._toggle_service,
            kind="on_dark",
            icon="\ue768",
            bg=DARK,
            height=36,
            fixed_width=272,
        )
        self.action_btn.pack(anchor="w", pady=(px(16), 0))
        tk.Frame(inside, bg=DARK_LINE, height=1).pack(
            fill="x", pady=(px(20), px(16))
        )
        tk.Label(
            inside,
            text="共享目录",
            bg=DARK,
            fg=DARK_MUTED,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            inside,
            text=self.share,
            bg=DARK,
            fg="#b9c7de",
            font=("Microsoft YaHei UI", 9),
            wraplength=px(272),
            justify="left",
        ).pack(anchor="w", pady=(px(4), 0))
        self.open_btn = RoundButton(
            inside,
            "打开文件夹",
            command=self.open_share,
            kind="on_dark_ghost",
            icon="\ue838",
            bg=DARK,
            height=32,
            fixed_width=272,
        )
        self.open_btn.pack(anchor="w", pady=(px(10), 0))

        tk.Frame(inside, bg=DARK_LINE, height=1).pack(
            fill="x", pady=(px(20), px(14))
        )
        tk.Label(
            inside,
            text="使用提示",
            bg=DARK,
            fg=DARK_MUTED,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(anchor="w")
        for glyph, tip in (
            (
                "\ue898",
                "拖文件到右侧列表导入"
                if DND_FILES is not None
                else "点「上传文件」，或拖进网页",
            ),
            ("\ue77f", "Ctrl+C 后回来点「粘贴」"),
            ("\ue7e8", "关掉窗口即停止服务"),
        ):
            row = tk.Frame(inside, bg=DARK)
            row.pack(fill="x", pady=(px(10), 0))
            GlyphBadge(
                row, glyph, bg=DARK, fill="#1c2b47", fg="#9db8e2"
            ).pack(side="left", anchor="n")
            tk.Label(
                row,
                text=tip,
                bg=DARK,
                fg="#b9c7de",
                font=("Microsoft YaHei UI", 9),
                wraplength=px(226),
                justify="left",
            ).pack(side="left", padx=(px(9), 0))

        files = RoundedCard(
            content,
            height=560,
            fill=CARD,
            border=LINE,
            radius=18,
            bg=BG,
            inset=12,
        )
        files.pack(side="left", fill="both", expand=True, padx=(px(16), 0))
        self.files_card = files
        fin = tk.Frame(files.body, bg=CARD)
        fin.pack(fill="both", expand=True, padx=px(16), pady=px(14))

        fhead = tk.Frame(fin, bg=CARD)
        fhead.pack(fill="x")
        tk.Label(
            fhead,
            text="文件",
            bg=CARD,
            fg=TEXT,
            font=("Microsoft YaHei UI", 16, "bold"),
        ).pack(side="left")
        self.count_var = tk.StringVar(value="")
        tk.Label(
            fhead,
            textvariable=self.count_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", padx=(px(10), 0), pady=(px(5), 0))
        self.refresh_btn = RoundButton(
            fhead,
            "",
            command=lambda: self.refresh_files(force=True),
            kind="ghost",
            icon="\ue72c",
            bg=CARD,
            height=34,
            padx=9,
            min_width=34,
        )
        self.refresh_btn.pack(side="right")

        path_row = tk.Frame(fin, bg=CARD)
        path_row.pack(fill="x", pady=(px(7), 0))
        self.up_btn = RoundButton(
            path_row,
            "",
            command=self._go_up,
            kind="ghost",
            icon="\ue72b",
            bg=CARD,
            height=24,
            padx=5,
            min_width=24,
            radius=7,
        )
        self.path_var = tk.StringVar(value="共享目录")
        self.path_label = tk.Label(
            path_row,
            textvariable=self.path_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        )
        self.path_label.pack(side="left", padx=(px(6), 0), fill="x", expand=True)

        bar = tk.Frame(fin, bg=CARD)
        bar.pack(fill="x", pady=(px(8), 0))
        self.add_btn = RoundButton(
            bar,
            "上传文件",
            self.add_files,
            kind="primary",
            icon="\ue710",
            bg=CARD,
        )
        self.add_btn.pack(side="left")
        self.paste_btn = RoundButton(
            bar,
            "粘贴",
            self.paste_files,
            kind="ghost",
            icon="\ue77f",
            bg=CARD,
        )
        self.paste_btn.pack(side="left", padx=(px(6), 0))
        self.export_btn = RoundButton(
            bar,
            "下载选中",
            self.export_selected,
            kind="ghost",
            icon="\ue896",
            bg=CARD,
        )
        self.export_btn.pack(side="left", padx=(px(6), 0))
        self.delete_btn = RoundButton(
            bar,
            "删除",
            self.delete_selected,
            kind="danger",
            icon="\ue74d",
            bg=CARD,
        )
        self.delete_btn.pack(side="left", padx=(px(6), 0))

        self.message_var = tk.StringVar(
            value="上传：把本机文件放进共享目录；下载：把共享目录的文件存到本机。"
        )
        self.footer = tk.Frame(fin, bg=CARD)
        self.footer.pack(side="bottom", fill="x")
        tk.Label(
            self.footer,
            text="\ue946",
            bg=CARD,
            fg=SOFT,
            font=("Segoe MDL2 Assets", 9),
        ).pack(side="left", padx=(px(2), px(8)))
        self.msg_label = tk.Label(
            self.footer,
            textvariable=self.message_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
        )
        self.msg_label.pack(
            side="left", fill="x", expand=True, pady=(px(9), px(9))
        )
        self.footer.bind("<Configure>", self._fit_message)
        tk.Frame(fin, bg=LINE, height=1).pack(
            side="bottom", fill="x", pady=(px(9), 0)
        )

        tree_frame = tk.Frame(fin, bg=CARD)
        tree_frame.pack(fill="both", expand=True, pady=(px(12), 0))
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("name", "size", "mtime"),
            show="headings",
            selectmode="extended",
            height=8,
            style="App.Treeview",
        )
        self.tree.heading("name", text="文件名", anchor="w")
        self.tree.heading("size", text="大小", anchor="e")
        self.tree.heading("mtime", text="修改时间", anchor="e")
        self.tree.column(
            "name", width=px(360), minwidth=px(180), anchor="w", stretch=False
        )
        self.tree.column("size", width=px(84), anchor="e", stretch=False)
        self.tree.column("mtime", width=px(150), anchor="e", stretch=False)
        self.tree.bind("<Configure>", self._fit_columns)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", self._on_tree_leave)
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<Double-1>", self._on_tree_open)
        self.tree.bind("<Return>", self._on_tree_open)
        self.tree.bind("<BackSpace>", lambda _e: self._go_up())
        self.tree.tag_configure("hover", background="#f3f7fc")
        self.tree.tag_configure(
            "folder", font=("Microsoft YaHei UI", 10, "bold")
        )
        self.scroll = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
            style="App.Vertical.TScrollbar",
        )
        self.tree.configure(yscrollcommand=self.scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        self.empty = tk.Canvas(
            tree_frame, bg=CARD, highlightthickness=0, bd=0
        )
        self.empty_title = tk.StringVar(value="共享目录还是空的")
        self.empty_hint = tk.StringVar(value="把文件拖到这里，或点「上传文件」")
        self._empty_title_font = tkfont.Font(
            root=self.root, family="Microsoft YaHei UI", size=13, weight="bold"
        )
        self._empty_hint_font = tkfont.Font(
            root=self.root, family="Microsoft YaHei UI", size=9
        )
        self.empty.bind("<Configure>", self._draw_empty)
        self.empty_title.trace_add("write", lambda *_: self._draw_empty())
        self.empty_hint.trace_add("write", lambda *_: self._draw_empty())
        self.root.after_idle(self._fit_columns)
        self.root.bind("<F5>", lambda _e: self.refresh_files(force=True))

    def _fit_message(self, event):
        self.msg_label.configure(
            wraplength=max(px(180), event.width - px(52))
        )

    def _fit_columns(self, _=None):
        total = self.tree.winfo_width()
        if total <= 1:
            return
        self.tree.column(
            "name",
            width=max(px(120), total - px(84) - px(150) - px(18)),
        )
        self.root.after_idle(self._sync_scroll)

    def _apply_tags(self, iid, hover):
        entry = self._rows.get(iid)
        tags = ("folder",) if entry is not None and entry.is_dir else ()
        if hover:
            tags = tags + ("hover",)
        self.tree.item(iid, tags=tags)

    def _on_tree_motion(self, event):
        row = self.tree.identify_row(event.y)
        if row == self._hover_row:
            return
        if self._hover_row:
            self._apply_tags(self._hover_row, False)
        if row:
            self._apply_tags(row, True)
        self._hover_row = row

    def _on_tree_leave(self, _event):
        if self._hover_row:
            self._apply_tags(self._hover_row, False)
            self._hover_row = None

    def _on_tree_open(self, event=None):
        if event is not None and event.y:
            row = self.tree.identify_row(event.y)
            if row:
                self.tree.selection_set(row)
        selected = self.tree.selection()
        if not selected:
            return
        entry = self._rows.get(selected[0])
        if entry is not None and entry.is_dir:
            self._enter_folder(entry.name)

    def _enter_folder(self, name):
        target = "/".join(part for part in (self.cwd, name) if part)
        if self.store.resolve_dir(target) is None:
            self.set_message("这个文件夹已经不在了。")
            self.refresh_files(force=True)
            return
        self.cwd = target
        self._update_path()
        self.refresh_files(force=True)

    def _go_up(self):
        if not self.cwd:
            return "break"
        self.cwd = self.cwd.rsplit("/", 1)[0] if "/" in self.cwd else ""
        self._update_path()
        self.refresh_files(force=True)
        return "break"

    def _update_path(self):
        parts = self.cwd.split("/") if self.cwd else []
        self.path_var.set("共享目录" + "".join(" / " + part for part in parts))
        if parts:
            if not self.up_btn.winfo_ismapped():
                self.up_btn.pack(side="left", before=self.path_label)
        elif self.up_btn.winfo_ismapped():
            self.up_btn.pack_forget()
        self.empty_title.set("这个文件夹是空的" if parts else "共享目录还是空的")
        self.empty_hint.set(
            "文件由主机放进来；上传会加在当前文件夹"
            if parts
            else "把文件拖到这里，或点「上传文件」"
        )

    def _enable_dnd(self, widget):
        if DND_FILES is None:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_drop_leave)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._enable_dnd(child)

    def _on_drop_enter(self, _event):
        if self._drop_leave_job is not None:
            self.root.after_cancel(self._drop_leave_job)
            self._drop_leave_job = None
        if not self._drop_hot:
            self._drop_hot = True
            self.files_card.set_border(ACCENT, 2)
            self._drop_saved_msg = self.message_var.get()
            self.set_message("松开鼠标，文件会放进共享目录。")
        return "copy"

    def _on_drop_leave(self, _event):
        if not self._drop_hot:
            return
        if self._drop_leave_job is not None:
            self.root.after_cancel(self._drop_leave_job)
        # 拖过子控件时会先 leave 再 enter，稍等再撤销高亮。
        self._drop_leave_job = self.root.after(120, self._drop_reset)

    def _drop_reset(self):
        self._drop_leave_job = None
        if not self._drop_hot:
            return
        self._drop_hot = False
        self.files_card.set_border(LINE, 1)
        if self._drop_saved_msg is not None:
            self.set_message(self._drop_saved_msg)
            self._drop_saved_msg = None

    def _on_drop(self, event):
        if self._drop_leave_job is not None:
            self.root.after_cancel(self._drop_leave_job)
            self._drop_leave_job = None
        self._drop_hot = False
        self._drop_saved_msg = None
        self.files_card.set_border(LINE, 1)
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:
            paths = [event.data]
        paths = [os.path.normpath(p) for p in paths if p]
        if not paths:
            self.set_message("没有识别到文件。")
            return "copy"
        self.root.after_idle(lambda: self.import_paths(paths))
        return "copy"

    def _select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _draw_empty(self, _event=None):
        canvas = self.empty
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 2 or height < 2:
            return
        canvas.delete("empty")
        title_h = self._empty_title_font.metrics("linespace")
        hint_h = self._empty_hint_font.metrics("linespace")
        icon_h = self.icon_empty.height() if self.icon_empty is not None else 0
        gap = px(10) if icon_h else 0
        block = icon_h + gap + title_h + px(3) + hint_h
        top = height * 0.55 - block / 2
        if self.icon_empty is not None:
            canvas.create_image(
                width / 2, top + icon_h / 2, image=self.icon_empty, tags="empty"
            )
            top += icon_h + gap
        canvas.create_text(
            width / 2,
            top,
            text=self.empty_title.get(),
            anchor="n",
            font=self._empty_title_font,
            fill=TEXT,
            tags="empty",
        )
        canvas.create_text(
            width / 2,
            top + title_h + px(3),
            text=self.empty_hint.get(),
            anchor="n",
            font=self._empty_hint_font,
            fill=MUTED,
            tags="empty",
        )

    def _toggle_empty(self, empty):
        if empty:
            self.scroll.pack_forget()
            self.empty.place(x=0, y=0, relwidth=1, relheight=1)
            self._draw_empty()
        else:
            self.empty.place_forget()
            self.root.after_idle(self._sync_scroll)

    def _sync_scroll(self):
        first, last = self.tree.yview()
        fits = first <= 0.0 and last >= 1.0
        if fits:
            if self.scroll.winfo_ismapped():
                self.scroll.pack_forget()
        elif not self.scroll.winfo_ismapped():
            self.scroll.pack(side="right", fill="y")

    def _set_status(self, kind, text):
        self.status_pill.set(kind, text)

    def _toggle_service(self):
        if self.server is None:
            self.start_service()
        else:
            self.stop_service()

    def set_message(self, text):
        self.message_var.set(text)

    def refresh_files(self, force=False):
        if self.cwd and self.store.resolve_dir(self.cwd) is None:
            self.cwd = ""
            self._update_path()
            self.set_message("当前文件夹已经不在了，已回到共享目录。")
        entries = self.store.list(self.cwd)
        signature = (
            self.cwd,
            tuple((e.name, e.size, e.mtime, e.is_dir) for e in entries),
        )
        if not force and signature == self.signature:
            return
        selected = set()
        for iid in self.tree.selection():
            entry = self._rows.get(iid)
            if entry is not None:
                selected.add(entry.name)
        scroll_pos = self.tree.yview()[0]
        self._hover_row = None
        self._rows = {}
        self.tree.delete(*self.tree.get_children())
        for entry in entries:
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    entry.name + "/" if entry.is_dir else entry.name,
                    "文件夹"
                    if entry.is_dir
                    else srv.human_size(entry.size),
                    "—"
                    if entry.is_dir
                    else datetime.fromtimestamp(entry.mtime).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                ),
                tags=("folder",) if entry.is_dir else (),
            )
            self._rows[iid] = entry
            if entry.name in selected:
                self.tree.selection_add(iid)
        self.tree.yview_moveto(scroll_pos)
        self.signature = signature
        files = [e for e in entries if not e.is_dir]
        folders = len(entries) - len(files)
        parts = []
        if files:
            parts.append(f"{len(files)} 个文件")
        if folders:
            parts.append(f"{folders} 个文件夹")
        self.count_var.set(" · ".join(parts))
        self._toggle_empty(not entries)

    def _tick(self):
        self.refresh_files()
        self._tick_job = self.root.after(REFRESH_MS, self._tick)

    def selected_names(self):
        names = []
        for iid in self.tree.selection():
            entry = self._rows.get(iid)
            if entry is not None and not entry.is_dir:
                names.append(entry.name)
        return names

    def _selected_folders(self):
        return [
            entry.name
            for iid in self.tree.selection()
            for entry in (self._rows.get(iid),)
            if entry is not None and entry.is_dir
        ]

    def start_service(self):
        if self.server is not None:
            return
        self.action_btn.set_enabled(False)
        self._set_status("busy", "正在启动…")
        self.set_message("正在启动服务…")
        self.root.update_idletasks()
        try:
            server, port = srv.create_server(
                self.share,
                self.token,
                host=self.host,
                port=self.preferred_port,
            )
        except Exception as e:
            self._set_status("error", "启动失败")
            self.action_btn.set_button(
                text="启动服务", kind="on_dark", icon="\ue768"
            )
            self.action_btn.set_enabled(True)
            self.set_message("启动失败。")
            messagebox.showerror("启动失败", str(e), parent=self.root)
            return
        self.server = server
        self.port = port
        self.server_thread = threading.Thread(
            target=server.serve_forever, daemon=True
        )
        self.server_thread.start()
        self.ips = srv.lan_ipv4s()
        local_only = not self.ips
        if local_only:
            self.ips = ["127.0.0.1"]
        self.ip_index = min(self.ip_index, len(self.ips) - 1)
        self._update_url()
        self._set_status("run", f"运行中 · {port}")
        self.action_btn.set_button(
            text="停止服务", kind="on_dark_ghost", icon="\ue7e8"
        )
        self.action_btn.set_enabled(True)
        if local_only:
            self.set_message("服务已启动，但没有找到局域网 IP；这台机可以先用 127.0.0.1 打开。")
        else:
            self.set_message("服务已启动。同一局域网内用浏览器打开左边的地址。")

    def stop_service(self):
        server = self.server
        if server is None:
            return
        self.server = None
        self.action_btn.set_enabled(False)
        self._set_status("busy", "正在停止…")
        self.root.update_idletasks()
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        if self.server_thread is not None:
            self.server_thread.join(timeout=2)
        self.server_thread = None
        self.url = ""
        self.url_box.set_url("")
        self.qr_btn.set_enabled(False)
        self._close_qr()
        self._set_status("idle", "未启动")
        self.action_btn.set_button(
            text="启动服务", kind="on_dark", icon="\ue768"
        )
        self.action_btn.set_enabled(True)
        self.set_message("服务已停止，浏览器现在打不开页面。")

    def _update_url(self):
        if self.server is None or not self.ips:
            self.url = ""
            self.url_box.set_url("")
            self.qr_btn.set_enabled(False)
            return
        self.url = "http://{}:{}/{}/".format(
            self.ips[self.ip_index], self.port, self.token
        )
        self.url_box.set_url(self.url)
        self.qr_btn.set_enabled(QrCode is not None)

    def _cycle_ip(self):
        if len(self.ips) < 2:
            return
        self.ip_index = (self.ip_index + 1) % len(self.ips)
        self._update_url()
        self.set_message("已切换地址：" + self.ips[self.ip_index])

    def copy_url(self):
        if not self.url:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url)
        self.root.update()
        self.set_message("链接已复制。")

    def show_qr(self):
        if not self.url:
            messagebox.showinfo("二维码", "先启动服务，再显示二维码。", parent=self.root)
            return
        if self._qr_win is not None and self._qr_win.winfo_exists():
            self._qr_win.lift()
            return
        try:
            self._qr_img = qr_photo(self.url, master=self.root)
        except Exception as e:
            messagebox.showerror("二维码", str(e), parent=self.root)
            return
        win = tk.Toplevel(self.root)
        self._qr_win = win
        win.title("扫码打开 LANist")
        win.configure(bg=CARD)
        win.transient(self.root)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self._close_qr)
        body = tk.Frame(win, bg=CARD)
        body.pack(padx=px(22), pady=px(20))
        tk.Label(body, image=self._qr_img, bg=CARD, bd=0).pack()
        tk.Label(
            body,
            text=self.url,
            bg=CARD,
            fg=TEXT,
            font=("Consolas", 9),
            wraplength=px(320),
            justify="center",
        ).pack(pady=(px(13), px(4)))
        tk.Label(
            body,
            text="用手机相机扫码打开；同一局域网内有效",
            bg=CARD,
            fg=SOFT,
            font=("Microsoft YaHei UI", 9),
        ).pack()
        RoundButton(
            body,
            "关闭",
            command=self._close_qr,
            kind="secondary",
            bg=CARD,
            height=32,
            fixed_width=110,
        ).pack(pady=(px(16), 0))
        win.bind("<Escape>", lambda _e: self._close_qr())
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        try:
            win.grab_set()
        except tk.TclError:
            pass

    def _close_qr(self):
        win = self._qr_win
        self._qr_win = None
        if win is not None:
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
        self._qr_img = None

    def open_share(self):
        try:
            self.store.ensure()
            os.startfile(self.share)
        except (OSError, RuntimeError) as e:
            messagebox.showerror("打不开共享目录", str(e), parent=self.root)

    def add_files(self):
        paths = filedialog.askopenfilenames(
            parent=self.root, title="选择要放入共享目录的文件"
        )
        if paths:
            self.import_paths(paths)

    def paste_files(self):
        try:
            paths = clipboard_files()
        except RuntimeError as e:
            messagebox.showerror("粘贴失败", str(e), parent=self.root)
            return
        if not paths:
            messagebox.showinfo(
                "粘贴",
                "剪贴板里没有文件。先在资源管理器里复制文件，再回来点粘贴。",
                parent=self.root,
            )
            return
        self.import_paths(paths)

    def import_paths(self, paths):
        self.set_message(f"正在复制 {len(paths)} 个文件…")
        self.root.update_idletasks()
        added, skipped, errors = copy_into_share(self.store, paths, self.cwd)
        self.refresh_files(force=True)
        summary = []
        if added:
            summary.append(f"已放入 {len(added)} 个文件")
        if skipped:
            summary.append(f"跳过 {len(skipped)} 个")
        if errors:
            summary.append(f"失败 {len(errors)} 个")
        self.set_message("，".join(summary) + "。" if summary else "没有可导入的文件。")
        if errors:
            messagebox.showerror(
                "部分文件未导入", "\n".join(errors[:10]), parent=self.root
            )
        elif skipped and not added:
            messagebox.showinfo(
                "未导入", "\n".join(skipped[:10]), parent=self.root
            )

    def export_selected(self):
        names = self.selected_names()
        if not names:
            messagebox.showinfo(
                "下载", "先在列表里选中要下载的文件。", parent=self.root
            )
            return
        dest = filedialog.askdirectory(
            parent=self.root, title="选择下载到哪个文件夹"
        )
        if not dest:
            return
        current = self.store.resolve_dir(self.cwd) or self.share
        if os.path.normcase(os.path.realpath(dest)) == os.path.normcase(
            os.path.realpath(current)
        ):
            messagebox.showinfo(
                "下载", "这就是共享目录里的当前文件夹，不用再导出。", parent=self.root
            )
            return
        self.set_message(f"正在下载 {len(names)} 个文件…")
        self.root.update_idletasks()
        copied, errors = export_files(self.store, names, dest, self.cwd)
        self.refresh_files(force=True)
        if copied:
            self.set_message(f"已下载 {len(copied)} 个文件到 {dest}。")
        if errors:
            messagebox.showerror(
                "部分文件未下载", "\n".join(errors[:10]), parent=self.root
            )

    def delete_selected(self):
        names = self.selected_names()
        if not names:
            message = (
                "文件夹请在资源管理器里删除。"
                if self._selected_folders()
                else "先在列表里选中要删除的文件。"
            )
            messagebox.showinfo("删除", message, parent=self.root)
            return
        paths = [
            p
            for p in (
                self.store.resolve(
                    "/".join(part for part in (self.cwd, name) if part)
                )
                for name in names
            )
            if p
        ]
        if not paths:
            self.refresh_files(force=True)
            self.set_message("选中的文件已经不存在。")
            return
        if not messagebox.askyesno(
            "删除",
            f"把选中的 {len(paths)} 个文件移到回收站？",
            parent=self.root,
        ):
            return
        try:
            recycle_paths(paths)
        except OSError as e:
            messagebox.showerror("删除失败", str(e), parent=self.root)
            return
        self.refresh_files(force=True)
        self.set_message(f"已移到回收站 {len(paths)} 个文件。")

    def on_close(self):
        self._close_qr()
        if self._tick_job is not None:
            try:
                self.root.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
        if self.server is not None:
            self.stop_service()
        # Release Tk images while Tcl is still alive; otherwise they can be
        # finalized from another thread later and raise.
        self.icon_img = None
        self.icon_head = None
        self.icon_empty = None
        self.root.destroy()


def _create_root():
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk()
        except Exception:
            pass
    return tk.Tk()


def apply_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "App.Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        rowheight=px(36),
        borderwidth=0,
        relief="flat",
        bordercolor=CARD,
        lightcolor=CARD,
        darkcolor=CARD,
        font=("Microsoft YaHei UI", 10),
    )
    style.map(
        "App.Treeview",
        background=[("selected", "#e8f0fe")],
        foreground=[("selected", TEXT)],
    )
    style.configure(
        "App.Treeview.Heading",
        background=CARD,
        foreground=MUTED,
        relief="flat",
        borderwidth=0,
        lightcolor=CARD,
        darkcolor=CARD,
        bordercolor=CARD,
        padding=(px(8), px(7)),
        font=("Microsoft YaHei UI", 9, "bold"),
    )
    style.map(
        "App.Treeview.Heading",
        background=[("active", CARD), ("pressed", CARD)],
    )
    try:
        style.layout(
            "App.Treeview",
            [("Treeview.treearea", {"sticky": "nswe"})],
        )
        style.layout(
            "App.Treeview.Heading",
            [
                (
                    "Treeheading.cell",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Treeheading.padding",
                                {
                                    "sticky": "nswe",
                                    "children": [
                                        (
                                            "Treeheading.image",
                                            {"side": "right", "sticky": ""},
                                        ),
                                        (
                                            "Treeheading.text",
                                            {"sticky": "we"},
                                        ),
                                    ],
                                },
                            )
                        ],
                    },
                )
            ],
        )
    except tk.TclError:
        pass
    style.configure(
        "App.Vertical.TScrollbar",
        background="#c9d5e6",
        troughcolor=CARD,
        bordercolor=CARD,
        lightcolor="#c9d5e6",
        darkcolor="#c9d5e6",
        arrowcolor=CARD,
        gripcount=0,
        gripsize=0,
        relief="flat",
        borderwidth=0,
        width=px(10),
    )
    try:
        style.layout(
            "App.Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {
                        "sticky": "ns",
                        "children": [
                            (
                                "Vertical.Scrollbar.thumb",
                                {"expand": "1", "sticky": "nswe"},
                            )
                        ],
                    },
                )
            ],
        )
    except tk.TclError:
        pass


def run(share, token, port=0, host="0.0.0.0"):
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LANist.App")
    except Exception:
        pass
    root = _create_root()
    global SCALE
    SCALE = root.winfo_fpixels("1i") / 96.0
    root.configure(bg=BG)
    apply_styles(root)
    try:
        App(root, share=share, token=token, port=port, host=host)
        root.mainloop()
    except Exception:
        import traceback

        traceback.print_exc()
        try:
            messagebox.showerror("LANist 启动失败", traceback.format_exc())
        except Exception:
            pass
        return 1
    return 0
