from instructions.AbstractInstruction import AbstractInstruction


class StopDrawing(AbstractInstruction):

    def __str__(self):
        return 'StopDrawing'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):
        environment.globals['drawing'] = False