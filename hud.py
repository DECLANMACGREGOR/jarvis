import tkinter as tk
import threading
import queue
import time
import math

# ── Color palette ──────────────────────────────────────────────────────────────
BG        = "#000a14"
CYAN      = "#00d4ff"
CYAN_MED  = "#0088aa"
CYAN_DIM  = "#001a2e"
ORANGE    = "#ff6600"
WHITE     = "#dff0ff"
GREEN     = "#00ff99"
RED       = "#ff3344"
GREY      = "#1a3a4a"

STATUS_COLORS = {
    "STANDBY":    CYAN_MED,
    "LISTENING":  CYAN,
    "ACTIVATED":  GREEN,
    "PROCESSING": ORANGE,
    "PERMISSION": RED,
    "SPEAKING":   GREEN,
    "ERROR":      RED,
}

W, H = 500, 620


class JarvisHUD:
    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        self._state = {
            "status": "STANDBY",
            "command": "",
            "response": "",
            "turn": 0,
        }
        self._start_time = time.monotonic()
        self._angle = 0.0
        self._scan_y = 0
        self._pulse = 0.0
        self._pulse_dir = 1
        self._root = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(self, **kwargs) -> None:
        self._q.put(kwargs)

    def close(self) -> None:
        if self._root:
            self._root.quit()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._root = tk.Tk()
        root = self._root
        root.title("J.A.R.V.I.S.")
        root.geometry(f"{W}x{H}+30+30")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.93)

        # ── Canvas ─────────────────────────────────────────────────────────────
        self._c = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
        self._c.pack()
        self._build_static()
        self._build_dynamic()

        root.after(16,  self._tick_anim)   # ~60 fps animation
        root.after(100, self._tick_queue)  # drain state updates
        root.after(500, self._tick_clock)  # clock + uptime
        root.mainloop()

    # ── Static skeleton (drawn once) ──────────────────────────────────────────

    def _build_static(self) -> None:
        c = self._c

        # Hex grid background
        self._draw_hex_grid()

        # Outer border
        c.create_rectangle(6, 6, W-6, H-6, outline=CYAN_MED, width=1, dash=(4, 6))

        # Corner brackets
        for x, y, dx, dy in [(8,8,1,1),(W-8,8,-1,1),(8,H-8,1,-1),(W-8,H-8,-1,-1)]:
            c.create_line(x, y, x+dx*22, y,        fill=CYAN, width=2)
            c.create_line(x, y, x,        y+dy*22, fill=CYAN, width=2)

        # Header bar
        c.create_rectangle(8, 8, W-8, 50, fill="#001020", outline=CYAN_MED, width=1)
        c.create_text(28, 29, text="◈  J.A.R.V.I.S.", fill=CYAN,
                      font=("Courier", 15, "bold"), anchor="w")

        # Arc reactor frame
        cx, cy = W // 2, 165
        c.create_oval(cx-68, cy-68, cx+68, cy+68, outline=CYAN_MED, width=1, dash=(2,4))
        c.create_oval(cx-52, cy-52, cx+52, cy+52, outline=CYAN_DIM, width=1)

        # Section labels
        for y_pos, label in [(310, "INPUT"), (430, "RESPONSE")]:
            c.create_line(14, y_pos, W-14, y_pos, fill=CYAN_MED, width=1)
            c.create_rectangle(14, y_pos-10, 14+len(label)*8+12, y_pos+2,
                                fill=BG, outline="")
            c.create_text(20, y_pos-4, text=f" {label} ", fill=CYAN_MED,
                          font=("Courier", 9), anchor="w")

        # Footer divider
        c.create_line(14, H-42, W-14, H-42, fill=CYAN_MED, width=1, dash=(2, 4))

    def _draw_hex_grid(self) -> None:
        c = self._c
        r = 18
        h_hex = r * math.sqrt(3)
        w_hex = 2 * r
        cols = int(W / (w_hex * 0.75)) + 2
        rows = int(H / h_hex) + 2
        for row in range(rows):
            for col in range(cols):
                x = col * w_hex * 0.75 - 10
                y = row * h_hex + (h_hex / 2 if col % 2 else 0) - 10
                pts = []
                for i in range(6):
                    a = math.pi / 180 * (60 * i - 30)
                    pts.extend([x + r * math.cos(a), y + r * math.sin(a)])
                c.create_polygon(pts, outline="#001830", fill="", width=1)

    # ── Dynamic elements (tags for easy updates) ──────────────────────────────

    def _build_dynamic(self) -> None:
        c = self._c

        # Clock (top-right header)
        c.create_text(W-16, 29, text="00:00:00", fill=CYAN_MED,
                      font=("Courier", 11), anchor="e", tags="clock")

        # Arc reactor rotating ring (8 spokes)
        cx, cy = W // 2, 165
        self._reactor_cx = cx
        self._reactor_cy = cy
        for i in range(8):
            c.create_line(cx, cy, cx, cy, fill=CYAN, width=2, tags=f"spoke{i}")
        c.create_oval(cx-8, cy-8, cx+8, cy+8, fill=CYAN_DIM, outline=CYAN,
                      width=2, tags="reactor_core")
        c.create_oval(cx-28, cy-28, cx+28, cy+28, fill="", outline=CYAN,
                      width=2, tags="reactor_ring")

        # Scanning line
        c.create_line(14, 60, W-14, 60, fill=CYAN_DIM, width=1, tags="scanline")

        # Status box
        c.create_rectangle(W//2-110, 246, W//2+110, 272,
                            fill=CYAN_DIM, outline=CYAN_MED, width=1, tags="status_bg")
        c.create_text(W//2, 259, text="● STANDBY", fill=CYAN,
                      font=("Courier", 12, "bold"), tags="status_text")

        # Input text
        c.create_text(20, 330, text="", fill=WHITE, font=("Courier", 10),
                      anchor="nw", width=W-40, tags="cmd_text")

        # Response text
        c.create_text(20, 450, text="", fill=WHITE, font=("Courier", 10),
                      anchor="nw", width=W-40, tags="resp_text")

        # Footer: turn + uptime
        c.create_text(20, H-20, text="TURN: 000", fill=CYAN_MED,
                      font=("Courier", 10), anchor="w", tags="turn_text")
        c.create_text(W-20, H-20, text="UPTIME: 00:00:00", fill=CYAN_MED,
                      font=("Courier", 10), anchor="e", tags="uptime_text")

    # ── Animation tick (~60fps) ────────────────────────────────────────────────

    def _tick_anim(self) -> None:
        c = self._c
        cx, cy = self._reactor_cx, self._reactor_cy

        # Rotate spokes
        self._angle += 1.5
        for i in range(8):
            a = math.radians(self._angle + i * 45)
            r_inner, r_outer = 12, 44
            x1 = cx + r_inner * math.cos(a)
            y1 = cy + r_inner * math.sin(a)
            x2 = cx + r_outer * math.cos(a)
            y2 = cy + r_outer * math.sin(a)
            c.coords(f"spoke{i}", x1, y1, x2, y2)

        # Pulse reactor ring
        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        alpha = int(0x44 + self._pulse * 0xBB)
        ring_color = f"#{alpha:02x}d4ff" if alpha <= 0xFF else CYAN
        # clamp hex
        r_hex = min(255, int(0x44 + self._pulse * 0xBB))
        ring_color = f"#{r_hex:02x}d4ff"
        c.itemconfig("reactor_ring", outline=ring_color)

        # Scanning line
        status = self._state["status"]
        if status in ("LISTENING", "PROCESSING"):
            self._scan_y += 3
            scan_top = 60
            scan_bot = H - 50
            if self._scan_y > scan_bot:
                self._scan_y = scan_top
            c.coords("scanline", 14, self._scan_y, W-14, self._scan_y)
            c.itemconfig("scanline", fill=CYAN_DIM)
        else:
            c.itemconfig("scanline", fill="")

        self._root.after(16, self._tick_anim)

    # ── Queue drain (100ms) ────────────────────────────────────────────────────

    def _tick_queue(self) -> None:
        changed = False
        while not self._q.empty():
            updates = self._q.get()
            self._state.update(updates)
            changed = True
        if changed:
            self._apply_state()
        self._root.after(100, self._tick_queue)

    def _apply_state(self) -> None:
        c = self._c
        s = self._state
        status = s["status"]
        color = STATUS_COLORS.get(status, CYAN)

        c.itemconfig("status_text", text=f"● {status}", fill=color)
        c.itemconfig("status_bg", outline=color)

        cmd = s["command"]
        c.itemconfig("cmd_text", text=f"> {cmd}" if cmd else "")

        resp = s["response"]
        # Truncate long responses to keep HUD clean
        if len(resp) > 220:
            resp = resp[:217] + "..."
        c.itemconfig("resp_text", text=f"> {resp}" if resp else "")

        c.itemconfig("turn_text", text=f"TURN: {s['turn']:03d}")

    # ── Clock tick (500ms) ─────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = time.strftime("%H:%M:%S")
        elapsed = int(time.monotonic() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, sec = divmod(rem, 60)
        uptime = f"{h:02d}:{m:02d}:{sec:02d}"
        self._c.itemconfig("clock", text=now)
        self._c.itemconfig("uptime_text", text=f"UPTIME: {uptime}")
        self._root.after(500, self._tick_clock)


# ── Module-level singleton ─────────────────────────────────────────────────────

_hud: JarvisHUD | None = None


def start() -> JarvisHUD:
    global _hud
    _hud = JarvisHUD()
    return _hud


def update(**kwargs) -> None:
    if _hud:
        _hud.update(**kwargs)
