from instructions.AbstractInstruction import AbstractInstruction


class Color(AbstractInstruction):

    def __str__(self):
        return 'Color'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):
        environment.globals['color'] = environment.stack.pop()