class LoadValue:

    def __str__(self):
        return 'LoadValue'

    def execute(self, environment):

        variable_name = environment.stack.pop()

        returned_value = environment.get_value_from_heap(variable_name)

        environment.stack.push(returned_value)