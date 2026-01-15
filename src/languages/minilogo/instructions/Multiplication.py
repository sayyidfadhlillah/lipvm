class Multiplication:

    def __str__(self):

        return 'Multiplication'

    def execute(self, environment):

        variable_name = environment.stack.pop()

        if variable_name in environment.heap:

            value = environment.heap[variable_name]
            environment.stack.push(value)

        raise KeyError(variable_name, " does not exist in the stack")