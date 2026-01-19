from instructions.AbstractInstruction import AbstractInstruction


class StartDrawing(AbstractInstruction):

    def __str__(self):
        return 'StartDrawing'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):
        environment.globals['drawing'] = True