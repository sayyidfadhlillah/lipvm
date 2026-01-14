class Value:

    def __init__(self, value):
        self._value = value

    def __str__(self):
        return 'Value ' + str(self._value)

    def execute(self, environment):
        environment.stack.push(self._value)