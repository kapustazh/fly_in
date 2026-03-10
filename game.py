from dataclasses import dataclass
from drone import DronesArmada
from typing import Dict, Any
from collections.abc import Mapping


@dataclass
class GameWorld:
    zones: Mapping[str, Dict[str, Any]]
    connections: Mapping[str, Dict[str, Any]]
    num_drones: int
    armada: DronesArmada | None
