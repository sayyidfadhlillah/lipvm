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

        self._slider = Scale(self._buttons, from_=0, to=200, orient=HORIZONTAL, state=NORMAL, command=self.navigate)
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

    def compile(self, event):
        self._execution = self._vm.compile_code(self.code())
        self._slider.config(state=DISABLED)
        self._canvas.delete("all")

    def start(self):
        self._execution.start()
        self.draw()

        self._slider.config(state=NORMAL, to=len(self._execution.history))

    def step_forward(self):
        self._execution.step_forward()
        self.draw()

    def step_backward(self):
        self._execution.step_backward()
        self.draw()

    def navigate(self, event):
        if self._execution.environment.ip > int(event):
            self.step_backward()
        
        if self._execution.environment.ip < int(event):
            self.step_forward()

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