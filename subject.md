# Fly-in Project Overview

This **Fly‑in** project is a Python-based drone routing simulator created for the 42
curriculum.  The goal is to route a fleet of drones from a *start hub* to an *end hub*
across a network of interconnected zones while respecting a comprehensive rule set.

## Key Concepts

- **Zone types** (`normal`, `blocked`, `restricted`, `priority`) affect movement cost
  and access.
- **Metadata** supports colors, per-zone `max_drones`, and per-connection
  `max_link_capacity`.
- **Parser** reads `.txt` maps containing hub definitions, connections, comments,
  and the number of drones.
- **Turn-based movement** allows drones to wait, move, or traverse multi-turn
  (restricted) links.
- **Capacity constraints** on zones and connections forbid overcrowding and
  blocked-zone entry.
- **Pathfinding** must minimize total simulation turns, balance traffic across
  routes, and prevent collisions or deadlocks.
- **Visualization** is provided via Pygame and/or colored terminal output.
- **Output format**: each simulation turn prints moves like
  `D1-roof1 D2-corridorA`.
- **Scoring targets** span easy (≤10 turns) to hard/challenger maps (≤60 turns,
  with a bonus 41-turn record).

## Repository Structure

- `parser.py` – builds zone/connection data structures and drone count.
- `assets.py` – singleton‑free asset manager for sprites and fonts.
- `render.py` & `layers.py` – Pygame renderer with layered drawing.
- `game.py` – `GameWorld` containing the graph, drone armada, and occupancy
  indexes.
- `drone.py` – drone entity model and `DronesArmada` manager.

## Design Goals

Create a fully typed, object‑oriented, flake8/mypy-compliant simulator capable of
handling arbitrary maps, enforcing all cost and capacity rules, and laying the
foundation for advanced pathfinding logic.  The architecture emphasizes
dependency injection, clear separation of concerns, and extensibility.


