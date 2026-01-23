from instructions.AbstractInstruction import AbstractInstruction


class LoadValue(AbstractInstruction):

    def __str__(self):
        return 'LoadValue'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):

        variable_name = environment.stack.pop()

        returned_value = environment.get_value_from_heap(variable_name)

        environment.stack.push(returned_value)