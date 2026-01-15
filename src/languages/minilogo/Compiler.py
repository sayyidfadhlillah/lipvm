from antlr4 import *

from .instructions.Addition import Addition
from .instructions.Expression import Expression
from .instructions.ForLoopPrimitive import ForLoopPrimitive
from .instructions.LoadValue import LoadValue
from .instructions.Multiplication import Multiplication
from .instructions.StoreValue import StoreValue

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

    # New implementation
    # Adding control flow, for loop
    def visitForAssign(self, ctx:LanguageParser.ForAssignContext):

        # Evaluate value candidate for the starting point of the loop
        self.visit(ctx.varAssignment())

        # Evaluate value candidate for the end point of the loop
        self.visit(ctx.end)

        # Evaluate the block
        self.visit(ctx.block())

        # Push the for loop instruction
        self._bytecode.add(ForLoopPrimitive())

    def visitForVar(self, ctx:LanguageParser.ForVarContext):

        # Since this is calling a variable name, we can directly load value as the starting point of the loop
        self._bytecode.add(LoadValue())

        # Evaluate value candidate for the end point of the loop
        self.visit(ctx.end)

        # Evaluate the block
        self.visit(ctx.block())

        #Push the for loop instruction
        self._bytecode.add(ForLoopPrimitive())

    def visitBlock(self, ctx:LanguageParser.BlockContext):

        list_of_commands = ctx.subcommands

        for command in list_of_commands:

            self.visit(command)

    def visitVarAssignment(self, ctx: LanguageParser.VarAssignmentContext):

        # Evaluate value candidate
        self.visit(ctx.expression())

        # Push variable name value into the bytecode
        self._bytecode.add(Value(ctx.identifier))

        # Push instruction store value into the bytecode
        self._bytecode.add(StoreValue())

    def visitMove(self, ctx:LanguageParser.MoveContext):

        # In original implementation, movement is only represented by integers
        # Now, it uses an expression that might be a result from arithmetic operation with integers or
        # value of a particular variable
        # self._bytecode.add(Value(int(ctx.y.text)))
        # self._bytecode.add(Value(int(ctx.x.text)))

        self._bytecode.add(Snapshot())
        self.visit(ctx.x)
        self.visit(ctx.y)
        self._bytecode.add(Move())

    def visitExpression(self, ctx: LanguageParser.ExpressionContext):

        #Left is a term. So, resolve that
        self.visit(ctx.leftVal)

        # Right is a term. So, resolve that
        self.visit(ctx.rightVal)

        # Push the instruction to perform addition
        self._bytecode.add(Addition())

    def visitTerm(self, ctx:LanguageParser.TermContext):

        # Left is a factor. So, resolve that
        self.visit(ctx.leftVal)

        # Right is a factor. So, resolve that
        self.visit(ctx.rightVal)

        # Push the instruction to perform multiplication
        self._bytecode.add(Multiplication())

    def visitFactor(self, ctx: LanguageParser.FactorContext):

        if ctx.ID() is not None:

            self._bytecode.add(LoadValue())

        elif ctx.NUMBER() is not None:

            self._bytecode.add(Value(ctx.NUMBER()))

        else:

            self.visit(ctx.expression())


    def visitFactor(self, ctx:LanguageParser.FactorContext):
        return self.visitChildren(ctx)

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