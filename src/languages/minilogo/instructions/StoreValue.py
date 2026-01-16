class StoreValue:

    def __str__(self):
        return 'StoreValue'

    def execute(self, environment):

        var_name = environment.stack.pop()
        var_value = environment.stack.pop()

        environment.store_value_in_heap(var_name, var_value)