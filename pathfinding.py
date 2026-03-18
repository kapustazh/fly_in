from __future__ import annotations
from abc import ABC, abstractmethod
from math import sqrt
from parser import ZoneTypes


class Heruistic:
    @staticmethod
    def eucl_distance(xy_one: tuple[int, int], xy_two: tuple[int, int]):
        return sqrt((xy_one[0] - xy_two[0]) ** 2) + sqrt(
            (xy_one[1] + xy_two[1]) ** 2
        )


class Node:
    def __init__(
        self, position: tuple[int, int], parent: Node | None = None
    ) -> None:
        self.position: tuple[int, int] = position
        self.parent: Node | None = parent
        self.g: float = 0.0
        self.h: float = 0.0
        self.f: float = 0.0

    def __eq__(self, other: object) -> bool:
        return (
            self.position == other.position
            if isinstance(other, Node)
            else False
        )

    def __lt__(self, other: Node) -> bool:
        if self.f == other.f:
            return self.h < other.h
        return self.f < other.f

    def __hash__(self) -> int:
        return hash(self.position)


class AStar:
    def __init__()


