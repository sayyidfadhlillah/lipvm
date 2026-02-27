import os
import socket
import sys
import time
from importlib import import_module
from tkinter import *
from tkinter import filedialog, messagebox

from backend.LipVM import LipVM
from backend.parser import ParserException
from languages.statemachine.LanguageInterpreter import LanguageInterpreter as StateMachineInterpreter

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
        self._interval_ms = 200
        self._interval_job = None
        self._rpc_check_interval_s = 1.0
        self._rpc_probe_timeout_s = 0.2
        self._last_rpc_check_at = 0.0
        self._rpc_connected = False
        self._rpc_host = ""
        self._rpc_port = ""
        self._client = None
        self._last_tick_error = None

        self.components()
        self.layout()
        self.bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.exit_app)
        self._update_title()

        # LipVM Definition
        self._vm = LipVM("languages.statemachine")
        self._interpreter: StateMachineInterpreter = self._vm.interpreter
        self._interpreter.set_driver(None)
        self._initialize_rpc_client()
        self.start_interval_loop()

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
        self._rpc_status = Label(self, anchor=W, text="RPC: Disconnected")

    def layout(self):
        self._rpc_status.pack(side=BOTTOM, fill=X)
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

    def _set_rpc_status(self, connected: bool, error: str | None = None):
        self._rpc_connected = connected
        if connected:
            self._rpc_status.config(
                text=f"RPC: Connected ({self._rpc_host}:{self._rpc_port})",
                fg="darkgreen"
            )
        else:
            message = "RPC: Disconnected"
            if error:
                message = f"{message} ({error})"
            self._rpc_status.config(text=message, fg="firebrick")

    def _initialize_rpc_client(self):
        self._rpc_host = os.environ.get("SIMULATION_RPC_CLIENT_HOST", "")
        self._rpc_port = os.environ.get("SIMULATION_RPC_CLIENT_PORT", "")
        module = os.environ.get("SIMULATION_RPC_CLIENT_MODULE", "")

        if not self._rpc_host or not self._rpc_port or not module:
            self._set_rpc_status(False, "missing RPC environment variables")
            return

        try:
            client_port = int(self._rpc_port)
            simulation_rpc_client = getattr(import_module(module + ".Simulator"), "SimulationJsonRpcClient")
            self._client = simulation_rpc_client(host=self._rpc_host, port=client_port)
            self._refresh_rpc_connection()
        except Exception as exc:
            self._client = None
            self._interpreter.set_driver(None)
            self._set_rpc_status(False, str(exc))

    def _refresh_rpc_connection(self):
        if self._client is None:
            self._interpreter.set_driver(None)
            self._set_rpc_status(False)
            return

        try:
            port = int(self._rpc_port)
            # Use a short TCP probe to avoid blocking the UI event loop on RPC calls.
            with socket.create_connection((self._rpc_host, port), timeout=self._rpc_probe_timeout_s):
                pass
            self._interpreter.set_driver(self._client)
            self._set_rpc_status(True)
            self._last_tick_error = None
        except Exception as exc:
            self._interpreter.set_driver(None)
            self._set_rpc_status(False, str(exc))

    def start_interval_loop(self):
        if self._interval_job is not None:
            self.after_cancel(self._interval_job)
        self._interval_job = self.after(self._interval_ms, self._interval_tick)

    def _interval_tick(self):
        self.on_interval()
        self._interval_job = self.after(self._interval_ms, self._interval_tick)

    def on_interval(self):
        # Implement periodic IDE behavior here. This runs every 200ms.
        now = time.monotonic()
        if now - self._last_rpc_check_at >= self._rpc_check_interval_s:
            self._last_rpc_check_at = now
            self._refresh_rpc_connection()
        try:
            self._interpreter.tick()
            self._last_tick_error = None
        except Exception as exc:
            self._set_rpc_status(False, str(exc))
            error_text = str(exc)
            if error_text != self._last_tick_error:
                print(error_text, file=sys.stderr)
                self._last_tick_error = error_text

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
            self._set_content(content)
            self._file_path = path
            self._dirty = False
            self._update_title()
            # When opening a file, the interpreter is automatically executed
            self._vm.interpreter.interpret(self._content())
        except OSError as exc:
            messagebox.showerror("Open File", f"Could not open file:\n{exc}")
            return "break"
        except ParserException as e:
            print(str(e), file=sys.stderr)
            return False
        except Exception as e:
            self._set_rpc_status(False, str(e))
            print(str(e), file=sys.stderr)
            return False

        return "break"

    def save_file(self, _event=None):
        if not self._file_path:
            return self.save_as_file()

        try:
            # The state machine should comply to the syntax before it can be saved
            self._vm.interpreter.interpret(self._content())
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(self._content())
            self._dirty = False
            self._update_title()
            return True

        except ParserException as e:
            print(str(e), file=sys.stderr)
            return False

        except OSError as exc:
            messagebox.showerror("Save File", f"Could not save file:\n{exc}")
            return False
        except Exception as e:
            self._set_rpc_status(False, str(e))
            print(str(e), file=sys.stderr)
            return False

        return False

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
        if self._interval_job is not None:
            self.after_cancel(self._interval_job)
            self._interval_job = None
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
