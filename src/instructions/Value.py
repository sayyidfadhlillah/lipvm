from instructions.AbstractInstruction import AbstractInstruction


class Value(AbstractInstruction):

    def __init__(self, value):
        self._value = value

    def __str__(self):
        return 'Value ' + str(self._value)

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):
        environment.stack.push(self._value)