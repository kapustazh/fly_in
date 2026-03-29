# Fly-in

*This project has been created as part of the 42 curriculum by mnestere.*

## Description

**Fly-in** is a graph-based drone routing simulator with a real-time Pygame visualization. The program reads a map file that describes zones (hubs), connections, zone types, and capacity limits, then plans routes for multiple drones from a **start hub** to an **end hub** while respecting:

- **Zone type costs** — `normal`, `restricted`, `priority`, and `blocked` affect movement cost and passability.
- **Per-zone occupancy** — `max_drones` caps how many drones may occupy a zone at the same simulation turn.
- **Per-connection throughput** — `max_link_capacity` caps how many drones may use a link per turn.

The implementation has three main parts: **parsing and validation** of map files into a `GameWorld`, **capacity-aware multi-drone planning** over discrete turns (timed search with reservations), and a **layered visual simulation** so you can watch routes unfold and inspect bottlenecks. The same planner drives **textual per-turn output** (VII.5-style lines) printed to the console as the simulation clock advances.

---

## Instructions

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.11 and dependencies from `pyproject.toml`)
- A display environment suitable for Pygame (the app opens a window)

### Installation

```bash
uv sync --python 3.11
```

Or: `make install` (same command).

### Run

```bash
uv run main.py path/to/map.txt
```

Example:

```bash
uv run main.py unit_tests/test_map.txt
```

Use any map under `maps/easy`, `maps/medium`, `maps/hard`, or `maps/challenger`, or your own file in the same format.

### Makefile

All project commands go through **uv**:

| Target | Effect |
|--------|--------|
| `make install` | `uv sync --python 3.11` |
| `make run` | `uv run main.py $(ARGS)` — e.g. `make run ARGS=unit_tests/test_map.txt` |
| `make debug` | `uv run -m pdb main.py $(ARGS)` |
| `make clean` | Remove `*.py[co]`, `__pycache__`, and tool caches (mypy, pytest) |
| `make lint` | `uv run flake8` + `uv run mypy` on `*.py` |
| `make lint-strict` | Stricter `mypy` |

```bash
make install
make run ARGS=maps/easy/01_linear_path.txt
```

---

## Algorithm explanation

### Base routing — A*

`RoutePlanner` runs **A\*** on the zone graph: nodes are zone names, **bridges** are connections between zones, `g(n)` accumulates **enter cost** from zone types via `ZoneMovementModel`, and `h(n)` is **Euclidean distance** on grid coordinates. When `f` scores tie, **priority** zones are preferred.

### Why timed (space–time) search

A shortest path per drone ignores **when** each bridge is used. Conflicts appear in **time**: too many drones in one zone or on one link in the same turn. Capacity limits are **temporal**, so the planner must reason in **(zone, turn)** space, not only topology.

### Timed pathfinding

`TimedPathfinder` searches states `(zone, turn)`. From a state it can **wait** (advance time in place) or **move** along a **bridge** to a neighbor zone, spending turns according to destination zone weight (`simulation_turn_weight`). Each expansion checks **TurnCapacityTracker**: zone occupancy and link usage for the turns the move spans. Infeasible expansions are skipped. The tracker uses a priority heap with `f = g + h` consistent with the spatial model.

### Fleet strategy

`FleetRoutePlanner` plans drones **one after another** on a **shared** capacity tracker. Each drone gets a feasible timed path; its usage is **reserved** before the next drone is planned. Start and end hubs are usually exempt from occupancy caps so traffic can clear. This sequential reservation is deterministic and matches the “first planned, first reserved” interpretation of shared infrastructure.

### Simulation output

`SimulationOutput` turns **timed states** into one console line per planner turn that has at least one movement. Tokens look like `Dk-zone` when drone `k` **enters** a zone, or `Dk-from-to` while crossing a **bridge** that takes **multiple simulation turns**. Drones that do not move on a turn are omitted; output stops when every drone has reached the end zone. If a route has no timed chain, the formatter falls back to the zone path only.

