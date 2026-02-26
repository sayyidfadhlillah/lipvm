from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from languages.statemachine.driver_library.conveyor_belt_lipvm import ConveyorBeltLipVM
from languages.statemachine.driver_library.factory_physics_simulation import Box


# ============================
# Tkinter Visualization (One Conveyor Belt)
# ============================
class ConveyorSimulatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("One Conveyor Belt (Delivered Counter)")

        # Timing
        self.dt = 0.02
        self._job: str | None = None
        self._advance_job: str | None = None
        self._advance_pressed = False

        # Model
        self.belt: ConveyorBeltLipVM = ConveyorBeltLipVM("Belt 1", 0.0, 10.0, 0.25, 4.0, self.dt)
        self.box_serial = 0
        self.default_box_weight = 5.0
        self.default_box_width = 0.9
        self.box_delivered = 0

        # UI Vars
        self.spawn_weight_var = tk.StringVar(value=f"{self.default_box_weight:.1f}")
        self.spawn_width_var = tk.StringVar(value=f"{self.default_box_width:.1f}")

        # Canvas
        self.canvas_w = 950
        self.canvas_h = 330
        self.canvas = tk.Canvas(root, width=self.canvas_w, height=self.canvas_h, bg="white")
        self.canvas.grid(row=0, column=0, columnspan=5, padx=10, pady=10, sticky="nsew")

        # Buttons
        self.btn_clear = tk.Button(root, text="Clear Boxes", width=14, command=self.clear_boxes)
        self.btn_advance = tk.Button(root, text="Advance Boxes", width=14)
        self.btn_spawn = tk.Button(root, text="Spawn New Box", width=16, command=self.on_spawn_box)
        self.btn_advance.bind("<ButtonPress-1>", self.on_advance_press)
        self.btn_advance.bind("<ButtonRelease-1>", self.on_advance_release)

        # Layout buttons
        self.btn_clear.grid(row=1, column=2, padx=6, pady=4, sticky="w")
        self.btn_advance.grid(row=1, column=3, padx=6, pady=4, sticky="w")
        self.btn_spawn.grid(row=1, column=4, padx=6, pady=4, sticky="w")

        # Spawn inputs
        self.spawn_weight_label = tk.Label(root, text="New box weight (before spawn):")
        self.spawn_weight_entry = tk.Entry(root, textvariable=self.spawn_weight_var, width=10)
        self.spawn_width_label = tk.Label(root, text="New box width (before spawn):")
        self.spawn_width_entry = tk.Entry(root, textvariable=self.spawn_width_var, width=10)

        self.spawn_weight_label.grid(row=2, column=0, padx=(10, 4), pady=(6, 10), sticky="e")
        self.spawn_weight_entry.grid(row=2, column=1, padx=(0, 10), pady=(6, 10), sticky="w")
        self.spawn_width_label.grid(row=3, column=0, padx=(10, 4), pady=(0, 10), sticky="e")
        self.spawn_width_entry.grid(row=3, column=1, padx=(0, 10), pady=(0, 10), sticky="w")

        # Delivered label (requested attribute)
        self.delivered_var = tk.StringVar()
        self.delivered_label = tk.Label(root, textvariable=self.delivered_var, anchor="w", justify="left")
        self.delivered_label.grid(row=4, column=0, columnspan=5, padx=10, pady=(0, 2), sticky="we")

        # Info label
        self.info_var = tk.StringVar()
        self.info_label = tk.Label(root, textvariable=self.info_var, anchor="w", justify="left")
        self.info_label.grid(row=5, column=0, columnspan=5, padx=10, pady=(0, 10), sticky="we")

        # Resizing
        for c in range(5):
            root.grid_columnconfigure(c, weight=1)
        root.grid_rowconfigure(0, weight=1)

        # Drawing geometry
        self.belt_margin = 80
        self.belt_left = self.belt_margin
        self.belt_right = self.canvas_w - self.belt_margin
        self.belt_height = 52
        self.belt_y = 190
        self.box_h = 46
        self.min_box_width_px = 10

        self.draw()
        self.ensure_loop_running()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- Buttons ----------
    def clear_boxes(self) -> None:
        self.belt.clear_boxes()

    def advance_boxes(self) -> None:
        self.belt.advance_boxes(self.belt.base_speed)
        self.consume_delivered_boxes()

    def on_advance_press(self, _event: tk.Event) -> None:
        self._advance_pressed = True
        # A quick click still performs one step immediately.
        self.advance_boxes()
        self.ensure_advance_loop_running()

    def on_advance_release(self, _event: tk.Event) -> None:
        self._advance_pressed = False
        if self._advance_job is not None:
            try:
                self.root.after_cancel(self._advance_job)
            except tk.TclError:
                pass
            self._advance_job = None

    def set_current_state_name(self, new_state_name: str):

        self.belt.state_name = new_state_name

    def on_spawn_box(self) -> None:
        weight = self.get_spawn_weight()
        if weight is None:
            return
        width = self.get_spawn_width()
        if width is None:
            return

        self.box_serial += 1
        box = Box(name=f"Box-{self.box_serial}", weight=weight, width=width)
        loaded = self.belt.load_box(box)
        if not loaded:
            self.box_serial -= 1
            messagebox.showwarning("Spawn blocked", "Belt start area is occupied. Wait for space.")
            return

        self.draw()

    # ---------- Input + Slider callbacks ----------
    def get_spawn_weight(self) -> float | None:
        raw_weight = self.spawn_weight_var.get().strip()
        try:
            weight = float(raw_weight)
        except ValueError:
            messagebox.showerror("Invalid weight", "Please enter a valid number for box weight.")
            return None

        if weight < 0:
            messagebox.showerror("Invalid weight", "Box weight must be >= 0.")
            return None

        return weight

    def get_spawn_width(self) -> float | None:
        raw_width = self.spawn_width_var.get().strip()
        try:
            width = float(raw_width)
        except ValueError:
            messagebox.showerror("Invalid width", "Please enter a valid number for box width.")
            return None

        if width <= 0:
            messagebox.showerror("Invalid width", "Box width must be > 0.")
            return None

        return width

    # ---------- Loop ----------
    def ensure_loop_running(self) -> None:
        if self._job is None:
            self._job = self.root.after(int(self.dt * 1000), self.loop)

    def loop(self) -> None:
        self._job = None

        self.draw()
        self.ensure_loop_running()

    def ensure_advance_loop_running(self) -> None:
        if self._advance_job is None:
            self._advance_job = self.root.after(int(self.dt * 1000), self.advance_loop)

    def advance_loop(self) -> None:
        self._advance_job = None
        if not self._advance_pressed:
            return
        self.advance_boxes()
        self.ensure_advance_loop_running()

    def consume_delivered_boxes(self) -> None:
        while self.belt.pop_box_at_end() is not None:
            self.box_delivered += 1

    # ---------- Drawing ----------
    def draw_belt(self, belt: ConveyorBeltLipVM) -> None:
        left, right = self.belt_left, self.belt_right
        y_center = self.belt_y
        y0 = y_center - self.belt_height / 2
        y1 = y_center + self.belt_height / 2

        self.canvas.create_rectangle(left, y0, right, y1, outline="black", width=2)

        # A/B markers
        self.canvas.create_line(left, y0 - 25, left, y1 + 25, width=2)
        self.canvas.create_text(left, y0 - 40, text="A", font=("Arial", 12, "bold"))
        self.canvas.create_line(right, y0 - 25, right, y1 + 25, width=2)
        self.canvas.create_text(right, y0 - 40, text="B", font=("Arial", 12, "bold"))

        # Motion lines
        for x in range(int(left) + 10, int(right), 30):
            self.canvas.create_line(x, y_center, x + 15, y_center, width=2)

        # Label
        self.canvas.create_text(
            left,
            y0 - 10,
            text=f"{belt.name}  |  State: {belt.state_name}",
            anchor="w",
            font=("Arial", 11, "bold"),
        )
        self.canvas.create_text(
            left,
            y0 - 28,
            text=f"Base speed: {belt.base_speed:.1f} units/s",
            anchor="w",
            font=("Arial", 10),
        )

        # Boxes
        boxes = sorted(belt.boxes, key=lambda b: b.position)
        for box in boxes:
            px = self.model_to_canvas_x(belt, box.position, left, right)
            box_width_px = self.model_width_to_canvas_width(belt, box.width, left, right)

            bx0 = px - box_width_px / 2
            bx1 = px + box_width_px / 2
            by0 = y_center - self.box_h / 2
            by1 = y_center + self.box_h / 2

            self.canvas.create_rectangle(bx0, by0, bx1, by1, outline="black", width=2)
            self.canvas.create_text(px, y_center - 8, text=box.name, font=("Arial", 10, "bold"))
            self.canvas.create_text(
                px,
                y_center + 10,
                text=f"w={box.weight:.1f}, width={box.width:.1f}",
                font=("Arial", 10),
            )

    def draw(self) -> None:
        self.canvas.delete("all")

        self.draw_belt(self.belt)

        # Delivered counter (requested attribute)
        self.delivered_var.set(f"Box Delivered: {self.box_delivered}")

        # Info
        self.info_var.set(
            "Rule: effective_speed = base_speed / (1 + weight_factor * weight)"
        )

    def model_to_canvas_x(self, belt: ConveyorBeltLipVM, position: float, left: float, right: float) -> float:
        t = (position - belt.start_point) / (belt.end_point - belt.start_point)
        t = max(0.0, min(1.0, t))
        return left + t * (right - left)

    def model_width_to_canvas_width(self, belt: ConveyorBeltLipVM, width: float, left: float, right: float) -> float:
        belt_model_length = belt.end_point - belt.start_point
        belt_canvas_length = right - left
        width_px = (width / belt_model_length) * belt_canvas_length
        return max(self.min_box_width_px, width_px)

    # ---------- Shutdown ----------
    def on_close(self) -> None:
        if self._advance_job is not None:
            try:
                self.root.after_cancel(self._advance_job)
            except tk.TclError:
                pass
            self._advance_job = None
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = ConveyorSimulatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
