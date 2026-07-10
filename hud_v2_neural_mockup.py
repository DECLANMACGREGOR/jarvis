"""jarvis_hud_v2_neural.py — Neural Constellation HUD, mockup.

Standalone PyQt6 window. Cycles through IDLE -> THINKING -> EXECUTING ->
SPEAKING -> IDLE automatically (with occasional MEMORY_WRITE bursts) so
you can see the visual language before wiring it into brain.py/tools.py.

Run:  C:\\jv\\Scripts\\python.exe hud_v2_neural_mockup.py
Exit: close the window, or press Ctrl+C in the terminal.

Real integration plan (once approved):
- Replace _run_demo_step() with signals emitted from brain.think() and
  tools.dispatch() — one signal per state change / tool fire / memory write.
- Replace TOOLS/faces/memory seed data with live introspection of
  tools.TOOL_DEFINITIONS, memory.load(), vision.known_names().
- Keep this file as the "presentation" layer; JARVIS emits events, the
  constellation just visualizes them.
"""

import math
import random
import sys
from enum import Enum

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget


WIDTH, HEIGHT = 1000, 760
CX, CY = WIDTH // 2, HEIGHT // 2 + 20  # nudge down so header has breathing room
FPS = 60
DT_MS = 1000 // FPS


# ── Palette ───────────────────────────────────────────────────────────
BG        = QColor(4, 8, 18)
CORE_CYAN = QColor(0, 210, 255)
CORE_GREEN= QColor(80, 255, 180)
CORE_AMBER= QColor(255, 170, 60)
TOOL_C    = QColor(60, 200, 240)
TOOL_HOT  = QColor(220, 255, 255)
MEM_C     = QColor(255, 210, 100)
FACE_C    = QColor(200, 130, 255)
EDGE_C    = QColor(0, 210, 255)
TEXT_C    = QColor(200, 230, 255)
DIM_C     = QColor(90, 130, 170)


