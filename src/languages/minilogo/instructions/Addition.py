class Addition:

    def __str__(self):
        return 'Addition'

    def execute(self, environment):

        right_val = environment.stack.pop()
        left_val = environment.stack.pop()

        result = int(left_val) + int(right_val)

        environment.stack.push(result)