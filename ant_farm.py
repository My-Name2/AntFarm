#!/usr/bin/env python3
"""
Ant Farm Simulation
Ants wander the grid, find food, and carry it back to the colony.
Pheromone trails guide other ants toward food sources.
"""

import curses
import random
import time
from dataclasses import dataclass, field
from enum import Enum

# ── Config ────────────────────────────────────────────────────────────────────
FOOD_COUNT       = 20
ANT_COUNT        = 15
PHEROMONE_DECAY  = 0.97   # multiplied each tick
PHEROMONE_MAX    = 200.0
FOOD_RESPAWN     = 60     # ticks between each new food item
TICK_DELAY       = 0.08   # seconds per frame


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
    state: State         = State.SEARCHING
    dx: int              = 0
    dy: int              = 0
    steps_since_turn: int = 0
    carried_food: bool   = False

    def __post_init__(self):
        self._pick_direction()

    def _pick_direction(self):
        self.dx, self.dy = random.choice(
            [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
        )
        self.steps_since_turn = 0


# ── World ─────────────────────────────────────────────────────────────────────

class AntFarm:
    def __init__(self, width: int, height: int):
        self.W = width
        self.H = height
        self.grid: list[list[Cell]] = [[Cell() for _ in range(width)] for _ in range(height)]
        self.colony_x = width  // 2
        self.colony_y = height // 2
        self.ants: list[Ant] = []
        self.food_carried_home = 0
        self.tick = 0
        self._spawn_food(FOOD_COUNT)
        self._spawn_ants(ANT_COUNT)

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.W and 0 <= y < self.H

    def _spawn_food(self, n: int):
        placed = 0
        while placed < n:
            x = random.randint(0, self.W - 1)
            y = random.randint(0, self.H - 1)
            dist = abs(x - self.colony_x) + abs(y - self.colony_y)
            if dist > 5 and not self.grid[y][x].has_food:
                self.grid[y][x].has_food = True
                placed += 1

    def _spawn_ants(self, n: int):
        for _ in range(n):
            self.ants.append(Ant(x=self.colony_x, y=self.colony_y))

    # ── Ant logic ─────────────────────────────────────────────────────────────

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
            # Wander randomly occasionally, or if direction would hit a wall
            next_x = ant.x + ant.dx
            next_y = ant.y + ant.dy
            hit_wall = not self._in_bounds(next_x, next_y)
            if hit_wall or ant.steps_since_turn > random.randint(4, 10) or random.random() < 0.15:
                ant._pick_direction()

            # Follow pheromone gradient away from colony (toward food sources):
            # prefer neighbours whose pheromone is LOWER than current cell,
            # since trails lead home — going against the gradient finds food.
            cur_ph = self.grid[ant.y][ant.x].pheromone
            best_score = -1
            best_nx, best_ny = ant.x + ant.dx, ant.y + ant.dy
            for nx, ny in self._neighbours(ant.x, ant.y):
                if not self._in_bounds(nx, ny):
                    continue
                ph = self.grid[ny][nx].pheromone
                # Score: mild pheromone presence is attractive, but avoid
                # cells much stronger than current (those lead to colony).
                if ph > 0 and ph <= cur_ph * 1.2:
                    score = ph
                else:
                    score = 0
                if score > best_score and random.random() < 0.5:
                    best_score = score
                    best_nx, best_ny = nx, ny

            # Fall back to current direction if no pheromone found
            if best_score <= 0:
                best_nx = ant.x + ant.dx
                best_ny = ant.y + ant.dy

            nx = max(0, min(self.W - 1, best_nx))
            ny = max(0, min(self.H - 1, best_ny))
            ant.x, ant.y = nx, ny

            # If we still didn't move (e.g. clamped to same cell), force new direction
            if ant.x == nx and ant.y == ny and hit_wall:
                ant._pick_direction()

            # Pick up food
            if self.grid[ant.y][ant.x].has_food:
                self.grid[ant.y][ant.x].has_food = False
                ant.state = State.CARRYING
                ant.carried_food = True
                ant._pick_direction()

        else:  # CARRYING — head home
            # Move toward colony, with small wobble
            tx, ty = self.colony_x, self.colony_y
            dx = 0 if ant.x == tx else (1 if tx > ant.x else -1)
            dy = 0 if ant.y == ty else (1 if ty > ant.y else -1)
            if random.random() < 0.15:   # wobble
                dx += random.choice([-1, 0, 1])
                dy += random.choice([-1, 0, 1])
            nx = max(0, min(self.W - 1, ant.x + (1 if dx > 0 else -1 if dx < 0 else 0)))
            ny = max(0, min(self.H - 1, ant.y + (1 if dy > 0 else -1 if dy < 0 else 0)))
            ant.x, ant.y = nx, ny

            # Deposit pheromone on path home
            cell = self.grid[ant.y][ant.x]
            cell.pheromone = min(PHEROMONE_MAX, cell.pheromone + 20.0)

            # Drop food at colony
            if ant.x == self.colony_x and ant.y == self.colony_y:
                self.food_carried_home += 1
                ant.carried_food = False
                ant.state = State.SEARCHING
                ant._pick_direction()

    def update(self):
        self.tick += 1
        for ant in self.ants:
            self._move_ant(ant)

        # Decay pheromones
        for row in self.grid:
            for cell in row:
                cell.pheromone *= PHEROMONE_DECAY
                if cell.pheromone < 0.5:
                    cell.pheromone = 0.0

        # Respawn food periodically
        if self.tick % FOOD_RESPAWN == 0:
            self._spawn_food(1)

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, stdscr):
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Build ant position map
        ant_positions: dict[tuple[int,int], list[Ant]] = {}
        for ant in self.ants:
            key = (ant.x, ant.y)
            ant_positions.setdefault(key, []).append(ant)

        for gy in range(min(self.H, h - 3)):
            for gx in range(min(self.W, w)):
                cell = self.grid[gy][gx]

                # Colony
                if gx == self.colony_x and gy == self.colony_y:
                    stdscr.addstr(gy, gx, "C", curses.color_pair(5) | curses.A_BOLD)
                    continue

                # Ants
                if (gx, gy) in ant_positions:
                    ants_here = ant_positions[(gx, gy)]
                    carrying = any(a.carried_food for a in ants_here)
                    char = "@" if carrying else "a"
                    color = curses.color_pair(3) if carrying else curses.color_pair(2)
                    stdscr.addstr(gy, gx, char, color | curses.A_BOLD)
                    continue

                # Food
                if cell.has_food:
                    stdscr.addstr(gy, gx, "*", curses.color_pair(4) | curses.A_BOLD)
                    continue

                # Pheromone trail
                if cell.pheromone > 0:
                    intensity = cell.pheromone / PHEROMONE_MAX
                    if intensity > 0.6:
                        ch, pair = "▓", 1
                    elif intensity > 0.3:
                        ch, pair = "▒", 1
                    else:
                        ch, pair = "░", 1
                    try:
                        stdscr.addstr(gy, gx, ch, curses.color_pair(pair))
                    except curses.error:
                        pass
                    continue

                stdscr.addstr(gy, gx, ".", curses.color_pair(6))

        # Status bar
        status = (
            f" Tick:{self.tick:5d}  "
            f"Ants:{ANT_COUNT}  "
            f"Food home:{self.food_carried_home:4d}  "
            f"[Q] quit  [+] more food"
        )
        try:
            stdscr.addstr(h - 2, 0, status[:w-1], curses.color_pair(5))
        except curses.error:
            pass

        legend = " a=ant  @=carrying  *=food  C=colony  ░▒▓=pheromone"
        try:
            stdscr.addstr(h - 1, 0, legend[:w-1], curses.color_pair(6))
        except curses.error:
            pass

        stdscr.refresh()


# ── Main ──────────────────────────────────────────────────────────────────────

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    -1)   # pheromone
    curses.init_pair(2, curses.COLOR_GREEN,   -1)   # ant searching
    curses.init_pair(3, curses.COLOR_YELLOW,  -1)   # ant carrying
    curses.init_pair(4, curses.COLOR_RED,     -1)   # food
    curses.init_pair(5, curses.COLOR_WHITE,   -1)   # colony / status
    curses.init_pair(6, curses.COLOR_BLACK+8, -1)   # ground (bright black)

    h, w = stdscr.getmaxyx()
    farm = AntFarm(width=w, height=h - 3)

    while True:
        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            break
        if key == ord('+'):
            farm._spawn_food(5)

        farm.update()
        farm.render(stdscr)
        time.sleep(TICK_DELAY)


if __name__ == "__main__":
    curses.wrapper(main)
