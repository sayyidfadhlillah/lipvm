from backend.instructions.AbstractInstruction import AbstractInstruction


class Move(AbstractInstruction):

    def __str__(self):
        return 'Move'

    def need_to_have_snapshot(self):

        return True

    def execute(self, environment):
        position = (environment.stack.pop(), environment.stack.pop())

        if 'drawing' in environment.globals and environment.globals['drawing'] and 'position' in environment.globals:

            line = (environment.globals['position'] , position, environment.globals['color'])

            if 'lines' in environment.heap:
                environment.heap['lines'].append(line)
            else:
                environment.heap['lines'] = [line]

        environment.globals['position'] = position