from antlr4 import *

from .instructions.Addition import Addition
from .instructions.ForLoopPrimitive import ForLoopPrimitive
from .instructions.Increase import Increase
from .instructions.Jump import Jump
from .instructions.JumpIfEqual import JumpIfEqual
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

import uuid

from src.instructions.Value import Value
from src.instructions.Snapshot import Snapshot
from src.Bytecode import Bytecode

class Compiler(ParseTreeVisitor):

    # New implementation
    # Adding control flow, for loop
    def visitForAssign(self, ctx:LanguageParser.ForAssignContext):

        # Evaluate the block
        self.visit(ctx.block())

        # Push the for loop instruction
        self._bytecode.add(ForLoopPrimitive())

        # Evaluate value candidate for the starting point of the loop
        self.visit(ctx.varAssignment())

        # Evaluate value candidate for the end point of the loop
        self.visit(ctx.end)

    def visitForVar(self, ctx:LanguageParser.ForVarContext):

        start_loop_identifier = uuid.uuid4().hex[:8]
        end_loop_identifier = uuid.uuid4().hex[:8]

        # Value of the loop end
        self.visit(ctx.end)

        # Identifier of the loop end
        self._bytecode.add(Value(end_loop_identifier))

        # Push instruction store value into the bytecode, to save the ending loop value
        self._bytecode.add(StoreValue())

        # Value of the loop start
        self._bytecode.add(Value(ctx.varCall.text))
        self._bytecode.add(LoadValue())

        # Identifier of the loop start
        self._bytecode.add(Value(start_loop_identifier))

        # Push instruction store value into the bytecode, to save the starting loop value
        self._bytecode.add(StoreValue())

        # Mark the instruction point to jump, this is the starting point
        starting_point_ip = self._bytecode.size() - 1

        self._bytecode.add(Value(end_loop_identifier))
        self._bytecode.add(LoadValue())

        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(LoadValue())

        jump_to_end_instruction = JumpIfEqual()

        self._bytecode.add(jump_to_end_instruction)

        # Evaluate the block
        self.visit(ctx.block())

        # Add the starting pointer by one
        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(LoadValue())
        self._bytecode.add(Increase())
        self._bytecode.add(Value(start_loop_identifier))
        self._bytecode.add(StoreValue())

        #Jump to the loop starting point
        self._bytecode.add(Jump(starting_point_ip))

        #get the loop end and patch it with that value
        ending_point_ip = self._bytecode.size() - 1
        jump_to_end_instruction.loopend_ip = ending_point_ip

    def visitBlock(self, ctx:LanguageParser.BlockContext):

        list_of_commands = ctx.subcommands

        for command in list_of_commands:

            self.visit(command)

    def visitVarAssignment(self, ctx: LanguageParser.VarAssignmentContext):

        # Evaluate value candidate
        self.visit(ctx.expression())

        # Push variable name value into the bytecode
        self._bytecode.add(Value(ctx.identifier.text))

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


        if ctx.rightVal is not None:

            # Right is a term. So, resolve that
            self.visit(ctx.rightVal)

            # Push the instruction to perform addition
            self._bytecode.add(Addition())

    def visitTerm(self, ctx:LanguageParser.TermContext):

        # Left is a factor. So, resolve that
        self.visit(ctx.leftVal)

        if ctx.rightVal is not None:
            # Right is a factor. So, resolve that
            self.visit(ctx.rightVal)

            # Push the instruction to perform multiplication
            self._bytecode.add(Multiplication())

    def visitFactor(self, ctx: LanguageParser.FactorContext):

        if ctx.ID() is not None:

            self._bytecode.add(Value(ctx.ID().getText()))
            self._bytecode.add(LoadValue())

        elif ctx.NUMBER() is not None:

            int_val = int(ctx.NUMBER().getText())
            self._bytecode.add(Value(int_val))

        else:

            self.visit(ctx.expression())

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