class VarAssignment:

    def __str__(self):
        return 'VarAssignment'

    def execute(self, environment):

        var_value = environment.stack.pop()
        var_name = environment.stack.pop()

        environment.heap[var_name] = var_value