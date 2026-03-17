from abc import ABC, abstractmethod
from math import sqrt


class Heruistic:
    @staticmethod
    def eucl_distance(xy_one: tuple[int, int], xy_two: tuple[int, int]):
        return sqrt((xy_one[0] - xy_two[0]) ** 2) + sqrt(
            (xy_one[1] + xy_two[1]) ** 2
        )


class Graph:
    pass


class Pathfinding(ABC):
    @abstractmethod
    # def find_path(self) -> deque: ...

if __name__ == "__name__":
    ...
