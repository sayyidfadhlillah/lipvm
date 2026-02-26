import sys
from collections import deque

from antlr4 import *
from backend.interpreter import Interpreter

from languages.statemachine.LanguageParser import LanguageParser


class State:

    def __init__(self, name):
        self._name = name
        self._transitions = {}
        self._activation_function = None
        self._tick_function = None

    def __str__(self):
        return self._name

    def add_transition(self, name, state_name):
        self._transitions[name] = state_name

    def add_activation_function(self, body):
        self._activation_function = body

    def add_tick_function(self, body):
        self._tick_function = body

    @property
    def name(self):
        return self._name

    @property
    def transitions(self):
        return self._transitions

    @property
    def activation_function(self):
        return self._activation_function

    @property
    def tick_function(self):
        return self._tick_function

class Machine:

    def __init__(self, name):
        self._name = name
        self._events = []
        self._states = {}
        self._initial_state = None

    def add_event(self, name):
        self._events.append(name)

    def add_state(self, name, state):
        self._states[name] = state

    def add_initial_state(self, name):
        self._initial_state = name

    @property
    def name(self):
        return self._name

    @property
    def events(self):
        return self._events

    @property
    def states(self):
        return self._states

    @property
    def initial_state(self):
        return self._initial_state

class LanguageInterpreter(Interpreter):

    def __init__(self, parser: Parser):
        super().__init__(parser)

        # Initializing machines
        self._environment.machine = None
        self._environment.current_state = None

        # State of execution
        self._environment.sp = -1                # Scope pointer
        self._environment.scopes = [None] * 100  # Closure scopes
        self._event_queue = deque()

        # Primitives
        self._environment.primitives = {}
        self._install_primitives()
        self._driver = None
        self._exposed_driver_methods = {
            "clear_boxes",
            "advance_boxes",
            "has_any_collision",
            "set_current_state_name",
        }

    @property
    def parser(self):

        return self._parser

    def set_driver(self, driver) -> None:
        self._driver = driver

    def _install_primitives(self) -> None:
        self._environment.primitives["print"] = lambda *values: print(*values)
        self._environment.primitives["send_event"] = self.enqueue_event

    def _reset_runtime(self) -> None:
        self._event_queue.clear()
        self._halt = False
        self._environment.machine = None
        self._environment.current_state = None
        self._environment.sp = -1
        self._environment.scopes = [None] * 100

    def _run_context(self, ctx) -> None:
        if ctx is None or self._halt:
            return
        self._interpretation_stack = [self.visit(ctx)]
        self._interpretation_result = None
        self._interpretation_steps = []
        self._interpretation()

    def load_program(self, code: str) -> None:
        tree = self._parser.parse(code)
        self._reset_runtime()
        self._run_context(tree)

    def interpret(self, code: str):
        self.load_program(code)

    def enqueue_event(self, event_name) -> None:
        self._event_queue.append(str(event_name))

    def available_events(self) -> list[str]:
        if self._environment.machine is None:
            return []
        return list(self._environment.machine.events)

    def is_program_loaded(self) -> bool:
        return self._environment.machine is not None and self._environment.current_state is not None

    def current_state_name(self) -> str | None:
        if self._environment.current_state is None:
            return None
        return self._environment.current_state.name

    def pending_events(self) -> list[str]:
        return list(self._event_queue)

    def tick(self) -> None:
        if self._halt:
            return
        if self._environment.machine is None or self._environment.current_state is None:
            return

        current_state = self._environment.current_state
        if current_state.tick_function is not None:
            self._run_context(current_state.tick_function)

        if self._event_queue:
            self._handle_event(self._event_queue.popleft())

    def _handle_event(self, event_name: str) -> None:
        if self.error_exist(event_name):
            return

        target = self._environment.current_state.transitions[event_name]
        self._environment.current_state = self._environment.machine.states[target]

        if self._driver is not None:
            self._driver.set_current_state_name(self._environment.current_state.name)

        if self._environment.current_state.activation_function is not None:
            self._run_context(self._environment.current_state.activation_function)

    def visitMachine(self, ctx:LanguageParser.MachineContext):
        self._environment.machine = Machine(ctx.ID().getText())

    def visitEvents(self, ctx:LanguageParser.EventsContext):
        events = [param.getText() for param in ctx.ID()]
        for event in events:
           self._environment.machine.add_event(event)

    def visitInitial(self, ctx:LanguageParser.InitialContext):
        self._environment.machine.add_initial_state(ctx.ID().getText())

    def visitState(self, ctx:LanguageParser.StateContext):
        state = State(ctx.ID().getText())
        self._environment.machine.add_state(state.name, state)
        for transition in ctx.transition():
            tr = yield self.visit(transition)
            state.add_transition(tr[0], tr[1])

        state.add_activation_function(ctx.activate())
        state.add_tick_function(ctx.tick())

    def visitTransition(self, ctx:LanguageParser.TransitionContext):
        yield ctx.ID(0).getText(), ctx.ID(1).getText()

    def visitActivate(self, ctx:LanguageParser.ActivateContext):
        yield self.visit(ctx.body())

    def visitTick(self, ctx:LanguageParser.TickContext):
        yield self.visit(ctx.body())

    def visitConditional(self, ctx:LanguageParser.ConditionalContext):

        condition = yield self.visit(ctx.condition)

        if condition:

            yield self.visit(ctx.then_body)

        elif ctx.else_body is not None:

            yield self.visit(ctx.else_body)

    def visitDriver_call(self, ctx:LanguageParser.Driver_callContext):

        function_to_call = ctx.driverCall.ID().getText()
        arguments_node = ctx.driverCall.arguments()
        arguments = [] if arguments_node is None else (yield self.visit(arguments_node))
        if self._driver is None:
            raise Exception("No simulator driver is bound to the interpreter")
        if function_to_call not in self._exposed_driver_methods:
            raise Exception("Unsupported simulator driver method: " + function_to_call)

        driver_method = getattr(self._driver, function_to_call, None)
        if driver_method is None:
            raise Exception("Simulator driver has no method: " + function_to_call)
        yield driver_method(*arguments)

    def visitVariable(self, ctx: LanguageParser.VariableContext):
        variable_name = ctx.ID().getText()
        current_scope = self._environment.scopes[self._environment.sp]
        if current_scope is not None and variable_name in current_scope:
            yield current_scope[variable_name]
            return

        if self._environment.machine is not None and variable_name in self._environment.machine.events:
            # Allow `send_event(start)` style event identifiers.
            yield variable_name
            return

        raise Exception("Undefined variable: " + str(variable_name))

    def visitLiteral(self, ctx: LanguageParser.LiteralContext):
        if ctx.variable() is not None:
            yield self.visit(ctx.variable())
        elif ctx.STRING() is not None:
            yield ctx.STRING().getText()
        elif ctx.TRUE() is not None:
            yield True
        elif ctx.FALSE() is not None:
            yield False
        else:
            yield int(ctx.NUMBER().getText())

    def visitExpression(self, ctx: LanguageParser.ExpressionContext):
        if ctx.leftOperand is not None and ctx.rightOperand is not None:

            left = yield self.visit(ctx.leftOperand)
            right = yield self.visit(ctx.rightOperand)

            match ctx.OPERATOR().getText():
                case "+": yield left + right
                case "-": yield left - right
                case "*": yield left * right
                case "/": yield left / right
                case "&&": yield left and right
                case '||': yield left or right
                case _:
                    raise Exception("Unknown operator: " + str(ctx.OPERATOR().getText()))

        elif ctx.literal() is not None:
            yield self.visit(ctx.literal())

        elif ctx.expression(0) is not None:
            yield self.visit(ctx.expression(0))

        elif ctx.driver_call() is not None:
            yield self.visit(ctx.driver_call())

        else:
            raise Exception("Unrecognized expression: " + str(ctx))

    def visitArguments(self, ctx: LanguageParser.ArgumentsContext):
        arguments = []
        for arg_node in ctx.expression():
            arg = yield self.visit(arg_node)
            arguments.append(arg)
        yield arguments

    def visitCall(self, ctx: LanguageParser.CallContext):
        if not ctx.ID().getText() in self._environment.primitives:
            raise Exception("Undefined function: " + str(ctx.ID().getText()))

        # Get the function from the supported ones
        function = self._environment.primitives[ctx.ID().getText()]
        arguments_node = ctx.arguments()
        arguments = [] if arguments_node is None else (yield self.visit(arguments_node))

        # Execute the function
        function(*arguments)

    def visitHalt(self, ctx:LanguageParser.HaltContext):
        self.halt()

    def visitBody(self, ctx: LanguageParser.BodyContext):
        yield self.visitChildren(ctx)

    def visitAssignment(self, ctx: LanguageParser.AssignmentContext):
        self._environment.scopes[self._environment.sp][ctx.ID().getText()] = yield self.visit(ctx.expression())
        yield self._environment.scopes[self._environment.sp][ctx.ID().getText()]

    def visitForloop(self, ctx: LanguageParser.ForloopContext):
        self._open_closure()
        if ctx.assignment() is not None:
            iterator = yield self.visit(ctx.assignment())
            variable = ctx.assignment().ID().getText()
        elif ctx.variable() is not None:
            iterator = yield self.visit(ctx.variable())
            variable = ctx.variable().ID().getText()
        else:
            raise Exception("Cannot resolve iterator: " + str(ctx))

        if ctx.expression() is None:
            raise Exception("Undefined boundary in for loop: " + str(ctx))

        limit = yield self.visit(ctx.expression())
        for iterator in range(limit):
            self._environment.scopes[self._environment.sp][variable] = iterator
            yield self.visit(ctx.body())
        self._close_closure()

    def visitMain(self, ctx: LanguageParser.MainContext):
        self._environment.sp = 0
        self._environment.scopes[self._environment.sp] = {}
        yield self.visitChildren(ctx)

        if self._environment.machine is None:
            raise Exception("No state machine has been declared")
        if self._environment.machine.initial_state not in self._environment.machine.states:
            raise Exception("Initial state " + self._environment.machine.initial_state + " not defined")
        self._environment.current_state = self._environment.machine.states[self._environment.machine.initial_state]
        if self._driver is not None:
            self._driver.set_current_state_name(self._environment.current_state.name)
        if self._environment.current_state.activation_function is not None:
            yield self.visit(self._environment.current_state.activation_function)

    def error_exist(self, command: str):
        if self._environment.machine is None or self._environment.current_state is None:
            print("Machine is not initialized", file=sys.stderr)
            return True

        if command not in self._environment.machine.events:
            print("Unrecognized event: " + str(command), file=sys.stderr)
            return True

        if not command in self._environment.current_state.transitions:
            print("Cannot execute transition event \"" + str(command) + "\" from current state: " +
                  str(self._environment.current_state), file=sys.stderr)
            return True

        target = self._environment.current_state.transitions[command]
        if not target in self._environment.machine.states:
            print("Cannot execute transition event " + str(command) + " from as " + target +
                  " does not exist in the machine", file=sys.stderr)
            return True

        return False

del LanguageParser
