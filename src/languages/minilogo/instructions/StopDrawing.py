class StopDrawing:

    def __str__(self):
        return 'StopDrawing'

    def execute(self, environment):
        environment.globals['drawing'] = False