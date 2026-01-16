from tkinter import *
from tkinter import ttk

from src.Environment import Environment
from src.Execution import Execution
from src.LipVM import LipVM

class Minilogo(Tk):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Minilogo")
        self.geometry("800x600")

        self.components()
        self.bindings()
        self.layout()

        self._vm = LipVM()
        self._execution = None

    def components(self):
        self._panes = ttk.PanedWindow(self, orient=HORIZONTAL)

        self._code_pane = Frame(self._panes, bg="white")
        self._preview_pane = Frame(self._panes, bg="white")

        self._panes.add(self._code_pane, weight=1)
        self._panes.add(self._preview_pane, weight=1)

        self._code = Text(self._code_pane, width=1, height=1)

        self._canvas = Canvas(self._preview_pane, bg="white")
        self._buttons = Frame(self._preview_pane)

        # Slider represents the timeline. We keep it enabled so it can display a position
        # and (optionally) allow manual navigation too. Buttons will also move it.
        self._slider = Scale(
            self._buttons,
            from_=0,
            to=0,
            orient=HORIZONTAL,
            state=DISABLED,
            command=self.navigate
        )

        self._start_button = Button(self._buttons, text="Run", command=self.start)
        self._step_forward_button = Button(self._buttons, text="Step forward", command=self.step_forward)
        self._step_backward_button = Button(self._buttons, text="Step backward", command=self.step_backward)

    def bindings(self):
        self._code.bind("<KeyRelease>", self.compile)

    def layout(self):
        # Main layout
        self._panes.pack(fill=BOTH, expand=True)

        # Code layout
        self._code.pack(fill=BOTH, expand=True)

        # Preview layout
        self._canvas.pack(fill=BOTH, expand=True)
        self._buttons.pack(fill=X, expand=False)

        # Buttons layout
        self._buttons.grid_rowconfigure(0, weight=1)
        self._buttons.grid_rowconfigure(1, weight=1)

        self._buttons.grid_columnconfigure(0, weight=1)
        self._buttons.grid_columnconfigure(1, weight=1)
        self._buttons.grid_columnconfigure(2, weight=1)

        self._slider.grid(row=0, column=0, columnspan=3, sticky='nesw')
        self._start_button.grid(row=1, column=0, sticky='nesw')
        self._step_forward_button.grid(row=1, column=1, sticky='nesw')
        self._step_backward_button.grid(row=1, column=2, sticky='nesw')

    def code(self):
        return self._code.get('1.0', END)

    def compile(self, event=None):
        self._execution = self._vm.compile_code(self.code())

        # Reset UI + timeline
        self._canvas.delete("all")
        self._slider.config(state=DISABLED, from_=0, to=0)
        self._slider.set(0)

    def start(self):

        if not self._execution:
            return

        self._execution.start()
        self.draw()

        # Timeline range based on history length.
        # If your ip is an index into history, the max valid index is len(history)-1.
        max_step = max(0, len(self._execution.history) - 1)

        self._slider.config(state=NORMAL, from_=0, to=max_step)

        # Sync slider with current state
        self._slider.set(len(self._execution.history) - 1)

    def step_forward(self):

        self._execution.step_forward()

        target = int(float(self._slider.get())) + 1
        self._slider.set(target)

        self.draw()

    def step_backward(self):

        self._execution.step_backward()

        target = int(float(self._slider.get())) - 1
        self._slider.set(target)

        self.draw()

    def navigate(self, value):

        # If user drags the slider, apply that timeline too
        if not self._execution:
            return

    def draw(self):
        self._canvas.delete("all")
        state = self._execution.environment.heap

        if 'lines' in state:
            for line in state['lines']:
                self._canvas.create_line(
                    line[0][0],
                    line[0][1],
                    line[1][0],
                    line[1][1],
                    fill=line[2],
                    width=4
                )


Minilogo().mainloop()