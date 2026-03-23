from antlr4 import *

from backend.interpreter import Interpreter
from languages.sysml_vtwo.SysMLv2Parser import SysMLv2Parser

class LanguageInterpreter(Interpreter):

    def __init__(self, parser: Parser):
        super().__init__(parser)

        # Initializing machines
        self._environment.machine = None
        self._environment.current_state = None

        # State of execution
        self._environment.sp = -1  # Scope pointer
        self._environment.scopes = [None] * 100  # Closure scopes
        self._environment.primitives = {}  # Supported primitive functions



