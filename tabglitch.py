import customtkinter as ctk
import psutil
import ctypes
import ctypes.wintypes
import time
import json
import os
import sys
from pynput import keyboard as pynput_kb
from pynput import mouse as pynput_ms


#  windows api pra freezar  e desfreezar o processo do roblox
_ntdll = ctypes.WinDLL("ntdll")
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_PROCESS_SUSPEND_RESUME = 0x0800


def _suspend(pid):
    h = _kernel32.OpenProcess(_PROCESS_SUSPEND_RESUME, False, pid)
    if h:
        _ntdll.NtSuspendProcess(h)
        _kernel32.CloseHandle(h)
        return True
    return False


def _resume(pid):
    h = _kernel32.OpenProcess(_PROCESS_SUSPEND_RESUME, False, pid)
    if h:
        _ntdll.NtResumeProcess(h)
        _kernel32.CloseHandle(h)
        return True
    return False


def _find_roblox():
    for p in psutil.process_iter(["name", "pid"]):
        try:
            n = p.info["name"]
            if n and n.lower().startswith("robloxplayer"):
                return p.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


# persistencia da config

_CFG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(sys.argv[0])), "tabglitch_config.json"
)
_DEFAULTS = {"keybind": "mouse_x2", "mode": "hold"}


def _load_cfg():
    try:
        with open(_CFG_PATH, "r", encoding="utf-8") as f:
            return {**_DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return _DEFAULTS.copy()


def _save_cfg(cfg):
    try:
        with open(_CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except PermissionError:
        pass


# keybinds

_MOUSE_DEFS = [
    ("left",   "Mouse Left",        "mouse_left"),
    ("right",  "Mouse Right",       "mouse_right"),
    ("middle", "Mouse Middle (M3)", "mouse_middle"),
    ("x1",     "Mouse 4 (Back)",    "mouse_x1"),
    ("x2",     "Mouse 5 (Forward)", "mouse_x2"),
]

_BTN_DISPLAY = {}  
_BTN_ID = {}        
_ID_DISPLAY = {}    

for _attr, _disp, _mid in _MOUSE_DEFS:
    _btn = getattr(pynput_ms.Button, _attr, None)
    if _btn is not None:
        _BTN_DISPLAY[_btn] = _disp
        _BTN_ID[_btn] = _mid
        _ID_DISPLAY[_mid] = _disp


def _key_id(key):
    """Pynput key/button → serialisable string id."""
    if isinstance(key, pynput_ms.Button):
        return _BTN_ID.get(key, f"mouse_{key.name}")
    if isinstance(key, pynput_kb.Key):
        return f"key_{key.name}"
    if isinstance(key, pynput_kb.KeyCode):
        if key.char is not None:
            return f"char_{key.char.lower()}"
        if key.vk is not None:
            return f"vk_{key.vk}"
    return str(key)


def _display(kid):
    """String id → user-friendly label."""
    if kid in _ID_DISPLAY:
        return _ID_DISPLAY[kid]
    if kid.startswith("key_"):
        return kid[4:].replace("_", " ").title()
    if kid.startswith("vk_"):
        vk = int(kid[3:])
        if 65 <= vk <= 90:
            return chr(vk)
        if 48 <= vk <= 57:
            return chr(vk)
        if 112 <= vk <= 123:
            return f"F{vk - 111}"
        return f"VK {vk}"
    if kid.startswith("char_"):
        return kid[5:].upper()
    return kid


# 

class TabGlitchApp(ctk.CTk):

    # cores
    C_ACCENT    = "#58a6ff"
    C_BG_CARD   = "#161b22"
    C_BG        = "#0d1117"
    C_TEXT      = "#c9d1d9"
    C_DIM       = "#8b949e"
    C_GREEN     = "#3fb950"
    C_RED       = "#f85149"
    C_YELLOW    = "#d29922"
    C_PURPLE    = "#bc8cff"

    def __init__(self):
        super().__init__()
        self.cfg = _load_cfg()
        self.capturing = False
        self.frozen = False
        self.frozen_pid = None
        self.enabled = False

        self.title("tabglitch - joao")
        self.geometry("420x600")
        self.resizable(False, False)
        self.configure(fg_color=self.C_BG)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        ctk.set_appearance_mode("dark")

        self._build()
        self._start_listeners()
        self._poll_roblox()

    # ui

    def _build(self):
        self._header()
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=20, pady=15)
        self._status_card(wrap)
        self._keybind_card(wrap)
        self._mode_card(wrap)
        self._toggle_card(wrap)
        self._log_card(wrap)
        self._log("auto explicativo")

    def _header(self):
        hdr = ctk.CTkFrame(self, fg_color=self.C_BG_CARD, corner_radius=0, height=80)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        mid = ctk.CTkFrame(hdr, fg_color="transparent")
        mid.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(mid, text="tabglitch",
                     font=ctk.CTkFont("Segoe UI", 28, "bold"),
                     text_color=self.C_ACCENT).pack()
        ctk.CTkLabel(mid, text="piggas",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=self.C_DIM).pack()
        ctk.CTkFrame(self, fg_color=self.C_ACCENT, height=2,
                     corner_radius=0).pack(fill="x")

    # status 
    def _status_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.C_BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=14)
        ctk.CTkLabel(inner, text="STATUS",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=self.C_DIM).pack(anchor="w")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        self.dot = ctk.CTkLabel(row, text="●", font=ctk.CTkFont(size=14),
                                text_color=self.C_RED)
        self.dot.pack(side="left")
        self.status_lbl = ctk.CTkLabel(row, text="Roblox not detected",
                                       font=ctk.CTkFont("Segoe UI", 13),
                                       text_color=self.C_TEXT)
        self.status_lbl.pack(side="left", padx=(8, 0))
        self.freeze_badge = ctk.CTkLabel(row, text="",
                                         font=ctk.CTkFont("Segoe UI", 12, "bold"),
                                         text_color=self.C_YELLOW)
        self.freeze_badge.pack(side="right")

    # keybind config
    def _keybind_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.C_BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=14)
        ctk.CTkLabel(inner, text="KEYBIND",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=self.C_DIM).pack(anchor="w")
        ctk.CTkLabel(inner,
                     text="Click the button, then press any key or mouse button",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=self.C_DIM).pack(anchor="w", pady=(2, 8))
        self.kb_btn = ctk.CTkButton(
            inner, text=_display(self.cfg["keybind"]),
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color="#21262d", hover_color="#30363d",
            border_color=self.C_ACCENT, border_width=2,
            corner_radius=8, height=45, text_color=self.C_ACCENT,
            command=self._capture_start)
        self.kb_btn.pack(fill="x")

    # modos
    def _mode_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.C_BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=14)
        ctk.CTkLabel(inner, text="MODE",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=self.C_DIM).pack(anchor="w")
        ctk.CTkLabel(inner,
                     text="Hold = freeze while pressed  ·  Toggle = click on / click off",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=self.C_DIM).pack(anchor="w", pady=(2, 10))
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self._mode_var = ctk.StringVar(value=self.cfg.get("mode", "hold"))
        self.btn_hold = ctk.CTkButton(
            row, text="🔒  HOLD",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            corner_radius=8, height=42, width=170,
            command=lambda: self._set_mode("hold"))
        self.btn_hold.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.btn_toggle = ctk.CTkButton(
            row, text="🔄  TOGGLE",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            corner_radius=8, height=42, width=170,
            command=lambda: self._set_mode("toggle"))
        self.btn_toggle.pack(side="right", expand=True, fill="x", padx=(6, 0))
        self._update_mode_btns()

    # toggle de novo
    def _toggle_card(self, parent):
        self.toggle_btn = ctk.CTkButton(
            parent, text="▶  ENABLE",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            fg_color="#238636", hover_color="#2ea043",
            corner_radius=12, height=55, command=self._toggle)
        self.toggle_btn.pack(fill="x", pady=(4, 12))

    # logs
    def _log_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.C_BG_CARD, corner_radius=12)
        card.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=12)
        ctk.CTkLabel(inner, text="LOG",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=self.C_DIM).pack(anchor="w")
        self.log_box = ctk.CTkTextbox(
            inner, font=ctk.CTkFont("Consolas", 11),
            fg_color=self.C_BG, text_color=self.C_DIM,
            corner_radius=8, height=80, state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(5, 0))

    # burbaloni

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    #  keybind capture

    def _capture_start(self):
        self.kb_btn.configure(
            text="⌨  Press any key…",
            fg_color="#30363d", border_color=self.C_YELLOW,
            text_color=self.C_YELLOW)
        self._log("Waiting for input… (ESC to cancel)")
        # delay pequeno pra evitar que o clique do botao seja capturado como keybind
        self.after(250, self._capture_arm)

    def _capture_arm(self):
        self.capturing = True

    def _capture_finish(self, kid):
        self.capturing = False
        self.cfg["keybind"] = kid
        _save_cfg(self.cfg)
        self.kb_btn.configure(
            text=_display(kid), fg_color="#21262d",
            border_color=self.C_ACCENT, text_color=self.C_ACCENT)
        self._log(f"Keybind → {_display(kid)}")

    def _capture_cancel(self):
        self.capturing = False
        self.kb_btn.configure(
            text=_display(self.cfg["keybind"]), fg_color="#21262d",
            border_color=self.C_ACCENT, text_color=self.C_ACCENT)
        self._log("Capture cancelled.")

    # mode

    def _set_mode(self, mode):
        self.cfg["mode"] = mode
        self._mode_var.set(mode)
        _save_cfg(self.cfg)
        self._update_mode_btns()
        self._log(f"Mode → {mode.upper()}")

    def _update_mode_btns(self):
        m = self._mode_var.get()
        if m == "hold":
            self.btn_hold.configure(fg_color=self.C_PURPLE, hover_color="#d2a8ff",
                                    text_color="#0d1117")
            self.btn_toggle.configure(fg_color="#21262d", hover_color="#30363d",
                                      text_color=self.C_DIM)
        else:
            self.btn_toggle.configure(fg_color=self.C_PURPLE, hover_color="#d2a8ff",
                                      text_color="#0d1117")
            self.btn_hold.configure(fg_color="#21262d", hover_color="#30363d",
                                    text_color=self.C_DIM)

    # toggle
    def _toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.toggle_btn.configure(
                text="■  DISABLE", fg_color=self.C_RED,
                hover_color="#da3633")
            self._log("ENABLED — listening for keybind.")
        else:
            self.toggle_btn.configure(
                text="▶  ENABLE", fg_color="#238636",
                hover_color="#2ea043")
            self._log("DISABLED.")

    # logica do tab glitch

    def _freeze_start(self):
        if self.frozen:
            return
        pid = _find_roblox()
        if pid is None:
            self.after(0, lambda: self._log("Roblox not found!"))
            return
        if _suspend(pid):
            self.frozen = True
            self.frozen_pid = pid
            self.after(0, lambda: self.freeze_badge.configure(text="⚡ FROZEN"))
            self.after(0, lambda: self._log("Frozen."))
        else:
            self.after(0, lambda: self._log("Failed to freeze!"))

    def _freeze_stop(self):
        if not self.frozen:
            return
        pid = self.frozen_pid
        if pid is not None:
            _resume(pid)
        self.frozen = False
        self.frozen_pid = None
        self.after(0, lambda: self.freeze_badge.configure(text=""))
        self.after(0, lambda: self._log("Resumed."))

    # inputs

    def _start_listeners(self):
        self._kbl = pynput_kb.Listener(on_press=self._on_key_press,
                                       on_release=self._on_key_release)
        self._msl = pynput_ms.Listener(on_click=self._on_click)
        self._kbl.daemon = True
        self._msl.daemon = True
        self._kbl.start()
        self._msl.start()

    def _on_key_press(self, key):
        if self.capturing:
            if isinstance(key, pynput_kb.Key) and key == pynput_kb.Key.esc:
                self.after(0, self._capture_cancel)
                return
            kid = _key_id(key)
            self.after(0, lambda: self._capture_finish(kid))
            return
        if not self.enabled or _key_id(key) != self.cfg["keybind"]:
            return
        if self.cfg["mode"] == "hold":
            self._freeze_start()
        else:
            if self.frozen:
                self._freeze_stop()
            else:
                self._freeze_start()

    def _on_key_release(self, key):
        if not self.enabled or _key_id(key) != self.cfg["keybind"]:
            return
        if self.cfg["mode"] == "hold":
            self._freeze_stop()

    def _on_click(self, _x, _y, button, pressed):
        kid = _key_id(button)
        if pressed and self.capturing:
            self.after(0, lambda: self._capture_finish(kid))
            return
        if not self.enabled or kid != self.cfg["keybind"]:
            return
        if self.cfg["mode"] == "hold":
            if pressed:
                self._freeze_start()
            else:
                self._freeze_stop()
        else:
            if pressed:
                if self.frozen:
                    self._freeze_stop()
                else:
                    self._freeze_start()

    # loop d deteccao do boblox

    def _poll_roblox(self):
        pid = _find_roblox()
        if pid:
            self.dot.configure(text_color=self.C_GREEN)
            self.status_lbl.configure(text=f"Roblox detected  (PID {pid})")
        else:
            self.dot.configure(text_color=self.C_RED)
            self.status_lbl.configure(text="Roblox not detected")
        self.after(3000, self._poll_roblox)

    # brr brr patapim

    def _quit(self):
        if self.frozen:
            self._freeze_stop()
        self._kbl.stop()
        self._msl.stop()
        self.destroy()


if __name__ == "__main__":
    app = TabGlitchApp()
    app.mainloop()
