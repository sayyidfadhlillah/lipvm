# Generated from C:/Users/hfadhlil/PycharmProjects/lipvm/languages/statemachine/Language.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .LanguageParser import LanguageParser
else:
    from LanguageParser import LanguageParser

# This class defines a complete generic visitor for a parse tree produced by LanguageParser.

class LanguageVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by LanguageParser#machine.
    def visitMachine(self, ctx:LanguageParser.MachineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#events.
    def visitEvents(self, ctx:LanguageParser.EventsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#initial.
    def visitInitial(self, ctx:LanguageParser.InitialContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#state.
    def visitState(self, ctx:LanguageParser.StateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#transition.
    def visitTransition(self, ctx:LanguageParser.TransitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#activate.
    def visitActivate(self, ctx:LanguageParser.ActivateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#tick.
    def visitTick(self, ctx:LanguageParser.TickContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#conditional.
    def visitConditional(self, ctx:LanguageParser.ConditionalContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#variable.
    def visitVariable(self, ctx:LanguageParser.VariableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#literal.
    def visitLiteral(self, ctx:LanguageParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#driver_call.
    def visitDriver_call(self, ctx:LanguageParser.Driver_callContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#expression.
    def visitExpression(self, ctx:LanguageParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#orExpression.
    def visitOrExpression(self, ctx:LanguageParser.OrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#andExpression.
    def visitAndExpression(self, ctx:LanguageParser.AndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#additiveExpression.
    def visitAdditiveExpression(self, ctx:LanguageParser.AdditiveExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#multiplicativeExpression.
    def visitMultiplicativeExpression(self, ctx:LanguageParser.MultiplicativeExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#unaryExpression.
    def visitUnaryExpression(self, ctx:LanguageParser.UnaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#primaryExpression.
    def visitPrimaryExpression(self, ctx:LanguageParser.PrimaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#arguments.
    def visitArguments(self, ctx:LanguageParser.ArgumentsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#call.
    def visitCall(self, ctx:LanguageParser.CallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#halt.
    def visitHalt(self, ctx:LanguageParser.HaltContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#body.
    def visitBody(self, ctx:LanguageParser.BodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#assignment.
    def visitAssignment(self, ctx:LanguageParser.AssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#forloop.
    def visitForloop(self, ctx:LanguageParser.ForloopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LanguageParser#main.
    def visitMain(self, ctx:LanguageParser.MainContext):
        return self.visitChildren(ctx)



del LanguageParser