from instructions.AbstractInstruction import AbstractInstruction


class Increase(AbstractInstruction):

    def __str__(self):

        return 'Increase'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):

        curr_value = environment.stack.pop()
        environment.stack.push(curr_value+1)