class State(Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    MEMORY = "MEMORY WRITE"
    SPEAKING = "SPEAKING"


# ── Orbit radii ───────────────────────────────────────────────────────
INNER_R = 150  # tools
MID_R   = 245  # memories
OUTER_R = 325  # enrolled faces

TOOLS = [
    "search", "camera", "calendar", "gmail",
    "vault", "code", "memory", "open",
]


# ── Node types (dumb geometry holders; painting done in the view) ─────

class ToolNode:
    def __init__(self, name, angle):
        self.name = name
        self.angle = angle
        self.orbit_speed = 0.0004
        self.excitation = 0.0  # 0..1, glow when considered
        self.firing = 0.0      # 0..1, hot flash when actually invoked

    def pos(self):
        return QPointF(CX + INNER_R * math.cos(self.angle),
                       CY + INNER_R * math.sin(self.angle))

    def step(self):
        self.angle += self.orbit_speed
        self.excitation *= 0.94
        self.firing *= 0.90


class MemoryStar:
    def __init__(self, angle, radius):
        self.angle = angle
        self.radius = radius
        self.size = random.uniform(1.5, 3.0)
        self.orbit_speed = random.uniform(-0.0003, 0.0003)
        self.drift_phase = random.uniform(0, math.tau)
        self.age = 1.0        # <1 = spawning; grows to 1
        self.brightness = random.uniform(0.6, 1.0)

    def pos(self):
        # Slight elliptical wobble so the ring doesn't feel mechanical.
        r = self.radius + math.sin(self.drift_phase) * 5
        return QPointF(CX + r * math.cos(self.angle),
                       CY + r * math.sin(self.angle))

    def step(self):
        self.angle += self.orbit_speed
        self.drift_phase += 0.01
        if self.age < 1.0:
            self.age = min(1.0, self.age + 0.02)


class FaceNode:
    def __init__(self, initials, angle):
        self.initials = initials
        self.angle = angle
        self.orbit_speed = 0.00015

    def pos(self):
        return QPointF(CX + OUTER_R * math.cos(self.angle),
                       CY + OUTER_R * math.sin(self.angle))

    def step(self):
        self.angle += self.orbit_speed


class Edge:
    """Center-to-tool reasoning line, grows in then out."""
    def __init__(self, target_tool):
        self.target = target_tool
        self.strength = 0.0
        self.growing = True

    def step(self):
        if self.growing:
            self.strength = min(1.0, self.strength + 0.06)
        else:
            self.strength = max(0.0, self.strength - 0.04)

    @property
    def dead(self):
        return not self.growing and self.strength <= 0


class Ripple:
    def __init__(self, origin, color):
        self.origin = QPointF(origin)
        self.color = color
        self.radius = 0.0
        self.alpha = 1.0

    def step(self):
        self.radius += 4
        self.alpha = max(0.0, self.alpha - 0.025)

    @property
    def dead(self):
        return self.alpha <= 0


class BgStar:
    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.size = random.uniform(0.3, 1.6)
        self.twinkle = random.uniform(0, math.tau)

    def step(self):
        self.twinkle += 0.02


# ── The constellation view ────────────────────────────────────────────

class ConstellationView(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH, HEIGHT)
        self.setStyleSheet(
            f"background-color: rgb({BG.red()},{BG.green()},{BG.blue()});"
        )

        # Seed nodes
        self.tools = [ToolNode(name, i * (math.tau / len(TOOLS)))
                      for i, name in enumerate(TOOLS)]
        self.memories = [
            MemoryStar(random.uniform(0, math.tau),
                       random.uniform(MID_R - 30, MID_R + 30))
            for _ in range(16)
        ]
        # Sample enrolled faces — replace with vision.known_names()
        self.faces = [FaceNode("DM", 0.0),
                      FaceNode("EM", math.tau / 3),
                      FaceNode("GR", 2 * math.tau / 3)]
        self.edges = []
        self.ripples = []
        self.bg_stars = [BgStar() for _ in range(80)]

        # State
        self.state = State.IDLE
        self.state_color = CORE_CYAN
        self.status_text = ""
        self.activity_log = []  # last handful of executed tools
        self.pulse_t = 0.0
        self.grid_angle = 0.0

        # Demo cycler
        self.demo_frame = 0

        # Frame timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(DT_MS)

    # ── Demo state machine ────────────────────────────────────────
    # ~12 seconds per "conversation" cycle. Real HUD replaces this
    # entire method with slots connected to brain/tools signals.
    def _run_demo_step(self):
        self.demo_frame += 1
        cycle = self.demo_frame % 720

        if cycle == 60:
            self._set_state(State.THINKING, "Considering approach...")
            for t in random.sample(self.tools, 3):
                t.excitation = 1.0
                self.edges.append(Edge(t))
        elif cycle == 240:
            for e in self.edges:
                e.growing = False
        elif cycle == 280:
            firing = random.choice(self.tools)
            self._set_state(State.EXECUTING, f"Executing {firing.name}")
            firing.firing = 1.0
            firing.excitation = 1.0
            self.ripples.append(Ripple(firing.pos(), TOOL_HOT))
            self.activity_log.append(firing.name)
            if len(self.activity_log) > 5:
                self.activity_log.pop(0)
        elif cycle == 360 and random.random() < 0.45:
            self._set_state(State.MEMORY, "Saving to memory")
            new_star = MemoryStar(random.uniform(0, math.tau),
                                  random.uniform(MID_R - 30, MID_R + 30))
            new_star.age = 0.0
            new_star.brightness = 1.0
            self.memories.append(new_star)
            self.ripples.append(Ripple(QPointF(CX, CY), MEM_C))
        elif cycle == 440:
            self._set_state(State.SPEAKING, "Responding...")
        elif cycle == 620:
            self._set_state(State.IDLE, "")

    def _set_state(self, state, text):
        self.state = state
        self.status_text = text
        self.state_color = {
            State.IDLE:      CORE_CYAN,
            State.THINKING:  CORE_AMBER,
            State.EXECUTING: CORE_AMBER,
            State.MEMORY:    MEM_C,
            State.SPEAKING:  CORE_GREEN,
        }[state]

    # ── Frame tick ────────────────────────────────────────────────
    def _tick(self):
        self._run_demo_step()
        self.pulse_t += 0.03
        self.grid_angle += 0.0008
        for t in self.tools: t.step()
        for m in self.memories: m.step()
        for f in self.faces: f.step()
        for e in self.edges: e.step()
        for r in self.ripples: r.step()
        for s in self.bg_stars: s.step()
        self.edges   = [e for e in self.edges   if not e.dead]
        self.ripples = [r for r in self.ripples if not r.dead]
        self.update()

    # ── Painting ──────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        self._paint_bg_stars(p)
        self._paint_orbit_rings(p)
        self._paint_angular_grid(p)
        self._paint_edges(p)
        self._paint_faces(p)
        self._paint_memories(p)
        self._paint_tools(p)
        self._paint_ripples(p)
        self._paint_center(p)
        self._paint_chrome(p)

    def _paint_bg_stars(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        for s in self.bg_stars:
            twinkle = (math.sin(s.twinkle) + 1) / 2
            alpha = int(50 + twinkle * 110)
            p.setBrush(QColor(180, 200, 230, alpha))
            p.drawEllipse(QPointF(s.x, s.y), s.size, s.size)

    def _paint_orbit_rings(self, p):
        p.setPen(QPen(QColor(EDGE_C.red(), EDGE_C.green(), EDGE_C.blue(), 28), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for r in (INNER_R, MID_R, OUTER_R):
            p.drawEllipse(QPointF(CX, CY), r, r)

    def _paint_angular_grid(self, p):
        # 12 faint radial guide lines rotating slowly — subtle "compass".
        p.setPen(QPen(QColor(EDGE_C.red(), EDGE_C.green(), EDGE_C.blue(), 14), 1))
        for i in range(12):
            a = self.grid_angle + i * (math.tau / 12)
            x = CX + math.cos(a) * (OUTER_R + 20)
            y = CY + math.sin(a) * (OUTER_R + 20)
            p.drawLine(QPointF(CX, CY), QPointF(x, y))

    def _paint_edges(self, p):
        center = QPointF(CX, CY)
        for e in self.edges:
            target = e.target.pos()
            alpha = int(180 * e.strength)
            p.setPen(QPen(QColor(EDGE_C.red(), EDGE_C.green(),
                                 EDGE_C.blue(), alpha), 1.5))
            dx = target.x() - center.x()
            dy = target.y() - center.y()
            end = QPointF(center.x() + dx * e.strength,
                          center.y() + dy * e.strength)
            p.drawLine(center, end)

    def _paint_tools(self, p):
        for t in self.tools:
            pos = t.pos()
            # Blend cyan -> hot white based on firing intensity
            base = QColor(
                int(TOOL_C.red()   + (TOOL_HOT.red()   - TOOL_C.red())   * t.firing),
                int(TOOL_C.green() + (TOOL_HOT.green() - TOOL_C.green()) * t.firing),
                int(TOOL_C.blue()  + (TOOL_HOT.blue()  - TOOL_C.blue())  * t.firing),
            )
            glow_r = 22 + t.excitation * 14 + t.firing * 22
            grad = QRadialGradient(pos, glow_r)
            grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 200))
            grad.setColorAt(0.45, QColor(base.red(), base.green(), base.blue(), 70))
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(pos, glow_r, glow_r)
            core_r = 5 + t.firing * 3
            p.setBrush(QBrush(base))
            p.drawEllipse(pos, core_r, core_r)
            # Label just outside the ring
            p.setPen(QPen(TEXT_C))
            p.setFont(QFont("Consolas", 8))
            angle = math.atan2(pos.y() - CY, pos.x() - CX)
            lx = pos.x() + math.cos(angle) * 22
            ly = pos.y() + math.sin(angle) * 22 + 3
            w = p.fontMetrics().horizontalAdvance(t.name)
            p.drawText(int(lx - w / 2), int(ly), t.name)

    def _paint_memories(self, p):
        p.setPen(Qt.PenStyle.NoPen)
        for m in self.memories:
            pos = m.pos()
            size = m.size * m.age * m.brightness
            alpha = int(200 * m.brightness * m.age)
            grad = QRadialGradient(pos, size * 3.5)
            grad.setColorAt(0, QColor(MEM_C.red(), MEM_C.green(), MEM_C.blue(), alpha))
            grad.setColorAt(1, QColor(MEM_C.red(), MEM_C.green(), MEM_C.blue(), 0))
            p.setBrush(QBrush(grad))
            p.drawEllipse(pos, size * 3.5, size * 3.5)
            p.setBrush(QBrush(QColor(MEM_C.red(), MEM_C.green(),
                                     MEM_C.blue(), alpha)))
            p.drawEllipse(pos, size, size)

    def _paint_faces(self, p):
        for f in self.faces:
            pos = f.pos()
            p.setPen(QPen(QColor(FACE_C.red(), FACE_C.green(),
                                 FACE_C.blue(), 170), 1.5))
            p.setBrush(QBrush(QColor(FACE_C.red(), FACE_C.green(),
                                     FACE_C.blue(), 45)))
            p.drawEllipse(pos, 15, 15)
            p.setPen(QPen(TEXT_C))
            p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            w = p.fontMetrics().horizontalAdvance(f.initials)
            p.drawText(int(pos.x() - w / 2), int(pos.y() + 4), f.initials)

    def _paint_ripples(self, p):
        p.setBrush(Qt.BrushStyle.NoBrush)
        for r in self.ripples:
            p.setPen(QPen(QColor(r.color.red(), r.color.green(),
                                 r.color.blue(), int(180 * r.alpha)), 1.5))
            p.drawEllipse(r.origin, r.radius, r.radius)

    def _paint_center(self, p):
        breath = (math.sin(self.pulse_t) + 1) / 2
        c = self.state_color
        # Outer halo
        halo_r = 68 + breath * 22
        grad = QRadialGradient(QPointF(CX, CY), halo_r)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 180))
        grad.setColorAt(0.35, QColor(c.red(), c.green(), c.blue(), 70))
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(CX, CY), halo_r, halo_r)
        # Core sphere
        core_r = 20 + breath * 4
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(CX, CY), core_r, core_r)
        # Inner sparkle
        p.setBrush(QBrush(QColor(255, 255, 255, int(190 * breath))))
        p.drawEllipse(QPointF(CX, CY), 5, 5)

    def _paint_chrome(self, p):
        # ── Header ──
        p.setPen(QPen(TEXT_C))
        p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        p.drawText(30, 32, "◈ J.A.R.V.I.S. // NEURAL CONSTELLATION")
        # State + subtitle
        p.setPen(QPen(self.state_color))
        p.setFont(QFont("Consolas", 11))
        p.drawText(30, 56, f"◉ {self.state.value}")
        if self.status_text:
            p.setPen(QPen(DIM_C))
            p.drawText(30, 74, self.status_text)

        # ── Top-right telemetry (weather / calendar / counts) ──
        p.setPen(QPen(DIM_C))
        p.setFont(QFont("Consolas", 9))
        lines_tr = [
            "OCEANPORT, NJ · 72°F · overcast",
            "next event: (none)",
            f"tools {len(self.tools)}  ·  memories {len(self.memories)}  ·  people {len(self.faces)}",
        ]
        for i, ln in enumerate(lines_tr):
            w = p.fontMetrics().horizontalAdvance(ln)
            p.drawText(WIDTH - 30 - w, 32 + i * 18, ln)

        # ── Bottom activity trail ──
        p.setPen(QPen(DIM_C))
        p.setFont(QFont("Consolas", 9))
        p.drawText(30, HEIGHT - 30, "ACTIVITY  ›")
        for i, name in enumerate(reversed(self.activity_log[-5:])):
            fade = 255 - i * 42
            p.setPen(QPen(QColor(TEXT_C.red(), TEXT_C.green(),
                                 TEXT_C.blue(), fade)))
            p.drawText(120 + i * 105, HEIGHT - 30, name)
        p.setPen(QPen(DIM_C))
        p.setFont(QFont("Consolas", 9))
        p.drawText(WIDTH - 160, HEIGHT - 30, "DEMO ● 60 FPS")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — Neural Constellation (mockup)")
        self.setFixedSize(WIDTH, HEIGHT)
        self.setCentralWidget(ConstellationView())


def main():
    app = QApplication(sys.argv)
    # Optional --test flag: launch, render one frame, exit — for smoke testing.
    if "--test" in sys.argv:
        win = MainWindow()
        win.show()
        QTimer.singleShot(300, app.quit)
    else:
        win = MainWindow()
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
