import sys
from tkinter import *
from tkinter import filedialog, messagebox

from backend.LipVM import LipVM
from backend.parser import ParserException

FILETYPES = [
    ("State Machine Models", "*.statemachine"),
    ("All files", "*.*"),
]

class StateMachineIDE(Tk):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.geometry("800x600")
        self._file_path = None
        self._dirty = False

        self.components()
        self.layout()
        self.bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.exit_app)
        self._update_title()
        self._vm = LipVM("languages.statemachine")

    def components(self):
        self._menu = Menu(self)
        self.config(menu=self._menu)

        self._file_menu = Menu(self._menu, tearoff=0)
        self._file_menu.add_command(label="New", accelerator="Ctrl+N", command=self.new_file)
        self._file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file)
        self._file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        self._file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_as_file)
        self._file_menu.add_separator()
        self._file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self.exit_app)
        self._menu.add_cascade(label="File", menu=self._file_menu)

        self._edit_menu = Menu(self._menu, tearoff=0)
        self._edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        self._edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: self._code.event_generate("<<Cut>>"))
        self._edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: self._code.event_generate("<<Copy>>"))
        self._edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: self._code.event_generate("<<Paste>>"))
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.select_all)
        self._menu.add_cascade(label="Edit", menu=self._edit_menu)

        self._scrollbar = Scrollbar(self)
        self._code = Text(self, width=1, height=1, undo=True, yscrollcommand=self._scrollbar.set)
        self._scrollbar.config(command=self._code.yview)
        self._code.bind("<<Modified>>", self.on_modified)
        self._code.edit_modified(False)

    def layout(self):
        self._scrollbar.pack(side=RIGHT, fill=Y)
        self._code.pack(fill=BOTH, expand=True)

    def code(self):
        return self._code.get('1.0', END)

    def bind_shortcuts(self):
        self.bind("<Control-n>", self.new_file)
        self.bind("<Control-o>", self.open_file)
        self.bind("<Control-s>", self.save_file)
        self.bind("<Control-Shift-S>", self.save_as_file)
        self.bind("<Control-a>", self.select_all)
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-y>", self.redo)

    def on_modified(self, _event=None):
        if self._code.edit_modified():
            self._dirty = True
            self._update_title()
            self._code.edit_modified(False)

    def _update_title(self):
        name = self._file_path if self._file_path else "Untitled"
        dirty_mark = "*" if self._dirty else ""
        self.title(f"{dirty_mark}{name} - State Machine IDE")

    def _content(self):
        return self._code.get("1.0", "end-1c")

    def _set_content(self, content):
        self._code.delete("1.0", END)
        self._code.insert("1.0", content)
        self._code.edit_modified(False)

    def _confirm_discard_changes(self):
        if not self._dirty:
            return True

        name = self._file_path if self._file_path else "Untitled"
        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            f"Save changes to {name}?"
        )
        if answer is None:
            return False
        if answer:
            return self.save_file()
        return True

    def new_file(self, _event=None):
        if not self._confirm_discard_changes():
            return "break"
        self._set_content("")
        self._file_path = None
        self._dirty = False
        self._update_title()
        return "break"

    def open_file(self, _event=None):
        if not self._confirm_discard_changes():
            return "break"

        path = filedialog.askopenfilename(
            filetypes=FILETYPES
        )
        if not path:
            return "break"

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            messagebox.showerror("Open File", f"Could not open file:\n{exc}")
            return "break"

        self._set_content(content)
        self._file_path = path
        self._dirty = False
        self._update_title()
        return "break"

    def interpret(self, code: str):

        try:
            self._vm.interpreter.interpret(code)
        except ParserException as e:
            print(str(e), file=sys.stderr)

    def save_file(self, _event=None):
        if not self._file_path:
            return self.save_as_file()

        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(self._content())
            self.interpret(self._content())
        except OSError as exc:
            messagebox.showerror("Save File", f"Could not save file:\n{exc}")
            return False

        self._dirty = False
        self._update_title()
        return True

    def save_as_file(self, _event=None):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=FILETYPES
        )
        if not path:
            return False
        self._file_path = path
        return self.save_file()

    def exit_app(self, _event=None):
        if not self._confirm_discard_changes():
            return "break"
        self.destroy()
        return "break"

    def select_all(self, _event=None):
        self._code.tag_add(SEL, "1.0", END)
        self._code.mark_set(INSERT, "1.0")
        self._code.see(INSERT)
        return "break"

    def undo(self, _event=None):
        try:
            self._code.edit_undo()
        except TclError:
            pass
        return "break"

    def redo(self, _event=None):
        try:
            self._code.edit_redo()
        except TclError:
            pass
        return "break"

if __name__ == '__main__':
    StateMachineIDE().mainloop()
