class Color:

    def __str__(self):
        return 'Color'

    def execute(self, environment):
        environment.globals['color'] = environment.stack.pop()