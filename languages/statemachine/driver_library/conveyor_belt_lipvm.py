from languages.statemachine.driver_library.factory_physics_simulation import MovementPhysics, Box

# ============================
# Context (Conveyor Belt)
# ============================
class ConveyorBeltLipVM:
    def __init__(
        self,
        name: str,
        start_point: float,
        end_point: float,
        weight_factor: float,
        base_speed: float,
        dt: float
    ) -> None:
        if end_point <= start_point:
            raise ValueError("end_point must be greater than start_point")
        if base_speed <= 0:
            raise ValueError("base_speed must be > 0")
        if weight_factor < 0:
            raise ValueError("weight_factor must be >= 0")
        if dt <= 0:

            raise ValueError("dt must be > 0")

        self.dt = dt
        self.name = name
        self.start_point = float(start_point)
        self.end_point = float(end_point)
        self.base_speed = float(base_speed)
        self.weight_factor = float(weight_factor)
        self._state_name = "Placeholder"
        self.boxes: list[Box] = []

    @property
    def state_name(self) -> str:
        return self._state_name

    @state_name.setter
    def state_name(self, value: str) -> None:
        self._state_name = value

    def can_accept_new_box(self, new_box: Box) -> bool:

        if self.state_name == "ERROR":
            return False
        candidate = Box(
            name=new_box.name,
            weight=new_box.weight,
            width=new_box.width,
            position=self.start_point,
        )

        for existing_box in self.boxes:
            if MovementPhysics.has_collision(candidate, existing_box):
                return False

        return True

    def load_box(self, box: Box) -> bool:

        if self.state_name == "ERROR":
            return False

        box.position = self.start_point
        self.boxes.append(box)
        self.boxes.sort(key=lambda b: b.position)

        if self.has_any_collision():
            self.set_error()
            return False

        return True

    def peek_box_at_end(self) -> Box | None:

        if self.state_name == "ERROR":
            return None
        if not self.boxes:
            return None
        self.boxes.sort(key=lambda b: b.position)
        candidate = self.boxes[-1]
        if candidate.position < self.end_point:
            return None
        return candidate

    def pop_box_at_end(self) -> Box | None:

        if self.state_name == "ERROR":
            return None
        if not self.boxes:
            return None
        self.boxes.sort(key=lambda b: b.position)
        if self.boxes[-1].position < self.end_point:
            return None
        return self.boxes.pop(-1)

    def clear_boxes(self):

        self.boxes.clear()

    def advance_boxes(self, speed: float) -> None:

        if not self.boxes:
            return

        for box in self.boxes:
            speed = MovementPhysics.effective_speed(
                base_speed=speed,
                weight_factor=self.weight_factor,
                weight=box.weight,
            )
            target_position = box.position + speed * self.dt
            box.position = min(target_position, self.end_point)

    def has_any_collision(self) -> bool:

        if len(self.boxes) < 2:
            return False

        self.boxes.sort(key=lambda b: b.position)

        for box_index in range(len(self.boxes) - 1):

            current_box = self.boxes[box_index]
            next_box = self.boxes[box_index + 1]

            if MovementPhysics.has_collision(current_box, next_box):
                return True

        return False