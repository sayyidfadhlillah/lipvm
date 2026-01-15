class LoadValue:

    def __str__(self):
        return 'LoadValue'

    def execute(self, environment):

        variable_name = environment.stack.pop()

        if variable_name in environment.heap:

            value = environment.heap[variable_name]
            environment.stack.push(value)

        else:
            raise KeyError(variable_name, " does not exist in the stack")