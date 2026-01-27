from backend.instructions.AbstractInstruction import AbstractInstruction


class Subtraction(AbstractInstruction):

    def __str__(self):

        return 'Subtraction'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):

        right_val = environment.stack.pop()
        left_val = environment.stack.pop()

        result = int(left_val) - int(right_val)

        environment.stack.push(result)