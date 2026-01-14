class StartDrawing:

    def __str__(self):
        return 'StartDrawing'

    def execute(self, environment):
        environment.globals['drawing'] = True