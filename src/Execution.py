from .Environment import Environment
from .Bytecode import Bytecode
from .Stack import Stack

from .instructions.Snapshot import Snapshot

from copy import deepcopy

class Execution:

    def __init__(self, bytecode, environment, runtime_mode=True):
        self._history = []
        self._interrupt = False

        self._bytecode = bytecode
        self._environment = environment

        self._initial_environment = environment
        self._runtime_mode = runtime_mode

    def is_runtime_mode(self):

        return self._runtime_mode

    def started(self):
        return self._environment.ip > 0

    def ended(self):
        return self._environment.ip >= self._bytecode.size()

    def restart(self):
        self._history = []
        self._environment = self._initial_environment

    # def start(self):
    #     while not (self._interrupt or self.ended()):
    #         self.step_forward()
    #     self._interrupt = False

    def start(self):

        while not (self._interrupt or self.ended()):

            self.step_forward()

    def stop(self):
        if self.started():
            self._interrupt = True
        else:
            raise Exception("Trying to stop a non-running execution")

    # Execute instruction in the bytecode one step at a time
    # Each step is limited by a Snapshot instruction
    def step_forward(self):

        if self.ended():
            raise Exception("Cannot step forward an execution that has ended")

        instruction_is_a_snapshot: bool = False

        while not (self._interrupt or self.ended() or instruction_is_a_snapshot):

            instruction = self._bytecode.instructions[self._environment.ip]
            instruction_is_a_snapshot = type(instruction) is Snapshot

            if instruction_is_a_snapshot:
                self._history.append(deepcopy(self._environment))
            else:
                instruction.execute(self._environment)

            self._environment.ip += 1

    def step_backward(self):

        if self._environment.ip == 0:
            raise Exception("Cannot step backward beyond the start of an execution")

        self._environment = self._history.pop()

    @property
    def history(self):
        return self._history

    @property
    def environment(self):
        return self._environment