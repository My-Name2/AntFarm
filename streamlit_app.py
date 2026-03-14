"""
Ant Farm – Streamlit UI (self-contained)
Run with:  streamlit run streamlit_app.py
"""

import random
import time
from dataclasses import dataclass
from enum import Enum

import streamlit as st

# ── Simulation ────────────────────────────────────────────────────────────────

PHEROMONE_DECAY = 0.97
PHEROMONE_MAX   = 200.0
FOOD_RESPAWN    = 60


class State(Enum):
    SEARCHING = "search"
    CARRYING  = "carry"


@dataclass
class Cell:
    pheromone: float = 0.0
    has_food: bool   = False


@dataclass
class Ant:
    x: int
    y: int
    state: State          = State.SEARCHING
    dx: int               = 0
    dy: int               = 0
    steps_since_turn: int = 0
    carried_food: bool    = False

    def __post_init__(self):
        self._pick_direction()

    def _pick_direction(self):
        self.dx, self.dy = random.choice(
            [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
        )
        self.steps_since_turn = 0


class AntFarm:
    def __init__(self, width: int, height: int, ant_count: int, food_count: int):
        self.W = width
        self.H = height
        self.grid: list[list[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]
        self.colony_x = width  // 2
        self.colony_y = height // 2
        self.ants: list[Ant] = []
        self.food_carried_home = 0
        self.tick = 0
        self._spawn_food(food_count)
        self._spawn_ants(ant_count)

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.W and 0 <= y < self.H

    def _spawn_food(self, n: int):
        placed = 0
        attempts = 0
        while placed < n and attempts < n * 20:
            attempts += 1
            x = random.randint(0, self.W - 1)
            y = random.randint(0, self.H - 1)
            dist = abs(x - self.colony_x) + abs(y - self.colony_y)
            if dist > 5 and not self.grid[y][x].has_food:
                self.grid[y][x].has_food = True
                placed += 1

    def _spawn_ants(self, n: int):
        for _ in range(n):
            self.ants.append(Ant(x=self.colony_x, y=self.colony_y))

    def _neighbours(self, x: int, y: int):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self._in_bounds(nx, ny):
                    yield nx, ny

    def _move_ant(self, ant: Ant):
        ant.steps_since_turn += 1

        if ant.state == State.SEARCHING:
            # Pick a new direction if about to hit a wall or time to wander
            next_x = ant.x + ant.dx
            next_y = ant.y + ant.dy
            hit_wall = not self._in_bounds(next_x, next_y)
            if hit_wall or ant.steps_since_turn > random.randint(4, 10) or random.random() < 0.15:
                ant._pick_direction()

            # Follow pheromone gradient away from colony (toward food):
            # prefer neighbours with mild pheromone (not stronger than current),
            # since return trails converge at the colony — going against them finds food.
            cur_ph = self.grid[ant.y][ant.x].pheromone
            best_score = -1
            best_nx, best_ny = ant.x + ant.dx, ant.y + ant.dy
            for nx, ny in self._neighbours(ant.x, ant.y):
                ph = self.grid[ny][nx].pheromone
                if ph > 0 and ph <= cur_ph * 1.2:
                    score = ph
                else:
                    score = 0
                if score > best_score and random.random() < 0.5:
                    best_score = score
                    best_nx, best_ny = nx, ny

            if best_score <= 0:
                best_nx = ant.x + ant.dx
                best_ny = ant.y + ant.dy

            nx = max(0, min(self.W - 1, best_nx))
            ny = max(0, min(self.H - 1, best_ny))
            ant.x, ant.y = nx, ny

            # If still stuck at edge, force a new direction next tick
            if hit_wall and ant.x == nx and ant.y == ny:
                ant._pick_direction()

            # Pick up food
            if self.grid[ant.y][ant.x].has_food:
                self.grid[ant.y][ant.x].has_food = False
                ant.state = State.CARRYING
                ant.carried_food = True
                ant._pick_direction()

        else:  # CARRYING — head home
            tx, ty = self.colony_x, self.colony_y
            dx = 0 if ant.x == tx else (1 if tx > ant.x else -1)
            dy = 0 if ant.y == ty else (1 if ty > ant.y else -1)
            if random.random() < 0.15:
                dx += random.choice([-1, 0, 1])
                dy += random.choice([-1, 0, 1])
            nx = max(0, min(self.W - 1, ant.x + (1 if dx > 0 else -1 if dx < 0 else 0)))
            ny = max(0, min(self.H - 1, ant.y + (1 if dy > 0 else -1 if dy < 0 else 0)))
            ant.x, ant.y = nx, ny

            cell = self.grid[ant.y][ant.x]
            cell.pheromone = min(PHEROMONE_MAX, cell.pheromone + 20.0)

            if ant.x == self.colony_x and ant.y == self.colony_y:
                self.food_carried_home += 1
                ant.carried_food = False
                ant.state = State.SEARCHING
                ant._pick_direction()

    def update(self):
        self.tick += 1
        for ant in self.ants:
            self._move_ant(ant)

        for row in self.grid:
            for cell in row:
                cell.pheromone *= PHEROMONE_DECAY
                if cell.pheromone < 0.5:
                    cell.pheromone = 0.0

        if self.tick % FOOD_RESPAWN == 0:
            self._spawn_food(1)


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Ant Farm", page_icon="🐜", layout="wide")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🐜 Ant Farm")
    ant_count  = st.slider("Number of ants",       5,  50, 15)
    food_count = st.slider("Starting food",         5,  60, 20)
    grid_w     = st.slider("Grid width",           40, 120, 80)
    grid_h     = st.slider("Grid height",          20,  60, 35)
    speed      = st.slider("Speed (ticks/frame)",   1,  10,  3)

    st.markdown("---")
    col1, col2 = st.columns(2)
    start_btn = col1.button("▶ Start",  use_container_width=True)
    stop_btn  = col2.button("⏹ Stop",   use_container_width=True)
    reset_btn = st.button("🔄 Reset",   use_container_width=True)
    food_btn  = st.button("🍎 +5 Food", use_container_width=True)

    st.markdown("---")
    st.markdown("""
**Legend**
- ⬜ `C` — Colony
- 🟢 `a` — Ant (searching)
- 🟡 `@` — Ant (carrying food)
- 🔴 `*` — Food
- 🔵 `·` — Pheromone trail
""")

# ── Session state ─────────────────────────────────────────────────────────────
if "farm" not in st.session_state or reset_btn:
    st.session_state.farm    = AntFarm(grid_w, grid_h, ant_count, food_count)
    st.session_state.running = False

if start_btn:
    st.session_state.running = True
if stop_btn:
    st.session_state.running = False
if food_btn:
    st.session_state.farm._spawn_food(5)

farm: AntFarm = st.session_state.farm

# ── Metrics ───────────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Tick",         farm.tick)
m2.metric("Ants",         len(farm.ants))
m3.metric("Food at home", farm.food_carried_home)
carrying = sum(1 for a in farm.ants if a.carried_food)
m4.metric("Carrying",     carrying)

# ── Grid renderer ─────────────────────────────────────────────────────────────
COLORS = {
    "ground":  "#1a1a2e",
    "colony":  "#e0e0e0",
    "ant_s":   "#44ff88",
    "ant_c":   "#ffdd00",
    "food":    "#ff4444",
    "ph_low":  "#003366",
    "ph_mid":  "#005599",
    "ph_high": "#0077cc",
}


def build_html(farm: AntFarm) -> str:
    ant_map: dict[tuple[int, int], bool] = {}
    for ant in farm.ants:
        ant_map[(ant.x, ant.y)] = ant_map.get((ant.x, ant.y), False) or ant.carried_food

    cell_px = max(6, min(12, 720 // farm.W))
    rows = []
    for gy in range(farm.H):
        cells = []
        for gx in range(farm.W):
            cell = farm.grid[gy][gx]
            if gx == farm.colony_x and gy == farm.colony_y:
                bg, ch, fg = COLORS["colony"], "C", "#000"
            elif (gx, gy) in ant_map:
                c = ant_map[(gx, gy)]
                bg, ch, fg = (COLORS["ant_c"], "@", "#000") if c else (COLORS["ant_s"], "a", "#000")
            elif cell.has_food:
                bg, ch, fg = COLORS["food"], "*", "#fff"
            elif cell.pheromone > 0:
                t = cell.pheromone / PHEROMONE_MAX
                bg = COLORS["ph_high"] if t > 0.6 else COLORS["ph_mid"] if t > 0.3 else COLORS["ph_low"]
                ch, fg = "·", "#aad4ff"
            else:
                bg, ch, fg = COLORS["ground"], " ", "#333"

            cells.append(
                f'<td style="background:{bg};color:{fg};width:{cell_px}px;height:{cell_px}px;'
                f'font-size:{max(6, cell_px - 2)}px;text-align:center;vertical-align:middle;'
                f'padding:0;font-family:monospace;line-height:1;">{ch}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")

    table = (
        '<table style="border-collapse:collapse;margin:auto;background:#1a1a2e;border:2px solid #444;">'
        + "".join(rows) + "</table>"
    )
    return f'<div style="overflow:auto;max-height:75vh;">{table}</div>'


grid_slot = st.empty()
grid_slot.markdown(build_html(farm), unsafe_allow_html=True)

# ── Simulation loop ───────────────────────────────────────────────────────────
if st.session_state.running:
    for _ in range(speed):
        farm.update()
    time.sleep(0.05)
    grid_slot.markdown(build_html(farm), unsafe_allow_html=True)
    st.rerun()