### Complexity (informal)

- Static A*: on the order of `(V + B) log V` for the graph (`V` zones, `B` bridges).
- Timed search: state space grows with time horizon `T`; cost grows roughly with the product of graph size and `T`.
- Fleet: timed search runs once per drone with increasing reservation pressure.

---

## Visual representation and user experience

The renderer is built as a **stack of layers** (bottom to top) so the map stays readable while drones and UI sit on top:

| Layer | Role |
|-------|------|
| **Water** | Animated background; frames the playfield. |
| **Map** | Island and obstacle tiles; **metadata-driven tinting** reflects zone type (normal, restricted, priority, blocked). |
| **Flags** | Marks **start** and **end** hubs clearly. |
| **Drones** | Animated sprites **oriented along** the current travel direction, so motion and congestion are easy to read. |
| **Map legend** | Small reference for zone types and icons. |
| **HUD** | Turn-related feedback and high-level state (e.g. pause). |
| **Zone tooltip** | On hover, shows zone details (metadata) for inspection without cluttering the map. |
| **Help overlay** | Toggleable summary of keyboard controls. |

**UX goals:** large or dense maps stay navigable via **camera panning**; **pause** lets you freeze and study conflicts; **color and legend** tie the formal rules (zone types, hubs) to what you see; **animated drones** make multi-turn delays and queues intuitive compared to text-only output.

### Controls

| Key | Action |
|-----|--------|
| `W` / `A` / `S` / `D` or arrow keys | Pan camera |
| `SPACE` | Pause / resume simulation |
| `R` | Restart and re-plan routes |
| `H` | Toggle help overlay |
| `Q` | Quit |

---

## Example input and expected output

### Input (`unit_tests/test_map.txt`)

```txt
nb_drones: 3

start_hub: hub 1 0 [color=green]
end_hub: goal 1 15 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA1 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 10 17 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA1
connection: roof1-roof2
connection: roof2-goal
connection: corridorA1-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

### Expected console output (textual simulation lines)

After `uv run main.py unit_tests/test_map.txt`, as the in-game planner clock advances, lines similar to the following are printed (exact routes depend on the planner and capacity reservations; this matches the current sequential fleet plan):

```txt
D1-corridorA1 D2-hub-roof1
D1-tunnelB D2-roof1 D3-corridorA1
D1-goal D2-roof2 D3-tunnelB
D2-goal D3-goal
```

Each line is one **simulation turn** with movement: listed drones are those that report a position or transition that turn. The window shows the same routes as pixel motion.

---

## Project structure (reference)

| Module | Responsibility |
|--------|------------------|
| `parser.py` | Map file parsing and validation |
| `game.py` | `GameWorld` (zones, connections, start/end) |
| `routing_costs.py` | Zone costs and passability |
| `pathfinding.py` | A* `RoutePlanner` |
| `timed_pathfinding.py` | Timed search and `TurnCapacityTracker` |
| `fleet_planner.py` | Multi-drone sequential planning |
| `drone.py` | Route execution and simulation time |
| `simulation_output.py` | Per-turn line formatter |
| `render.py`, `layers.py`, `assets.py`, `sprites.py` | Pygame UI |

---

## Resources

- [Pygame documentation](https://www.pygame.org/docs/)
- [Python `heapq`](https://docs.python.org/3/library/heapq.html)
- [A* search — Wikipedia](https://en.wikipedia.org/wiki/A*_search_algorithm)
- [Space-time A* concepts](https://w9-pathfinding.readthedocs.io/stable/mapf/SpaceTimeAStar.html)
- [Silver 2005 — Cooperative Pathfinding (AAAI)](https://www.aaai.org/Papers/AAAI/2005/AAAI05-094.pdf)

### How AI was used

AI assistants were used for drafting and structuring documentation (including this README), diagrams, and wording; technical claims were checked against the source modules.
