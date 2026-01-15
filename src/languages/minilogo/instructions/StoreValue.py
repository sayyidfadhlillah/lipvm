class StoreValue:

    def __str__(self):
        return 'StoreValue'

    def execute(self, environment):

        var_value = environment.stack.pop()
        var_name = environment.stack.pop()

        if var_name in environment.heap:
            environment.heap[var_name].append(var_value)
        else:
            environment.heap[var_name] = var_value