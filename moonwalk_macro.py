import json
import math
import os
import random
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

# ============================================================================
#  WINDOWS API  (ctypes)  -  SendInput pakai SCAN CODE biar kebaca game
# ============================================================================
import ctypes
from ctypes import wintypes

# ============================================================================
#  OPSI TAMPILAN  -  ubah di sini kalau ada masalah
# ============================================================================
LAYOUT = "macos"             # "macos" | "game" | "minimal" | "pro"
SHOW_BG = True               # background senja di layout "game"
VERSION = "6.0"
UPDATE_URL = ""              # link raw ke moonwalk_macro.py versi terbaru
USE_CUSTOM_TITLEBAR = True   # False = pakai frame Windows biasa (lebih aman)
ALWAYS_ON_TOP       = True   # False = jendela bisa ketutup window lain


IS_WINDOWS = sys.platform.startswith("win")
user32 = ctypes.WinDLL("user32", use_last_error=True) if IS_WINDOWS else None
PUL = ctypes.POINTER(ctypes.c_ulong)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", PUL)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", PUL)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SC_A, SC_D = 0x1E, 0x20      # scan code set 1

# Scan code set 1 untuk tombol yang bisa dipakai di urutan macro
SC_MAP = {
    "A": 0x1E, "B": 0x30, "C": 0x2E, "D": 0x20, "E": 0x12, "F": 0x21,
    "G": 0x22, "H": 0x23, "I": 0x17, "J": 0x24, "K": 0x25, "L": 0x26,
    "M": 0x32, "N": 0x31, "O": 0x18, "P": 0x19, "Q": 0x10, "R": 0x13,
    "S": 0x1F, "T": 0x14, "U": 0x16, "V": 0x2F, "W": 0x11, "X": 0x2D,
    "Y": 0x15, "Z": 0x2C,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07,
    "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "SPACE": 0x39, "TAB": 0x0F, "SHIFT": 0x2A, "CTRL": 0x1D, "ALT": 0x38,
    "ENTER": 0x1C, "ESC": 0x01, "BACKSPACE": 0x0E, "CAPSLOCK": 0x3A,
    "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E, "F5": 0x3F, "F6": 0x40,
    "F7": 0x41, "F8": 0x42, "F9": 0x43, "F10": 0x44, "F11": 0x57, "F12": 0x58,
    "LEFT": 0x4B, "RIGHT": 0x4D, "UP": 0x48, "DOWN": 0x50,
}
EXTENDED_KEYS = {"LEFT", "RIGHT", "UP", "DOWN"}


def sc_from_name(name):
    """Scan code + flag extended dari nama tombol."""
    n = (name or "").strip().upper()
    return SC_MAP.get(n, 0), (n in EXTENDED_KEYS)


def _send_scan(scan_code, key_up_flag, extended=False):
    if not IS_WINDOWS or not scan_code:
        return
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up_flag else 0)
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    extra = ctypes.c_ulong(0)
    inp = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(
        ki=KEYBDINPUT(0, scan_code, flags, 0, ctypes.pointer(extra))))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def key_down(sc, ext=False):
    _send_scan(sc, False, ext)


def key_up(sc, ext=False):
    _send_scan(sc, True, ext)


# ---------------------------------------------------------------------------
#  TIMING PRESISI
#
#  Masalah: default-nya Windows cuma bangunin thread tiap 15.6 ms. Jadi
#  time.sleep(0.035) beneran tidurnya 31 ms ATAU 47 ms — acak. Di game keliatan
#  patah-patah walaupun angka di UI-nya 35 ms.
#
#  Solusi: minta resolusi timer 1 ms ke Windows (timeBeginPeriod), sisa waktu
#  di bawah 2 ms di-spin biar akurat sampai < 0.5 ms.
# ---------------------------------------------------------------------------
_timer_boosted = [False]


def timer_begin():
    """Naikin resolusi timer Windows ke 1 ms."""
    if not IS_WINDOWS or _timer_boosted[0]:
        return
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
        _timer_boosted[0] = True
    except Exception:
        pass


def timer_end():
    if not IS_WINDOWS or not _timer_boosted[0]:
        return
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
        _timer_boosted[0] = False
    except Exception:
        pass


