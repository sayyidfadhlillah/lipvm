from antlr4 import *

if "." in __name__:
    from .syntax.LanguageParser import LanguageParser
    from .instructions.Color import Color
    from .instructions.Move import Move
    from .instructions.StartDrawing import StartDrawing
    from .instructions.StopDrawing import StopDrawing
else:
    from languages.minilogo.syntax.LanguageParser import LanguageParser
    from languages.minilogo.instructions.Color import Color
    from languages.minilogo.instructions.Move import Move
    from languages.minilogo.instructions.StartDrawing import StartDrawing
    from languages.minilogo.instructions.StopDrawing import StopDrawing

from src.instructions.Value import Value
from src.instructions.Snapshot import Snapshot
from src.Bytecode import Bytecode

class Compiler(ParseTreeVisitor):

    def visitMove(self, ctx:LanguageParser.MoveContext):
        self._bytecode.add(Snapshot())
        self._bytecode.add(Value(int(ctx.y.text)))
        self._bytecode.add(Value(int(ctx.x.text)))
        self._bytecode.add(Move())

    def visitColor(self, ctx:LanguageParser.ColorContext):
        self._bytecode.add(Value(ctx.code.text))
        self._bytecode.add(Color())
        
    def visitDraw(self, ctx:LanguageParser.DrawContext):
        self._bytecode.add(StartDrawing())
        self.visitChildren(ctx)
        self._bytecode.add(StopDrawing())
    
    def visitStart(self, ctx:LanguageParser.StartContext):
        self.visitChildren(ctx)

    def compile(self, ast):
        self._bytecode = Bytecode()
        self.visit(ast)
        return self._bytecode