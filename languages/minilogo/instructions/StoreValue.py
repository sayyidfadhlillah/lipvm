from backend.instructions.AbstractInstruction import AbstractInstruction


class StoreValue(AbstractInstruction):

    def __str__(self):
        return 'StoreValue'

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):

        var_name = environment.stack.pop()
        var_value = environment.stack.pop()

        environment.store_value_in_heap(var_name, var_value)