class Multiplication:

    def __str__(self):

        return 'Multiplication'

    def execute(self, environment):

        right_val = environment.stack.pop()
        left_val = environment.stack.pop()

        result = int(left_val) * (right_val)

        environment.stack.push(result)