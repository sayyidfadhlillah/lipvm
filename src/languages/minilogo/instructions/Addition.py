class Addition:

    def __str__(self):
        return 'Addition'

    def execute(self, environment):

        right_val = environment.stack.pop()
        left_val = environment.stack.pop()

        result = left_val + right_val

        environment.stack.push(result)