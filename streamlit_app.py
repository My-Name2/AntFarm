"""
Ant Farm – Side View
Streamlit app showing a cross-section of an ant colony.
Run with:  streamlit run streamlit_app.py
"""

import random
from dataclasses import dataclass
from enum import Enum
import streamlit as st
from PIL import Image, ImageDraw

# ── Cell types ────────────────────────────────────────────────────────────────

class Cell(Enum):
    SKY    = 0
    GRASS  = 1   # ground surface row
    DIRT   = 2   # solid underground
    TUNNEL = 3   # excavated passage
    NEST   = 4   # colony chamber

# ── Ant states ────────────────────────────────────────────────────────────────

class AntState(Enum):
    LEAVING   = "leaving"    # underground, heading up to surface
    FORAGING  = "foraging"   # on surface, hunting for food
    RETURNING = "returning"  # carrying food, heading back underground
    IN_NEST   = "in_nest"    # depositing food, then leaving again

# ── Ant ───────────────────────────────────────────────────────────────────────

@dataclass
class Ant:
    x: int
    y: int
    state: AntState = AntState.LEAVING
    has_food: bool  = False
    dx: int         = 1   # surface walk direction

# ── World ─────────────────────────────────────────────────────────────────────

class AntFarm:
    def __init__(self, width: int, height: int, ant_count: int, food_count: int):
        self.W, self.H   = width, height
        self.GROUND_Y    = max(5, height // 6)
        self.grid        = [[Cell.SKY] * width for _ in range(height)]
        self.food: set[tuple[int,int]] = set()
        self.food_stored = 0
        self.tick        = 0
        self.ants: list[Ant] = []
        self._build_world()
        self._spawn_food(food_count)
        self._spawn_ants(ant_count)

    # ── World building ────────────────────────────────────────────────────────

    def _build_world(self):
        W, H, GY = self.W, self.H, self.GROUND_Y
        cx = W // 2
        self.cx     = cx
        self.nest_y = GY + max(8, (H - GY) // 3)

        # Underground → DIRT
        for y in range(GY, H):
            for x in range(W):
                self.grid[y][x] = Cell.DIRT

        # Grass surface line
        for x in range(W):
            self.grid[GY][x] = Cell.GRASS

        # Nest chamber
        for dy in range(-2, 3):
            for dx in range(-6, 7):
                ny, nx = self.nest_y + dy, cx + dx
                if GY < ny < H and 0 <= nx < W:
                    self.grid[ny][nx] = Cell.NEST

        # Main entrance shaft (vertical, centred)
        for y in range(GY + 1, self.nest_y - 2):
            self.grid[y][cx] = Cell.TUNNEL

        # Horizontal tunnels left/right from nest
        branch = W // 4
        for dx in range(1, branch + 1):
            for bx in [cx - dx, cx + dx]:
                if 0 <= bx < W:
                    self.grid[self.nest_y][bx] = Cell.TUNNEL

        # Secondary shafts + small chambers at branch ends
        for bx in [cx - branch, cx + branch]:
            if 0 <= bx < W:
                for dy in range(1, 5):
                    ny = self.nest_y + dy
                    if ny < H:
                        self.grid[ny][bx] = Cell.TUNNEL
                for ddx in range(-2, 3):
                    sx = bx + ddx
                    ny = min(H - 1, self.nest_y + 4)
                    if 0 <= sx < W:
                        self.grid[ny][sx] = Cell.TUNNEL

        # Random rock texture variation stored as a float overlay (for colour only)
        self._dirt_shade = [
            [random.uniform(0.85, 1.15) for _ in range(W)]
            for _ in range(H)
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ok(self, x: int, y: int) -> bool:
        return 0 <= x < self.W and 0 <= y < self.H

    def _passable_surface(self, x: int, y: int) -> bool:
        return self._ok(x, y) and self.grid[y][x] in (Cell.SKY, Cell.GRASS)

    def _passable_underground(self, x: int, y: int) -> bool:
        return self._ok(x, y) and self.grid[y][x] in (Cell.TUNNEL, Cell.NEST)

    def _step_toward(self, ax, ay, tx, ty, *, underground: bool) -> tuple[int, int]:
        """One-step greedy move toward (tx, ty) through passable cells."""
        passable = self._passable_underground if underground else self._passable_surface
        ddx = 0 if ax == tx else (1 if tx > ax else -1)
        ddy = 0 if ay == ty else (1 if ty > ay else -1)

        # Ordered candidates: diagonal first, then axis-aligned, then perpendicular
        options = [
            (ax + ddx, ay + ddy),
            (ax + ddx, ay),
            (ax,       ay + ddy),
            (ax - ddy, ay + ddx),
            (ax + ddy, ay - ddx),
        ]
        for nx, ny in options:
            if passable(nx, ny):
                return nx, ny

        # Fallback: any passable neighbour
        nbrs = [(ax+dx, ay+dy) for dx in (-1,0,1) for dy in (-1,0,1)
                if (dx or dy) and passable(ax+dx, ay+dy)]
        if nbrs:
            return random.choice(nbrs)
        return ax, ay

    # ── Spawning ──────────────────────────────────────────────────────────────

    def _spawn_food(self, n: int):
        placed = tries = 0
        while placed < n and tries < n * 40:
            tries += 1
            x = random.randint(0, self.W - 1)
            y = random.randint(0, self.GROUND_Y - 1)
            if (x, y) not in self.food:
                self.food.add((x, y))
                placed += 1

    def _spawn_ants(self, n: int):
        for _ in range(n):
            x = max(0, min(self.W-1, self.cx + random.randint(-4, 4)))
            y = max(0, min(self.H-1, self.nest_y + random.randint(-1, 1)))
            self.ants.append(Ant(x=x, y=y, state=AntState.LEAVING,
                                 dx=random.choice([-1, 1])))

    # ── Ant logic ─────────────────────────────────────────────────────────────

    def _move_ant(self, ant: Ant):
        GY = self.GROUND_Y

        if ant.state == AntState.LEAVING:
            # Target one cell below grass (GY+1 = top of tunnel), then emerge
            ant.x, ant.y = self._step_toward(ant.x, ant.y, self.cx, GY + 1,
                                             underground=True)
            if ant.y == GY + 1 and ant.x == self.cx:
                ant.y   = GY          # step onto grass
                ant.state = AntState.FORAGING
                ant.dx    = random.choice([-1, 1])

        elif ant.state == AntState.FORAGING:
            # Wander the surface
            if random.random() < 0.2:
                ant.dx = random.choice([-1, -1, 1, 1, 0])
            ny = GY if random.random() > 0.35 else max(0, GY - random.randint(1, 3))
            nx = max(0, min(self.W - 1, ant.x + ant.dx))
            if self._passable_surface(nx, ny):
                ant.x, ant.y = nx, ny
            # Bounce off edges
            if ant.x in (0, self.W - 1):
                ant.dx = -ant.dx

            # Grab nearby food
            for fx, fy in list(self.food):
                if abs(fx - ant.x) <= 1 and abs(fy - ant.y) <= 1:
                    self.food.discard((fx, fy))
                    ant.has_food = True
                    ant.state    = AntState.RETURNING
                    ant.dx       = -ant.dx
                    break

        elif ant.state == AntState.RETURNING:
            if ant.y <= GY:
                # On surface: walk toward entrance column then descend
                ant.x, ant.y = self._step_toward(ant.x, ant.y, self.cx, GY,
                                                 underground=False)
                if ant.x == self.cx and ant.y == GY:
                    ant.y = GY + 1    # step into tunnel
            else:
                # Underground: head to nest
                ant.x, ant.y = self._step_toward(ant.x, ant.y, self.cx, self.nest_y,
                                                 underground=True)
                if self.grid[ant.y][ant.x] == Cell.NEST:
                    ant.state    = AntState.IN_NEST
                    ant.has_food = False
                    self.food_stored += 1

        elif ant.state == AntState.IN_NEST:
            # Rest briefly in nest, then leave again
            if random.random() < 0.15:
                ant.state = AntState.LEAVING

    # ── Digging ───────────────────────────────────────────────────────────────

    def _dig(self):
        """Randomly extend tunnels from existing tunnel edges."""
        if random.random() > 0.04:
            return
        # Sample a random underground position
        y = random.randint(self.GROUND_Y + 1, self.H - 2)
        x = random.randint(1, self.W - 2)
        if self.grid[y][x] not in (Cell.TUNNEL, Cell.NEST):
            return
        dirs = [(1, 0), (-1, 0), (0, 1)]  # sides and down, not up
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if self._ok(nx, ny) and self.grid[ny][nx] == Cell.DIRT:
                self.grid[ny][nx] = Cell.TUNNEL
                return

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self):
        self.tick += 1
        for ant in self.ants:
            self._move_ant(ant)
        self._dig()
        if self.tick % 60 == 0:
            self._spawn_food(3)


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Ant Farm", page_icon="🐜", layout="wide")

with st.sidebar:
    st.title("🐜 Ant Farm")
    ant_count  = st.slider("Ants",              5,  60, 20)
    food_count = st.slider("Starting food",     5,  60, 25)
    grid_w     = st.slider("Width",            50, 140, 90)
    grid_h     = st.slider("Height",           30,  80, 50)
    speed      = st.slider("Speed (ticks/frame)", 1, 10, 1)

    st.markdown("---")
    c1, c2 = st.columns(2)
    start_btn = c1.button("▶ Start",   width="stretch")
    stop_btn  = c2.button("⏹ Stop",    width="stretch")
    reset_btn = st.button("🔄 Reset",  width="stretch")
    food_btn  = st.button("🍎 +10 Food", width="stretch")

    st.markdown("---")
    st.markdown("""
**Legend**
- 🟦 Sky
- 🟩 Grass surface
- 🟫 Dirt (solid)
- ⬛ Tunnel (open)
- 🟨 Nest chamber
- 🔴 Food
- ⚫ Ant (searching)
- 🟡 Ant (carrying food)
""")

# ── Session state ─────────────────────────────────────────────────────────────

if "farm" not in st.session_state or reset_btn:
    st.session_state.farm    = AntFarm(grid_w, grid_h, ant_count, food_count)
    st.session_state.running = False

if start_btn: st.session_state.running = True
if stop_btn:  st.session_state.running = False
if food_btn:  st.session_state.farm._spawn_food(10)

# Store speed in session state so the fragment can read it
st.session_state.speed = speed

farm: AntFarm = st.session_state.farm

# ── Renderer ──────────────────────────────────────────────────────────────────

SCALE = 10   # pixels per cell

SKY_TOP    = (135, 206, 235)
SKY_BOT    = (176, 226, 250)
GRASS_COL  = (60,  160,  50)
DIRT_COL   = (101,  67,  33)
TUNNEL_COL = (30,   16,   6)
NEST_COL   = (160, 110,  20)
ANT_S_COL  = (10,   10,  10)
ANT_C_COL  = (255, 215,   0)
FOOD_COL   = (255,  50,  30)


def lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def render_frame(farm: AntFarm) -> Image.Image:
    W, H, GY = farm.W, farm.H, farm.GROUND_Y
    img = Image.new("RGB", (W * SCALE, H * SCALE))
    draw = ImageDraw.Draw(img)

    ant_map: dict[tuple[int,int], bool] = {}
    for ant in farm.ants:
        ant_map[(ant.x, ant.y)] = ant_map.get((ant.x, ant.y), False) or ant.has_food

    for gy in range(H):
        for gx in range(W):
            ctype = farm.grid[gy][gx]

            if ctype == Cell.SKY:
                col = lerp(SKY_TOP, SKY_BOT, gy / max(1, GY))
            elif ctype == Cell.GRASS:
                v   = (gx * 7 + gy * 3) % 20
                col = (30, 140 + v, 30)
            elif ctype == Cell.DIRT:
                s   = farm._dirt_shade[gy][gx]
                col = tuple(min(255, int(c * s)) for c in DIRT_COL)
            elif ctype == Cell.TUNNEL:
                col = TUNNEL_COL
            elif ctype == Cell.NEST:
                s   = 0.88 + 0.24 * ((gx + gy) % 2)
                col = tuple(min(255, int(c * s)) for c in NEST_COL)
            else:
                col = (0, 0, 0)

            x0, y0 = gx * SCALE, gy * SCALE
            x1, y1 = x0 + SCALE - 1, y0 + SCALE - 1
            draw.rectangle([x0, y0, x1, y1], fill=col)

            # Grass blades
            if ctype == Cell.GRASS and gx % 3 == 0:
                draw.line([x0 + SCALE//2, y0, x0 + SCALE//2, y0 + SCALE - 2],
                          fill=(40, 200, 40), width=1)

            # Food
            if (gx, gy) in farm.food:
                cx, cy = x0 + SCALE//2, y0 + SCALE//2
                r = max(2, SCALE // 3)
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=FOOD_COL)

            # Ants
            if (gx, gy) in ant_map:
                cx, cy = x0 + SCALE//2, y0 + SCALE//2
                r = max(2, SCALE // 3)
                acol = ANT_C_COL if ant_map[(gx, gy)] else ANT_S_COL
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=acol)

    return img


# ── Simulation fragment (auto-refreshes without WebSocket spam) ───────────────

@st.fragment(run_every=0.35)
def simulation_view():
    farm = st.session_state.farm
    if st.session_state.get("running"):
        spd = st.session_state.get("speed", 1)
        for _ in range(spd):
            farm.update()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tick",            farm.tick)
    m2.metric("Ants",            len(farm.ants))
    m3.metric("Food stored",     farm.food_stored)
    m4.metric("Food on surface", len(farm.food))
    m5.metric("Carrying",        sum(1 for a in farm.ants if a.has_food))
    st.image(render_frame(farm), width="stretch")

simulation_view()
