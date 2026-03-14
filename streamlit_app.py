"""
Ant Farm – Streamlit UI
Run with:  streamlit run streamlit_app.py
"""

import time
import streamlit as st

# Import simulation logic (no curses needed)
from ant_farm import AntFarm, State

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Ant Farm", page_icon="🐜", layout="wide")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🐜 Ant Farm")
    ant_count  = st.slider("Number of ants",  5, 50, 15)
    food_count = st.slider("Starting food",   5, 60, 20)
    grid_w     = st.slider("Grid width",     40, 120, 80)
    grid_h     = st.slider("Grid height",    20,  60, 35)
    speed      = st.slider("Speed (ticks/frame)", 1, 10, 3)

    st.markdown("---")
    col1, col2 = st.columns(2)
    start_btn  = col1.button("▶ Start",    use_container_width=True)
    stop_btn   = col2.button("⏹ Stop",     use_container_width=True)
    reset_btn  = st.button("🔄 Reset",     use_container_width=True)
    food_btn   = st.button("🍎 +5 Food",   use_container_width=True)

    st.markdown("---")
    st.markdown("""
**Legend**
- 🟤 `C` — Colony
- 🟢 `a` — Ant (searching)
- 🟡 `@` — Ant (carrying food)
- 🔴 `*` — Food
- 🔵 `░▒▓` — Pheromone trail
""")

# ── Session state ─────────────────────────────────────────────────────────────
if "farm" not in st.session_state or reset_btn:
    st.session_state.farm     = AntFarm(width=grid_w, height=grid_h)
    st.session_state.farm.ants = []
    # Rebuild with chosen counts
    from ant_farm import Ant, FOOD_COUNT
    farm = st.session_state.farm
    farm.grid = [[__import__('ant_farm').Cell() for _ in range(grid_w)] for _ in range(grid_h)]
    farm._spawn_food(food_count)
    farm._spawn_ants(ant_count)
    st.session_state.running  = False
    st.session_state.tick_acc = 0

if start_btn:
    st.session_state.running = True
if stop_btn:
    st.session_state.running = False
if food_btn:
    st.session_state.farm._spawn_food(5)

farm: AntFarm = st.session_state.farm

# ── Metrics row ───────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Tick",         farm.tick)
m2.metric("Ants",         len(farm.ants))
m3.metric("Food at home", farm.food_carried_home)
searching = sum(1 for a in farm.ants if a.state == State.SEARCHING)
m4.metric("Carrying",     len(farm.ants) - searching)

# ── Grid renderer ─────────────────────────────────────────────────────────────
COLORS = {
    "ground":    "#1a1a2e",
    "colony":    "#e0e0e0",
    "ant_s":     "#44ff88",   # searching
    "ant_c":     "#ffdd00",   # carrying
    "food":      "#ff4444",
    "ph_low":    "#003366",
    "ph_mid":    "#005599",
    "ph_high":   "#0077cc",
}

def build_html(farm: AntFarm) -> str:
    ant_map: dict[tuple[int,int], bool] = {}  # pos -> carrying?
    for ant in farm.ants:
        key = (ant.x, ant.y)
        # If any ant at this cell is carrying, show carry colour
        ant_map[key] = ant_map.get(key, False) or ant.carried_food

    cell_size = max(6, min(12, 720 // farm.W))
    rows_html = []

    for gy in range(farm.H):
        cells = []
        for gx in range(farm.W):
            cell = farm.grid[gy][gx]

            if gx == farm.colony_x and gy == farm.colony_y:
                bg, char = COLORS["colony"], "C"
                fg = "#000"
            elif (gx, gy) in ant_map:
                carrying = ant_map[(gx, gy)]
                bg   = COLORS["ant_c"] if carrying else COLORS["ant_s"]
                char = "@" if carrying else "a"
                fg   = "#000"
            elif cell.has_food:
                bg, char, fg = COLORS["food"], "*", "#fff"
            elif cell.pheromone > 0:
                intensity = cell.pheromone / 200.0
                if intensity > 0.6:
                    bg = COLORS["ph_high"]
                elif intensity > 0.3:
                    bg = COLORS["ph_mid"]
                else:
                    bg = COLORS["ph_low"]
                char, fg = "·", "#aad4ff"
            else:
                bg, char, fg = COLORS["ground"], " ", "#333"

            cells.append(
                f'<td style="background:{bg};color:{fg};width:{cell_size}px;'
                f'height:{cell_size}px;font-size:{max(6,cell_size-2)}px;'
                f'text-align:center;vertical-align:middle;padding:0;'
                f'font-family:monospace;line-height:1;">{char}</td>'
            )
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    table = (
        '<table style="border-collapse:collapse;margin:auto;'
        'background:#1a1a2e;border:2px solid #444;">'
        + "".join(rows_html)
        + "</table>"
    )
    return f'<div style="overflow:auto;max-height:75vh;">{table}</div>'


grid_placeholder    = st.empty()
grid_placeholder.markdown(build_html(farm), unsafe_allow_html=True)

# ── Simulation loop ───────────────────────────────────────────────────────────
if st.session_state.running:
    for _ in range(speed):
        farm.update()
    time.sleep(0.05)
    grid_placeholder.markdown(build_html(farm), unsafe_allow_html=True)
    st.rerun()