def boost_thread():
    """Naikin prioritas thread spam biar nggak kalah rebutan CPU."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.kernel32.SetThreadPriority(
            ctypes.windll.kernel32.GetCurrentThread(), 2)  # HIGHEST
    except Exception:
        pass


def sleep_precise(sec):
    """time.sleep yang akurat: tidur kasar dulu, sisanya di-spin."""
    if sec <= 0:
        return
    end = time.perf_counter() + sec
    coarse = sec - 0.0016
    if coarse > 0:
        time.sleep(coarse)
    while time.perf_counter() < end:
        pass


def press_name(name, down=True):
    sc, ext = sc_from_name(name)
    _send_scan(sc, not down, ext)


def is_pressed(vk):
    if not IS_WINDOWS or vk <= 0:
        return False
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)



GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080


def show_in_taskbar(root):
    """Window borderless (overrideredirect) normalnya hilang dari taskbar.
    Ini bikin dia tetap muncul + bisa di-Alt+Tab."""
    if not IS_WINDOWS:
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style & WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        root.withdraw()
        root.after(10, root.deiconify)
    except Exception:
        pass


def enable_dpi_awareness():
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ============================================================================
#  MAPPING NAMA TOMBOL -> VIRTUAL KEY
# ============================================================================
VK_MAP = {
    "BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "SHIFT": 0x10, "CTRL": 0x11,
    "ALT": 0x12, "CAPSLOCK": 0x14, "ESC": 0x1B, "SPACE": 0x20,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22, "END": 0x23, "HOME": 0x24,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "INSERT": 0x2D, "DELETE": 0x2E,
    "MOUSE3": 0x04, "MOUSE4": 0x05, "MOUSE5": 0x06,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}
for _i in range(1, 13):
    VK_MAP["F%d" % _i] = 0x6F + _i
for _i in range(10):
    VK_MAP["NUM%d" % _i] = 0x60 + _i
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    VK_MAP[_c] = ord(_c)


def vk_from_name(name):
    return VK_MAP.get((name or "").strip().upper(), 0)


def name_from_vk(vk):
    for k, v in VK_MAP.items():
        if v == vk:
            return k
    return "?"


# ============================================================================
#  SETTINGS
# ============================================================================
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SETTINGS_PATH = os.path.join(app_dir(), "settings.json")
DEFAULTS = {"hotkey": "Q", "speed": 35, "mode": "HOLD", "master_key": "F2",
            "theme": "emas", "sequence": ["A", "D"], "jitter": 0, "gap": 0, "layout": "macos",
            "show_bg": True, "update_url": ""}

PRESET_SEQ = [
    ("DA HOOD", ["I", "O"]),          # zoom kamera in/out = speed glitch
    ("MOONWALK", ["A", "D"]),
    ("MAJU MUNDUR", ["W", "S"]),
    ("A D + LOMPAT", ["A", "D", "SPACE"]),
    ("ZIGZAG", ["A", "A", "D", "D"]),
]


def _ver_tuple(v):
    out = []
    for part in str(v).split("."):
        try:
            out.append(int(re.sub(r"[^0-9]", "", part) or 0))
        except ValueError:
            out.append(0)
    return tuple(out)


def check_update(url, timeout=12):
    """Ambil versi terbaru dari url.

    Balikin (versi, isi_file, pesan_error). Sengaja nggak pakai library luar —
    urllib udah bawaan Python.
    """
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "moonwalk"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read().decode("utf-8", "replace")
    except Exception as ex:
        return None, None, "gagal ambil: %s" % ex
    if "M4CRO MOONWALK" not in data or len(data) < 20000:
        return None, None, "isinya bukan moonwalk_macro.py"
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', data, re.M)
    if not m:
        return None, None, "versi nggak ketemu di file"
    return m.group(1), data, ""


def apply_update(text):
    """Timpa file yang lagi jalan, yang lama disimpen jadi .bak."""
    try:
        me = os.path.abspath(__file__)
    except NameError:
        return "nggak bisa update versi .exe — pakai file .py"
    try:
        with open(me, "r", encoding="utf-8") as f:
            old = f.read()
        with open(me + ".bak", "w", encoding="utf-8") as f:
            f.write(old)
        with open(me, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as ex:
        return "gagal nulis file: %s" % ex
    return ""


def restart_app():
    """Jalanin ulang aplikasi pakai file yang baru."""
    try:
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])
    except Exception:
        os._exit(0)


def load_settings():
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except Exception:
        pass
    return data


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ============================================================================
#  ENGINE MACRO
# ============================================================================
class MacroEngine:
    def __init__(self):
        self.cfg = load_settings()
        self.hotkey_vk = vk_from_name(self.cfg["hotkey"]) or ord("Q")
        self.master_vk = vk_from_name(self.cfg["master_key"]) or 0x71
        self.delay = max(1, int(self.cfg["speed"])) / 1000.0
        self.mode = self.cfg.get("mode", "HOLD")
        seq = self.cfg.get("sequence") or ["A", "D"]
        self.sequence = [k for k in seq if sc_from_name(k)[0]] or ["A", "D"]
        self.jitter = int(self.cfg.get("jitter", 0))
        self.gap = int(self.cfg.get("gap", 0))

        self.enabled = True
        self.spamming = False
        self.capture_mode = False
        self.captured_vk = 0

        self.active_key = ""        # "A" / "D" / "" -> buat visualizer
        self.presses = 0
        self._press_times = []

        self._stop = threading.Event()
        self.on_state_change = None

        threading.Thread(target=self._watcher_loop, daemon=True).start()
        threading.Thread(target=self._spam_loop, daemon=True).start()

    # ---------------- watcher hotkey global ----------------
    def _watcher_loop(self):
        prev_master = prev_hotkey = False
        while not self._stop.is_set():
            try:
                if self.capture_mode:
                    for name, vk in VK_MAP.items():
                        if vk in (0x01, 0x02):
                            continue
                        if is_pressed(vk):
                            self.captured_vk = vk
                            self.capture_mode = False
                            break
                    time.sleep(0.02)
                    continue

                m = is_pressed(self.master_vk)
                if m and not prev_master:
                    self.enabled = not self.enabled
                    if not self.enabled:
                        self._set_spam(False)
                    self._notify()
                prev_master = m

                h = is_pressed(self.hotkey_vk)
                if self.enabled:
                    if self.mode == "HOLD":
                        if h != self.spamming:
                            self._set_spam(h)
                    else:
                        if h and not prev_hotkey:
                            self._set_spam(not self.spamming)
                elif self.spamming:
                    self._set_spam(False)
                prev_hotkey = h
                time.sleep(0.005)
            except Exception:
                time.sleep(0.05)

    def _set_spam(self, value):
        if value:
            timer_begin()
        self.spamming = value
        if not value:
            self.release_all()
            self.active_key = ""
        self._notify()

    def release_all(self):
        for name in list(self.sequence):
            press_name(name, False)

    # ---------------- loop spam A + D ----------------
    def _delay_now(self):
        """Delay + jitter acak biar polanya nggak kaku."""
        d = self.delay
        if self.jitter > 0:
            j = self.jitter / 100.0
            d *= 1.0 + random.uniform(-j, j)
        return max(0.001, d)

    def _spam_loop(self):
        boost_thread()
        while not self._stop.is_set():
            if not self.spamming:
                time.sleep(0.004)
                continue
            for idx, name in enumerate(list(self.sequence)):
                if not self.spamming:
                    break
                self.active_key = "%d:%s" % (idx, name)
                # jadwal absolut: telat di satu tombol nggak numpuk ke tombol
                # berikutnya
                t0 = time.perf_counter()
                press_name(name, True)
                sleep_precise(self._delay_now() - (time.perf_counter() - t0))
                press_name(name, False)
                self._count()
                if self.gap:
                    sleep_precise(self.gap / 1000.0)
            if not self.spamming:
                self.active_key = ""

    def _count(self):
        self.presses += 1
        now = time.time()
        self._press_times.append(now)
        if len(self._press_times) > 60:
            self._press_times = self._press_times[-60:]

    def keys_per_sec(self):
        t = list(self._press_times)
        if len(t) < 2:
            return 0.0
        span = t[-1] - t[0]
        if span <= 0:
            return 0.0
        return (len(t) - 1) / span

    # ---------------- API GUI ----------------
    def set_hotkey(self, name):
        vk = vk_from_name(name)
        if not vk:
            return False
        self.hotkey_vk = vk
        self.cfg["hotkey"] = name.strip().upper()
        save_settings(self.cfg)
        self._notify()
        return True

    def set_speed(self, value):
        try:
            ms = int(float(value))
        except (ValueError, TypeError):
            return False
        ms = max(5, min(300, ms))
        self.delay = ms / 1000.0
        self.cfg["speed"] = ms
        save_settings(self.cfg)
        return True

    def set_mode(self, mode):
        self.mode = mode
        self.cfg["mode"] = mode
        save_settings(self.cfg)
        self._set_spam(False)

    def set_sequence(self, seq):
        seq = [k.upper() for k in seq if sc_from_name(k)[0]]
        self.sequence = seq or ["A"]
        self.cfg["sequence"] = self.sequence
        save_settings(self.cfg)
        self._set_spam(False)
        self._notify()

    def set_gap(self, ms):
        """Jeda setelah tombol dilepas, sebelum tombol berikutnya ditekan.

        Beberapa game (Roblox dkk) baca input per frame. Kalau tombol
        ditekan-lepas terlalu mepet, input-nya bisa kelewat sama sekali.
        """
        self.gap = max(0, min(200, int(ms)))
        self.cfg["gap"] = self.gap
        save_settings(self.cfg)

    def set_jitter(self, pct):
        self.jitter = max(0, min(60, int(pct)))
        self.cfg["jitter"] = self.jitter
        save_settings(self.cfg)

    def set_theme(self, key):
        self.cfg["theme"] = key
        save_settings(self.cfg)

    def toggle_enabled(self):
        self.enabled = not self.enabled
        if not self.enabled:
            self._set_spam(False)
        self._notify()

    def shutdown(self):
        timer_end()
        self._stop.set()
        self.release_all()

    def _notify(self):
        if self.on_state_change:
            try:
                self.on_state_change()
            except Exception:
                pass


def mix(c1, c2, t):
    c1, c2 = c1.lstrip("#"), c2.lstrip("#")
    t = max(0.0, min(1.0, t))
    out = []
    for i in (0, 2, 4):
        a, b = int(c1[i:i + 2], 16), int(c2[i:i + 2], 16)
        out.append(max(0, min(255, int(a + (b - a) * t))))
    return "#%02x%02x%02x" % tuple(out)


# ============================================================================
#  TEMA & FONT
# ============================================================================
#  Daftar tema warna. Tinggal klik titik warna di title bar buat ganti.
THEMES = {
    "emas":  {"label": "Emas",  "top": "#0b0b14", "bot": "#13131f",
              "acc": "#ffb340", "hot": "#ff8f1f", "glow2": "#5b8cff"},
    "cyan":  {"label": "Cyan",  "top": "#060f14", "bot": "#0c1a24",
              "acc": "#35e0ff", "hot": "#00b6e6", "glow2": "#2b6cff"},
    "ungu":  {"label": "Ungu",  "top": "#0d0918", "bot": "#17102a",
              "acc": "#b06bff", "hot": "#8a3dff", "glow2": "#ff5bb0"},
    "merah": {"label": "Merah", "top": "#120a0c", "bot": "#1d1014",
              "acc": "#ff6b5e", "hot": "#ff3527", "glow2": "#ffa14a"},
    "hijau": {"label": "Hijau", "top": "#06120d", "bot": "#0d2019",
              "acc": "#3ce68f", "hot": "#0fc46a", "glow2": "#35e0ff"},
}
THEME_ORDER = ["emas", "cyan", "ungu", "merah", "hijau"]

BG_TOP = BG_BOT = CARD = CARD_HI = CARD_TOP = BORDER = "#000000"
TXT = MUTED = DIM = GOLD = GOLD_HOT = GOLD_DIM = BLUE = "#ffffff"
GREEN    = "#31e39a"
GREEN_BG = "#0d4632"
RED      = "#ff5c73"
RED_BG   = "#4a1520"
CURRENT_THEME = "emas"


def apply_theme(key):
    """Set semua warna global sesuai tema pilihan."""
    global BG_TOP, BG_BOT, CARD, CARD_HI, CARD_TOP, BORDER, TXT, MUTED, DIM
    global GOLD, GOLD_HOT, GOLD_DIM, BLUE, CURRENT_THEME
    t = THEMES.get(key) or THEMES["emas"]
    CURRENT_THEME = key if key in THEMES else "emas"
    BG_TOP, BG_BOT = t["top"], t["bot"]
    GOLD, GOLD_HOT, BLUE = t["acc"], t["hot"], t["glow2"]
    GOLD_DIM = mix(BG_BOT, GOLD, 0.32)
    CARD     = mix(BG_BOT, "#ffffff", 0.035)
    CARD_HI  = mix(BG_BOT, "#ffffff", 0.085)
    CARD_TOP = mix(BG_BOT, "#ffffff", 0.125)
    BORDER   = mix(BG_BOT, GOLD, 0.16)
    TXT      = "#f2f4fb"
    MUTED    = mix("#f2f4fb", BG_BOT, 0.52)
    DIM      = mix("#f2f4fb", BG_BOT, 0.70)


G_PANEL = "#241a13"
G_LINE = "#5a4a3c"
G_TXT = "#f5f2ec"
G_ON = "#7ed321"
G_DIM = "#a99e92"


def on_accent():
    """Warna teks di atas tombol accent (dibikin gelap biar kontras)."""
    return mix(BG_TOP, "#000000", 0.62)

_FONT_UI = None
_FONT_MONO = None


def _pick(cands, fallback):
    try:
        fams = set(tkfont.families())
    except Exception:
        fams = set()
    for c in cands:
        if c in fams:
            return c
    return fallback


def ui_font(size=10, bold=False, italic=False):
    global _FONT_UI
    if _FONT_UI is None:
        _FONT_UI = _pick(("Segoe UI Variable Display", "Segoe UI", "Inter",
                          "Roboto", "Noto Sans", "DejaVu Sans", "Helvetica"),
                         "TkDefaultFont")
    return tkfont.Font(family=_FONT_UI, size=size,
                       weight="bold" if bold else "normal",
                       slant="italic" if italic else "roman")


def mono_font(size=12, bold=True):
    global _FONT_MONO
    if _FONT_MONO is None:
        _FONT_MONO = _pick(("Cascadia Mono", "Consolas", "JetBrains Mono",
                            "DejaVu Sans Mono", "Courier New"), "TkFixedFont")
    return tkfont.Font(family=_FONT_MONO, size=size,
                       weight="bold" if bold else "normal")


def sp(text, gap=" "):
    """Kasih jarak antar huruf: 'SPEED' -> 'S P E E D'."""
    return gap.join(text)


# ============================================================================
#  HELPER GAMBAR
# ============================================================================
def rr_pts(x1, y1, x2, y2, r):
    r = max(0, min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def rr(cv, x1, y1, x2, y2, r=12, **kw):
    return cv.create_polygon(rr_pts(x1, y1, x2, y2, r), smooth=True,
                             splinesteps=26, **kw)


def vgrad(cv, x1, y1, x2, y2, c1, c2, steps=64, tags=()):
    """Gradien vertikal pakai garis-garis."""
    h = (y2 - y1) / float(steps)
    for i in range(steps):
        cv.create_rectangle(x1, y1 + i * h, x2, y1 + (i + 1) * h + 1,
                            fill=mix(c1, c2, i / float(steps - 1)),
                            outline="", tags=tags)


def glow(cv, cx, cy, radius, color, bg, layers=40, power=2.4, tags=()):
    """Cahaya lembut (aurora) pakai oval konsentris."""
    ids = []
    for i in range(layers, 0, -1):
        t = i / float(layers)
        r = radius * t
        c = mix(bg, color, (1 - t) ** power * 0.30)
        ids.append(cv.create_oval(cx - r, cy - r * 0.72, cx + r, cy + r * 0.72,
                                  fill=c, outline="", tags=tags))
    return ids


def rr_glow(cv, x1, y1, x2, y2, r, color, bg, layers=10, spread=10, tags=()):
    """Cahaya di sekeliling kotak rounded."""
    ids = []
    for i in range(layers, 0, -1):
        t = i / float(layers)
        pad = spread * t
        c = mix(bg, color, (1 - t) ** 2.2 * 0.30)
        ids.append(rr(cv, x1 - pad, y1 - pad, x2 + pad, y2 + pad, r + pad,
                      fill=c, outline="", tags=tags))
    return ids


# ============================================================================
#  KOMPONEN CANVAS
# ============================================================================
class CvButton:
    """Tombol rounded di atas canvas bersama."""

    _n = 0

    def __init__(self, cv, x1, y1, x2, y2, text, command=None, r=12,
                 fill=CARD_HI, fg=TXT, font=None, accent=False, glow_on=False,
                 bg=BG_BOT, border=None, sub=None):
        CvButton._n += 1
        self.cv, self.tag = cv, "btn%d" % CvButton._n
        self.box = (x1, y1, x2, y2)
        self.r, self.bg = r, bg
        self.command = command
        self.base = GOLD if accent else fill
        self.fgc = on_accent() if accent else fg
        self.border = border
        self.glow_ids = []
        self.glow_on = glow_on
        if glow_on:
            self.glow_ids = rr_glow(cv, x1, y1, x2, y2, r, GOLD, bg,
                                    tags=(self.tag + "g",))
        self.shape = rr(cv, x1, y1, x2, y2, r, fill=self.base,
                        outline=border or self.base, tags=(self.tag,))
        cy = (y1 + y2) / 2
        if sub:
            self.txt = cv.create_text((x1 + x2) / 2, cy - 8, text=text,
                                      fill=self.fgc, font=font or ui_font(8, True),
                                      tags=(self.tag,))
            self.sub = cv.create_text((x1 + x2) / 2, cy + 8, text=sub,
                                      fill=self.fgc, font=ui_font(8),
                                      tags=(self.tag,))
        else:
            self.txt = cv.create_text((x1 + x2) / 2, cy, text=text, fill=self.fgc,
                                      font=font or ui_font(10, True),
                                      tags=(self.tag,))
            self.sub = None
        cv.tag_bind(self.tag, "<Enter>", self._enter)
        cv.tag_bind(self.tag, "<Leave>", self._leave)
        cv.tag_bind(self.tag, "<ButtonPress-1>", self._press)
        cv.tag_bind(self.tag, "<ButtonRelease-1>", self._release)

    def _paint(self, c):
        self.cv.itemconfig(self.shape, fill=c, outline=self.border or c)

    def _enter(self, _=None):
        self._paint(mix(self.base, "#ffffff", 0.13))
        self.cv.config(cursor="hand2")

    def _leave(self, _=None):
        self._paint(self.base)
        self.cv.config(cursor="")

    def _press(self, _=None):
        self._paint(mix(self.base, "#000000", 0.22))

    def _release(self, e=None):
        self._paint(mix(self.base, "#ffffff", 0.13))
        x1, y1, x2, y2 = self.box
        if self.command and x1 <= e.x <= x2 and y1 <= e.y <= y2:
            self.command()

    def set_text(self, t):
        self.cv.itemconfig(self.txt, text=t)

    def set_style(self, fill, fg, show_glow=None):
        self.base, self.fgc = fill, fg
        self._paint(fill)
        self.cv.itemconfig(self.txt, fill=fg)
        if self.sub:
            self.cv.itemconfig(self.sub, fill=fg)
        if show_glow is not None:
            st = "normal" if show_glow else "hidden"
            for i in self.glow_ids:
                self.cv.itemconfig(i, state=st)


class CvSlider:
    """Slider gold dengan knob bercahaya."""

    def __init__(self, cv, x1, x2, y, lo, hi, value, command=None):
        self.cv, self.x1, self.x2, self.y = cv, x1, x2, y
        self.lo, self.hi, self.command = lo, hi, command
        CvSlider._n = getattr(CvSlider, "_n", 0) + 1
        self.tag = "sld%d" % CvSlider._n
        cv.create_line(x1, y, x2, y, fill=CARD_HI, width=6, capstyle="round",
                       tags=(self.tag,))
        self.fill = cv.create_line(x1, y, x1 + 1, y, fill=GOLD, width=6,
                                   capstyle="round", tags=(self.tag,))
        self.halo = cv.create_oval(0, 0, 0, 0, fill=GOLD_DIM, outline="",
                                   tags=(self.tag,))
        self.knob = cv.create_oval(0, 0, 0, 0, fill=GOLD, outline=TXT, width=0,
                                   tags=(self.tag,))
        # area klik lebih lebar
        self.hit = cv.create_rectangle(x1 - 6, y - 14, x2 + 6, y + 14,
                                       fill="", outline="", tags=(self.tag,))
        cv.tag_bind(self.tag, "<Button-1>", self._drag)
        cv.tag_bind(self.tag, "<B1-Motion>", self._drag)
        cv.tag_bind(self.tag, "<Enter>",
                    lambda e: (cv.itemconfig(self.knob, width=2),
                               cv.config(cursor="hand2")))
        cv.tag_bind(self.tag, "<Leave>",
                    lambda e: (cv.itemconfig(self.knob, width=0),
                               cv.config(cursor="")))
        self.set(value)

    def set(self, v, fire=False):
        v = max(self.lo, min(self.hi, int(round(v))))
        self.value = v
        t = (v - self.lo) / float(self.hi - self.lo)
        x = self.x1 + t * (self.x2 - self.x1)
        self.cv.coords(self.fill, self.x1, self.y, max(self.x1 + 1, x), self.y)
        self.cv.coords(self.halo, x - 13, self.y - 13, x + 13, self.y + 13)
        self.cv.coords(self.knob, x - 8, self.y - 8, x + 8, self.y + 8)
        if fire and self.command:
            self.command(v)

    def _drag(self, e):
        t = (e.x - self.x1) / float(self.x2 - self.x1)
        self.set(self.lo + t * (self.hi - self.lo), fire=True)


class CvSegment:
    """Segmented control dengan indikator geser."""

    _n = 0

    def __init__(self, cv, x1, y1, x2, y2, options, value, command=None):
        CvSegment._n += 1
        self.cv, self.command = cv, command
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.options = options
        self.seg = (x2 - x1) / len(options)
        self.tag = "seg%d" % CvSegment._n
        rr(cv, x1, y1, x2, y2, 11, fill=CARD_HI, outline=CARD_HI, tags=(self.tag,))
        self.ind = rr(cv, x1 + 3, y1 + 3, x1 + self.seg - 3, y2 - 3, 9,
                      fill=GOLD, outline=GOLD, tags=(self.tag,))
        self.texts = []
        for i, (lbl, _v) in enumerate(options):
            self.texts.append(cv.create_text(x1 + self.seg * (i + 0.5),
                                             (y1 + y2) / 2, text=lbl,
                                             fill=MUTED, font=ui_font(9, True),
                                             tags=(self.tag,)))
        cv.tag_bind(self.tag, "<Button-1>", self._click)
        cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))
        idx = [v for _l, v in options].index(value) if value in [v for _l, v in options] else 0
        self.cur = self.target = x1 + idx * self.seg
        self._apply(idx)
        self._anim()

    def _click(self, e):
        idx = int((e.x - self.x1) // self.seg)
        idx = max(0, min(len(self.options) - 1, idx))
        self.target = self.x1 + idx * self.seg
        self._apply(idx)
        if self.command:
            self.command(self.options[idx][1])

    def _apply(self, idx):
        for i, t in enumerate(self.texts):
            self.cv.itemconfig(t, fill=on_accent() if i == idx else MUTED)

    def _anim(self):
        try:
            if not self.cv.winfo_exists():
                return
        except Exception:
            return
        if abs(self.cur - self.target) > 0.4:
            self.cur += (self.target - self.cur) * 0.32
            self.cv.coords(self.ind, *rr_pts(self.cur + 3, self.y1 + 3,
                                             self.cur + self.seg - 3,
                                             self.y2 - 3, 9))
        self.cv.after(16, self._anim)


# ===========================================================================
#  WIDGET GAYA macOS  (dipakai LAYOUT = "macos")
# ===========================================================================
class CvSwitch:
    """Toggle switch ala macOS: pil kecil + knob yang geser."""

    def __init__(self, cv, x2, cy, value, command=None, w=44, h=25):
        self.cv, self.cmd = cv, command
        self.val = bool(value)
        self.x1, self.x2 = x2 - w, x2
        self.y1, self.y2 = cy - h / 2, cy + h / 2
        self.h = h
        self.tag = "sw%d" % id(self)
        self.bg = rr(cv, self.x1, self.y1, self.x2, self.y2, h / 2,
                     fill=GOLD if self.val else mix(CARD_HI, "#ffffff", 0.06),
                     outline="", tags=(self.tag,))
        k = h - 6
        self.knob = cv.create_oval(0, 0, 0, 0, fill="#ffffff", outline="",
                                   tags=(self.tag,))
        self._place(k)
        cv.tag_bind(self.tag, "<ButtonRelease-1>", self._click)
        cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))

    def _place(self, k):
        cx = (self.x2 - 3 - k / 2) if self.val else (self.x1 + 3 + k / 2)
        cy = (self.y1 + self.y2) / 2
        self.cv.coords(self.knob, cx - k / 2, cy - k / 2, cx + k / 2, cy + k / 2)

    def _click(self, _=None):
        if self.cmd:
            self.cmd(not self.val)

    def set(self, value):
        self.val = bool(value)
        self.cv.itemconfig(self.bg, fill=GOLD if self.val
                           else mix(CARD_HI, "#ffffff", 0.06))
        self._place(self.h - 6)


class CvPopup:
    """Popup button ala macOS: nilai + panah dobel, klik = menu turun."""

    def __init__(self, cv, app, x2, cy, options, value, command=None, minw=96,
                 flat=False, w=None):
        self.cv, self.app, self.cmd = cv, app, command
        self.options = options            # [(label, value), ...]
        self.value = value
        self.flat = flat
        f = ui_font(12) if flat else ui_font(9)
        w = w or max(minw, max(f.measure(o[0]) for o in options) + 60)
        self.x1, self.x2 = x2 - w, x2
        self.y1, self.y2 = (cy - 22, cy + 22) if flat else (cy - 14, cy + 14)
        self.tag = "pop%d" % id(self)
        if flat:
            rr(cv, self.x1, self.y1, self.x2, self.y2, 6,
               fill=mix(G_PANEL, "#000000", 0.30), outline=G_LINE, width=1,
               tags=(self.tag,))
            self.txt = cv.create_text(self.x1 + 18, cy, anchor="w",
                                      text=self._label(), fill=G_TXT, font=f,
                                      tags=(self.tag,))
            cv.create_line(self.x2 - 30, cy - 4, self.x2 - 22, cy + 4,
                           self.x2 - 14, cy - 4, fill=G_TXT, width=2,
                           capstyle="round", joinstyle="round", tags=(self.tag,))
            cv.tag_bind(self.tag, "<ButtonRelease-1>", self._open)
            cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))
            return
        rr(cv, self.x1, self.y1, self.x2, self.y2, 6,
           fill=mix(CARD_HI, "#ffffff", 0.05), outline="", tags=(self.tag,))
        self.txt = cv.create_text(self.x2 - 34, cy, anchor="e", text=self._label(),
                                  fill=TXT, font=f, tags=(self.tag,))
        # kotak panah kecil warna aksen
        ax = self.x2 - 24
        rr(cv, ax, cy - 11, ax + 18, cy + 11, 4, fill=GOLD, outline="",
           tags=(self.tag,))
        c = on_accent()
        cv.create_polygon(ax + 9, cy - 7, ax + 5, cy - 2.5, ax + 13, cy - 2.5,
                          fill=c, outline="", tags=(self.tag,))
        cv.create_polygon(ax + 9, cy + 7, ax + 5, cy + 2.5, ax + 13, cy + 2.5,
                          fill=c, outline="", tags=(self.tag,))
        cv.tag_bind(self.tag, "<ButtonRelease-1>", self._open)
        cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))

    def _label(self):
        for o in self.options:
            if o[1] == self.value:
                return o[0]
        return str(self.value)

    def _open(self, _=None):
        self.app.close_menu()
        cv = self.cv
        f = ui_font(12) if self.flat else ui_font(9)
        ih = 36 if self.flat else 26
        w = max(self.x2 - self.x1, max(f.measure(o[0]) for o in self.options) + 62)
        x2 = self.x2
        x1 = x2 - w
        # menu muncul sejajar item yang lagi kepilih (kebiasaan macOS)
        idx = next((i for i, o in enumerate(self.options) if o[1] == self.value), 0)
        y1 = (self.y1 + self.y2) / 2 - 13 - idx * ih - 5
        y2 = y1 + len(self.options) * ih + 10
        maxy = self.app.win_h - 8
        if y2 > maxy:
            y1 -= (y2 - maxy)
            y2 = maxy
        if y1 < self.app.Y(52):
            y1 = self.app.Y(52)
            y2 = y1 + len(self.options) * ih + 10
        t = "menu"
        m_bg = mix(G_PANEL, "#000000", 0.12) if self.flat \
            else mix(BG_TOP, "#ffffff", 0.16)
        m_bd = G_LINE if self.flat else mix(BG_TOP, "#ffffff", 0.24)
        m_fg = G_TXT if self.flat else TXT
        m_hi = G_ON if self.flat else GOLD
        m_hf = mix("#000000", G_ON, 0.25) if self.flat else on_accent()
        rr(cv, x1 + 2, y1 + 3, x2 + 2, y2 + 3, 8,
           fill=mix(BG_TOP, "#000000", 0.5), outline="", tags=(t,))
        rr(cv, x1, y1, x2, y2, 8, fill=m_bg, outline=m_bd, tags=(t,))
        for i, o in enumerate(self.options):
            iy = y1 + 5 + i * ih
            sub = "%s_i%d" % (t, i)
            box = rr(cv, x1 + 4, iy, x2 - 4, iy + ih, 5, fill="", outline="",
                     tags=(t, sub))
            if o[1] == self.value:
                cv.create_text(x1 + 18, iy + ih / 2, text="✓", fill=m_fg,
                               font=ui_font(9, True), tags=(t, sub))
            lbl = cv.create_text(x1 + 32, iy + ih / 2, anchor="w", text=o[0],
                                 fill=m_fg, font=f, tags=(t, sub))
            if len(o) > 2 and o[2]:      # bulatan warna (buat pilihan tema)
                cv.create_oval(x2 - 26, iy + ih / 2 - 5, x2 - 16, iy + ih / 2 + 5,
                               fill=o[2], outline="", tags=(t, sub))
            cv.tag_bind(sub, "<Enter>", lambda e, b=box, l=lbl: (
                cv.itemconfig(b, fill=m_hi), cv.itemconfig(l, fill=m_hf),
                cv.config(cursor="hand2")))
            cv.tag_bind(sub, "<Leave>", lambda e, b=box, l=lbl: (
                cv.itemconfig(b, fill=""), cv.itemconfig(l, fill=m_fg),
                cv.config(cursor="")))
            cv.tag_bind(sub, "<ButtonRelease-1>",
                        lambda e, v=o[1]: self._choose(v))
        self.app.menu_open = True
        self.app._menu_time = time.time()

    def _choose(self, v):
        self.app.close_menu()
        self.value = v
        self.cv.itemconfig(self.txt, text=self._label())
        if self.cmd:
            self.app.after(1, lambda: self.cmd(v))

# ===========================================================================
#  WIDGET GAYA GAME MENU  (dipakai LAYOUT = "game")
# ===========================================================================
class CvToggle:
    """Saklar kotak ala menu game: blok geser kiri (mati) / kanan (nyala)."""

    def __init__(self, cv, x2, cy, value, command=None, w=80, h=36):
        self.cv, self.cmd = cv, command
        self.val = bool(value)
        self.x1, self.x2 = x2 - w, x2
        self.y1, self.y2 = cy - h / 2, cy + h / 2
        self.tag = "tg%d" % id(self)
        rr(cv, self.x1, self.y1, self.x2, self.y2, 8,
           fill=mix(G_PANEL, "#000000", 0.30), outline=G_LINE, width=2,
           tags=(self.tag,))
        self.knob = rr(cv, 0, 0, 1, 1, 6, fill="#ffffff", outline="",
                       tags=(self.tag,))
        self._place()
        cv.tag_bind(self.tag, "<ButtonRelease-1>",
                    lambda e: self.cmd and self.cmd(not self.val))
        cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))

    def _place(self):
        w = (self.x2 - self.x1) / 2 - 3
        x = (self.x2 - 4 - w) if self.val else (self.x1 + 4)
        pts = rr_pts(x, self.y1 + 4, x + w, self.y2 - 4, 6)
        self.cv.coords(self.knob, *pts)
        self.cv.itemconfig(self.knob,
                           fill=G_ON if self.val else mix("#ffffff", G_PANEL, 0.42))

    def set(self, v):
        self.val = bool(v)
        self._place()


class CvRadio:
    """Kotak pilihan tunggal (low / medium / high)."""

    def __init__(self, cv, cx, cy, value, selected, command=None, s=30):
        self.cv, self.val, self.cmd = cv, value, command
        self.tag = "rd%d" % id(self)
        rr(cv, cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2, 7, fill="",
           outline="#ffffff", width=2, tags=(self.tag,))
        cv.create_rectangle(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2,
                            fill="", outline="", tags=(self.tag,))
        self.dot = rr(cv, cx - 8, cy - 8, cx + 8, cy + 8, 3,
                      fill="#ffffff" if selected else "", outline="",
                      tags=(self.tag,))
        cv.tag_bind(self.tag, "<ButtonRelease-1>",
                    lambda e: self.cmd and self.cmd(self.val))
        cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))


class CvCheck:
    """Kotak centang."""

    def __init__(self, cv, x, cy, text, value, command=None, s=32):
        self.cv, self.cmd = cv, command
        self.val = bool(value)
        self.tag = "ck%d" % id(self)
        rr(cv, x, cy - s / 2, x + s, cy + s / 2, 7, fill="", outline="#ffffff",
           width=2, tags=(self.tag,))
        self.mark = cv.create_line(x + 7, cy, x + 13, cy + 7, x + 25, cy - 8,
                                   fill="#ffffff" if self.val else "",
                                   width=3, capstyle="round",
                                   joinstyle="round", tags=(self.tag,))
        cv.create_text(x + s + 16, cy, anchor="w", text=text, fill=G_TXT,
                       font=ui_font(12), tags=(self.tag,))
        cv.tag_bind(self.tag, "<ButtonRelease-1>",
                    lambda e: self.cmd and self.cmd(not self.val))
        cv.tag_bind(self.tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(self.tag, "<Leave>", lambda e: cv.config(cursor=""))


class CvGSlider:
    """Slider ala game: garis hijau + gagang kotak putih."""

    def __init__(self, cv, x1, x2, cy, lo, hi, value, command=None):
        self.cv, self.cmd = cv, command
        self.x1, self.x2, self.cy = x1, x2, cy
        self.lo, self.hi = lo, hi
        self.val = max(lo, min(hi, value))
        self.tag = "gs%d" % id(self)
        rr(cv, x1, cy - 4, x2, cy + 4, 4, fill=mix("#ffffff", G_PANEL, 0.55),
           outline="", tags=(self.tag,))
        self.fill = rr(cv, x1, cy - 4, x1 + 1, cy + 4, 4, fill=G_ON,
                       outline="", tags=(self.tag,))
        self.knob = rr(cv, 0, 0, 1, 1, 4, fill="#ffffff",
                       outline=mix("#ffffff", "#000000", 0.35), tags=(self.tag,))
        cv.create_rectangle(x1 - 6, cy - 18, x2 + 6, cy + 18, fill="",
                            outline="", tags=(self.tag,))
        self._paint()
        for ev in ("<Button-1>", "<B1-Motion>"):
            cv.tag_bind(self.tag, ev, self._drag)

    def _paint(self):
        t = (self.val - self.lo) / float(self.hi - self.lo)
        x = self.x1 + t * (self.x2 - self.x1)
        self.cv.coords(self.fill, *rr_pts(self.x1, self.cy - 4, max(self.x1 + 1, x),
                                          self.cy + 4, 4))
        self.cv.coords(self.knob, *rr_pts(x - 13, self.cy - 16, x + 13,
                                          self.cy + 16, 4))

    def _drag(self, e):
        t = (e.x - self.x1) / float(self.x2 - self.x1)
        self.val = int(round(self.lo + max(0.0, min(1.0, t)) * (self.hi - self.lo)))
        self._paint()
        if self.cmd:
            self.cmd(self.val)

    def set(self, v):
        self.val = max(self.lo, min(self.hi, int(v)))
        self._paint()

class CvKeyCap:
    """Keycap 3D yang bercahaya saat aktif."""

    def __init__(self, cv, cx, cy, letter, size=58, bg=BG_BOT):
        self.cv, self.bg = cv, bg
        h = size / 2
        self.glow_ids = rr_glow(cv, cx - h, cy - h, cx + h, cy + h, 14, GOLD,
                                bg, layers=7, spread=11)
        for i in self.glow_ids:
            cv.itemconfig(i, state="hidden")
        self.body = rr(cv, cx - h, cy - h, cx + h, cy + h, 14, fill=CARD_HI,
                       outline=BORDER)
        self.top = rr(cv, cx - h + 5, cy - h + 4, cx + h - 5, cy - 2, 9,
                      fill=CARD_TOP, outline="")
        self.txt = cv.create_text(cx, cy + 2, text=letter, fill=MUTED,
                                  font=ui_font(18, True))
        self.level = 0.0

    def update(self, active):
        self.level = 1.0 if active else max(0.0, self.level - 0.14)
        L = self.level
        self.cv.itemconfig(self.body, fill=mix(CARD_HI, GOLD, L),
                           outline=mix(BORDER, GOLD_HOT, L))
        self.cv.itemconfig(self.top, fill=mix(CARD_TOP, mix(GOLD, "#ffffff", 0.5), L))
        self.cv.itemconfig(self.txt, fill=mix(MUTED, on_accent(), L))
        st = "normal" if L > 0.15 else "hidden"
        for i in self.glow_ids:
            self.cv.itemconfig(i, state=st)


class CvPill:
    """Status pill ON/OFF dengan titik berdenyut."""

    def __init__(self, cv, cx, cy, w=178, h=34):
        self.cv, self.cx, self.cy, self.w, self.h = cv, cx, cy, w, h
        x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
        self.shape = rr(cv, x1, y1, x2, y2, h / 2, fill=mix(BG_BOT, GOLD, 0.22),
                        outline=GREEN_BG)
        self.dot = cv.create_oval(0, 0, 0, 0, fill=GOLD, outline="")
        self.txt = cv.create_text(cx + 8, cy, text="AKTIF (ON)", fill=GOLD,
                                  font=ui_font(11, True))
        self.dot_x = x1 + 22
        self.on = True
        self.phase = 0.0

    def set_state(self, on):
        self.on = on
        c, bgc, t = (GREEN, GREEN_BG, "AKTIF (ON)") if on else (RED, RED_BG, "MATI (OFF)")
        self.cv.itemconfig(self.shape, fill=bgc, outline=bgc)
        self.cv.itemconfig(self.dot, fill=c)
        self.cv.itemconfig(self.txt, text=t, fill=c)

    def tick(self):
        self.phase += 0.14
        s = 4.2 + math.sin(self.phase) * 1.7
        self.cv.coords(self.dot, self.dot_x - s, self.cy - s,
                       self.dot_x + s, self.cy + s)


class CvVisualizer:
    """Bar visualizer aktivitas tombol (kayak equalizer)."""

    def __init__(self, cv, x1, y1, x2, y2, n=52):
        self.cv, self.y1, self.y2 = cv, y1, y2
        self.n = n
        self.vals = [0.0] * n
        gap = 2.0
        bw = ((x2 - x1) - gap * (n - 1)) / n
        self.bars = []
        for i in range(n):
            bx = x1 + i * (bw + gap)
            self.bars.append(cv.create_rectangle(bx, y2 - 3, bx + bw, y2,
                                                 fill=CARD_HI, outline=""))

    def push(self, v):
        self.vals.pop(0)
        self.vals.append(v)
        H = self.y2 - self.y1
        for i, val in enumerate(self.vals):
            x1c, _, x2c, _ = self.cv.coords(self.bars[i])
            hgt = max(3.0, val * H)
            self.cv.coords(self.bars[i], x1c, self.y2 - hgt, x2c, self.y2)
            if val < 0.05:
                c = mix(CARD_HI, GOLD, 0.10)
            else:
                c = mix(GOLD_HOT, GOLD, val)
            self.cv.itemconfig(self.bars[i], fill=c)


# ============================================================================
#  IKON (vector kecil)
# ============================================================================
def icon_keyboard(cv, x, y, c=GOLD):
    rr(cv, x, y - 5, x + 16, y + 6, 3, fill="", outline=c)
    for i in range(3):
        cv.create_line(x + 3 + i * 4, y - 1, x + 4 + i * 4, y - 1, fill=c, width=2)
    cv.create_line(x + 5, y + 3, x + 11, y + 3, fill=c, width=2)


def icon_bolt(cv, x, y, c=GOLD):
    cv.create_polygon(x + 9, y - 7, x + 3, y + 1, x + 7, y + 1, x + 5, y + 8,
                      x + 12, y - 1, x + 8, y - 1, fill=c, outline="")


def icon_switch(cv, x, y, c=GOLD):
    rr(cv, x, y - 5, x + 17, y + 5, 5, fill="", outline=c)
    cv.create_oval(x + 9, y - 3, x + 15, y + 3, fill=c, outline="")


def icon_moon(cv, cx, cy, r=10, c=GOLD, bg=BG_TOP):
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=c, outline="")
    cv.create_oval(cx - r + 5, cy - r - 3, cx + r + 5, cy + r - 3,
                   fill=bg, outline="")


# ============================================================================
#  APP
# ============================================================================
class App(tk.Tk):
    W, H = 940, 580                 # layout "pro"
    WPRO, HPRO = 940, 580
    WMIN, HMIN = 404, 620           # layout "minimal"
    WMAC, HMAC = 880, 684           # layout "macos"
    WGAME, HGAME = 726, 742         # layout "game" (background nyala)
    WGAME0, HGAME0 = 566, 666       # layout "game" (background mati)
    SW = 236                        # lebar sidebar macOS
    LW = 368          # lebar panel kiri
    MW, MH = 304, 74
    MAX_ACT = 7

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        engine.on_state_change = lambda: self.after(0, self.refresh)

        apply_theme(engine.cfg.get("theme", "emas"))
        self.mini = False
        self.capture_for = "hotkey"
        self.tab = "macro"
        self.gtab = "macro"
        self.sel = None
        global LAYOUT, SHOW_BG
        LAYOUT = engine.cfg.get("layout", LAYOUT)
        SHOW_BG = bool(engine.cfg.get("show_bg", True))
        global UPDATE_URL
        UPDATE_URL = engine.cfg.get("update_url", "")
        self.minimal = LAYOUT == "minimal"
        self.macos = LAYOUT == "macos"
        self.game = LAYOUT == "game"
        self.page = "macro"
        self.menu_open = False
        self.sw_power = None
        self.mac_rows = []
        if self.game:
            self.W, self.H = self._game_size()
        elif self.macos:
            self.W, self.H = self.WMAC, self.HMAC
        elif self.minimal:
            self.W, self.H = self.WMIN, self.HMIN
        self.topmost = ALWAYS_ON_TOP
        self.title("Moonwalk Macro")
        self.configure(bg=BG_TOP)
        self.custom_bar = USE_CUSTOM_TITLEBAR
        h = self.H if self.custom_bar else self.H - 46
        self.geometry("%dx%d" % (self.W, h))
        self.resizable(False, False)
        if ALWAYS_ON_TOP:
            self.attributes("-topmost", True)
        if self.custom_bar:
            try:
                self.overrideredirect(True)
                show_in_taskbar(self)
            except Exception:
                self.custom_bar = False
        self._center(h)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass

        self.win_h = h
        self.cv = None
        self.e_hotkey = None
        self._build_ui()

        round_window_corners(self)
        self._fade_in()
        self._tick()

    def _build_ui(self):
        """Gambar ulang seluruh UI (dipakai juga waktu ganti tema)."""
        if self.e_hotkey is not None:
            try:
                self.e_hotkey.destroy()
            except Exception:
                pass
        if self.cv is not None:
            try:
                self.cv.destroy()
            except Exception:
                pass
        h = self.win_h
        self.configure(bg=BG_TOP)
        self.cv = tk.Canvas(self, width=self.W, height=h, bg=BG_TOP,
                            highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)

        self.top = 0 if self.custom_bar else -46
        if not self.mini:
            self._draw_background(h)
            if self.custom_bar:
                self._draw_titlebar()
        if self.mini:
            self._build_mini()
            self.refresh()
            return
        if self.game:
            self._draw_game()
        elif self.macos:
            self._draw_mac()
        elif self.minimal:
            self._draw_min()
        else:
            self._draw_shell()
            self._draw_tabs()
            self._draw_left()
            self._draw_right()
        self.refresh()
        self._resync_pointer()

    def _resync_pointer(self):
        """Kasih tau Tk posisi kursor di canvas yang baru.

        Waktu canvas lama dihapus dan diganti yang baru, Tk masih nyimpen
        catatan lama soal item mana yang ada di bawah kursor. Kalau kursornya
        nggak digerakin, klik berikutnya bisa nggak kena apa-apa — makanya
        ganti tema cuma jalan sekali. Motion palsu ini yang nyegerin catatan itu.
        """
        try:
            x = self.winfo_pointerx() - self.cv.winfo_rootx()
            y = self.winfo_pointery() - self.cv.winfo_rooty()
            if 0 <= x < self.W and 0 <= y < self.win_h:
                self.cv.event_generate("<Motion>", x=x, y=y)
        except Exception:
            pass

    def _resize_mini(self):
        self.MW, self.MH = self._mini_size()
        self.win_h = self.MH
        self.geometry("%dx%d" % (self.MW, self.MH))

    def _set_theme(self, key):
        apply_theme(key)
        self.engine.set_theme(key)
        if self.mini:
            self._resize_mini()          # tiap tema beda bentuk & ukuran
        self._build_ui()

    # -------------------------------------------------------------- utility
    def _center(self, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.W) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _fade_in(self, a=0.0):
        try:
            self.attributes("-alpha", min(1.0, a))
            if a < 1.0:
                self.after(12, lambda: self._fade_in(a + 0.09))
        except Exception:
            pass

    def Y(self, v):
        return v + self.top

    def bg_at(self, y):
        """Warna background pada posisi y (buat glow yang nyatu)."""
        return mix(BG_TOP, BG_BOT, max(0.0, min(1.0, y / float(self.H))))

    # ----------------------------------------------------------- background
    def _draw_background(self, h):
        if self.game:
            self._game_palette()
            self._game_bg(h)
            return
        if self.macos:
            self._mac_colors()
            self.cv.create_rectangle(0, 0, self.W, h, fill=self.PANE,
                                     outline="")
            return
        if self.minimal:
            self.cv.create_rectangle(0, 0, self.W, h, fill=BG_TOP, outline="")
            self.cv.create_rectangle(0, 0, self.W, self.Y(46),
                                     fill=mix(BG_TOP, "#ffffff", 0.03),
                                     outline="")
            return
        vgrad(self.cv, 0, 0, self.W, h, BG_TOP, BG_BOT, steps=96)
        glow(self.cv, self.LW + 260, self.Y(120), 340, GOLD,
             self.bg_at(self.Y(120)), layers=44, power=2.9)
        glow(self.cv, self.W - 40, h - 30, 240, BLUE, self.bg_at(h - 30),
             layers=40, power=3.2)

    # ------------------------------------------------------------- titlebar
    def _draw_titlebar(self):
        if self.game:
            return          # judul udah nempel di panel dialog-nya
        if self.macos:
            self._draw_mac_bar()
            return
        cv = self.cv
        cv.create_rectangle(0, 0, self.W, 46, fill="#0e0e18", outline="",
                            tags=("bar",))
        cv.create_line(0, 46, self.W, 46, fill="#1c1c2b")
        icon_moon(cv, 26, 23, 9, GOLD, "#0e0e18")
        f1 = ui_font(9, True)
        x = 46
        cv.create_text(x, 23, text="MOONWALK", anchor="w", fill=TXT, font=f1,
                       tags=("bar",))
        x += f1.measure("MOONWALK ")
        cv.create_text(x, 23, text="MACRO", anchor="w", fill=GOLD, font=f1,
                       tags=("bar",))
        x += f1.measure("MACRO  ")
        cv.create_text(x, 24, text="v" + VERSION, anchor="w", fill=DIM, font=ui_font(8),
                       tags=("bar",))

        for i, (txt, cmd, hov, tg) in enumerate(
                (("✕", self.quit_app, RED, "wbx"), ("—", self.minimize, CARD_HI, "wbm"),
                 ("⤡", self.toggle_mini, CARD_HI, "wbc"))):
            x2 = self.W - i * 44
            x1 = x2 - 44
            box = cv.create_rectangle(x1, 0, x2, 46, fill="#0e0e18", outline="",
                                      tags=(tg,))
            cv.create_text((x1 + x2) / 2, 23, text=txt, fill=MUTED,
                           font=ui_font(11), tags=(tg,))
            cv.tag_bind(tg, "<Enter>", lambda e, b=box, c=hov: (
                cv.itemconfig(b, fill=c), cv.config(cursor="hand2")))
            cv.tag_bind(tg, "<Leave>", lambda e, b=box: (
                cv.itemconfig(b, fill="#0e0e18"), cv.config(cursor="")))
            cv.tag_bind(tg, "<ButtonRelease-1>", lambda e, c=cmd: c())

        cv.tag_bind("bar", "<Button-1>", self._drag_start)
        cv.tag_bind("bar", "<B1-Motion>", self._drag_move)

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    def minimize(self):
        """Minimize tanpa kedip.

        Cara lama (overrideredirect off -> iconify -> on lagi) bikin jendela
        kedip-kedip. Di Windows kita minimize langsung lewat ShowWindow,
        jadi statusnya nggak diutak-atik sama sekali.
        """
        if IS_WINDOWS:
            try:
                hwnd = (ctypes.windll.user32.GetParent(self.winfo_id())
                        or self.winfo_id())
                ctypes.windll.user32.ShowWindow(hwnd, 6)   # SW_MINIMIZE
                return
            except Exception:
                pass
        try:
            self.overrideredirect(False)
            self.iconify()
            self.bind("<Map>", self._on_restore)
        except Exception:
            pass

    def _on_restore(self, _=None):
        self.unbind("<Map>")

        def back():
            try:
                self.overrideredirect(True)
                show_in_taskbar(self)
                round_window_corners(self)
            except Exception:
                pass
        self.after(10, back)

    # ------------------------------------------------------------------ UI
    def _card(self, y1, y2, title, icon_fn=None):
        cv = self.cv
        x1, x2 = 22, self.W - 22
        rr(cv, x1, y1, x2, y2, 16, fill=CARD, outline=BORDER)
        rr(cv, x1 + 1, y1 + 1, x2 - 1, y1 + 26, 15, fill=mix(CARD, "#ffffff", 0.025),
           outline="")
        rr(cv, x1 + 18, y1 + 15, x1 + 21, y1 + 29, 1.5, fill=GOLD, outline=GOLD)
        cv.create_text(x1 + 31, y1 + 22, text=sp(title), anchor="w", fill=MUTED,
                       font=ui_font(8, True))
        return x1, x2

    # ======================================================================
    #  SHELL: panel kiri + garis pemisah
    # ======================================================================
    def _draw_shell(self):
        cv = self.cv
        cv.create_rectangle(0, self.Y(46), self.LW, self.win_h,
                            fill=mix(BG_TOP, "#000000", 0.30), outline="")
        cv.create_line(self.LW, self.Y(46), self.LW, self.win_h, fill=BORDER)

    def _draw_tabs(self):
        cv = self.cv
        tabs = [("MACRO", "macro"), ("TAMPILAN", "tema")]
        x = 16
        for label, key in tabs:
            f = ui_font(9, True)
            w = f.measure(label) + 30
            act = self.tab == key
            tg = "tab_" + key
            cv.create_rectangle(x, self.Y(58), x + w, self.Y(88), fill="",
                                outline="", tags=(tg,))
            cv.create_text(x + w / 2, self.Y(72), text=label,
                           fill=GOLD if act else MUTED, font=f, tags=(tg,))
            if act:
                rr(cv, x + 8, self.Y(86), x + w - 8, self.Y(89), 1.5,
                   fill=GOLD, outline=GOLD)
            cv.tag_bind(tg, "<Button-1>", lambda e, k=key: self._set_tab(k))
            cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
            x += w + 6

    def _set_tab(self, key):
        self.tab = key
        self._build_ui()

    def _panel(self, x1, y1, x2, y2, title, right_text=None):
        cv = self.cv
        rr(cv, x1, y1, x2, y2, 14, fill=CARD, outline=BORDER)
        rr(cv, x1 + 14, y1 + 14, x1 + 17, y1 + 28, 1.5, fill=GOLD, outline=GOLD)
        cv.create_text(x1 + 27, y1 + 21, text=sp(title), anchor="w", fill=MUTED,
                       font=ui_font(8, True))
        if right_text:
            cv.create_text(x2 - 14, y1 + 21, text=right_text, anchor="e",
                           fill=DIM, font=ui_font(7))
        return x1, x2

    # ======================================================================
    #  PANEL KIRI
    # ======================================================================
    def _draw_left(self):
        if self.tab == "macro":
            self._left_macro()
        else:
            self._left_tema()
        self._left_footer()

    def _left_macro(self):
        cv = self.cv
        x1, x2 = self._panel(16, self.Y(100), 352, self.Y(260), "TRIGGER")

        cv.create_text(x1 + 16, self.Y(142), anchor="w", text="Tombol pemicu",
                       fill=DIM, font=ui_font(8))
        fy = self.Y(154)
        rr(cv, x1 + 16, fy, x1 + 238, fy + 34, 10, fill=CARD_HI, outline=BORDER)
        self.var_hotkey = tk.StringVar(value=self.engine.cfg["hotkey"])
        self.e_hotkey = tk.Entry(self, textvariable=self.var_hotkey, bg=CARD_HI,
                                 fg=TXT, relief="flat", font=ui_font(10, True),
                                 insertbackground=GOLD, justify="center",
                                 highlightthickness=0, bd=0)
        cv.create_window((x1 + 16 + x1 + 238) / 2, fy + 17, window=self.e_hotkey,
                         width=200, height=22)
        self.btn_set = CvButton(cv, x1 + 246, fy, x2 - 16, fy + 34, "SET",
                                self.set_hotkey, r=10, accent=True, bg=CARD,
                                font=ui_font(9, True))

        cv.create_text(x1 + 16, self.Y(204), anchor="w", text="Cara kerja",
                       fill=DIM, font=ui_font(8))
        self.seg = CvSegment(cv, x1 + 16, self.Y(216), x2 - 16, self.Y(250),
                             [("TAHAN", "HOLD"), ("TOGGLE", "TOGGLE")],
                             self.engine.mode, command=self._on_mode)

        # ---- speed & jitter ----
        y1, y2 = self.Y(272), self.Y(452)
        x1, x2 = self._panel(16, y1, 352, y2, "KECEPATAN")
        self.lbl_speed = cv.create_text(x2 - 14, y1 + 21, anchor="e",
                                        text="35 ms", fill=GOLD,
                                        font=mono_font(14, True))
        self.slider = CvSlider(cv, x1 + 26, x2 - 26, y1 + 54, 5, 150,
                               int(self.engine.cfg["speed"]),
                               command=lambda v: self._set_speed(v, True))
        presets = [("LAMBAT", 60), ("NORMAL", 35), ("CEPAT", 20), ("GILA", 10)]
        self.chips = []
        cw = (x2 - x1 - 32 - 3 * 7) / 4.0
        for i, (name, val) in enumerate(presets):
            bx = x1 + 16 + i * (cw + 7)
            b = CvButton(cv, bx, y1 + 72, bx + cw, y1 + 108, name,
                         command=lambda v=val: self._set_speed(v), r=9,
                         fill=CARD_HI, fg=MUTED, bg=CARD, sub="%d ms" % val,
                         font=ui_font(7, True))
            b.preset = val
            self.chips.append(b)

        cv.create_line(x1 + 16, y1 + 122, x2 - 16, y1 + 122, fill=BORDER)
        cv.create_text(x1 + 16, y1 + 140, anchor="w", text=sp("JITTER"),
                       fill=MUTED, font=ui_font(8, True))
        cv.create_text(x1 + 16, y1 + 158, anchor="w", text="delay diacak",
                       fill=DIM, font=ui_font(7))
        self.jchips = []
        jw = 52
        for i, val in enumerate((0, 10, 20, 30)):
            bx = x2 - 16 - (4 - i) * (jw + 6) + 6
            b = CvButton(cv, bx, y1 + 134, bx + jw, y1 + 164,
                         "OFF" if val == 0 else "%d%%" % val,
                         command=lambda v=val: self._set_jitter(v), r=8,
                         fill=CARD_HI, fg=MUTED, bg=CARD, font=ui_font(8, True))
            b.preset = val
            self.jchips.append(b)

    def _left_tema(self):
        cv = self.cv
        x1, x2 = self._panel(16, self.Y(100), 352, self.Y(230), "TEMA WARNA")
        sw = (x2 - x1 - 32 - 4 * 8) / 5.0
        for i, key in enumerate(THEME_ORDER):
            th = THEMES[key]
            bx = x1 + 16 + i * (sw + 8)
            act = key == CURRENT_THEME
            b = CvButton(cv, bx, self.Y(134), bx + sw, self.Y(134) + 54, "",
                         command=lambda k=key: self._set_theme(k), r=11,
                         fill=mix(CARD_HI, th["acc"], 0.30) if act else CARD_HI,
                         bg=CARD, border=th["acc"] if act else BORDER)
            cv.create_oval(bx + sw / 2 - 11, self.Y(152), bx + sw / 2 + 11,
                           self.Y(174), fill=th["acc"], outline="")
            cv.create_text(bx + sw / 2, self.Y(200), text=th["label"].upper(),
                           fill=GOLD if act else DIM, font=ui_font(7, True))
            b.lift = None
        cv.create_text(x1 + 16, self.Y(214), anchor="w",
                       text="warna langsung berubah & otomatis tersimpan",
                       fill=DIM, font=ui_font(7))

        y1, y2 = self.Y(242), self.Y(452)
        x1, x2 = self._panel(16, y1, 352, y2, "JENDELA")
        cv.create_text(x1 + 16, y1 + 40, anchor="w", text="Selalu di atas window lain",
                       fill=TXT, font=ui_font(9))
        self.seg_top = CvSegment(cv, x1 + 16, y1 + 52, x2 - 16, y1 + 84,
                                 [("YA", "1"), ("TIDAK", "0")],
                                 "1" if self.topmost else "0",
                                 command=self._set_topmost)
        cv.create_text(x1 + 16, y1 + 104, anchor="w",
                       text="Mode overlay kecil buat nemenin main",
                       fill=TXT, font=ui_font(9))
        CvButton(cv, x1 + 16, y1 + 116, x2 - 16, y1 + 148,
                 "AKTIFKAN MINI OVERLAY", self.toggle_mini, r=10,
                 fill=CARD_HI, fg=TXT, bg=CARD, border=BORDER,
                 font=ui_font(9, True))
        cv.create_text(x1 + 16, y1 + 162, anchor="w", text="Model tampilan",
                       fill=TXT, font=ui_font(9))
        lay = (("PRO", "pro"), ("GAME", "game"), ("macOS", "macos"),
               ("MINI", "minimal"))
        bw = (x2 - x1 - 32 - 3 * 6) / 4.0
        for i, (txt, key) in enumerate(lay):
            bx = x1 + 16 + i * (bw + 6)
            act = LAYOUT == key
            CvButton(cv, bx, y1 + 174, bx + bw, y1 + 204, txt,
                     command=lambda k=key: self._set_layout(k), r=8,
                     fill=GOLD if act else CARD_HI,
                     fg=on_accent() if act else MUTED, bg=CARD,
                     border=None if act else BORDER, font=ui_font(7, True))

    def _set_topmost(self, val):
        self.topmost = val == "1"
        try:
            self.attributes("-topmost", self.topmost)
        except Exception:
            pass

    def _left_footer(self):
        cv = self.cv
        self.pill = CvPill(cv, self.LW / 2, self.Y(476), w=200, h=36)
        by1, by2 = self.Y(508), self.Y(556)
        bgc = mix(BG_TOP, "#000000", 0.30)
        self.btn_power = CvButton(cv, 16, by1, 216, by2, "ON / OFF   (F2)",
                                  self.engine.toggle_enabled, r=13, accent=True,
                                  glow_on=True, bg=bgc, font=ui_font(10, True))
        CvButton(cv, 226, by1, 352, by2, "KELUAR", self.quit_app, r=13,
                 fill=CARD_HI, fg=MUTED, bg=bgc, border=BORDER,
                 font=ui_font(9, True))

    # ======================================================================
    #  PANEL KANAN - ACTION EDITOR
    # ======================================================================
    def _draw_right(self):
        cv = self.cv
        x1, x2 = self.LW + 16, self.W - 16
        cv.create_text(x1, self.Y(66), anchor="w", text=sp("ACTION EDITOR"),
                       fill=TXT, font=ui_font(10, True))
        cv.create_text(x1, self.Y(84), anchor="w",
                       text="dijalanin urut dari atas ke bawah",
                       fill=DIM, font=ui_font(7))

        # ---- toolbar ----
        tools = [("+", self._seq_add, "tambah"), ("COPY", self._act_dup, ""),
                 ("↑", self._act_up, ""), ("↓", self._act_down, ""),
                 ("HAPUS", self._act_del, ""), ("RESET", self._act_reset, "")]
        widths = {"+": 34, "↑": 34, "↓": 34, "COPY": 52, "HAPUS": 58, "RESET": 58}
        total = sum(widths[t[0]] for t in tools) + 6 * (len(tools) - 1)
        tx = x2 - total
        for label, cmd, _hint in tools:
            w = widths[label]
            acc = label == "+"
            CvButton(cv, tx, self.Y(58), tx + w, self.Y(88), label, cmd, r=8,
                     fill=GOLD if acc else CARD_HI,
                     fg=on_accent() if acc else MUTED,
                     bg=BG_TOP, border=None if acc else BORDER,
                     font=ui_font(11 if acc else 8, True))
            tx += w + 6

        # ---- daftar action ----
        ly1, ly2 = self.Y(100), self.Y(452)
        rr(cv, x1, ly1, x2, ly2, 14, fill=mix(CARD, "#000000", 0.30),
           outline=BORDER)
        seq = self.engine.sequence[:self.MAX_ACT]
        self.rows = []
        if not seq:
            cv.create_text((x1 + x2) / 2, (ly1 + ly2) / 2 - 8,
                           text="Belum ada action.", fill=MUTED,
                           font=ui_font(10, True))
            cv.create_text((x1 + x2) / 2, (ly1 + ly2) / 2 + 12,
                           text="Klik  +  di atas buat nambah tombol.",
                           fill=DIM, font=ui_font(8))
        for i, name in enumerate(seq):
            self.rows.append(self._draw_row(i, name, x1 + 12, x2 - 12,
                                            ly1 + 12 + i * 48))
        if len(self.engine.sequence) > self.MAX_ACT:
            cv.create_text((x1 + x2) / 2, ly2 - 16,
                           text="+%d action lagi (nggak muat ditampilin)"
                                % (len(self.engine.sequence) - self.MAX_ACT),
                           fill=DIM, font=ui_font(7))

        # ---- preset ----
        pw = (x2 - x1 - 3 * 8) / 4.0
        for i, (label, sq) in enumerate(PRESET_SEQ):
            bx = x1 + i * (pw + 8)
            act = sq == self.engine.sequence
            CvButton(cv, bx, self.Y(464), bx + pw, self.Y(494), label,
                     command=lambda q=sq: self._seq_set(q), r=9,
                     fill=GOLD if act else CARD_HI,
                     fg=on_accent() if act else MUTED, bg=BG_BOT,
                     border=None if act else BORDER, font=ui_font(8, True))

        # ---- visualizer + stats ----
        vy1, vy2 = self.Y(506), self.Y(542)
        rr(cv, x1, vy1, x2, vy2, 11, fill=mix(CARD, "#000000", 0.35),
           outline=BORDER)
        self.viz = CvVisualizer(cv, x1 + 12, vy1 + 9, x2 - 12, vy2 - 9, n=60)
        self.lbl_stats = cv.create_text(x1, self.Y(558), anchor="w",
                                        text="0 tekan  ·  0.0 keys/s",
                                        fill=DIM, font=ui_font(8))
        self.lbl_hint = cv.create_text(x2, self.Y(558), anchor="e",
                                       text="F2 = ON / OFF", fill=DIM,
                                       font=ui_font(8))

    def _draw_row(self, idx, name, x1, x2, y):
        """Satu baris action."""
        cv = self.cv
        h = 42
        tg = "row%d" % idx
        sel = self.sel == idx
        body = rr(cv, x1, y, x2, y + h, 10, fill=CARD_HI,
                  outline=GOLD if sel else mix(CARD_HI, "#ffffff", 0.05),
                  tags=(tg,))
        cv.create_oval(x1 + 12, y + h / 2 - 11, x1 + 34, y + h / 2 + 11,
                       fill=mix(CARD_HI, "#000000", 0.4), outline="", tags=(tg,))
        cv.create_text(x1 + 23, y + h / 2, text=str(idx + 1), fill=MUTED,
                       font=ui_font(8, True), tags=(tg,))
        label = {"SPACE": "SPACE", "SHIFT": "SHIFT", "CTRL": "CTRL"}.get(name, name)
        f = ui_font(9, True)
        cw = max(46, f.measure(label) + 24)
        chip = rr(cv, x1 + 46, y + h / 2 - 14, x1 + 46 + cw, y + h / 2 + 14, 8,
                  fill=mix(CARD_HI, GOLD, 0.12), outline=mix(BORDER, GOLD, 0.3),
                  tags=(tg,))
        txt = cv.create_text(x1 + 46 + cw / 2, y + h / 2, text=label, fill=GOLD,
                             font=f, tags=(tg,))
        jit = self.engine.jitter
        desc = "tekan → tahan %d ms" % self.engine.cfg["speed"]
        if jit:
            desc += "  ±%d%%" % jit
        desc_id = cv.create_text(x1 + 60 + cw, y + h / 2, anchor="w", text=desc,
                                 fill=DIM, font=ui_font(8), tags=(tg,))
        # tombol hapus per baris
        dtg = "del%d" % idx
        cv.create_oval(x2 - 34, y + h / 2 - 11, x2 - 12, y + h / 2 + 11,
                       fill=mix(CARD_HI, "#000000", 0.3), outline="", tags=(dtg,))
        cv.create_text(x2 - 23, y + h / 2 - 1, text="✕", fill=MUTED,
                       font=ui_font(8), tags=(dtg,))
        cv.tag_bind(dtg, "<Button-1>", lambda e, i=idx: self._seq_remove(i))
        cv.tag_bind(dtg, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(dtg, "<Leave>", lambda e: cv.config(cursor=""))
        cv.tag_bind(tg, "<Button-1>", lambda e, i=idx: self._select(i))
        cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
        return {"body": body, "chip": chip, "txt": txt, "desc": desc_id,
                "key": "%d:%s" % (idx, name), "sel": sel, "level": 0.0}

    def _select(self, idx):
        self.sel = None if self.sel == idx else idx
        for i, r in enumerate(self.rows):
            on = self.sel == i
            r["sel"] = on
            self.cv.itemconfig(r["body"],
                               outline=GOLD if on else mix(CARD_HI, "#ffffff", 0.05))

    # ---- aksi toolbar ----
    def _need_sel(self):
        if self.sel is None or self.sel >= len(self.engine.sequence):
            self._flash("pilih dulu action-nya (klik barisnya)")
            return False
        return True

    def _act_dup(self):
        if not self._need_sel():
            return
        seq = list(self.engine.sequence)
        if len(seq) >= self.MAX_ACT:
            self._flash("maksimal %d action" % self.MAX_ACT)
            return
        seq.insert(self.sel + 1, seq[self.sel])
        self.sel += 1
        self._seq_set(seq)

    def _act_up(self):
        if not self._need_sel() or self.sel == 0:
            return
        seq = list(self.engine.sequence)
        i = self.sel
        seq[i - 1], seq[i] = seq[i], seq[i - 1]
        self.sel = i - 1
        self._seq_set(seq)

    def _act_down(self):
        if not self._need_sel() or self.sel >= len(self.engine.sequence) - 1:
            return
        seq = list(self.engine.sequence)
        i = self.sel
        seq[i + 1], seq[i] = seq[i], seq[i + 1]
        self.sel = i + 1
        self._seq_set(seq)

    def _act_del(self):
        if not self._need_sel():
            return
        self._seq_remove(self.sel)

    def _act_reset(self):
        self.sel = None
        self._seq_set(["A", "D"])

    # ---- urutan tombol ----
    def _seq_set(self, seq):
        self.engine.set_sequence(list(seq))
        if self.sel is not None and self.sel >= len(self.engine.sequence):
            self.sel = None
        self._build_ui()

    def _seq_remove(self, idx):
        seq = list(self.engine.sequence)
        if len(seq) <= 1:
            self._flash("minimal harus ada 1 action")
            return
        del seq[idx]
        if self.sel is not None and self.sel >= len(seq):
            self.sel = None
        self._seq_set(seq)

    def _seq_add(self):
        if len(self.engine.sequence) >= self.MAX_ACT:
            self._flash("maksimal %d action" % self.MAX_ACT)
            return
        self.capture_for = "seq"
        self.engine.captured_vk = 0
        self.engine.capture_mode = True
        self._flash("tekan tombol yang mau ditambah...")
        self.after(60, self._poll_capture)

    # ======================================================================
    #  LAYOUT MINIMALIS  (LAYOUT = "minimal")
    # ======================================================================
    def _draw_min(self):
        cv, W = self.cv, self.W
        pad = 24

        # ---- status ----
        e = self.engine
        self.m_dot2 = cv.create_oval(pad, self.Y(72), pad + 10, self.Y(82),
                                     fill=GOLD, outline="")
        self.m_big = cv.create_text(pad + 20, self.Y(77), anchor="w",
                                    text="AKTIF", fill=GOLD,
                                    font=ui_font(15, True))
        self.m_sub = cv.create_text(pad, self.Y(102), anchor="w", text="",
                                    fill=DIM, font=ui_font(8))
        self._hline(self.Y(124))

        # ---- hotkey ----
        cv.create_text(pad, self.Y(150), anchor="w", text="Hotkey", fill=TXT,
                       font=ui_font(9))
        self.btn_set = CvButton(cv, W - pad - 72, self.Y(134), W - pad,
                                self.Y(166), self.engine.cfg["hotkey"],
                                self.set_hotkey, r=9, fill=CARD_HI, fg=GOLD,
                                bg=BG_TOP, border=BORDER, font=ui_font(9, True))
        self._hline(self.Y(178))

        # ---- mode ----
        cv.create_text(pad, self.Y(204), anchor="w", text="Cara kerja", fill=TXT,
                       font=ui_font(9))
        self.seg = CvSegment(cv, W - pad - 156, self.Y(188), W - pad,
                             self.Y(220), [("TAHAN", "HOLD"),
                                           ("TOGGLE", "TOGGLE")],
                             self.engine.mode, command=self._on_mode)
        self._hline(self.Y(232))

        # ---- kecepatan ----
        cv.create_text(pad, self.Y(258), anchor="w", text="Kecepatan", fill=TXT,
                       font=ui_font(9))
        self.lbl_speed = cv.create_text(W - pad, self.Y(258), anchor="e",
                                        text="35 ms", fill=GOLD,
                                        font=mono_font(12, True))
        self.slider = CvSlider(cv, pad + 4, W - pad - 4, self.Y(286), 5, 150,
                               int(self.engine.cfg["speed"]),
                               command=lambda v: self._set_speed(v, True))
        self.chips = []
        self._hline(self.Y(308))

        # ---- jitter ----
        cv.create_text(pad, self.Y(334), anchor="w", text="Jitter", fill=TXT,
                       font=ui_font(9))
        self.jchips = []
        jw = 42
        for i, val in enumerate((0, 10, 20, 30)):
            bx = W - pad - (4 - i) * (jw + 5) + 5
            b = CvButton(cv, bx, self.Y(318), bx + jw, self.Y(350),
                         "OFF" if val == 0 else "%d%%" % val,
                         command=lambda v=val: self._set_jitter(v), r=8,
                         fill=CARD_HI, fg=MUTED, bg=BG_TOP, border=BORDER,
                         font=ui_font(8, True))
            b.preset = val
            self.jchips.append(b)
        self._hline(self.Y(362))

        # ---- jeda antar tombol ----
        cv.create_text(pad, self.Y(388), anchor="w", text="Jeda antar tombol",
                       fill=TXT, font=ui_font(9))
        self.gchips = []
        gw = 42
        for i, val in enumerate((0, 10, 20, 40)):
            bx = W - pad - (4 - i) * (gw + 5) + 5
            b = CvButton(cv, bx, self.Y(372), bx + gw, self.Y(404),
                         "0" if val == 0 else str(val),
                         command=lambda v=val: self._set_gap(v), r=8,
                         fill=CARD_HI, fg=MUTED, bg=BG_TOP, border=BORDER,
                         font=ui_font(8, True))
            b.preset = val
            self.gchips.append(b)
        self._hline(self.Y(416))

        # ---- urutan tombol ----
        cv.create_text(pad, self.Y(442), anchor="w", text="Urutan tombol",
                       fill=TXT, font=ui_font(9))
        cv.create_text(W - pad, self.Y(442), anchor="e", text="klik = hapus",
                       fill=DIM, font=ui_font(7))
        self.rows = []
        x = pad
        f = ui_font(9, True)
        for i, name in enumerate(self.engine.sequence[:self.MAX_ACT]):
            w = max(38, f.measure(name) + 20)
            if x + w > W - pad - 40:
                break
            b = CvButton(cv, x, self.Y(458), x + w, self.Y(492), name,
                         command=lambda i=i: self._seq_remove(i), r=9,
                         fill=CARD_HI, fg=TXT, bg=BG_TOP, border=BORDER, font=f)
            self.rows.append({"btn": b, "key": "%d:%s" % (i, name),
                              "level": 0.0})
            x += w + 6
        if len(self.engine.sequence) < self.MAX_ACT:
            CvButton(cv, x, self.Y(458), x + 34, self.Y(492), "+",
                     self._seq_add, r=9, fill=BG_TOP, fg=GOLD, bg=BG_TOP,
                     border=GOLD, font=ui_font(11, True))
        self._hline(self.Y(510))

        # ---- tombol utama ----
        self.btn_power = CvButton(cv, pad, self.Y(528), W - pad, self.Y(574),
                                  "ON / OFF   (F2)", self.engine.toggle_enabled,
                                  r=12, accent=True, bg=BG_TOP,
                                  font=ui_font(10, True))

        # ---- baris bawah: keluar + tema ----
        CvButton(cv, pad - 6, self.Y(588), pad + 56, self.Y(614), "Keluar",
                 self.quit_app, r=8, fill=BG_TOP, fg=DIM, bg=BG_TOP,
                 font=ui_font(8))
        # pilihan model tampilan biar nggak nyangkut di satu layout
        CvPopup(cv, self, 258, self.Y(601),
                [("Minimalis", "minimal"), ("Game menu", "game"),
                 ("macOS", "macos"), ("Pro", "pro")], LAYOUT,
                self._set_layout, minw=124)
        cx = W - pad - 8
        for key in reversed(THEME_ORDER):
            th = THEMES[key]
            tg = "sw_" + key
            act = key == CURRENT_THEME
            r = 6 if act else 4.5
            if act:
                cv.create_oval(cx - 9, self.Y(601) - 9, cx + 9, self.Y(601) + 9,
                               outline=th["acc"], width=1, tags=(tg,))
            cv.create_oval(cx - r, self.Y(601) - r, cx + r, self.Y(601) + r,
                           fill=th["acc"], outline="", tags=(tg,))
            # area klik tembus pandang (warnanya sama kayak background) biar
            # nggak perlu ngincer bulatan kecilnya
            hit = cv.create_oval(cx - 10, self.Y(601) - 10, cx + 10,
                                 self.Y(601) + 10, fill=BG_TOP, outline="",
                                 tags=(tg,))
            cv.tag_lower(hit)
            cv.tag_bind(tg, "<Button-1>",
                        lambda ev, k=key: self.after(1, lambda: self._set_theme(k)))
            cv.tag_bind(tg, "<Enter>", lambda ev: cv.config(cursor="hand2"))
            cv.tag_bind(tg, "<Leave>", lambda ev: cv.config(cursor=""))
            cx -= 20

        self.lbl_hint = cv.create_text(W / 2, self.Y(601), text="",
                                       fill=GREEN, font=ui_font(7))
        self.lbl_stats = None
        self.pill = None
        self.viz = None

    def _set_gap(self, val):
        self.engine.set_gap(val)
        if self.game:
            return
        for b in getattr(self, "gchips", []):
            on = b.preset == self.engine.gap
            b.set_style(GOLD if on else CARD_HI, on_accent() if on else MUTED)

    def _hline(self, y):
        self.cv.create_line(20, y, self.W - 20, y, fill=mix(BG_TOP, "#ffffff", 0.07))

    def _refresh_min(self):
        e = self.engine
        c = GOLD if e.enabled else RED
        self.cv.itemconfig(self.m_dot2, fill=c)
        self.cv.itemconfig(self.m_big, text="AKTIF" if e.enabled else "MATI",
                           fill=c)
        self.btn_power.set_style(GOLD if e.enabled else CARD_HI,
                                 on_accent() if e.enabled else MUTED,
                                 show_glow=False)
        self._set_speed(e.cfg["speed"])
        self._set_jitter(e.jitter)
        self._set_gap(e.gap)

    def _tick_min(self):
        e = self.engine
        kps = e.keys_per_sec()
        hk = e.cfg["hotkey"]
        seq = " → ".join(e.sequence[:4])
        if e.spamming:
            sub = "%s  ·  %.1f keys/s  ·  %s tekan" % (seq, kps, f"{e.presses:,}")
            col = GOLD
        else:
            verb = "tahan" if e.mode == "HOLD" else "tekan"
            sub = "%s '%s' buat spam  %s" % (verb, hk, seq)
            col = DIM
        if e.enabled and is_app_focused(self):
            sub = "klik ke jendela game dulu — input dikirim ke window aktif"
            col = RED
        self.cv.itemconfig(self.m_sub, text=sub, fill=col)
        for r in self.rows:
            r["level"] = 1.0 if e.active_key == r["key"] else max(0.0, r["level"] - 0.28)
            L = r["level"]
            r["btn"].set_style(mix(CARD_HI, GOLD, L), mix(TXT, on_accent(), L))

    # ======================================================================
    #  LAYOUT macOS  (LAYOUT = "macos")
    # ======================================================================
    def close_menu(self):
        if getattr(self, "menu_open", False):
            self.cv.delete("menu")
            self.menu_open = False

    def _mac_colors(self):
        self.SIDE = mix(BG_TOP, "#000000", 0.28)
        self.PANE = mix(BG_TOP, "#ffffff", 0.045)
        self.CARDM = mix(self.PANE, "#ffffff", 0.06)
        self.SEP = mix(self.CARDM, "#ffffff", 0.07)
        self.CTRL = mix(self.CARDM, "#ffffff", 0.10)

    def _mac_icon(self, x, y, kind, color, size=22):
        """Ikon kotak-bulat kecil ala System Settings."""
        cv = self.cv
        s = size
        rr(cv, x, y, x + s, y + s, s * 0.28, fill=color, outline="")
        cx, cy = x + s / 2, y + s / 2
        w = "#ffffff"
        if kind == "key":                       # keyboard
            rr(cv, cx - 7, cy - 5, cx + 7, cy + 5, 2, outline=w, fill="")
            for dx in (-4, -1.3, 1.3, 4):
                cv.create_line(cx + dx, cy - 2, cx + dx, cy - 1.4, fill=w,
                               width=1.6)
            cv.create_line(cx - 3, cy + 2.2, cx + 3, cy + 2.2, fill=w, width=1.6)
        elif kind == "bolt":
            cv.create_polygon(cx + 1, cy - 7, cx - 5, cy + 1, cx - 1, cy + 1,
                              cx - 1, cy + 7, cx + 5, cy - 1, cx + 1, cy - 1,
                              fill=w, outline="")
        elif kind == "list":
            for i, dy in enumerate((-4.5, 0, 4.5)):
                cv.create_oval(cx - 6, cy + dy - 1, cx - 4, cy + dy + 1,
                               fill=w, outline="")
                cv.create_line(cx - 2, cy + dy, cx + 6, cy + dy, fill=w)
        elif kind == "palette":
            cv.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline=w)
            cv.create_oval(cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5, fill=w,
                           outline="")
        elif kind == "info":
            cv.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline=w)
            cv.create_text(cx, cy + 0.5, text="i", fill=w, font=ui_font(8, True))
        elif kind == "power":
            cv.create_arc(cx - 5.5, cy - 5.5, cx + 5.5, cy + 5.5, start=65,
                          extent=290, style="arc", outline=w)
            cv.create_line(cx, cy - 7, cx, cy - 1, fill=w, width=2)
        elif kind == "swap":
            cv.create_line(cx - 5, cy - 2.5, cx + 5, cy - 2.5, fill=w,
                           arrow="last", arrowshape=(4, 5, 2))
            cv.create_line(cx + 5, cy + 2.5, cx - 5, cy + 2.5, fill=w,
                           arrow="last", arrowshape=(4, 5, 2))
        elif kind == "clock":
            cv.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline=w)
            cv.create_line(cx, cy, cx, cy - 3.5, fill=w)
            cv.create_line(cx, cy, cx + 3, cy, fill=w)
        elif kind == "dice":
            cv.create_rectangle(cx - 5.5, cy - 5.5, cx + 5.5, cy + 5.5, outline=w)
            for dx, dy in ((-2.5, -2.5), (2.5, 2.5), (0, 0)):
                cv.create_oval(cx + dx - 1, cy + dy - 1, cx + dx + 1,
                               cy + dy + 1, fill=w, outline="")
        elif kind == "target":
            cv.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, outline=w)
            cv.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=w, outline="")
            for a, b_ in ((-9, -4), (9, 4)):
                cv.create_line(cx + a, cy, cx + b_, cy, fill=w)
                cv.create_line(cx, cy + a, cx, cy + b_, fill=w)
        elif kind == "window":
            cv.create_rectangle(cx - 6, cy - 5, cx + 6, cy + 5, outline=w)
            cv.create_line(cx - 6, cy - 2, cx + 6, cy - 2, fill=w)
        elif kind == "num":
            pass
        return cx, cy

    def _mac_numicon(self, x, y, n, active=False, size=22):
        cv = self.cv
        col = GOLD if active else mix(self.CARDM, "#ffffff", 0.16)
        cv.create_oval(x, y, x + size, y + size, fill=col, outline="")
        cv.create_text(x + size / 2, y + size / 2 + 0.5, text=str(n),
                       fill=on_accent() if active else TXT,
                       font=ui_font(8, True))

    # ------------------------------------------------------------ kerangka
    def _draw_mac(self):
        self._mac_colors()
        self.mac_rows = []
        self.mac_pops = []
        self.sw_power = None      # switch-nya cuma ada di halaman Macro
        self._mac_sidebar()
        self._mac_header()
        y = self.Y(72)
        page = getattr(self, "page", "macro")
        if page == "macro":
            self._mac_p_macro(y)
        elif page == "speed":
            self._mac_p_speed(y)
        elif page == "seq":
            self._mac_p_seq(y)
        elif page == "dahood":
            self._mac_p_dahood(y)
        elif page == "tampilan":
            self._mac_p_tampilan(y)
        else:
            self._mac_p_tentang(y)
        self.cv.bind("<ButtonRelease-1>", self._mac_bgclick, add="+")

    def _mac_bgclick(self, _=None):
        if getattr(self, "menu_open", False):
            self.after(1, self._mac_maybe_close)

    def _mac_maybe_close(self):
        if getattr(self, "menu_open", False) and \
                time.time() - getattr(self, "_menu_time", 0) > 0.25:
            self.close_menu()

    def _mac_sidebar(self):
        cv, w = self.cv, self.SW
        cv.create_rectangle(0, self.Y(46), w, self.win_h, fill=self.SIDE,
                            outline="")
        cv.create_line(w, self.Y(46), w, self.win_h,
                       fill=mix(self.SIDE, "#ffffff", 0.10))
        # baris identitas (posisinya kayak baris Apple ID)
        hb = mix(self.SIDE, "#ffffff", 0.06)
        rr(cv, 12, self.Y(58), w - 12, self.Y(106), 8, fill=hb, outline="")
        icon_moon(cv, 40, self.Y(82), 12, GOLD, hb)
        cv.create_text(64, self.Y(75), anchor="w", text="Moonwalk Macro",
                       fill=TXT, font=ui_font(9, True))
        self.mac_sub = cv.create_text(64, self.Y(92), anchor="w", text="",
                                      fill=DIM, font=ui_font(7))
        items = (("macro", "Macro", "key", GOLD),
                 ("speed", "Kecepatan", "bolt", "#3b82f6"),
                 ("seq", "Urutan Tombol", "list", "#a855f7"),
                 ("dahood", "Da Hood", "target", "#ef4444"),
                 ("tampilan", "Tampilan", "palette", "#ec4899"),
                 ("tentang", "Tentang", "info", mix(TXT, BG_TOP, 0.45)))
        y = self.Y(122)
        page = getattr(self, "page", "macro")
        for key, label, kind, col in items:
            act = page == key
            tg = "sb_" + key
            box = rr(cv, 10, y, w - 10, y + 34, 7,
                     fill=GOLD if act else self.SIDE, outline="", tags=(tg,))
            self._mac_icon(20, y + 6, kind, col)
            cv.create_text(54, y + 17, anchor="w", text=label,
                           fill=on_accent() if act else TXT,
                           font=ui_font(9, act), tags=(tg,))
            if not act:
                cv.tag_bind(tg, "<Enter>", lambda e, b=box: (
                    cv.itemconfig(b, fill=mix(self.SIDE, "#ffffff", 0.07)),
                    cv.config(cursor="hand2")))
                cv.tag_bind(tg, "<Leave>", lambda e, b=box: (
                    cv.itemconfig(b, fill=self.SIDE), cv.config(cursor="")))
            cv.tag_bind(tg, "<ButtonRelease-1>",
                        lambda e, k=key: self._mac_goto(k))
            y += 38
        self.mac_foot = cv.create_text(20, self.win_h - 22, anchor="w", text="",
                                       fill=DIM, font=ui_font(7))

    def _mac_goto(self, key):
        self.close_menu()
        self.page = key
        self._build_ui()

    def _mac_header(self):
        cv, x = self.cv, self.SW
        titles = {"macro": "Macro", "speed": "Kecepatan",
                  "seq": "Urutan Tombol", "dahood": "Da Hood",
                  "tampilan": "Tampilan", "tentang": "Tentang"}
        page = getattr(self, "page", "macro")
        order = ["macro", "speed", "seq", "dahood", "tampilan", "tentang"]
        i = order.index(page)
        for k, dx, step in (("bk", 26, -1), ("fw", 52, 1)):
            j = i + step
            on = 0 <= j < len(order)
            c = MUTED if on else mix(DIM, self.PANE, 0.55)
            tg = "nav" + k
            cv.create_rectangle(x + dx - 12, self.Y(10), x + dx + 12,
                                self.Y(36), fill="", outline="", tags=(tg,))
            sgn = 1 if step < 0 else -1
            cv.create_line(x + dx + 3 * sgn, self.Y(16), x + dx - 3 * sgn,
                           self.Y(23), x + dx + 3 * sgn, self.Y(30),
                           fill=c, width=2, capstyle="round", joinstyle="round",
                           tags=(tg,))
            if on:
                cv.tag_bind(tg, "<ButtonRelease-1>",
                            lambda e, kk=order[j]: self._mac_goto(kk))
                cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
                cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
        cv.create_text(x + 78, self.Y(23), anchor="w", text=titles[page],
                       fill=TXT, font=ui_font(12, True))

    # -------------------------------------------------------------- kartu
    def _mac_card(self, y, rows, title=None, caption=None):
        cv = self.cv
        x1, x2 = self.SW + 24, self.W - 24
        if title:
            cv.create_text(x1 + 2, y, anchor="w", text=title, fill=DIM,
                           font=ui_font(7, True))
            y += 20
        h = sum(r.get("h", 52) for r in rows)
        rr(cv, x1, y, x2, y + h, 10, fill=self.CARDM, outline="")
        ry = y
        for i, r in enumerate(rows):
            rh = r.get("h", 52)
            cy = ry + rh / 2
            if i:
                cv.create_line(x1 + 52, ry, x2 - 1, ry, fill=self.SEP)
            lx = x1 + 16
            if r.get("icon"):
                self._mac_icon(x1 + 14, cy - 11, r["icon"][0], r["icon"][1])
                lx = x1 + 48
            elif r.get("num"):
                self._mac_numicon(x1 + 14, cy - 11, r["num"])
                lx = x1 + 48
            ty = cy - 8 if r.get("sub") else cy
            tid = cv.create_text(lx, ty, anchor="w", text=r["label"], fill=TXT,
                                 font=ui_font(9, r.get("bold", False)))
            sid = None
            if r.get("sub"):
                sid = cv.create_text(lx, cy + 9, anchor="w", text=r["sub"],
                                     fill=DIM, font=ui_font(7))
            if r.get("build"):
                r["build"](x2 - 16, cy, lx, tid, sid)
            ry += rh
        y += h
        if caption:
            y += 9
            for line in caption:
                cv.create_text(x1 + 4, y, anchor="nw", text=line, fill=DIM,
                               font=ui_font(7))
                y += 14
        return y + 20

    def _mac_btn(self, x2, cy, text, cmd, w=None, fg=None, fill=None):
        f = ui_font(8, True)
        w = w or f.measure(text) + 28
        return CvButton(self.cv, x2 - w, cy - 13, x2, cy + 13, text, cmd, r=6,
                        fill=fill or self.CTRL, fg=fg or TXT, bg=self.CARDM,
                        font=f)

    def _mac_popup(self, x2, cy, options, value, cmd):
        p = CvPopup(self.cv, self, x2, cy, options, value, cmd)
        self.mac_pops.append(p)
        return p

    # -------------------------------------------------------------- halaman
    def _mac_p_macro(self, y):
        e = self.engine
        hk = e.cfg["hotkey"]

        def b_switch(x2, cy, lx, tid, sid):
            self.sw_power = CvSwitch(self.cv, x2, cy, e.enabled,
                                     lambda v: e.toggle_enabled())

        def b_hotkey(x2, cy, lx, tid, sid):
            self.btn_set = self._mac_btn(x2, cy, hk, self.set_hotkey, w=64,
                                         fg=GOLD)

        def b_mode(x2, cy, lx, tid, sid):
            self._mac_popup(x2, cy, [("Tahan tombol", "HOLD"),
                                     ("Mode toggle", "TOGGLE")],
                            e.mode, self._on_mode)

        y = self._mac_card(y, [
            {"label": "Macro aktif", "icon": ("power", GOLD),
             "sub": "master switch — sama kayak tombol F2", "build": b_switch},
            {"label": "Tombol pemicu", "icon": ("key", "#3b82f6"),
             "sub": "klik buat rekam tombol baru", "build": b_hotkey},
            {"label": "Cara kerja", "icon": ("swap", "#a855f7"),
             "build": b_mode},
        ], title="PENGATURAN UTAMA", caption=[
            "Tahan: spam jalan selama tombol pemicu ditahan.",
            "Toggle: sekali tekan buat nyalain, tekan lagi buat matiin."])

        def b_mini(x2, cy, lx, tid, sid):
            self._mac_btn(x2, cy, "Buka", self.toggle_mini, w=64)

        def b_f2(x2, cy, lx, tid, sid):
            self.cv.create_text(x2, cy, anchor="e", text=e.cfg["master_key"],
                                fill=MUTED, font=mono_font(10, True))

        self._mac_card(y, [
            {"label": "Nyalain / matiin macro", "icon": ("power", "#22c55e"),
             "build": b_f2},
            {"label": "Mini overlay", "icon": ("window", "#64748b"),
             "sub": "jendela kecil biar nggak nutupin game", "build": b_mini},
        ], title="PINTASAN")

    def _mac_p_speed(self, y):
        e = self.engine
        sp_opts = [("Lambat — 60 ms", 60), ("Normal — 35 ms", 35),
                   ("Cepat — 20 ms", 20), ("Gila — 10 ms", 10)]
        cur = int(e.cfg["speed"])
        if cur not in [o[1] for o in sp_opts]:
            sp_opts.append(("Custom — %d ms" % cur, cur))

        def b_preset(x2, cy, lx, tid, sid):
            self.pop_speed = self._mac_popup(x2, cy, sp_opts, cur,
                                             lambda v: self._set_speed_full(v))

        def b_slider(x2, cy, lx, tid, sid):
            self.lbl_speed = self.cv.create_text(x2, cy, anchor="e",
                                                 text="%d ms" % cur, fill=GOLD,
                                                 font=mono_font(10, True))
            self.slider = CvSlider(self.cv, lx, x2 - 58, cy + 16, 5, 150, cur,
                                   command=lambda v: self._set_speed(v, True))

        def b_jit(x2, cy, lx, tid, sid):
            self._mac_popup(x2, cy, [("Mati", 0), ("10%", 10), ("20%", 20),
                                     ("30%", 30)], e.jitter, self._set_jitter)

        def b_gap(x2, cy, lx, tid, sid):
            self._mac_popup(x2, cy, [("Nggak ada", 0), ("10 ms", 10),
                                     ("20 ms", 20), ("40 ms", 40)],
                            e.gap, self._set_gap)

        self.jchips = []
        self.gchips = []
        y = self._mac_card(y, [
            {"label": "Preset kecepatan", "icon": ("bolt", "#3b82f6"),
             "build": b_preset},
            {"label": "Atur sendiri", "icon": ("clock", "#0ea5e9"),
             "h": 68, "build": b_slider},
            {"label": "Jitter", "icon": ("dice", "#a855f7"),
             "sub": "delay diacak biar nggak kaku", "build": b_jit},
            {"label": "Jeda antar tombol", "icon": ("swap", "#f59e0b"),
             "sub": "diam sebentar setelah tombol dilepas", "build": b_gap},
        ], title="TIMING", caption=[
            "Roblox baca input per frame (16 ms). Kalau tombolnya ditekan-lepas",
            "kekencengan tanpa jeda, input-nya bisa kelewat. Buat Roblox coba",
            "kecepatan 45 ms + jeda 10 ms."])

    def _mac_p_seq(self, y):
        e = self.engine
        rows = []
        for i, name in enumerate(e.sequence):
            def b_act(x2, cy, lx, tid, sid, i=i):
                self.mac_rows.append({"txt": tid, "sub": sid,
                                      "key": "%d:%s" % (i, e.sequence[i]),
                                      "level": 0.0})
                bx = x2
                for txt, cmd in (("✕", lambda i=i: self._seq_remove(i)),
                                 ("↓", lambda i=i: self._mac_move(i, 1)),
                                 ("↑", lambda i=i: self._mac_move(i, -1))):
                    CvButton(self.cv, bx - 30, cy - 13, bx, cy + 13, txt, cmd,
                             r=6, fill=self.CTRL, fg=MUTED, bg=self.CARDM,
                             font=ui_font(9, True))
                    bx -= 34
            rows.append({"label": name, "num": i + 1,
                         "sub": "tekan → tahan %d ms" % e.cfg["speed"],
                         "bold": True, "build": b_act})
        if len(e.sequence) < self.MAX_ACT:
            def b_add(x2, cy, lx, tid, sid):
                self._mac_btn(x2, cy, "Tambah", self._seq_add, w=80, fg=GOLD)
            rows.append({"label": "Tambah action", "icon": ("list", "#a855f7"),
                         "build": b_add})
        y = self._mac_card(y, rows, title="DIJALANIN URUT DARI ATAS",
                           caption=["Baris yang lagi dikirim bakal nyala pas macro jalan."])

        def b_preset(x2, cy, lx, tid, sid):
            cur = ",".join(e.sequence)
            opts = [(k.title(), ",".join(v)) for k, v in PRESET_SEQ]
            if cur not in [o[1] for o in opts]:
                opts.append(("Custom", cur))
            self._mac_popup(x2, cy, opts, cur,
                            lambda v: self._seq_set(v.split(",")))

        self._mac_card(y, [
            {"label": "Preset urutan", "icon": ("list", "#ec4899"),
             "build": b_preset},
        ], title="PRESET")

    def _mac_p_dahood(self, y):
        e = self.engine

        def b_pasang(x2, cy, lx, tid, sid):
            self._mac_btn(x2, cy, "Pasang", self._pasang_dahood, w=84, fg=GOLD)

        siap = (e.sequence == ["I", "O"] and e.mode == "HOLD"
                and int(e.cfg["speed"]) <= 20 and e.gap == 0)
        y = self._mac_card(y, [
            {"label": "Setelan speed glitch", "icon": ("bolt", "#f59e0b"),
             "sub": ("sudah terpasang ✓" if siap
                     else "urutan I → O · 15 ms · tanpa jeda · mode tahan"),
             "build": b_pasang},
        ], title="SETELAN OTOMATIS", caption=[
            "Da Hood bukan di-spam A/D. Yang di-spam itu tombol zoom kamera",
            "I dan O — itu yang bikin speed glitch / moonwalk-nya jalan."])

        langkah = [
            ("Nyalain shift lock", "biar arah karakter ngunci ke kamera"),
            ("Pasang emote greet", "tunggu sampai tangannya naik deket kepala"),
            ("Keluarin senjata, langsung simpen", "ini yang mancing glitch-nya"),
            ("Hadap ke arah tujuan", "nanti kamu jalannya mundur"),
            ("Tahan hotkey + tahan S", "macro spam I/O, kamu tetap tahan S"),
        ]
        rows = [{"label": t, "sub": s2, "num": i + 1, "h": 44}
                for i, (t, s2) in enumerate(langkah)]
        y = self._mac_card(y, rows, title="LANGKAH DI DALAM GAME", caption=[
            "Timing pas naruh senjata itu bagian paling susah — wajar kalau",
            "gagal beberapa kali. Latihan dulu di tempat sepi."])

        def val(v):
            def b(x2, cy, lx, tid, sid, v=v):
                self.cv.create_text(x2, cy, anchor="e", text=v, fill=MUTED,
                                    font=ui_font(8))
            return b

        self._mac_card(y, [
            {"label": "FPS 60 (default)", "build": val("delay 12 – 18 ms"),
             "h": 36},
            {"label": "FPS unlocker (144+)", "build": val("delay 8 – 10 ms"),
             "h": 36},
            {"label": "Grafik game", "build": val("Low GFX / level 1 – 2"),
             "h": 36},
        ], title="KALAU MASIH BELUM JALAN", caption=[
            "Karakter cuma getar di tempat = delay-nya kekecilan, naikin.",
            "Jalan tapi pelan = delay-nya kegedean, turunin 1-2 ms.",
            "Macro di game online tetap ada risiko banned — tanggung sendiri ya."])

    def _pasang_dahood(self):
        e = self.engine
        e.set_sequence(["I", "O"])
        e.set_speed(15)
        e.set_gap(0)
        e.set_jitter(0)
        e.set_mode("HOLD")
        self._build_ui()
        self._flash("setelan Da Hood terpasang — I → O, 15 ms")

    def _mac_move(self, i, d):
        seq = list(self.engine.sequence)
        j = i + d
        if 0 <= j < len(seq):
            seq[i], seq[j] = seq[j], seq[i]
            self._seq_set(seq)

    def _mac_p_tampilan(self, y):
        e = self.engine

        def b_tema(x2, cy, lx, tid, sid):
            opts = [(k.title(), k, THEMES[k]["acc"]) for k in THEME_ORDER]
            self._mac_popup(x2, cy, opts, CURRENT_THEME, self._set_theme)

        def b_layout(x2, cy, lx, tid, sid):
            self._mac_popup(x2, cy, [("Minimalis", "minimal"),
                                     ("Pro — dua panel", "pro"),
                                     ("macOS", "macos"),
                                     ("Game menu", "game")], LAYOUT,
                            self._set_layout)

        def b_top(x2, cy, lx, tid, sid):
            CvSwitch(self.cv, x2, cy, self.topmost, self._set_topmost)

        def b_mini(x2, cy, lx, tid, sid):
            self._mac_btn(x2, cy, "Aktifkan", self.toggle_mini, w=84)

        self._mac_card(y, [
            {"label": "Tema warna", "icon": ("palette", "#ec4899"),
             "build": b_tema},
            {"label": "Model tampilan", "icon": ("window", "#3b82f6"),
             "sub": "ganti gaya UI-nya, langsung berubah", "build": b_layout},
            {"label": "Selalu di atas window lain", "icon": ("list", "#64748b"),
             "build": b_top},
            {"label": "Mini overlay", "icon": ("window", "#22c55e"),
             "sub": "jendela kecil 304×74", "build": b_mini},
        ], title="TAMPILAN", caption=[
            "Semua pilihan di sini langsung kesimpen otomatis."])

    def _mac_p_tentang(self, y):
        rows = []
        for label, val in (("Versi", VERSION),
                           ("Dibuat pakai", "Python + Tkinter"),
                           ("Target", "Roblox / game apa aja"),
                           ("Cara kirim tombol", "SendInput + scan code")):
            def b_val(x2, cy, lx, tid, sid, v=val):
                self.cv.create_text(x2, cy, anchor="e", text=v, fill=MUTED,
                                    font=ui_font(8))
            rows.append({"label": label, "build": b_val, "h": 40})
        y = self._mac_card(y, rows, title="INFO", caption=[
            "Pakai macro di game online ada risiko kena banned.",
            "Pakai dengan tanggung jawab sendiri."])

        def b_paste(x2, cy, lx, tid, sid):
            self._mac_btn(x2, cy, "Tempel link", self._paste_url, w=104)

        def b_upd(x2, cy, lx, tid, sid):
            self._mac_btn(x2, cy, "Cek update", self._do_update, w=104, fg=GOLD)

        url = UPDATE_URL or "belum diisi — copy link-nya dulu, terus Tempel link"
        if len(url) > 46:
            url = url[:43] + "..."
        y = self._mac_card(y, [
            {"label": "Link update", "sub": url, "icon": ("target", "#3b82f6"),
             "build": b_paste},
            {"label": "Cek versi baru", "sub": "update tanpa download manual",
             "icon": ("bolt", "#22c55e"), "build": b_upd},
        ], title="UPDATE OTOMATIS", caption=[
            "Taruh moonwalk_macro.py terbaru di GitHub (raw) atau Gist, copy",
            "link-nya, terus klik Tempel link. Sekali set, update tinggal 1 klik.",
            "File lama otomatis dibackup jadi moonwalk_macro.py.bak"])

        def b_quit(x2, cy, lx, tid, sid):
            self._mac_btn(x2, cy, "Keluar", self.quit_app, w=84, fg=RED)

        self._mac_card(y, [
            {"label": "Tutup aplikasi", "icon": ("power", RED),
             "build": b_quit}])

    # ------------------------------------------------------------- dinamis
    def _set_speed_full(self, v):
        self.engine.set_speed(v)
        self._build_ui()

    def _set_layout(self, key):
        global LAYOUT
        LAYOUT = key
        self.engine.cfg["layout"] = key
        save_settings(self.engine.cfg)
        self.minimal = key == "minimal"
        self.macos = key == "macos"
        self.game = key == "game"
        if self.game:
            self.W, self.H = self._game_size()
        elif self.macos:
            self.W, self.H = self.WMAC, self.HMAC
        elif self.minimal:
            self.W, self.H = self.WMIN, self.HMIN
        else:
            self.W, self.H = self.WPRO, self.HPRO
        self.win_h = self.H if self.custom_bar else self.H - 46
        self.geometry("%dx%d" % (self.W, self.win_h))
        self._center(self.win_h)
        self._build_ui()

    def _game_size(self):
        """Background nyala = window lega. Background mati = pas ukuran panel."""
        if SHOW_BG:
            return self.WGAME, self.HGAME
        return self.WGAME0, self.HGAME0

    def _refresh_mac(self):
        e = self.engine
        if getattr(self, "sw_power", None) is not None:
            try:
                self.sw_power.set(e.enabled)
            except tk.TclError:
                self.sw_power = None
        self.cv.itemconfig(self.mac_sub,
                           text="Macro aktif · %s" % e.cfg["hotkey"]
                           if e.enabled else "Macro mati",
                           fill=GOLD if e.enabled else DIM)

    def _tick_mac(self):
        e = self.engine
        if e.spamming:
            txt = "%.1f keys/s · %s tekan" % (e.keys_per_sec(),
                                              f"{e.presses:,}")
            col = GOLD
        elif e.enabled:
            verb = "tahan" if e.mode == "HOLD" else "tekan"
            txt = "%s '%s' buat spam" % (verb, e.cfg["hotkey"])
            col = DIM
        else:
            txt = "macro lagi mati · F2"
            col = DIM
        if e.enabled and is_app_focused(self):
            txt, col = "klik ke jendela game dulu", RED
        self.cv.itemconfig(self.mac_foot, text=txt, fill=col)
        for r in self.mac_rows:
            r["level"] = 1.0 if e.active_key == r["key"] else max(
                0.0, r["level"] - 0.28)
            L = r["level"]
            self.cv.itemconfig(r["txt"], fill=mix(TXT, GOLD, L))
            if r["sub"]:
                self.cv.itemconfig(r["sub"], fill=mix(DIM, GOLD, L))

    def _draw_mac_bar(self):
        cv = self.cv
        cv.create_rectangle(0, 0, self.SW, 46, fill=self.SIDE, outline="",
                            tags=("bar",))
        cv.create_rectangle(self.SW, 0, self.W, 46, fill=self.PANE, outline="",
                            tags=("bar",))
        cv.create_line(self.SW, 46, self.W, 46,
                       fill=mix(self.PANE, "#ffffff", 0.08))
        lights = (("#ff5f57", self.quit_app, "tl0"),
                  ("#febc2e", self.minimize, "tl1"),
                  ("#28c840", self.toggle_mini, "tl2"))
        for i, (col, cmd, tg) in enumerate(lights):
            cx = 22 + i * 20
            cv.create_oval(cx - 6, 17, cx + 6, 29, fill=col, outline="",
                           tags=(tg,))
            cv.tag_bind(tg, "<ButtonRelease-1>", lambda e, c=cmd: c())
            cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
        cv.tag_bind("bar", "<Button-1>", self._drag_start)
        cv.tag_bind("bar", "<B1-Motion>", self._drag_move)

    # ======================================================================
    #  LAYOUT GAME MENU  (LAYOUT = "game")
    # ======================================================================
    def _game_palette(self):
        global G_PANEL, G_LINE, G_TXT, G_ON, G_DIM
        G_PANEL = mix(mix(BG_BOT, GOLD, 0.16), "#000000", 0.18)
        G_LINE = mix(G_PANEL, "#ffffff", 0.32)
        G_TXT = "#f7f4ee"
        G_ON = GOLD          # ikut tema; pilih tema hijau = persis referensi
        G_DIM = mix(G_TXT, G_PANEL, 0.42)

    def _game_bg(self, h):
        """Background 'game' — langit senja yang diblur (bisa dimatiin)."""
        cv = self.cv
        if not SHOW_BG:
            cv.create_rectangle(0, 0, self.W, h,
                                fill=mix(BG_BOT, "#000000", 0.35), outline="")
            return
        top = mix(GOLD, "#ffffff", 0.42)
        bot = mix(BG_BOT, GOLD, 0.12)
        vgrad(cv, 0, 0, self.W, h, top, bot, steps=110)
        # matahari
        glow(cv, self.W * 0.58, h * 0.12, 210, mix(GOLD, "#ffffff", 0.75),
             mix(top, bot, 0.12), layers=46, power=2.0)
        # semak-semak buram di bawah
        for fx, fy, r, c in ((0.12, 0.80, 150, "#3b3a1c"), (0.72, 0.86, 190, "#2f3318"),
                             (0.42, 0.95, 160, "#40371d"), (0.92, 0.74, 120, "#4a3a1e")):
            glow(cv, self.W * fx, h * fy, r, mix(c, GOLD, 0.20),
                 mix(top, bot, min(1.0, fy + 0.05)), layers=34, power=1.7)

    def _game_panel(self, x1, y1, x2, y2, title):
        cv = self.cv
        rad = 10 if SHOW_BG else 0
        if SHOW_BG:
            rr(cv, x1 + 2, y1 + 3, x2 + 2, y2 + 3, 10,
               fill=mix(G_PANEL, "#000000", 0.55), outline="")
        rr(cv, x1, y1, x2, y2, rad, fill=G_PANEL, outline=G_LINE, width=1)
        # gradasi tipis di dalam panel -> kesannya tembus pandang
        vgrad(cv, x1 + 2, y1 + 57, x2 - 2, y2 - 2,
              mix(G_PANEL, "#ffffff", 0.05), mix(G_PANEL, "#000000", 0.22),
              steps=60)
        rr(cv, x1, y1, x2, y1 + 56, rad, fill=mix(G_PANEL, "#000000", 0.38),
           outline="", tags=("bar",))
        cv.create_rectangle(x1, y1 + 40, x2, y1 + 56,
                            fill=mix(G_PANEL, "#000000", 0.38), outline="",
                            tags=("bar",))
        cv.create_line(x1 + 1, y1 + 56, x2 - 1, y1 + 56, fill=G_LINE)
        cv.create_text(x1 + 24, y1 + 28, anchor="w", text=title, fill=G_TXT,
                       font=ui_font(13, True), tags=("bar",))
        tg = "gx%d" % int(y1)
        cv.create_text(x2 - 26, y1 + 28, text="✕", fill=G_TXT,
                       font=ui_font(13), tags=(tg,))
        cv.create_rectangle(x2 - 44, y1 + 8, x2 - 8, y1 + 48, fill="",
                            outline="", tags=(tg,))
        cv.tag_bind(tg, "<ButtonRelease-1>", lambda e: self.quit_app())
        cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
        # tombol mini overlay di sebelah ✕
        tg2 = "gm%d" % int(y1)
        cv.create_text(x2 - 62, y1 + 28, text="⤡", fill=G_TXT,
                       font=ui_font(12), tags=(tg2,))
        cv.create_rectangle(x2 - 80, y1 + 8, x2 - 46, y1 + 48, fill="",
                            outline="", tags=(tg2,))
        cv.tag_bind(tg2, "<ButtonRelease-1>", lambda e: self.toggle_mini())
        cv.tag_bind(tg2, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(tg2, "<Leave>", lambda e: cv.config(cursor=""))
        cv.tag_bind("bar", "<Button-1>", self._drag_start)
        cv.tag_bind("bar", "<B1-Motion>", self._drag_move)
        return x1 + 32, x2 - 32

    def _draw_game(self):
        self._game_palette()
        cv = self.cv
        e = self.engine
        self.game_rows = []
        if SHOW_BG:
            pw = 566
            x1 = (self.W - pw) / 2
            x2 = x1 + pw
            y1, y2 = self.Y(38), self.win_h - 38
        else:
            x1, x2 = 0, self.W
            y1, y2 = self.Y(0), self.win_h
        lx, rx = self._game_panel(x1, y1, x2, y2, "Setelan Macro")
        f = ui_font(12)

        def label(y, t):
            cv.create_text(lx, y, anchor="w", text=t, fill=G_TXT, font=f)

        # ---------- strip tab ----------
        tab = getattr(self, "gtab", "macro")
        tw = 150
        for i, (key, txt) in enumerate((("macro", "SETELAN"),
                                        ("tampilan", "TAMPILAN"))):
            bx = lx + i * (tw + 8)
            act = tab == key
            tg = "gt_" + key
            rr(cv, bx, y1 + 62, bx + tw, y1 + 98, 6,
               fill=mix(G_PANEL, "#ffffff", 0.10) if act else "",
               outline=G_LINE if act else "", tags=(tg,))
            cv.create_text(bx + tw / 2, y1 + 80, text=txt,
                           fill=G_ON if act else G_DIM,
                           font=ui_font(10, True), tags=(tg,))
            if not act:
                cv.tag_bind(tg, "<ButtonRelease-1>",
                            lambda ev, k=key: self._game_tab(k))
                cv.tag_bind(tg, "<Enter>", lambda ev: cv.config(cursor="hand2"))
                cv.tag_bind(tg, "<Leave>", lambda ev: cv.config(cursor=""))
        cv.create_line(lx, y1 + 110, rx, y1 + 110, fill=G_LINE)

        if tab == "macro":
            self._game_page_macro(cv, e, y1, lx, rx, label)
        else:
            self._game_page_tampilan(cv, e, y1, lx, rx, label)

        # ---------- footer ----------
        fy = y2 - 96
        cv.create_line(x1 + 1, fy, x2 - 1, fy, fill=G_LINE)
        cv.create_rectangle(x1 + 1, fy + 1, x2 - 1, y2 - 1,
                            fill=mix(G_PANEL, "#000000", 0.22), outline="")
        rr(cv, x1, y2 - 12, x2, y2, 10 if SHOW_BG else 0,
           fill=mix(G_PANEL, "#000000", 0.22), outline="")
        mid = (x1 + x2) / 2
        self.btn_power = CvButton(cv, lx, fy + 26, mid - 8, fy + 74, "",
                                  e.toggle_enabled, r=6, fill=G_ON,
                                  fg=mix("#000000", G_ON, 0.25), bg=G_PANEL,
                                  font=ui_font(12, True))
        CvButton(cv, mid + 8, fy + 26, rx, fy + 74, "Keluar", self.quit_app,
                 r=6, fill=G_PANEL, fg=G_TXT, bg=G_PANEL, border=G_LINE,
                 font=ui_font(12))
        self.lbl_hint = cv.create_text((x1 + x2) / 2, fy + 17, text="",
                                       fill=G_DIM, font=ui_font(9))
        self.lbl_stats = None
        cv.bind("<ButtonRelease-1>", self._mac_bgclick, add="+")

    def _game_tab(self, key):
        self.close_menu()
        self.gtab = key
        self._build_ui()

    def _game_page_macro(self, cv, e, y1, lx, rx, label):
        # --- macro on/off ---
        label(y1 + 138, "Macro")
        self.sw_power = CvToggle(cv, rx, y1 + 138, e.enabled,
                                 lambda v: e.toggle_enabled())

        # --- kecepatan ---
        label(y1 + 190, "Kecepatan")
        self.lbl_speed = cv.create_text(rx, y1 + 190, anchor="e",
                                        text="%d ms" % e.cfg["speed"],
                                        fill=G_ON, font=mono_font(11, True))
        self.slider = CvGSlider(cv, lx + 128, rx - 76, y1 + 190, 5, 150,
                                int(e.cfg["speed"]),
                                command=lambda v: self._set_speed(v, True))

        # --- jitter (radio) ---
        label(y1 + 268, "Jitter")
        opts = ((0, "mati"), (10, "10%"), (20, "20%"), (30, "30%"))
        step = 76
        x0 = rx - 3 * step
        for i, (val, txt) in enumerate(opts):
            cx = x0 + i * step
            cv.create_text(cx, y1 + 236, text=txt, fill=G_DIM, font=ui_font(10))
            CvRadio(cv, cx, y1 + 268, val, e.jitter == val, self._set_jitter)

        cv.create_line(lx, y1 + 302, rx, y1 + 302, fill=G_LINE)

        # --- checkbox ---
        cv.create_text(lx, y1 + 330, anchor="w", text="Opsi tambahan",
                       fill=G_TXT, font=ui_font(12, True))
        CvCheck(cv, lx + 14, y1 + 368, "Jeda antar tombol (10 ms)", e.gap > 0,
                lambda v: self._game_gap(v))
        CvCheck(cv, lx + 14, y1 + 412, "Mode toggle (bukan tahan)",
                e.mode == "TOGGLE",
                lambda v: self._on_mode("TOGGLE" if v else "HOLD"))

        # --- urutan tombol ---
        label(y1 + 462, "Urutan")
        cur = ",".join(e.sequence)
        popts = [(k.title(), ",".join(v)) for k, v in PRESET_SEQ]
        if cur not in [o[1] for o in popts]:
            popts.append((" · ".join(e.sequence), cur))
        self.pop_seq = CvPopup(cv, self, rx, y1 + 462, popts, cur,
                               lambda v: self._seq_set(v.split(",")),
                               flat=True, w=rx - lx - 128)

        # --- hotkey ---
        label(y1 + 514, "Tombol pemicu")
        self.btn_set = CvButton(cv, rx - 132, y1 + 492, rx, y1 + 536,
                                e.cfg["hotkey"], self.set_hotkey, r=6,
                                fill=mix(G_PANEL, "#000000", 0.30), fg=G_TXT,
                                bg=G_PANEL, border=G_LINE, font=ui_font(12, True))

    def _game_page_tampilan(self, cv, e, y1, lx, rx, label):
        self.sw_power = None

        # --- tema ---
        label(y1 + 150, "Tema warna")
        topts = [(THEMES[k]["label"].title(), k, THEMES[k]["acc"])
                 for k in THEME_ORDER]
        CvPopup(cv, self, rx, y1 + 150, topts, CURRENT_THEME, self._set_theme,
                flat=True, w=rx - lx - 150)

        # --- model tampilan ---
        label(y1 + 214, "Model tampilan")
        CvPopup(cv, self, rx, y1 + 214,
                [("Game menu", "game"), ("macOS", "macos"),
                 ("Minimalis", "minimal"), ("Pro — dua panel", "pro")],
                LAYOUT, self._set_layout, flat=True, w=rx - lx - 150)

        # --- background ---
        label(y1 + 278, "Background senja")
        CvToggle(cv, rx, y1 + 278, SHOW_BG, self._set_bg)

        # --- selalu di atas ---
        label(y1 + 342, "Selalu di atas")
        CvToggle(cv, rx, y1 + 342, self.topmost, self._set_topmost)

        # --- mini overlay ---
        label(y1 + 406, "Mini overlay")
        CvButton(cv, rx - 150, y1 + 384, rx, y1 + 428, "Aktifkan",
                 self.toggle_mini, r=6, fill=mix(G_PANEL, "#000000", 0.30),
                 fg=G_TXT, bg=G_PANEL, border=G_LINE, font=ui_font(11))

        cv.create_line(lx, y1 + 452, rx, y1 + 452, fill=G_LINE)
        label(y1 + 486, "Update  ·  v" + VERSION)
        CvButton(cv, rx - 150, y1 + 464, rx, y1 + 508, "Cek update",
                 self._do_update, r=6, fill=mix(G_PANEL, "#000000", 0.30),
                 fg=G_ON, bg=G_PANEL, border=G_LINE, font=ui_font(11))
        cv.create_text(lx, y1 + 528, anchor="w",
                       text=("link: " + (UPDATE_URL[:52] if UPDATE_URL
                                         else "belum diisi — set di halaman Tentang")),
                       fill=G_DIM, font=ui_font(9))

    def _paste_url(self):
        """Ambil link update dari clipboard."""
        global UPDATE_URL
        try:
            url = self.clipboard_get().strip()
        except Exception:
            url = ""
        if not url.startswith("http"):
            self._flash("clipboard-nya bukan link http")
            return
        UPDATE_URL = url
        self.engine.cfg["update_url"] = url
        save_settings(self.engine.cfg)
        self._build_ui()
        self._flash("link update kesimpen")

    def _do_update(self):
        if not UPDATE_URL:
            self._flash("isi dulu link update-nya")
            return
        self._flash("lagi cek update...")
        self.update_idletasks()
        ver, text, err = check_update(UPDATE_URL)
        if err:
            self._flash(err)
            return
        if _ver_tuple(ver) <= _ver_tuple(VERSION):
            self._flash("udah versi terbaru (%s)" % VERSION)
            return
        err = apply_update(text)
        if err:
            self._flash(err)
            return
        self._flash("update ke v%s berhasil — restart..." % ver)
        self.after(900, restart_app)

    def _set_bg(self, on):
        global SHOW_BG
        SHOW_BG = bool(on)
        self.engine.cfg["show_bg"] = SHOW_BG
        save_settings(self.engine.cfg)
        if self.game:
            self.W, self.H = self._game_size()
            self.win_h = self.H if self.custom_bar else self.H - 46
            self.geometry("%dx%d" % (self.W, self.win_h))
            self._center(self.win_h)
        self._build_ui()

    def _game_gap(self, on):
        self._set_gap(10 if on else 0)
        self._build_ui()

    def _game_capture_modal(self):
        """Panel kecil di tengah waktu lagi ngerekam tombol (ala dialog login)."""
        cv = self.cv
        cv.create_rectangle(0, 0, self.W, self.win_h, fill="#000000",
                            stipple="gray50", outline="", tags=("modal",))
        w, h = 340, 190
        x1 = (self.W - w) / 2
        y1 = (self.win_h - h) / 2
        rr(cv, x1 + 2, y1 + 3, x1 + w + 2, y1 + h + 3, 10,
           fill=mix(G_PANEL, "#000000", 0.6), outline="", tags=("modal",))
        rr(cv, x1, y1, x1 + w, y1 + h, 10, fill=G_PANEL, outline=G_LINE,
           tags=("modal",))
        rr(cv, x1, y1, x1 + w, y1 + 44, 10, fill=mix(G_PANEL, "#000000", 0.38),
           outline="", tags=("modal",))
        cv.create_rectangle(x1, y1 + 30, x1 + w, y1 + 44,
                            fill=mix(G_PANEL, "#000000", 0.38), outline="",
                            tags=("modal",))
        cv.create_line(x1 + 1, y1 + 44, x1 + w - 1, y1 + 44, fill=G_LINE,
                       tags=("modal",))
        cv.create_text(x1 + 18, y1 + 22, anchor="w", text="Rekam tombol",
                       fill=G_TXT, font=ui_font(11, True), tags=("modal",))
        cv.create_text(x1 + w / 2, y1 + 74, text="Tekan tombol apa aja...",
                       fill=G_DIM, font=ui_font(11), tags=("modal",))
        rr(cv, x1 + 40, y1 + 92, x1 + w - 40, y1 + 136, 6, fill="#ffffff",
           outline="", tags=("modal",))
        self.modal_key = cv.create_text(x1 + w / 2, y1 + 114, text="...",
                                        fill="#2a2a2a", font=ui_font(14, True),
                                        tags=("modal",))
        tg = "modalx"
        cv.create_text(x1 + w - 22, y1 + 22, text="✕", fill=G_TXT,
                       font=ui_font(11), tags=("modal", tg))
        cv.create_rectangle(x1 + w - 40, y1 + 4, x1 + w - 4, y1 + 40, fill="",
                            outline="", tags=("modal", tg))
        cv.tag_bind(tg, "<ButtonRelease-1>", lambda e: self._game_modal_close())
        cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))

    def _game_modal_close(self):
        self.engine.capture_mode = False
        self.cv.delete("modal")

    def _refresh_game(self):
        e = self.engine
        if getattr(self, "sw_power", None) is not None:
            try:
                self.sw_power.set(e.enabled)
            except tk.TclError:
                self.sw_power = None
        self.btn_power.set_text("MATIIN  (F2)" if e.enabled else "NYALAIN  (F2)")
        self.btn_power.set_style(G_ON if e.enabled
                                 else mix(G_PANEL, "#ffffff", 0.12),
                                 mix("#000000", G_ON, 0.25) if e.enabled
                                 else G_TXT, show_glow=False)

    def _tick_game(self):
        e = self.engine
        if e.spamming:
            txt = "%s  ·  %.1f keys/s  ·  %s tekan" % (
                " → ".join(e.sequence[:4]), e.keys_per_sec(), f"{e.presses:,}")
            col = G_ON
        elif e.enabled:
            verb = "tahan" if e.mode == "HOLD" else "tekan"
            txt = "%s '%s' buat mulai spam" % (verb, e.cfg["hotkey"])
            col = G_DIM
        else:
            txt = "macro lagi mati"
            col = G_DIM
        if e.enabled and is_app_focused(self):
            txt, col = "klik ke jendela game dulu", RED
        self.cv.itemconfig(self.lbl_hint, text=txt, fill=col)

    # ======================================================================
    #  MINI OVERLAY — tiap tema punya bentuk UI sendiri
    # ======================================================================
    MINI_SIZE = {"emas": (304, 74), "cyan": (334, 66), "ungu": (252, 92),
                 "merah": (322, 72), "hijau": (322, 64)}

    def _mini_size(self):
        return self.MINI_SIZE.get(CURRENT_THEME, (self.MW, self.MH))

    def _mini_seq_text(self, maxlen=11):
        seq = self.engine.sequence
        txt = " ".join(seq[:3]) + ("…" if len(seq) > 3 else "")
        if len(txt) > maxlen:
            txt = " ".join(seq[:2]) + "…"
        return txt

    def _mini_btns(self, x, cy, style="soft"):
        """Tombol ⤢ (balik gede) + ✕ (keluar)."""
        cv = self.cv
        if style == "flat":
            for dx, ch, cmd in ((0, "⤢", self.toggle_mini),
                                (26, "✕", self.quit_app)):
                tg = "mb%d" % dx
                cv.create_text(x + dx, cy, text=ch, fill=mix(MUTED, GOLD, 0.4),
                               font=ui_font(10), tags=(tg,))
                cv.create_rectangle(x + dx - 12, cy - 12, x + dx + 12, cy + 12,
                                    fill="", outline="", tags=(tg,))
                cv.tag_bind(tg, "<ButtonRelease-1>", lambda e, c=cmd: c())
                cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
                cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
            return
        bg = mix(CARD_HI, GOLD, 0.14)
        CvButton(cv, x, cy - 14, x + 28, cy + 14, "⤢", self.toggle_mini, r=8,
                 fill=bg, fg=mix(MUTED, GOLD, 0.5), bg=BG_BOT,
                 border=mix(BORDER, GOLD, 0.35), font=ui_font(10, True))
        CvButton(cv, x + 34, cy - 14, x + 60, cy + 14, "✕", self.quit_app, r=8,
                 fill=bg, fg=mix(MUTED, GOLD, 0.5), bg=BG_BOT,
                 border=mix(BORDER, GOLD, 0.35), font=ui_font(9, True))

    def _build_mini(self):
        """Bentuk overlay-nya ngikut tema yang lagi dipakai."""
        cv = self.cv
        self.m_dot = self.m_state = self.m_stats = self.m_seq = None
        self.m_bars = []
        self.m_arc = self.m_cursor = self.m_line = None
        self.mini_kind = CURRENT_THEME
        {"cyan": self._mini_hud, "ungu": self._mini_capsule,
         "merah": self._mini_tag,
         "hijau": self._mini_term}.get(CURRENT_THEME, self._mini_bar)()
        cv.tag_bind("mbar", "<Button-1>", self._drag_start)
        cv.tag_bind("mbar", "<B1-Motion>", self._drag_move)

    # ---------------------------------------------------- emas: bar klasik
    def _mini_bar(self):
        cv = self.cv
        w, h = self.MW, self.MH
        top, bot = mix(BG_TOP, GOLD, 0.10), mix(BG_BOT, GOLD, 0.05)
        vgrad(cv, 0, 0, w, h, top, bot, steps=26, tags=("mbar",))
        rr(cv, 1, 1, w - 1, h - 1, 14, fill="",
           outline=mix(BORDER, GOLD, 0.45), tags=("mbar",))
        cy = h / 2
        glow(cv, 8, cy, 26, GOLD, mix(top, bot, 0.5), layers=16, power=2.6,
             tags=("mbar",))
        rr(cv, 6, cy - 18, 10, cy + 18, 2, fill=GOLD, outline="", tags=("mbar",))
        self.m_dot = cv.create_oval(20, cy - 5, 30, cy + 5, fill=GOLD,
                                    outline="", tags=("mbar",))
        self.m_state = cv.create_text(40, cy - 10, anchor="w", text="AKTIF",
                                      fill=GOLD, font=ui_font(9, True),
                                      tags=("mbar",))
        self.m_stats = cv.create_text(40, cy + 10, anchor="w", text="0.0 keys/s",
                                      fill=mix(DIM, GOLD, 0.35),
                                      font=ui_font(8), tags=("mbar",))
        txt = self._mini_seq_text()
        bx2 = w - 74
        bx1 = bx2 - max(58, ui_font(8, True).measure(txt) + 18)
        rr(cv, bx1, cy - 13, bx2, cy + 13, 8, fill=mix(CARD_HI, GOLD, 0.22),
           outline=mix(BORDER, GOLD, 0.55), tags=("mbar",))
        self.m_seq = cv.create_text((bx1 + bx2) / 2, cy, text=txt, fill=GOLD,
                                    font=ui_font(8, True), tags=("mbar",))
        self._mini_btns(w - 68, cy)

    # -------------------------------------------------- cyan: HUD + bar EQ
    def _mini_hud(self):
        cv = self.cv
        w, h = self.MW, self.MH
        bg = mix(BG_TOP, GOLD, 0.12)
        cv.create_rectangle(0, 0, w, h, fill=bg, outline="", tags=("mbar",))
        rr(cv, 1, 1, w - 1, h - 1, 6, fill="", outline=mix(BORDER, GOLD, 0.6),
           tags=("mbar",))
        # garis status tipis di atas
        self.m_line = cv.create_rectangle(1, 1, w - 1, 4, fill=GOLD,
                                          outline="", tags=("mbar",))
        cy = h / 2
        self.m_stats = cv.create_text(16, cy - 4, anchor="w", text="0.0",
                                      fill=GOLD, font=mono_font(17, True),
                                      tags=("mbar",))
        cv.create_text(17, cy + 16, anchor="w", text="KEYS / SEC", fill=DIM,
                       font=ui_font(6, True), tags=("mbar",))
        self.m_state = cv.create_text(w - 74, 14, anchor="e", text="AKTIF",
                                      fill=GOLD, font=ui_font(7, True),
                                      tags=("mbar",))
        self.m_seq = cv.create_text(w - 74, h - 14, anchor="e",
                                    text=self._mini_seq_text(14),
                                    fill=mix(DIM, GOLD, 0.4),
                                    font=mono_font(8), tags=("mbar",))
        # equalizer
        bw, gap, n = 4, 3, 14
        x0 = 96
        for i in range(n):
            bx = x0 + i * (bw + gap)
            self.m_bars.append(cv.create_rectangle(
                bx, cy + 12, bx + bw, cy + 14, fill=mix(GOLD, bg, 0.55),
                outline="", tags=("mbar",)))
        self._mini_btns(w - 42, cy, style="flat")

    # ------------------------------------------------- ungu: kapsul + ring
    def _mini_capsule(self):
        cv = self.cv
        w, h = self.MW, self.MH
        top, bot = mix(BG_TOP, GOLD, 0.16), mix(BG_BOT, GOLD, 0.08)
        vgrad(cv, 0, 0, w, h, top, bot, steps=26, tags=("mbar",))
        rr(cv, 2, 2, w - 2, h - 2, h / 2 - 2, fill="",
           outline=mix(BORDER, GOLD, 0.6), width=1, tags=("mbar",))
        cx, cy = 46, h / 2
        glow(cv, cx, cy, 34, GOLD, mix(top, bot, 0.5), layers=18, power=2.8,
             tags=("mbar",))
        cv.create_oval(cx - 26, cy - 26, cx + 26, cy + 26, fill="",
                       outline=mix(CARD_HI, GOLD, 0.25), width=5,
                       tags=("mbar",))
        self.m_arc = cv.create_arc(cx - 26, cy - 26, cx + 26, cy + 26,
                                   start=90, extent=-1, style="arc",
                                   outline=GOLD, width=5, tags=("mbar",))
        self.m_state = cv.create_text(cx, cy, text="ON", fill=GOLD,
                                      font=ui_font(10, True), tags=("mbar",))
        self.m_stats = cv.create_text(88, cy - 12, anchor="w", text="0.0 k/s",
                                      fill=GOLD, font=mono_font(11, True),
                                      tags=("mbar",))
        self.m_seq = cv.create_text(88, cy + 10, anchor="w",
                                    text=self._mini_seq_text(9),
                                    fill=mix(DIM, GOLD, 0.35),
                                    font=ui_font(8, True), tags=("mbar",))
        bg = mix(CARD_HI, GOLD, 0.18)
        CvButton(cv, w - 46, 14, w - 14, 42, "⤢", self.toggle_mini, r=14,
                 fill=bg, fg=mix(MUTED, GOLD, 0.5), bg=bot,
                 border=mix(BORDER, GOLD, 0.4), font=ui_font(9, True))
        CvButton(cv, w - 46, h - 42, w - 14, h - 14, "✕", self.quit_app, r=14,
                 fill=bg, fg=mix(MUTED, GOLD, 0.5), bg=bot,
                 border=mix(BORDER, GOLD, 0.4), font=ui_font(8, True))

    # --------------------------------------------- merah: gamer tag runcing
    def _mini_tag(self):
        cv = self.cv
        w, h = self.MW, self.MH
        bg = mix(BG_TOP, GOLD, 0.14)
        n = 14
        cv.create_polygon(0, 0, w, 0, w, h - n, w - n, h, 0, h,
                          fill=bg, outline=mix(BORDER, GOLD, 0.55),
                          tags=("mbar",))
        cy = h / 2
        cv.create_polygon(0, 0, 16, 0, 8, h, 0, h, fill=GOLD, outline="",
                          tags=("mbar",))
        self.m_stats = cv.create_text(30, cy - 6, anchor="w", text="0.0",
                                      fill=GOLD, font=mono_font(16, True),
                                      tags=("mbar",))
        cv.create_text(31, cy + 14, anchor="w", text="KEYS/S", fill=DIM,
                       font=ui_font(6, True), tags=("mbar",))
        self.m_state = cv.create_text(112, cy - 6, anchor="w", text="AKTIF",
                                      fill=GOLD, font=ui_font(10, True),
                                      tags=("mbar",))
        self.m_dot = cv.create_rectangle(112, cy + 8, 152, cy + 12, fill=GOLD,
                                         outline="", tags=("mbar",))
        # tombol urutan sebagai kotak kecil
        x = 186
        for k in self.engine.sequence[:3]:
            cv.create_rectangle(x, cy - 12, x + 24, cy + 12,
                                fill=mix(CARD_HI, GOLD, 0.2),
                                outline=mix(BORDER, GOLD, 0.5), tags=("mbar",))
            cv.create_text(x + 12, cy, text=k[:2], fill=GOLD,
                           font=ui_font(7, True), tags=("mbar",))
            x += 28
        for dx, ch, cmd in ((0, "⤢", self.toggle_mini), (28, "✕", self.quit_app)):
            bx = w - 58 + dx
            tg = "tagb%d" % dx
            cv.create_rectangle(bx, cy - 12, bx + 24, cy + 12, fill="",
                                outline=mix(BORDER, GOLD, 0.5), tags=(tg,))
            cv.create_text(bx + 12, cy, text=ch, fill=mix(MUTED, GOLD, 0.5),
                           font=ui_font(8, True), tags=(tg,))
            cv.tag_bind(tg, "<ButtonRelease-1>", lambda e, c=cmd: c())
            cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))

    # ------------------------------------------------- hijau: gaya terminal
    def _mini_term(self):
        cv = self.cv
        w, h = self.MW, self.MH
        bg = mix(BG_TOP, "#000000", 0.35)
        cv.create_rectangle(0, 0, w, h, fill=bg, outline="", tags=("mbar",))
        rr(cv, 1, 1, w - 1, h - 1, 4, fill="", outline=mix(BORDER, GOLD, 0.7),
           tags=("mbar",))
        cv.create_rectangle(1, 1, w - 1, 18, fill=mix(bg, GOLD, 0.12),
                            outline="", tags=("mbar",))
        cv.create_text(8, 9, anchor="w", text="moonwalk@macro:~", fill=DIM,
                       font=mono_font(7), tags=("mbar",))
        for dx, ch, cmd in ((0, "[ ]", self.toggle_mini),
                            (28, "[x]", self.quit_app)):
            tg = "trm%d" % dx
            cv.create_text(w - 46 + dx, 9, text=ch, fill=mix(MUTED, GOLD, 0.5),
                           font=mono_font(7), tags=(tg,))
            cv.create_rectangle(w - 58 + dx, 1, w - 34 + dx, 18, fill="",
                                outline="", tags=(tg,))
            cv.tag_bind(tg, "<ButtonRelease-1>", lambda e, c=cmd: c())
            cv.tag_bind(tg, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(tg, "<Leave>", lambda e: cv.config(cursor=""))
        cv.create_text(8, 32, anchor="w", text="$ spam", fill=mix(DIM, GOLD, 0.3),
                       font=mono_font(9), tags=("mbar",))
        self.m_seq = cv.create_text(58, 32, anchor="w",
                                    text=self._mini_seq_text(16), fill=GOLD,
                                    font=mono_font(9, True), tags=("mbar",))
        self.m_stats = cv.create_text(8, 50, anchor="w", text="> 0.0 keys/s",
                                      fill=mix(DIM, GOLD, 0.25),
                                      font=mono_font(8), tags=("mbar",))
        self.m_state = cv.create_text(w - 12, 50, anchor="e", text="[RUNNING]",
                                      fill=GOLD, font=mono_font(8, True),
                                      tags=("mbar",))
        self.m_cursor = cv.create_rectangle(0, 0, 0, 0, fill=GOLD, outline="",
                                            tags=("mbar",))

    # ------------------------------------------------------ update per gaya
    def _refresh_mini(self, en):
        cv = self.cv
        c = GOLD if en else RED
        kind = getattr(self, "mini_kind", "emas")
        if self.m_dot is not None:
            cv.itemconfig(self.m_dot, fill=c)
        if self.m_line is not None:
            cv.itemconfig(self.m_line, fill=c)
        if self.m_arc is not None:
            cv.itemconfig(self.m_arc, outline=c)
        if self.m_state is not None:
            if kind == "ungu":
                txt = "ON" if en else "OFF"
            elif kind == "hijau":
                txt = "[RUNNING]" if en else "[STOPPED]"
            else:
                txt = "AKTIF" if en else "MATI"
            cv.itemconfig(self.m_state, text=txt, fill=c)

    def _tick_mini(self, kps, spamming):
        cv = self.cv
        kind = getattr(self, "mini_kind", "emas")
        act = GOLD if spamming else mix(DIM, GOLD, 0.35)
        if kind == "cyan":
            cv.itemconfig(self.m_stats, text="%.1f" % kps, fill=act)
            lvl = min(1.0, kps / 90.0)
            for i, b in enumerate(self.m_bars):
                x1, _, x2, _ = cv.coords(b)
                amp = lvl * (0.35 + 0.65 * random.random()) if spamming else 0.04
                cy = self.MH / 2
                cv.coords(b, x1, cy + 14 - max(2, amp * 30), x2, cy + 14)
                cv.itemconfig(b, fill=mix(GOLD, mix(BG_TOP, GOLD, 0.12),
                                          0.15 if spamming else 0.7))
        elif kind == "ungu":
            cv.itemconfig(self.m_stats, text="%.1f k/s" % kps, fill=act)
            frac = min(1.0, kps / 90.0)
            cv.itemconfig(self.m_arc, extent=-max(1, 359 * frac))
        elif kind == "hijau":
            cv.itemconfig(self.m_stats, text="> %.1f keys/s" % kps, fill=act)
            x = 106 + mono_font(8).measure("> %.1f keys/s" % kps) - 96
            on = spamming and int(time.time() * 2) % 2 == 0
            cv.coords(self.m_cursor, x, 45, x + 7, 56) if on else \
                cv.coords(self.m_cursor, 0, 0, 0, 0)
        else:
            cv.itemconfig(self.m_stats,
                          text=("%.1f" % kps) if kind == "merah"
                          else ("%.1f keys/s" % kps), fill=act)

    def toggle_mini(self):
        self.mini = not self.mini
        if self.mini:
            self._full_pos = (self.winfo_x(), self.winfo_y())
            self.MW, self.MH = self._mini_size()
            self.win_h = self.MH
            self.geometry("%dx%d" % (self.MW, self.MH))
            try:
                self.overrideredirect(True)
                self.attributes("-alpha", 0.92)
            except Exception:
                pass
        else:
            self.win_h = self.H if self.custom_bar else self.H - 46
            self.geometry("%dx%d" % (self.W, self.win_h))
            try:
                self.overrideredirect(self.custom_bar)
                self.attributes("-alpha", 1.0)
            except Exception:
                pass
            x, y = getattr(self, "_full_pos", (None, None))
            if x is not None:
                self.geometry("+%d+%d" % (x, y))
        self._build_ui()
        round_window_corners(self)

    # --------------------------------------------------------------- aksi
    def _on_mode(self, value):
        self.engine.set_mode(value)
        self.refresh()

    def _set_speed(self, val, from_slider=False):
        self.engine.set_speed(val)
        if not from_slider:
            self.slider.set(self.engine.cfg["speed"])
        cur = self.engine.cfg["speed"]
        self.cv.itemconfig(self.lbl_speed, text="%d ms" % cur)
        if self.minimal or self.macos or self.game:
            return
        for b in self.chips:
            on = b.preset == cur
            b.set_style(GOLD if on else CARD_HI, on_accent() if on else MUTED)

    def _set_jitter(self, val):
        self.engine.set_jitter(val)
        for b in self.jchips:
            on = b.preset == self.engine.jitter
            b.set_style(GOLD if on else CARD_HI, on_accent() if on else MUTED)

    def set_hotkey(self):
        if self.game:
            self.capture_for = "hotkey"
            self.engine.captured_vk = 0
            self.engine.capture_mode = True
            self._game_capture_modal()
            self.after(60, self._poll_capture)
            return
        if self.minimal or self.macos:
            self.capture_for = "hotkey"
            self.engine.captured_vk = 0
            self.engine.capture_mode = True
            self.btn_set.set_text("...")
            self.btn_set.set_style(GOLD, on_accent())
            self.after(60, self._poll_capture)
            return
        typed = self.var_hotkey.get().strip()
        if typed and vk_from_name(typed) and typed.upper() != self.engine.cfg["hotkey"]:
            self.engine.set_hotkey(typed)
            self.var_hotkey.set(typed.upper())
            self._flash("✓ hotkey: " + typed.upper())
            return
        self.capture_for = "hotkey"
        self.engine.captured_vk = 0
        self.engine.capture_mode = True
        self.var_hotkey.set("tekan tombol...")
        self.btn_set.set_style(CARD_HI, GOLD)
        self.after(60, self._poll_capture)

    def _poll_capture(self):
        if self.engine.capture_mode:
            self.after(60, self._poll_capture)
            return
        vk = self.engine.captured_vk
        name = name_from_vk(vk) if vk else None
        if self.capture_for == "seq":
            if name and sc_from_name(name)[0]:
                self._seq_set(list(self.engine.sequence) + [name])
                self._flash("✓ ditambah: " + name)
            else:
                self._flash("tombol itu nggak bisa dipakai")
                self._build_ui()
            return
        if self.game:
            if name:
                self.engine.set_hotkey(name)
                self.cv.itemconfig(self.modal_key, text=name)
                self.after(350, lambda: (self.cv.delete("modal"),
                                         self._build_ui()))
            else:
                self.cv.delete("modal")
            return
        if self.minimal or self.macos:
            if name:
                self.engine.set_hotkey(name)
                self.btn_set.set_text(name)
                self.btn_set.set_style(CARD_HI, GOLD)
                self._flash("✓ hotkey: " + name)
            else:
                self.btn_set.set_style(CARD_HI, GOLD)
            return
        self.btn_set.set_style(GOLD, on_accent())
        if name:
            self.engine.set_hotkey(name)
            self.var_hotkey.set(name)
            self._flash("✓ hotkey: " + name)
        else:
            self.var_hotkey.set(self.engine.cfg["hotkey"])

    def _flash(self, msg):
        if self.game:
            self.cv.itemconfig(self.lbl_hint, text=msg, fill=G_ON)
            return
        if self.macos:
            self.cv.itemconfig(self.mac_foot, text=msg, fill=GREEN)
            return
        if self.mini or getattr(self, "lbl_hint", None) is None:
            return
        self.cv.itemconfig(self.lbl_hint, text=msg, fill=GREEN)
        self.after(2200, lambda: self.cv.itemconfig(self.lbl_hint,
                                                    text="F2 = ON / OFF", fill=DIM))

    def refresh(self):
        en = self.engine.enabled
        if self.mini:
            self._refresh_mini(en)
            return
        if self.game:
            self._refresh_game()
            return
        if self.macos:
            self._refresh_mac()
            return
        if self.minimal:
            self._refresh_min()
            return
        self.pill.set_state(en)
        self.btn_power.set_style(GOLD if en else CARD_HI,
                                 on_accent() if en else MUTED, show_glow=en)
        if self.tab == "macro":
            self._set_speed(self.engine.cfg["speed"])
            self._set_jitter(self.engine.jitter)

    def _tick(self):
        e = self.engine
        if self.cv is None or not self.cv.winfo_exists():
            self.after(60, self._tick)
            return
        kps = e.keys_per_sec()
        if self.mini:
            self._tick_mini(kps, e.spamming)
            self.after(60, self._tick)
            return
        if self.game:
            self._tick_game()
            self.after(40, self._tick)
            return
        if self.macos:
            self._tick_mac()
            self.after(40, self._tick)
            return
        if self.minimal:
            self._tick_min()
            self.after(40, self._tick)
            return
        self.pill.tick()
        # baris action nyala pas tombolnya lagi dikirim
        for r in self.rows:
            r["level"] = 1.0 if e.active_key == r["key"] else max(0.0, r["level"] - 0.28)
            L = r["level"]
            self.cv.itemconfig(r["body"], fill=mix(CARD_HI, GOLD, L * 0.55),
                               outline=(GOLD if r["sel"] else
                                        mix(mix(CARD_HI, "#ffffff", 0.05), GOLD, L)))
            self.cv.itemconfig(r["chip"], fill=mix(mix(CARD_HI, GOLD, 0.12), GOLD, L))
            self.cv.itemconfig(r["txt"], fill=mix(GOLD, on_accent(), L))
            self.cv.itemconfig(r["desc"], fill=mix(DIM, on_accent(), L))
        if e.spamming:
            t = time.time()
            base = 0.35 + min(0.65, kps / 45.0)
            wave = 0.55 + 0.45 * abs(math.sin(t * 7.5)) * abs(math.cos(t * 3.1))
            level = base * wave
        else:
            level = 0.0
        self.viz.push(min(1.0, level))
        self.cv.itemconfig(self.lbl_stats,
                           text="%s tekan  ·  %.1f keys/s" % (f"{e.presses:,}", kps),
                           fill=GOLD if e.spamming else DIM)
        self.after(33, self._tick)

    def quit_app(self):
        self.engine.shutdown()
        self.destroy()
        os._exit(0)


def is_app_focused(root):
    """True kalau jendela macro ini yang lagi aktif (bukan game)."""
    if not IS_WINDOWS:
        return False
    try:
        fg = ctypes.windll.user32.GetForegroundWindow()
        mine = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        return fg == mine
    except Exception:
        return False


def round_window_corners(root):
    """Sudut jendela membulat (Windows 11)."""
    if not IS_WINDOWS:
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)   # DWMWCP_ROUND
    except Exception:
        pass


def main():
    enable_dpi_awareness()
    if not IS_WINDOWS:
        print("Program ini khusus Windows.")
    App(MacroEngine()).mainloop()


if __name__ == "__main__":
    main()
