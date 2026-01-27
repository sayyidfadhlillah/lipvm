import sys

from antlr4 import *

from languages.minilogo.syntax.LanguageLexer import LanguageLexer
from languages.minilogo.syntax.LanguageParser import LanguageParser
from languages.minilogo.Compiler import Compiler

from backend.Environment import Environment
from backend.Execution import Execution

from io import StringIO

class LipVM:

    def __init__(self):
        self._compiler = Compiler()
        self._executions = []

    def compile(self, stream):
        lexer = LanguageLexer(stream)
        stream = CommonTokenStream(lexer)
        
        parser = LanguageParser(stream)
        parser.removeErrorListeners()

        tree = parser.start()

        if parser.getNumberOfSyntaxErrors() > 0:
            raise Exception("Syntax errors")
        
        return Execution(self._compiler.compile(tree), Environment())

    def compile_file(self, path):
        return self.compile(FileStream(path))
    
    def compile_code(self, code):
        return self.compile(InputStream(code))


if __name__ == '__main__':
    vm = LipVM()
    execution = vm.compile_file(sys.argv[1])
    execution.start()
    print(execution.environment)