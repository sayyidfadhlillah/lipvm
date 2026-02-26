from __future__ import annotations

class Box:
    def __init__(
        self,
        name: str,
        weight: float,
        width: float = 0.9,
        position: float = 0.0,
    ) -> None:

        if weight < 0:
            raise ValueError("box.weight must be >= 0")

        if width <= 0:
            raise ValueError("box.width must be > 0")

        if len(name.strip()) == 0:
            raise ValueError("Name must not be an empty string")

        self._name = name
        self._weight = weight
        self._width = width
        self._position = position

    @property
    def name(self) -> str:
        return self._name

    @property
    def weight(self) -> float:
        return self._weight

    @property
    def width(self) -> float:
        return self._width

    @property
    def position(self) -> float:
        return self._position

    @position.setter
    def position(self, value: float) -> None:
        self._position = value


class MovementPhysics:
    COLLISION_EPSILON = 1e-9

    @staticmethod
    def effective_speed(base_speed: float, weight_factor: float, weight: float) -> float:
        return base_speed / (1.0 + weight_factor * weight)

    @classmethod
    def has_collision(cls, first_box: Box, second_box: Box) -> bool:
        first_back = first_box.position - (first_box.width / 2.0)
        first_front = first_box.position + (first_box.width / 2.0)
        second_back = second_box.position - (second_box.width / 2.0)
        second_front = second_box.position + (second_box.width / 2.0)

        return (first_front > second_back + cls.COLLISION_EPSILON) and (
            second_front > first_back + cls.COLLISION_EPSILON
        )
